"""``archive-plan-v1``: a reviewable, machine-readable pre-write archive plan.

Produced by ``lifetxt project archive --dry-run --emit-plan PATH`` and
consumed by ``lifetxt project archive --apply-plan PLAN`` (#254/#255,
following up on the production zero-byte data-loss incident #183).

Design summary (see ``.ai/project/changes/project-archive-plan-v1/`` for the
full change package):

* A plan freezes every input to an eventual live archive -- resolved
  workspace/config identity, exact source and destination revisions, the
  selected item-ID set, and the archive parameters -- as one JSON document a
  human or script can review before anything is written.
* ``--apply-plan`` re-verifies every one of those frozen facts against
  *current* state before delegating to the existing, already-hardened
  ``command_archive`` write path. Any drift -- a changed file, a changed
  config, a changed candidate selection, an unsupported plan version, a
  plan file that fails its own self-consistency check, or unreachable
  recovery evidence -- is refused loudly before any write, mirroring the
  precede-side-effects discipline ``archive_safety_v3.py`` already
  established for the ad-hoc ``--revision`` path.
* ``plan_hash`` is a self-consistency checksum (SHA-256 over the plan's own
  fields, stored in the same file), not a signature: it catches accidental
  corruption or a hand-edited field, not a deliberate forgery. A plan file
  must be kept under the same trust as any other local input to this
  command -- see ``verify_plan_hash``'s docstring and ``decisions.md`` in
  the change package.
* This module intentionally does not build new transaction/journal
  pre-registration machinery: ``reserved_transaction_id`` is a plan-identity
  value for audit correlation, not a value threaded into the underlying
  journal transaction (see ``decisions.md`` in the change package for why
  that is out of scope here).
"""

from __future__ import unicode_literals

import getpass
import hashlib
import json
import os
import socket
import sys
import uuid

PLAN_VERSION = 1
SUPPORTED_PLAN_VERSIONS = (1,)

SCHEMA_NAME = "archive-plan-v1.schema.json"

# Mirrors command_archive's own external-reference warning keys
# (lifetxt/cli.py's _ext_ref_keys) so the plan's recorded effects match what
# the existing dry-run text already warns about.
_EXTERNAL_REF_KEYS = ("depends_on", "blocks", "parent", "ref", "related")


