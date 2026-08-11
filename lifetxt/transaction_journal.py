"""Durable recovery journal for compensated multi-target mutations.

The multi-target layer can compensate failures observed in the current process, but
it cannot recover a process or machine crash without durable evidence.  This module
stores exact before/after artifacts plus a small versioned JSON journal using fsync-
ordered writes.  Recovery is explicit: resume, compensate, abandon with backup, or
export evidence.  A target is never overwritten when its current hash matches neither
the recorded before nor after revision.
"""

from __future__ import unicode_literals

import datetime
import json
import os
import shutil
import tempfile
import time
import uuid
from collections import OrderedDict

from . import mutation
from .atomic import (
    _REPLACE_PERMISSION_RETRY_DELAYS_SECONDS,
    _REPLACE_PERMISSION_RETRY_OS_NAMES,
)
from .mutation import FileLock, MISSING_HASH, MutationConflict
from .transaction_policy import (
    build_integrity_manifest,
    enforce_capacity,
    ensure_evidence_storage_profile,
    fault_point,
    permission_report,
    policy_from_config,
    storage_access_diagnostic,
    version_compatibility,
    verify_integrity_manifest,
    write_integrity_manifest,
)
from .timeutil import parse_iso_datetime


SCHEMA_VERSION = 1
TERMINAL_STATES = frozenset(("committed", "compensated", "abandoned"))
RECOVERY_STATES = frozenset(
    (
        "prepared",
        "committing",
        "compensating",
        "recovery_required",
        "resume_failed",
        "compensation_failed",
    )
)


class TransactionJournalError(RuntimeError):
    pass


class TransactionJournalConflict(TransactionJournalError):
    def __init__(self, path, expected_before, expected_after, actual, action):
        self.path = os.path.abspath(path)
        self.expected_before = expected_before
        self.expected_after = expected_after
        self.actual = actual
        self.action = action
        TransactionJournalError.__init__(
            self,
            "%s cannot continue for %s: current hash %s matches neither before %s "
            "nor after %s. Inspect the target and choose an explicit recovery action."
            % (action, self.path, actual, expected_before, expected_after),
        )


