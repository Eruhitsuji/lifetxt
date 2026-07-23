"""Release-manifest schema extension for the Format 1.0 schema bundle."""

from __future__ import unicode_literals

import json
from collections import OrderedDict


SCHEMA_NAME = "release-manifest-v1.schema.json"


def release_manifest_schema():
    base = "https://github.com/Eruhitsuji/lifetxt/raw/main/dist/schemas/"
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": base + SCHEMA_NAME,
        "title": "lifetxt release manifest v1",
        "type": "object",
        "required": [
            "release_policy_version",
            "package",
            "package_version",
            "versions",
            "checks",
            "ok",
            "fingerprint",
        ],
        "properties": {
            "release_policy_version": {"type": "string"},
            "package": {"const": "lifetxt"},
            "package_version": {"type": "string"},
            "versions": {
                "type": "object",
                "required": ["format", "canon", "schema", "capability"],
                "properties": {
                    "format": {"type": "string"},
                    "canon": {"type": "string"},
                    "schema": {"type": "string"},
                    "capability": {"type": "string"},
                },
                "additionalProperties": True,
            },
            "checks": {
                "type": "object",
                "minProperties": 1,
                "additionalProperties": {
                    "type": "object",
                    "required": ["ok"],
                    "properties": {"ok": {"type": "boolean"}},
                    "additionalProperties": True,
                },
            },
            "ok": {"type": "boolean"},
            "fingerprint": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
        },
        "additionalProperties": False,
    }


def install_release_manifest_schema():
    from . import release_policy, safety_foundation

    if getattr(release_policy, "_lifetxt_release_manifest_schema_installed", False):
        return
    original_bundle = safety_foundation.schema_bundle
    original_samples = release_policy._schema_samples

    def schema_bundle():
        bundle = OrderedDict(original_bundle())
        bundle[SCHEMA_NAME] = release_manifest_schema()
        return bundle

    def schema_samples():
        samples = OrderedDict(original_samples())
        samples[SCHEMA_NAME] = {
            "release_policy_version": "1",
            "package": "lifetxt",
            "package_version": "0.1.0",
            "versions": {
                "format": "1",
                "canon": "LIFETXT_CANON_V1",
                "schema": "1",
                "capability": "1",
            },
            "checks": {"mutation_cas": {"ok": True}},
            "ok": True,
            "fingerprint": "0" * 64,
        }
        return samples

    safety_foundation.schema_bundle = schema_bundle
    release_policy.schema_bundle = schema_bundle
    release_policy._schema_samples = schema_samples
    release_policy._lifetxt_release_manifest_schema_installed = True
