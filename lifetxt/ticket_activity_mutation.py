"""Exact-revision compound ticket and append-only activity mutations."""

from __future__ import unicode_literals

import copy
import re
from collections import OrderedDict

from .serializer import item_to_line

from . import mutation
from .surface_runtime import normalize_revision
from .ticket_activity import (
    _first,
    _utc_text,
    _sequence,
    _time_sequence,
    _safe_id,
    _changed_fields,
    build_ticket_event,
    build_time_entry,
    event_view,
    time_entry_view,
    iter_ticket_events,
    validate_ticket_history,
)


def _append_items(text, items):
    if not items:
        return text
    newline = "\r\n" if "\r\n" in text else "\n"
    prefix = text
    if prefix and not prefix.endswith(("\n", "\r")):
        prefix += newline
    rendered = newline.join(item_to_line(item).replace("\n", newline) for item in items)
    return prefix + rendered + newline


def _parse_items(text, key):
    from .parser import parse_text

    items, diagnostics = parse_text(
        text, id_key=key, check_ids=False, check_references=False
    )
    errors = [
        d.to_dict() for d in diagnostics if getattr(d, "severity", None) == "error"
    ]
    if errors:
        raise ValueError(errors)
    return items


def _find_ticket(items, ticket_id, key):
    from .tickets import is_ticket, ticket_id_of

    matches = [
        item
        for item in items
        if is_ticket(item) and str(ticket_id_of(item, key)) == str(ticket_id)
    ]
    if not matches:
        raise ValueError("Ticket %r not found." % ticket_id)
    if len(matches) > 1:
        raise ValueError("Multiple tickets found with %s:%s." % (key, ticket_id))
    return matches[0]


def _copy_item(item):
    cloned = copy.copy(item)
    cloned.details = OrderedDict(
        (key, list(values)) for key, values in item.details.items()
    )
    return cloned


def _transaction_id(ticket_id, sequence, timestamp, supplied=None):
    if supplied not in (None, ""):
        value = str(supplied).strip()
        if not re.match(r"^[A-Za-z0-9_.:-]+$", value):
            raise ValueError("Transaction id contains unsupported characters.")
        return value
    stamp = (
        str(timestamp)
        .replace("-", "")
        .replace(":", "")
        .replace("T", "-")
        .replace("Z", "")
    )
    return "TX-%s-%06d-%s" % (_safe_id(ticket_id), int(sequence), stamp)


def apply_ticket_activity(
    path,
    ticket_id,
    event_type,
    author,
    expected_revision,
    config=None,
    key="id",
    detail_updates=None,
    status=None,
    comment=None,
    at=None,
    event_extra=None,
    time_entry=None,
    transaction_id=None,
    dry_run=False,
    operation=None,
):
    """Apply a ticket change and required side records in one exact-revision write."""
    from .ticket_revision_writes import _replace_ticket_text
    from .tickets import validate_ticket

    expected = normalize_revision(
        expected_revision, supplied=expected_revision is not None
    )
    if expected is None:
        raise ValueError(
            "Ticket activity writes require an exact --revision from `ticket revision`."
        )
    timestamp = _utc_text(at)
    snapshot = mutation.read_text_snapshot(path, allow_missing=False)
    if snapshot.content_hash != expected:
        raise mutation.MutationConflict(
            path, expected, snapshot.content_hash, operation=operation or event_type
        )

    holder = {}

    def transform(current):
        items_before = _parse_items(current, key)
        before_ticket = _find_ticket(items_before, ticket_id, key)
        sequence = _sequence(items_before, ticket_id)
        txid = _transaction_id(ticket_id, sequence, timestamp, transaction_id)
        for existing in iter_ticket_events(items_before):
            if str(_first(existing, "transaction", "")) == txid:
                raise ValueError("Ticket transaction %r already exists." % txid)

        def update_item(item):
            for field, value in (detail_updates or {}).items():
                if value is None:
                    item.details.pop(str(field), None)
                elif isinstance(value, (list, tuple)):
                    item.details[str(field)] = [str(entry) for entry in value]
                else:
                    item.details[str(field)] = [str(value)]
            if status is not None:
                item.status = str(status)

        changed_ticket = bool(detail_updates) or status is not None
        if changed_ticket:
            replacement, updated = _replace_ticket_text(
                current, ticket_id, key, update_item
            )
        else:
            replacement = current
            updated = _copy_item(before_ticket)

        ticket_errors = [
            row
            for row in validate_ticket(updated, config or {}, key=key)
            if row.get("severity") == "error"
        ]
        if ticket_errors:
            raise ValueError(ticket_errors)

        changes = _changed_fields(before_ticket, updated)
        from_status = _first(before_ticket, "ticket_status")
        to_status = _first(updated, "ticket_status")
        event = build_ticket_event(
            ticket_id,
            event_type,
            author,
            timestamp,
            sequence,
            txid,
            expected,
            changes=changes,
            body=comment,
            project=_first(updated, "project"),
            tracker=_first(updated, "tracker"),
            from_status=from_status,
            to_status=to_status,
            extra=event_extra,
        )
        appended = [event]
        time_item = None
        if time_entry is not None:
            time_sequence = _time_sequence(items_before, ticket_id)
            time_item = build_time_entry(
                ticket_id,
                _first(updated, "project"),
                time_entry.get("user") or author,
                time_entry.get("activity") or "development",
                time_entry.get("date"),
                time_entry.get("duration"),
                time_sequence,
                _first(event, "id"),
                timestamp,
                comment=time_entry.get("comment"),
                source=time_entry.get("source"),
                timer_ref=time_entry.get("timer_ref"),
                corrects=time_entry.get("corrects"),
            )
            appended.append(time_item)
        final_text = _append_items(replacement, appended)
        final_items = _parse_items(final_text, key)
        history_errors = [
            row
            for row in validate_ticket_history(final_items, config=config, key=key)
            if row.get("severity") == "error"
        ]
        if history_errors:
            raise ValueError(history_errors)
        holder.update(
            {
                "ticket": updated,
                "event": event,
                "time_entry": time_item,
                "transaction_id": txid,
                "text": final_text,
            }
        )
        return final_text

    operation_name = operation or ("ticket.%s" % event_type)
    if dry_run:
        replacement = transform(snapshot.text)
        after_hash = mutation.hash_text(
            replacement, encoding=snapshot.encoding, bom=snapshot.bom
        )
        result = None
    else:
        result = mutation.mutate_text(
            path,
            transform,
            expected_hash=expected,
            operation=operation_name,
        )
        after_hash = result.after_hash
    return OrderedDict(
        (
            ("contract_version", "1"),
            ("operation", operation_name),
            ("path", str(path)),
            ("ticket_id", str(ticket_id)),
            ("transaction_id", holder["transaction_id"]),
            ("dry_run", bool(dry_run)),
            ("changed", True),
            ("revision_before", expected),
            ("revision_after", after_hash),
            ("ticket", holder["ticket"].to_dict()),
            ("event", event_view(holder["event"])),
            (
                "time_entry",
                time_entry_view(holder["time_entry"])
                if holder.get("time_entry") is not None
                else None,
            ),
        )
    )
