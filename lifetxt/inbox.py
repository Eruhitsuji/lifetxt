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
from .config import config_paths, config_section, config_user_name, config_write_file
from .model import Item
from .mutation import MutationConflict
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
    atomic_write_text(
        path, json.dumps(list(proposals), ensure_ascii=False, indent=2) + "\n"
    )


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


def new_proposal(
    operation,
    source,
    changes,
    warnings=None,
    expected_revision="",
    provenance=None,
    proposal_id=None,
    staged_target=None,
    idempotency_key=None,
):
    return OrderedDict(
        (
            ("proposal_version", PROPOSAL_VERSION),
            ("id", proposal_id or new_proposal_id()),
            ("operation", str(operation)),
            ("source", str(source)),
            ("expected_revision", str(expected_revision or "")),
            ("staged_target", str(staged_target) if staged_target else ""),
            ("idempotency_key", str(idempotency_key) if idempotency_key else ""),
            ("changes", list(changes)),
            ("warnings", list(warnings or [])),
            ("status", "pending"),
            ("provenance", provenance or OrderedDict()),
            ("created", _timestamp()),
        )
    )


def _default_proposal_target(config):
    """Resolve the same default accept target `command_proposal_accept`
    would use, so a stage-time revision snapshot describes the file the
    proposal will most likely be accepted into."""
    target = config_write_file(config)
    if target:
        return target
    paths = config_paths(config)
    return paths[0] if paths else "life.txt"


def _timestamp():
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime())


def stage_proposal(config, proposal):
    proposals = load_proposals(config)
    proposals.append(proposal)
    _save(config, proposals)
    return proposal


def _idempotent_match(proposals, idempotency_key, change):
    """Find an existing proposal already staged under ``idempotency_key``.

    Returns the matching proposal when its own recorded create-change is
    identical to ``change`` -- a safe-to-retry duplicate, such as an MCP
    client resubmitting `stage_proposal` after a dropped/timed-out response.
    Raises ``ValueError`` when the key was reused for a materially different
    request rather than silently creating a second proposal or silently
    reusing a mismatched one, mirroring the
    ``REMOTE_TRANSACTION_REUSED``/``event_matches`` precedent in
    :mod:`lifetxt.remote_ticket_write_core`. Returns ``None`` when the key is
    not registered yet, so the caller should stage a new proposal.
    """
    for proposal in proposals:
        if not proposal.get("idempotency_key"):
            continue
        if proposal["idempotency_key"] != idempotency_key:
            continue
        if _create_change(proposal) == change:
            return proposal
        raise ValueError(
            "idempotency_key %r was already used to stage a different "
            "request (existing proposal %r)." % (idempotency_key, proposal.get("id"))
        )
    return None


def stage_create(
    config,
    title,
    kind="T",
    details=None,
    source="manual",
    warnings=None,
    status="[ ]",
    idempotency_key=None,
):
    from .write_operations import snapshot

    change = build_create_change(kind=kind, title=title, details=details, status=status)
    if idempotency_key:
        existing = _idempotent_match(
            load_proposals(config), str(idempotency_key), change
        )
        if existing is not None:
            return existing
    target = _default_proposal_target(config)
    revision = snapshot(target, allow_missing=True).content_hash
    provenance = OrderedDict((("source", str(source)),))
    proposal = new_proposal(
        "create",
        source,
        [change],
        warnings=warnings,
        expected_revision=revision,
        provenance=provenance,
        staged_target=target,
        idempotency_key=idempotency_key,
    )
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


def edit_proposal(
    config, proposal_id, title=None, details=None, kind=None, status=None
):
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


def proposal_item(proposal):
    """The :class:`~lifetxt.model.Item` a create proposal's change describes,
    without serializing it -- shared by ``proposal_to_line`` and by
    ``apply_proposal``'s ticket-shape detection so both read the identical
    object rather than parsing the change dict twice."""
    change = _create_change(proposal)
    if change is None:
        raise ValueError("Proposal has no create change.")
    return Item(
        status=change.get("status") or "[ ]",
        kind=change.get("kind") or "T",
        title=change.get("title") or "",
        details=change.get("details") or {},
    )


def proposal_to_line(proposal):
    return item_to_line(proposal_item(proposal))


