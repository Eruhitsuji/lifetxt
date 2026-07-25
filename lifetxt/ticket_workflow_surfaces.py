"""Read-only surface integration for ticket workflow, history, time, and planning."""
from __future__ import unicode_literals

from collections import OrderedDict

from .ticket_activity import (
    _first,
    event_view,
    iter_ticket_events,
    iter_time_entries,
    normalize_duration,
    ticket_activity_report,
    time_entry_view,
    validate_ticket_history,
)
from .ticket_planning import planning_report, validate_planning
from .ticket_workflow import workflow_contract

_INSTALLED = False
_ORIGINALS = {}
_MCP_TOOLS = (
    "get_ticket_workflow",
    "get_ticket_activity",
    "get_ticket_time",
    "get_ticket_planning",
    "validate_ticket_history",
    "validate_ticket_planning",
)


def _activity_summary(items, ticket_id):
    events = [event_view(item) for item in iter_ticket_events(items or [], ticket_id)]
    entries = [time_entry_view(item) for item in iter_time_entries(items or [], ticket_id)]
    events.sort(key=lambda row: (row["at"] or "", row["sequence"], row["id"] or ""))
    superseded = {str(row.get("corrects")) for row in entries if row.get("corrects")}
    effective = [row for row in entries if str(row.get("id")) not in superseded]
    seconds = sum(row["seconds"] or 0 for row in effective)
    return OrderedDict(
        (
            ("event_count", len(events)),
            ("latest_event", events[-1] if events else None),
            ("time_entry_count", len(entries)),
            ("time_logged_seconds", seconds),
            ("history_append_only", True),
            ("time_policy", "time entries authoritative when present; legacy elapsed remains separate"),
        )
    )


def ticket_workflow_history_contract(config=None):
    workflow = workflow_contract(config)
    return OrderedDict(
        (
            ("contract_version", "1"),
            (
                "schemas",
                [
                    "ticket-workflow-v1.schema.json",
                    "ticket-event-v1.schema.json",
                    "ticket-time-entry-v1.schema.json",
                    "ticket-activity-v1.schema.json",
                    "ticket-version-v1.schema.json",
                    "ticket-sprint-v1.schema.json",
                    "ticket-planning-v1.schema.json",
                ],
            ),
            (
                "cli",
                [
                    "ticket workflow",
                    "ticket transition",
                    "ticket comment",
                    "ticket watch",
                    "ticket unwatch",
                    "ticket reassign",
                    "ticket change",
                    "ticket activity",
                    "ticket log-time",
                    "ticket time",
                    "ticket validate-history",
                    "ticket plan",
                    "ticket backlog",
                    "ticket roadmap",
                    "ticket validate-planning",
                    "version new|list|show|lock|release|close|reopen",
                    "sprint new|list|show|start|close|reopen",
                ],
            ),
            ("mcp_tools", list(_MCP_TOOLS)),
            ("compound_scope", "same authoritative life.txt file"),
            ("exact_revision_required", True),
            ("ticket_event_required", True),
            ("events_append_only", True),
            ("time_entries_append_only", True),
            ("remote_writes_enabled", False),
            ("local_role", workflow["role"]),
            ("workflow_valid", workflow["valid"]),
            ("activities", workflow["activities"]),
            (
                "recovery",
                "same-file operations use one sidecar lock, one exact revision, one atomic replacement, and post-write verification",
            ),
            (
                "deferred",
                [
                    "cross-file ticket/event stores require revision sets and journal recovery",
                    "authenticated remote role enforcement",
                    "notification delivery side effects",
                    "timer-to-time-entry proposal integration",
                ],
            ),
        )
    )


def _patch_ticket_view():
    from . import tickets

    if "ticket_view" in _ORIGINALS:
        return
    original = tickets.ticket_view
    _ORIGINALS["ticket_view"] = original

    def ticket_view(item, config, items=None, key="id"):
        result = OrderedDict(original(item, config, items=items, key=key))
        ticket_id = str(tickets.ticket_id_of(item, key) or "")
        result["activity"] = _activity_summary(items or [], ticket_id)
        result["planning"] = OrderedDict(
            (
                ("version", _first(item, "version")),
                ("sprint", _first(item, "sprint")),
                ("story_points", _first(item, "story_points")),
            )
        )
        return result

    tickets.ticket_view = ticket_view
    try:
        from . import mcp
        if hasattr(mcp, "ticket_view"):
            mcp.ticket_view = ticket_view
    except Exception:
        pass


