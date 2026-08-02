"""Cross-surface integration for shared ticket/project reports.

The authoritative aggregation remains :mod:`lifetxt.ticket_project_report`.
This module only resolves effective configuration and installs adapters for the
main CLI, project/portfolio read models, MCP, and capability discovery.  Every
surface returns the same ``ticket-project-report-v1`` payload instead of
reimplementing counts or attention rules.
"""

from __future__ import unicode_literals

import argparse
import copy
import json
from collections import OrderedDict

from .ticket_project_report import build_ticket_project_report
from .ticket_project_values import (
    DEFAULT_HIGH_SEVERITIES,
    DEFAULT_STALE_DAYS,
    DEFAULT_TERMINAL_STATUSES,
    parse_datetime,
)
from .ticket_projects import format_attention, format_board, format_summary


_INSTALLED = False
_ORIGINALS = {}
_MCP_TOOL_NAMES = (
    "get_ticket_project_report",
    "get_ticket_board",
    "get_ticket_attention",
)


def _ticketing_section(config):
    config = config or {}
    section = config.get("ticketing") if isinstance(config, dict) else None
    return section if isinstance(section, dict) else {}


def _report_section(config):
    section = _ticketing_section(config)
    report = section.get("report")
    return report if isinstance(report, dict) else {}


def _string_values(value):
    if value in (None, ""):
        return []
    if isinstance(value, dict):
        source = value.keys()
    elif isinstance(value, (list, tuple, set, frozenset)):
        source = value
    else:
        source = str(value).split(",")
    result = []
    for entry in source:
        text = str(entry).strip()
        if text and text not in result:
            result.append(text)
    return result


def effective_terminal_statuses(config=None):
    """Detailed ticket statuses whose configured life status is terminal."""
    from .tickets import status_map

    values = [
        str(name)
        for name, life_status in status_map(config or {}).items()
        if str(life_status) in ("[x]", "[-]")
    ]
    return tuple(values or DEFAULT_TERMINAL_STATUSES)


def effective_high_severities(config=None):
    """High-attention severities from ticketing.report or ticketing."""
    section = _ticketing_section(config)
    report = _report_section(config)
    raw = report.get("high_severities")
    if raw in (None, ""):
        raw = section.get("high_severities")
    values = _string_values(raw)
    if values:
        return tuple(value.lower() for value in values)

    configured = section.get("severities")
    if isinstance(configured, dict):
        marked = []
        for name, metadata in configured.items():
            if isinstance(metadata, dict) and (
                metadata.get("high")
                or metadata.get("attention")
                or metadata.get("critical")
            ):
                marked.append(str(name).lower())
        if marked:
            return tuple(marked)
    return tuple(DEFAULT_HIGH_SEVERITIES)


def effective_stale_after_days(config=None):
    """Stale-ticket window shared by every integrated surface."""
    section = _ticketing_section(config)
    report = _report_section(config)
    raw = report.get("stale_after_days")
    if raw in (None, ""):
        raw = section.get("stale_after_days")
    if raw in (None, ""):
        return DEFAULT_STALE_DAYS
    if isinstance(raw, bool):
        raise ValueError("ticketing.report.stale_after_days must be an integer.")
    try:
        value = int(raw)
    except (TypeError, ValueError):
        raise ValueError("ticketing.report.stale_after_days must be an integer.")
    if value < 0:
        raise ValueError("ticketing.report.stale_after_days must be zero or greater.")
    return value


def effective_report_settings(config=None):
    return OrderedDict(
        (
            ("terminal_statuses", list(effective_terminal_statuses(config))),
            ("high_severities", list(effective_high_severities(config))),
            ("stale_after_days", effective_stale_after_days(config)),
        )
    )


def _canonical_project_map(config):
    from .projects import alias_map

    return alias_map(config or {})


def canonical_project_name(config, name):
    if name in (None, ""):
        return None
    text = str(name)
    return _canonical_project_map(config).get(text, text)


