"""Schema contract for the bounded temporal-thread-v1 lifecycle read model."""

from __future__ import unicode_literals

from collections import OrderedDict

BASE = "https://github.com/Eruhitsuji/lifetxt/raw/main/dist/schemas/"
DRAFT = "https://json-schema.org/draft/2020-12/schema"
NAME = "temporal-thread-v1.schema.json"


def temporal_thread_v1_schema():
    item_ref = {
        "type": "object",
        "required": ["id", "title", "kind", "status", "source", "line"],
        "properties": {
            "id": {"type": "string"},
            "title": {"type": "string"},
            "kind": {"type": "string"},
            "status": {"type": "string"},
            "source": {"type": ["string", "null"]},
            "line": {"type": ["integer", "null"]},
            "provenance": {"type": "object"},
        },
        "additionalProperties": True,
    }
    relation_names = [
        "predecessors",
        "successors",
        "realized_plans",
        "realized_by",
        "replacement_predecessors",
        "replacement_successors",
    ]
    consistency_warning = {
        "type": "object",
        "required": [
            "relation",
            "source_id",
            "target_id",
            "reason",
            "observed_order",
            "expected_order",
            "evidence",
            "provenance",
        ],
        "properties": {
            "relation": {"enum": ["follows", "replaced_by"]},
            "source_id": {"type": "string"},
            "target_id": {"type": "string"},
            "reason": {"const": "explicit_order_conflicts_with_time_order"},
            "observed_order": {"const": "before"},
            "expected_order": {"const": "after"},
            "evidence": {
                "type": "object",
                "required": [
                    "source_field",
                    "source_value",
                    "target_field",
                    "target_value",
                    "successor_id",
                    "predecessor_id",
                ],
                "properties": {
                    "source_field": {"type": "string"},
                    "source_value": {"type": "string"},
                    "target_field": {"type": "string"},
                    "target_value": {"type": "string"},
                    "successor_id": {"type": "string"},
                    "predecessor_id": {"type": "string"},
                },
                "additionalProperties": False,
            },
            "provenance": {
                "type": "object",
                "required": ["explicit", "temporal"],
                "properties": {
                    "explicit": {
                        "type": "object",
                        "required": ["kind", "authority", "source_field", "source"],
                        "properties": {
                            "kind": {"const": "explicit"},
                            "authority": {"const": "life.txt"},
                            "source_field": {"type": "string"},
                            "source": {"type": ["string", "null"]},
                        },
                        "additionalProperties": False,
                    },
                    "temporal": {
                        "type": "object",
                        "required": ["kind", "authority", "rule", "granularity"],
                        "properties": {
                            "kind": {"const": "derived"},
                            "authority": {"const": "temporal-context-v1"},
                            "rule": {"const": "before"},
                            "granularity": {"const": "date"},
                        },
                        "additionalProperties": False,
                    },
                },
                "additionalProperties": False,
            },
        },
        "additionalProperties": False,
    }
    item_ref_use = {"$ref": "#/$defs/itemRef"}
    return {
        "$schema": DRAFT,
        "$id": BASE + NAME,
        "title": "lifetxt temporal thread v1",
        "type": "object",
        "$defs": {"itemRef": item_ref, "consistencyWarning": consistency_warning},
        "required": [
            "schema",
            "reference_date",
            "target_id",
            "target",
            "bounds",
            "relations",
            "explicit",
            "consistency",
            "derived",
        ],
        "properties": {
            "schema": {"const": "temporal-thread-v1"},
            "reference_date": {"type": ["string", "null"]},
            "target_id": {"type": "string"},
            "target": item_ref_use,
            "bounds": {
                "type": "object",
                "required": ["max_depth", "max_nodes", "window_days", "temporal_limit"],
                "properties": {
                    name: {
                        "type": "integer",
                        "minimum": 1 if name == "max_nodes" else 0,
                    }
                    for name in (
                        "max_depth",
                        "max_nodes",
                        "window_days",
                        "temporal_limit",
                    )
                },
                "additionalProperties": False,
            },
            "relations": {
                "type": "object",
                "required": relation_names,
                "properties": {
                    name: {"type": "array", "items": item_ref_use}
                    for name in relation_names
                },
                "additionalProperties": False,
            },
            "explicit": {
                "type": "object",
                "required": ["nodes", "edges", "cycles", "truncated"],
                "properties": {
                    "nodes": {"type": "array", "items": item_ref_use},
                    "edges": {"type": "array", "items": {"type": "object"}},
                    "cycles": {"type": "array", "items": {"type": "object"}},
                    "truncated": {"type": "boolean"},
                },
                "additionalProperties": False,
            },
            "consistency": {
                "type": "object",
                "required": ["warnings", "truncated"],
                "properties": {
                    "warnings": {
                        "type": "array",
                        "items": {"$ref": "#/$defs/consistencyWarning"},
                    },
                    "truncated": {"type": "boolean"},
                },
                "additionalProperties": False,
            },
            "derived": {"type": "object"},
            "revision": {"type": ["string", "null"]},
        },
        "additionalProperties": True,
    }


def temporal_thread_v1_sample():
    from .parser import parse_text
    from .temporal_thread import temporal_thread

    import datetime

    items, _ = parse_text(
        "[ ] E Previous_visit id:previous on:2026-09-10\n"
        "[ ] E Planned_visit id:plan on:2026-09-08\n"
        "[x] E Visit id:actual on:2026-09-01 realizes:plan follows:previous\n"
    )
    result = temporal_thread(items, items[2], datetime.date(2026, 9, 8))
    result["revision"] = (
        "3f1c2b9a4d5e6f708192a3b4c5d6e7f8091a2b3c4d5e6f708192a3b4c5d6e7f8"
    )
    return result


def install_schema_extensions_v26():
    from . import release_policy, safety_foundation

    if getattr(release_policy, "_lifetxt_schema_extensions_v26", False):
        return
    old_bundle = safety_foundation.schema_bundle
    old_samples = release_policy._schema_samples

    def bundle():
        result = OrderedDict(old_bundle())
        result[NAME] = temporal_thread_v1_schema()
        return result

    def samples():
        result = OrderedDict(old_samples())
        result[NAME] = temporal_thread_v1_sample()
        return result

    safety_foundation.schema_bundle = bundle
    release_policy.schema_bundle = bundle
    release_policy._schema_samples = samples
    release_policy._lifetxt_schema_extensions_v26 = True
