"""Append-only ticket activity and same-file compound mutation contracts.

Ticket history stays in life.txt.  ``record:ticket_event`` and
``record:time_entry`` are normal Note records.  Operations that change a ticket
append the required side records in the same exact-revision mutation, so a
successful ticket update without its audit event is impossible on this path.
"""
from __future__ import unicode_literals

import copy
import datetime
import json
import re
from collections import OrderedDict

from . import mutation
from .model import Item
from .serializer import item_to_line
from .surface_runtime import normalize_revision

EVENT_MARKER = "ticket_event"
TIME_ENTRY_MARKER = "time_entry"
EVENT_SCHEMA = "ticket-event-v1.schema.json"
TIME_ENTRY_SCHEMA = "ticket-time-entry-v1.schema.json"
ACTIVITY_SCHEMA = "ticket-activity-v1.schema.json"

EVENT_TYPES = (
    "created", "comment", "transition", "assignment", "field_change",
    "time_entry", "relation_added", "relation_removed", "commit_linked",
    "pr_linked", "build_failed", "build_passed", "version_assigned",
    "sprint_assigned", "watch_added", "watch_removed", "closed", "reopened",
)
DEFAULT_ACTIVITIES = ("development", "review", "testing", "research", "support", "meeting")


def _first(item, key, default=None):
    values = getattr(item, "details", {}).get(key) or []
    return values[0] if values else default


def _values(item, key):
    return [str(value) for value in (getattr(item, "details", {}).get(key) or [])]


def _marker(item, value):
    return value in _values(item, "record")


def is_ticket_event(item):
    return getattr(item, "kind", None) == "N" and _marker(item, EVENT_MARKER)


def is_time_entry(item):
    return getattr(item, "kind", None) == "N" and _marker(item, TIME_ENTRY_MARKER)


def iter_ticket_events(items, ticket_id=None):
    rows = [item for item in items if is_ticket_event(item)]
    if ticket_id is not None:
        rows = [item for item in rows if str(_first(item, "parent", "")) == str(ticket_id)]
    return rows


def iter_time_entries(items, ticket_id=None):
    rows = [item for item in items if is_time_entry(item)]
    if ticket_id is not None:
        rows = [item for item in rows if str(_first(item, "parent", "")) == str(ticket_id)]
    return rows


def _utc_text(value=None):
    if value in (None, ""):
        parsed = datetime.datetime.now(datetime.timezone.utc)
    elif isinstance(value, datetime.datetime):
        parsed = value
    else:
        text = str(value).strip()
        try:
            parsed = datetime.datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            raise ValueError("Event timestamp must be an ISO date-time with an offset.")
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("Event timestamp must include a UTC offset.")
    parsed = parsed.astimezone(datetime.timezone.utc)
    return parsed.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _date_text(value=None):
    if value in (None, ""):
        return datetime.datetime.now(datetime.timezone.utc).date().isoformat()
    if isinstance(value, datetime.datetime):
        return value.date().isoformat()
    if isinstance(value, datetime.date):
        return value.isoformat()
    try:
        return datetime.date.fromisoformat(str(value).strip()).isoformat()
    except ValueError:
        raise ValueError("Time-entry date must be YYYY-MM-DD.")


def _safe_id(value):
    text = re.sub(r"[^A-Za-z0-9_.-]+", "-", str(value)).strip("-")
    return text or "ticket"


