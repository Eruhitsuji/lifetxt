"""Deterministic historical Personal Context composition."""

from collections import OrderedDict

from .personal_context import context_capsule, select_personal_context
from .personal_context_currentness import item_currentness, resolve_currentness


def historical_personal_context(items, cutoff, person="self", tags=None, limit=100):
    """Return Personal Context valid at an explicit cutoff, without present fallback."""
    states = resolve_currentness(items, evaluation_time=cutoff)
    selected = []
    wanted = set(str(tag) for tag in (tags or []))
    for item in select_personal_context(items, person=person, tags=tags):
        state = item_currentness(item, states)
        if not state or state["state"] not in ("current", "stale"):
            continue
        selected.append(item)
    capsule = context_capsule(selected, person=person, tags=tags, include_stale=True, limit=limit, evaluation_time=cutoff)
    return OrderedDict((("schema", "historical-personal-context-v1"), ("cutoff", cutoff), ("source", "semantic-as-of+currentness"), ("items", capsule["items"]), ("count", capsule["count"]), ("limitations", [])))
