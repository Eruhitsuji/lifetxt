"""Schema contract for the derived, read-only temporal-context-v1 result.

See :mod:`lifetxt.temporal_context` for the producer (``lifetxt temporal
ID``, #481/#485) and the #481 investigation comment for why this is a
separate, bounded contract rather than an extension of ``graph-v1``-shaped
results or ``command-center-v1``.
"""

from __future__ import unicode_literals

from collections import OrderedDict

BASE = "https://github.com/Eruhitsuji/lifetxt/raw/main/dist/schemas/"
DRAFT = "https://json-schema.org/draft/2020-12/schema"
NAME = "temporal-context-v1.schema.json"


def temporal_context_v1_schema():
    ref = {
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "kind": {"type": "string"},
            "status": {"type": "string"},
            "source": {"type": ["string", "null"]},
            "line": {"type": ["integer", "null"]},
        },
        "additionalProperties": True,
    }
    fact = {
        "type": "object",
        "required": ["rule", "source_field", "reference_time"],
        "properties": {
            "rule": {"type": "string"},
            "source_field": {"type": "string"},
            "reference_time": {"type": ["string", "null"]},
            "days": {"type": "integer", "minimum": 0},
            "threshold_days": {"type": "integer", "minimum": 0},
        },
        "additionalProperties": True,
    }
    edge = {
        "type": "object",
        "required": [
            "relation",
            "rule",
            "source_field",
            "target_field",
            "days",
            "target",
        ],
        "properties": {
            "relation": {"enum": ["same_day", "before", "after"]},
            "rule": {"type": "string"},
            "source_field": {"type": ["string", "null"]},
            "target_field": {"type": ["string", "null"]},
            "reference_time": {"type": ["string", "null"]},
            "days": {"type": "integer", "minimum": 0},
            "target_id": {"type": ["string", "null"]},
            "target": ref,
        },
        "additionalProperties": True,
    }
    return {
        "$schema": DRAFT,
        "$id": BASE + NAME,
        "title": "lifetxt derived temporal context v1",
        "type": "object",
        "required": [
            "schema",
            "reference_date",
            "target_id",
            "target",
            "window_days",
            "facts",
            "related",
        ],
        "properties": {
            "schema": {"const": "temporal-context-v1"},
            "reference_date": {"type": ["string", "null"]},
            "target_id": {"type": ["string", "null"]},
            "target": ref,
            "window_days": {"type": "integer", "minimum": 0},
            "facts": {"type": "array", "items": fact},
            "related": {"type": "array", "items": edge},
        },
        "additionalProperties": True,
    }


def temporal_context_v1_sample():
    return OrderedDict(
        (
            ("schema", "temporal-context-v1"),
            ("reference_date", "2026-08-22"),
            ("target_id", "T-1"),
            (
                "target",
                OrderedDict(
                    (
                        ("title", "Ship report"),
                        ("kind", "T"),
                        ("status", "[ ]"),
                        ("source", "life.txt"),
                        ("line", 3),
                    )
                ),
            ),
            ("window_days", 7),
            (
                "facts",
                [
                    OrderedDict(
                        (
                            ("rule", "overdue_by"),
                            ("source_field", "due"),
                            ("reference_time", "2026-08-22"),
                            ("days", 2),
                        )
                    )
                ],
            ),
            (
                "related",
                [
                    OrderedDict(
                        (
                            ("relation", "same_day"),
                            ("rule", "same_day"),
                            ("source_field", "due"),
                            ("target_field", "due"),
                            ("reference_time", "2026-08-22"),
                            ("days", 0),
                            ("target_id", "T-2"),
                            (
                                "target",
                                OrderedDict(
                                    (
                                        ("title", "Review draft"),
                                        ("kind", "T"),
                                        ("status", "[ ]"),
                                        ("source", "life.txt"),
                                        ("line", 5),
                                    )
                                ),
                            ),
                        )
                    )
                ],
            ),
        )
    )


def install_schema_extensions_v24():
    from . import release_policy, safety_foundation

    if getattr(release_policy, "_lifetxt_schema_extensions_v24", False):
        return
    old_bundle = safety_foundation.schema_bundle
    old_samples = release_policy._schema_samples

    def bundle():
        result = OrderedDict(old_bundle())
        result[NAME] = temporal_context_v1_schema()
        return result

    def samples():
        result = OrderedDict(old_samples())
        result[NAME] = temporal_context_v1_sample()
        return result

    safety_foundation.schema_bundle = bundle
    release_policy.schema_bundle = bundle
    release_policy._schema_samples = samples
    release_policy._lifetxt_schema_extensions_v24 = True
