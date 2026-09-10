"""Published bounded native Temporal Timeline contract (#715)."""

from __future__ import unicode_literals

from collections import OrderedDict

from .schema_extensions_v27 import BASE, DRAFT


NAME = "temporal-timeline-v1.schema.json"


def temporal_timeline_v1_schema():
    coverage = {
        "type": "object",
        "required": ["coverage", "complete"],
        "properties": {
            "coverage": {"type": "string"},
            "complete": {"type": "boolean"},
            "diagnostic_codes": {
                "type": "array",
                "items": {"type": "string"},
            },
        },
        "additionalProperties": False,
    }
    event = {
        "type": "object",
        "required": [
            "record_kind",
            "record_id",
            "parent",
            "event",
            "at",
            "sequence",
            "transaction",
            "source_revision",
            "payload",
            "valid",
        ],
        "properties": {
            "record_kind": {
                "enum": [
                    "item_event",
                    "progress_event",
                    "ticket_event",
                    "time_entry",
                ]
            },
            "record_id": {"type": "string"},
            "parent": {"type": "string"},
            "event": {"type": "string"},
            "at": {"type": "string"},
            "sequence": {"type": ["integer", "null"]},
            "transaction": {"type": "string"},
            "source_revision": {"type": "string"},
            "payload": {
                "type": "object",
                "additionalProperties": {
                    "type": "array",
                    "items": {"type": "string"},
                },
            },
            "valid": {"type": "boolean"},
        },
        "additionalProperties": False,
    }
    diagnostic = {
        "type": "object",
        "required": ["severity", "code", "message", "source", "line"],
        "properties": {
            "severity": {"type": "string"},
            "code": {"type": "string"},
            "message": {"type": "string"},
            "source": {"type": ["string", "null"]},
            "line": {"type": ["integer", "null"]},
        },
        "additionalProperties": False,
    }
    return {
        "$schema": DRAFT,
        "$id": BASE + NAME,
        "title": "lifetxt native temporal timeline v1",
        "type": "object",
        "$defs": {"coverage": coverage, "event": event, "diagnostic": diagnostic},
        "required": [
            "schema",
            "target_id",
            "target",
            "source",
            "git_composed",
            "bounds",
            "complete",
            "limitations",
            "completeness",
            "events",
            "invalid_events",
            "diagnostics",
        ],
        "properties": {
            "schema": {"const": "temporal-timeline-v1"},
            "target_id": {"type": "string"},
            "target": {
                "type": "object",
                "required": ["title", "kind", "status"],
                "properties": {
                    "title": {"type": "string"},
                    "kind": {"type": "string"},
                    "status": {"type": "string"},
                },
                "additionalProperties": False,
            },
            "source": {"const": "native_life_txt"},
            "git_composed": {"const": False},
            "revision": {
                "type": ["string", "null"],
                "description": "Optional source-set revision added by revision-aware read surfaces.",
            },
            "bounds": {
                "type": "object",
                "required": [
                    "limit",
                    "total_valid_events",
                    "returned_events",
                    "truncated",
                ],
                "properties": {
                    "limit": {"type": "integer", "minimum": 0, "maximum": 500},
                    "total_valid_events": {"type": "integer", "minimum": 0},
                    "returned_events": {"type": "integer", "minimum": 0},
                    "truncated": {"type": "boolean"},
                },
                "additionalProperties": False,
            },
            "complete": {"type": "boolean"},
            "limitations": {"type": "array", "items": {"type": "string"}},
            "completeness": {
                "type": "object",
                "required": ["item", "progress", "ticket", "time_entry"],
                "properties": {
                    "item": {"$ref": "#/$defs/coverage"},
                    "progress": {"$ref": "#/$defs/coverage"},
                    "ticket": {"$ref": "#/$defs/coverage"},
                    "time_entry": {"$ref": "#/$defs/coverage"},
                },
                "additionalProperties": False,
            },
            "events": {"type": "array", "items": {"$ref": "#/$defs/event"}},
            "invalid_events": {
                "type": "array",
                "items": {"$ref": "#/$defs/event"},
            },
            "diagnostics": {
                "type": "array",
                "items": {"$ref": "#/$defs/diagnostic"},
            },
        },
        "additionalProperties": False,
    }


def temporal_timeline_v1_sample():
    return OrderedDict(
        (
            ("schema", "temporal-timeline-v1"),
            ("target_id", "task-1"),
            ("target", OrderedDict((("title", "Task"), ("kind", "T"), ("status", "[ ]")))),
            ("source", "native_life_txt"),
            ("git_composed", False),
            ("bounds", OrderedDict((("limit", 100), ("total_valid_events", 0), ("returned_events", 0), ("truncated", False)))),
            ("complete", False),
            ("limitations", ["no_native_history"]),
            (
                "completeness",
                OrderedDict(
                    (
                        ("item", OrderedDict((("coverage", "partial"), ("complete", False), ("diagnostic_codes", [])))),
                        ("progress", OrderedDict((("coverage", "none"), ("complete", False)))),
                        ("ticket", OrderedDict((("coverage", "none"), ("complete", False)))),
                        ("time_entry", OrderedDict((("coverage", "none"), ("complete", False)))),
                    )
                ),
            ),
            ("events", []),
            ("invalid_events", []),
            ("diagnostics", []),
        )
    )


def install_schema_extensions_v29():
    from . import release_policy, safety_foundation

    if getattr(release_policy, "_lifetxt_schema_extensions_v29", False):
        return
    old_bundle = safety_foundation.schema_bundle
    old_samples = release_policy._schema_samples

    def bundle():
        result = OrderedDict(old_bundle())
        result[NAME] = temporal_timeline_v1_schema()
        return result

    def samples():
        result = OrderedDict(old_samples())
        result[NAME] = temporal_timeline_v1_sample()
        return result

    safety_foundation.schema_bundle = bundle
    release_policy.schema_bundle = bundle
    release_policy._schema_samples = samples
    release_policy._lifetxt_schema_extensions_v29 = True