def _integer(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(default)


def _sequence(items, ticket_id):
    values = []
    for item in iter_ticket_events(items, ticket_id):
        raw = _first(item, "sequence")
        try:
            values.append(int(raw))
        except (TypeError, ValueError):
            continue
    return max(values or [0]) + 1


def _time_sequence(items, ticket_id):
    values = []
    for item in iter_time_entries(items, ticket_id):
        raw = _first(item, "sequence")
        try:
            values.append(int(raw))
        except (TypeError, ValueError):
            continue
    return max(values or [0]) + 1


def _compact_change(field, before, after):
    return json.dumps(
        OrderedDict((("field", field), ("before", list(before)), ("after", list(after)))),
        ensure_ascii=False,
        separators=(",", ":"),
    )


def _changed_fields(before_item, after_item):
    rows = []
    if before_item.status != after_item.status:
        rows.append(_compact_change("$status", [before_item.status], [after_item.status]))
    keys = sorted(set(before_item.details) | set(after_item.details))
    for key in keys:
        before = [str(v) for v in before_item.details.get(key, [])]
        after = [str(v) for v in after_item.details.get(key, [])]
        if before != after:
            rows.append(_compact_change(key, before, after))
    return rows


def event_id(ticket_id, sequence):
    return "EV-%s-%06d" % (_safe_id(ticket_id), int(sequence))


def time_entry_id(ticket_id, sequence):
    return "TIME-%s-%06d" % (_safe_id(ticket_id), int(sequence))


def _event_title(event_type, ticket_id):
    return "Ticket_%s_%s" % (_safe_id(ticket_id), str(event_type))


def build_ticket_event(
    ticket_id,
    event_type,
    author,
    at,
    sequence,
    transaction_id,
    ticket_revision,
    changes=None,
    body=None,
    project=None,
    tracker=None,
    from_status=None,
    to_status=None,
    provider=None,
    references=None,
    extra=None,
):
    if event_type not in EVENT_TYPES:
        raise ValueError("Unsupported ticket event %r." % event_type)
    details = OrderedDict()
    details["record"] = [EVENT_MARKER]
    details["id"] = [event_id(ticket_id, sequence)]
    details["parent"] = [str(ticket_id)]
    details["event"] = [str(event_type)]
    details["author"] = [str(author or "local")]
    details["at"] = [_utc_text(at)]
    details["sequence"] = [str(int(sequence))]
    details["transaction"] = [str(transaction_id)]
    details["ticket_revision"] = [str(ticket_revision)]
    if project:
        details["project"] = [str(project)]
    if tracker:
        details["tracker"] = [str(tracker)]
    if from_status:
        details["from_status"] = [str(from_status)]
    if to_status:
        details["to_status"] = [str(to_status)]
    if changes:
        details["change"] = [str(value) for value in changes]
    if body not in (None, ""):
        details["body"] = [str(body)]
    if provider:
        details["provider"] = [str(provider)]
    if references:
        details["ref"] = [str(value) for value in references]
    for key, value in (extra or {}).items():
        if value in (None, ""):
            continue
        details[str(key)] = [str(v) for v in value] if isinstance(value, (list, tuple)) else [str(value)]
    return Item("[N]", "N", _event_title(event_type, ticket_id), details)


def build_time_entry(
    ticket_id,
    project,
    user,
    activity,
    date,
    duration,
    sequence,
    event_id_value,
    created_at,
    comment=None,
    source=None,
    timer_ref=None,
    corrects=None,
):
    normalized_duration, _seconds = normalize_duration(duration)
    details = OrderedDict()
    details["record"] = [TIME_ENTRY_MARKER]
    details["id"] = [time_entry_id(ticket_id, sequence)]
    details["parent"] = [str(ticket_id)]
    details["user"] = [str(user or "local")]
    details["activity"] = [str(activity or "development")]
    details["on"] = [_date_text(date)]
    details["elapsed"] = [normalized_duration]
    details["sequence"] = [str(int(sequence))]
    details["event_id"] = [str(event_id_value)]
    details["created_at"] = [_utc_text(created_at)]
    if project:
        details["project"] = [str(project)]
    if comment not in (None, ""):
        details["body"] = [str(comment)]
    if source:
        details["source"] = [str(source)]
    if timer_ref:
        details["timer_ref"] = [str(timer_ref)]
    if corrects:
        details["corrects"] = [str(corrects)]
    return Item("[N]", "N", "Ticket_time_%s" % _safe_id(ticket_id), details)


def normalize_duration(value):
    from .agenda import parse_duration

    try:
        parsed = parse_duration(str(value))
    except (TypeError, ValueError):
        raise ValueError("Duration must be a lifetxt duration such as 30m, 2h, or 1d.")
    seconds = int(parsed.total_seconds())
    if seconds <= 0:
        raise ValueError("Duration must be greater than zero.")
    return str(value).strip(), seconds


def _diag(code, message, item=None, hint=None):
    return OrderedDict(
        (
            ("severity", "error"),
            ("code", code),
            ("message", message),
            ("hint", hint or "Repair the append-only ticket history record."),
            ("source", getattr(item, "source", None) if item is not None else None),
            ("line", getattr(item, "line", None) if item is not None else None),
        )
    )


def validate_ticket_event(item, ticket_ids=None):
    rows = []
    for key in ("id", "parent", "event", "author", "at", "sequence", "transaction", "ticket_revision"):
        if not _values(item, key):
            rows.append(_diag("TK020", "Ticket event is missing %s." % key, item))
    event_type = _first(item, "event")
    if event_type and event_type not in EVENT_TYPES:
        rows.append(_diag("TK021", "Unknown ticket event %r." % event_type, item))
    try:
        _utc_text(_first(item, "at"))
    except ValueError as exc:
        rows.append(_diag("TK022", str(exc), item))
    try:
        if int(_first(item, "sequence", 0)) <= 0:
            raise ValueError()
    except (TypeError, ValueError):
        rows.append(_diag("TK023", "Ticket event sequence must be a positive integer.", item))
    parent = str(_first(item, "parent", ""))
    if ticket_ids is not None and parent not in ticket_ids:
        rows.append(_diag("TK024", "Ticket event parent %r does not resolve to a ticket." % parent, item))
    return rows


def validate_time_entry(item, ticket_ids=None, activities=None):
    rows = []
    for key in ("id", "parent", "user", "activity", "on", "elapsed", "sequence", "event_id", "created_at"):
        if not _values(item, key):
            rows.append(_diag("TK025", "Time entry is missing %s." % key, item))
    try:
        _date_text(_first(item, "on"))
    except ValueError as exc:
        rows.append(_diag("TK026", str(exc), item))
    try:
        normalize_duration(_first(item, "elapsed"))
    except ValueError as exc:
        rows.append(_diag("TK027", str(exc), item))
    activity = str(_first(item, "activity", ""))
    if activities and activity not in activities:
        rows.append(_diag("TK028", "Time-entry activity %r is not configured." % activity, item))
    parent = str(_first(item, "parent", ""))
    if ticket_ids is not None and parent not in ticket_ids:
        rows.append(_diag("TK029", "Time-entry parent %r does not resolve to a ticket." % parent, item))
    return rows


def configured_activities(config=None):
    section = (config or {}).get("ticketing") if isinstance(config or {}, dict) else {}
    section = section if isinstance(section, dict) else {}
    raw = section.get("activities")
    if isinstance(raw, dict):
        values = list(raw.keys())
    elif isinstance(raw, (list, tuple)):
        values = list(raw)
    else:
        values = list(DEFAULT_ACTIVITIES)
    result = []
    for value in values:
        text = str(value).strip()
        if text and text not in result:
            result.append(text)
    return tuple(result or DEFAULT_ACTIVITIES)


def validate_ticket_history(items, config=None, key="id"):
    from .tickets import is_ticket, ticket_id_of

    ticket_ids = set()
    for item in items:
        if is_ticket(item):
            value = ticket_id_of(item, key)
            if value:
                ticket_ids.add(str(value))
    rows = []
    event_ids = {}
    sequences = {}
    transactions = {}
    for item in iter_ticket_events(items):
        rows.extend(validate_ticket_event(item, ticket_ids))
        identifier = str(_first(item, "id", ""))
        if identifier:
            if identifier in event_ids:
                rows.append(_diag("TK030", "Duplicate ticket event id %r." % identifier, item))
            event_ids[identifier] = item
        parent = str(_first(item, "parent", ""))
        sequence = str(_first(item, "sequence", ""))
        pair = (parent, sequence)
        if parent and sequence:
            if pair in sequences:
                rows.append(_diag("TK031", "Duplicate event sequence %s for ticket %s." % (sequence, parent), item))
            sequences[pair] = item
        txid = str(_first(item, "transaction", ""))
        if txid:
            if txid in transactions:
                rows.append(_diag("TK032", "Duplicate ticket transaction %r." % txid, item))
            transactions[txid] = item
    time_ids = {}
    for item in iter_time_entries(items):
        rows.extend(validate_time_entry(item, ticket_ids, configured_activities(config)))
        identifier = str(_first(item, "id", ""))
        if identifier:
            if identifier in time_ids:
                rows.append(_diag("TK033", "Duplicate time-entry id %r." % identifier, item))
            time_ids[identifier] = item
        event_ref = str(_first(item, "event_id", ""))
        if event_ref and event_ref not in event_ids:
            rows.append(_diag("TK034", "Time entry references missing event %r." % event_ref, item))
        parent = str(_first(item, "parent", ""))
        sequence = _integer(_first(item, "sequence", 0))
        identifier = str(_first(item, "id", ""))
        if parent and sequence > 0 and identifier and identifier != time_entry_id(parent, sequence):
            rows.append(
                _diag(
                    "TK036",
                    "Time-entry id %r does not match parent/sequence; expected %r."
                    % (identifier, time_entry_id(parent, sequence)),
                    item,
                )
            )
    for item in iter_ticket_events(items):
        parent = str(_first(item, "parent", ""))
        sequence = _integer(_first(item, "sequence", 0))
        identifier = str(_first(item, "id", ""))
        if parent and sequence > 0 and identifier and identifier != event_id(parent, sequence):
            rows.append(
                _diag(
                    "TK035",
                    "Ticket-event id %r does not match parent/sequence; expected %r."
                    % (identifier, event_id(parent, sequence)),
                    item,
                )
            )
    by_time_id = {
        str(_first(item, "id", "")): item
        for item in iter_time_entries(items)
        if str(_first(item, "id", ""))
    }
    corrections = {}
    for item in iter_time_entries(items):
        identifier = str(_first(item, "id", ""))
        target = str(_first(item, "corrects", ""))
        if not target:
            continue
        target_item = by_time_id.get(target)
        if target_item is None:
            rows.append(_diag("TK037", "Time entry %r corrects missing entry %r." % (identifier, target), item))
            continue
        if str(_first(target_item, "parent", "")) != str(_first(item, "parent", "")):
            rows.append(_diag("TK037", "Time entry %r corrects an entry from another ticket." % identifier, item))
        if target == identifier:
            rows.append(_diag("TK038", "Time entry %r cannot correct itself." % identifier, item))
        corrections[identifier] = target
    for identifier in corrections:
        seen = set()
        current = identifier
        while current in corrections:
            if current in seen:
                rows.append(_diag("TK038", "Time-entry correction cycle includes %r." % identifier, by_time_id.get(identifier)))
                break
            seen.add(current)
            current = corrections[current]
    by_parent = {}
    for item in iter_ticket_events(items):
        parent = str(_first(item, "parent", ""))
        sequence = _integer(_first(item, "sequence", 0))
        if parent and sequence > 0:
            by_parent.setdefault(parent, []).append(sequence)
    for parent, values in by_parent.items():
        ordered = sorted(set(values))
        expected_values = list(range(1, max(ordered) + 1)) if ordered else []
        if ordered != expected_values:
            rows.append(
                _diag(
                    "TK039",
                    "Ticket %s event sequence has gaps: found %s."
                    % (parent, ",".join(str(value) for value in ordered)),
                    None,
                    "Append events through ticket workflow commands; do not renumber history.",
                )
            )
    return rows


def _decode_changes(values):
    rows = []
    for value in values:
        try:
            parsed = json.loads(value)
        except (TypeError, ValueError):
            parsed = {"raw": value}
        rows.append(parsed)
    return rows


def event_view(item):
    return OrderedDict(
        (
            ("id", _first(item, "id")),
            ("ticket_id", _first(item, "parent")),
            ("event", _first(item, "event")),
            ("author", _first(item, "author")),
            ("at", _first(item, "at")),
            ("sequence", _integer(_first(item, "sequence", 0))),
            ("transaction_id", _first(item, "transaction")),
            ("ticket_revision", _first(item, "ticket_revision")),
            ("from_status", _first(item, "from_status")),
            ("to_status", _first(item, "to_status")),
            ("changes", _decode_changes(_values(item, "change"))),
            ("body", _first(item, "body")),
            ("project", _first(item, "project")),
            ("tracker", _first(item, "tracker")),
            ("provider", _first(item, "provider")),
            ("references", _values(item, "ref")),
            ("source", getattr(item, "source", None)),
            ("line", getattr(item, "line", None)),
        )
    )


def time_entry_view(item):
    try:
        _normalized, seconds = normalize_duration(_first(item, "elapsed"))
    except ValueError:
        seconds = None
    return OrderedDict(
        (
            ("id", _first(item, "id")),
            ("ticket_id", _first(item, "parent")),
            ("project", _first(item, "project")),
            ("user", _first(item, "user")),
            ("activity", _first(item, "activity")),
            ("date", _first(item, "on")),
            ("duration", _first(item, "elapsed")),
            ("seconds", seconds),
            ("comment", _first(item, "body")),
            ("source", _first(item, "source")),
            ("timer_ref", _first(item, "timer_ref")),
            ("corrects", _first(item, "corrects")),
            ("event_id", _first(item, "event_id")),
            ("created_at", _first(item, "created_at")),
            ("sequence", _integer(_first(item, "sequence", 0))),
            ("line", getattr(item, "line", None)),
        )
    )


def _format_seconds(seconds):
    seconds = int(seconds or 0)
    hours, remainder = divmod(seconds, 3600)
    minutes, remainder = divmod(remainder, 60)
    parts = []
    if hours:
        parts.append("%dh" % hours)
    if minutes:
        parts.append("%dm" % minutes)
    if remainder or not parts:
        parts.append("%ds" % remainder)
    return "".join(parts)


def ticket_activity_report(items, ticket_id, config=None, key="id", event_types=None, limit=None):
    from .tickets import is_ticket, ticket_id_of, ticket_view

    ticket = None
    for item in items:
        if is_ticket(item) and str(ticket_id_of(item, key)) == str(ticket_id):
            ticket = item
            break
    if ticket is None:
        raise ValueError("Ticket %r not found." % ticket_id)
    events = [event_view(item) for item in iter_ticket_events(items, ticket_id)]
    if event_types:
        allowed = set(str(value) for value in event_types)
        events = [row for row in events if row["event"] in allowed]
    events.sort(key=lambda row: (row["at"] or "", row["sequence"], row["id"] or ""))
    if limit is not None:
        events = events[-max(0, int(limit)) :]
    entries = [time_entry_view(item) for item in iter_time_entries(items, ticket_id)]
    entries.sort(key=lambda row: (row["date"] or "", row["created_at"] or "", row["sequence"], row["id"] or ""))
    superseded_ids = {
        str(row.get("corrects"))
        for row in entries
        if row.get("corrects")
    }
    effective_entries = [
        row for row in entries
        if str(row.get("id")) not in superseded_ids
    ]
    seconds = sum(row["seconds"] or 0 for row in effective_entries)
    corrected = sum(row["seconds"] or 0 for row in entries if row.get("corrects"))
    diagnostics = [
        row for row in validate_ticket_history(items, config=config, key=key)
        if str(ticket_id) in row.get("message", "") or row.get("line") in {
            getattr(item, "line", None)
            for item in iter_ticket_events(items, ticket_id) + iter_time_entries(items, ticket_id)
        }
    ]
    return OrderedDict(
        (
            ("schema", ACTIVITY_SCHEMA),
            ("contract_version", "1"),
            ("ticket", ticket_view(ticket, config or {}, items, key=key)),
            ("events", events),
            ("time_entries", entries),
            (
                "time",
                OrderedDict(
                    (
                        ("entry_count", len(entries)),
                        ("authoritative_seconds", seconds),
                        ("authoritative_duration", _format_seconds(seconds)),
                        ("correction_seconds", corrected),
                        ("effective_entry_ids", [row.get("id") for row in effective_entries]),
                        ("superseded_entry_ids", sorted(superseded_ids)),
                        ("legacy_elapsed", _first(ticket, "elapsed")),
                        (
                            "policy",
                            "append-only time entries are authoritative; correction entries supersede their referenced entries, while legacy elapsed is reported separately and never double-counted",
                        ),
                    )
                ),
            ),
            ("diagnostics", diagnostics),
        )
    )


