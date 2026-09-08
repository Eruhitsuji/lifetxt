"""Append-only, authoritative history for explicit ``progress:`` writes.

``record:progress_event`` Notes live beside the item they describe.  The
supported progress command replaces the item and appends its event in one
exact-revision mutation, so this path cannot publish a new current value
without its corresponding evidence.  Manual and generic edits remain valid,
but continuity validation makes them visible as incomplete history rather
than guessing a timeline from the current file.
"""

from __future__ import unicode_literals

import datetime
import re
from collections import OrderedDict, namedtuple

from . import mutation
from .model import Diagnostic, Item
from .parser import parse_text
from .progress import ProgressValueError, parse_progress
from .serializer import item_to_line
from .timeutil import parse_iso_datetime
from .timezone_policy import utcnow
from .write_operations import SemanticWriteError, transform_items_text


PROGRESS_EVENT_MARKER = "progress_event"
PROGRESS_EVENT_OPERATIONS = ("set", "delta")
_REVISION_RE = re.compile(r"^[0-9a-f]{64}$")
_SAFE_ID_RE = re.compile(r"[^A-Za-z0-9_.-]+")

ProgressMutationResult = namedtuple(
    "ProgressMutationResult", ("mutation", "item", "event")
)


def _first(item, key, default=None):
    values = getattr(item, "details", {}).get(key) or []
    return values[0] if values else default


