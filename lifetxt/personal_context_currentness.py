"""Deterministic Personal Context currentness resolver.

Classifies Personal AI Memory records (or any item carrying the same
``corrects:``/``replaced_by:`` supersession conventions) into one of seven
derived *read* states without deleting history and without introducing
mandatory Format metadata:

- ``current``
- ``future-effective``
- ``stale``
- ``superseded``
- ``expired``
- ``conflicting``
- ``historical-only``

These are read states computed at query time, never persisted status
fields. The resolver reuses existing foundations rather than building a
parallel clock/history model:

- staleness reuses :func:`lifetxt.temporal_context.node_facts`'s existing
  ``stale_since`` rule (via ``updated:``/``reference_time``);
- ``valid_from:``/``valid_to:`` are optional custom-detail conventions
  parsed with the existing :mod:`lifetxt.timeutil` date/datetime parser --
  no second timestamp parser or policy is introduced;
- supersession reuses the existing Personal Context correction evidence
  (``corrects:<id>``) and the existing lifecycle replacement relation
  (``replaced_by:``) without changing either storage convention.

Resolution precedence (first match wins):

1. malformed validity evidence, a supersession cycle, or competing
   replacement ambiguity -> ``conflicting``
2. a unique superseding replacement exists -> ``superseded``
3. ``valid_from`` is later than the evaluation time -> ``future-effective``
4. ``valid_to`` is earlier than the evaluation time -> ``expired``
5. explicitly historical-only input/context -> ``historical-only``
6. the existing temporal staleness rule reports stale -> ``stale``
7. otherwise -> ``current``
"""

from __future__ import unicode_literals

from collections import OrderedDict

from .temporal_context import DEFAULT_STALE_DAYS, node_facts
from .timeutil import parse_date_or_datetime
from .timezone_policy import now as timezone_now
from .personal_context_review_policy import effective_review_policy


CORRECTS_KEY = "corrects"
REPLACED_BY_KEY = "replaced_by"

STATE_CONFLICTING = "conflicting"
STATE_SUPERSEDED = "superseded"
STATE_FUTURE_EFFECTIVE = "future-effective"
STATE_EXPIRED = "expired"
STATE_HISTORICAL_ONLY = "historical-only"
STATE_STALE = "stale"
STATE_CURRENT = "current"

#: Every state a Personal Context record can resolve to. ``current`` is the
#: only state ordinary retrieval should treat as usable-now truth.
ALL_STATES = (
    STATE_CURRENT,
    STATE_FUTURE_EFFECTIVE,
    STATE_STALE,
    STATE_SUPERSEDED,
    STATE_EXPIRED,
    STATE_CONFLICTING,
    STATE_HISTORICAL_ONLY,
)


def _values(item, key):
    return [str(value) for value in item.details.get(key, []) if str(value)]


def _first(item, key, default=""):
    values = _values(item, key)
    return values[0] if values else default


def _item_id(item, key="id"):
    return _first(item, key)


def _identity(item, key="id"):
    item_id = _item_id(item, key=key)
    if item_id:
        return item_id
    source = getattr(item, "source", None) or "?"
    line = getattr(item, "line", None)
    return "%s:%s" % (source, line if line is not None else "?")


def parse_validity_bounds(item):
    """Return ``(valid_from, valid_to, malformed)`` for one item.

    Reuses :func:`lifetxt.timeutil.parse_date_or_datetime` -- the same
    parser used across this codebase's date-range handling -- rather than
    introducing a second timestamp parser. A present-but-unparsable value,
    or a ``valid_from`` later than ``valid_to``, is reported as malformed
    rather than silently treated as an absent bound.
    """
    malformed = False
    raw_from = _first(item, "valid_from") or None
    raw_to = _first(item, "valid_to") or None
    valid_from = None
    valid_to = None
    if raw_from is not None:
        valid_from = parse_date_or_datetime(raw_from, is_end=False)
        if valid_from is None:
            malformed = True
    if raw_to is not None:
        valid_to = parse_date_or_datetime(raw_to, is_end=True)
        if valid_to is None:
            malformed = True
    if valid_from is not None and valid_to is not None and valid_from > valid_to:
        malformed = True
    return valid_from, valid_to, malformed


def _supersession_edges(items, key="id"):
    """Map an item id to the set of ids that directly supersede it.

    Both ``corrects:<target>`` (the correcting record points back at the
    old target) and ``<old>`` carrying ``replaced_by:<new>`` are normalized
    into the same directed ``old -> new`` edge shape. Neither storage
    convention is changed.
    """
    edges = {}
    for item in items:
        item_id = _item_id(item, key=key)
        if not item_id:
            continue
        for target_id in _values(item, CORRECTS_KEY):
            edges.setdefault(target_id, set()).add(item_id)
        for successor_id in _values(item, REPLACED_BY_KEY):
            edges.setdefault(item_id, set()).add(successor_id)
    return edges


