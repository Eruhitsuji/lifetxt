"""One daily command-center aggregation shared by every surface.

``today``, the morning/evening briefs, the TUI dashboard, the Web dashboard, and
MCP all read from :func:`command_center` so they agree on what "today" means.
The aggregation is computed from parsed items plus the configuration; it never
writes and never duplicates source records — every bucket holds lightweight
references back to the underlying items.

Deterministic by construction: given the same items, config, and reference
date, the output is identical. Callers pass ``today`` explicitly so tests and
fixtures stay stable across time zones.
"""

from __future__ import unicode_literals

from collections import OrderedDict

from .inbox import inbox_summary
from .nextaction import next_action_items
from .projects import collect_projects, compute_health
from .timeutil import parse_date_or_datetime


OPEN_STATUSES = ("[ ]", "[/]", "[?]")
DONE_STATUS = "[x]"
CANCELLED_STATUS = "[-]"
DEFERRED_STATUS = "[>]"
WAITING_STATUS = "[?]"
WORK_KINDS = ("T", "D")


def _first(item, key, default=None):
    values = item.details.get(key)
    return values[0] if values else default


def _date_of(value):
    if not value:
        return None
    try:
        parsed = parse_date_or_datetime(value)
    except Exception:
        return None
    if parsed is None:
        return None
    return getattr(parsed, "date", lambda: parsed)()


def _ref(item):
    return OrderedDict(
        (
            ("title", item.title),
            ("kind", item.kind),
            ("status", item.status),
            ("due", _first(item, "due")),
            ("project", _first(item, "project")),
            ("assignee", _first(item, "assignee") or _first(item, "owner")),
            ("source", item.source),
            ("line", item.line),
        )
    )


def _status_by_id(items):
    result = {}
    for item in items:
        for value in item.details.get("id", []):
            result[str(value)] = item
    return result


def _message_suppressed(item, today):
    """Ack or an active snooze suppresses a message from daily attention.

    Mirrors :mod:`lifetxt.notifier`'s ack/snooze due-notification
    suppression rule, at the same reference-*date* granularity this module
    already uses for every other bucket (``command_center`` takes a
    reference date, not a reference instant, so this checks whether
    ``snooze_until`` falls on a later date than ``today`` rather than
    comparing exact timestamps).
    """
    if item.details.get("ack"):
        return True
    snooze_until = _date_of(_first(item, "snooze_until"))
    if snooze_until is not None and today is not None and snooze_until > today:
        return True
    return False


def scoped_items(items, config, saved_view=None, area=None):
    """Narrow the input item set to a personalization scope before aggregation.

    At most one of ``saved_view``/``area`` may be given. Both reuse an
    existing selection mechanism unmodified --
    :func:`lifetxt.saved_views.run_saved_view` / :func:`lifetxt.areas.area_row_keys`
    -- rather than inventing a Today-only configuration language. Raises
    ``ValueError`` (matching the convention those modules already use for an
    unknown name) when both are given or when resolution fails, so a caller
    can report the exact same message a direct ``saved view`` or ``area``
    lookup would.
    """
    if saved_view and area:
        raise ValueError(
            "today: --saved-view and --area cannot be combined; choose one scope."
        )
    if saved_view:
        from .saved_views import run_saved_view

        filtered, diagnostics = run_saved_view(items, config, saved_view)
        errors = [d for d in diagnostics if d.get("severity") == "error"]
        if errors:
            raise ValueError(errors[0]["message"])
        return filtered
    if area:
        from .areas import area_row_keys, area_show

        keys = area_row_keys(items, config, area)
        if not keys:
            area_show(items, config, area)  # raises ValueError on an unknown name
        return [it for it in items if (getattr(it, "source", None), it.line) in keys]
    return items


def _status_now(items, person=None):
    """Active Status/Presence records: current context for the NOW section.

    Reuses :func:`lifetxt.presence.active_status_items` unmodified -- the
    same open-``S``-record definition ``lifetxt status``/``lifetxt start``
    already use -- so "what is the person doing right now" is derived once.
    """
    from .presence import active_status_items

    rows = []
    for item in active_status_items(items, person=person):
        rows.append(
            OrderedDict(
                (
                    ("person", _first(item, "person") or "self"),
                    ("state", _first(item, "state") or item.title),
                    ("title", item.title),
                    ("since", _first(item, "from")),
                    ("source", item.source),
                    ("line", item.line),
                )
            )
        )
    return rows


