"""Surface-neutral exact-revision item mutations with native evidence."""

from __future__ import unicode_literals

from collections import namedtuple

from . import mutation
from .native_history import build_item_event, iter_item_events
from .parser import parse_text
from .serializer import item_to_line
from .timezone_policy import utcnow
from .write_operations import SemanticWriteError


NativeMutationResult = namedtuple("NativeMutationResult", ("mutation", "item", "event"))


def _values(item, key):
    return [str(value) for value in (getattr(item, "details", {}).get(key) or [])]


def _first(item, key, default=None):
    values = _values(item, key)
    return values[0] if values else default


def _parse(text, id_key):
    items, diagnostics = parse_text(
        text, id_key=id_key, check_ids=False, check_references=False
    )
    errors = [row for row in diagnostics if row.severity == "error"]
    if errors:
        raise ValueError(errors[0].format())
    return items


def _find(items, item_id, id_key, required=True):
    matches = [
        item
        for item in items
        if not iter_item_events([item]) and str(item_id) in _values(item, id_key)
    ]
    if len(matches) != (1 if required else 0):
        expected = "exactly one" if required else "no"
        raise SemanticWriteError(
            "Expected %s item with %s:%s, found %d."
            % (expected, id_key, item_id, len(matches))
        )
    return matches[0] if matches else None


def _timestamp(value=None):
    from .native_history import _utc_text

    return _utc_text(value or utcnow())


def _sequence(items, item_id):
    values = []
    for event in iter_item_events(items, item_id):
        try:
            values.append(int(_first(event, "sequence", 0)))
        except (TypeError, ValueError):
            continue
    return max(values or [0]) + 1


def _transaction(item_id, sequence, timestamp):
    stamp = (
        timestamp.replace("-", "").replace(":", "").replace("T", "-").replace("Z", "")
    )
    return "ITX-%s-%06d-%s" % (str(item_id), int(sequence), stamp)


def _append(text, event):
    newline = "\r\n" if "\r\n" in text else "\n"
    prefix = text
    if prefix and not prefix.endswith(("\n", "\r")):
        prefix += newline
    return prefix + item_to_line(event).replace("\n", newline) + newline


def _derived_payload(
    event_type, before, after, field=None, target=None, completed_at=None
):
    if event_type == "created":
        return {
            "item_kind": after.kind,
            "item_title": after.title,
            "after_status": after.status,
        }
    if event_type in ("status_changed", "completed", "reopened", "canceled"):
        if before.status == after.status:
            raise ValueError("%s requires an actual status transition." % event_type)
        payload = {"before_status": before.status, "after_status": after.status}
        if event_type == "completed" and completed_at:
            payload["completed_at"] = completed_at
        return payload
    if event_type in ("relation_added", "relation_removed"):
        before_values = _values(before, field)
        after_values = _values(after, field)
        if event_type == "relation_added" and not (
            target not in before_values and target in after_values
        ):
            raise ValueError("relation_added does not match the item mutation.")
        if event_type == "relation_removed" and not (
            target in before_values and target not in after_values
        ):
            raise ValueError("relation_removed does not match the item mutation.")
        return {"relation": field, "target": target}
    if event_type == "schedule_changed":
        before_values = _values(before, field)
        after_values = _values(after, field)
        if len(before_values) > 1 or len(after_values) > 1:
            raise ValueError("schedule_changed supports one value per field in v1.")
        if before_values == after_values:
            raise ValueError("schedule_changed requires an actual value transition.")
        return {
            "field": field,
            "before": before_values[0] if before_values else None,
            "before_missing": not before_values,
            "after": after_values[0] if after_values else None,
            "after_missing": not after_values,
        }
    raise ValueError("Unsupported item event %r." % event_type)


_STATUS_EVENT_FOR = {
    # (before.status, after.status) -> event_type, mirroring the exact
    # transitions CLI's own done/complete/reopen commands already emit
    # (#714). Anything not covered here (e.g. "[ ]" -> "[/]") is a
    # supported status_changed, since it does not represent completion,
    # reopening, or cancellation specifically.
    ("[x]", "[/]"): "reopened",
    ("[x]", "[ ]"): "reopened",
}


def _classify_status_transition(before_status, after_status):
    if before_status == after_status:
        return None
    if after_status == "[x]":
        return "completed"
    if after_status == "[-]":
        return "canceled"
    mapped = _STATUS_EVENT_FOR.get((before_status, after_status))
    if mapped is not None:
        return mapped
    return "status_changed"


