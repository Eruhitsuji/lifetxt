"""Bounded lifecycle thread composed from shared link and temporal engines.

``follows``/``realizes``/``replaced_by`` are authoritative because they are
stored in life.txt. Date-neighbor relations remain derived and read-only in
the embedded ``temporal-context-v1`` result. This module never converts one
kind into the other.
"""

from __future__ import unicode_literals

from collections import OrderedDict, deque

from .links import build_id_index, link_records, relation_cycle_paths
from .temporal_context import (
    DEFAULT_PAIR_LIMIT,
    DEFAULT_STALE_DAYS,
    DEFAULT_WINDOW_DAYS,
    temporal_context,
)


EXPLICIT_RELATIONS = ("follows", "realizes", "replaced_by")
DEFAULT_MAX_DEPTH = 8
DEFAULT_MAX_NODES = 50
HARD_MAX_DEPTH = 32
HARD_MAX_NODES = 500
HARD_TEMPORAL_LIMIT = 500


def _bounded(value, name, default, hard_max):
    if value is None:
        value = default
    try:
        value = int(value)
    except (TypeError, ValueError):
        raise ValueError("%s must be an integer." % name)
    if value < 0:
        raise ValueError("%s must be zero or greater." % name)
    return min(value, hard_max)


def _item_ref(item, item_id):
    return OrderedDict(
        (
            ("id", item_id),
            ("title", item.title),
            ("kind", item.kind),
            ("status", item.status),
            ("source", item.source),
            ("line", item.line),
        )
    )


def _edge(record):
    return OrderedDict(
        (
            ("relation", record["relation"]),
            ("source_id", record["source_id"]),
            ("target_id", record["target_id"]),
            (
                "provenance",
                OrderedDict(
                    (
                        ("kind", "explicit"),
                        ("authority", "life.txt"),
                        ("source_field", record["relation"]),
                        ("source", record.get("source_location")),
                    )
                ),
            ),
        )
    )


def _relation_ref(record, other_id, item):
    result = _item_ref(item, other_id)
    result["provenance"] = OrderedDict(
        (
            ("kind", "explicit"),
            ("authority", "life.txt"),
            ("source_field", record["relation"]),
            ("source", record.get("source_location")),
        )
    )
    return result


def temporal_thread(
    items,
    target,
    today,
    key="id",
    max_depth=DEFAULT_MAX_DEPTH,
    max_nodes=DEFAULT_MAX_NODES,
    window_days=DEFAULT_WINDOW_DAYS,
    temporal_limit=DEFAULT_PAIR_LIMIT,
    stale_after_days=DEFAULT_STALE_DAYS,
):
    """Return one deterministic, bounded lifecycle neighborhood."""
    max_depth = _bounded(max_depth, "max_depth", DEFAULT_MAX_DEPTH, HARD_MAX_DEPTH)
    max_nodes = _bounded(max_nodes, "max_nodes", DEFAULT_MAX_NODES, HARD_MAX_NODES)
    if max_nodes == 0:
        raise ValueError("max_nodes must be one or greater.")
    window_days = _bounded(window_days, "window_days", DEFAULT_WINDOW_DAYS, 36500)
    temporal_limit = _bounded(
        temporal_limit, "temporal_limit", DEFAULT_PAIR_LIMIT, HARD_TEMPORAL_LIMIT
    )
    stale_after_days = _bounded(
        stale_after_days, "stale_after_days", DEFAULT_STALE_DAYS, 36500
    )

    index = build_id_index(items, key)
    duplicate_ids = [item_id for item_id, matches in index.items() if len(matches) > 1]
    if duplicate_ids:
        raise ValueError(
            "Temporal thread requires unique %s values; duplicate: %s."
            % (key, ", ".join(duplicate_ids))
        )
    target_values = [str(value) for value in target.details.get(key, []) if value]
    target_id = target_values[0] if target_values else None
    if not target_id or len(index.get(target_id, [])) != 1:
        raise ValueError("Temporal thread target must have one unique %s value." % key)

    raw = [
        record
        for record in link_records(items, key=key, relations=EXPLICIT_RELATIONS)
        if record["status"] == "ok" and record["source_id"]
    ]
    raw.sort(
        key=lambda record: (
            record.get("source_line") or 0,
            record["relation"],
            record["target_id"],
        )
    )
    adjacency = OrderedDict()
    for record in raw:
        adjacency.setdefault(record["source_id"], []).append(record)
        adjacency.setdefault(record["target_id"], []).append(record)

    visible_ids = []
    depths = {target_id: 0}
    queue = deque([target_id])
    truncated = False
    while queue:
        current = queue.popleft()
        if len(visible_ids) >= max_nodes:
            truncated = True
            break
        visible_ids.append(current)
        depth = depths[current]
        neighbors = []
        for record in adjacency.get(current, []):
            neighbor = (
                record["target_id"]
                if record["source_id"] == current
                else record["source_id"]
            )
            neighbors.append(neighbor)
        if depth >= max_depth:
            if any(neighbor not in depths for neighbor in neighbors):
                truncated = True
            continue
        for neighbor in neighbors:
            if neighbor not in depths:
                depths[neighbor] = depth + 1
                queue.append(neighbor)

    visible = set(visible_ids)
    edges = [
        _edge(record)
        for record in raw
        if record["source_id"] in visible and record["target_id"] in visible
    ]
    if any(
        record["source_id"] in visible or record["target_id"] in visible
        for record in raw
        if not (record["source_id"] in visible and record["target_id"] in visible)
    ):
        truncated = True

    relations = OrderedDict(
        (
            ("predecessors", []),
            ("successors", []),
            ("realized_plans", []),
            ("realized_by", []),
            ("replacement_predecessors", []),
            ("replacement_successors", []),
        )
    )
    for record in raw:
        source_id = record["source_id"]
        stored_target_id = record["target_id"]
        if target_id not in (source_id, stored_target_id):
            continue
        other_id = stored_target_id if source_id == target_id else source_id
        other = index[other_id][0]
        relation = record["relation"]
        if relation == "follows":
            group = "predecessors" if source_id == target_id else "successors"
        elif relation == "realizes":
            group = "realized_plans" if source_id == target_id else "realized_by"
        else:
            group = (
                "replacement_successors"
                if source_id == target_id
                else "replacement_predecessors"
            )
        relations[group].append(_relation_ref(record, other_id, other))

    cycles = []
    for cycle in relation_cycle_paths(items, key=key, relations=EXPLICIT_RELATIONS):
        if any(node in visible for node in cycle["path"]):
            cycles.append(cycle)

    derived = temporal_context(
        items,
        target,
        today,
        key=key,
        window_days=window_days,
        limit=temporal_limit,
        stale_after_days=stale_after_days,
    )
    return OrderedDict(
        (
            ("schema", "temporal-thread-v1"),
            ("reference_date", today.isoformat() if today else None),
            ("target_id", target_id),
            ("target", _item_ref(target, target_id)),
            (
                "bounds",
                OrderedDict(
                    (
                        ("max_depth", max_depth),
                        ("max_nodes", max_nodes),
                        ("window_days", window_days),
                        ("temporal_limit", temporal_limit),
                    )
                ),
            ),
            ("relations", relations),
            (
                "explicit",
                OrderedDict(
                    (
                        (
                            "nodes",
                            [
                                _item_ref(index[item_id][0], item_id)
                                for item_id in visible_ids
                                if len(index.get(item_id, [])) == 1
                            ],
                        ),
                        ("edges", edges),
                        ("cycles", cycles),
                        ("truncated", truncated),
                    )
                ),
            ),
            ("derived", derived),
        )
    )