def _today_events(items, today):
    """Events and Reminders whose occurrence falls on ``today``.

    Reuses :func:`lifetxt.agenda.agenda_records` unmodified, bounded to a
    single day's range -- the identical occurrence/recurrence/timezone
    resolution ``agenda`` and the Web Calendar already use -- then narrows
    the result to Event/Reminder kinds. Deadlines and Tasks due today
    already appear in ``due_today``, so they are not duplicated here.
    """
    if today is None:
        return []
    import datetime

    from .agenda import agenda_records, format_match_time

    range_start = datetime.datetime.combine(today, datetime.time.min)
    range_end = datetime.datetime.combine(today, datetime.time.max)
    rows = []
    for record in agenda_records(items, range_start, range_end):
        if record.get("type") not in ("E", "R"):
            continue
        # Prefer an at: time-of-day match for display over an all-day on:
        # span when both are present on the same record -- agenda_records()
        # already computed both; this only picks which existing match to
        # show, it does not derive a new occurrence.
        when = record.get("when")
        for match in record.get("matches") or []:
            if match.get("key") == "at":
                when = format_match_time(match)
                break
        rows.append(
            OrderedDict(
                (
                    ("when", when),
                    ("title", record.get("title")),
                    ("kind", record.get("type")),
                    ("status", record.get("status")),
                    ("blocked", record.get("blocked", False)),
                    ("source", record.get("source")),
                    ("line", record.get("line")),
                )
            )
        )
    return rows


def _attention_reason(item, today):
    """A short, deterministic explanation for why an item needs attention.

    Reuses :func:`lifetxt.temporal_context.node_facts` unmodified -- the
    same ``overdue_by``/``due_in`` signals :func:`lifetxt.temporal_context.temporal_context`
    and the ``explain_item`` MCP prompt already derive -- so "why is this
    urgent" has one deterministic answer, not a second one reimplemented
    here. Deliberately text, not a generated summary: this is the
    deterministic groundwork assistive Today features can build on later,
    not an assistive feature itself.
    """
    if today is None:
        return None
    from .temporal_context import node_facts

    for fact in node_facts(item, today):
        if fact["rule"] == "overdue_by":
            days = fact["days"]
            return "%d day%s overdue" % (days, "" if days == 1 else "s")
        if fact["rule"] == "due_in" and fact["days"] == 0:
            return "due today"
    return None


def _is_blocked(item, status_by_id):
    for target in item.details.get("depends_on") or []:
        blocker = status_by_id.get(str(target))
        if blocker is not None and blocker.status not in (
            DONE_STATUS,
            CANCELLED_STATUS,
        ):
            return True
    return False