def _canonicalized_project_items(items, config):
    """Return shallow copies only where a project alias needs normalization."""
    mapping = _canonical_project_map(config)
    if not mapping:
        return list(items)
    normalized = []
    for item in items:
        projects = list(getattr(item, "details", {}).get("project") or [])
        canonical = [mapping.get(str(value), str(value)) for value in projects]
        if projects and canonical != [str(value) for value in projects]:
            cloned = copy.copy(item)
            cloned.details = OrderedDict(
                (key, list(values)) for key, values in item.details.items()
            )
            cloned.details["project"] = canonical
            normalized.append(cloned)
        else:
            normalized.append(item)
    return normalized


def build_configured_ticket_project_report(
    items,
    config=None,
    project=None,
    reference_time=None,
    stale_after_days=None,
    terminal_statuses=None,
    high_severities=None,
):
    """Build the shared report using one effective ticketing configuration."""
    config = config or {}
    canonical_project = canonical_project_name(config, project)
    return build_ticket_project_report(
        _canonicalized_project_items(items, config),
        reference_time=reference_time,
        stale_after_days=(
            effective_stale_after_days(config)
            if stale_after_days is None
            else int(stale_after_days)
        ),
        project=canonical_project,
        terminal_statuses=(
            effective_terminal_statuses(config)
            if terminal_statuses is None
            else tuple(terminal_statuses)
        ),
        high_severities=(
            effective_high_severities(config)
            if high_severities is None
            else tuple(high_severities)
        ),
    )


def ticket_project_contract(config=None):
    """Capability-discovery document for the read-only report contract."""
    return OrderedDict(
        (
            ("contract_version", "1"),
            ("schema", "ticket-project-report-v1.schema.json"),
            ("read_only", True),
            ("operations", ["summary", "board", "attention"]),
            (
                "cli",
                [
                    "ticket summary",
                    "ticket board",
                    "ticket attention",
                    "project tickets",
                ],
            ),
            ("mcp_tools", list(_MCP_TOOL_NAMES)),
            ("embedded_in", ["project_hub", "portfolio"]),
            ("configuration", effective_report_settings(config)),
            (
                "dependency_scope",
                "Dependencies absent from the selected report remain dependency_unknown.",
            ),
        )
    )


def _reference_value(value):
    if value in (None, ""):
        return None
    parsed = parse_datetime(value)
    if parsed is None:
        raise ValueError("--at/at must be an ISO date or datetime.")
    return parsed


def _override_values(values):
    result = []
    for value in values or []:
        result.extend(_string_values(value))
    return tuple(result) if result else None


def _report_from_namespace(args, cli_module, project=None):
    config = cli_module._config(args)
    items, diagnostics = cli_module._parse_or_exit(args.paths, config)
    cli_module._print_warnings(diagnostics)
    return build_configured_ticket_project_report(
        items,
        config=config,
        project=project if project is not None else getattr(args, "project", None),
        reference_time=_reference_value(getattr(args, "at", None)),
        stale_after_days=getattr(args, "stale_after", None),
        terminal_statuses=_override_values(getattr(args, "terminal_statuses", None)),
        high_severities=_override_values(getattr(args, "high_severities", None)),
    )


def _write_cli_report(args, cli_module, report, mode):
    if getattr(args, "format", "text") == "json":
        output = json.dumps(
            report,
            ensure_ascii=False,
            indent=2 if getattr(args, "pretty", False) else None,
            separators=None if getattr(args, "pretty", False) else (",", ":"),
        )
        cli_module.write_text(None, output + "\n")
    else:
        formatter = {
            "summary": format_summary,
            "board": format_board,
            "attention": format_attention,
        }[mode]
        cli_module.write_text(None, formatter(report))
    return 0


def _command_ticket_report(args):
    from . import cli as cli_module

    mode = getattr(args, "ticket_report_mode", "summary")
    report = _report_from_namespace(args, cli_module)
    return _write_cli_report(args, cli_module, report, mode)


