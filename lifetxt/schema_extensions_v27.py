"""Historical temporal-thread and semantic temporal-diff schema contracts."""

from __future__ import unicode_literals

from collections import OrderedDict
from copy import deepcopy

from .schema_extensions_v26 import (
    BASE,
    DRAFT,
    NAME as THREAD_NAME,
    temporal_thread_v1_schema,
)


DIFF_NAME = "temporal-diff-v1.schema.json"


def _path_evidence_properties():
    return {
        "requested_paths": {"type": "array", "items": {"type": "string"}},
        "loaded_paths": {"type": "array", "items": {"type": "string"}},
        "missing_paths": {"type": "array", "items": {"type": "string"}},
        "evidence_complete": {"type": "boolean"},
        "limitations": {"type": "array", "items": {"type": "string"}},
    }


def historical_evidence_schema():
    path_fields = [
        "requested_paths",
        "loaded_paths",
        "missing_paths",
        "evidence_complete",
        "limitations",
    ]
    exact_properties = _path_evidence_properties()
    exact_properties.update(
        {
            "mode": {"const": "git_exact_revision"},
            "requested_revision": {"type": "string"},
            "resolved_commit": {
                "type": "string",
                "pattern": "^(?:[0-9a-f]{40}|[0-9a-f]{64})$",
            },
        }
    )
    as_of_properties = _path_evidence_properties()
    as_of_properties.update(
        {
            "mode": {"const": "git_as_of"},
            "cutoff": {"type": "string"},
            "time_policy": {"const": "committer"},
            "requested_ref": {"type": "string"},
            "selection_root": {
                "type": "string",
                "pattern": "^(?:[0-9a-f]{40}|[0-9a-f]{64})$",
            },
            "selected_commit": {
                "type": "string",
                "pattern": "^(?:[0-9a-f]{40}|[0-9a-f]{64})$",
            },
            "selected_committer_time": {"type": "string"},
            "tie_break": {"const": "maximum_full_sha"},
            "history_complete": {"type": "boolean"},
        }
    )
    return {
        "oneOf": [
            {
                "type": "object",
                "required": [
                    "mode",
                    "requested_revision",
                    "resolved_commit",
                ]
                + path_fields,
                "properties": exact_properties,
                "additionalProperties": False,
            },
            {
                "type": "object",
                "required": [
                    "mode",
                    "cutoff",
                    "time_policy",
                    "requested_ref",
                    "selection_root",
                    "selected_commit",
                    "selected_committer_time",
                    "tie_break",
                    "history_complete",
                ]
                + path_fields,
                "properties": as_of_properties,
                "additionalProperties": False,
            },
        ]
    }


def temporal_thread_v1_historical_schema():
    schema = deepcopy(temporal_thread_v1_schema())
    schema["properties"]["historical"] = historical_evidence_schema()
    return schema