def command_center(
    items,
    config=None,
    today=None,
    horizon_days=3,
    person=None,
    mode="today",
    next_actions_limit=None,
    inbox_limit=5,
    ticket_stale_after_days=None,
):
    """Build the daily command-center aggregation.

    ``mode`` is advisory metadata for briefs (``today``/``morning``/``evening``);
    the buckets themselves are always computed so any surface can pick what to
    render. ``person`` scopes unacknowledged messages to a recipient.

    ``next_actions`` reuses :func:`lifetxt.nextaction.next_action_items` --
    the same actionable-item definition ``next``, the TUI ``/next`` view, and
    the MCP ``get_next_actions`` tool already share -- so this aggregation
    never carries a second definition of "actionable". ``inbox`` reuses
    :func:`lifetxt.inbox.inbox_summary` for the pending/deferred proposal
    counts, then bounds the pending list to ``inbox_limit`` entries with only
    the minimal fields a daily overview needs; the operational proposal store
    itself is never duplicated here. ``ticket_attention`` reuses
    :func:`lifetxt.ticket_project_values.is_ticket`/``ticket_row`` and
    :func:`lifetxt.temporal_context.node_facts` for open ticket-kind items in
    ``review`` status, at or above a high severity, or stale beyond
    ``ticket_stale_after_days`` (default matches
    :data:`lifetxt.ticket_project_values.DEFAULT_STALE_DAYS`); no severity,
    workflow, or staleness rule is duplicated here. ``now`` reuses
    :func:`lifetxt.presence.active_status_items` for current Status/Presence
    context, and ``today_events`` reuses :func:`lifetxt.agenda.agenda_records`
    bounded to ``today`` for Event/Reminder occurrences. Every ``overdue``/
    ``due_today`` entry that has a determinable due date also carries a
    deterministic ``reason`` (from :func:`lifetxt.temporal_context.node_facts`)
    explaining why it needs attention.
    """
    config = config or {}
    status_by_id = _status_by_id(items)

    overdue = []
    due_today = []
    upcoming = []
    blocked = []
    waiting = []
    habits = []
    messages = []
    captures = []

    for item in items:
        if item.kind == "M":
            if (
                item.status in OPEN_STATUSES
                and _message_needs_attention(item, person)
                and not _message_suppressed(item, today)
            ):
                messages.append(_ref(item))
            continue
        if item.kind == "H" and item.status in OPEN_STATUSES:
            habits.append(_ref(item))
            continue
        if item.kind not in WORK_KINDS:
            continue
        status = item.status
        if status in (DONE_STATUS, CANCELLED_STATUS):
            continue
        if status == WAITING_STATUS:
            waiting.append(_ref(item))
        if _is_blocked(item, status_by_id):
            blocked.append(_ref(item))
        due = _date_of(_first(item, "due"))
        if due is not None and today is not None:
            if due < today:
                ref = _ref(item)
                reason = _attention_reason(item, today)
                if reason:
                    ref["reason"] = reason
                overdue.append(ref)
            elif due == today:
                ref = _ref(item)
                reason = _attention_reason(item, today)
                if reason:
                    ref["reason"] = reason
                due_today.append(ref)
            elif due <= _add_days(today, horizon_days):
                upcoming.append(_ref(item))
        if (
            status in OPEN_STATUSES
            and not item.details.get("project")
            and not item.details.get("due")
            and not item.details.get("assignee")
        ):
            captures.append(_ref(item))

    project_attention = _project_attention(items, config, today)
    safety = _safety_summary(config)
    next_actions = _next_actions(items, next_actions_limit)
    inbox = _inbox_section(config, inbox_limit)
    ticket_attention = _ticket_attention(items, today, ticket_stale_after_days)
    now = _status_now(items, person)
    today_events = _today_events(items, today)

    return OrderedDict(
        (
            ("mode", mode),
            ("reference_date", today.isoformat() if today is not None else None),
            ("horizon_days", horizon_days),
            ("person", person),
            ("now", now),
            ("today_events", today_events),
            ("overdue", overdue),
            ("due_today", due_today),
            ("upcoming", upcoming),
            ("blocked", blocked),
            ("waiting", waiting),
            ("next_actions", next_actions),
            ("habits", habits),
            ("messages", messages),
            ("captures", captures),
            ("inbox", inbox),
            ("project_attention", project_attention),
            ("ticket_attention", ticket_attention),
            ("safety", safety),
            (
                "counts",
                OrderedDict(
                    (
                        ("now", len(now)),
                        ("today_events", len(today_events)),
                        ("overdue", len(overdue)),
                        ("due_today", len(due_today)),
                        ("upcoming", len(upcoming)),
                        ("blocked", len(blocked)),
                        ("waiting", len(waiting)),
                        ("next_actions", len(next_actions)),
                        ("habits", len(habits)),
                        ("messages", len(messages)),
                        ("captures", len(captures)),
                        ("inbox_pending", inbox["pending_count"]),
                        ("projects_need_attention", len(project_attention)),
                        ("ticket_attention", len(ticket_attention)),
                    )
                ),
            ),
        )
    )


def _next_actions(items, limit):
    """The shared actionable-next-step list, mapped through the same ``_ref``.

    Delegates entirely to :func:`lifetxt.nextaction.next_action_items` for
    both the actionable predicate and the priority/due/age ordering; this
    function only adapts the result to the command-center reference shape.
    """
    actionable = next_action_items(items, limit=limit)
    return [_ref(item) for item in actionable]


