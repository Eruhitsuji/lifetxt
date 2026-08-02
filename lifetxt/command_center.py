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
    items, config=None, today=None, horizon_days=3, person=None, mode="today"
):
    """Build the daily command-center aggregation.

    ``mode`` is advisory metadata for briefs (``today``/``morning``/``evening``);
    the buckets themselves are always computed so any surface can pick what to
    render. ``person`` scopes unacknowledged messages to a recipient.
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
            if item.status in OPEN_STATUSES and _message_needs_attention(item, person):
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
                overdue.append(_ref(item))
            elif due == today:
                due_today.append(_ref(item))
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

    return OrderedDict(
        (
            ("mode", mode),
            ("reference_date", today.isoformat() if today is not None else None),
            ("horizon_days", horizon_days),
            ("person", person),
            ("overdue", overdue),
            ("due_today", due_today),
            ("upcoming", upcoming),
            ("blocked", blocked),
            ("waiting", waiting),
            ("habits", habits),
            ("messages", messages),
            ("captures", captures),
            ("project_attention", project_attention),
            ("safety", safety),
            (
                "counts",
                OrderedDict(
                    (
                        ("overdue", len(overdue)),
                        ("due_today", len(due_today)),
                        ("upcoming", len(upcoming)),
                        ("blocked", len(blocked)),
                        ("waiting", len(waiting)),
                        ("habits", len(habits)),
                        ("messages", len(messages)),
                        ("captures", len(captures)),
                        ("projects_need_attention", len(project_attention)),
                    )
                ),
            ),
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
