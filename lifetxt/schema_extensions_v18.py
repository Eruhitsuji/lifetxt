"""Schemas for ticket workflow, append-only history, time, and planning."""
from __future__ import unicode_literals

import copy
from collections import OrderedDict

BASE = "https://github.com/Eruhitsuji/lifetxt/raw/main/dist/schemas/"
DRAFT = "https://json-schema.org/draft/2020-12/schema"


def _schema(name, title, properties, required=()):
    return {
        "$schema": DRAFT,
        "$id": BASE + name,
        "title": title,
        "type": "object",
        "required": list(required),
        "properties": properties,
        "additionalProperties": True,
    }


def workflow_schema():
    transition = {
        "type": "object",
        "required": ["to", "from", "event"],
        "properties": {
            "to": {"type": "string"},
            "from": {"type": "array", "items": {"type": "string"}, "uniqueItems": True},
            "roles": {"type": "array", "items": {"type": "string"}, "uniqueItems": True},
            "required_fields": {"type": "array", "items": {"type": "string"}, "uniqueItems": True},
            "resolution_required": {"type": "boolean"},
            "comment_required": {"type": "boolean"},
            "event": {"type": "string"},
            "set": {"type": "object", "additionalProperties": {"type": "string"}},
            "unset": {"type": "array", "items": {"type": "string"}, "uniqueItems": True},
            "label": {"type": "string"},
            "description": {"type": "string"},
            "allowed_for_role": {"type": "boolean"},
        },
        "additionalProperties": True,
    }
    return _schema(
        "ticket-workflow-v1.schema.json",
        "lifetxt ticket workflow v1",
        {
            "schema": {"const": "ticket-workflow-v1.schema.json"},
            "contract_version": {"const": "1"},
            "valid": {"type": "boolean"},
            "source": {"type": "string"},
            "replace_defaults": {"type": "boolean"},
            "initial_status": {"type": "string"},
            "local_role": {"type": "string"},
            "role": {"type": "string"},
            "statuses": {"type": "object", "additionalProperties": {"type": "string"}},
            "transitions": {"type": "object", "additionalProperties": transition},
            "activities": {"type": "array", "items": {"type": "string"}},
            "diagnostics": {"type": "array", "items": {"type": "object"}},
            "exact_revision_required": {"type": "boolean"},
            "remote_write_enforcement": {"type": "boolean"},
        },
        ("schema", "contract_version", "valid", "statuses", "transitions"),
    )


def event_schema():
    return _schema(
        "ticket-event-v1.schema.json",
        "lifetxt append-only ticket event v1",
        {
            "id": {"type": "string"},
            "ticket_id": {"type": "string"},
            "event": {"type": "string"},
            "author": {"type": "string"},
            "at": {"type": "string", "format": "date-time"},
            "sequence": {"type": "integer", "minimum": 1},
            "transaction_id": {"type": "string"},
            "ticket_revision": {"type": "string"},
            "from_status": {"type": ["string", "null"]},
            "to_status": {"type": ["string", "null"]},
            "changes": {"type": "array", "items": {"type": "object"}},
            "body": {"type": ["string", "null"]},
            "project": {"type": ["string", "null"]},
            "tracker": {"type": ["string", "null"]},
            "provider": {"type": ["string", "null"]},
            "references": {"type": "array", "items": {"type": "string"}},
            "source": {"type": ["string", "null"]},
            "line": {"type": ["integer", "null"]},
        },
        ("id", "ticket_id", "event", "author", "at", "sequence", "transaction_id", "ticket_revision"),
    )


def time_entry_schema():
    return _schema(
        "ticket-time-entry-v1.schema.json",
        "lifetxt append-only ticket time entry v1",
        {
            "id": {"type": "string"},
            "ticket_id": {"type": "string"},
            "project": {"type": ["string", "null"]},
            "user": {"type": "string"},
            "activity": {"type": "string"},
            "date": {"type": "string", "format": "date"},
            "duration": {"type": "string"},
            "seconds": {"type": ["integer", "null"], "minimum": 1},
            "comment": {"type": ["string", "null"]},
            "source": {"type": ["string", "null"]},
            "timer_ref": {"type": ["string", "null"]},
            "corrects": {"type": ["string", "null"]},
            "event_id": {"type": "string"},
            "created_at": {"type": "string", "format": "date-time"},
            "sequence": {"type": "integer", "minimum": 1},
            "line": {"type": ["integer", "null"]},
        },
        ("id", "ticket_id", "user", "activity", "date", "duration", "event_id", "created_at", "sequence"),
    )


