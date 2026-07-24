"""Schemas for project registry metadata and project summaries."""

from __future__ import unicode_literals

from collections import OrderedDict

BASE = "https://github.com/Eruhitsuji/lifetxt/raw/main/dist/schemas/"
DRAFT = "https://json-schema.org/draft/2020-12/schema"


def schema_bundle_v6():
    registry_entry = {
        "type": "object",
        "properties": {
            "display_name": {"type": "string"},
            "aliases": {"type": "array", "items": {"type": "string"}},
            "default_source": {"type": "string"},
            "default_assignee": {"type": "string"},
            "default_area": {"type": "string"},
            "templates": {"type": "array", "items": {"type": "string"}},
            "visibility": {"type": "string"},
        },
        "additionalProperties": True,
    }
    progress = {
        "type": "object",
        "required": ["done", "total", "percent", "formula"],
        "properties": {
            "done": {"type": "integer", "minimum": 0},
            "total": {"type": "integer", "minimum": 0},
            "percent": {"type": ["number", "null"]},
            "formula": {"type": "string"},
            "undefined_reason": {"type": ["string", "null"]},
        },
        "additionalProperties": False,
    }
    return OrderedDict(
        (
            (
                "project-registry-v1.schema.json",
                {
                    "$schema": DRAFT,
                    "$id": BASE + "project-registry-v1.schema.json",
                    "title": "lifetxt project registry v1",
                    "type": "object",
                    "additionalProperties": registry_entry,
                },
            ),
            (
                "project-summary-v1.schema.json",
                {
                    "$schema": DRAFT,
                    "$id": BASE + "project-summary-v1.schema.json",
                    "title": "lifetxt project summary v1",
                    "type": "object",
                    "required": ["name", "state", "task_total", "task_done", "health"],
                    "properties": {
                        "name": {"type": "string"},
                        "display_name": {"type": "string"},
                        "state": {"type": "string"},
                        "owner": {"type": ["string", "null"]},
                        "area": {"type": ["string", "null"]},
                        "archived": {"type": "boolean"},
                        "task_total": {"type": "integer", "minimum": 0},
                        "task_done": {"type": "integer", "minimum": 0},
                        "progress_percent": {"type": ["number", "null"]},
                        "open_count": {"type": "integer", "minimum": 0},
                        "overdue_count": {"type": "integer", "minimum": 0},
                        "blocked_count": {"type": "integer", "minimum": 0},
                        "milestone_count": {"type": "integer", "minimum": 0},
                        "open_risk_count": {"type": "integer", "minimum": 0},
                        "health": {"enum": ["green", "yellow", "red"]},
                        "progress": progress,
                    },
                    "additionalProperties": True,
                },
            ),
        )
    )


def schema_samples_v6():
    return OrderedDict(
        (
            (
                "project-registry-v1.schema.json",
                {
                    "web": {
                        "display_name": "Website Revamp",
                        "aliases": ["website"],
                        "default_assignee": "alice",
                        "default_area": "work",
                    }
                },
            ),
            (
                "project-summary-v1.schema.json",
                {
                    "name": "web",
                    "display_name": "Website Revamp",
                    "state": "active",
                    "owner": "alice",
                    "area": "work",
                    "archived": False,
                    "task_total": 4,
                    "task_done": 1,
                    "progress_percent": 25.0,
                    "open_count": 3,
                    "overdue_count": 1,
                    "blocked_count": 1,
                    "milestone_count": 1,
                    "open_risk_count": 1,
                    "health": "red",
                },
            ),
        )
    )


def install_schema_extensions_v6():
    from . import release_policy, safety_foundation

    if getattr(release_policy, "_lifetxt_schema_extensions_v6", False):
        return
    original_bundle = safety_foundation.schema_bundle
    original_samples = release_policy._schema_samples

    def schema_bundle():
        result = OrderedDict(original_bundle())
        result.update(schema_bundle_v6())
        return result

    def schema_samples():
        result = OrderedDict(original_samples())
        result.update(schema_samples_v6())
        return result

    safety_foundation.schema_bundle = schema_bundle
    release_policy.schema_bundle = schema_bundle
    release_policy._schema_samples = schema_samples
    release_policy._lifetxt_schema_extensions_v6 = True
