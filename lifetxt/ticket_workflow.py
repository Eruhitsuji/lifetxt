"""Versioned development-ticket workflow contracts.

The effective workflow is configuration-backed but has deterministic defaults.
Every transition is checked before the same-file ticket/event compound mutation.
"""

from __future__ import unicode_literals

import copy
from collections import OrderedDict

from .ticket_activity import EVENT_TYPES, _first, configured_activities
from .ticket_activity_mutation import apply_ticket_activity

WORKFLOW_SCHEMA = "ticket-workflow-v1.schema.json"

DEFAULT_TRANSITIONS = OrderedDict(
    (
        (
            "new",
            {
                "from": ["resolved", "closed", "rejected", "duplicate", "wont_fix"],
                "event": "reopened",
                "unset": ["resolution", "closed_by"],
            },
        ),
        ("triaged", {"from": ["new"], "event": "transition"}),
        (
            "assigned",
            {
                "from": ["new", "triaged"],
                "required_fields": ["assignee"],
                "event": "assignment",
            },
        ),
        (
            "in_progress",
            {
                "from": [
                    "new",
                    "triaged",
                    "assigned",
                    "review",
                    "testing",
                    "blocked",
                    "needs_info",
                    "deferred",
                ],
                "event": "transition",
            },
        ),
        ("review", {"from": ["in_progress", "testing"], "event": "transition"}),
        ("testing", {"from": ["in_progress", "review"], "event": "transition"}),
        (
            "needs_info",
            {
                "from": [
                    "new",
                    "triaged",
                    "assigned",
                    "in_progress",
                    "review",
                    "testing",
                ],
                "event": "transition",
            },
        ),
        (
            "blocked",
            {
                "from": [
                    "new",
                    "triaged",
                    "assigned",
                    "in_progress",
                    "review",
                    "testing",
                ],
                "event": "transition",
            },
        ),
        (
            "deferred",
            {
                "from": [
                    "new",
                    "triaged",
                    "assigned",
                    "in_progress",
                    "review",
                    "testing",
                    "needs_info",
                    "blocked",
                ],
                "event": "transition",
            },
        ),
        (
            "resolved",
            {
                "from": ["in_progress", "review", "testing", "blocked", "needs_info"],
                "resolution_required": True,
                "event": "closed",
            },
        ),
        (
            "closed",
            {
                "from": ["resolved"],
                "resolution_required": True,
                "event": "closed",
            },
        ),
        (
            "rejected",
            {
                "from": [
                    "new",
                    "triaged",
                    "assigned",
                    "in_progress",
                    "review",
                    "testing",
                    "needs_info",
                    "blocked",
                    "deferred",
                ],
                "resolution_required": True,
                "event": "closed",
            },
        ),
        (
            "duplicate",
            {
                "from": [
                    "new",
                    "triaged",
                    "assigned",
                    "in_progress",
                    "review",
                    "testing",
                ],
                "required_fields": ["duplicate_of"],
                "event": "closed",
            },
        ),
        (
            "wont_fix",
            {
                "from": [
                    "new",
                    "triaged",
                    "assigned",
                    "in_progress",
                    "review",
                    "testing",
                    "needs_info",
                    "blocked",
                    "deferred",
                ],
                "resolution_required": True,
                "event": "closed",
            },
        ),
    )
)

TERMINAL_LIFE_STATUSES = ("[x]", "[-]")


def _diag(code, message, hint=None):
    return OrderedDict(
        (
            ("severity", "error"),
            ("code", code),
            ("message", message),
            ("hint", hint or "Fix ticketing.workflow before using ticket transitions."),
        )
    )


def _string_list(value):
    if value in (None, ""):
        return []
    source = value.keys() if isinstance(value, dict) else value
    if not isinstance(source, (list, tuple, set, frozenset, type({}.keys()))):
        source = [source]
    result = []
    for entry in source:
        text = str(entry).strip()
        if text and text not in result:
            result.append(text)
    return result


def _bool(value, default=False):
    if value is None:
        return bool(default)
    if isinstance(value, bool):
        return value
    raise ValueError("must be a boolean")


def _workflow_section(config=None):
    config = config or {}
    ticketing = config.get("ticketing") if isinstance(config, dict) else None
    ticketing = ticketing if isinstance(ticketing, dict) else {}
    raw = ticketing.get("workflow")
    if raw is None:
        raw = ticketing.get("workflows")
        if isinstance(raw, dict) and "default" in raw:
            raw = raw.get("default")
    return raw if isinstance(raw, dict) else {}