def infer_item_event_specs(before, after):
    """Classify a before/after item pair into zero or more supported
    ``record:item_event`` specs (#767).

    Pure, file-I/O-free diff over two already-parsed
    :class:`lifetxt.model.Item` objects, reusing exactly the same event
    vocabulary and field scope CLI's dedicated done/complete/reopen/due
    commands already emit through
    :func:`augment_item_mutation_with_event`/:func:`build_item_event`
    (#714) -- ``status`` family transitions, the ``due:`` schedule field
    (the only schedule field with an atomic capture route today, per the
    #759 investigation), and the ``follows``/``realizes``/``replaced_by``
    lifecycle relations.

    Returns a list of ``{"event_type": ..., "field": ..., "target": ...}``
    dicts suitable for :func:`commit_item_mutations_with_events`'s
    ``event_specs``/``augment_item_mutation_with_event``'s ``field``/
    ``target`` arguments (each entry omits ``field``/``target`` when not
    applicable). An empty list means no supported semantic change was
    detected -- the caller should commit the plain mutation with no
    Native History event, exactly as an unsupported generic edit already
    does; this function never guesses at an unsupported change.
    """
    specs = []
    status_event = _classify_status_transition(before.status, after.status)
    if status_event is not None:
        specs.append({"event_type": status_event})
    before_due = _values(before, "due")
    after_due = _values(after, "due")
    if before_due != after_due and len(before_due) <= 1 and len(after_due) <= 1:
        specs.append({"event_type": "schedule_changed", "field": "due"})
    for relation in ("follows", "realizes", "replaced_by"):
        before_values = _values(before, relation)
        after_values = _values(after, relation)
        for target in after_values:
            if target not in before_values:
                specs.append(
                    {
                        "event_type": "relation_added",
                        "field": relation,
                        "target": target,
                    }
                )
        for target in before_values:
            if target not in after_values:
                specs.append(
                    {
                        "event_type": "relation_removed",
                        "field": relation,
                        "target": target,
                    }
                )
    return specs


def commit_item_mutation_with_event(
    path,
    item_id,
    event_type,
    replacement_text,
    expected_revision,
    id_key="id",
    actor=None,
    source=None,
    at=None,
    field=None,
    target=None,
    completed_at=None,
):
    """Commit a prevalidated item replacement and its event in one CAS write."""
    result, items, events = commit_item_mutations_with_events(
        path,
        replacement_text,
        expected_revision,
        [
            {
                "item_id": item_id,
                "event_type": event_type,
                "actor": actor,
                "source": source,
                "at": at,
                "field": field,
                "target": target,
                "completed_at": completed_at,
            }
        ],
        id_key=id_key,
    )
    return NativeMutationResult(result, items[0], events[0])


def commit_item_mutations_with_events(
    path, replacement_text, expected_revision, event_specs, id_key="id"
):
    """Commit one replacement plus one or more independently typed events."""
    if expected_revision in (None, ""):
        raise ValueError("Native history writes require an exact source revision.")
    specs = list(event_specs or [])
    if not specs:
        raise ValueError("At least one native item event is required.")
    holder = {"items": [], "events": []}

    def transform(current):
        final_text = replacement_text
        for spec in specs:
            final_text, after, event = augment_item_mutation_with_event(
                current,
                final_text,
                spec["item_id"],
                spec["event_type"],
                expected_revision,
                id_key=id_key,
                actor=spec.get("actor"),
                source=spec.get("source"),
                at=spec.get("at"),
                field=spec.get("field"),
                target=spec.get("target"),
                completed_at=spec.get("completed_at"),
            )
            holder["items"].append(after)
            holder["events"].append(event)
        return final_text

    result = mutation.write_text(
        path,
        expected_hash=str(expected_revision),
        operation="item_history.compound",
        create=expected_revision == mutation.MISSING_HASH,
        transform=transform,
        default_text="",
    )
    return result, holder["items"], holder["events"]


def augment_item_mutation_with_event(
    current_text,
    replacement_text,
    item_id,
    event_type,
    source_revision,
    id_key="id",
    actor=None,
    source=None,
    at=None,
    field=None,
    target=None,
    completed_at=None,
):
    """Pure transformer for journal-backed or other compound write paths."""
    before_items = _parse(current_text, id_key)
    before = _find(before_items, item_id, id_key, required=event_type != "created")
    if event_type == "created":
        _find(before_items, item_id, id_key, required=False)
    after_items = _parse(replacement_text, id_key)
    after = _find(after_items, item_id, id_key)
    sequence = _sequence(before_items, item_id)
    payload = _derived_payload(
        event_type,
        before,
        after,
        field=field,
        target=target,
        completed_at=completed_at,
    )
    revision = (
        mutation.hash_text("")
        if source_revision == mutation.MISSING_HASH
        else str(source_revision)
    )
    timestamp = _timestamp(at)
    txid = _transaction(item_id, sequence, timestamp)
    event = build_item_event(
        item_id,
        event_type,
        timestamp,
        sequence,
        txid,
        revision,
        actor=actor,
        source=source,
        **payload,
    )
    final_text = _append(replacement_text, event)
    _parse(final_text, id_key)
    return final_text, after, event