def _command_project_tickets(args):
    from . import cli as cli_module

    mode = getattr(args, "view", "summary")
    report = _report_from_namespace(args, cli_module, project=args.name)
    return _write_cli_report(args, cli_module, report, mode)


def _subparsers_action(parser):
    for action in getattr(parser, "_actions", []):
        if isinstance(action, argparse._SubParsersAction):
            return action
    return None


def _add_common_cli_options(parser, cli_module, include_project=False):
    cli_module._add_input_paths(parser)
    if include_project:
        parser.add_argument(
            "--project", help="Restrict the report to one project or alias."
        )
    parser.add_argument(
        "--at", help="ISO reference date/datetime; defaults to the shared UTC clock."
    )
    parser.add_argument(
        "--stale-after",
        type=int,
        default=None,
        metavar="DAYS",
        help="Override ticketing.report.stale_after_days.",
    )
    parser.add_argument(
        "--terminal-status",
        action="append",
        dest="terminal_statuses",
        help="Override terminal statuses; repeat or use comma-separated values.",
    )
    parser.add_argument(
        "--high-severity",
        action="append",
        dest="high_severities",
        help="Override high severities; repeat or use comma-separated values.",
    )
    parser.add_argument("--format", choices=("text", "json"), default="text")
    parser.add_argument(
        "--pretty", action="store_true", help="Pretty-print JSON output."
    )


def _install_cli_commands(parser, cli_module):
    root = _subparsers_action(parser)
    if root is None:
        return parser

    ticket_parser = root.choices.get("ticket")
    if ticket_parser is not None:
        ticket_actions = _subparsers_action(ticket_parser)
        if ticket_actions is not None:
            for mode in ("summary", "board", "attention"):
                if mode in ticket_actions.choices:
                    continue
                report_parser = ticket_actions.add_parser(
                    mode,
                    help="Show the shared ticket/project %s report." % mode,
                )
                _add_common_cli_options(report_parser, cli_module, include_project=True)
                report_parser.set_defaults(
                    func=_command_ticket_report,
                    ticket_report_mode=mode,
                )

    project_parser = root.choices.get("project")
    if project_parser is not None:
        project_actions = _subparsers_action(project_parser)
        if project_actions is not None and "tickets" not in project_actions.choices:
            report_parser = project_actions.add_parser(
                "tickets",
                help="Show the shared development-ticket report for one project.",
            )
            report_parser.add_argument("name", help="Project name or configured alias.")
            _add_common_cli_options(report_parser, cli_module, include_project=False)
            report_parser.add_argument(
                "--view",
                choices=("summary", "board", "attention"),
                default="summary",
                help="Text view to render; JSON always returns the complete report.",
            )
            report_parser.set_defaults(func=_command_project_tickets)
    return parser


def _patch_cli():
    from . import cli as cli_module

    if "cli_build_parser" in _ORIGINALS:
        return
    original = cli_module.build_parser
    _ORIGINALS["cli_build_parser"] = original

    def build_parser():
        return _install_cli_commands(original(), cli_module)

    cli_module.build_parser = build_parser