def _normalize_transition(target, raw, status_names, diagnostics):
    if isinstance(raw, (list, tuple)):
        raw = {"from": list(raw)}
    if not isinstance(raw, dict):
        diagnostics.append(
            _diag("TK011", "Workflow transition %r must be an object." % target)
        )
        raw = {}
    allowed = {
        "from",
        "roles",
        "required_fields",
        "resolution_required",
        "event",
        "set",
        "unset",
        "comment_required",
        "label",
        "description",
    }
    unknown = sorted(set(raw) - allowed)
    if unknown:
        diagnostics.append(
            _diag(
                "TK011",
                "Workflow transition %r has unknown keys: %s."
                % (target, ", ".join(unknown)),
            )
        )
    sources = _string_list(raw.get("from"))
    for source in sources:
        if source not in status_names:
            diagnostics.append(
                _diag(
                    "TK012",
                    "Workflow transition to %r references unknown source status %r."
                    % (target, source),
                )
            )
    roles = _string_list(raw.get("roles"))
    required_fields = _string_list(raw.get("required_fields"))
    event_type = str(raw.get("event") or "transition")
    if event_type not in EVENT_TYPES:
        diagnostics.append(
            _diag(
                "TK013",
                "Workflow transition to %r uses unsupported event %r."
                % (target, event_type),
            )
        )
        event_type = "transition"
    set_fields = raw.get("set") or {}
    if not isinstance(set_fields, dict):
        diagnostics.append(
            _diag("TK014", "Workflow transition %r set must be an object." % target)
        )
        set_fields = {}
    unset_fields = _string_list(raw.get("unset"))
    try:
        resolution_required = _bool(raw.get("resolution_required"), False)
        comment_required = _bool(raw.get("comment_required"), False)
    except ValueError:
        diagnostics.append(
            _diag(
                "TK014", "Workflow transition %r boolean metadata is invalid." % target
            )
        )
        resolution_required = False
        comment_required = False
    return OrderedDict(
        (
            ("to", str(target)),
            ("from", sources),
            ("roles", roles),
            ("required_fields", required_fields),
            ("resolution_required", resolution_required),
            ("comment_required", comment_required),
            ("event", event_type),
            ("set", OrderedDict((str(k), str(v)) for k, v in set_fields.items())),
            ("unset", unset_fields),
            ("label", str(raw.get("label") or target)),
            ("description", str(raw.get("description") or "")),
        )
    )


def effective_workflow(config=None):
    """Return the normalized workflow plus diagnostics and source provenance."""
    from .tickets import status_map

    statuses = status_map(config or {})
    status_names = list(statuses)
    configured = _workflow_section(config)
    raw_transitions = (
        configured.get("transitions")
        if isinstance(configured.get("transitions"), dict)
        else {}
    )
    replace_defaults = (
        bool(configured.get("replace_defaults"))
        if isinstance(configured, dict)
        else False
    )
    merged = OrderedDict()
    if not replace_defaults:
        for target, value in DEFAULT_TRANSITIONS.items():
            if target in statuses:
                merged[target] = copy.deepcopy(value)
    for target, value in raw_transitions.items():
        merged[str(target)] = value
    diagnostics = []
    transitions = OrderedDict()
    for target, raw in merged.items():
        if target not in statuses:
            diagnostics.append(
                _diag("TK012", "Workflow target status %r is not configured." % target)
            )
            continue
        transitions[target] = _normalize_transition(
            target, raw, status_names, diagnostics
        )
    initial = str(configured.get("initial_status") or "new")
    if initial not in statuses:
        diagnostics.append(
            _diag("TK012", "Workflow initial_status %r is not configured." % initial)
        )
    local_role = str(configured.get("local_role") or "administrator")
    return OrderedDict(
        (
            ("schema", WORKFLOW_SCHEMA),
            ("contract_version", "1"),
            ("valid", not diagnostics),
            (
                "source",
                "configured+defaults"
                if raw_transitions and not replace_defaults
                else ("configured" if raw_transitions else "defaults"),
            ),
            ("replace_defaults", replace_defaults),
            ("initial_status", initial),
            ("local_role", local_role),
            ("statuses", OrderedDict((name, statuses[name]) for name in statuses)),
            ("transitions", transitions),
            ("activities", list(configured_activities(config))),
            ("diagnostics", diagnostics),
        )
    )


def workflow_contract(config=None, tracker=None, project=None, role=None):
    report = effective_workflow(config)
    result = OrderedDict(report)
    role_value = str(role or report["local_role"])
    transitions = OrderedDict()
    for target, transition in report["transitions"].items():
        value = OrderedDict(transition)
        roles = transition.get("roles") or []
        value["allowed_for_role"] = (
            role_value == "administrator" or not roles or role_value in roles
        )
        value["tracker"] = tracker
        value["project"] = project
        transitions[target] = value
    result["role"] = role_value
    result["transitions"] = transitions
    result["remote_write_enforcement"] = False
    result["exact_revision_required"] = True
    return result


