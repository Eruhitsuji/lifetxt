"""Shared native semantic-event contract and legacy record adapters.

The stored ``record:item_event`` shape is deliberately closed.  Existing
progress, ticket, and time-entry records are not rewritten; adapters expose a
common read model while retaining their original record identity.
"""

from __future__ import unicode_literals

import datetime
import re
from collections import OrderedDict

from .model import Diagnostic, Item
from .timeutil import parse_iso_datetime
from .timezone_policy import utcnow


ITEM_EVENT_MARKER = "item_event"
ITEM_EVENT_SCHEMA = "item-event-v1.schema.json"
ITEM_EVENT_TYPES = (
    "created",
    "status_changed",
    "completed",
    "reopened",
    "canceled",
    "relation_added",
    "relation_removed",
    "schedule_changed",
)
RELATION_FIELDS = ("follows", "realizes", "replaced_by")
SCHEDULE_FIELDS = ("on", "due", "from", "to", "at")

_REVISION_RE = re.compile(r"^[0-9a-f]{64}$")
_SAFE_ID_RE = re.compile(r"[^A-Za-z0-9_.-]+")
_COMMON_FIELDS = (
    "record",
    "id",
    "parent",
    "event",
    "at",
    "sequence",
    "transaction",
    "source_revision",
)
_OPTIONAL_COMMON_FIELDS = ("actor", "source")
_EVENT_FIELDS = {
    "created": ("item_kind", "item_title", "after_status"),
    "status_changed": ("before_status", "after_status"),
    "completed": ("before_status", "after_status"),
    "reopened": ("before_status", "after_status"),
    "canceled": ("before_status", "after_status"),
    "relation_added": ("relation", "target"),
    "relation_removed": ("relation", "target"),
    "schedule_changed": ("field",),
}
_OPTIONAL_EVENT_FIELDS = {"completed": ("completed_at",)}
_MISSING_FIELDS = ("before_missing", "after_missing")
_VALUE_FIELDS = ("before", "after")


def _values(item, key):
    return [str(value) for value in (getattr(item, "details", {}).get(key) or [])]


def _first(item, key, default=None):
    values = _values(item, key)
    return values[0] if values else default


def _safe_id(value):
    text = _SAFE_ID_RE.sub("-", str(value)).strip("-")
    return text or "item"