def _cycle_members(edges):
    """Return the set of node ids participating in a supersession cycle."""
    WHITE, GRAY, BLACK = 0, 1, 2
    color = {}
    in_cycle = set()
    stack_path = []

    all_nodes = set(edges.keys())
    for successors in edges.values():
        all_nodes.update(successors)

    def visit(node):
        color[node] = GRAY
        stack_path.append(node)
        for neighbor in edges.get(node, ()):
            state = color.get(neighbor, WHITE)
            if state == WHITE:
                visit(neighbor)
            elif state == GRAY:
                idx = stack_path.index(neighbor)
                in_cycle.update(stack_path[idx:])
        stack_path.pop()
        color[node] = BLACK

    for node in sorted(all_nodes):
        if color.get(node, WHITE) == WHITE:
            visit(node)
    return in_cycle


def _stale_fact(item, stale_after_days=DEFAULT_STALE_DAYS):
    for fact in node_facts(item, None, stale_after_days=stale_after_days):
        if fact.get("rule") == "stale_since":
            return fact
    return None


def resolve_currentness(
    items,
    key="id",
    evaluation_time=None,
    stale_after_days=DEFAULT_STALE_DAYS,
    historical_ids=None,
    tag_policies=None,
    apply_review_policy=True,
):
    """Classify every item's Personal Context currentness state.

    Domain-neutral and bounded: it composes existing temporal/link
    foundations over whatever ``items`` it is given -- callers filter to
    Personal Context records themselves (see
    :func:`lifetxt.personal_context.select_personal_context`).

    Returns an :class:`OrderedDict` keyed by item identity (the item's
    ``key`` value, falling back to ``source:line`` when absent) mapping to
    a record with ``id``, ``state``, ``reasons``, ``valid_from``, and
    ``valid_to``.
    """
    evaluation_time = evaluation_time or timezone_now()
    historical_ids = {str(value) for value in (historical_ids or ())}

    edges = _supersession_edges(items, key=key)
    cycle_members = _cycle_members(edges)
    ambiguous_targets = set()
    for successors in edges.values():
        if len(successors) > 1:
            ambiguous_targets.update(successors)

    results = OrderedDict()
    for item in items:
        item_id = _item_id(item, key=key)
        identity = _identity(item, key=key)
        valid_from, valid_to, malformed = parse_validity_bounds(item)
        successors = edges.get(item_id, set()) if item_id else set()
        policy = effective_review_policy(item, stale_after_days, tag_policies)
        if not apply_review_policy:
            policy = {"mode": "periodic", "days": int(stale_after_days),
                      "source": "historical_periodic_fallback", "diagnostics": []}
        raw_stale = _stale_fact(item, stale_after_days=stale_after_days)
        effective_stale = (
            _stale_fact(item, stale_after_days=policy["days"])
            if policy["mode"] == "periodic" else None
        )

        reasons = []
        state = None

        if item_id and item_id in cycle_members:
            state = STATE_CONFLICTING
            reasons.append("supersession_cycle")
        elif malformed:
            state = STATE_CONFLICTING
            reasons.append("malformed_validity_range")
        elif len(successors) > 1:
            state = STATE_CONFLICTING
            reasons.append("competing_replacements:%s" % ",".join(sorted(successors)))
        elif item_id and item_id in ambiguous_targets:
            state = STATE_CONFLICTING
            reasons.append("competing_replacement_candidate")
        elif len(successors) == 1:
            state = STATE_SUPERSEDED
            reasons.append("superseded_by:%s" % next(iter(successors)))
        elif valid_from is not None and valid_from > evaluation_time:
            state = STATE_FUTURE_EFFECTIVE
            reasons.append("valid_from_in_future")
        elif valid_to is not None and valid_to < evaluation_time:
            state = STATE_EXPIRED
            reasons.append("valid_to_in_past")
        elif item_id and item_id in historical_ids:
            state = STATE_HISTORICAL_ONLY
            reasons.append("explicit_historical_context")
        else:
            if effective_stale is not None:
                state = STATE_STALE
                reasons.append("stale_since")
            else:
                state = STATE_CURRENT

        results[identity] = OrderedDict(
            (
                ("id", item_id or None),
                ("state", state),
                ("review_policy", policy),
                ("review_due", state == STATE_STALE),
                ("raw_stale_fact", raw_stale),
                ("reasons", reasons),
                (
                    "valid_from",
                    valid_from.isoformat() if valid_from is not None else None,
                ),
                (
                    "valid_to",
                    valid_to.isoformat() if valid_to is not None else None,
                ),
            )
        )
    return results


def item_currentness(item, states, key="id"):
    """Look up one item's classification from a :func:`resolve_currentness` map."""
    return states.get(_identity(item, key=key))