def _ticket_status(item):
    return str(_first(item, "ticket_status", ""))


def _field_present(item, key, pending=None):
    if pending and key in pending:
        value = pending[key]
        if value is None:
            return False
        if isinstance(value, (list, tuple)):
            return any(str(entry) for entry in value)
        return bool(str(value))
    return bool(getattr(item, "details", {}).get(key))


def transition_plan(
    item,
    target_status,
    config=None,
    role=None,
    comment=None,
    resolution=None,
    extra_updates=None,
):
    from .tickets import status_map

    report = effective_workflow(config)
    if not report["valid"]:
        raise ValueError(report["diagnostics"])
    target = str(target_status)
    transition = report["transitions"].get(target)
    if transition is None:
        raise ValueError(
            "No workflow transition is configured for target status %r." % target
        )
    current = _ticket_status(item)
    if current == target:
        raise ValueError("Ticket is already in ticket_status %s." % target)
    allowed_sources = transition.get("from") or []
    if allowed_sources and current not in allowed_sources:
        raise ValueError(
            "Transition %s -> %s is not allowed." % (current or "<unset>", target)
        )
    role_value = str(role or report["local_role"])
    allowed_roles = transition.get("roles") or []
    if (
        role_value != "administrator"
        and allowed_roles
        and role_value not in allowed_roles
    ):
        raise ValueError("Role %r cannot transition to %s." % (role_value, target))
    updates = OrderedDict()
    for key, value in transition.get("set", {}).items():
        updates[key] = value
    for key in transition.get("unset", []):
        updates[key] = None
    for key, value in (extra_updates or {}).items():
        updates[str(key)] = value
    updates["ticket_status"] = target
    if resolution not in (None, ""):
        updates["resolution"] = str(resolution)
    if transition.get("resolution_required") and not _field_present(
        item, "resolution", updates
    ):
        raise ValueError("Transition to %s requires resolution." % target)
    if transition.get("comment_required") and not str(comment or "").strip():
        raise ValueError("Transition to %s requires a comment." % target)
    missing = [
        field
        for field in transition.get("required_fields", [])
        if not _field_present(item, field, updates)
    ]
    if missing:
        raise ValueError(
            "Transition to %s requires fields: %s." % (target, ", ".join(missing))
        )
    life_status = status_map(config or {}).get(target)
    if not life_status:
        raise ValueError("ticket_status %r has no life status mapping." % target)
    event_type = transition.get("event") or "transition"
    if life_status in TERMINAL_LIFE_STATUSES and event_type == "transition":
        event_type = "closed"
    if (
        current
        and status_map(config or {}).get(current) in TERMINAL_LIFE_STATUSES
        and life_status not in TERMINAL_LIFE_STATUSES
    ):
        event_type = "reopened"
        updates["resolution"] = None
        updates["closed_by"] = None
    if life_status in TERMINAL_LIFE_STATUSES:
        updates["closed_by"] = str(_first(item, "closed_by") or "")
    return OrderedDict(
        (
            ("from", current),
            ("to", target),
            ("life_status", life_status),
            ("role", role_value),
            ("event", event_type),
            ("detail_updates", updates),
            ("required_fields", list(transition.get("required_fields") or [])),
            ("resolution_required", bool(transition.get("resolution_required"))),
            ("comment_required", bool(transition.get("comment_required"))),
        )
    )


def apply_transition(
    path,
    ticket_id,
    target_status,
    actor,
    role,
    expected_revision,
    config=None,
    key="id",
    comment=None,
    resolution=None,
    extra_updates=None,
    at=None,
    transaction_id=None,
    dry_run=False,
):
    from . import mutation
    from .ticket_activity_mutation import _find_ticket, _parse_items

    snapshot = mutation.read_text_snapshot(path, allow_missing=False)
    items = _parse_items(snapshot.text, key)
    ticket = _find_ticket(items, ticket_id, key)
    plan = transition_plan(
        ticket,
        target_status,
        config=config,
        role=role,
        comment=comment,
        resolution=resolution,
        extra_updates=extra_updates,
    )
    updates = OrderedDict(plan["detail_updates"])
    if plan["life_status"] in TERMINAL_LIFE_STATUSES:
        updates["closed_by"] = str(actor or "local")
    result = apply_ticket_activity(
        path,
        ticket_id,
        plan["event"],
        actor,
        expected_revision,
        config=config,
        key=key,
        detail_updates=updates,
        status=plan["life_status"],
        comment=comment,
        at=at,
        event_extra={"role": plan["role"]},
        transaction_id=transaction_id,
        dry_run=dry_run,
        operation="ticket.transition",
    )
    result["workflow"] = plan
    return result


