"""Unified Inbox: reviewable proposals before authoritative writes.

Quick captures, MCP suggestions, and (later) remote/integration events are
staged as ``proposal-v1`` records in an operational store rather than written
straight into life.txt. A person reviews each proposal and accepts, edits,
rejects, defers, or batch-applies it. Only on accept is the change appended to
the workspace write target through the same validated, atomic writer as every
other authoritative mutation.

The store is operational, not authoritative: it holds pending intentions, never
the life.txt truth. Accepting a proposal is the single point where an intention
becomes a record.
"""

from __future__ import unicode_literals

import json
import os
import time
import uuid
from collections import OrderedDict

from .atomic import atomic_write_text
from .config import config_section
from .model import Item
from .serializer import item_to_line


PROPOSAL_VERSION = "1"
STATUSES = ("pending", "accepted", "rejected", "deferred")
DEFAULT_STORE = os.path.join(".cache", "lifetxt", "proposals.json")


def proposals_path(config):
    section = config_section(config, "inbox")
    path = section.get("proposals_file") or DEFAULT_STORE
    return os.path.expanduser(str(path))


def load_proposals(config):
    path = proposals_path(config)
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return []
    if isinstance(data, dict):
        data = data.get("proposals", [])
    return [p for p in data if isinstance(p, dict)]


def _save(config, proposals):
    path = proposals_path(config)
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    atomic_write_text(path, json.dumps(list(proposals), ensure_ascii=False, indent=2) + "\n")


def new_proposal_id():
    return "P-" + uuid.uuid4().hex[:8]


def build_create_change(kind="T", title="", details=None, status="[ ]"):
    return OrderedDict(
        (
            ("op", "create"),
            ("kind", str(kind)),
            ("status", str(status)),
            ("title", str(title)),
            ("details", _normalize_details(details)),
        )
    )


def _normalize_details(details):
    result = OrderedDict()
    for key, value in (details or {}).items():
        if value in (None, ""):
            continue
        if isinstance(value, (list, tuple)):
            values = [str(v) for v in value if str(v) != ""]
        else:
            values = [str(value)]
        if values:
            result[str(key)] = values
    return result


def new_proposal(operation, source, changes, warnings=None, expected_revision="",
                 provenance=None, proposal_id=None):
    return OrderedDict(
        (
            ("proposal_version", PROPOSAL_VERSION),
            ("id", proposal_id or new_proposal_id()),
            ("operation", str(operation)),
            ("source", str(source)),
            ("expected_revision", str(expected_revision or "")),
            ("changes", list(changes)),
            ("warnings", list(warnings or [])),
            ("status", "pending"),
            ("provenance", provenance or OrderedDict()),
            ("created", _timestamp()),
        )
    )


def _timestamp():
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime())


def stage_proposal(config, proposal):
    proposals = load_proposals(config)
    proposals.append(proposal)
    _save(config, proposals)
    return proposal


def stage_create(config, title, kind="T", details=None, source="manual",
                 warnings=None, status="[ ]"):
    change = build_create_change(kind=kind, title=title, details=details, status=status)
    proposal = new_proposal("create", source, [change], warnings=warnings)
    return stage_proposal(config, proposal)


def list_proposals(config, status=None):
    proposals = load_proposals(config)
    if status:
        proposals = [p for p in proposals if p.get("status") == status]
    return proposals


def get_proposal(config, proposal_id):
    for proposal in load_proposals(config):
        if proposal.get("id") == proposal_id:
            return proposal
    return None


def set_status(config, proposal_id, status):
    if status not in STATUSES:
        raise ValueError("Unknown proposal status %r." % status)
    proposals = load_proposals(config)
    found = False
    for proposal in proposals:
        if proposal.get("id") == proposal_id:
            proposal["status"] = status
            found = True
    if not found:
        raise ValueError("Unknown proposal %r." % proposal_id)
    _save(config, proposals)
    return get_proposal(config, proposal_id)


def edit_proposal(config, proposal_id, title=None, details=None, kind=None, status=None):
    """Edit a pending create proposal's fields before it is applied."""
    proposals = load_proposals(config)
    target = None
    for proposal in proposals:
        if proposal.get("id") == proposal_id:
            target = proposal
            break
    if target is None:
        raise ValueError("Unknown proposal %r." % proposal_id)
    if target.get("status") != "pending":
        raise ValueError("Only pending proposals can be edited.")
    change = _create_change(target)
    if change is None:
        raise ValueError("Proposal %r is not a create proposal." % proposal_id)
    if title is not None:
        change["title"] = str(title)
    if kind is not None:
        change["kind"] = str(kind)
    if status is not None:
        change["status"] = str(status)
    if details:
        merged = OrderedDict(change.get("details") or {})
        merged.update(_normalize_details(details))
        change["details"] = merged
    _save(config, proposals)
    return target


def _create_change(proposal):
    for change in proposal.get("changes", []):
        if isinstance(change, dict) and change.get("op") == "create":
            return change
    return None


def proposal_to_line(proposal):
    change = _create_change(proposal)
    if change is None:
        raise ValueError("Proposal has no create change.")
    item = Item(
        status=change.get("status") or "[ ]",
        kind=change.get("kind") or "T",
        title=change.get("title") or "",
        details=change.get("details") or {},
    )
    return item_to_line(item)


def apply_proposal(config, proposal, target, expected_revision=None):
    """Append a create proposal's item to ``target`` and mark it accepted."""
    from .write_operations import append_life_records

    line = proposal_to_line(proposal)
    result = append_life_records(
        target, line + "\n",
        expected_revision=expected_revision,
        operation="inbox.accept",
    )
    set_status(config, proposal["id"], "accepted")
    return OrderedDict(
        (
            ("id", proposal["id"]),
            ("applied", True),
            ("target", target),
            ("line", line),
            ("result", result),
        )
    )


def accept(config, proposal_id, target, expected_revision=None):
    proposal = get_proposal(config, proposal_id)
    if proposal is None:
        raise ValueError("Unknown proposal %r." % proposal_id)
    if proposal.get("status") == "accepted":
        raise ValueError("Proposal %r is already accepted." % proposal_id)
    return apply_proposal(config, proposal, target, expected_revision)


def reject(config, proposal_id):
    return set_status(config, proposal_id, "rejected")


def defer(config, proposal_id):
    return set_status(config, proposal_id, "deferred")


def batch_apply(config, proposal_ids, target, expected_revision=None):
    """Apply several proposals, reporting per-proposal outcomes."""
    results = []
    for proposal_id in proposal_ids:
        try:
            results.append(accept(config, proposal_id, target, expected_revision))
            expected_revision = None  # revision changes after the first append
        except ValueError as exc:
            results.append(
                OrderedDict((("id", proposal_id), ("applied", False), ("error", str(exc))))
            )
    applied = sum(1 for r in results if r.get("applied"))
    return OrderedDict(
        (("applied", applied), ("total", len(proposal_ids)), ("results", results))
    )


def inbox_summary(config):
    proposals = load_proposals(config)
    counts = OrderedDict((status, 0) for status in STATUSES)
    for proposal in proposals:
        status = proposal.get("status", "pending")
        counts[status] = counts.get(status, 0) + 1
    return OrderedDict(
        (
            ("total", len(proposals)),
            ("counts", counts),
            ("pending", [p for p in proposals if p.get("status") == "pending"]),
        )
    )
