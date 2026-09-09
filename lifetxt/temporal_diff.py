"""Deterministic semantic comparison of two temporal-thread read models."""

from __future__ import unicode_literals

import json
from collections import OrderedDict


STABLE_ITEM_FIELDS = ("status", "kind", "title")


def _item_value(item):
    return OrderedDict(
        (name, item.get(name)) for name in ("id", "title", "kind", "status")
    )


def _edge_value(edge):
    return OrderedDict(
        (name, edge.get(name)) for name in ("relation", "source_id", "target_id")
    )


def _warning_value(warning):
    return OrderedDict(
        (
            ("relation", warning.get("relation")),
            ("source_id", warning.get("source_id")),
            ("target_id", warning.get("target_id")),
            ("reason", warning.get("reason")),
            ("observed_order", warning.get("observed_order")),
            ("expected_order", warning.get("expected_order")),
            ("evidence", warning.get("evidence")),
            ("provenance", warning.get("provenance")),
        )
    )


def _warning_identity(warning):
    return OrderedDict(
        (name, warning.get(name))
        for name in ("relation", "source_id", "target_id", "reason")
    )


def _derived_edge_value(edge):
    return OrderedDict(
        (name, edge.get(name))
        for name in (
            "relation",
            "rule",
            "source_field",
            "target_field",
            "days",
            "target_id",
        )
    )


def _fact_value(fact):
    return OrderedDict(
        (name, value) for name, value in fact.items() if name != "reference_time"
    )


def _identity(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _set_diff(before, after, normalize, identity=None):
    identity = identity or normalize
    left = {_identity(identity(value)): normalize(value) for value in before}
    right = {_identity(identity(value)): normalize(value) for value in after}
    added = [right[key] for key in sorted(set(right) - set(left))]
    removed = [left[key] for key in sorted(set(left) - set(right))]
    return added, removed, len(set(left) & set(right))


def _thread_section(thread, section, key):
    if thread is None:
        return []
    return thread[section][key]


def temporal_diff(from_thread, to_thread, from_metadata, to_metadata, target_id):
    """Compare normalized thread semantics, ignoring serialization order."""
    before_nodes = _thread_section(from_thread, "explicit", "nodes")
    after_nodes = _thread_section(to_thread, "explicit", "nodes")
    before_by_id = {item["id"]: _item_value(item) for item in before_nodes}
    after_by_id = {item["id"]: _item_value(item) for item in after_nodes}
    added_ids = sorted(set(after_by_id) - set(before_by_id))
    removed_ids = sorted(set(before_by_id) - set(after_by_id))
    changed = []
    for item_id in sorted(set(before_by_id) & set(after_by_id)):
        changes = OrderedDict()
        for field in STABLE_ITEM_FIELDS:
            before = before_by_id[item_id].get(field)
            after = after_by_id[item_id].get(field)
            if before != after:
                changes[field] = OrderedDict((("from", before), ("to", after)))
        if changes:
            changed.append(OrderedDict((("id", item_id), ("changes", changes))))

    added_edges, removed_edges, _unchanged_edges = _set_diff(
        _thread_section(from_thread, "explicit", "edges"),
        _thread_section(to_thread, "explicit", "edges"),
        _edge_value,
    )
    introduced_warnings, resolved_warnings, unchanged_warnings = _set_diff(
        _thread_section(from_thread, "consistency", "warnings"),
        _thread_section(to_thread, "consistency", "warnings"),
        _warning_value,
        _warning_identity,
    )
    before_facts = [] if from_thread is None else from_thread["derived"]["facts"]
    after_facts = [] if to_thread is None else to_thread["derived"]["facts"]
    added_facts, removed_facts, _unchanged_facts = _set_diff(
        before_facts, after_facts, _fact_value
    )
    before_related = [] if from_thread is None else from_thread["derived"]["related"]
    after_related = [] if to_thread is None else to_thread["derived"]["related"]
    added_derived, removed_derived, _unchanged_derived = _set_diff(
        before_related, after_related, _derived_edge_value
    )

    limitations = []
    for label, metadata in (("from", from_metadata), ("to", to_metadata)):
        limitations.extend(
            "%s:%s" % (label, value) for value in metadata.get("limitations", [])
        )
        if not metadata.get("evidence_complete", False):
            limitations.append("%s_evidence_incomplete" % label)
    for label, thread in (("from", from_thread), ("to", to_thread)):
        if thread is None:
            continue
        if thread["explicit"]["truncated"] or thread["consistency"]["truncated"]:
            limitations.append("%s_thread_truncated" % label)
        temporal_limit = thread["bounds"]["temporal_limit"]
        if temporal_limit == 0 or len(thread["derived"]["related"]) >= temporal_limit:
            limitations.append("%s_derived_limit_may_truncate" % label)
    limitations = sorted(set(limitations))

    reference_date = (
        to_thread["reference_date"]
        if to_thread is not None
        else (from_thread["reference_date"] if from_thread is not None else None)
    )
    return OrderedDict(
        (
            ("schema", "temporal-diff-v1"),
            ("reference_date", reference_date),
            ("target_id", str(target_id)),
            (
                "availability",
                OrderedDict(
                    (
                        ("from", from_thread is not None),
                        ("to", to_thread is not None),
                    )
                ),
            ),
            ("from", from_metadata),
            ("to", to_metadata),
            ("complete", not limitations),
            ("limitations", limitations),
            (
                "items",
                OrderedDict(
                    (
                        ("added", [after_by_id[item_id] for item_id in added_ids]),
                        ("removed", [before_by_id[item_id] for item_id in removed_ids]),
                        ("changed", changed),
                    )
                ),
            ),
            (
                "explicit",
                OrderedDict(
                    (("added_edges", added_edges), ("removed_edges", removed_edges))
                ),
            ),
            (
                "consistency",
                OrderedDict(
                    (
                        ("introduced_warnings", introduced_warnings),
                        ("resolved_warnings", resolved_warnings),
                        ("unchanged_warning_count", unchanged_warnings),
                    )
                ),
            ),
            (
                "derived",
                OrderedDict(
                    (
                        ("added_facts", added_facts),
                        ("removed_facts", removed_facts),
                        ("added_edges", added_derived),
                        ("removed_edges", removed_derived),
                    )
                ),
            ),
        )
    )
