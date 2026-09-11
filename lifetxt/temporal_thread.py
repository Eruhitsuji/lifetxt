"""Bounded lifecycle thread composed from shared link and temporal engines.

``follows``/``realizes``/``replaced_by`` are authoritative because they are
stored in life.txt. Date-neighbor relations remain derived and read-only in
the embedded ``temporal-context-v1`` result. This module never converts one
kind into the other.
"""

from __future__ import unicode_literals

from collections import Counter, OrderedDict, deque

from .links import build_id_index, link_records, relation_cycle_paths
from .temporal_context import (
    DEFAULT_PAIR_LIMIT,
    DEFAULT_STALE_DAYS,
    DEFAULT_WINDOW_DAYS,
    comparable_time_evidence,
    temporal_context,
)


EXPLICIT_RELATIONS = ("follows", "realizes", "replaced_by")
DEFAULT_MAX_DEPTH = 8
DEFAULT_MAX_NODES = 50
HARD_MAX_DEPTH = 32
HARD_MAX_NODES = 500
HARD_TEMPORAL_LIMIT = 500
CONSISTENCY_RELATIONS = ("follows", "replaced_by")
CONSISTENCY_REASON = "explicit_order_conflicts_with_time_order"


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


def _consistency_warning(record, index):
    relation = record["relation"]
    if relation not in CONSISTENCY_RELATIONS:
        return None
    source_id = record["source_id"]
    target_id = record["target_id"]
    source_matches = index.get(source_id, [])
    target_matches = index.get(target_id, [])
    if len(source_matches) != 1 or len(target_matches) != 1:
        return None

    source_evidence = comparable_time_evidence(source_matches[0])
    target_evidence = comparable_time_evidence(target_matches[0])
    if source_evidence is None or target_evidence is None:
        return None

    if relation == "follows":
        successor_id = source_id
        successor_evidence = source_evidence
        predecessor_id = target_id
        predecessor_evidence = target_evidence
    else:
        successor_id = target_id
        successor_evidence = target_evidence
        predecessor_id = source_id
        predecessor_evidence = source_evidence

    if successor_evidence["date"] >= predecessor_evidence["date"]:
        return None

    return OrderedDict(
        (
            ("relation", relation),
            ("source_id", source_id),
            ("target_id", target_id),
            ("reason", CONSISTENCY_REASON),
            ("observed_order", "before"),
            ("expected_order", "after"),
            (
                "evidence",
                OrderedDict(
                    (
                        ("source_field", source_evidence["field"]),
                        ("source_value", source_evidence["value"]),
                        ("target_field", target_evidence["field"]),
                        ("target_value", target_evidence["value"]),
                        ("successor_id", successor_id),
                        ("predecessor_id", predecessor_id),
                    )
                ),
            ),
            (
                "provenance",
                OrderedDict(
                    (
                        (
                            "explicit",
                            OrderedDict(
                                (
                                    ("kind", "explicit"),
                                    ("authority", "life.txt"),
                                    ("source_field", relation),
                                    ("source", record.get("source_location")),
                                )
                            ),
                        ),
                        (
                            "temporal",
                            OrderedDict(
                                (
                                    ("kind", "derived"),
                                    ("authority", "temporal-context-v1"),
                                    ("rule", "before"),
                                    ("granularity", "date"),
                                )
                            ),
                        ),
                    )
                ),
            ),
        )
    )


def temporal_consistency(items, key="id", records=None, limit=None):
    """Return read-only contradictions between explicit and temporal order.

    Only resolved ``follows`` and ``replaced_by`` edges participate. The
    result never mutates or reverses authoritative relations, and absence of
    comparable evidence produces no warning rather than a guessed result.
    """
    index = build_id_index(items, key)
    if records is None:
        records = link_records(items, key=key, relations=CONSISTENCY_RELATIONS)
    warnings = []
    for record in records:
        if record.get("status") != "ok":
            continue
        warning = _consistency_warning(record, index)
        if warning is not None:
            warnings.append(warning)
    truncated = limit is not None and len(warnings) > limit
    if limit is not None:
        warnings = warnings[:limit]
    return OrderedDict((("warnings", warnings), ("truncated", truncated)))


def temporal_thread_metrics(thread):
    """Summarize only the bounded explicit graph already present in a thread."""
    nodes = thread.get("explicit", {}).get("nodes", [])
    edges = thread.get("explicit", {}).get("edges", [])
    follows = [edge for edge in edges if edge.get("relation") == "follows"]
    outgoing, incoming = {}, {}
    for edge in follows:
        outgoing.setdefault(edge["source_id"], []).append(edge["target_id"])
        incoming.setdefault(edge["target_id"], []).append(edge["source_id"])
    depths = {thread.get("target_id"): 0}
    queue = deque([thread.get("target_id")])
    while queue:
        current = queue.popleft()
        for neighbor in outgoing.get(current, []) + incoming.get(current, []):
            if neighbor not in depths:
                depths[neighbor] = depths[current] + 1
                queue.append(neighbor)
    branch_points = sorted({node for node, values in outgoing.items() if len(values) > 1})
    merge_points = sorted({node for node, values in incoming.items() if len(values) > 1})
    return OrderedDict((
        ("analysis", "temporal_thread_metrics"), ("observed_node_count", len(nodes)),
        ("observed_edge_count", len(edges)),
        ("edge_counts", OrderedDict((relation, sum(e.get("relation") == relation for e in edges)) for relation in EXPLICIT_RELATIONS)),
        ("predecessor_count", len(thread.get("relations", {}).get("predecessors", []))),
        ("successor_count", len(thread.get("relations", {}).get("successors", []))),
        ("max_follows_depth", max(depths.values()) if depths else 0),
        ("branch_points", branch_points),
        ("branch_point_count", len(branch_points)),
        ("merge_points", merge_points),
        ("merge_point_count", len(merge_points)),
        ("truncated", bool(thread.get("explicit", {}).get("truncated"))),
        ("limitations", ["bounded_graph_truncated"] if thread.get("explicit", {}).get("truncated") else []),
    ))


