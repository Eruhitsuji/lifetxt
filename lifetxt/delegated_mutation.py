"""Restart-safe proposal contract for delegated text mutations.

External programs never receive the authoritative life.txt path. They edit a
private temporary copy. The resulting text, exact base revision, hashes, and
unified diff can be persisted and applied later with an optimistic-concurrency
precondition.
"""

from __future__ import unicode_literals

import datetime
import difflib
import hashlib
import json
import os
import shlex
import shutil
import subprocess
import tempfile
import uuid
from collections import OrderedDict

from . import mutation
from .parser import parse_text
from .safety_foundation import format_version_report
from .timezone_policy import utcnow

PROPOSAL_VERSION = 1
PROPOSAL_STATES = frozenset(("prepared", "applied", "rejected"))
DEFAULT_ADAPTER_ID = "cli.delegated"
DEFAULT_ADAPTER_KIND = "local_process"
DEFAULT_ADAPTER_VERSION = "1"
CONTRACT_HASH_FIELDS = (
    "proposal_version",
    "id",
    "state",
    "operation",
    "path",
    "command",
    "before_revision",
    "edited_revision",
    "diff_sha256",
    "changed",
    "adapter",
    "provenance",
    "authorization",
    "lifecycle",
    "sandbox",
)


class DelegatedMutationError(ValueError):
    pass