def _patch_capability():
    from . import safety_foundation, surface_runtime

    if "capability_for" in _ORIGINALS:
        return
    original_for = surface_runtime.capability_document_for
    original_base = safety_foundation.capability_document
    _ORIGINALS["capability_for"] = original_for
    _ORIGINALS["capability_base"] = original_base

    def enrich(value, config=None):
        result = OrderedDict(value)
        result["ticket_workflow_history"] = ticket_workflow_history_contract(config)
        return result

    def capability_document_for(
        surface,
        read_only=False,
        authentication="token",
        writable_targets=None,
        config=None,
    ):
        return enrich(
            original_for(
                surface,
                read_only=read_only,
                authentication=authentication,
                writable_targets=writable_targets,
                config=config,
            ),
            config=config,
        )

    def capability_document(
        read_only=False,
        authentication="token",
        writable_targets=None,
        config=None,
    ):
        return enrich(
            original_base(
                read_only=read_only,
                authentication=authentication,
                writable_targets=writable_targets,
                config=config,
            ),
            config=config,
        )

    surface_runtime.capability_document_for = capability_document_for
    safety_foundation.capability_document = capability_document


def _mcp_activity(args, context):
    from . import mcp

    items, _diagnostics = mcp._read_items(context)
    types = args.get("events") or args.get("event")
    if isinstance(types, str):
        types = [value.strip() for value in types.split(",") if value.strip()]
    return ticket_activity_report(
        items,
        str(args.get("id") or ""),
        config=context.config,
        key=mcp._id_key(context),
        event_types=types,
        limit=args.get("limit"),
    )


def _mcp_workflow(args, context):
    return workflow_contract(
        context.config,
        tracker=args.get("tracker"),
        project=args.get("project"),
        role=args.get("role"),
    )


def _mcp_time(args, context):
    report = _mcp_activity(args, context)
    return OrderedDict(
        (
            ("schema", report["schema"]),
            ("ticket_id", args.get("id")),
            ("time", report["time"]),
            ("entries", report["time_entries"]),
        )
    )


def _mcp_planning(args, context):
    from . import mcp

    items, _diagnostics = mcp._read_items(context)
    return planning_report(
        items,
        project=args.get("project"),
        config=context.config,
        key=mcp._id_key(context),
    )


def _mcp_validate_history(_args, context):
    from . import mcp

    items, _diagnostics = mcp._read_items(context)
    rows = validate_ticket_history(items, config=context.config, key=mcp._id_key(context))
    return {
        "ok": not any(row["severity"] == "error" for row in rows),
        "diagnostic_count": len(rows),
        "diagnostics": rows,
    }


def _mcp_validate_planning(_args, context):
    from . import mcp

    items, _diagnostics = mcp._read_items(context)
    rows = validate_planning(items, key=mcp._id_key(context))
    return {
        "ok": not any(row["severity"] == "error" for row in rows),
        "diagnostic_count": len(rows),
        "diagnostics": rows,
    }


def _patch_mcp():
    from . import mcp

    if "mcp_schemas" in _ORIGINALS:
        return
    original_schemas = mcp._tool_schemas
    _ORIGINALS["mcp_schemas"] = original_schemas

    def schemas():
        rows = list(original_schemas())
        existing = {row.get("name") for row in rows}
        additions = [
            mcp._tool(
                "get_ticket_workflow",
                "Return the effective versioned ticket workflow and role evaluation.",
                {
                    "tracker": mcp._string("Optional tracker context."),
                    "project": mcp._string("Optional project context."),
                    "role": mcp._string("Role to evaluate."),
                },
            ),
            mcp._tool(
                "get_ticket_activity",
                "Return append-only events, comments, transitions, and time entries for one ticket.",
                {
                    "id": mcp._string("Ticket ID."),
                    "events": mcp._string("Comma-separated event types."),
                    "limit": mcp._integer("Maximum newest events."),
                },
                required=["id"],
            ),
            mcp._tool(
                "get_ticket_time",
                "Return authoritative append-only time entries for one ticket.",
                {"id": mcp._string("Ticket ID.")},
                required=["id"],
            ),
            mcp._tool(
                "get_ticket_planning",
                "Return versions, sprints, backlog, warnings, and planning diagnostics.",
                {"project": mcp._string("Optional project filter.")},
            ),
            mcp._tool(
                "validate_ticket_history",
                "Validate event IDs, parent references, sequences, transactions, and time entries.",
                {},
            ),
            mcp._tool(
                "validate_ticket_planning",
                "Validate version/sprint records and ticket memberships.",
                {},
            ),
        ]
        rows.extend(row for row in additions if row.get("name") not in existing)
        return rows

    mcp._tool_schemas = schemas
    mcp.TOOL_HANDLERS.update(
        OrderedDict(
            (
                ("get_ticket_workflow", _mcp_workflow),
                ("get_ticket_activity", _mcp_activity),
                ("get_ticket_time", _mcp_time),
                ("get_ticket_planning", _mcp_planning),
                ("validate_ticket_history", _mcp_validate_history),
                ("validate_ticket_planning", _mcp_validate_planning),
            )
        )
    )
    mcp.READ_ONLY_TOOLS = frozenset(set(mcp.READ_ONLY_TOOLS) | set(_MCP_TOOLS))


def install_ticket_workflow_surfaces():
    global _INSTALLED
    if _INSTALLED:
        return
    _patch_ticket_view()
    _patch_mcp()
    _patch_capability()
    _INSTALLED = True
