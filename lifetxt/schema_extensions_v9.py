"""Schema for the compiled query plan of the shared query language."""

from __future__ import unicode_literals

from collections import OrderedDict

BASE = "https://github.com/Eruhitsuji/lifetxt/raw/main/dist/schemas/"
DRAFT = "https://json-schema.org/draft/2020-12/schema"


def schema_bundle_v9():
    return OrderedDict(
        (
            (
                "query-plan-v1.schema.json",
                {
                    "$schema": DRAFT,
                    "$id": BASE + "query-plan-v1.schema.json",
                    "title": "lifetxt compiled query plan v1",
                    "type": "object",
                    "required": ["query", "membership", "date_filters", "text", "open_only"],
                    "properties": {
                        "query": {"type": "string"},
                        "membership": {
                            "type": "object",
                            "additionalProperties": {"type": "array", "items": {"type": "string"}},
                        },
                        "excludes": {"type": "array", "items": {"type": "string"}},
                        "details": {
                            "type": "object",
                            "additionalProperties": {"type": "array", "items": {"type": "string"}},
                        },
                        "date_filters": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "required": ["field", "op", "date"],
                                "properties": {
                                    "field": {"type": "string"},
                                    "op": {"type": "string"},
                                    "date": {"type": "string"},
                                },
                                "additionalProperties": False,
                            },
                        },
                        "text": {"type": "array", "items": {"type": "string"}},
                        "open_only": {"type": "boolean"},
                        "diagnostics": {"type": "array", "items": {"type": "object"}},
                    },
                    "additionalProperties": True,
                },
            ),
        )
    )


def schema_samples_v9():
    return OrderedDict(
        (
            (
                "query-plan-v1.schema.json",
                {
                    "query": "open project:web due<2026-08-01",
                    "membership": {"project": ["web"]},
                    "excludes": [],
                    "details": {},
                    "date_filters": [{"field": "due", "op": "<", "date": "2026-08-01"}],
                    "text": [],
                    "open_only": True,
                    "diagnostics": [],
                },
            ),
        )
    )


def install_schema_extensions_v9():
    from . import release_policy, safety_foundation

    if getattr(release_policy, "_lifetxt_schema_extensions_v9", False):
        return
    original_bundle = safety_foundation.schema_bundle
    original_samples = release_policy._schema_samples

    def schema_bundle():
        result = OrderedDict(original_bundle())
        result.update(schema_bundle_v9())
        return result

    def schema_samples():
        result = OrderedDict(original_samples())
        result.update(schema_samples_v9())
        return result

    safety_foundation.schema_bundle = schema_bundle
    release_policy.schema_bundle = schema_bundle
    release_policy._schema_samples = schema_samples
    release_policy._lifetxt_schema_extensions_v9 = True
