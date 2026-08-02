"""Schema for stored Unified Inbox proposals."""

from __future__ import unicode_literals

from collections import OrderedDict

BASE = "https://github.com/Eruhitsuji/lifetxt/raw/main/dist/schemas/"
DRAFT = "https://json-schema.org/draft/2020-12/schema"


def schema_bundle_v12():
    return OrderedDict(
        (
            (
                "inbox-proposal-v1.schema.json",
                {
                    "$schema": DRAFT,
                    "$id": BASE + "inbox-proposal-v1.schema.json",
                    "title": "lifetxt inbox proposal v1",
                    "type": "object",
                    "required": [
                        "proposal_version",
                        "id",
                        "operation",
                        "source",
                        "changes",
                        "status",
                    ],
                    "properties": {
                        "proposal_version": {"const": "1"},
                        "id": {"type": "string", "minLength": 1},
                        "operation": {"type": "string"},
                        "source": {"type": "string"},
                        "expected_revision": {"type": "string"},
                        "changes": {"type": "array", "items": {"type": "object"}},
                        "warnings": {"type": "array", "items": {"type": "string"}},
                        "status": {
                            "enum": ["pending", "accepted", "rejected", "deferred"]
                        },
                        "provenance": {"type": "object"},
                        "created": {"type": "string"},
                    },
                    "additionalProperties": True,
                },
            ),
        )
    )


def schema_samples_v12():
    return OrderedDict(
        (
            (
                "inbox-proposal-v1.schema.json",
                {
                    "proposal_version": "1",
                    "id": "P-1a2b3c4d",
                    "operation": "create",
                    "source": "mcp",
                    "expected_revision": "",
                    "changes": [
                        {
                            "op": "create",
                            "kind": "T",
                            "status": "[ ]",
                            "title": "Buy milk",
                            "details": {"project": ["home"]},
                        }
                    ],
                    "warnings": [],
                    "status": "pending",
                    "provenance": {},
                    "created": "2026-07-25T00:00:00",
                },
            ),
        )
    )


def install_schema_extensions_v12():
    from . import release_policy, safety_foundation

    if getattr(release_policy, "_lifetxt_schema_extensions_v12", False):
        return
    original_bundle = safety_foundation.schema_bundle
    original_samples = release_policy._schema_samples

    def schema_bundle():
        result = OrderedDict(original_bundle())
        result.update(schema_bundle_v12())
        return result

    def schema_samples():
        result = OrderedDict(original_samples())
        result.update(schema_samples_v12())
        return result

    safety_foundation.schema_bundle = schema_bundle
    release_policy.schema_bundle = schema_bundle
    release_policy._schema_samples = schema_samples
    release_policy._lifetxt_schema_extensions_v12 = True