def replacement_chain_analysis(thread):
    relations = thread.get("relations", {})
    predecessors = relations.get("replacement_predecessors", [])
    successors = relations.get("replacement_successors", [])
    edges = [edge for edge in thread.get("explicit", {}).get("edges", []) if edge.get("relation") == "replaced_by"]
    forward = {}
    backward = {}
    for edge in edges:
        forward.setdefault(edge["source_id"], []).append(edge["target_id"])
        backward.setdefault(edge["target_id"], []).append(edge["source_id"])
    target = thread.get("target_id")
    observed = {target}
    for direction in (forward, backward):
        current, seen = [target], set()
        while current:
            node = current.pop(0)
            if node in seen:
                continue
            seen.add(node)
            for neighbor in direction.get(node, []):
                observed.add(neighbor)
                current.append(neighbor)
    endpoints = [row.get("id") for row in predecessors + successors if row.get("id")]
    limitations = ["bounded_graph_truncated"] if thread.get("explicit", {}).get("truncated") else []
    if thread.get("explicit", {}).get("cycles"): limitations.append("replacement_cycle_detected")
    predecessor_ids = sorted(row.get("id") for row in predecessors)
    successor_ids = sorted(row.get("id") for row in successors)
    def endpoint(mapping):
        current, seen = target, set()
        while current not in seen and mapping.get(current):
            seen.add(current)
            current = mapping[current][0]
        return current
    oldest_endpoint = endpoint(backward)
    newest_endpoint = endpoint(forward)
    return OrderedDict((("analysis", "replacement_chain"), ("predecessor_count", len(predecessors)), ("successor_count", len(successors)), ("observed_chain_length", len(observed)), ("observed_item_ids", sorted(observed)), ("predecessor_ids", predecessor_ids), ("successor_ids", successor_ids), ("oldest_endpoint_id", oldest_endpoint), ("newest_endpoint_id", newest_endpoint), ("limitations", limitations)))


def temporal_consistency_summary(thread):
    """Aggregate existing warnings without creating additional consistency rules."""
    warnings = thread.get("consistency", {}).get("warnings", [])
    by_relation = Counter(row.get("relation", "unknown") for row in warnings)
    by_source = Counter(row.get("source_id", "unknown") for row in warnings)
    by_target = Counter(row.get("target_id", "unknown") for row in warnings)
    timestamps = [row.get("evidence", {}).get("source_value") for row in warnings if row.get("evidence", {}).get("source_value")]
    def timestamp_key(value):
        from .timeutil import parse_iso_date, parse_iso_datetime
        instant = parse_iso_datetime(value)
        if instant is not None:
            return (0, instant.date().toordinal())
        date = parse_iso_date(value)
        if date is not None:
            return (0, date.toordinal())
        return (2, str(value))
    ordered_timestamps = sorted(timestamps, key=timestamp_key)
    truncated = bool(thread.get("consistency", {}).get("truncated"))
    return OrderedDict((("analysis", "temporal_consistency_summary"), ("warning_count", len(warnings)), ("by_relation", OrderedDict((key, by_relation[key]) for key in sorted(by_relation))), ("by_source_id", OrderedDict((key, by_source[key]) for key in sorted(by_source))), ("by_target_id", OrderedDict((key, by_target[key]) for key in sorted(by_target))), ("earliest_evidence", ordered_timestamps[0] if ordered_timestamps else None), ("latest_evidence", ordered_timestamps[-1] if ordered_timestamps else None), ("warnings", warnings), ("truncated", truncated), ("limitations", ["consistency_warnings_truncated"] if truncated else [])))


def realization_timing_analysis(items, thread, key="id"):
    """Compare explicit realizes pairs using canonical temporal evidence only."""
    index = build_id_index(items, key)
    rows = []
    for ref in thread.get("relations", {}).get("realized_plans", []):
        plan_id = ref.get("id")
        actual_id = thread.get("target_id")
        plan = index.get(plan_id, [])
        actual = index.get(actual_id, [])
        plan_evidence = comparable_time_evidence(plan[0]) if len(plan) == 1 else None
        actual_evidence = comparable_time_evidence(actual[0]) if len(actual) == 1 else None
        row = OrderedDict((("plan_id", plan_id), ("actual_id", actual_id), ("plan_evidence", plan_evidence), ("actual_evidence", actual_evidence)))
        if plan_evidence and actual_evidence and plan_evidence.get("date") and actual_evidence.get("date"):
            row["classification"] = "before_plan_time" if actual_evidence["date"] < plan_evidence["date"] else "after_plan_time" if actual_evidence["date"] > plan_evidence["date"] else "same_time_or_day"
            row["delta_days"] = (actual_evidence["date"] - plan_evidence["date"]).days
        else:
            row["classification"] = "incomparable"
            row["delta_days"] = None
        rows.append(row)
    return OrderedDict((("analysis", "realizes_timing"), ("results", rows), ("limitations", ["incomparable_evidence"] if any(row["classification"] == "incomparable" for row in rows) else [])))


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

    visible_records = [
        record
        for record in raw
        if record["source_id"] in visible and record["target_id"] in visible
    ]
    consistency = temporal_consistency(
        items, key=key, records=visible_records, limit=max_nodes
    )
    consistency["truncated"] = consistency["truncated"] or truncated

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
            ("consistency", consistency),
            ("derived", derived),
        )
    )
