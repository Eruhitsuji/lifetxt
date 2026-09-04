"""Schemas for the daily command center and area summaries.

``revision`` (command-center-v1) is populated only when this shape is
returned by the MCP ``get_command_center`` tool (see #513); direct library
callers of :func:`lifetxt.command_center.command_center` do not set it.
"""

from __future__ import unicode_literals

from collections import OrderedDict

BASE = "https://github.com/Eruhitsuji/lifetxt/raw/main/dist/schemas/"
DRAFT = "https://json-schema.org/draft/2020-12/schema"


def schema_bundle_v7():
    item_ref = {"type": "array", "items": {"type": "object"}}
    counts = {
        "type": "object",
        "additionalProperties": {"type": "integer", "minimum": 0},
    }
    return OrderedDict(
        (
            (
                "command-center-v1.schema.json",
                {
                    "$schema": DRAFT,
                    "$id": BASE + "command-center-v1.schema.json",
                    "title": "lifetxt daily command center v1",
                    "type": "object",
                    "required": ["mode", "overdue", "due_today", "counts"],
                    "properties": {
                        "mode": {"type": "string"},
                        "reference_date": {"type": ["string", "null"]},
                        "horizon_days": {"type": "integer", "minimum": 0},
                        "person": {"type": ["string", "null"]},
                        "now": item_ref,
                        "today_events": item_ref,
                        "overdue": item_ref,
                        "due_today": item_ref,
                        "upcoming": item_ref,
                        "blocked": item_ref,
                        "waiting": item_ref,
                        "next_actions": item_ref,
                        "habits": item_ref,
                        "messages": item_ref,
                        "captures": item_ref,
                        "inbox": {
                            "type": "object",
                            "properties": {
                                "total": {"type": "integer", "minimum": 0},
                                "pending_count": {"type": "integer", "minimum": 0},
                                "deferred_count": {"type": "integer", "minimum": 0},
                                "counts": {
                                    "type": "object",
                                    "additionalProperties": {
                                        "type": "integer",
                                        "minimum": 0,
                                    },
                                },
                                "pending": {
                                    "type": "array",
                                    "items": {"type": "object"},
                                },
                            },
                            "additionalProperties": True,
                        },
                        "project_attention": {
                            "type": "array",
                            "items": {"type": "object"},
                        },
                        "ticket_attention": {
                            "type": "array",
                            "items": {"type": "object"},
                        },
                        "safety": {"type": "object"},
                        "counts": counts,
                        "revision": {"type": ["string", "null"]},
                    },
                    "additionalProperties": True,
                },
            ),
            (
                "area-summary-v1.schema.json",
                {
                    "$schema": DRAFT,
                    "$id": BASE + "area-summary-v1.schema.json",
                    "title": "lifetxt area summary v1",
                    "type": "object",
                    "required": ["name", "task_total", "task_done", "project_count"],
                    "properties": {
                        "name": {"type": "string"},
                        "task_total": {"type": "integer", "minimum": 0},
                        "task_done": {"type": "integer", "minimum": 0},
                        "task_open": {"type": "integer", "minimum": 0},
                        "progress_percent": {"type": ["number", "null"]},
                        "project_count": {"type": "integer", "minimum": 0},
                        "projects": {"type": "array", "items": {"type": "string"}},
                        "open_items": {"type": "array", "items": {"type": "object"}},
                    },
                    "additionalProperties": True,
                },
            ),
        )
    )


def schema_samples_v7():
    return OrderedDict(
        (
            (
                "command-center-v1.schema.json",
                {
                    "mode": "today",
                    "reference_date": "2026-07-24",
                    "horizon_days": 3,
                    "person": None,
                    "now": [
                        {
                            "person": "self",
                            "state": "focus",
                            "title": "self",
                            "since": "2026-07-24T08:00",
                        }
                    ],
                    "today_events": [
                        {"when": "2026-07-24T09:00", "title": "Standup", "kind": "E"}
                    ],
                    "overdue": [
                        {
                            "title": "Design",
                            "kind": "T",
                            "status": "[ ]",
                            "reason": "2 days overdue",
                        }
                    ],
                    "due_today": [],
                    "upcoming": [],
                    "blocked": [],
                    "waiting": [],
                    "next_actions": [{"title": "Design", "kind": "T", "status": "[ ]"}],
                    "habits": [],
                    "messages": [],
                    "captures": [],
                    "inbox": {
                        "total": 1,
                        "pending_count": 1,
                        "deferred_count": 0,
                        "counts": {
                            "pending": 1,
                            "accepted": 0,
                            "rejected": 0,
                            "deferred": 0,
                        },
                        "pending": [
                            {
                                "id": "P-1a2b3c4d",
                                "source": "manual",
                                "created": "2026-07-24T09:00:00",
                                "summary": "Review Q3 plan",
                            }
                        ],
                    },
                    "project_attention": [],
                    "ticket_attention": [],
                    "safety": {"config_errors": 0, "config_warnings": 0, "ok": True},
                    "counts": {
                        "now": 1,
                        "today_events": 1,
                        "overdue": 1,
                        "due_today": 0,
                        "next_actions": 1,
                        "inbox_pending": 1,
                    },
                    "revision": "3f1c2b9a4d5e6f708192a3b4c5d6e7f8091a2b3c4d5e6f708192a3b4c5d6e7f8",
                },
            ),
            (
                "area-summary-v1.schema.json",
                {
                    "name": "work",
                    "task_total": 5,
                    "task_done": 2,
                    "task_open": 3,
                    "progress_percent": 40.0,
                    "project_count": 2,
                    "projects": ["web", "mobile"],
                },
            ),
        )
    )


def install_schema_extensions_v7():
    from . import release_policy, safety_foundation

    if getattr(release_policy, "_lifetxt_schema_extensions_v7", False):
        return
    original_bundle = safety_foundation.schema_bundle
    original_samples = release_policy._schema_samples

    def schema_bundle():
        result = OrderedDict(original_bundle())
        result.update(schema_bundle_v7())
        return result

    def schema_samples():
        result = OrderedDict(original_samples())
        result.update(schema_samples_v7())
        return result

    safety_foundation.schema_bundle = schema_bundle
    release_policy.schema_bundle = schema_bundle
    release_policy._schema_samples = schema_samples
    release_policy._lifetxt_schema_extensions_v7 = True
