"""Deterministic historical Personal Context composition."""

from collections import OrderedDict

from .native_semantic_as_of import semantic_as_of
from .personal_context import select_personal_context
from .personal_context_currentness import item_currentness, resolve_currentness


def historical_personal_context(
    items, cutoff, person="self", tags=None, limit=100, id_key="id"
):
    """Return field-level as-of context; unavailable fields never use current values."""
    states = resolve_currentness(items, key=id_key, evaluation_time=cutoff)
    rows = []
    limitations = set()
    for item in select_personal_context(items, person=person, tags=tags):
        ids = [str(value) for value in item.details.get(id_key, [])]
        currentness = item_currentness(item, states, key=id_key)
        state = currentness or {"state": "unavailable", "reasons": ["no_unique_id"]}
        if not ids:
            fields = OrderedDict(
                (
                    (
                        field,
                        OrderedDict(
                            (
                                ("state", "unavailable"),
                                ("value", None),
                                ("reason", "no_unique_id"),
                            )
                        ),
                    )
                    for field in ("status", "due", "do", "on", "at", "from", "to")
                )
            )
            limitations.add("item_without_unique_id")
        else:
            as_of = semantic_as_of(items, ids[0], cutoff, id_key=id_key)
            fields = as_of["fields"]
            if not as_of.get("source"):
                limitations.add("semantic_as_of_source_unavailable")
        rows.append(
            OrderedDict(
                (
                    ("id", ids[0] if ids else None),
                    ("title", item.title),
                    ("fields", fields),
                    ("currentness", state),
                    (
                        "provenance",
                        OrderedDict(
                            (
                                ("source", getattr(item, "source", None)),
                                ("line", getattr(item, "line", None)),
                                ("semantic_as_of", bool(ids)),
                            )
                        ),
                    ),
                )
            )
        )
    rows.sort(key=lambda row: (row["id"] or "", row["title"]))
    truncated = len(rows) > int(limit)
    if truncated:
        limitations.add("item_limit_truncated")
    return OrderedDict(
        (
            ("schema", "historical-personal-context-v1"),
            ("cutoff", cutoff),
            ("source", "semantic-as-of+currentness"),
            ("items", rows[: int(limit)]),
            ("count", min(len(rows), int(limit))),
            (
                "bounds",
                OrderedDict(
                    (
                        ("limit", int(limit)),
                        ("total", len(rows)),
                        ("truncated", truncated),
                    )
                ),
            ),
            ("complete", not limitations),
            ("limitations", sorted(limitations)),
        )
    )