def _utc_text(value=None):
    if value in (None, ""):
        parsed = utcnow()
    elif isinstance(value, datetime.datetime):
        parsed = value
    else:
        parsed = parse_iso_datetime(str(value).strip())
        if parsed is None:
            raise ValueError("Item event timestamp must be an ISO date-time with an offset.")
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("Item event timestamp must include a UTC offset.")
    return (
        parsed.astimezone(datetime.timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def item_event_id(parent_id, sequence):
    return "IE-%s-%06d" % (_safe_id(parent_id), int(sequence))


def is_item_event(item):
    return (
        getattr(item, "kind", None) == "N"
        and ITEM_EVENT_MARKER in _values(item, "record")
    )


def iter_item_events(items, parent_id=None):
    rows = [item for item in items if is_item_event(item)]
    if parent_id is not None:
        rows = [
            item for item in rows if str(_first(item, "parent", "")) == str(parent_id)
        ]
    return rows


def build_item_event(
    parent_id,
    event_type,
    at,
    sequence,
    transaction_id,
    source_revision,
    actor=None,
    source=None,
    **payload
):
    """Build one closed-vocabulary ``record:item_event`` Note."""
    if event_type not in ITEM_EVENT_TYPES:
        raise ValueError("Unsupported item event %r." % event_type)
    if not _REVISION_RE.match(str(source_revision or "")):
        raise ValueError("Item event source revision must be a SHA-256 hash.")
    sequence = int(sequence)
    if sequence <= 0:
        raise ValueError("Item event sequence must be a positive integer.")

    required = set(_EVENT_FIELDS[event_type])
    allowed = required | set(_OPTIONAL_EVENT_FIELDS.get(event_type, ()))
    if event_type == "schedule_changed":
        allowed |= set(_MISSING_FIELDS + _VALUE_FIELDS)
    unknown = sorted(set(payload) - allowed)
    missing = sorted(key for key in required if payload.get(key) in (None, ""))
    if unknown:
        raise ValueError("Unsupported %s payload field(s): %s." % (event_type, ", ".join(unknown)))
    if missing:
        raise ValueError("Missing %s payload field(s): %s." % (event_type, ", ".join(missing)))
    if event_type in ("relation_added", "relation_removed") and payload["relation"] not in RELATION_FIELDS:
        raise ValueError("Unsupported relation field %r." % payload["relation"])
    if event_type == "schedule_changed":
        if payload["field"] not in SCHEDULE_FIELDS:
            raise ValueError("Unsupported schedule field %r." % payload["field"])
        for side in ("before", "after"):
            missing_key = side + "_missing"
            has_value = payload.get(side) not in (None, "")
            is_missing = payload.get(missing_key) is True
            if has_value == is_missing:
                raise ValueError(
                    "schedule_changed requires exactly one of %s or %s:true."
                    % (side, missing_key)
                )

    details = OrderedDict()
    details["record"] = [ITEM_EVENT_MARKER]
    details["id"] = [item_event_id(parent_id, sequence)]
    details["parent"] = [str(parent_id)]
    details["event"] = [str(event_type)]
    details["at"] = [_utc_text(at)]
    details["sequence"] = [str(sequence)]
    details["transaction"] = [str(transaction_id)]
    details["source_revision"] = [str(source_revision)]
    if actor not in (None, ""):
        details["actor"] = [str(actor)]
    if source not in (None, ""):
        details["source"] = [str(source)]
    for key in _EVENT_FIELDS[event_type] + _OPTIONAL_EVENT_FIELDS.get(event_type, ()):
        if payload.get(key) not in (None, ""):
            details[key] = [str(payload[key])]
    if event_type == "schedule_changed":
        for side in ("before", "after"):
            if payload.get(side) not in (None, ""):
                details[side] = [str(payload[side])]
            else:
                details[side + "_missing"] = ["true"]
    title = "Item_%s_%06d" % (_safe_id(parent_id), sequence)
    return Item("[N]", "N", title, details)


def _diagnostic(code, message, item=None):
    return Diagnostic(
        "warning",
        code,
        message,
        line=getattr(item, "line", None),
        source=getattr(item, "source", None),
        hint="Use a supported typed mutation; do not edit item events in place.",
    )


def _parent_index(items, id_key):
    index = {}
    for item in items:
        if is_item_event(item):
            continue
        for value in _values(item, id_key):
            index.setdefault(value, []).append(item)
    return index


def item_event_diagnostics(item):
    """Validate one event without requiring its parent stream."""
    rows = []
    required = list(_COMMON_FIELDS)
    missing = [key for key in required if not _values(item, key)]
    repeated = [key for key in required if len(_values(item, key)) != 1]
    if missing:
        rows.append(_diagnostic("W261", "Item event is missing required field(s): %s." % ", ".join(missing), item))
    if repeated:
        rows.append(_diagnostic("W261", "Item event field(s) must occur exactly once: %s." % ", ".join(repeated), item))

    event_type = str(_first(item, "event", ""))
    if event_type and event_type not in ITEM_EVENT_TYPES:
        rows.append(_diagnostic("W262", "Unsupported item event %r." % event_type, item))
    allowed = set(_COMMON_FIELDS + _OPTIONAL_COMMON_FIELDS)
    if event_type in _EVENT_FIELDS:
        required_payload = _EVENT_FIELDS[event_type]
        allowed.update(required_payload)
        allowed.update(_OPTIONAL_EVENT_FIELDS.get(event_type, ()))
        if event_type == "schedule_changed":
            allowed.update(_MISSING_FIELDS + _VALUE_FIELDS)
        missing_payload = [key for key in required_payload if len(_values(item, key)) != 1]
        if missing_payload:
            rows.append(_diagnostic("W263", "Item event payload field(s) must occur exactly once: %s." % ", ".join(missing_payload), item))
    unknown = sorted(set(getattr(item, "details", {})) - allowed)
    if unknown:
        rows.append(_diagnostic("W264", "Item event contains unsupported field(s): %s." % ", ".join(unknown), item))
    repeated_optional = [key for key in allowed if len(_values(item, key)) > 1]
    if repeated_optional:
        rows.append(_diagnostic("W264", "Item event field(s) must not repeat: %s." % ", ".join(sorted(repeated_optional)), item))

    try:
        raw_at = str(_first(item, "at", ""))
        normalized = _utc_text(raw_at)
        if raw_at != normalized:
            rows.append(_diagnostic("W265", "Item event timestamp must be normalized UTC (%s)." % normalized, item))
    except ValueError as exc:
        rows.append(_diagnostic("W265", str(exc), item))
    try:
        sequence = int(_first(item, "sequence", 0))
        if sequence <= 0:
            raise ValueError()
    except (TypeError, ValueError):
        sequence = 0
        rows.append(_diagnostic("W266", "Item event sequence must be a positive integer.", item))
    revision = str(_first(item, "source_revision", ""))
    if revision and not _REVISION_RE.match(revision):
        rows.append(_diagnostic("W267", "Item event source_revision must be a lowercase SHA-256 hash.", item))

    if event_type in ("relation_added", "relation_removed"):
        relation = str(_first(item, "relation", ""))
        if relation and relation not in RELATION_FIELDS:
            rows.append(_diagnostic("W268", "Unsupported relation field %r." % relation, item))
    if event_type == "schedule_changed":
        field = str(_first(item, "field", ""))
        if field and field not in SCHEDULE_FIELDS:
            rows.append(_diagnostic("W268", "Unsupported schedule field %r." % field, item))
        for side in ("before", "after"):
            values = _values(item, side)
            missing_values = _values(item, side + "_missing")
            valid_missing = missing_values == ["true"]
            if (len(values) == 1) == valid_missing or (missing_values and not valid_missing):
                rows.append(_diagnostic("W269", "schedule_changed requires exactly one of %s or %s_missing:true." % (side, side), item))
    if event_type in ("status_changed", "completed", "reopened", "canceled"):
        before = str(_first(item, "before_status", ""))
        after = str(_first(item, "after_status", ""))
        if before and after and before == after:
            rows.append(_diagnostic("W270", "%s must change status." % event_type, item))
    return rows


def item_event_history_diagnostics(items, id_key="id"):
    """Return diagnostics that make an item-event stream non-authoritative."""
    rows = []
    parent_items = _parent_index(items, id_key)
    ids = {}
    transactions = {}
    sequences = {}
    by_parent = {}
    for event in iter_item_events(items):
        rows.extend(item_event_diagnostics(event))
        parent = str(_first(event, "parent", ""))
        if parent and len(parent_items.get(parent, [])) != 1:
            rows.append(_diagnostic("W271", "Item event parent %r does not resolve to exactly one item." % parent, event))
        try:
            sequence = int(_first(event, "sequence", 0))
        except (TypeError, ValueError):
            sequence = 0
        identifier = str(_first(event, "id", ""))
        transaction = str(_first(event, "transaction", ""))
        for key, value, seen in (("id", identifier, ids), ("transaction", transaction, transactions)):
            if value in seen:
                rows.append(_diagnostic("W272", "Duplicate item event %s %r." % (key, value), event))
            elif value:
                seen[value] = event
        pair = (parent, sequence)
        if parent and sequence > 0:
            if pair in sequences:
                rows.append(_diagnostic("W272", "Duplicate item event sequence %d for item %s." % (sequence, parent), event))
            sequences[pair] = event
            if identifier and identifier != item_event_id(parent, sequence):
                rows.append(_diagnostic("W272", "Item event id %r does not match parent/sequence; expected %r." % (identifier, item_event_id(parent, sequence)), event))
            by_parent.setdefault(parent, []).append(event)

    for parent, events in by_parent.items():
        ordered = sorted(events, key=lambda row: int(_first(row, "sequence", 0)))
        found = sorted(set(int(_first(row, "sequence", 0)) for row in ordered))
        expected_start = 1 if ordered and _first(ordered[0], "event") == "created" else found[0]
        expected = list(range(expected_start, max(found) + 1)) if found else []
        if found != expected:
            rows.append(_diagnostic("W273", "Item %s event sequence has gaps: found %s." % (parent, ",".join(str(value) for value in found)), ordered[-1]))
        previous_status = None
        previous_at = None
        for event in ordered:
            event_type = str(_first(event, "event", ""))
            try:
                event_at = parse_iso_datetime(str(_first(event, "at", "")))
            except (TypeError, ValueError):
                event_at = None
            if previous_at and event_at and previous_at > event_at:
                rows.append(_diagnostic("W274", "Item %s event timestamps go backwards at sequence %s." % (parent, _first(event, "sequence", "?")), event))
            if event_at:
                previous_at = event_at
            if event_type == "created":
                if event is not ordered[0] or int(_first(event, "sequence", 0)) != 1:
                    rows.append(_diagnostic("W275", "Item %s created event must be sequence 1." % parent, event))
                previous_status = str(_first(event, "after_status", ""))
            elif event_type in ("status_changed", "completed", "reopened", "canceled"):
                before = str(_first(event, "before_status", ""))
                after = str(_first(event, "after_status", ""))
                if previous_status is not None and before != previous_status:
                    rows.append(_diagnostic("W276", "Item %s status history is discontinuous at sequence %s." % (parent, _first(event, "sequence", "?")), event))
                previous_status = after
        if previous_status is not None and len(parent_items.get(parent, [])) == 1:
            if getattr(parent_items[parent][0], "status", None) != previous_status:
                rows.append(_diagnostic("W277", "Item %s current status does not match its latest item event." % parent, ordered[-1]))
    return rows


def item_event_completeness(items, parent_id, id_key="id"):
    """Return explicit coverage; absence of a creation event is readable partial."""
    events = sorted(iter_item_events(items, parent_id), key=lambda row: int(_first(row, "sequence", 0) or 0))
    relevant = events + _parent_index(items, id_key).get(str(parent_id), [])
    diagnostics = item_event_history_diagnostics(relevant, id_key=id_key)
    from_creation = bool(events and _first(events[0], "event") == "created" and _first(events[0], "sequence") == "1")
    return OrderedDict(
        (
            ("coverage", "from_creation" if from_creation else "partial"),
            ("complete", bool(from_creation and not diagnostics)),
            ("diagnostic_codes", [row.code for row in diagnostics]),
        )
    )


def _normalized(item, record_kind, event, at, sequence, transaction, revision, payload, valid=True):
    return OrderedDict(
        (
            ("record_kind", record_kind),
            ("record_id", str(_first(item, "id", ""))),
            ("parent", str(_first(item, "parent", ""))),
            ("event", str(event)),
            ("at", at),
            ("sequence", sequence),
            ("transaction", str(transaction or "")),
            ("source_revision", str(revision or "")),
            ("payload", payload),
            ("valid", bool(valid)),
        )
    )


def normalize_native_events(items, parent_id=None):
    """Adapt all native history records without changing their stored shape."""
    from .progress_history import is_progress_event
    from .ticket_activity import (
        is_ticket_event,
        is_time_entry,
        validate_ticket_event,
        validate_time_entry,
    )

    rows = []
    for item in items:
        parent = str(_first(item, "parent", ""))
        if parent_id is not None and parent != str(parent_id):
            continue
        if is_item_event(item):
            # Keep actor/source provenance in the normalized read model.  They
            # are common envelope fields, but analytics consumers must not lose
            # the original field/value when adapting an event.
            excluded = set(_COMMON_FIELDS)
            payload = OrderedDict((key, list(_values(item, key))) for key in item.details if key not in excluded)
            rows.append(_normalized(item, ITEM_EVENT_MARKER, _first(item, "event", ""), _first(item, "at", ""), _int_or_none(_first(item, "sequence")), _first(item, "transaction", ""), _first(item, "source_revision", ""), payload, not item_event_diagnostics(item)))
        elif is_progress_event(item):
            payload = OrderedDict((key, list(_values(item, key))) for key in ("operation", "before_progress", "before_missing", "after_progress") if _values(item, key))
            rows.append(_normalized(item, "progress_event", "progress_" + str(_first(item, "operation", "unknown")), _first(item, "at", ""), _int_or_none(_first(item, "sequence")), _first(item, "transaction", ""), _first(item, "source_revision", ""), payload, _valid_progress_shape(item)))
        elif is_ticket_event(item):
            excluded = {"record", "id", "parent", "event", "at", "sequence", "transaction", "ticket_revision"}
            payload = OrderedDict((key, list(_values(item, key))) for key in item.details if key not in excluded)
            rows.append(_normalized(item, "ticket_event", _first(item, "event", ""), _first(item, "at", ""), _int_or_none(_first(item, "sequence")), _first(item, "transaction", ""), _first(item, "ticket_revision", ""), payload, not validate_ticket_event(item)))
        elif is_time_entry(item):
            excluded = {"record", "id", "parent", "created_at", "sequence", "event"}
            payload = OrderedDict((key, list(_values(item, key))) for key in item.details if key not in excluded)
            rows.append(_normalized(item, "time_entry", "time_entry", _first(item, "created_at", _first(item, "on", "")), _int_or_none(_first(item, "sequence")), _first(item, "event_id", ""), "", payload, not validate_time_entry(item)))
    return rows


def _int_or_none(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _valid_progress_shape(item):
    from .progress import ProgressValueError, parse_progress
    from .progress_history import PROGRESS_EVENT_OPERATIONS

    required = (
        "id",
        "parent",
        "at",
        "sequence",
        "transaction",
        "source_revision",
        "operation",
        "after_progress",
    )
    if any(len(_values(item, key)) != 1 for key in required):
        return False
    try:
        if _utc_text(_first(item, "at")) != _first(item, "at"):
            return False
        if int(_first(item, "sequence")) <= 0:
            return False
        if not _REVISION_RE.match(str(_first(item, "source_revision", ""))):
            return False
        if _first(item, "operation") not in PROGRESS_EVENT_OPERATIONS:
            return False
        parse_progress(_first(item, "after_progress"))
        before = _values(item, "before_progress")
        before_missing = _values(item, "before_missing") == ["true"]
        if (len(before) == 1) == before_missing:
            return False
        if before:
            parse_progress(before[0])
    except (TypeError, ValueError, ProgressValueError):
        return False
    return True


def native_history_completeness(items, parent_id, id_key="id"):
    """Report bounded completeness independently for each stored domain."""
    from .progress_history import authoritative_progress_events, iter_progress_events
    from .ticket_activity import (
        iter_ticket_events,
        iter_time_entries,
        validate_ticket_event,
        validate_time_entry,
    )

    parent_id = str(parent_id)
    progress = list(iter_progress_events(items, parent_id))
    tickets = list(iter_ticket_events(items, parent_id))
    times = list(iter_time_entries(items, parent_id))
    ticket_valid = bool(tickets) and not any(validate_ticket_event(row) for row in tickets)
    ticket_from_creation = bool(
        ticket_valid
        and any(
            _first(row, "event") == "created" and _first(row, "sequence") == "1"
            for row in tickets
        )
    )
    return OrderedDict(
        (
            ("item", item_event_completeness(items, parent_id, id_key=id_key)),
            (
                "progress",
                OrderedDict(
                    (
                        ("coverage", "from_first_write" if progress else "none"),
                        (
                            "complete",
                            bool(
                                progress
                                and authoritative_progress_events(
                                    items, parent_id, id_key=id_key
                                )
                            ),
                        ),
                    )
                ),
            ),
            (
                "ticket",
                OrderedDict(
                    (
                        ("coverage", "from_creation" if ticket_from_creation else ("partial" if tickets else "none")),
                        ("complete", ticket_from_creation),
                    )
                ),
            ),
            (
                "time_entry",
                OrderedDict(
                    (
                        ("coverage", "recorded_entries" if times else "none"),
                        ("complete", bool(times and not any(validate_time_entry(row) for row in times))),
                    )
                ),
            ),
        )
    )
