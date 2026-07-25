"""Schema for person overview aggregation."""

from __future__ import unicode_literals

from collections import OrderedDict

BASE = "https://github.com/Eruhitsuji/lifetxt/raw/main/dist/schemas/"
DRAFT = "https://json-schema.org/draft/2020-12/schema"


def schema_bundle_v11():
    item_list = {"type": "array", "items": {"type": "object"}}
    return OrderedDict(
        (
            (
                "person-overview-v1.schema.json",
                {
                    "$schema": DRAFT,
                    "$id": BASE + "person-overview-v1.schema.json",
                    "title": "lifetxt person overview v1",
                    "type": "object",
                    "required": ["person", "counts", "memberships"],
                    "properties": {
                        "person": {"type": "string"},
                        "aliases": {"type": "array", "items": {"type": "string"}},
                        "presence": {"type": ["object", "null"]},
                        "assigned_open": item_list,
                        "waiting": item_list,
                        "overdue": item_list,
                        "messages_sent": item_list,
                        "messages_received": item_list,
                        "meetings": item_list,
                        "projects": {"type": "array", "items": {"type": "object"}},
                        "memberships": {
                            "type": "object",
                            "required": ["teams", "groups"],
                            "properties": {
                                "teams": {"type": "array", "items": {"type": "string"}},
                                "groups": {"type": "array", "items": {"type": "string"}},
                            },
                            "additionalProperties": False,
                        },
                        "counts": {
                            "type": "object",
                            "additionalProperties": {"type": "integer", "minimum": 0},
                        },
                    },
                    "additionalProperties": True,
                },
            ),
        )
    )


def schema_samples_v11():
    return OrderedDict(
        (
            (
                "person-overview-v1.schema.json",
                {
                    "person": "alice",
                    "aliases": [],
                    "presence": None,
                    "assigned_open": [],
                    "waiting": [],
                    "overdue": [],
                    "messages_sent": [],
                    "messages_received": [],
                    "meetings": [],
                    "projects": [],
                    "memberships": {"teams": ["platform"], "groups": ["eng"]},
                    "counts": {"assigned_open": 2, "overdue": 1},
                },
            ),
        )
    )


def install_schema_extensions_v11():
    from . import release_policy, safety_foundation

    if getattr(release_policy, "_lifetxt_schema_extensions_v11", False):
        return
    original_bundle = safety_foundation.schema_bundle
    original_samples = release_policy._schema_samples

    def schema_bundle():
        result = OrderedDict(original_bundle())
        result.update(schema_bundle_v11())
        return result

    def schema_samples():
        result = OrderedDict(original_samples())
        result.update(schema_samples_v11())
        return result

    safety_foundation.schema_bundle = schema_bundle
    release_policy.schema_bundle = schema_bundle
    release_policy._schema_samples = schema_samples
    release_policy._lifetxt_schema_extensions_v11 = True