def temporal_diff_v1_schema():
    item = {
        "type": "object",
        "required": ["id", "title", "kind", "status"],
        "properties": {
            "id": {"type": "string"},
            "title": {"type": "string"},
            "kind": {"type": "string"},
            "status": {"type": "string"},
        },
        "additionalProperties": False,
    }
    edge = {
        "type": "object",
        "required": ["relation", "source_id", "target_id"],
        "properties": {
            "relation": {"enum": ["follows", "realizes", "replaced_by"]},
            "source_id": {"type": "string"},
            "target_id": {"type": "string"},
        },
        "additionalProperties": False,
    }
    warning = deepcopy(temporal_thread_v1_schema()["$defs"]["consistencyWarning"])
    historical = historical_evidence_schema()["oneOf"][0]
    return {
        "$schema": DRAFT,
        "$id": BASE + DIFF_NAME,
        "title": "lifetxt temporal diff v1",
        "type": "object",
        "$defs": {
            "item": item,
            "edge": edge,
            "warning": warning,
            "historicalExact": historical,
        },
        "required": [
            "schema",
            "reference_date",
            "target_id",
            "availability",
            "from",
            "to",
            "complete",
            "limitations",
            "items",
            "explicit",
            "consistency",
            "derived",
        ],
        "properties": {
            "schema": {"const": "temporal-diff-v1"},
            "reference_date": {"type": ["string", "null"]},
            "target_id": {"type": "string"},
            "availability": {
                "type": "object",
                "required": ["from", "to"],
                "properties": {
                    "from": {"type": "boolean"},
                    "to": {"type": "boolean"},
                },
                "additionalProperties": False,
            },
            "from": {"$ref": "#/$defs/historicalExact"},
            "to": {"$ref": "#/$defs/historicalExact"},
            "complete": {"type": "boolean"},
            "limitations": {"type": "array", "items": {"type": "string"}},
            "items": {
                "type": "object",
                "required": ["added", "removed", "changed"],
                "properties": {
                    "added": {"type": "array", "items": {"$ref": "#/$defs/item"}},
                    "removed": {"type": "array", "items": {"$ref": "#/$defs/item"}},
                    "changed": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "required": ["id", "changes"],
                            "properties": {
                                "id": {"type": "string"},
                                "changes": {
                                    "type": "object",
                                    "additionalProperties": {
                                        "type": "object",
                                        "required": ["from", "to"],
                                        "properties": {
                                            "from": {"type": "string"},
                                            "to": {"type": "string"},
                                        },
                                        "additionalProperties": False,
                                    },
                                },
                            },
                            "additionalProperties": False,
                        },
                    },
                },
                "additionalProperties": False,
            },
            "explicit": {
                "type": "object",
                "required": ["added_edges", "removed_edges"],
                "properties": {
                    "added_edges": {
                        "type": "array",
                        "items": {"$ref": "#/$defs/edge"},
                    },
                    "removed_edges": {
                        "type": "array",
                        "items": {"$ref": "#/$defs/edge"},
                    },
                },
                "additionalProperties": False,
            },
            "consistency": {
                "type": "object",
                "required": [
                    "introduced_warnings",
                    "resolved_warnings",
                    "unchanged_warning_count",
                ],
                "properties": {
                    "introduced_warnings": {
                        "type": "array",
                        "items": {"$ref": "#/$defs/warning"},
                    },
                    "resolved_warnings": {
                        "type": "array",
                        "items": {"$ref": "#/$defs/warning"},
                    },
                    "unchanged_warning_count": {"type": "integer", "minimum": 0},
                },
                "additionalProperties": False,
            },
            "derived": {
                "type": "object",
                "required": [
                    "added_facts",
                    "removed_facts",
                    "added_edges",
                    "removed_edges",
                ],
                "properties": {
                    "added_facts": {"type": "array", "items": {"type": "object"}},
                    "removed_facts": {"type": "array", "items": {"type": "object"}},
                    "added_edges": {"type": "array", "items": {"type": "object"}},
                    "removed_edges": {"type": "array", "items": {"type": "object"}},
                },
                "additionalProperties": False,
            },
        },
        "additionalProperties": False,
    }


def temporal_diff_v1_sample():
    commit_a = "1" * 40
    commit_b = "2" * 40

    def evidence(commit):
        return OrderedDict(
            (
                ("mode", "git_exact_revision"),
                ("requested_revision", commit),
                ("resolved_commit", commit),
                ("requested_paths", ["life.txt"]),
                ("loaded_paths", ["life.txt"]),
                ("missing_paths", []),
                ("evidence_complete", True),
                ("limitations", []),
            )
        )

    return OrderedDict(
        (
            ("schema", "temporal-diff-v1"),
            ("reference_date", "2026-09-09"),
            ("target_id", "visit"),
            ("availability", OrderedDict((("from", True), ("to", True)))),
            ("from", evidence(commit_a)),
            ("to", evidence(commit_b)),
            ("complete", True),
            ("limitations", []),
            (
                "items",
                OrderedDict((("added", []), ("removed", []), ("changed", []))),
            ),
            (
                "explicit",
                OrderedDict((("added_edges", []), ("removed_edges", []))),
            ),
            (
                "consistency",
                OrderedDict(
                    (
                        ("introduced_warnings", []),
                        ("resolved_warnings", []),
                        ("unchanged_warning_count", 0),
                    )
                ),
            ),
            (
                "derived",
                OrderedDict(
                    (
                        ("added_facts", []),
                        ("removed_facts", []),
                        ("added_edges", []),
                        ("removed_edges", []),
                    )
                ),
            ),
        )
    )


def install_schema_extensions_v27():
    from . import release_policy, safety_foundation

    if getattr(release_policy, "_lifetxt_schema_extensions_v27", False):
        return
    old_bundle = safety_foundation.schema_bundle
    old_samples = release_policy._schema_samples

    def bundle():
        result = OrderedDict(old_bundle())
        result[THREAD_NAME] = temporal_thread_v1_historical_schema()
        result[DIFF_NAME] = temporal_diff_v1_schema()
        return result

    def samples():
        result = OrderedDict(old_samples())
        result[DIFF_NAME] = temporal_diff_v1_sample()
        return result

    safety_foundation.schema_bundle = bundle
    release_policy.schema_bundle = bundle
    release_policy._schema_samples = samples
    release_policy._lifetxt_schema_extensions_v27 = True