def apply_comment(
    path,
    ticket_id,
    body,
    author,
    expected_revision,
    config=None,
    key="id",
    at=None,
    transaction_id=None,
    dry_run=False,
):
    if not str(body or "").strip():
        raise ValueError("Ticket comment must not be empty.")
    return apply_ticket_activity(
        path,
        ticket_id,
        "comment",
        author,
        expected_revision,
        config=config,
        key=key,
        comment=str(body),
        at=at,
        transaction_id=transaction_id,
        dry_run=dry_run,
        operation="ticket.comment",
    )


def apply_watch(
    path,
    ticket_id,
    watcher,
    author,
    expected_revision,
    add=True,
    config=None,
    key="id",
    at=None,
    transaction_id=None,
    dry_run=False,
):
    from . import mutation
    from .ticket_activity_mutation import _find_ticket, _parse_items

    value = str(watcher or "").strip()
    if not value:
        raise ValueError("Watcher must not be empty.")
    snapshot = mutation.read_text_snapshot(path, allow_missing=False)
    item = _find_ticket(_parse_items(snapshot.text, key), ticket_id, key)
    existing = [str(v) for v in item.details.get("watcher", [])]
    if add:
        if value in existing:
            raise ValueError("%s is already watching %s." % (value, ticket_id))
        updated = existing + [value]
        event_type = "watch_added"
    else:
        if value not in existing:
            raise ValueError("%s is not watching %s." % (value, ticket_id))
        updated = [entry for entry in existing if entry != value]
        event_type = "watch_removed"
    return apply_ticket_activity(
        path,
        ticket_id,
        event_type,
        author,
        expected_revision,
        config=config,
        key=key,
        detail_updates={"watcher": updated if updated else None},
        at=at,
        event_extra={"watcher": value},
        transaction_id=transaction_id,
        dry_run=dry_run,
        operation="ticket.watch" if add else "ticket.unwatch",
    )


def apply_time(
    path,
    ticket_id,
    duration,
    user,
    activity,
    expected_revision,
    config=None,
    key="id",
    date=None,
    comment=None,
    source=None,
    timer_ref=None,
    corrects=None,
    at=None,
    transaction_id=None,
    dry_run=False,
):
    allowed = configured_activities(config)
    activity_value = str(activity or "development")
    if activity_value not in allowed:
        raise ValueError(
            "Unknown ticket activity %r. Use one of: %s."
            % (activity_value, ", ".join(allowed))
        )
    return apply_ticket_activity(
        path,
        ticket_id,
        "time_entry",
        user,
        expected_revision,
        config=config,
        key=key,
        comment=comment,
        at=at,
        event_extra={"activity": activity_value},
        time_entry={
            "user": user,
            "activity": activity_value,
            "date": date,
            "duration": duration,
            "comment": comment,
            "source": source,
            "timer_ref": timer_ref,
            "corrects": corrects,
        },
        transaction_id=transaction_id,
        dry_run=dry_run,
        operation="ticket.log-time",
    )


def apply_assignment(
    path,
    ticket_id,
    assignee,
    actor,
    expected_revision,
    config=None,
    key="id",
    at=None,
    comment=None,
    transaction_id=None,
    dry_run=False,
):
    value = str(assignee or "").strip()
    if not value:
        raise ValueError("Assignee must not be empty.")
    return apply_ticket_activity(
        path,
        ticket_id,
        "assignment",
        actor,
        expected_revision,
        config=config,
        key=key,
        detail_updates={"assignee": value},
        comment=comment,
        at=at,
        event_extra={"assignee": value},
        transaction_id=transaction_id,
        dry_run=dry_run,
        operation="ticket.reassign",
    )


def apply_field_change(
    path,
    ticket_id,
    updates,
    actor,
    expected_revision,
    config=None,
    key="id",
    at=None,
    comment=None,
    transaction_id=None,
    dry_run=False,
):
    if not updates:
        raise ValueError("No field changes were supplied.")
    return apply_ticket_activity(
        path,
        ticket_id,
        "field_change",
        actor,
        expected_revision,
        config=config,
        key=key,
        detail_updates=updates,
        comment=comment,
        at=at,
        transaction_id=transaction_id,
        dry_run=dry_run,
        operation="ticket.change",
    )
