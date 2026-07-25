"""Schema for global search results."""

from __future__ import unicode_literals

from collections import OrderedDict

BASE = "https://github.com/Eruhitsuji/lifetxt/raw/main/dist/schemas/"
DRAFT = "https://json-schema.org/draft/2020-12/schema"


def schema_bundle_v14():
    result_row = {
        "type": "object",
        "required": ["type", "name", "field", "snippet"],
        "properties": {
            "type": {"enum": ["item", "project", "person", "group", "area", "proposal"]},
            "name": {"type": "string"},
            "field": {"type": "string"},
            "snippet": {"type": "string"},
            "source": {"type": ["string", "null"]},
            "line": {"type": ["integer", "null"]},
        },
        "additionalProperties": True,
    }
    return OrderedDict(
        (
            (
                "global-search-v1.schema.json",
                {
                    "$schema": DRAFT,
                    "$id": BASE + "global-search-v1.schema.json",
                    "title": "lifetxt global search result v1",
                    "type": "object",
                    "required": ["term", "total", "groups"],
                    "properties": {
                        "term": {"type": "string"},
                        "total": {"type": "integer", "minimum": 0},
                        "groups": {
                            "type": "object",
                            "additionalProperties": {"type": "array", "items": result_row},
                        },
                    },
                    "additionalProperties": True,
                },
            ),
        )
    )


def schema_samples_v14():
    return OrderedDict(
        (
            (
                "global-search-v1.schema.json",
                {
                    "term": "web",
                    "total": 2,
                    "groups": {
                        "item": [
                            {"type": "item", "name": "T1", "field": "title",
                             "snippet": "Design website", "source": "life.txt", "line": 3}
                        ],
                        "project": [
                            {"type": "project", "name": "web", "field": "name",
                             "snippet": "name:web", "source": None, "line": None}
                        ],
                    },
                },
            ),
        )
    )


def install_schema_extensions_v14():
    from . import release_policy, safety_foundation

    if getattr(release_policy, "_lifetxt_schema_extensions_v14", False):
        return
    original_bundle = safety_foundation.schema_bundle
    original_samples = release_policy._schema_samples

    def schema_bundle():
        result = OrderedDict(original_bundle())
        result.update(schema_bundle_v14())
        return result

    def schema_samples():
        result = OrderedDict(original_samples())
        result.update(schema_samples_v14())
        return result

    safety_foundation.schema_bundle = schema_bundle
    release_policy.schema_bundle = schema_bundle
    release_policy._schema_samples = schema_samples
    release_policy._lifetxt_schema_extensions_v14 = True