def activity_schema():
    return _schema(
        "ticket-activity-v1.schema.json",
        "lifetxt ticket activity v1",
        {
            "schema": {"const": "ticket-activity-v1.schema.json"},
            "contract_version": {"const": "1"},
            "ticket": {"type": "object"},
            "events": {
                "type": "array",
                "items": {"$ref": BASE + "ticket-event-v1.schema.json"},
            },
            "time_entries": {
                "type": "array",
                "items": {"$ref": BASE + "ticket-time-entry-v1.schema.json"},
            },
            "time": {
                "type": "object",
                "required": ["entry_count", "authoritative_seconds", "authoritative_duration", "policy"],
                "properties": {
                    "entry_count": {"type": "integer", "minimum": 0},
                    "authoritative_seconds": {"type": "integer", "minimum": 0},
                    "authoritative_duration": {"type": "string"},
                    "correction_seconds": {"type": "integer", "minimum": 0},
                    "effective_entry_ids": {"type": "array", "items": {"type": ["string", "null"]}},
                    "superseded_entry_ids": {"type": "array", "items": {"type": "string"}},
                    "legacy_elapsed": {"type": ["string", "null"]},
                    "policy": {"type": "string"},
                },
                "additionalProperties": True,
            },
            "diagnostics": {"type": "array", "items": {"type": "object"}},
        },
        ("schema", "contract_version", "ticket", "events", "time_entries", "time"),
    )


def version_schema():
    return _schema(
        "ticket-version-v1.schema.json",
        "lifetxt ticket version v1",
        {
            "id": {"type": "string"},
            "title": {"type": "string"},
            "project": {"type": "string"},
            "state": {"type": "string", "enum": ["open", "locked", "released", "closed"]},
            "due": {"type": ["string", "null"], "format": "date"},
            "release": {"type": ["string", "null"], "format": "date"},
            "description": {"type": ["string", "null"]},
            "parent_version": {"type": ["string", "null"]},
            "ticket_ids": {"type": "array", "items": {"type": "string"}},
            "open_ticket_ids": {"type": "array", "items": {"type": "string"}},
            "ticket_count": {"type": "integer", "minimum": 0},
            "open_ticket_count": {"type": "integer", "minimum": 0},
            "warnings": {"type": "array", "items": {"type": "string"}},
            "source": {"type": ["string", "null"]},
            "line": {"type": ["integer", "null"]},
        },
        ("id", "title", "project", "state", "ticket_ids", "open_ticket_ids", "ticket_count", "open_ticket_count"),
    )


def sprint_schema():
    return _schema(
        "ticket-sprint-v1.schema.json",
        "lifetxt ticket sprint v1",
        {
            "id": {"type": "string"},
            "title": {"type": "string"},
            "project": {"type": "string"},
            "state": {"type": "string", "enum": ["planned", "active", "closed"]},
            "start": {"type": "string", "format": "date"},
            "end": {"type": "string", "format": "date"},
            "goal": {"type": ["string", "null"]},
            "capacity": {"type": ["string", "null"]},
            "version": {"type": ["string", "null"]},
            "ticket_ids": {"type": "array", "items": {"type": "string"}},
            "open_ticket_ids": {"type": "array", "items": {"type": "string"}},
            "ticket_count": {"type": "integer", "minimum": 0},
            "open_ticket_count": {"type": "integer", "minimum": 0},
            "story_points": {"type": "number", "minimum": 0},
            "warnings": {"type": "array", "items": {"type": "string"}},
            "source": {"type": ["string", "null"]},
            "line": {"type": ["integer", "null"]},
        },
        ("id", "title", "project", "state", "start", "end", "ticket_ids", "open_ticket_ids"),
    )


def planning_schema():
    return _schema(
        "ticket-planning-v1.schema.json",
        "lifetxt ticket planning v1",
        {
            "schema": {"const": "ticket-planning-v1.schema.json"},
            "contract_version": {"const": "1"},
            "project": {"type": ["string", "null"]},
            "versions": {
                "type": "array",
                "items": {"$ref": BASE + "ticket-version-v1.schema.json"},
            },
            "sprints": {
                "type": "array",
                "items": {"$ref": BASE + "ticket-sprint-v1.schema.json"},
            },
            "backlog": {"type": "array", "items": {"type": "object"}},
            "diagnostics": {"type": "array", "items": {"type": "object"}},
            "caveats": {"type": "array", "items": {"type": "string"}},
        },
        ("schema", "contract_version", "versions", "sprints", "backlog", "diagnostics"),
    )


def schema_bundle_v18():
    return OrderedDict(
        (
            ("ticket-workflow-v1.schema.json", workflow_schema()),
            ("ticket-event-v1.schema.json", event_schema()),
            ("ticket-time-entry-v1.schema.json", time_entry_schema()),
            ("ticket-activity-v1.schema.json", activity_schema()),
            ("ticket-version-v1.schema.json", version_schema()),
            ("ticket-sprint-v1.schema.json", sprint_schema()),
            ("ticket-planning-v1.schema.json", planning_schema()),
        )
    )