def _inbox_section(config, limit):
    """Bounded Unified Inbox summary, built from :func:`inbox_summary`.

    Counting and status filtering stay in ``lifetxt.inbox``; this only trims
    the pending list to ``limit`` entries and narrows each proposal down to
    the minimal fields a daily overview needs (never the full operational
    record, which may carry the entire proposed change).
    """
    summary = inbox_summary(config)
    counts = summary.get("counts") or {}
    pending = summary.get("pending") or []
    limit = max(0, int(limit or 0))
    return OrderedDict(
        (
            ("total", summary.get("total", 0)),
            ("pending_count", counts.get("pending", 0)),
            ("deferred_count", counts.get("deferred", 0)),
            ("counts", OrderedDict(counts)),
            ("pending", [_proposal_ref(p) for p in pending[:limit]]),
        )
    )


def _proposal_ref(proposal):
    changes = proposal.get("changes") or []
    change = changes[0] if changes and isinstance(changes[0], dict) else {}
    return OrderedDict(
        (
            ("id", proposal.get("id")),
            ("source", proposal.get("source")),
            ("created", proposal.get("created")),
            ("summary", str(change.get("title") or "")),
        )
    )


def _message_needs_attention(item, person):
    if person is None:
        return True
    recipients = [str(v) for v in item.details.get("recipient", [])]
    if not recipients:
        return True
    return person in recipients


def _add_days(date, days):
    import datetime

    return date + datetime.timedelta(days=int(days or 0))


def _project_attention(items, config, today):
    rows = []
    for proj in collect_projects(items, config, today).values():
        if proj["archived"]:
            continue
        health = compute_health(proj, today)
        if health["label"] == "green":
            continue
        rows.append(
            OrderedDict(
                (
                    ("name", proj["name"]),
                    ("display_name", proj["display_name"]),
                    ("health", health["label"]),
                    ("reasons", health["reasons"]),
                    ("overdue_count", health["overdue_count"]),
                    ("blocked_count", health["blocked_count"]),
                    ("top_risk_severity", health["top_risk_severity"]),
                )
            )
        )
    rows.sort(key=lambda r: (0 if r["health"] == "red" else 1, r["name"]))
    return rows


def _ticket_attention(items, today, stale_after_days):
    """Bounded ticket attention: review status, high severity, or stale.

    Every classification reuses :mod:`lifetxt.ticket_project_values` /
    :func:`lifetxt.temporal_context.node_facts` unmodified -- no severity,
    workflow, or staleness rule is duplicated here. Bounded by
    construction: only ticket-kind items already in ``items`` are
    considered (each a cheap O(1) node-level check), never a workspace or
    dependency-graph scan; the richer cross-project dependency-universe
    reasoning stays in ``ticket project`` reports, not duplicated here.
    """
    from .temporal_context import DEFAULT_STALE_DAYS, node_facts
    from .ticket_project_values import (
        DEFAULT_HIGH_SEVERITIES,
        DEFAULT_TERMINAL_STATUSES,
        is_ticket,
        ticket_row,
    )

    if stale_after_days is None:
        stale_after_days = DEFAULT_STALE_DAYS
    terminal = set(DEFAULT_TERMINAL_STATUSES)
    severe = set(str(value).lower() for value in DEFAULT_HIGH_SEVERITIES)

    rows = []
    for item in items:
        if not is_ticket(item):
            continue
        row = ticket_row(item)
        if row["status"] in terminal:
            continue
        reasons = []
        if row["status"] == "review":
            reasons.append("review")
        if str(row["severity"]).lower() in severe:
            reasons.append("high_severity")
        if today is not None:
            facts = node_facts(item, today, stale_after_days=stale_after_days)
            if any(fact["rule"] == "stale_since" for fact in facts):
                reasons.append("stale")
        if not reasons:
            continue
        ref = _ref(item)
        ref["reasons"] = reasons
        rows.append(ref)
    rows.sort(key=lambda r: (0 if "high_severity" in r["reasons"] else 1, r["title"]))
    return rows


def _safety_summary(config):
    """Lightweight, non-fatal safety signal for the dashboard header."""
    try:
        from .config_validation import validate_config

        rows = validate_config(config, use_jsonschema=False)
    except Exception:
        rows = []
    errors = [r for r in rows if r.get("severity") == "error"]
    warnings = [r for r in rows if r.get("severity") == "warning"]
    return OrderedDict(
        (
            ("config_errors", len(errors)),
            ("config_warnings", len(warnings)),
            ("ok", not errors),
        )
    )