def _patch_projects():
    from . import projects

    if "project_hub" in _ORIGINALS:
        return
    original_hub = projects.project_hub
    original_portfolio = projects.portfolio
    _ORIGINALS["project_hub"] = original_hub
    _ORIGINALS["portfolio"] = original_portfolio

    def project_hub(
        items,
        config=None,
        name=None,
        today=None,
        reference_time=None,
        stale_after_days=None,
        terminal_statuses=None,
        high_severities=None,
    ):
        result = OrderedDict(original_hub(items, config, name, today))
        result["ticket_report"] = build_configured_ticket_project_report(
            items,
            config=config,
            project=result.get("name") or name,
            reference_time=reference_time,
            stale_after_days=stale_after_days,
            terminal_statuses=terminal_statuses,
            high_severities=high_severities,
        )
        return result

    def portfolio(
        items,
        config=None,
        today=None,
        include_archived=False,
        reference_time=None,
        stale_after_days=None,
        terminal_statuses=None,
        high_severities=None,
    ):
        result = OrderedDict(original_portfolio(items, config, today, include_archived))
        report = build_configured_ticket_project_report(
            items,
            config=config,
            reference_time=reference_time,
            stale_after_days=stale_after_days,
            terminal_statuses=terminal_statuses,
            high_severities=high_severities,
        )
        by_project = dict((row["project"], row) for row in report.get("projects", []))
        rows = []
        for original_row in result.get("projects", []):
            row = OrderedDict(original_row)
            row["ticket_summary"] = by_project.get(row.get("name"))
            rows.append(row)
        result["projects"] = rows
        result["ticket_report"] = report
        return result

    projects.project_hub = project_hub
    projects.portfolio = portfolio


def _mcp_tool(name, description):
    return {
        "name": name,
        "description": description,
        "inputSchema": {
            "type": "object",
            "properties": {
                "project": {
                    "type": "string",
                    "description": "Optional project name or alias.",
                },
                "at": {
                    "type": "string",
                    "description": "Optional ISO reference date/datetime.",
                },
                "stale_after": {"type": "integer", "minimum": 0},
                "terminal_statuses": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional complete terminal-status override.",
                },
                "high_severities": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional complete high-severity override.",
                },
            },
            "additionalProperties": False,
        },
        "annotations": {
            "title": name.replace("_", " "),
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    }


def _mcp_report(arguments, context):
    from . import mcp

    items, _diagnostics = mcp._read_items(context)
    return build_configured_ticket_project_report(
        items,
        config=context.config,
        project=arguments.get("project"),
        reference_time=_reference_value(arguments.get("at")),
        stale_after_days=arguments.get("stale_after"),
        terminal_statuses=_override_values(arguments.get("terminal_statuses")),
        high_severities=_override_values(arguments.get("high_severities")),
    )


def _patch_mcp():
    from . import mcp

    if "mcp_tool_schemas" in _ORIGINALS:
        return
    original_schemas = mcp.tool_schemas
    _ORIGINALS["mcp_tool_schemas"] = original_schemas

    mcp.TOOL_HANDLERS.update(
        OrderedDict((name, _mcp_report) for name in _MCP_TOOL_NAMES)
    )
    mcp.READ_ONLY_TOOLS = frozenset(set(mcp.READ_ONLY_TOOLS) | set(_MCP_TOOL_NAMES))

    def tool_schemas():
        schemas = list(original_schemas())
        existing = set(schema.get("name") for schema in schemas)
        descriptions = {
            "get_ticket_project_report": "Return the complete shared ticket/project summary, board, attention, and ticket rows.",
            "get_ticket_board": "Return the complete shared report for deterministic status-board use.",
            "get_ticket_attention": "Return the complete shared report for blocked, overdue, stale, severity, and assignment attention use.",
        }
        for name in _MCP_TOOL_NAMES:
            if name not in existing:
                schemas.append(_mcp_tool(name, descriptions[name]))
        return schemas

    mcp.tool_schemas = tool_schemas


def _patch_capabilities():
    from . import safety_foundation, surface_runtime

    if "surface_capability_document_for" in _ORIGINALS:
        return
    original_for = surface_runtime.capability_document_for
    original_base = safety_foundation.capability_document
    _ORIGINALS["surface_capability_document_for"] = original_for
    _ORIGINALS["base_capability_document"] = original_base

    def enrich(data, config=None):
        result = OrderedDict(data)
        result["ticket_project_report"] = ticket_project_contract(config)
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


def install_ticket_project_surfaces():
    global _INSTALLED
    if _INSTALLED:
        return
    _patch_projects()
    _patch_cli()
    _patch_mcp()
    _patch_capabilities()
    _INSTALLED = True