def schema_samples_v18():
    return OrderedDict(
        (
            (
                "ticket-workflow-v1.schema.json",
                {
                    "schema": "ticket-workflow-v1.schema.json",
                    "contract_version": "1",
                    "valid": True,
                    "source": "defaults",
                    "replace_defaults": False,
                    "initial_status": "new",
                    "local_role": "administrator",
                    "statuses": {"new": "[ ]", "in_progress": "[/]", "resolved": "[x]"},
                    "transitions": {
                        "in_progress": {
                            "to": "in_progress",
                            "from": ["new"],
                            "roles": [],
                            "required_fields": [],
                            "resolution_required": False,
                            "comment_required": False,
                            "event": "transition",
                            "set": {},
                            "unset": [],
                            "label": "in_progress",
                            "description": "",
                        }
                    },
                    "activities": ["development"],
                    "diagnostics": [],
                },
            ),
            (
                "ticket-event-v1.schema.json",
                {
                    "id": "EV-BUG-1-000001",
                    "ticket_id": "BUG-1",
                    "event": "transition",
                    "author": "alice",
                    "at": "2026-07-25T00:00:00Z",
                    "sequence": 1,
                    "transaction_id": "TX-BUG-1-1",
                    "ticket_revision": "a" * 64,
                    "from_status": "new",
                    "to_status": "in_progress",
                    "changes": [],
                    "body": None,
                    "project": "web",
                    "tracker": "bug",
                    "provider": None,
                    "references": [],
                    "source": "life.txt",
                    "line": 2,
                },
            ),
            (
                "ticket-time-entry-v1.schema.json",
                {
                    "id": "TIME-BUG-1-000001",
                    "ticket_id": "BUG-1",
                    "project": "web",
                    "user": "alice",
                    "activity": "development",
                    "date": "2026-07-25",
                    "duration": "2h",
                    "seconds": 7200,
                    "comment": "Implementation",
                    "source": "manual",
                    "timer_ref": None,
                    "corrects": None,
                    "event_id": "EV-BUG-1-000002",
                    "created_at": "2026-07-25T02:00:00Z",
                    "sequence": 1,
                    "line": 3,
                },
            ),
            (
                "ticket-activity-v1.schema.json",
                {
                    "schema": "ticket-activity-v1.schema.json",
                    "contract_version": "1",
                    "ticket": {"summary": {"id": "BUG-1", "title": "Bug", "status": "[/]"}, "fields": {}, "relations": {}},
                    "events": [],
                    "time_entries": [],
                    "time": {
                        "entry_count": 0,
                        "authoritative_seconds": 0,
                        "authoritative_duration": "0s",
                        "correction_seconds": 0,
                        "effective_entry_ids": [],
                        "superseded_entry_ids": [],
                        "legacy_elapsed": None,
                        "policy": "append-only time entries are authoritative when present",
                    },
                    "diagnostics": [],
                },
            ),
            (
                "ticket-version-v1.schema.json",
                {
                    "id": "VER-1",
                    "title": "v1.0",
                    "project": "web",
                    "state": "open",
                    "due": "2026-08-01",
                    "release": None,
                    "description": None,
                    "parent_version": None,
                    "ticket_ids": ["BUG-1"],
                    "open_ticket_ids": ["BUG-1"],
                    "ticket_count": 1,
                    "open_ticket_count": 1,
                    "warnings": [],
                    "source": "life.txt",
                    "line": 4,
                },
            ),
            (
                "ticket-sprint-v1.schema.json",
                {
                    "id": "SPR-1",
                    "title": "Sprint 1",
                    "project": "web",
                    "state": "active",
                    "start": "2026-07-20",
                    "end": "2026-08-02",
                    "goal": "Stabilize tickets",
                    "capacity": "20",
                    "version": "VER-1",
                    "ticket_ids": ["BUG-1"],
                    "open_ticket_ids": ["BUG-1"],
                    "ticket_count": 1,
                    "open_ticket_count": 1,
                    "story_points": 5,
                    "warnings": [],
                    "source": "life.txt",
                    "line": 5,
                },
            ),
            (
                "ticket-planning-v1.schema.json",
                {
                    "schema": "ticket-planning-v1.schema.json",
                    "contract_version": "1",
                    "project": "web",
                    "versions": [],
                    "sprints": [],
                    "backlog": [],
                    "diagnostics": [],
                    "caveats": [],
                },
            ),
        )
    )


def install_schema_extensions_v18():
    from . import release_policy, safety_foundation

    if getattr(release_policy, "_lifetxt_schema_extensions_v18", False):
        return
    original_bundle = safety_foundation.schema_bundle
    original_samples = release_policy._schema_samples

    def schema_bundle():
        result = OrderedDict(original_bundle())
        ticket = copy.deepcopy(result.get("ticket-v1.schema.json"))
        if ticket is not None:
            ticket.setdefault("properties", {})["activity"] = {"type": "object"}
            ticket.setdefault("properties", {})["planning"] = {"type": "object"}
            result["ticket-v1.schema.json"] = ticket
        result.update(schema_bundle_v18())
        return result

    def schema_samples():
        result = OrderedDict(original_samples())
        result.update(schema_samples_v18())
        return result

    safety_foundation.schema_bundle = schema_bundle
    release_policy.schema_bundle = schema_bundle
    release_policy._schema_samples = schema_samples
    release_policy._lifetxt_schema_extensions_v18 = True
