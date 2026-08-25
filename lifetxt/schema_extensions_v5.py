"""Schemas for versioned configuration and workspace source manifests."""

from __future__ import unicode_literals

from collections import OrderedDict

BASE = "https://github.com/Eruhitsuji/lifetxt/raw/main/dist/schemas/"
DRAFT = "https://json-schema.org/draft/2020-12/schema"


def _source_manifest_entry():
    return {
        "type": "object",
        "required": ["path"],
        "properties": {
            "path": {"type": "string", "minLength": 1},
            "role": {
                "enum": [
                    "primary",
                    "input",
                    "generated",
                    "archive",
                    "readonly",
                    "reference",
                    "ticket_event",
                    "time_entry",
                ]
            },
            "required": {"type": "boolean"},
            "writable": {"type": "boolean"},
            "default_visible": {"type": "boolean"},
            "format": {"type": "string"},
            "priority": {"type": "integer"},
            "watch": {"type": "boolean"},
            "privacy": {"type": "string"},
            "generated_by": {"type": ["string", "null"]},
            "exclude": {"type": "array", "items": {"type": "string"}},
        },
        "additionalProperties": False,
    }


def _report_profile():
    non_empty_string = {"type": "string", "minLength": 1}
    return {
        "type": "object",
        "required": ["period"],
        "properties": {
            "period": {"enum": ["daily", "weekly", "monthly"]},
            "output": non_empty_string,
            "title": non_empty_string,
            "project": non_empty_string,
            "type": non_empty_string,
            "tag": non_empty_string,
            "open": {"type": "boolean"},
            "mode": {"enum": ["replace", "create", "append"]},
            "frontmatter": {"type": "boolean"},
        },
        "additionalProperties": False,
    }


def schema_bundle_v5():
    source = {
        "oneOf": [
            {"type": "string", "minLength": 1},
            _source_manifest_entry(),
        ]
    }
    workspace = {
        "type": "object",
        "properties": {
            "sources": {"type": "array", "items": source},
            "paths": {"type": "array", "items": source},
            "write_file": {"type": "string"},
        },
        "additionalProperties": True,
    }
    return OrderedDict(
        (
            (
                "workspace-source-manifest-v1.schema.json",
                {
                    "$schema": DRAFT,
                    "$id": BASE + "workspace-source-manifest-v1.schema.json",
                    "title": "lifetxt workspace source manifest v1",
                    "type": "object",
                    "required": ["manifest_version", "name", "sources"],
                    "properties": {
                        "manifest_version": {"const": 1},
                        "name": {"type": "string"},
                        "legacy": {"type": "boolean"},
                        "base_dir": {"type": "string"},
                        "write_file": {"type": ["string", "null"]},
                        "input_paths": {"type": "array", "items": {"type": "string"}},
                        "default_visible_paths": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                        "generated_paths": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                        "archive_paths": {"type": "array", "items": {"type": "string"}},
                        "ok": {"type": "boolean"},
                        "sources": {"type": "array", "items": {"type": "object"}},
                        "diagnostics": {"type": "array", "items": {"type": "object"}},
                    },
                    "additionalProperties": True,
                },
            ),
            (
                "config-v1.schema.json",
                {
                    "$schema": DRAFT,
                    "$id": BASE + "config-v1.schema.json",
                    "title": "lifetxt configuration v1",
                    "type": "object",
                    "properties": {
                        "config_version": {"type": "integer", "minimum": 1},
                        "default_workspace": {"type": "string"},
                        "paths": {"type": "array", "items": {"type": "string"}},
                        "write_file": {"type": "string"},
                        "config": {
                            "type": "object",
                            "properties": {
                                "write": {
                                    "type": "object",
                                    "properties": {
                                        "require_revision": {"type": "boolean"},
                                    },
                                    "additionalProperties": True,
                                },
                            },
                            "additionalProperties": True,
                        },
                        "workspaces": {
                            "type": "object",
                            "additionalProperties": workspace,
                        },
                        "workspace": {
                            "type": "object",
                            "properties": {
                                "max_total_source_bytes": {
                                    "type": "integer",
                                    "minimum": 1,
                                },
                            },
                            "additionalProperties": True,
                        },
                        "update": {
                            "type": "object",
                            "properties": {
                                "repository": {"type": "string"},
                            },
                            "additionalProperties": True,
                        },
                        "profiles": {
                            "type": "object",
                            "additionalProperties": {"type": "object"},
                        },
                        "reports": {
                            "type": "object",
                            "additionalProperties": _report_profile(),
                        },
                        "defaults": {
                            "type": "object",
                            "properties": {
                                "person": {"type": "string"},
                                "timezone": {"type": "string"},
                            },
                            "additionalProperties": True,
                        },
                    },
                    "additionalProperties": True,
                },
            ),
        )
    )


def schema_samples_v5():
    return OrderedDict(
        (
            (
                "workspace-source-manifest-v1.schema.json",
                {
                    "manifest_version": 1,
                    "name": "default",
                    "legacy": False,
                    "base_dir": "/srv/lifetxt",
                    "write_file": "/srv/lifetxt/life.txt",
                    "input_paths": ["/srv/lifetxt/life.txt"],
                    "default_visible_paths": ["/srv/lifetxt/life.txt"],
                    "generated_paths": [],
                    "archive_paths": [],
                    "ok": True,
                    "sources": [{"path": "life.txt", "role": "primary"}],
                    "diagnostics": [],
                },
            ),
            (
                "config-v1.schema.json",
                {
                    "config_version": 1,
                    "default_workspace": "personal",
                    "config": {"write": {"require_revision": False}},
                    "workspaces": {
                        "personal": {
                            "sources": [
                                "life.txt",
                                {
                                    "path": ".generated/cal.life.txt",
                                    "role": "generated",
                                },
                            ],
                            "write_file": "life.txt",
                        }
                    },
                    "workspace": {"max_total_source_bytes": 67108864},
                    "update": {"repository": "Eruhitsuji/lifetxt"},
                    "reports": {
                        "weekly": {
                            "period": "weekly",
                            "output": "reports/{iso_year}-W{iso_week}.md",
                            "mode": "replace",
                            "frontmatter": True,
                        }
                    },
                    "defaults": {"person": "self", "timezone": "Asia/Tokyo"},
                },
            ),
        )
    )


def install_schema_extensions_v5():
    from . import release_policy, safety_foundation

    if getattr(release_policy, "_lifetxt_schema_extensions_v5", False):
        return
    original_bundle = safety_foundation.schema_bundle
    original_samples = release_policy._schema_samples

    def schema_bundle():
        result = OrderedDict(original_bundle())
        result.update(schema_bundle_v5())
        return result

    def schema_samples():
        result = OrderedDict(original_samples())
        result.update(schema_samples_v5())
        return result

    safety_foundation.schema_bundle = schema_bundle
    release_policy.schema_bundle = schema_bundle
    release_policy._schema_samples = schema_samples
    release_policy._lifetxt_schema_extensions_v5 = True