def _ticket_creation_event_line(item, config):
    """A companion ``record:ticket_event`` line for a ticket-shaped create
    proposal, or ``None`` when the proposal is not ticket-shaped or lacks the
    ``id:`` a ticket contract requires (staging does not auto-generate one
    the way ``ticket new`` does, so a proposal missing it cannot get a
    meaningful event either)."""
    from .ticket_project_values import is_ticket

    if not is_ticket(item):
        return None
    ticket_id = (item.details.get("id") or [None])[0]
    if not ticket_id:
        return None
    from .ticket_activity import build_creation_event

    author = (item.details.get("assignee") or [None])[0] or config_user_name(config)
    project = (item.details.get("project") or [None])[0]
    tracker = (item.details.get("tracker") or [None])[0]
    event = build_creation_event(
        ticket_id, author=author, project=project, tracker=tracker
    )
    return item_to_line(event)


def apply_proposal(
    config, proposal, target, expected_revision=None, use_staged_revision=True
):
    """Append a create proposal's item to ``target`` and mark it accepted.

    If the caller does not explicitly supply ``expected_revision``, and
    ``use_staged_revision`` is true, and the proposal's own ``staged_target``
    matches ``target``, the revision captured when the proposal was staged is
    used: a workspace that has materially changed since then is refused with
    a distinct stale-proposal error instead of silently rebasing onto
    whatever ``target`` currently contains. A ``staged_target`` mismatch
    (accepting into a different file than the one assumed at stage time)
    intentionally skips this check, since the captured revision does not
    describe ``target``. ``use_staged_revision=False`` lets
    :func:`batch_apply` accept several proposals staged before any of them
    were applied without each later one seeing an earlier one's own
    just-written change as external staleness.

    A ticket-shaped create proposal (``record:ticket`` on a ``T`` item, with
    an ``id:``) also gets its ``record:ticket_event`` creation entry
    appended in the same write, matching what ``ticket new`` produces --
    accepting such a proposal is no longer indistinguishable, in the audit
    trail, from a ticket that was never audited at all.
    """
    from .write_operations import append_life_records

    item = proposal_item(proposal)
    line = item_to_line(item)
    event_line = _ticket_creation_event_line(item, config)
    text = line if event_line is None else line + "\n" + event_line
    revision = expected_revision
    if (
        revision is None
        and use_staged_revision
        and proposal.get("staged_target") == target
    ):
        revision = proposal.get("expected_revision") or None
    try:
        result = append_life_records(
            target,
            text + "\n",
            expected_revision=revision,
            operation="inbox.accept",
        )
    except MutationConflict:
        raise ValueError(
            "Proposal %r is stale: %s changed since it was staged. "
            "Review the current file and re-stage if the change still "
            "applies." % (proposal.get("id"), target)
        )
    set_status(config, proposal["id"], "accepted")
    outcome = OrderedDict(
        (
            ("id", proposal["id"]),
            ("applied", True),
            ("target", target),
            ("line", line),
            ("result", result),
        )
    )
    if event_line is not None:
        outcome["event_line"] = event_line
    return outcome


def accept(
    config, proposal_id, target, expected_revision=None, use_staged_revision=True
):
    proposal = get_proposal(config, proposal_id)
    if proposal is None:
        raise ValueError("Unknown proposal %r." % proposal_id)
    if proposal.get("status") == "accepted":
        raise ValueError("Proposal %r is already accepted." % proposal_id)
    return apply_proposal(
        config, proposal, target, expected_revision, use_staged_revision
    )


def reject(config, proposal_id):
    return set_status(config, proposal_id, "rejected")


def defer(config, proposal_id):
    return set_status(config, proposal_id, "deferred")


def batch_apply(config, proposal_ids, target, expected_revision=None):
    """Apply several proposals, reporting per-proposal outcomes.

    Only the first proposal in the batch is checked against its own
    stage-time revision (protecting against a change external to this
    batch); once one proposal has been applied, later proposals in the same
    batch skip their own stage-time check, since this batch's own earlier
    writes are expected to have moved the target past what any of them
    individually saw when staged.
    """
    results = []
    use_staged_revision = True
    for proposal_id in proposal_ids:
        try:
            results.append(
                accept(
                    config,
                    proposal_id,
                    target,
                    expected_revision,
                    use_staged_revision=use_staged_revision,
                )
            )
            expected_revision = None  # revision changes after the first append
            use_staged_revision = False
        except ValueError as exc:
            results.append(
                OrderedDict(
                    (("id", proposal_id), ("applied", False), ("error", str(exc)))
                )
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
