"""Bounded per-field ``semantic-as-of-v1`` projection over Native History.

This module answers "what was true about one field at time T" by replaying
the existing, unmodified ``record:item_event`` stream up to an offset-aware
cutoff.  It never falls back to current ``life.txt`` state for a field with
no applicable event evidence at or before the cutoff -- such a field reports
``unavailable`` rather than a guess.

Every reader below is reused unmodified:

- :func:`lifetxt.native_timeline.native_timeline` supplies the ordered,
  validated, deduplicated event stream (via its private
  ``include_all_valid`` hand-off), so this module never re-implements event
  normalization, validation, or ordering.
- :func:`lifetxt.native_history.item_event_completeness` supplies the
  coverage/completeness signal used to distinguish ``known`` from
  ``partial``.
- :func:`lifetxt.historical_temporal.parse_cutoff` supplies the single
  offset-aware RFC3339 cutoff parser already used by ``show --as-of`` and
  ``query --as-of``, so there is no second timestamp-format policy.

Scope (from the ``#759`` investigation): lifecycle status, the ``due:``
schedule field, and the ``follows:``/``realizes:``/``replaced_by:``
lifecycle relations.  ``on:``/``from:``/``to:``/``at:`` and any lifecycle
relation never captured through the ticket link/unlink route always report
``unavailable`` -- there is no atomic capture route for them today.
"""

from __future__ import unicode_literals

from collections import OrderedDict

from .historical_temporal import parse_cutoff
from .native_history import RELATION_FIELDS, item_event_completeness
from .native_timeline import MAX_LIMIT, native_timeline
from .timeutil import parse_iso_datetime


SCHEMA = "semantic-as-of-v1"

_STATUS_EVENTS = ("created", "status_changed", "completed", "reopened", "canceled")
_UNCAPTURED_SCHEDULE_FIELDS = ("on", "from", "to", "at")


def _row_instant(row):
    parsed = parse_iso_datetime(str(row.get("at") or ""))
    return parsed


def _known_state(complete):
    return "known" if complete else "partial"


def _project_status(events, cutoff, complete):
    applicable = [
        row
        for row in events
        if row["record_kind"] == "item_event" and row["event"] in _STATUS_EVENTS
    ]
    at_or_before = [row for row in applicable if _row_instant(row) <= cutoff]
    if not at_or_before:
        return OrderedDict(
            (
                ("state", "unavailable"),
                ("value", None),
                ("reason", "no_status_capture_before_cutoff"),
                ("as_of_event", None),
            )
        )
    at_or_before.sort(key=lambda row: (row.get("sequence") or 0, _row_instant(row)))
    latest = at_or_before[-1]
    value = (latest["payload"].get("after_status") or [None])[0]
    return OrderedDict(
        (
            ("state", _known_state(complete)),
            ("value", value),
            ("reason", None),
            ("as_of_event", latest["record_id"] or None),
        )
    )


def _project_due(events, cutoff, complete):
    applicable = [
        row
        for row in events
        if row["record_kind"] == "item_event"
        and row["event"] == "schedule_changed"
        and (row["payload"].get("field") or [None])[0] == "due"
    ]
    if not applicable:
        return OrderedDict(
            (
                ("state", "unavailable"),
                ("value", None),
                ("reason", "no_schedule_changed_capture"),
                ("as_of_event", None),
            )
        )
    at_or_before = [row for row in applicable if _row_instant(row) <= cutoff]
    if not at_or_before:
        # A due: field was captured, but never changed at or before this
        # cutoff.  We cannot infer whether it existed earlier without a
        # creation-time snapshot of due:, which item_event "created" does
        # not carry -- so this stays explicitly unavailable rather than a
        # guessed absence.
        return OrderedDict(
            (
                ("state", "unavailable"),
                ("value", None),
                ("reason", "no_schedule_changed_capture_before_cutoff"),
                ("as_of_event", None),
            )
        )
    at_or_before.sort(key=lambda row: (row.get("sequence") or 0, _row_instant(row)))
    latest = at_or_before[-1]
    payload = latest["payload"]
    after_missing = (payload.get("after_missing") or ["false"])[0] == "true"
    value = None if after_missing else (payload.get("after") or [None])[0]
    return OrderedDict(
        (
            ("state", _known_state(complete)),
            ("value", value),
            ("reason", None),
            ("as_of_event", latest["record_id"] or None),
        )
    )


def _project_relation(events, cutoff, complete, relation):
    applicable = [
        row
        for row in events
        if row["record_kind"] == "item_event"
        and row["event"] in ("relation_added", "relation_removed")
        and (row["payload"].get("relation") or [None])[0] == relation
    ]
    if not applicable:
        return OrderedDict(
            (
                ("state", "unavailable"),
                ("values", None),
                ("reason", "no_relation_capture"),
                ("as_of_event", None),
            )
        )
    at_or_before = sorted(
        (row for row in applicable if _row_instant(row) <= cutoff),
        key=lambda row: (row.get("sequence") or 0, _row_instant(row)),
    )
    active = []
    last_event_id = None
    for row in at_or_before:
        target = (row["payload"].get("target") or [None])[0]
        if target is None:
            continue
        if row["event"] == "relation_added" and target not in active:
            active.append(target)
        elif row["event"] == "relation_removed" and target in active:
            active.remove(target)
        last_event_id = row["record_id"] or None
    return OrderedDict(
        (
            ("state", _known_state(complete)),
            ("values", active),
            ("reason", None),
            ("as_of_event", last_event_id),
        )
    )


def _project_uncaptured_schedule_field(field):
    return OrderedDict(
        (
            ("state", "unavailable"),
            ("value", None),
            ("reason", "no_schedule_changed_capture"),
            ("as_of_event", None),
        )
    )


def semantic_as_of(items, target_id, cutoff, id_key="id"):
    """Reconstruct known/partial/unavailable field state at ``cutoff``.

    ``cutoff`` may be a pre-parsed timezone-aware ``datetime`` or a raw
    string, in which case it is parsed with the shared
    :func:`lifetxt.historical_temporal.parse_cutoff`.
    """
    if isinstance(cutoff, str):
        cutoff = parse_cutoff(cutoff)
    if cutoff.tzinfo is None or cutoff.utcoffset() is None:
        raise ValueError("--as-of must be offset-aware.")

    timeline = native_timeline(
        items,
        target_id,
        id_key=id_key,
        limit=MAX_LIMIT,
        include_all_valid=True,
    )
    events = timeline.get("_all_valid_events", timeline["events"])
    item_completeness = timeline["completeness"].get("item", {})
    complete = bool(item_completeness.get("complete"))

    fields = OrderedDict()
    fields["status"] = _project_status(events, cutoff, complete)
    fields["due"] = _project_due(events, cutoff, complete)
    for relation in RELATION_FIELDS:
        fields[relation] = _project_relation(events, cutoff, complete, relation)
    for field in _UNCAPTURED_SCHEDULE_FIELDS:
        fields[field] = _project_uncaptured_schedule_field(field)

    as_of_text = cutoff.isoformat()
    if as_of_text.endswith("+00:00"):
        as_of_text = as_of_text[: -len("+00:00")] + "Z"

    return OrderedDict(
        (
            ("schema", SCHEMA),
            ("target_id", str(target_id)),
            ("as_of", as_of_text),
            ("source", "native_life_txt"),
            ("git_composed", False),
            ("fields", fields),
        )
    )
