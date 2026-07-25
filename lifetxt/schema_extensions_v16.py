"""Schema registration for shared ticket/project reports."""

from __future__ import unicode_literals

from collections import OrderedDict

BASE = "https://github.com/Eruhitsuji/lifetxt/raw/main/dist/schemas/"
DRAFT = "https://json-schema.org/draft/2020-12/schema"


def _count_property():
    return {"type": "integer", "minimum": 0}


def _nullable_number():
    return {"type": ["number", "null"]}


def ticket_project_report_schema():
    attention_names = (
        "blocked", "dependency_unknown", "overdue", "unassigned", "high_severity", "stale"
    )
    summary_properties = OrderedDict(
        (name, _count_property())
        for name in (
            "total", "open", "terminal", "project_count", "blocked",
            "dependency_unknown", "overdue", "unassigned", "high_severity", "stale",
        )
    )
    summary_properties["progress_percent"] = {
        "type": ["number", "null"], "minimum": 0, "maximum": 100
    }
    project_properties = OrderedDict(
        (
            ("project", {"type": "string"}),
            ("total", _count_property()),
            ("open", _count_property()),
            ("terminal", _count_property()),
            ("progress_percent", {"type": ["number", "null"], "minimum": 0, "maximum": 100}),
            ("blocked", _count_property()),
            ("dependency_unknown", _count_property()),
            ("overdue", _count_property()),
            ("unassigned", _count_property()),
            ("high_severity", _count_property()),
            ("stale", _count_property()),
            ("by_status", {"$ref": "#/$defs/counts"}),
            ("by_priority", {"$ref": "#/$defs/counts"}),
            ("by_severity", {"$ref": "#/$defs/counts"}),
            ("by_tracker", {"$ref": "#/$defs/counts"}),
            ("by_assignee", {"$ref": "#/$defs/counts"}),
            ("by_component", {"$ref": "#/$defs/counts"}),
            ("estimate_hours", _nullable_number()),
            ("estimate_ticket_count", _count_property()),
            ("elapsed_hours", _nullable_number()),
            ("elapsed_ticket_count", _count_property()),
            ("paired_variance_hours", _nullable_number()),
            ("paired_variance_ticket_count", _count_property()),
        )
    )
    ticket_properties = OrderedDict(
        (
            ("id", {"type": "string"}),
            ("title", {"type": "string"}),
            ("project", {"type": "string"}),
            ("status", {"type": "string"}),
            ("tracker", {"type": "string"}),
            ("priority", {"type": "string"}),
            ("severity", {"type": "string"}),
            ("assignee", {"type": "string"}),
            ("reporter", {"type": "string"}),
            ("component", {"type": "string"}),
            ("due", {"type": "string"}),
            ("updated", {"type": "string"}),
            ("estimate_hours", _nullable_number()),
            ("elapsed_hours", _nullable_number()),
            ("depends_on", {"type": "array", "items": {"type": "string"}}),
            ("terminal", {"type": "boolean"}),
            ("blocked", {"type": "boolean"}),
            ("dependency_unknown", {"type": "boolean"}),
            ("unresolved_dependencies", {"type": "array", "items": {"type": "string"}}),
            ("unevaluated_dependencies", {"type": "array", "items": {"type": "string"}}),
            ("overdue", {"type": "boolean"}),
            ("unassigned", {"type": "boolean"}),
            ("high_severity", {"type": "boolean"}),
            ("stale", {"type": "boolean"}),
            ("variance_hours", _nullable_number()),
        )
    )
    ticket_array = {"type": "array", "items": {"$ref": "#/$defs/ticket"}}
    return {
        "$schema": DRAFT,
        "$id": BASE + "ticket-project-report-v1.schema.json",
        "title": "lifetxt ticket project report v1",
        "description": "Read-only ticket aggregation shared by project and portfolio surfaces.",
        "type": "object",
        "required": [
            "schema", "reference_time", "stale_after_days", "scope", "configuration",
            "summary", "projects", "board", "attention", "tickets", "formulas", "caveats",
        ],
        "properties": {
            "schema": {"const": "ticket-project-report-v1"},
            "reference_time": {"type": "string", "format": "date-time"},
            "stale_after_days": _count_property(),
            "scope": {
                "type": "object",
                "required": ["project"],
                "properties": {"project": {"type": ["string", "null"]}},
                "additionalProperties": False,
            },
            "configuration": {
                "type": "object",
                "required": ["terminal_statuses", "high_severities"],
                "properties": {
                    "terminal_statuses": {
                        "type": "array", "items": {"type": "string"}, "uniqueItems": True
                    },
                    "high_severities": {
                        "type": "array", "items": {"type": "string"}, "uniqueItems": True
                    },
                },
                "additionalProperties": False,
            },
            "summary": {"$ref": "#/$defs/summary"},
            "projects": {"type": "array", "items": {"$ref": "#/$defs/project"}},
            "board": {"type": "object", "additionalProperties": ticket_array},
            "attention": {
                "type": "object",
                "required": list(attention_names),
                "properties": OrderedDict((name, ticket_array) for name in attention_names),
                "additionalProperties": False,
            },
            "tickets": ticket_array,
            "formulas": {"type": "object", "additionalProperties": {"type": "string"}},
            "caveats": {"type": "array", "items": {"type": "string"}},
        },
        "$defs": {
            "counts": {
                "type": "object", "additionalProperties": {"type": "integer", "minimum": 0}
            },
            "summary": {
                "type": "object",
                "required": list(summary_properties.keys()),
                "properties": summary_properties,
                "additionalProperties": False,
            },
            "project": {
                "type": "object",
                "required": list(project_properties.keys()),
                "properties": project_properties,
                "additionalProperties": False,
            },
            "ticket": {
                "type": "object",
                "required": list(ticket_properties.keys()),
                "properties": ticket_properties,
                "additionalProperties": False,
            },
        },
        "additionalProperties": False,
    }


