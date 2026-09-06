"""Schema contract for the derived, read-only freebusy-v1 result.

See :mod:`lifetxt.freebusy` for the producer (``lifetxt freebusy``, #673)
and that module's own docstring for why this is a separate, bounded
contract from ``temporal-context-v1``: free/busy interval algebra over
``E``/``R`` occurrences is a different question from per-item date facts
and proximity edges.
"""

from __future__ import unicode_literals

from collections import OrderedDict

BASE = "https://github.com/Eruhitsuji/lifetxt/raw/main/dist/schemas/"
DRAFT = "https://json-schema.org/draft/2020-12/schema"
NAME = "freebusy-v1.schema.json"


def freebusy_v1_schema():
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
    busy_entry = {
        "type": "object",
        "required": ["start", "end", "source_field", "item"],
        "properties": {
            "start": {"type": "string"},
            "end": {"type": "string"},
            "source_field": {"type": "string"},
            "item": ref,
        },
        "additionalProperties": True,
    }
    free_entry = {
        "type": "object",
        "required": ["start", "end"],
        "properties": {
            "start": {"type": "string"},
            "end": {"type": "string"},
        },
        "additionalProperties": True,
    }
    conflict_entry = {
        "type": "object",
        "required": ["a", "b", "start", "end"],
        "properties": {
            "a": ref,
            "b": ref,
            "start": {"type": "string"},
            "end": {"type": "string"},
        },
        "additionalProperties": True,
    }
    instant_entry = {
        "type": "object",
        "required": ["at", "source_field", "item"],
        "properties": {
            "at": {"type": "string"},
            "source_field": {"type": "string"},
            "item": ref,
        },
        "additionalProperties": True,
    }
    diagnostic_entry = {
        "type": "object",
        "required": ["code", "message", "item"],
        "properties": {
            "code": {"type": "string"},
            "message": {"type": "string"},
            "item": ref,
            "detail_key": {"type": "string"},
            "value": {"type": "string"},
        },
        "additionalProperties": True,
    }
    return {
        "$schema": DRAFT,
        "$id": BASE + NAME,
        "title": "lifetxt derived freebusy v1",
        "type": "object",
        "required": [
            "schema",
            "range_start",
            "range_end",
            "busy",
            "free",
            "conflicts",
            "instants",
            "diagnostics",
        ],
        "properties": {
            "schema": {"const": "freebusy-v1"},
            "range_start": {"type": "string"},
            "range_end": {"type": "string"},
            "busy": {"type": "array", "items": busy_entry},
            "free": {"type": "array", "items": free_entry},
            "conflicts": {"type": "array", "items": conflict_entry},
            "instants": {"type": "array", "items": instant_entry},
            "diagnostics": {"type": "array", "items": diagnostic_entry},
        },
        "additionalProperties": True,
    }


def freebusy_v1_sample():
    return OrderedDict(
        (
            ("schema", "freebusy-v1"),
            ("range_start", "2026-08-22T09:00"),
            ("range_end", "2026-08-22T18:00"),
            (
                "busy",
                [
                    OrderedDict(
                        (
                            ("start", "2026-08-22T10:00"),
                            ("end", "2026-08-22T11:00"),
                            ("source_field", "from/to"),
                            (
                                "item",
                                OrderedDict(
                                    (
                                        ("title", "Standup"),
                                        ("kind", "E"),
                                        ("status", "[ ]"),
                                        ("source", "life.txt"),
                                        ("line", 3),
                                    )
                                ),
                            ),
                        )
                    )
                ],
            ),
            (
                "free",
                [
                    OrderedDict(
                        (("start", "2026-08-22T09:00"), ("end", "2026-08-22T10:00"))
                    ),
                    OrderedDict(
                        (("start", "2026-08-22T11:00"), ("end", "2026-08-22T18:00"))
                    ),
                ],
            ),
            ("conflicts", []),
            ("instants", []),
            ("diagnostics", []),
        )
    )


def install_schema_extensions_v25():
    from . import release_policy, safety_foundation

    if getattr(release_policy, "_lifetxt_schema_extensions_v25", False):
        return
    old_bundle = safety_foundation.schema_bundle
    old_samples = release_policy._schema_samples

    def bundle():
        result = OrderedDict(old_bundle())
        result[NAME] = freebusy_v1_schema()
        return result

    def samples():
        result = OrderedDict(old_samples())
        result[NAME] = freebusy_v1_sample()
        return result

    safety_foundation.schema_bundle = bundle
    release_policy.schema_bundle = bundle
    release_policy._schema_samples = samples
    release_policy._lifetxt_schema_extensions_v25 = True