def _values(item, key):
    return [str(value) for value in (getattr(item, "details", {}).get(key) or [])]


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
            raise ValueError(
                "Progress event timestamp must be an ISO date-time with an offset."
            )
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("Progress event timestamp must include a UTC offset.")
    return (
        parsed.astimezone(datetime.timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def is_progress_event(item):
    return (
        getattr(item, "kind", None) == "N"
        and PROGRESS_EVENT_MARKER in _values(item, "record")
    )


def iter_progress_events(items, parent_id=None):
    rows = [item for item in items if is_progress_event(item)]
    if parent_id is not None:
        rows = [
            item
            for item in rows
            if str(_first(item, "parent", "")) == str(parent_id)
        ]
    return rows


def progress_event_id(parent_id, sequence):
    return "PE-%s-%06d" % (_safe_id(parent_id), int(sequence))


def _sequence(items, parent_id):
    values = []
    for item in iter_progress_events(items, parent_id):
        try:
            values.append(int(_first(item, "sequence", 0)))
        except (TypeError, ValueError):
            continue
    return max(values or [0]) + 1


def _transaction_id(parent_id, sequence, timestamp):
    stamp = (
        str(timestamp)
        .replace("-", "")
        .replace(":", "")
        .replace("T", "-")
        .replace("Z", "")
    )
    return "PTX-%s-%06d-%s" % (_safe_id(parent_id), int(sequence), stamp)


def build_progress_event(
    parent_id,
    before_progress,
    after_progress,
    operation,
    at,
    sequence,
    transaction_id,
    source_revision,
):
    """Build one progress event while preserving raw progress values."""
    if operation not in PROGRESS_EVENT_OPERATIONS:
        raise ValueError("Unsupported progress event operation %r." % operation)
    parse_progress(after_progress)
    if before_progress is not None:
        parse_progress(before_progress)
    if not _REVISION_RE.match(str(source_revision or "")):
        raise ValueError("Progress event source revision must be a SHA-256 hash.")
    timestamp = _utc_text(at)
    sequence = int(sequence)
    if sequence <= 0:
        raise ValueError("Progress event sequence must be a positive integer.")

    details = OrderedDict()
    details["record"] = [PROGRESS_EVENT_MARKER]
    details["id"] = [progress_event_id(parent_id, sequence)]
    details["parent"] = [str(parent_id)]
    details["at"] = [timestamp]
    details["sequence"] = [str(sequence)]
    details["transaction"] = [str(transaction_id)]
    details["source_revision"] = [str(source_revision)]
    details["operation"] = [str(operation)]
    if before_progress is None:
        details["before_missing"] = ["true"]
    else:
        details["before_progress"] = [str(before_progress)]
    details["after_progress"] = [str(after_progress)]
    title = "Progress_%s_%06d" % (_safe_id(parent_id), sequence)
    return Item("[N]", "N", title, details)


def _append_item(text, item):
    newline = "\r\n" if "\r\n" in text else "\n"
    prefix = text
    if prefix and not prefix.endswith(("\n", "\r")):
        prefix += newline
    return prefix + item_to_line(item).replace("\n", newline) + newline


def _parse_items(text, id_key):
    items, diagnostics = parse_text(
        text, id_key=id_key, check_ids=False, check_references=False
    )
    errors = [
        diagnostic.to_dict()
        for diagnostic in diagnostics
        if getattr(diagnostic, "severity", None) == "error"
    ]
    if errors:
        raise ValueError(errors)
    return items


def _find_item(items, item_id, id_key):
    matches = [
        item
        for item in items
        if not is_progress_event(item)
        and str(item_id) in [str(value) for value in item.details.get(id_key, [])]
    ]
    if len(matches) != 1:
        raise SemanticWriteError(
            "Expected exactly one item with %s:%s, found %d."
            % (id_key, item_id, len(matches))
        )
    return matches[0]


def apply_progress_mutation(
    path,
    item_id,
    new_progress,
    operation,
    expected_revision,
    id_key="id",
    expected_before=None,
    at=None,
):
    """Update an item's progress and append its event in one CAS mutation."""
    if expected_revision in (None, ""):
        raise ValueError("Progress history writes require an exact source revision.")
    parse_progress(new_progress)
    timestamp = _utc_text(at)
    holder = {}

    def transform(current):
        items_before = _parse_items(current, id_key)
        before_item = _find_item(items_before, item_id, id_key)
        raw_values = before_item.details.get("progress") or []
        before_progress = raw_values[0] if raw_values else None
        if before_progress != expected_before:
            raise mutation.MutationConflict(
                path,
                expected_revision,
                mutation.hash_text(current),
                operation="progress history precondition",
            )
        if before_progress is not None:
            parse_progress(before_progress)

        sequence = _sequence(items_before, item_id)
        txid = _transaction_id(item_id, sequence, timestamp)
        if any(
            str(_first(event, "transaction", "")) == txid
            for event in iter_progress_events(items_before)
        ):
            raise ValueError("Progress transaction %r already exists." % txid)
        event = build_progress_event(
            item_id,
            before_progress,
            new_progress,
            operation,
            timestamp,
            sequence,
            txid,
            expected_revision,
        )
        event_identifier = str(_first(event, "id", ""))
        if any(event_identifier in _values(item, "id") for item in items_before):
            raise ValueError("Progress event id %r already exists." % event_identifier)
        replacement = transform_items_text(
            current,
            [
                {
                    "id": str(item_id),
                    "set_details": {"progress": [str(new_progress)]},
                }
            ],
            id_key=id_key,
        )
        final_text = _append_item(replacement, event)
        final_items = _parse_items(final_text, id_key)
        holder["event"] = event
        holder["item"] = _find_item(final_items, item_id, id_key)
        return final_text

    result = mutation.mutate_text(
        path,
        transform,
        expected_hash=str(expected_revision),
        operation="progress.%s" % operation,
    )
    return ProgressMutationResult(result, holder["item"], holder["event"])


def _diagnostic(code, message, item=None, hint=None):
    return Diagnostic(
        "warning",
        code,
        message,
        line=getattr(item, "line", None),
        source=getattr(item, "source", None),
        hint=hint
        or "Append progress history through `lifetxt progress`; do not edit events.",
    )


def progress_history_diagnostics(items, id_key="id"):
    """Return diagnostics for evidence that cannot be treated as authoritative."""
    events = iter_progress_events(items)
    parent_items = {}
    for item in items:
        if is_progress_event(item):
            continue
        for value in item.details.get(id_key, []):
            parent_items.setdefault(str(value), []).append(item)

    rows = []
    ids = {}
    transactions = {}
    sequences = {}
    by_parent = {}
    for event in events:
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
        missing = [key for key in required if not _values(event, key)]
        if missing:
            rows.append(
                _diagnostic(
                    "W231",
                    "Progress event is missing required field(s): %s."
                    % ", ".join(missing),
                    event,
                )
            )
        repeated = [key for key in required if len(_values(event, key)) > 1]
        if repeated:
            rows.append(
                _diagnostic(
                    "W231",
                    "Progress event field(s) must occur exactly once: %s."
                    % ", ".join(repeated),
                    event,
                )
            )

        parent = str(_first(event, "parent", ""))
        if parent and len(parent_items.get(parent, [])) != 1:
            rows.append(
                _diagnostic(
                    "W232",
                    "Progress event parent %r does not resolve to exactly one item."
                    % parent,
                    event,
                )
            )
        try:
            raw_timestamp = str(_first(event, "at", ""))
            timestamp = _utc_text(raw_timestamp)
            if raw_timestamp != timestamp:
                rows.append(
                    _diagnostic(
                        "W233",
                        "Progress event timestamp must be normalized UTC (%s)."
                        % timestamp,
                        event,
                    )
                )
        except ValueError as exc:
            timestamp = None
            rows.append(_diagnostic("W233", str(exc), event))
        try:
            sequence = int(_first(event, "sequence", 0))
            if sequence <= 0:
                raise ValueError()
        except (TypeError, ValueError):
            sequence = 0
            rows.append(
                _diagnostic(
                    "W234", "Progress event sequence must be a positive integer.", event
                )
            )

        revision = str(_first(event, "source_revision", ""))
        if revision and not _REVISION_RE.match(revision):
            rows.append(
                _diagnostic(
                    "W235",
                    "Progress event source_revision must be a lowercase SHA-256 hash.",
                    event,
                )
            )
        operation = str(_first(event, "operation", ""))
        if operation and operation not in PROGRESS_EVENT_OPERATIONS:
            rows.append(
                _diagnostic(
                    "W236",
                    "Unsupported progress event operation %r." % operation,
                    event,
                )
            )

        before_values = _values(event, "before_progress")
        after_values = _values(event, "after_progress")
        before_missing_values = _values(event, "before_missing")
        before_missing = before_missing_values == ["true"]
        if before_missing == bool(before_values):
            rows.append(
                _diagnostic(
                    "W237",
                    "Progress event must contain exactly one of before_progress "
                    "or before_missing:true.",
                    event,
                )
            )
        if before_missing_values and not before_missing:
            rows.append(
                _diagnostic(
                    "W237", "before_missing must occur exactly once as true.", event
                )
            )
        if before_missing and operation == "delta":
            rows.append(
                _diagnostic(
                    "W237",
                    "A delta progress event cannot start from missing progress.",
                    event,
                )
            )
        if before_missing and sequence > 1:
            rows.append(
                _diagnostic(
                    "W237",
                    "Only the first progress event may start from missing progress.",
                    event,
                )
            )
        for key, values in (
            ("before_progress", before_values),
            ("after_progress", after_values),
        ):
            if len(values) > 1:
                rows.append(
                    _diagnostic(
                        "W238", "%s must occur exactly once." % key, event
                    )
                )
            for value in values:
                try:
                    parse_progress(value)
                except ProgressValueError as exc:
                    rows.append(
                        _diagnostic("W238", "%s: %s." % (key, exc.reason), event)
                    )

        identifier = str(_first(event, "id", ""))
        if identifier:
            if identifier in ids:
                rows.append(
                    _diagnostic(
                        "W239", "Duplicate progress event id %r." % identifier, event
                    )
                )
            ids[identifier] = event
        transaction = str(_first(event, "transaction", ""))
        if transaction:
            if transaction in transactions:
                rows.append(
                    _diagnostic(
                        "W239",
                        "Duplicate progress transaction %r." % transaction,
                        event,
                    )
                )
            transactions[transaction] = event
        pair = (parent, sequence)
        if parent and sequence > 0:
            if pair in sequences:
                rows.append(
                    _diagnostic(
                        "W239",
                        "Duplicate progress sequence %d for item %s."
                        % (sequence, parent),
                        event,
                    )
                )
            sequences[pair] = event
            by_parent.setdefault(parent, []).append(
                (
                    sequence,
                    timestamp,
                    before_values,
                    before_missing,
                    after_values,
                    event,
                )
            )
            expected_id = progress_event_id(parent, sequence)
            if identifier and identifier != expected_id:
                rows.append(
                    _diagnostic(
                        "W239",
                        "Progress event id %r does not match parent/sequence; "
                        "expected %r." % (identifier, expected_id),
                        event,
                    )
                )

    for parent, parent_events in by_parent.items():
        ordered = sorted(parent_events, key=lambda row: row[0])
        found = sorted(set(row[0] for row in ordered))
        expected = list(range(1, max(found) + 1)) if found else []
        if found != expected:
            rows.append(
                _diagnostic(
                    "W240",
                    "Item %s progress event sequence has gaps: found %s."
                    % (parent, ",".join(str(value) for value in found)),
                    ordered[-1][-1] if ordered else None,
                )
            )
        for previous, current in zip(ordered, ordered[1:]):
            if previous[4] and current[2] and previous[4][0] != current[2][0]:
                rows.append(
                    _diagnostic(
                        "W241",
                        "Item %s progress history is discontinuous between "
                        "sequences %d and %d."
                        % (parent, previous[0], current[0]),
                        current[-1],
                    )
                )
            if previous[1] and current[1] and previous[1] > current[1]:
                rows.append(
                    _diagnostic(
                        "W242",
                        "Item %s progress event timestamps go backwards at sequence %d."
                        % (parent, current[0]),
                        current[-1],
                    )
                )
        if ordered and ordered[-1][4] and len(parent_items.get(parent, [])) == 1:
            current_values = parent_items[parent][0].details.get("progress") or []
            current_raw = current_values[0] if current_values else None
            if current_raw != ordered[-1][4][0]:
                rows.append(
                    _diagnostic(
                        "W243",
                        "Item %s current progress does not match its latest "
                        "progress event." % parent,
                        ordered[-1][-1],
                        hint=(
                            "Record the current value through `lifetxt progress`; "
                            "history is incomplete until reconciled."
                        ),
                    )
                )
    return rows


def authoritative_progress_events(items, parent_id, id_key="id"):
    """Return ordered events only when that parent's full chain is valid."""
    parent_id = str(parent_id)
    relevant_items = [
        item
        for item in items
        if (
            is_progress_event(item)
            and str(_first(item, "parent", "")) == parent_id
        )
        or parent_id in [str(value) for value in item.details.get(id_key, [])]
    ]
    diagnostics = progress_history_diagnostics(relevant_items, id_key=id_key)
    if diagnostics:
        return []
    return sorted(
        iter_progress_events(relevant_items, parent_id),
        key=lambda item: int(_first(item, "sequence", 0)),
    )