def utc_now_text(now=None):
    value = now or datetime.datetime.now(datetime.timezone.utc)
    if value.tzinfo is None:
        value = value.replace(tzinfo=datetime.timezone.utc)
    return (
        value.astimezone(datetime.timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def journal_directory(config=None, writable_path=None):
    config = config or {}
    section = (
        config.get("transactions")
        if isinstance(config.get("transactions"), dict)
        else {}
    )
    configured = os.environ.get("LIFETXT_TRANSACTION_JOURNAL_DIR") or section.get(
        "journal_dir"
    )
    if configured:
        return os.path.abspath(os.path.expanduser(str(configured)))
    if writable_path:
        return os.path.join(
            os.path.dirname(os.path.abspath(writable_path)), ".lifetxt-transactions"
        )
    return os.path.abspath(os.path.join(".cache", "lifetxt", "transactions"))


def transaction_id(value=None):
    raw = str(value or uuid.uuid4().hex).strip()
    if not raw or any(
        ch not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_"
        for ch in raw
    ):
        raise ValueError(
            "transaction_id may contain only letters, digits, dash, and underscore."
        )
    return raw


def prepare(
    operation,
    staged_rows,
    journal_dir,
    transaction_id_value=None,
    now=None,
    config=None,
    policy=None,
):
    """Persist exact before/after artifacts and return a journal handle."""
    txid = transaction_id(transaction_id_value)
    root = os.path.abspath(journal_dir)
    resolved_policy = policy or policy_from_config(config)
    ensure_evidence_storage_profile(root, policy=resolved_policy, create=True)
    estimated = 4096
    for row in staged_rows:
        estimated += len(_before_bytes(row))
        if not row["plan"].delete:
            estimated += len(row.get("replacement_bytes") or b"")
    enforce_capacity(root, resolved_policy, estimated_bytes=estimated)
    tx_dir = os.path.join(root, txid)
    if os.path.exists(tx_dir):
        raise TransactionJournalError("Transaction journal already exists: %s" % tx_dir)
    fault_point("before_transaction_directory", path=tx_dir, operation=operation)
    os.makedirs(tx_dir, mode=0o700, exist_ok=False)
    try:
        os.chmod(tx_dir, 0o700)
    except OSError:
        pass
    _fsync_directory(root)
    fault_point("after_transaction_directory", path=tx_dir, operation=operation)
    targets = []
    for index, row in enumerate(staged_rows):
        plan = row["plan"]
        before_bytes = _before_bytes(row)
        after_bytes = row.get("replacement_bytes") if not plan.delete else None
        before_artifact = None
        after_artifact = None
        if row["before"].exists:
            before_artifact = "before-%03d.bin" % index
            fault_point("before_before_artifact", path=plan.path, index=index)
            _write_bytes_durable(os.path.join(tx_dir, before_artifact), before_bytes)
            fault_point("after_before_artifact", path=plan.path, index=index)
        if not plan.delete:
            after_artifact = "after-%03d.bin" % index
            fault_point("before_after_artifact", path=plan.path, index=index)
            _write_bytes_durable(
                os.path.join(tx_dir, after_artifact), after_bytes or b""
            )
            fault_point("after_after_artifact", path=plan.path, index=index)
        targets.append(
            OrderedDict(
                (
                    ("index", index),
                    ("path", plan.path),
                    ("kind", plan.kind),
                    ("before_hash", row["before"].content_hash),
                    ("after_hash", row["after_hash"]),
                    ("changed", bool(row["changed"])),
                    ("created", bool(not row["before"].exists and not plan.delete)),
                    ("deleted", bool(plan.delete and row["before"].exists)),
                    ("before_artifact", before_artifact),
                    ("after_artifact", after_artifact),
                    ("commit_state", "pending"),
                    ("compensation_state", "pending"),
                    ("last_error", None),
                )
            )
        )
    created = utc_now_text(now)
    record = OrderedDict(
        (
            ("schema_version", SCHEMA_VERSION),
            ("transaction_id", txid),
            ("operation", str(operation or "multi_target")),
            ("state", "prepared"),
            ("created_at_utc", created),
            ("updated_at_utc", created),
            ("terminal_at_utc", None),
            ("last_error", None),
            ("targets", targets),
        )
    )
    path = os.path.join(tx_dir, "journal.json")
    fault_point("before_journal_publish", path=path, transaction_id=txid)
    _write_json_durable(path, record)
    fault_point("after_journal_publish", path=path, transaction_id=txid)
    return TransactionJournal(path)


class TransactionJournal(object):
    def __init__(self, path):
        self.path = os.path.abspath(path)
        self.directory = os.path.dirname(self.path)

    def load(self):
        return load_record(self.path)

    def update(self, transform, now=None):
        record = self.load()
        replacement = transform(record)
        if replacement is None:
            replacement = record
        replacement["updated_at_utc"] = utc_now_text(now)
        validate_record(replacement, self.path)
        _write_json_durable(self.path, replacement)
        return replacement

    def set_state(self, state, error=None, now=None):
        def transform(record):
            record["state"] = str(state)
            record["last_error"] = None if error is None else str(error)
            if state in TERMINAL_STATES:
                record["terminal_at_utc"] = utc_now_text(now)
            return record

        return self.update(transform, now=now)

    def mark_target(
        self, index, commit_state=None, compensation_state=None, error=None, now=None
    ):
        def transform(record):
            target = record["targets"][int(index)]
            if commit_state is not None:
                target["commit_state"] = str(commit_state)
            if compensation_state is not None:
                target["compensation_state"] = str(compensation_state)
            target["last_error"] = None if error is None else str(error)
            return record

        return self.update(transform, now=now)


def load_record(path, allow_newer_read_only=False):
    try:
        with open(path, "r", encoding="utf-8") as handle:
            record = json.load(handle, object_pairs_hook=OrderedDict)
    except (OSError, ValueError) as exc:
        raise TransactionJournalError(
            "Cannot read transaction journal %s: %s" % (path, exc)
        )
    validate_record(record, path, allow_newer_read_only=allow_newer_read_only)
    return record


def validate_record(record, path=None, allow_newer_read_only=False):
    source = path or "<journal>"
    if not isinstance(record, dict):
        raise TransactionJournalError(
            "Transaction journal root must be an object: %s" % source
        )
    required = (
        "schema_version",
        "transaction_id",
        "operation",
        "state",
        "created_at_utc",
        "updated_at_utc",
        "targets",
    )
    missing = [name for name in required if name not in record]
    if missing:
        raise TransactionJournalError(
            "Transaction journal %s is missing %s." % (source, ", ".join(missing))
        )
    compatibility = version_compatibility(record, SCHEMA_VERSION)
    if compatibility["state"] == "invalid":
        raise TransactionJournalError(
            "Invalid transaction journal schema version in %s." % source
        )
    if compatibility["state"] != "current" and not (
        allow_newer_read_only and compatibility["state"] == "newer"
    ):
        raise TransactionJournalError(
            "Unsupported transaction journal schema version %r in %s."
            % (record.get("schema_version"), source)
        )
    if not isinstance(record.get("targets"), list) or not record["targets"]:
        raise TransactionJournalError(
            "Transaction journal must contain at least one target: %s" % source
        )
    seen = set()
    for index, target in enumerate(record["targets"]):
        if not isinstance(target, dict):
            raise TransactionJournalError(
                "Target %d in %s must be an object." % (index, source)
            )
        for name in (
            "path",
            "kind",
            "before_hash",
            "after_hash",
            "commit_state",
            "compensation_state",
        ):
            if name not in target:
                raise TransactionJournalError(
                    "Target %d in %s is missing %s." % (index, source, name)
                )
        absolute = os.path.abspath(target["path"])
        if absolute in seen:
            raise TransactionJournalError(
                "Duplicate target path in %s: %s" % (source, absolute)
            )
        seen.add(absolute)
        target["path"] = absolute
        if target["kind"] not in ("text", "json", "bytes"):
            raise TransactionJournalError(
                "Unsupported target kind %r in %s." % (target["kind"], source)
            )
        for artifact_key in ("before_artifact", "after_artifact"):
            artifact = target.get(artifact_key)
            if artifact and (os.path.isabs(artifact) or os.path.dirname(artifact)):
                raise TransactionJournalError(
                    "Artifact paths must be local file names in %s." % source
                )
    return record


def list_journals(journal_dir, include_terminal=True):
    root = os.path.abspath(journal_dir)
    rows = []
    if not os.path.isdir(root):
        return rows
    for name in sorted(os.listdir(root)):
        path = os.path.join(root, name, "journal.json")
        if not os.path.isfile(path):
            continue
        try:
            record = load_record(path, allow_newer_read_only=True)
            state = record["state"]
            if include_terminal or state not in TERMINAL_STATES:
                rows.append(_summary(path, record))
        except TransactionJournalError as exc:
            rows.append(
                OrderedDict(
                    (
                        ("journal_path", path),
                        ("transaction_id", name),
                        ("state", "corrupt"),
                        ("operation", None),
                        ("target_count", 0),
                        ("recovery_required", True),
                        ("error", str(exc)),
                    )
                )
            )
    return rows


def inspect_journal(path):
    record = load_record(path, allow_newer_read_only=True)
    result = OrderedDict(record)
    result["journal_path"] = os.path.abspath(path)
    result["recovery_required"] = record.get("state") not in TERMINAL_STATES
    compatibility = record.get("version_compatibility") or version_compatibility(
        record, SCHEMA_VERSION
    )
    result["read_only"] = not compatibility.get("writable", False)
    result["permission_report"] = permission_report(
        os.path.dirname(path), require_private=True
    )
    observed = []
    for target in record["targets"]:
        actual = current_hash(target["path"])
        if actual == target["after_hash"]:
            relation = "after"
        elif actual == target["before_hash"]:
            relation = "before"
        else:
            relation = "diverged"
        observed.append(
            {
                "path": target["path"],
                "current_hash": actual,
                "relation": relation,
                "resume_safe": relation in ("before", "after"),
                "compensate_safe": relation in ("before", "after"),
            }
        )
    result["observed_targets"] = observed
    result["available_actions"] = available_actions(record, observed)
    return result


def available_actions(record, observed=None):
    compatibility = record.get("version_compatibility") or version_compatibility(
        record, SCHEMA_VERSION
    )
    if not compatibility.get("writable", False):
        return ["inspect", "export"]
    state = record.get("state")
    if state in TERMINAL_STATES:
        return ["inspect", "export", "cleanup"]
    observed = observed or []
    diverged = any(row.get("relation") == "diverged" for row in observed)
    actions = ["inspect", "export", "abandon"]
    if not diverged:
        actions[1:1] = ["resume", "compensate"]
    return actions


def resume(path, lock_timeout=5.0):
    journal = TransactionJournal(path)
    record = journal.load()
    if record["state"] == "committed":
        return inspect_journal(path)
    if record["state"] in ("compensated", "abandoned"):
        raise TransactionJournalError(
            "Cannot resume terminal transaction state %s." % record["state"]
        )
    journal.set_state("committing")
    try:
        with _target_locks(record, "transaction.resume", lock_timeout):
            for target in record["targets"]:
                _resume_target(journal, target)
        journal.set_state("committed")
    except Exception as exc:
        journal.set_state("resume_failed", error=storage_access_diagnostic(exc))
        raise
    return inspect_journal(path)


def compensate(path, lock_timeout=5.0):
    journal = TransactionJournal(path)
    record = journal.load()
    if record["state"] == "compensated":
        return inspect_journal(path)
    if record["state"] == "abandoned":
        raise TransactionJournalError("Cannot compensate an abandoned transaction.")
    journal.set_state("compensating")
    try:
        with _target_locks(record, "transaction.compensate", lock_timeout):
            for target in reversed(record["targets"]):
                _compensate_target(journal, target)
        journal.set_state("compensated")
    except Exception as exc:
        journal.set_state("compensation_failed", error=storage_access_diagnostic(exc))
        raise
    return inspect_journal(path)


def abandon_with_backup(path, backup_dir, now=None):
    journal = TransactionJournal(path)
    record = journal.load()
    destination_root = os.path.abspath(backup_dir)
    ensure_evidence_storage_profile(
        destination_root, policy=policy_from_config(config=None), create=True
    )
    destination = os.path.join(destination_root, record["transaction_id"])
    if os.path.exists(destination):
        raise TransactionJournalError(
            "Backup destination already exists: %s" % destination
        )
    fault_point("before_backup_copy", path=path, backup_path=destination)
    shutil.copytree(journal.directory, destination)
    fault_point("after_backup_copy", path=path, backup_path=destination)
    manifest_path, manifest = write_integrity_manifest(destination)
    _fsync_tree(destination)
    journal.set_state(
        "abandoned", error="Abandoned with backup at %s" % destination, now=now
    )
    report = inspect_journal(path)
    report["backup_path"] = destination
    report["backup_manifest"] = manifest_path
    report["backup_manifest_sha256"] = manifest.get("manifest_sha256")
    return report


def export_evidence(path, output_path):
    report = inspect_journal(path)
    evidence = OrderedDict(
        (
            ("schema_version", 1),
            ("transaction_id", report["transaction_id"]),
            ("operation", report["operation"]),
            ("state", report["state"]),
            ("created_at_utc", report["created_at_utc"]),
            ("updated_at_utc", report["updated_at_utc"]),
            ("terminal_at_utc", report.get("terminal_at_utc")),
            ("last_error", report.get("last_error")),
            ("targets", report["targets"]),
            ("observed_targets", report["observed_targets"]),
            ("recovery_required", report["recovery_required"]),
        )
    )
    _write_json_durable(os.path.abspath(output_path), evidence)
    return evidence


def cleanup_terminal(
    journal_dir, older_than_days=30, force=False, now=None, policy=None, config=None
):
    root = os.path.abspath(journal_dir)
    resolved_policy = policy or policy_from_config(config)
    if older_than_days is None:
        older_than_days = resolved_policy["terminal_retention_days"]
    now_value = now or datetime.datetime.now(datetime.timezone.utc)
    removed = []
    skipped = []
    errors = []
    for row in list_journals(root, include_terminal=True):
        path = row["journal_path"]
        if row.get("state") not in TERMINAL_STATES:
            skipped.append(
                {"journal_path": path, "reason": "transaction is not terminal"}
            )
            continue
        try:
            record = load_record(path)
            terminal = _parse_utc(
                record.get("terminal_at_utc") or record.get("updated_at_utc")
            )
            age_days = (
                0.0
                if terminal is None
                else max(
                    0.0,
                    (
                        now_value.astimezone(datetime.timezone.utc) - terminal
                    ).total_seconds()
                    / 86400.0,
                )
            )
            if age_days < float(older_than_days):
                skipped.append(
                    {"journal_path": path, "reason": "retention window not complete"}
                )
                continue
            if not force:
                skipped.append({"journal_path": path, "reason": "--force is required"})
                continue
            fault_point("before_terminal_cleanup", path=path)
            shutil.rmtree(os.path.dirname(path))
            fault_point("after_terminal_cleanup", path=path)
            removed.append(path)
        except Exception as exc:
            errors.append({"journal_path": path, "error": str(exc)})
    if os.path.isdir(root):
        _fsync_directory(root)
    return {
        "journal_dir": root,
        "older_than_days": float(older_than_days),
        "force": bool(force),
        "removed": removed,
        "skipped": skipped,
        "errors": errors,
    }


def journal_policy_report(journal_dir, config=None, policy=None):
    resolved = policy or policy_from_config(config)
    from .transaction_policy import journal_usage

    usage = journal_usage(journal_dir)
    permissions = permission_report(
        journal_dir, require_private=resolved["require_private_permissions"]
    )
    violations = []
    if usage["transactions"] > resolved["max_transactions"]:
        violations.append("max_transactions")
    if usage["total_bytes"] > resolved["max_total_bytes"]:
        violations.append("max_total_bytes")
    if permissions.get("problems"):
        violations.append("permissions")
    return OrderedDict(
        (
            ("ok", not violations),
            ("policy", resolved),
            ("usage", usage),
            ("permissions", permissions),
            ("violations", violations),
        )
    )


def verify_backup(backup_dir):
    return verify_integrity_manifest(backup_dir)


def archive_terminal(
    journal_dir, archive_dir, older_than_days=30, force=False, now=None, config=None
):
    root = os.path.abspath(journal_dir)
    destination_root = os.path.abspath(archive_dir)
    resolved_policy = policy_from_config(config)
    ensure_evidence_storage_profile(
        destination_root, policy=resolved_policy, create=True
    )
    archived = []
    skipped = []
    errors = []
    now_value = now or datetime.datetime.now(datetime.timezone.utc)
    for row in list_journals(root, include_terminal=True):
        path = row["journal_path"]
        if row.get("state") not in TERMINAL_STATES:
            skipped.append(
                {"journal_path": path, "reason": "transaction is not terminal"}
            )
            continue
        try:
            record = load_record(path)
            terminal = _parse_utc(
                record.get("terminal_at_utc") or record.get("updated_at_utc")
            )
            age_days = (
                0.0
                if terminal is None
                else max(
                    0.0,
                    (
                        now_value.astimezone(datetime.timezone.utc) - terminal
                    ).total_seconds()
                    / 86400.0,
                )
            )
            if age_days < float(older_than_days):
                skipped.append(
                    {"journal_path": path, "reason": "retention window not complete"}
                )
                continue
            if not force:
                skipped.append({"journal_path": path, "reason": "--force is required"})
                continue
            destination = os.path.join(destination_root, record["transaction_id"])
            if os.path.exists(destination):
                raise TransactionJournalError(
                    "Archive destination already exists: %s" % destination
                )
            shutil.copytree(os.path.dirname(path), destination)
            manifest_path, manifest = write_integrity_manifest(destination)
            _fsync_tree(destination)
            if not verify_integrity_manifest(destination).get("ok"):
                raise TransactionJournalError(
                    "Archive integrity verification failed: %s" % destination
                )
            shutil.rmtree(os.path.dirname(path))
            archived.append(
                {
                    "journal_path": path,
                    "archive_path": destination,
                    "manifest": manifest_path,
                    "manifest_sha256": manifest.get("manifest_sha256"),
                }
            )
        except Exception as exc:
            errors.append({"journal_path": path, "error": str(exc)})
    if os.path.isdir(root):
        _fsync_directory(root)
    _fsync_directory(destination_root)
    return {
        "journal_dir": root,
        "archive_dir": destination_root,
        "archived": archived,
        "skipped": skipped,
        "errors": errors,
    }


def restore_backup(
    backup_dir,
    action="inspect",
    working_dir=None,
    operator=None,
    config=None,
    audit_file=None,
):
    """Verify immutable backup evidence and recover through a separate working copy."""
    from .transaction_admin import append_admin_audit, authorize_operator
    from .transaction_policy import write_integrity_manifest

    authorization = authorize_operator(
        config, operator, action="transaction backup restore"
    )
    source = os.path.abspath(backup_dir)
    ensure_evidence_storage_profile(
        source, policy=policy_from_config(config), create=False
    )
    try:
        verification = verify_integrity_manifest(source)
    except Exception as exc:
        raise TransactionJournalError(
            "Backup integrity verification failed: %s (%s)" % (source, exc)
        )
    if not verification.get("ok"):
        raise TransactionJournalError(
            "Backup integrity verification failed: %s" % source
        )
    source_journal = os.path.join(source, "journal.json")
    record = load_record(source_journal, allow_newer_read_only=True)
    if action == "inspect":
        return OrderedDict(
            (
                ("ok", True),
                ("action", "inspect"),
                ("backup_dir", source),
                ("verification", verification),
                ("authorization", authorization),
                ("journal", inspect_journal(source_journal)),
                ("working_dir", None),
                ("original_backup_unchanged", True),
            )
        )
    if action not in ("resume", "compensate"):
        raise ValueError("restore action must be inspect, resume, or compensate.")
    if working_dir is None:
        working_dir = source + ".restore-" + uuid.uuid4().hex[:8]
    destination = os.path.abspath(working_dir)
    if os.path.exists(destination):
        raise TransactionJournalError(
            "Restore working directory already exists: %s" % destination
        )
    fault_point(
        "before_restore_working_copy", backup_dir=source, working_dir=destination
    )
    shutil.copytree(source, destination)
    fault_point(
        "after_restore_working_copy", backup_dir=source, working_dir=destination
    )
    manifest_path = os.path.join(destination, "integrity-manifest.json")
    try:
        os.unlink(manifest_path)
    except FileNotFoundError:
        pass
    working_journal = os.path.join(destination, "journal.json")
    try:
        report = (
            resume(working_journal)
            if action == "resume"
            else compensate(working_journal)
        )
    except Exception:
        # Preserve the working copy exactly as failure evidence and publish a new
        # manifest for operator handoff before propagating the recovery failure.
        write_integrity_manifest(destination)
        raise
    new_manifest_path, new_manifest = write_integrity_manifest(destination)
    _fsync_tree(destination)
    if audit_file:
        append_admin_audit(
            audit_file,
            "backup.restore.%s" % action,
            operator=operator,
            details={
                "backup_dir": source,
                "working_dir": destination,
                "transaction_id": record.get("transaction_id"),
                "result_state": report.get("state"),
            },
            config=config,
        )
    return OrderedDict(
        (
            ("ok", True),
            ("action", action),
            ("backup_dir", source),
            ("working_dir", destination),
            ("verification", verification),
            ("authorization", authorization),
            ("transaction_id", record.get("transaction_id")),
            ("result", report),
            ("working_manifest", new_manifest_path),
            ("working_manifest_sha256", new_manifest.get("manifest_sha256")),
            (
                "original_backup_unchanged",
                verify_integrity_manifest(source).get("ok", False),
            ),
        )
    )


def current_hash(path):
    try:
        with open(path, "rb") as handle:
            return mutation.hash_bytes(handle.read())
    except FileNotFoundError:
        return MISSING_HASH


def _summary(path, record):
    return OrderedDict(
        (
            ("journal_path", os.path.abspath(path)),
            ("transaction_id", record["transaction_id"]),
            ("state", record["state"]),
            ("operation", record["operation"]),
            ("target_count", len(record["targets"])),
            ("created_at_utc", record.get("created_at_utc")),
            ("updated_at_utc", record.get("updated_at_utc")),
            ("terminal_at_utc", record.get("terminal_at_utc")),
            ("recovery_required", record["state"] not in TERMINAL_STATES),
            ("error", record.get("last_error")),
        )
    )


def _resume_target(journal, target):
    actual = current_hash(target["path"])
    if actual == target["after_hash"]:
        journal.mark_target(target["index"], commit_state="verified")
        return
    if actual != target["before_hash"]:
        raise TransactionJournalConflict(
            target["path"],
            target["before_hash"],
            target["after_hash"],
            actual,
            "resume",
        )
    _write_target(journal.directory, target, use_after=True)
    latest = current_hash(target["path"])
    if latest != target["after_hash"]:
        raise MutationConflict(
            target["path"],
            target["after_hash"],
            latest,
            operation="transaction.resume.verify",
        )
    journal.mark_target(target["index"], commit_state="verified")


def _compensate_target(journal, target):
    actual = current_hash(target["path"])
    if actual == target["before_hash"]:
        journal.mark_target(target["index"], compensation_state="verified")
        return
    if actual != target["after_hash"]:
        raise TransactionJournalConflict(
            target["path"],
            target["before_hash"],
            target["after_hash"],
            actual,
            "compensate",
        )
    _write_target(journal.directory, target, use_after=False)
    latest = current_hash(target["path"])
    if latest != target["before_hash"]:
        raise MutationConflict(
            target["path"],
            target["before_hash"],
            latest,
            operation="transaction.compensate.verify",
        )
    journal.mark_target(target["index"], compensation_state="verified")


def _write_target(tx_dir, target, use_after):
    fault_point(
        "before_recovery_target_write", path=target["path"], use_after=bool(use_after)
    )
    expected = target["after_hash"] if use_after else target["before_hash"]
    artifact = (
        target.get("after_artifact") if use_after else target.get("before_artifact")
    )
    if expected == MISSING_HASH:
        try:
            os.unlink(target["path"])
        except FileNotFoundError:
            pass
        _fsync_directory(os.path.dirname(target["path"]) or ".")
        fault_point(
            "after_recovery_target_write",
            path=target["path"],
            use_after=bool(use_after),
        )
        return
    if not artifact:
        raise TransactionJournalError(
            "Missing recovery artifact for %s." % target["path"]
        )
    artifact_path = os.path.join(tx_dir, artifact)
    try:
        with open(artifact_path, "rb") as handle:
            payload = handle.read()
    except FileNotFoundError:
        raise TransactionJournalError(
            "Missing recovery artifact for %s." % target["path"]
        )
    if mutation.hash_bytes(payload) != expected:
        raise TransactionJournalError(
            "Recovery artifact hash mismatch for %s." % target["path"]
        )
    mutation.atomic_write_bytes(target["path"], payload)
    fault_point(
        "after_recovery_target_write", path=target["path"], use_after=bool(use_after)
    )


def _before_bytes(row):
    before = row["before"]
    if not before.exists:
        return b""
    if row["plan"].kind in ("text", "json"):
        return mutation._encode_text(
            before.text, encoding=before.encoding, bom=before.bom
        )
    return before.data


class _target_locks(object):
    def __init__(self, record, operation, timeout):
        self.record = record
        self.operation = operation
        self.timeout = timeout
        self.locks = []

    def __enter__(self):
        try:
            for path in sorted(target["path"] for target in self.record["targets"]):
                lock = FileLock(path, operation=self.operation, timeout=self.timeout)
                lock.acquire()
                self.locks.append(lock)
        except Exception:
            self.__exit__(None, None, None)
            raise
        return self

    def __exit__(self, exc_type, exc, tb):
        for lock in reversed(self.locks):
            lock.release()
        self.locks = []
        return False


def _write_bytes_durable(path, data):
    directory = os.path.dirname(os.path.abspath(path)) or "."
    os.makedirs(directory, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=".lifetxt-tx-", dir=directory)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(data)
            handle.flush()
            fault_point("before_file_fsync", path=path, temporary=temporary)
            os.fsync(handle.fileno())
            fault_point("after_file_fsync", path=path, temporary=temporary)
        _replace_file(temporary, path)
        fault_point("after_file_replace", path=path)
        fault_point("before_parent_fsync", path=path, directory=directory)
        _fsync_directory(directory)
        fault_point("after_parent_fsync", path=path, directory=directory)
    except Exception:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise


def _write_json_durable(path, value):
    payload = (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    _write_bytes_durable(path, payload)


def _replace_file(temporary, path):
    """Replace a file, retrying transient Windows handle refusals briefly."""
    retry_enabled = os.name in _REPLACE_PERMISSION_RETRY_OS_NAMES
    retry_delays = (
        tuple(_REPLACE_PERMISSION_RETRY_DELAYS_SECONDS) if retry_enabled else ()
    )
    attempts = len(retry_delays) + 1
    for attempt in range(attempts):
        try:
            fault_point(
                "before_file_replace",
                path=path,
                temporary=temporary,
                attempt=attempt + 1,
                max_attempts=attempts,
            )
            os.replace(temporary, path)
            return
        except PermissionError:
            if attempt >= len(retry_delays):
                raise
            time.sleep(float(retry_delays[attempt]))


def _fsync_directory(path):
    directory = os.path.abspath(path or ".")
    try:
        descriptor = os.open(directory, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(descriptor)
    except OSError:
        pass
    finally:
        os.close(descriptor)


def _fsync_tree(root):
    for directory, _subdirs, files in os.walk(root):
        for name in files:
            try:
                with open(os.path.join(directory, name), "rb") as handle:
                    os.fsync(handle.fileno())
            except OSError:
                pass
        _fsync_directory(directory)


def _parse_utc(value):
    if not value:
        return None
    text = str(value)
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    parsed = parse_iso_datetime(text)
    if parsed is None:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=datetime.timezone.utc)
    return parsed.astimezone(datetime.timezone.utc)