def schema_bundle_v16():
    return OrderedDict(
        (("ticket-project-report-v1.schema.json", ticket_project_report_schema()),)
    )


def schema_samples_v16():
    return OrderedDict(
        (
            (
                "ticket-project-report-v1.schema.json",
                {
                    "schema": "ticket-project-report-v1",
                    "reference_time": "2026-07-25T03:00:00+00:00",
                    "stale_after_days": 14,
                    "scope": {"project": None},
                    "configuration": {
                        "terminal_statuses": ["closed", "done"],
                        "high_severities": ["blocker", "critical"],
                    },
                    "summary": {
                        "total": 0, "open": 0, "terminal": 0,
                        "project_count": 0, "blocked": 0, "dependency_unknown": 0,
                        "overdue": 0, "unassigned": 0, "high_severity": 0,
                        "stale": 0, "progress_percent": None,
                    },
                    "projects": [],
                    "board": {},
                    "attention": {
                        "blocked": [], "dependency_unknown": [], "overdue": [],
                        "unassigned": [], "high_severity": [], "stale": [],
                    },
                    "tickets": [],
                    "formulas": {"open": "ticket status is not terminal"},
                    "caveats": [],
                },
            ),
        )
    )


def install_schema_extensions_v16():
    from . import release_policy, safety_foundation

    if getattr(release_policy, "_lifetxt_schema_extensions_v16", False):
        return
    original_bundle = safety_foundation.schema_bundle
    original_samples = release_policy._schema_samples

    def schema_bundle():
        result = OrderedDict(original_bundle())
        result.update(schema_bundle_v16())
        return result

    def schema_samples():
        result = OrderedDict(original_samples())
        result.update(schema_samples_v16())
        return result

    safety_foundation.schema_bundle = schema_bundle
    release_policy.schema_bundle = schema_bundle
    release_policy._schema_samples = schema_samples
    release_policy._lifetxt_schema_extensions_v16 = True
