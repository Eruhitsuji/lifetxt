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


class DelegatedMutationError(ValueError):
    pass


def utc_now_text(now=None):
    value = now or utcnow()
    if value.tzinfo is None:
        value = value.replace(tzinfo=datetime.timezone.utc)
    return value.astimezone(datetime.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def normalize_command(command, temporary_path):
    if isinstance(command, str):
        argv = shlex.split(command, posix=os.name != "nt")
    elif isinstance(command, (list, tuple)):
        argv = [str(value) for value in command]
    else:
        raise DelegatedMutationError("Delegated command must be a string or argument list.")
    if not argv:
        raise DelegatedMutationError("Delegated command must not be empty.")
    replaced = False
    normalized = []
    for value in argv:
        if "{file}" in value:
            value = value.replace("{file}", temporary_path)
            replaced = True
        normalized.append(value)
    if not replaced:
        normalized.append(temporary_path)
    return normalized


def validate_lifetxt_text(text):
    version = format_version_report(text)
    if version.get("state") == "unsupported":
        raise DelegatedMutationError(
            "Delegated output declares unsupported format version %s." % version.get("declared")
        )
    _items, diagnostics = parse_text(text)
    errors = [item for item in diagnostics if getattr(item, "severity", None) == "error"]
    if errors:
        first = errors[0]
        raise DelegatedMutationError(
            "Delegated output is not valid life.txt: %s (line %s)."
            % (getattr(first, "message", str(first)), getattr(first, "line", "?"))
        )
    return True


def prepare_delegated_mutation(
    path,
    command,
    proposal_path=None,
    timeout=300.0,
    keep_temporary=False,
    environment=None,
    operation="delegated.mutation",
    now=None,
):
    source = mutation.read_text_snapshot(path)
    temp_root = tempfile.mkdtemp(prefix="lifetxt-delegated-")
    temporary_path = os.path.join(temp_root, os.path.basename(source.path) or "life.txt")
    try:
        # The handoff copy is non-authoritative. Copy exact bytes, then verify
        # them against the captured snapshot so a concurrent source change can
        # never alter the proposal base silently.
        shutil.copyfile(source.path, temporary_path)
        copied = mutation.read_text_snapshot(temporary_path)
        if copied.content_hash != source.content_hash:
            raise mutation.MutationConflict(
                source.path, source.content_hash, copied.content_hash,
                operation="delegated.prepare.copy",
            )
        argv = normalize_command(command, temporary_path)
        env = None
        if environment is not None:
            env = os.environ.copy()
            env.update({str(key): str(value) for key, value in dict(environment).items()})
        try:
            completed = subprocess.run(
                argv,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=float(timeout),
                env=env,
                shell=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise DelegatedMutationError("Delegated command timed out after %.3fs." % float(timeout)) from exc
        if completed.returncode != 0:
            raise DelegatedMutationError(
                "Delegated command exited with %d: %s"
                % (completed.returncode, (completed.stderr or completed.stdout or "").strip())
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
                ("edited_revision", mutation.hash_text(edited.text, encoding=source.encoding, bom=source.bom)),
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
            )
        )
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
        raise DelegatedMutationError("Invalid delegated proposal state: %r" % proposal.get("state"))
    for key in ("id", "operation", "path", "before_revision", "edited_revision", "diff_sha256", "edited_text", "diff"):
        if not isinstance(proposal.get(key), str) or (key not in ("edited_text", "diff") and not proposal.get(key)):
            raise DelegatedMutationError("Delegated proposal requires string field %s." % key)
    expected_edited = mutation.hash_text(
        proposal["edited_text"],
        encoding=str(proposal.get("encoding") or "utf-8"),
        bom=bool(proposal.get("bom")),
    )
    if expected_edited != proposal["edited_revision"]:
        raise DelegatedMutationError("Delegated proposal edited_text hash does not match edited_revision.")
    expected_diff = hashlib.sha256(proposal["diff"].encode("utf-8")).hexdigest()
    if expected_diff != proposal["diff_sha256"]:
        raise DelegatedMutationError("Delegated proposal diff hash does not match diff_sha256.")
    validate_lifetxt_text(proposal["edited_text"])
    return proposal


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
    return OrderedDict((("path", absolute), ("revision", result.after_hash), ("changed", result.changed)))


def read_delegated_proposal(path):
    snapshot = mutation.read_text_snapshot(path)
    try:
        proposal = json.loads(snapshot.text, object_pairs_hook=OrderedDict)
    except ValueError as exc:
        raise DelegatedMutationError("Cannot parse delegated proposal %s: %s" % (snapshot.path, exc))
    validate_delegated_proposal(proposal)
    return proposal, snapshot


def apply_delegated_proposal(proposal, expected_revision=None, unsafe=False):
    validate_delegated_proposal(proposal)
    if proposal.get("state") != "prepared":
        raise DelegatedMutationError("Only prepared delegated proposals may be applied.")
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


def apply_delegated_proposal_file(path, expected_proposal_revision=None, expected_revision=None, unsafe=False, now=None):
    proposal, snapshot = read_delegated_proposal(path)
    if expected_proposal_revision is not None and snapshot.content_hash != expected_proposal_revision:
        raise mutation.MutationConflict(
            snapshot.path,
            expected_proposal_revision,
            snapshot.content_hash,
            operation="delegated.proposal.apply",
        )
    applied = apply_delegated_proposal(proposal, expected_revision=expected_revision, unsafe=unsafe)
    updated = OrderedDict(proposal)
    updated["state"] = "applied"
    updated["applied_at_utc"] = utc_now_text(now)
    updated["result"] = applied
    saved = write_delegated_proposal(snapshot.path, updated, expected_revision=snapshot.content_hash)
    applied["proposal_path"] = saved["path"]
    applied["proposal_revision"] = saved["revision"]
    return applied


def reject_delegated_proposal_file(path, expected_proposal_revision=None, reason=None, now=None):
    proposal, snapshot = read_delegated_proposal(path)
    if expected_proposal_revision is not None and snapshot.content_hash != expected_proposal_revision:
        raise mutation.MutationConflict(
            snapshot.path,
            expected_proposal_revision,
            snapshot.content_hash,
            operation="delegated.proposal.reject",
        )
    if proposal.get("state") != "prepared":
        raise DelegatedMutationError("Only prepared delegated proposals may be rejected.")
    updated = OrderedDict(proposal)
    updated["state"] = "rejected"
    updated["rejected_at_utc"] = utc_now_text(now)
    updated["rejection_reason"] = None if reason is None else str(reason)
    saved = write_delegated_proposal(snapshot.path, updated, expected_revision=snapshot.content_hash)
    return OrderedDict(
        (
            ("rejected", True),
            ("proposal_id", proposal["id"]),
            ("proposal_path", saved["path"]),
            ("proposal_revision", saved["revision"]),
        )
    )
