"""Versioned transaction policy administration and startup preflight."""

from __future__ import unicode_literals

import datetime
import json
import os
import shutil
from collections import OrderedDict

from .mutation import MISSING_HASH, mutate_json, read_text_snapshot
from .transaction_policy import (
    TransactionPolicyError,
    ensure_private_tree,
    journal_usage,
    permission_report,
    policy_from_config,
)

POLICY_VERSION = 1
DEFAULT_AUDIT_MAX_EVENTS = 1000


class TransactionPolicyVersionError(TransactionPolicyError):
    pass


def utc_now_text(now=None):
    if now is None:
        from .timezone_policy import utcnow
        value = utcnow()
    else:
        value = now
    if value.tzinfo is None:
        value = value.replace(tzinfo=datetime.timezone.utc)
    return value.astimezone(datetime.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def policy_path(journal_dir, config=None):
    config = config or {}
    section = config.get("transactions") if isinstance(config.get("transactions"), dict) else {}
    configured = section.get("policy_file")
    if configured:
        return os.path.abspath(os.path.expanduser(str(configured)))
    return os.path.join(os.path.abspath(journal_dir), "policy.json")


def audit_path(journal_dir, config=None):
    config = config or {}
    section = config.get("transactions") if isinstance(config.get("transactions"), dict) else {}
    configured = section.get("admin_audit_file")
    if configured:
        return os.path.abspath(os.path.expanduser(str(configured)))
    return os.path.join(os.path.abspath(journal_dir), "admin-audit.json")


def policy_document(config=None, now=None, operator=None):
    return OrderedDict(
        (
            ("policy_version", POLICY_VERSION),
            ("updated_at_utc", utc_now_text(now)),
            ("updated_by", str(operator or "unknown")),
            ("policy", policy_from_config(config)),
        )
    )


def validate_policy_document(document, allow_older=False):
    if not isinstance(document, dict):
        raise TransactionPolicyError("Transaction policy document must be an object.")
    version = document.get("policy_version", 0)
    try:
        version = int(version)
    except (TypeError, ValueError):
        raise TransactionPolicyVersionError("Transaction policy version must be an integer.")
    if version > POLICY_VERSION:
        raise TransactionPolicyVersionError(
            "Transaction policy version %d is newer than supported version %d."
            % (version, POLICY_VERSION)
        )
    if version < POLICY_VERSION and not allow_older:
        raise TransactionPolicyVersionError(
            "Transaction policy version %d requires migration to version %d."
            % (version, POLICY_VERSION)
        )
    raw = document.get("policy")
    if not isinstance(raw, dict):
        raise TransactionPolicyError("Transaction policy document requires a policy object.")
    normalized = policy_from_config({"transactions": raw})
    result = OrderedDict(
        (
            ("policy_version", version),
            ("updated_at_utc", document.get("updated_at_utc")),
            ("updated_by", document.get("updated_by")),
            ("policy", normalized),
        )
    )
    if "migrated_from" in document:
        result["migrated_from"] = document.get("migrated_from")
    return result


def read_policy_document(path, allow_missing=False, allow_older=False):
    absolute = os.path.abspath(path)
    try:
        with open(absolute, "r", encoding="utf-8") as handle:
            raw = json.load(handle, object_pairs_hook=OrderedDict)
    except FileNotFoundError:
        if allow_missing:
            return None
        raise
    except (OSError, ValueError) as exc:
        raise TransactionPolicyError("Cannot read transaction policy %s: %s" % (absolute, exc))
    return validate_policy_document(raw, allow_older=allow_older)


def migrate_policy_document(document, now=None, operator=None):
    if not isinstance(document, dict):
        raise TransactionPolicyError("Transaction policy document must be an object.")
    raw_version = document.get("policy_version", 0)
    try:
        version = int(raw_version)
    except (TypeError, ValueError):
        version = 0
    if version > POLICY_VERSION:
        raise TransactionPolicyVersionError(
            "Refusing to migrate newer transaction policy version %d." % version
        )
    if version == POLICY_VERSION:
        return validate_policy_document(document)
    raw_policy = document.get("policy") if isinstance(document.get("policy"), dict) else document
    return OrderedDict(
        (
            ("policy_version", POLICY_VERSION),
            ("updated_at_utc", utc_now_text(now)),
            ("updated_by", str(operator or "unknown")),
            ("policy", policy_from_config({"transactions": raw_policy})),
            ("migrated_from", version),
        )
    )


def write_policy_document(path, document, expected_revision=None, operator=None, audit_file=None, now=None):
    absolute = os.path.abspath(path)
    ensure_private_tree(os.path.dirname(absolute) or ".", require_private=True)
    normalized = validate_policy_document(document)
    normalized["updated_at_utc"] = utc_now_text(now)
    normalized["updated_by"] = str(operator or normalized.get("updated_by") or "unknown")
    result = mutate_json(
        absolute,
        lambda _current: normalized,
        expected_hash=expected_revision,
        operation="transactions.policy.write",
        create=True,
        default={},
    )
    _make_private(absolute, directory=False)
    if audit_file:
        append_admin_audit(
            audit_file,
            "policy.write",
            operator=operator,
            details={"path": absolute, "before_revision": result.before_hash, "after_revision": result.after_hash},
            now=now,
        )
    return OrderedDict(
        (
            ("path", absolute),
            ("before_revision", result.before_hash),
            ("after_revision", result.after_hash),
            ("changed", result.changed),
            ("document", normalized),
        )
    )


def migrate_policy_file(path, expected_revision=None, operator=None, audit_file=None, now=None):
    absolute = os.path.abspath(path)
    snapshot = read_text_snapshot(absolute, allow_missing=True)
    if expected_revision is not None and snapshot.content_hash != expected_revision:
        from .mutation import MutationConflict
        raise MutationConflict(absolute, expected_revision, snapshot.content_hash, operation="transactions.policy.migrate")
    if snapshot.exists:
        try:
            current = json.loads(snapshot.text, object_pairs_hook=OrderedDict)
        except ValueError as exc:
            raise TransactionPolicyError("Cannot parse transaction policy %s: %s" % (absolute, exc))
    else:
        current = {}
    migrated = migrate_policy_document(current, now=now, operator=operator)
    return write_policy_document(
        absolute,
        migrated,
        expected_revision=snapshot.content_hash,
        operator=operator,
        audit_file=audit_file,
        now=now,
    )


def append_admin_audit(path, event, operator=None, details=None, max_events=DEFAULT_AUDIT_MAX_EVENTS, now=None):
    absolute = os.path.abspath(path)
    ensure_private_tree(os.path.dirname(absolute) or ".", require_private=True)
    limit = max(1, int(max_events))
    entry = OrderedDict(
        (
            ("timestamp_utc", utc_now_text(now)),
            ("operator", str(operator or "unknown")),
            ("event", str(event)),
            ("details", details or {}),
        )
    )

    def transform(current):
        current = current if isinstance(current, dict) else {}
        events = list(current.get("events") or [])
        events.append(entry)
        if len(events) > limit:
            events = events[-limit:]
        return OrderedDict((("audit_version", 1), ("events", events)))

    result = mutate_json(
        absolute,
        transform,
        operation="transactions.admin.audit",
        create=True,
        default={"audit_version": 1, "events": []},
    )
    _make_private(absolute, directory=False)
    return OrderedDict((("path", absolute), ("revision", result.after_hash), ("event_count", len(json.loads(result.snapshot.text).get("events") or []))))


def preflight_report(journal_dir, config=None, create=False):
    root = os.path.abspath(journal_dir)
    policy = policy_from_config(config)
    errors = []
    warnings = []
    if create:
        try:
            ensure_private_tree(root, require_private=policy["require_private_permissions"])
        except Exception as exc:
            errors.append(str(exc))
    permissions = permission_report(root, require_private=policy["require_private_permissions"])
    if permissions.get("problems"):
        errors.extend(permissions["problems"])
    usage = journal_usage(root)
    if usage["transactions"] >= policy["max_transactions"]:
        errors.append("transaction count is at or above max_transactions")
    elif usage["transactions"] >= int(policy["max_transactions"] * 0.8):
        warnings.append("transaction count is at least 80% of max_transactions")
    if usage["total_bytes"] >= policy["max_total_bytes"]:
        errors.append("journal bytes are at or above max_total_bytes")
    elif usage["total_bytes"] >= int(policy["max_total_bytes"] * 0.8):
        warnings.append("journal bytes are at least 80% of max_total_bytes")
    ppath = policy_path(root, config=config)
    policy_state = OrderedDict((("path", ppath), ("exists", os.path.exists(ppath)), ("revision", MISSING_HASH), ("version", None), ("state", "missing")))
    if os.path.exists(ppath):
        snapshot = read_text_snapshot(ppath)
        policy_state["revision"] = snapshot.content_hash
        try:
            raw = json.loads(snapshot.text)
            version = int(raw.get("policy_version", 0)) if isinstance(raw, dict) else 0
            policy_state["version"] = version
            if version == POLICY_VERSION:
                validate_policy_document(raw)
                policy_state["state"] = "current"
            elif version < POLICY_VERSION:
                policy_state["state"] = "migration_required"
                errors.append("transaction policy migration is required")
            else:
                policy_state["state"] = "newer_unsupported"
                errors.append("transaction policy is newer than this lifetxt version")
        except Exception as exc:
            policy_state["state"] = "invalid"
            errors.append(str(exc))
    return OrderedDict(
        (
            ("ok", not errors),
            ("journal_dir", root),
            ("policy", policy),
            ("policy_file", policy_state),
            ("usage", usage),
            ("permissions", permissions),
            ("warnings", warnings),
            ("errors", errors),
        )
    )


def rotate_archives(archive_dir, max_archives=100, max_total_bytes=1024 * 1024 * 1024, force=False, operator=None, audit_file=None):
    root = os.path.abspath(archive_dir)
    rows = []
    if os.path.isdir(root):
        for name in sorted(os.listdir(root)):
            path = os.path.join(root, name)
            if not os.path.isdir(path):
                continue
            manifest = os.path.join(path, "integrity-manifest.json")
            if not os.path.isfile(manifest):
                continue
            size = _tree_size(path)
            rows.append({"path": path, "name": name, "size": size, "mtime": os.path.getmtime(path)})
    rows.sort(key=lambda row: (row["mtime"], row["name"]))
    keep_count = max(0, int(max_archives))
    keep_bytes = max(0, int(max_total_bytes))
    total = sum(row["size"] for row in rows)
    remove = []
    remaining = len(rows)
    for row in rows:
        if remaining <= keep_count and total <= keep_bytes:
            break
        remove.append(row)
        remaining -= 1
        total -= row["size"]
    if remove and not force:
        return OrderedDict((("ok", False), ("archive_dir", root), ("requires_force", True), ("would_remove", remove), ("removed", [])))
    removed = []
    for row in remove:
        shutil.rmtree(row["path"])
        removed.append(row)
    if audit_file and removed:
        append_admin_audit(audit_file, "archive.rotate", operator=operator, details={"removed": [row["name"] for row in removed]})
    return OrderedDict((("ok", True), ("archive_dir", root), ("requires_force", False), ("removed", removed), ("remaining_count", remaining), ("remaining_bytes", total)))


def _tree_size(root):
    total = 0
    for directory, _subdirs, names in os.walk(root):
        for name in names:
            try:
                total += os.path.getsize(os.path.join(directory, name))
            except OSError:
                pass
    return total


def _make_private(path, directory=False):
    try:
        os.chmod(path, 0o700 if directory else 0o600)
    except OSError:
        pass
