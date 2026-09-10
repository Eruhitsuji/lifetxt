"""Published schema for the shared native item-event record (#713)."""

from __future__ import unicode_literals

from collections import OrderedDict

from .schema_extensions_v27 import BASE, DRAFT


NAME = "item-event-v1.schema.json"


def item_event_v1_schema():
    common = {
        "record": {"const": "item_event"},
        "id": {"type": "string", "pattern": "^IE-.+-[0-9]{6}$"},
        "parent": {"type": "string", "minLength": 1},
        "event": {
            "enum": [
                "created",
                "status_changed",
                "completed",
                "reopened",
                "canceled",
                "relation_added",
                "relation_removed",
                "schedule_changed",
            ]
        },
        "at": {"type": "string", "format": "date-time", "pattern": "Z$"},
        "sequence": {"type": "integer", "minimum": 1},
        "transaction": {"type": "string", "minLength": 1},
        "source_revision": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
        "actor": {"type": "string"},
        "source": {"type": "string"},
        "item_kind": {"type": "string", "minLength": 1},
        "item_title": {"type": "string"},
        "before_status": {"type": "string", "minLength": 1},
        "after_status": {"type": "string", "minLength": 1},
        "completed_at": {"type": "string", "format": "date-time"},
        "relation": {"enum": ["follows", "realizes", "replaced_by"]},
        "target": {"type": "string", "minLength": 1},
        "field": {"enum": ["on", "due", "from", "to", "at"]},
        "before": {"type": "string"},
        "before_missing": {"const": True},
        "after": {"type": "string"},
        "after_missing": {"const": True},
    }
    required = [
        "record",
        "id",
        "parent",
        "event",
        "at",
        "sequence",
        "transaction",
        "source_revision",
    ]
    variants = []
    for event, payload in (
        ("created", ["item_kind", "item_title", "after_status"]),
        ("status_changed", ["before_status", "after_status"]),
        ("completed", ["before_status", "after_status"]),
        ("reopened", ["before_status", "after_status"]),
        ("canceled", ["before_status", "after_status"]),
        ("relation_added", ["relation", "target"]),
        ("relation_removed", ["relation", "target"]),
    ):
        variants.append(
            {
                "properties": {"event": {"const": event}},
                "required": list(payload),
            }
        )
    variants.append(
        {
            "properties": {"event": {"const": "schedule_changed"}},
            "required": ["field"],
            "allOf": [
                {"oneOf": [{"required": ["before"]}, {"required": ["before_missing"]}]},
                {"oneOf": [{"required": ["after"]}, {"required": ["after_missing"]}]},
            ],
        }
    )
    return {
        "$schema": DRAFT,
        "$id": BASE + NAME,
        "title": "lifetxt native item event v1",
        "type": "object",
        "required": required,
        "properties": common,
        "oneOf": variants,
        "additionalProperties": False,
    }


def item_event_v1_sample():
    return OrderedDict(
        (
            ("record", "item_event"),
            ("id", "IE-task-1-000001"),
            ("parent", "task-1"),
            ("event", "created"),
            ("at", "2026-09-10T10:00:00Z"),
            ("sequence", 1),
            ("transaction", "ITX-task-1-000001"),
            ("source_revision", "a" * 64),
            ("actor", "local"),
            ("source", "cli"),
            ("item_kind", "T"),
            ("item_title", "Example"),
            ("after_status", "[ ]"),
        )
    )


def install_schema_extensions_v28():
    from . import release_policy, safety_foundation

    if getattr(release_policy, "_lifetxt_schema_extensions_v28", False):
        return
    old_bundle = safety_foundation.schema_bundle
    old_samples = release_policy._schema_samples

    def bundle():
        result = OrderedDict(old_bundle())
        result[NAME] = item_event_v1_schema()
        return result

    def samples():
        result = OrderedDict(old_samples())
        result[NAME] = item_event_v1_sample()
        return result

    safety_foundation.schema_bundle = bundle
    release_policy.schema_bundle = bundle
    release_policy._schema_samples = samples
    release_policy._lifetxt_schema_extensions_v28 = True