def _canonical_json(fields):
    """Deterministic serialization used for both hashing and file content.

    ``sort_keys=True`` makes the result independent of Python dict
    iteration/insertion order, so re-hashing a round-tripped (loaded then
    re-serialized) plan always reproduces the same bytes regardless of JSON
    object key order on disk.
    """
    return json.dumps(fields, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def compute_plan_hash(fields):
    """Hash over the plan's own canonical field serialization.

    ``fields`` must not include ``plan_hash`` itself -- the hash covers
    every other field so any post-emission edit to the plan file is
    detectable at apply time.
    """
    canonical = _canonical_json(fields)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _writer_identity():
    process = os.path.basename(sys.argv[0]) if sys.argv else "lifetxt"
    if not process:
        process = "lifetxt"
    try:
        user = getpass.getuser()
    except Exception:
        user = None
    try:
        host = socket.gethostname()
    except Exception:
        host = None
    return {
        "process": process,
        "pid": os.getpid(),
        "host": host,
        "user": user,
    }


def build_plan(
    project,
    workspace_name,
    config_path,
    config_revision,
    sources,
    destination_path,
    destination_revision,
    selected_item_ids,
    external_references,
    parameters,
    now_iso,
):
    """Build a complete, hashed ``archive-plan-v1`` document.

    ``sources`` is a list of ``(path, revision)`` tuples in scan order.
    ``external_references`` is a list of dicts already shaped for the plan
    (see ``_external_reference_rows``). ``parameters`` freezes the archive
    selection/execution parameters so ``--apply-plan`` never has to re-read
    current CLI flags for them.
    """
    fields = {
        "plan_version": PLAN_VERSION,
        "created_at": now_iso,
        "project": project,
        "workspace": {
            "name": workspace_name,
            "config_path": config_path,
            "config_revision": config_revision,
        },
        "sources": [{"path": path, "revision": revision} for path, revision in sources],
        "destination": {
            "path": destination_path,
            "revision": destination_revision,
        },
        "selected_item_ids": sorted(str(v) for v in selected_item_ids),
        "external_references": external_references,
        "parameters": parameters,
        "writer": _writer_identity(),
        "reserved_transaction_id": uuid.uuid4().hex,
    }
    plan = dict(fields)
    plan["plan_hash"] = compute_plan_hash(fields)
    return plan


def external_reference_rows(external_refs):
    """Shape ``_archive_select``'s ``external_refs`` tuples for the plan.

    Mirrors exactly what ``command_archive``'s dry-run warning prints
    (location, line, title, key, referenced id), per #254's acceptance
    criterion that plan effects mirror the existing dry-run warning content.
    """
    rows = []
    for item, key, ref_id in external_refs:
        location = getattr(item, "source", None) or None
        rows.append(
            {
                "source_path": location,
                "line": getattr(item, "line", None),
                "title": getattr(item, "title", None),
                "key": key,
                "referenced_id": ref_id,
            }
        )
    return rows


def write_plan(path, plan):
    """Write a plan document atomically as canonical, human-readable JSON."""
    from .atomic import atomic_write_text

    text = json.dumps(plan, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    atomic_write_text(path, text, encoding="utf-8")


def load_plan(path):
    """Load and minimally structurally validate a plan document.

    Raises ``ValueError`` (never a bare I/O or JSON exception) so every
    caller can treat plan-loading failures the same way it treats every
    other pre-write refusal.
    """
    try:
        with open(path, "r", encoding="utf-8") as handle:
            raw = handle.read()
    except OSError as exc:
        raise ValueError("Cannot read archive plan %s: %s" % (path, exc))
    try:
        plan = json.loads(raw)
    except ValueError as exc:
        raise ValueError("Archive plan %s is not valid JSON: %s" % (path, exc))
    if not isinstance(plan, dict):
        raise ValueError("Archive plan %s must be a JSON object." % path)
    for required in (
        "plan_version",
        "created_at",
        "project",
        "workspace",
        "sources",
        "destination",
        "selected_item_ids",
        "external_references",
        "parameters",
        "writer",
        "reserved_transaction_id",
        "plan_hash",
    ):
        if required not in plan:
            raise ValueError(
                "Archive plan %s is missing required field %r." % (path, required)
            )
    return plan


def verify_plan_version(plan):
    """Reject an unknown or future ``plan_version`` before any write."""
    version = plan.get("plan_version")
    if version not in SUPPORTED_PLAN_VERSIONS:
        raise ValueError(
            "Archive plan has unsupported plan_version %r. Supported: %s."
            % (version, ", ".join(str(v) for v in SUPPORTED_PLAN_VERSIONS))
        )


def verify_plan_hash(plan):
    """Re-verify the plan's self-consistency hash before any write.

    ``plan_hash`` is a SHA-256 over the plan's own fields, stored inside the
    same file it covers. It has no external key, so it does *not*
    authenticate the plan's origin or defend against a deliberate actor who
    can edit the plan file (they can trivially recompute a matching hash
    after editing any field). It catches accidental corruption or a
    hand-edited field -- the same class of protection a checksum gives, not
    a signature. Callers must not treat a passing ``verify_plan_hash`` as
    proof the plan's `sources`/`destination` paths are safe to trust; that
    guarantee instead comes from re-deriving those paths from the *current*
    workspace resolution, not from anything recorded in the plan.
    """
    recorded = plan.get("plan_hash")
    fields = dict(plan)
    fields.pop("plan_hash", None)
    expected = compute_plan_hash(fields)
    if not isinstance(recorded, str) or recorded != expected:
        raise ValueError(
            "Archive plan consistency check failed: the plan file does not "
            "match its own recorded hash (plan_hash mismatch) -- it may "
            "have been hand-edited or corrupted since it was emitted. This "
            "check detects accidental modification, not a deliberately "
            "forged plan; keep plan files under the same trust as any other "
            "local input to this command. Re-emit the plan with --emit-plan "
            "and review it again before applying."
        )


def verify_revisions_unchanged(plan, current_source_revisions, current_dest_revision):
    """Reject the plan if any recorded source/destination revision drifted."""
    recorded_sources = {row["path"]: row["revision"] for row in plan.get("sources", [])}
    mismatches = []
    for path, expected in recorded_sources.items():
        actual = current_source_revisions.get(path)
        if actual is None:
            mismatches.append(
                "%s: recorded in plan but no longer resolvable as a source" % path
            )
        elif str(actual) != str(expected):
            mismatches.append(
                "%s: plan expected %s, found %s" % (path, expected, actual)
            )
    destination = plan.get("destination") or {}
    dest_path = destination.get("path")
    dest_expected = destination.get("revision")
    if dest_path and str(current_dest_revision) != str(dest_expected):
        mismatches.append(
            "%s: plan expected %s, found %s"
            % (dest_path, dest_expected, current_dest_revision)
        )
    if mismatches:
        raise ValueError(
            "Archive plan is stale: the following file(s) changed since the "
            "plan was emitted: %s. Re-run --dry-run --emit-plan to produce a "
            "current plan." % "; ".join(mismatches)
        )


def verify_workspace_revision_unchanged(plan, current_config_revision):
    """Reject the plan if the workspace/config revision drifted."""
    recorded = (plan.get("workspace") or {}).get("config_revision")
    if str(current_config_revision) != str(recorded):
        raise ValueError(
            "Archive plan is stale: the workspace configuration changed "
            "since the plan was emitted (recorded revision %s, found %s). "
            "Re-run --dry-run --emit-plan to produce a current plan."
            % (recorded, current_config_revision)
        )


def verify_selection_unchanged(plan, current_item_ids):
    """Reject the plan if the re-derived candidate selection differs."""
    recorded = sorted(str(v) for v in plan.get("selected_item_ids", []))
    current = sorted(str(v) for v in current_item_ids)
    if recorded != current:
        added = sorted(set(current) - set(recorded))
        removed = sorted(set(recorded) - set(current))
        detail_parts = []
        if added:
            detail_parts.append("newly selected: %s" % ", ".join(added))
        if removed:
            detail_parts.append("no longer selected: %s" % ", ".join(removed))
        detail = "; ".join(detail_parts) or "selection differs"
        raise ValueError(
            "Archive plan is stale: the current candidate selection no "
            "longer matches the plan's frozen item list (%s). Re-run "
            "--dry-run --emit-plan to produce a current plan." % detail
        )


def journal_directory_reachable(directory):
    """Best-effort check that recovery evidence storage is reachable.

    Does not create anything: ``transaction_journal.prepare`` already
    creates the transaction journal directory on demand. This only confirms
    that doing so is plausible -- the directory already exists and is
    writable, or its nearest existing ancestor is -- before any archive
    write begins, closing the gap where a read-only or missing journal
    volume would only be discovered mid-write.
    """
    directory = os.path.abspath(directory)
    if os.path.isdir(directory):
        return os.access(directory, os.W_OK)
    parent = os.path.dirname(directory)
    seen = set()
    while parent and parent not in seen and not os.path.exists(parent):
        seen.add(parent)
        next_parent = os.path.dirname(parent)
        if next_parent == parent:
            break
        parent = next_parent
    return bool(parent) and os.path.isdir(parent) and os.access(parent, os.W_OK)


def verify_recovery_evidence_reachable(journal_dir):
    if not journal_directory_reachable(journal_dir):
        raise ValueError(
            "Archive plan cannot be applied: the transaction recovery "
            "directory %s is not reachable (missing and not creatable, or "
            "not writable). Fix storage access before applying." % journal_dir
        )
