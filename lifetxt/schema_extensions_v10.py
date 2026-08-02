"""Schema for recipient resolution (group/team/person expansion)."""

from __future__ import unicode_literals

from collections import OrderedDict

BASE = "https://github.com/Eruhitsuji/lifetxt/raw/main/dist/schemas/"
DRAFT = "https://json-schema.org/draft/2020-12/schema"


def schema_bundle_v10():
    return OrderedDict(
        (
            (
                "recipient-resolution-v1.schema.json",
                {
                    "$schema": DRAFT,
                    "$id": BASE + "recipient-resolution-v1.schema.json",
                    "title": "lifetxt recipient resolution v1",
                    "type": "object",
                    "required": ["references", "recipients", "count"],
                    "properties": {
                        "references": {"type": "array", "items": {"type": "string"}},
                        "recipients": {"type": "array", "items": {"type": "string"}},
                        "expansion": {
                            "type": "object",
                            "additionalProperties": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                        },
                        "count": {"type": "integer", "minimum": 0},
                        "diagnostics": {"type": "array", "items": {"type": "object"}},
                    },
                    "additionalProperties": True,
                },
            ),
        )
    )


def schema_samples_v10():
    return OrderedDict(
        (
            (
                "recipient-resolution-v1.schema.json",
                {
                    "references": ["group:eng", "erin"],
                    "recipients": ["alice", "carol", "dave", "erin"],
                    "expansion": {
                        "group:eng": ["alice", "carol", "dave"],
                        "erin": ["erin"],
                    },
                    "count": 4,
                    "diagnostics": [],
                },
            ),
        )
    )


def install_schema_extensions_v10():
    from . import release_policy, safety_foundation

    if getattr(release_policy, "_lifetxt_schema_extensions_v10", False):
        return
    original_bundle = safety_foundation.schema_bundle
    original_samples = release_policy._schema_samples

    def schema_bundle():
        result = OrderedDict(original_bundle())
        result.update(schema_bundle_v10())
        return result

    def schema_samples():
        result = OrderedDict(original_samples())
        result.update(schema_samples_v10())
        return result

    safety_foundation.schema_bundle = schema_bundle
    release_policy.schema_bundle = schema_bundle
    release_policy._schema_samples = schema_samples
    release_policy._lifetxt_schema_extensions_v10 = True
