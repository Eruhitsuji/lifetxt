"""Derived, read-only Temporal Context: bounded date-based facts and edges.

Combines lifetxt's existing explicit relation graph inputs (dates already on
items) with time semantics to answer "what is relevant now, before, after,
overdue, or stale?" for one item at a time. Nothing here is persisted back
into life.txt, and nothing here recomputes structural relations
(``depends_on``/``blocks``/... stay in :mod:`lifetxt.links`) -- this module
only derives *temporal* facts from date-bearing details that already exist.

Two kinds of derived fact:

- **node facts** (``overdue_by``/``due_in``/``stale_since``): about the
  target item alone, no second item involved.
- **pairwise edges** (``same_day``/``before``/``after``): between the
  target and another item that shares a comparable date within
  ``window_days``.

Every fact carries ``rule``, ``source_field``, and ``reference_time`` so a
consumer can explain "why" without re-deriving it. The result is always
bounded to one target item's neighborhood -- never an all-pairs scan of the
whole workspace -- by sorting candidates once and taking the nearest
``limit`` within ``window_days``, which stays O(n log n) regardless of how
many items share a date.

An item with no comparable date field simply produces no fact for that
field, matching :mod:`lifetxt.command_center`'s existing guard pattern; no
relation is ever guessed or defaulted. Completed/cancelled items remain
valid input for ``same_day``/``before``/``after`` (pure date ordering, not a
"still relevant" claim), matching how :mod:`lifetxt.query`'s date
comparisons already treat them.
"""

from __future__ import unicode_literals

from collections import OrderedDict

from .ticket_project_values import DEFAULT_STALE_DAYS, last_activity, reference_time
from .timeutil import parse_date_or_datetime


#: Detail keys considered as an item's own comparable "when" date, in
#: priority order. Matches the fields lifetxt.command_center and
#: lifetxt.agenda already treat as an item's primary date.
DATE_KEYS = ("due", "do", "on", "from")

DEFAULT_WINDOW_DAYS = 7
DEFAULT_PAIR_LIMIT = 20


def _first(item, key):
    values = item.details.get(key)
    return values[0] if values else None


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


def _item_date(item):
    for detail_key in DATE_KEYS:
        date = _date_of(_first(item, detail_key))
        if date is not None:
            return date, detail_key
    return None, None


def _ref(item):
    return OrderedDict(
        (
            ("title", item.title),
            ("kind", item.kind),
            ("status", item.status),
            ("source", item.source),
            ("line", item.line),
        )
    )


def _item_id(item, key):
    values = item.details.get(key)
    return str(values[0]) if values else None


def _fact(rule, source_field, reference_time_value, **extra):
    fact = OrderedDict(
        (
            ("rule", rule),
            ("source_field", source_field),
            (
                "reference_time",
                reference_time_value.isoformat()
                if hasattr(reference_time_value, "isoformat")
                else str(reference_time_value),
            ),
        )
    )
    for name, value in extra.items():
        fact[name] = value
    return fact


def node_facts(item, today, stale_after_days=DEFAULT_STALE_DAYS):
    """Node-level derived facts for one item: overdue_by / due_in / stale_since.

    Reuses the exact due-date resolution :mod:`lifetxt.command_center`
    already uses and the exact staleness formula
    :mod:`lifetxt.ticket_project_report` already uses (generalized beyond
    tickets, since ``last_activity``/``reference_time`` read details from
    any item shape, not only ticket records).
    """
    facts = []
    due = _date_of(_first(item, "due"))
    if due is not None and today is not None:
        delta_days = (today - due).days
        if delta_days > 0:
            facts.append(_fact("overdue_by", "due", today, days=delta_days))
        else:
            facts.append(_fact("due_in", "due", today, days=-delta_days))
    activity = last_activity(item)
    if activity is not None:
        now = reference_time(None)
        age_days = (now - activity).days
        if age_days > stale_after_days:
            facts.append(
                _fact(
                    "stale_since",
                    "updated",
                    now,
                    days=age_days,
                    threshold_days=stale_after_days,
                )
            )
    return facts


def temporal_context(
    items,
    target,
    today,
    key="id",
    window_days=DEFAULT_WINDOW_DAYS,
    limit=DEFAULT_PAIR_LIMIT,
    stale_after_days=DEFAULT_STALE_DAYS,
):
    """Bounded temporal context for one ``target`` item.

    Returns node-level facts about ``target`` plus the nearest ``limit``
    other items whose own comparable date falls within ``window_days`` of
    the target's date, each as a ``same_day``/``before``/``after`` edge.
    When the target has no comparable date, ``related`` is empty -- no
    proximity can be derived without a date to compare against.
    """
    facts = node_facts(target, today, stale_after_days=stale_after_days)
    target_date, target_field = _item_date(target)

    candidates = []
    if target_date is not None:
        for other in items:
            if other is target:
                continue
            other_date, other_field = _item_date(other)
            if other_date is None:
                continue
            delta_days = (other_date - target_date).days
            if abs(delta_days) > window_days:
                continue
            candidates.append((abs(delta_days), other, other_field, delta_days))
        candidates.sort(key=lambda entry: (entry[0], entry[1].line or 0))

    related = []
    for _distance, other, other_field, delta_days in candidates[:limit]:
        relation = (
            "same_day" if delta_days == 0 else ("after" if delta_days > 0 else "before")
        )
        related.append(
            OrderedDict(
                (
                    ("relation", relation),
                    ("rule", relation),
                    ("source_field", target_field),
                    ("target_field", other_field),
                    ("reference_time", today.isoformat() if today else None),
                    ("days", abs(delta_days)),
                    ("target_id", _item_id(other, key)),
                    ("target", _ref(other)),
                )
            )
        )

    return OrderedDict(
        (
            ("schema", "temporal-context-v1"),
            ("reference_date", today.isoformat() if today else None),
            ("target_id", _item_id(target, key)),
            ("target", _ref(target)),
            ("window_days", window_days),
            ("facts", facts),
            ("related", related),
        )
    )