def utc_now_text(now=None):
    value = now or utcnow()
    if value.tzinfo is None:
        value = value.replace(tzinfo=datetime.timezone.utc)
    return (
        value.astimezone(datetime.timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def normalize_command(command, temporary_path):
    if isinstance(command, str):
        argv = shlex.split(command, posix=os.name != "nt")
        command_was_string = True
    elif isinstance(command, (list, tuple)):
        argv = [str(value) for value in command]
        command_was_string = False
    else:
        raise DelegatedMutationError(
            "Delegated command must be a string or argument list."
        )
    if not argv:
        raise DelegatedMutationError("Delegated command must not be empty.")
    replaced = False
    normalized = []
    for value in argv:
        if command_was_string and os.name == "nt":
            value = _unquote_windows_argument(value)
        if "{file}" in value:
            value = value.replace("{file}", temporary_path)
            replaced = True
        normalized.append(value)
    if not replaced:
        normalized.append(temporary_path)
    return normalized


def _unquote_windows_argument(value):
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
        return value[1:-1]
    return value


def validate_lifetxt_text(text):
    version = format_version_report(text)
    if version.get("state") == "unsupported":
        raise DelegatedMutationError(
            "Delegated output declares unsupported format version %s."
            % version.get("declared")
        )
    _items, diagnostics = parse_text(text)
    errors = [
        item for item in diagnostics if getattr(item, "severity", None) == "error"
    ]
    if errors:
        first = errors[0]
        raise DelegatedMutationError(
            "Delegated output is not valid life.txt: %s (line %s)."
            % (getattr(first, "message", str(first)), getattr(first, "line", "?"))
        )
    return True


def _stable_json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha256_json(value):
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _validate_identifier(name, value):
    if not isinstance(value, str) or not value:
        raise DelegatedMutationError("%s must be a non-empty string." % name)
    allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._:-")
    if any(char not in allowed for char in value):
        raise DelegatedMutationError("%s contains unsupported characters." % name)
    return value


def delegated_contract_hash(proposal):
    payload = OrderedDict(
        (key, proposal.get(key)) for key in CONTRACT_HASH_FIELDS if key in proposal
    )
    return _sha256_json(payload)


def _adapter_metadata(adapter_id=None, adapter_kind=None, adapter_version=None):
    adapter_id = _validate_identifier("adapter.id", adapter_id or DEFAULT_ADAPTER_ID)
    adapter_kind = _validate_identifier(
        "adapter.kind", adapter_kind or DEFAULT_ADAPTER_KIND
    )
    adapter_version = _validate_identifier(
        "adapter.version", adapter_version or DEFAULT_ADAPTER_VERSION
    )
    return OrderedDict(
        (
            ("id", adapter_id),
            ("kind", adapter_kind),
            ("version", adapter_version),
        )
    )


def _provenance_metadata(argv, source):
    return OrderedDict(
        (
            ("prepared_by", "lifetxt"),
            ("command_sha256", _sha256_json([str(value) for value in argv])),
            ("source_revision", source.content_hash),
            (
                "source_path_sha256",
                hashlib.sha256(source.path.encode("utf-8")).hexdigest(),
            ),
            ("temporary_copy", True),
        )
    )


def _authorization_metadata():
    return OrderedDict(
        (
            ("permission_model", "local-user-invoked-proposal"),
            (
                "required_permissions",
                [
                    "read_source_snapshot",
                    "run_local_adapter_on_temporary_copy",
                    "write_source_via_revision_checked_apply",
                ],
            ),
            ("direct_write_allowed", False),
            ("apply_requires_revision", True),
        )
    )


def _lifecycle_metadata(timeout, keep_temporary, proposal_path=None):
    return OrderedDict(
        (
            ("process_timeout_seconds", float(timeout)),
            ("timeout_behavior", "abort_without_authoritative_write"),
            ("cancellation_behavior", "abort_without_authoritative_write"),
            (
                "proposal_retention",
                "persisted_if_proposal_path_supplied"
                if proposal_path
                else "not_persisted_without_proposal_path",
            ),
            (
                "temporary_cleanup",
                "retained_for_review" if keep_temporary else "delete_after_prepare",
            ),
        )
    )


def _sandbox_metadata(source, temporary_path, temp_root):
    return OrderedDict(
        (
            ("model", "private_temporary_copy"),
            ("private_temporary_copy", True),
            ("authoritative_path_exposed_to_adapter", False),
            (
                "authoritative_path_sha256",
                hashlib.sha256(source.path.encode("utf-8")).hexdigest(),
            ),
            (
                "temporary_path_sha256",
                hashlib.sha256(temporary_path.encode("utf-8")).hexdigest(),
            ),
            (
                "temporary_root_sha256",
                hashlib.sha256(temp_root.encode("utf-8")).hexdigest(),
            ),
        )
    )


def prepare_delegated_mutation(
    path,
    command,
    proposal_path=None,
    timeout=300.0,
    keep_temporary=False,
    environment=None,
    operation="delegated.mutation",
    adapter_id=None,
    adapter_kind=None,
    adapter_version=None,
    now=None,
):
    source = mutation.read_text_snapshot(path)
    temp_root = tempfile.mkdtemp(prefix="lifetxt-delegated-")
    temporary_path = os.path.join(
        temp_root, os.path.basename(source.path) or "life.txt"
    )
    if os.path.abspath(temporary_path) == os.path.abspath(source.path):
        raise DelegatedMutationError(
            "Delegated temporary copy must not be the authoritative source."
        )
    try:
        # The handoff copy is non-authoritative. Copy exact bytes, then verify
        # them against the captured snapshot so a concurrent source change can
        # never alter the proposal base silently.
        shutil.copyfile(source.path, temporary_path)
        copied = mutation.read_text_snapshot(temporary_path)
        if copied.content_hash != source.content_hash:
            raise mutation.MutationConflict(
                source.path,
                source.content_hash,
                copied.content_hash,
                operation="delegated.prepare.copy",
            )
        argv = normalize_command(command, temporary_path)
        env = None
        if environment is not None:
            env = os.environ.copy()
            env.update(
                {str(key): str(value) for key, value in dict(environment).items()}
            )
        try:
            completed = subprocess.run(
                argv,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
                timeout=float(timeout),
                env=env,
                shell=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise DelegatedMutationError(
                "Delegated command timed out after %.3fs." % float(timeout)
            ) from exc
        if completed.returncode != 0:
            raise DelegatedMutationError(
                "Delegated command exited with %d: %s"
                % (
                    completed.returncode,
                    (completed.stderr or completed.stdout or "").strip(),
                )
            )
        edited = mutation.read_text_snapshot(temporary_path)
        validate_lifetxt_text(edited.text)
        diff = "\n".join(
            difflib.unified_diff(
                source.text.splitlines(),
                edited.text.splitlines(),
                fromfile=source.path + " (base)",
                tofile=source.path + " (delegated)",
                lineterm="",
                n=3,
            )
        )
        proposal = OrderedDict(
            (
                ("proposal_version", PROPOSAL_VERSION),
                ("id", "D-" + uuid.uuid4().hex[:12]),
                ("state", "prepared"),
                ("operation", str(operation or "delegated.mutation")),
                ("path", source.path),
                ("command", argv),
                ("created_at_utc", utc_now_text(now)),
                ("before_revision", source.content_hash),
                (
                    "edited_revision",
                    mutation.hash_text(
                        edited.text, encoding=source.encoding, bom=source.bom
                    ),
                ),
                ("diff_sha256", hashlib.sha256(diff.encode("utf-8")).hexdigest()),
                ("changed", edited.text != source.text),
                ("diff", diff),
                ("edited_text", edited.text),
                ("encoding", source.encoding),
                ("bom", bool(source.bom)),
                ("stdout", completed.stdout),
                ("stderr", completed.stderr),
                ("exit_code", completed.returncode),
                ("temporary_path", temporary_path if keep_temporary else None),
                (
                    "adapter",
                    _adapter_metadata(
                        adapter_id=adapter_id,
                        adapter_kind=adapter_kind,
                        adapter_version=adapter_version,
                    ),
                ),
                ("provenance", _provenance_metadata(argv, source)),
                ("authorization", _authorization_metadata()),
                (
                    "lifecycle",
                    _lifecycle_metadata(timeout, keep_temporary, proposal_path),
                ),
                ("sandbox", _sandbox_metadata(source, temporary_path, temp_root)),
            )
        )
        proposal["contract_sha256"] = delegated_contract_hash(proposal)
        validate_delegated_proposal(proposal)
        result = OrderedDict(proposal)
        if proposal_path:
            saved = write_delegated_proposal(proposal_path, proposal)
            result["proposal_path"] = saved["path"]
            result["proposal_revision"] = saved["revision"]
        if keep_temporary:
            temp_root = None
        return result
    finally:
        if temp_root:
            shutil.rmtree(temp_root, ignore_errors=True)


def validate_delegated_proposal(proposal):
    if not isinstance(proposal, dict):
        raise DelegatedMutationError("Delegated proposal must be an object.")
    version = proposal.get("proposal_version")
    if version != PROPOSAL_VERSION:
        raise DelegatedMutationError(
            "Unsupported delegated proposal version %r; expected %d."
            % (version, PROPOSAL_VERSION)
        )
    if proposal.get("state") not in PROPOSAL_STATES:
        raise DelegatedMutationError(
            "Invalid delegated proposal state: %r" % proposal.get("state")
        )
    for key in (
        "id",
        "operation",
        "path",
        "before_revision",
        "edited_revision",
        "diff_sha256",
        "edited_text",
        "diff",
        "contract_sha256",
    ):
        if not isinstance(proposal.get(key), str) or (
            key not in ("edited_text", "diff") and not proposal.get(key)
        ):
            raise DelegatedMutationError(
                "Delegated proposal requires string field %s." % key
            )
    expected_edited = mutation.hash_text(
        proposal["edited_text"],
        encoding=str(proposal.get("encoding") or "utf-8"),
        bom=bool(proposal.get("bom")),
    )
    if expected_edited != proposal["edited_revision"]:
        raise DelegatedMutationError(
            "Delegated proposal edited_text hash does not match edited_revision."
        )
    expected_diff = hashlib.sha256(proposal["diff"].encode("utf-8")).hexdigest()
    if expected_diff != proposal["diff_sha256"]:
        raise DelegatedMutationError(
            "Delegated proposal diff hash does not match diff_sha256."
        )
    _validate_metadata(proposal)
    _validate_lifecycle(proposal)
    _validate_sandbox(proposal)
    expected_contract = delegated_contract_hash(proposal)
    if expected_contract != proposal["contract_sha256"]:
        raise DelegatedMutationError(
            "Delegated proposal contract metadata hash does not match contract_sha256."
        )
    validate_lifetxt_text(proposal["edited_text"])
    return proposal


def _require_object(proposal, key):
    value = proposal.get(key)
    if not isinstance(value, dict):
        raise DelegatedMutationError(
            "Delegated proposal requires object field %s." % key
        )
    return value


def _validate_metadata(proposal):
    adapter = _require_object(proposal, "adapter")
    _validate_identifier("adapter.id", adapter.get("id"))
    _validate_identifier("adapter.kind", adapter.get("kind"))
    _validate_identifier("adapter.version", adapter.get("version"))

    provenance = _require_object(proposal, "provenance")
    if provenance.get("prepared_by") != "lifetxt":
        raise DelegatedMutationError("Delegated proposal provenance must be lifetxt.")
    expected_command = _sha256_json(
        [str(value) for value in proposal.get("command") or []]
    )
    if provenance.get("command_sha256") != expected_command:
        raise DelegatedMutationError(
            "Delegated proposal command provenance does not match command."
        )
    if provenance.get("source_revision") != proposal.get("before_revision"):
        raise DelegatedMutationError(
            "Delegated proposal source provenance does not match before_revision."
        )
    if (
        not isinstance(provenance.get("source_path_sha256"), str)
        or len(provenance.get("source_path_sha256")) != 64
    ):
        raise DelegatedMutationError(
            "Delegated proposal source_path_sha256 must be a SHA-256 string."
        )
    if provenance.get("temporary_copy") is not True:
        raise DelegatedMutationError(
            "Delegated proposal provenance must record temporary_copy=true."
        )

    authorization = _require_object(proposal, "authorization")
    if authorization.get("permission_model") != "local-user-invoked-proposal":
        raise DelegatedMutationError(
            "Delegated proposal permission_model is unsupported."
        )
    required = authorization.get("required_permissions")
    if not isinstance(required, list):
        raise DelegatedMutationError(
            "Delegated proposal required_permissions must be a list."
        )
    required_set = set(str(value) for value in required)
    expected_permissions = {
        "read_source_snapshot",
        "run_local_adapter_on_temporary_copy",
        "write_source_via_revision_checked_apply",
    }
    if not expected_permissions.issubset(required_set):
        raise DelegatedMutationError(
            "Delegated proposal required_permissions are incomplete."
        )
    if authorization.get("direct_write_allowed") is not False:
        raise DelegatedMutationError(
            "Delegated proposals must not allow direct authoritative writes."
        )
    if authorization.get("apply_requires_revision") is not True:
        raise DelegatedMutationError(
            "Delegated proposal apply_requires_revision must be true."
        )


def _validate_lifecycle(proposal):
    lifecycle = _require_object(proposal, "lifecycle")
    try:
        timeout = float(lifecycle.get("process_timeout_seconds"))
    except (TypeError, ValueError):
        timeout = 0.0
    if timeout <= 0:
        raise DelegatedMutationError(
            "Delegated proposal process_timeout_seconds must be positive."
        )
    if lifecycle.get("timeout_behavior") != "abort_without_authoritative_write":
        raise DelegatedMutationError("Delegated proposal timeout_behavior is unsafe.")
    if lifecycle.get("cancellation_behavior") != "abort_without_authoritative_write":
        raise DelegatedMutationError(
            "Delegated proposal cancellation_behavior is unsafe."
        )
    if lifecycle.get("proposal_retention") not in (
        "persisted_if_proposal_path_supplied",
        "not_persisted_without_proposal_path",
    ):
        raise DelegatedMutationError(
            "Delegated proposal retention policy is unsupported."
        )
    if lifecycle.get("temporary_cleanup") not in (
        "delete_after_prepare",
        "retained_for_review",
    ):
        raise DelegatedMutationError(
            "Delegated proposal cleanup policy is unsupported."
        )


def _validate_sandbox(proposal):
    sandbox = _require_object(proposal, "sandbox")
    if sandbox.get("model") != "private_temporary_copy":
        raise DelegatedMutationError("Delegated proposal sandbox model is unsupported.")
    if sandbox.get("private_temporary_copy") is not True:
        raise DelegatedMutationError(
            "Delegated proposal must use a private temporary copy."
        )
    if sandbox.get("authoritative_path_exposed_to_adapter") is not False:
        raise DelegatedMutationError(
            "Delegated proposal must not expose the authoritative path to adapters."
        )
    for key in (
        "authoritative_path_sha256",
        "temporary_path_sha256",
        "temporary_root_sha256",
    ):
        value = sandbox.get(key)
        if not isinstance(value, str) or len(value) != 64:
            raise DelegatedMutationError(
                "Delegated proposal %s must be a SHA-256 string." % key
            )


def write_delegated_proposal(path, proposal, expected_revision=None):
    validate_delegated_proposal(proposal)
    absolute = os.path.abspath(path)
    os.makedirs(os.path.dirname(absolute) or ".", exist_ok=True)
    result = mutation.mutate_json(
        absolute,
        lambda _current: OrderedDict(proposal),
        expected_hash=expected_revision,
        operation="delegated.proposal.write",
        create=True,
        default={},
    )
    try:
        os.chmod(absolute, 0o600)
    except OSError:
        pass
    return OrderedDict(
        (
            ("path", absolute),
            ("revision", result.after_hash),
            ("changed", result.changed),
        )
    )


def read_delegated_proposal(path):
    snapshot = mutation.read_text_snapshot(path)
    try:
        proposal = json.loads(snapshot.text, object_pairs_hook=OrderedDict)
    except ValueError as exc:
        raise DelegatedMutationError(
            "Cannot parse delegated proposal %s: %s" % (snapshot.path, exc)
        )
    validate_delegated_proposal(proposal)
    return proposal, snapshot


def apply_delegated_proposal(proposal, expected_revision=None, unsafe=False):
    validate_delegated_proposal(proposal)
    if proposal.get("state") != "prepared":
        raise DelegatedMutationError(
            "Only prepared delegated proposals may be applied."
        )
    expected = expected_revision
    if expected is None and not unsafe:
        expected = proposal["before_revision"]
    if expected is None and unsafe:
        expected = mutation.read_text_snapshot(proposal["path"]).content_hash
    result = mutation.write_text(
        proposal["path"],
        proposal["edited_text"],
        expected_hash=expected,
        operation=str(proposal.get("operation") or "delegated.mutation"),
        create=False,
    )
    return OrderedDict(
        (
            ("applied", True),
            ("proposal_id", proposal["id"]),
            ("path", result.path),
            ("before_revision", result.before_hash),
            ("after_revision", result.after_hash),
            ("changed", result.changed),
            ("unsafe_override", bool(unsafe)),
        )
    )


def apply_delegated_proposal_file(
    path,
    expected_proposal_revision=None,
    expected_revision=None,
    unsafe=False,
    now=None,
):
    proposal, snapshot = read_delegated_proposal(path)
    if (
        expected_proposal_revision is not None
        and snapshot.content_hash != expected_proposal_revision
    ):
        raise mutation.MutationConflict(
            snapshot.path,
            expected_proposal_revision,
            snapshot.content_hash,
            operation="delegated.proposal.apply",
        )
    applied = apply_delegated_proposal(
        proposal, expected_revision=expected_revision, unsafe=unsafe
    )
    updated = OrderedDict(proposal)
    updated["state"] = "applied"
    updated["applied_at_utc"] = utc_now_text(now)
    updated["result"] = applied
    updated["contract_sha256"] = delegated_contract_hash(updated)
    saved = write_delegated_proposal(
        snapshot.path, updated, expected_revision=snapshot.content_hash
    )
    applied["proposal_path"] = saved["path"]
    applied["proposal_revision"] = saved["revision"]
    return applied


def reject_delegated_proposal_file(
    path, expected_proposal_revision=None, reason=None, now=None
):
    proposal, snapshot = read_delegated_proposal(path)
    if (
        expected_proposal_revision is not None
        and snapshot.content_hash != expected_proposal_revision
    ):
        raise mutation.MutationConflict(
            snapshot.path,
            expected_proposal_revision,
            snapshot.content_hash,
            operation="delegated.proposal.reject",
        )
    if proposal.get("state") != "prepared":
        raise DelegatedMutationError(
            "Only prepared delegated proposals may be rejected."
        )
    updated = OrderedDict(proposal)
    updated["state"] = "rejected"
    updated["rejected_at_utc"] = utc_now_text(now)
    updated["rejection_reason"] = None if reason is None else str(reason)
    updated["contract_sha256"] = delegated_contract_hash(updated)
    saved = write_delegated_proposal(
        snapshot.path, updated, expected_revision=snapshot.content_hash
    )
    return OrderedDict(
        (
            ("rejected", True),
            ("proposal_id", proposal["id"]),
            ("proposal_path", saved["path"]),
            ("proposal_revision", saved["revision"]),
        )
    )
