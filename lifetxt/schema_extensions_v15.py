"""Schemas for development tickets and the ticket field registry."""

from __future__ import unicode_literals

from collections import OrderedDict

BASE = "https://github.com/Eruhitsuji/lifetxt/raw/main/dist/schemas/"
DRAFT = "https://json-schema.org/draft/2020-12/schema"


def schema_bundle_v15():
    summary = {
        "type": "object",
        "required": ["id", "title", "status"],
        "properties": {
            "id": {"type": ["string", "null"]},
            "title": {"type": "string"},
            "tracker": {"type": ["string", "null"]},
            "status": {"type": "string"},
            "ticket_status": {"type": ["string", "null"]},
            "priority": {"type": ["string", "null"]},
            "severity": {"type": ["string", "null"]},
            "assignee": {"type": ["string", "null"]},
            "reporter": {"type": ["string", "null"]},
            "component": {"type": ["string", "null"]},
            "version": {"type": ["string", "null"]},
            "sprint": {"type": ["string", "null"]},
            "project": {"type": ["string", "null"]},
            "due": {"type": ["string", "null"]},
            "watchers": {"type": "array", "items": {"type": "string"}},
            "open": {"type": "boolean"},
            "source": {"type": ["string", "null"]},
            "line": {"type": ["integer", "null"]},
        },
        "additionalProperties": True,
    }
    return OrderedDict(
        (
            (
                "ticket-v1.schema.json",
                {
                    "$schema": DRAFT,
                    "$id": BASE + "ticket-v1.schema.json",
                    "title": "lifetxt development ticket v1",
                    "type": "object",
                    "required": ["summary", "fields", "relations"],
                    "properties": {
                        "summary": summary,
                        "fields": {"type": "object"},
                        "relations": {
                            "type": "object",
                            "additionalProperties": {"type": "array", "items": {"type": "string"}},
                        },
                        "incoming_links": {"type": "array", "items": {"type": "object"}},
                        "est": {"type": ["string", "null"]},
                        "elapsed": {"type": ["string", "null"]},
                        "resolution": {"type": ["string", "null"]},
                    },
                    "additionalProperties": True,
                },
            ),
            (
                "ticket-field-registry-v1.schema.json",
                {
                    "$schema": DRAFT,
                    "$id": BASE + "ticket-field-registry-v1.schema.json",
                    "title": "lifetxt ticket field registry v1",
                    "type": "object",
                    "additionalProperties": {
                        "type": "object",
                        "required": ["repeatable", "registry"],
                        "properties": {
                            "repeatable": {"type": "boolean"},
                            "registry": {"type": "boolean"},
                        },
                        "additionalProperties": True,
                    },
                },
            ),
        )
    )


def schema_samples_v15():
    return OrderedDict(
        (
            (
                "ticket-v1.schema.json",
                {
                    "summary": {
                        "id": "BUG-1", "title": "Login fails", "tracker": "bug",
                        "status": "[ ]", "ticket_status": "new", "priority": "high",
                        "severity": "critical", "assignee": "alice", "reporter": None,
                        "component": "auth", "version": None, "sprint": None,
                        "project": "web", "due": None, "watchers": [], "open": True,
                        "source": "life.txt", "line": 2,
                    },
                    "fields": {"tracker": "bug", "ticket_status": "new", "priority": "high"},
                    "relations": {"depends_on": ["BUG-2"]},
                    "incoming_links": [],
                    "est": None,
                    "elapsed": None,
                    "resolution": None,
                },
            ),
            (
                "ticket-field-registry-v1.schema.json",
                {
                    "tracker": {"repeatable": False, "registry": True},
                    "watcher": {"repeatable": True, "registry": False},
                },
            ),
        )
    )


def install_schema_extensions_v15():
    from . import release_policy, safety_foundation

    if getattr(release_policy, "_lifetxt_schema_extensions_v15", False):
        return
    original_bundle = safety_foundation.schema_bundle
    original_samples = release_policy._schema_samples

    def schema_bundle():
        result = OrderedDict(original_bundle())
        result.update(schema_bundle_v15())
        return result

    def schema_samples():
        result = OrderedDict(original_samples())
        result.update(schema_samples_v15())
        return result

    safety_foundation.schema_bundle = schema_bundle
    release_policy.schema_bundle = schema_bundle
    release_policy._schema_samples = schema_samples
    release_policy._lifetxt_schema_extensions_v15 = True
