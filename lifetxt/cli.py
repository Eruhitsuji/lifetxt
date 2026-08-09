import argparse
import contextlib
import datetime
import html
import hashlib
import io
import json
import os
import sys
import types
from collections import OrderedDict
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .atomic import atomic_write_bytes as _shared_atomic_write_bytes
from .atomic import atomic_write_text as _shared_atomic_write_text
from .config import (
    config_notification_recipient,
    config_paths,
    config_section,
    config_tag_aliases,
    config_template_text,
    config_team_aliases,
    config_team_members,
    config_templates,
    config_user_aliases,
    config_user_name,
    config_write_file,
    load_config,
)
from .agenda import (
    agenda_records,
    agenda_records_to_json,
    agenda_records_to_jsonl,
    agenda_records_to_life,
    filter_agenda_records,
    filter_items,
    format_match_time,
    format_agenda_table,
    parse_agenda_range,
    parse_optional_time_range,
    _format_table_row as _agenda_format_table_row,
    _table_cell as _agenda_table_cell,
    _first_detail_value,
    next_repeat_occurrence,
)
from .assist import (
    DETAIL_FLAGS,
    build_item_from_args,
    has_update_fields,
    item_to_assisted_line,
    prompt_item,
    update_text,
)
from .csvio import items_from_csv_text, items_to_csv
from .demo import DEFAULT_COUNT as DEMO_DEFAULT_COUNT
from .demo import demo_text, parse_demo_base_datetime, parse_demo_types
from .diagnostic_contract import (
    DIAGNOSTIC_CATEGORIES,
    diagnostic_category,
    diagnostic_to_output_dict,
)
from .ics import items_from_ics_text
from .ids import (
    auto_ids_enabled,
    collect_item_ids,
    duplicate_id_diagnostics,
    ensure_item_id,
    id_audit,
    id_key_from_config,
    id_prefix_for_item,
)
from .links import (
    dependency_blocker_records,
    dependency_chain_records,
    dependency_chains_to_dot,
    dependency_chains_to_mermaid,
    format_dependency_chain,
    format_link_table,
    link_records,
    links_to_dot,
    links_to_json,
    links_to_jsonl,
    links_to_mermaid,
    reference_diagnostics,
)
from .markdown import markdown_to_html, markdown_to_plain
from .model import Diagnostic, Item
from .timezone_policy import local_now_naive, today as timezone_today
from .timeutil import format_datetime, parse_date_or_datetime
from .notifier import (
    format_notification_email,
    format_notification_table,
    notification_email_subject,
    notification_records,
    records_to_json as notifications_to_json,
    records_to_jsonl as notifications_to_jsonl,
    watch_notifications,
)
from .parser import parse_directives, parse_line, parse_text
from .paths import expand_paths
from .serializer import (
    item_to_line,
    items_from_json_text,
    items_from_jsonl_text,
    items_to_json,
    items_to_jsonl,
)
from .status_summary import (
    format_status_table,
    latest_status_records,
    status_records_to_json,
    status_records_to_jsonl,
)
from .validator import validate_item


def main(argv=None):
    try:
        argv, config_path, workspace_name = _extract_config_arg(argv)
    except ValueError as exc:
        sys.stderr.write("ERROR: %s\n" % exc)
        return 1
    if argv and argv[0] == "fzf-preview":
        if len(argv) != 2:
            sys.stderr.write("ERROR: fzf-preview requires one token.\n")
            return 2
        from .fzf_helper import cmd_fzf_preview

        return cmd_fzf_preview(argparse.Namespace(token=argv[1]))
    parser = build_parser()
    args = parser.parse_args(argv)
    args.config = config_path
    args.workspace = workspace_name
    try:
        args.config_data = load_config(config_path)
    except ValueError as exc:
        sys.stderr.write("ERROR: %s\n" % exc)
        return 1
    try:
        _maybe_apply_workspace(args)
    except ValueError as exc:
        sys.stderr.write("ERROR: %s\n" % exc)
        return 1
    if not hasattr(args, "func"):
        parser.print_help()
        return 2
    try:
        return args.func(args)
    except ValueError as exc:
        sys.stderr.write("ERROR: %s\n" % exc)
        return 1


def _extract_config_arg(argv):
    if argv is None:
        raw = list(sys.argv[1:])
    else:
        raw = list(argv)

    config_path = None
    workspace_name = None
    cleaned = []
    index = 0
    while index < len(raw):
        value = raw[index]
        if value == "--config":
            if index + 1 >= len(raw):
                raise ValueError("--config requires a path.")
            config_path = raw[index + 1]
            index += 2
            continue
        if value.startswith("--config="):
            config_path = value.split("=", 1)[1]
            index += 1
            continue
        if value == "--workspace":
            if index + 1 >= len(raw):
                raise ValueError("--workspace requires a name.")
            workspace_name = raw[index + 1]
            index += 2
            continue
        if value.startswith("--workspace="):
            workspace_name = value.split("=", 1)[1]
            index += 1
            continue
        cleaned.append(value)
        index += 1
    return cleaned, config_path, workspace_name


def build_parser():
    from . import __version__

    parser = argparse.ArgumentParser(
        prog="python -m lifetxt",
        description="Parser, validator, converter, and input helper for life.txt.",
    )
    parser.add_argument(
        "--version",
        "-V",
        action="version",
        version="lifetxt %s" % __version__,
    )
    parser.add_argument(
        "--config",
        help="External JSON config file. May also be set with LIFETXT_CONFIG.",
    )
    parser.add_argument(
        "--workspace",
        help="Named workspace to resolve inputs and write target from.",
    )
    subparsers = parser.add_subparsers(dest="command")

    check = subparsers.add_parser("check", help="Check life.txt syntax and warnings.")
    _add_input_paths(check)
    check.add_argument(
        "--verify-files",
        action="store_true",
        help="Also verify file:/dir: content hashes. Reads every referenced file.",
    )
    check.add_argument(
        "--no-files",
        action="store_true",
        help="Skip file:/dir: attachment checks entirely.",
    )
    check.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="Diagnostic output format.",
    )
    check.add_argument(
        "--warnings-as-errors",
        action="store_true",
        help="Exit non-zero when warnings are present.",
    )
    check.add_argument(
        "--ignore",
        action="append",
        dest="ignore_codes",
        metavar="CODE",
        help="Suppress a diagnostic code, e.g. W225. Can be repeated or comma-separated.",
    )
    check.add_argument(
        "--severity",
        dest="diagnostic_severities",
        action="append",
        help="Only show diagnostics with this severity, such as error or warning. Can be repeated or comma-separated.",
    )
    check.add_argument(
        "--code",
        dest="diagnostic_codes",
        action="append",
        help="Only show diagnostics with this code, such as E010 or W213. Can be repeated or comma-separated.",
    )
    check.add_argument(
        "--category",
        dest="diagnostic_categories",
        action="append",
        help="Only show diagnostics in this category: %s. Can be repeated or comma-separated."
        % ", ".join(DIAGNOSTIC_CATEGORIES),
    )
    check.set_defaults(func=command_check)

    ids_command = subparsers.add_parser(
        "ids",
        help="Audit id details, missing IDs, and duplicate IDs.",
    )
    _add_input_paths(ids_command)
    ids_command.add_argument(
        "--key",
        help="Detail key to audit. Defaults to ids.key, api.id_key, or id.",
    )
    ids_command.add_argument(
        "--only",
        choices=("all", "present", "missing", "duplicates"),
        default="all",
        help="Limit the audit output. Defaults to all.",
    )
    ids_command.add_argument(
        "--format",
        choices=("text", "json", "jsonl"),
        default="text",
        help="Output format.",
    )
    ids_command.add_argument(
        "--pretty", action="store_true", help="Pretty-print JSON output."
    )
    ids_command.add_argument(
        "--assign",
        action="store_true",
        help="Assign IDs to items missing the selected ID key.",
    )
    ids_command.add_argument(
        "--dry-run",
        action="store_true",
        help="Show planned ID assignments without writing files.",
    )
    ids_command.add_argument(
        "--backup",
        action="store_true",
        help="Write a .bak backup before changing files with --assign.",
    )
    ids_command.add_argument(
        "--prefix",
        help="ID prefix to use with --assign. Defaults to the type-specific configured prefix.",
    )
    ids_command.set_defaults(func=command_ids)

    links_command = subparsers.add_parser(
        "links",
        help="Inspect id-based references such as parent:, ref:, depends_on:, blocks:, and related:.",
    )
    _add_input_paths(links_command)
    links_command.add_argument(
        "--id",
        dest="item_id",
        help="Show links connected to this id. Defaults to all links.",
    )
    links_command.add_argument(
        "--chain",
        metavar="ID",
        help="Show the dependency blocker chain for this item ID.",
    )
    links_command.add_argument(
        "--direction",
        choices=("incoming", "outgoing", "both"),
        default="both",
        help="Direction when --id is used. Defaults to both.",
    )
    links_command.add_argument(
        "--relation",
        action="append",
        help="Limit links to a relation key such as depends_on, blocks, parent, ref, or related. Can be repeated or comma-separated.",
    )
    links_command.add_argument(
        "--key",
        help="Detail key to use as the item ID. Defaults to ids.key, api.id_key, or id.",
    )
    links_command.add_argument(
        "--format",
        choices=("text", "json", "jsonl", "mermaid", "dot"),
        default="text",
        help="Output format.",
    )
    links_command.add_argument(
        "--pretty", action="store_true", help="Pretty-print JSON output."
    )
    links_command.set_defaults(func=command_links)

    sources_command = subparsers.add_parser(
        "sources",
        help="Report which source file owns each parsed item.",
    )
    _add_input_paths(sources_command)
    sources_command.add_argument(
        "--key",
        help="Detail key to display as the item ID. Defaults to ids.key, api.id_key, or id.",
    )
    sources_command.add_argument(
        "--missing-id",
        action="store_true",
        help="Only show items missing the selected ID key.",
    )
    sources_command.add_argument(
        "--format",
        choices=("text", "json", "jsonl"),
        default="text",
        help="Output format.",
    )
    sources_command.add_argument(
        "--pretty", action="store_true", help="Pretty-print JSON output."
    )
    sources_command.set_defaults(func=command_sources)

    to_json = subparsers.add_parser("to-json", help="Convert life.txt to JSON array.")
    _add_input_paths(to_json)
    to_json.add_argument("-o", "--output", help="Output file. Defaults to stdout.")
    to_json.add_argument("--pretty", action="store_true", help="Pretty-print JSON.")
    _add_item_filter_arguments(to_json)
    _add_occurrence_export_arguments(to_json)
    to_json.set_defaults(func=command_to_json)

    to_jsonl = subparsers.add_parser("to-jsonl", help="Convert life.txt to JSONL.")
    _add_input_paths(to_jsonl)
    to_jsonl.add_argument("-o", "--output", help="Output file. Defaults to stdout.")
    _add_item_filter_arguments(to_jsonl)
    _add_occurrence_export_arguments(to_jsonl)
    to_jsonl.set_defaults(func=command_to_jsonl)

    to_csv = subparsers.add_parser("to-csv", help="Convert life.txt to CSV.")
    _add_input_paths(to_csv)
    to_csv.add_argument("-o", "--output", help="Output file. Defaults to stdout.")
    _add_item_filter_arguments(to_csv)
    _add_occurrence_export_arguments(to_csv)
    to_csv.set_defaults(func=command_to_csv)

    demo = subparsers.add_parser(
        "demo",
        help="Generate a valid demo life.txt file.",
        description="Generate a valid demo life.txt file for testing CLI, Web UI, and API features.",
    )
    demo.add_argument(
        "-n",
        "--count",
        type=int,
        default=DEMO_DEFAULT_COUNT,
        help="Number of item records to generate. Defaults to %(default)s.",
    )
    demo.add_argument(
        "--date",
        help="Base date or datetime for generated records. Defaults to the current datetime.",
    )
    demo.add_argument(
        "--types",
        action="append",
        help="Comma-separated item types to generate, e.g. T,E,S,M,J. Defaults to all supported types.",
    )
    demo.add_argument(
        "--seed",
        type=int,
        default=1,
        help="Deterministic seed for demo variation. Defaults to %(default)s.",
    )
    demo.add_argument(
        "--project",
        default="demo",
        help="Project detail value for generated project-aware records. Defaults to %(default)s.",
    )
    demo.add_argument(
        "--person",
        action="append",
        help="Person name for generated assignee/attendee/sender/recipient/status records. Can be repeated.",
    )
    demo.add_argument(
        "--start-index",
        type=int,
        help="First numeric suffix for demo IDs. Defaults to 1, or the next demo ID when --append is used.",
    )
    demo.add_argument("-o", "--output", help="Output file. Defaults to stdout.")
    demo.add_argument(
        "--append",
        action="store_true",
        help="Append to --output instead of overwriting it.",
    )
    demo.add_argument(
        "--no-check",
        action="store_true",
        help="Skip validation of generated demo text before output.",
    )
    demo.set_defaults(func=command_demo)

    markdown_command = subparsers.add_parser(
        "markdown",
        help="Render the safe life.txt Markdown subset from selected fields.",
    )
    _add_input_paths(markdown_command)
    markdown_command.add_argument(
        "-o", "--output", help="Output file. Defaults to stdout."
    )
    markdown_command.add_argument(
        "--format",
        choices=("html", "text", "json", "jsonl"),
        default="html",
        help="Output format. Defaults to html.",
    )
    markdown_command.add_argument(
        "--field",
        action="append",
        help="Field to render: title, body, note, or all. Can be repeated or comma-separated. Defaults to body.",
    )
    markdown_command.add_argument(
        "--pretty", action="store_true", help="Pretty-print JSON output."
    )
    _add_item_filter_arguments(markdown_command)
    markdown_command.set_defaults(func=command_markdown)

    import_ics = subparsers.add_parser(
        "import-ics",
        help="Convert iCalendar .ics VEVENT entries to life.txt event items.",
    )
    _add_input_paths(import_ics)
    import_ics.add_argument("-o", "--output", help="Output file. Defaults to stdout.")
    import_ics.add_argument(
        "--append",
        action="store_true",
        help="Append to --output instead of overwriting it.",
    )
    import_ics.add_argument(
        "--project",
        help="Add this project: detail to every imported event.",
    )
    import_ics.add_argument(
        "--tag",
        action="append",
        default=[],
        help="Add this tag: detail to every imported event. Can be repeated.",
    )
    import_ics.add_argument(
        "--expand-rrule",
        action="store_true",
        help="Write one record per occurrence instead of a single record with repeat:RRULE:.",
    )
    import_ics.add_argument(
        "--expand-until",
        help="Expand occurrences up to this date. Defaults to one year out.",
    )
    import_ics.add_argument(
        "--expand-count",
        type=int,
        help="Maximum occurrences per recurring event. Capped at 500.",
    )
    import_ics.add_argument(
        "--preset",
        choices=("ics", "markdown", "todoist", "github"),
        default="ics",
        help=(
            "Source preset. Default 'ics' converts VEVENT entries; "
            "'markdown' imports Markdown task lists, 'todoist' imports Todoist CSV exports, "
            "and 'github' imports GitHub Issues JSON exports."
        ),
    )
    import_ics.set_defaults(func=command_import_ics)

    sync_ics = subparsers.add_parser(
        "sync-ics",
        help="Fetch iCalendar .ics URLs and write generated life.txt event items.",
    )
    sync_ics.add_argument(
        "--url",
        action="append",
        default=[],
        help="iCalendar URL to fetch. Can be repeated.",
    )
    sync_ics.add_argument(
        "--url-env",
        action="append",
        default=[],
        help="Environment variable containing an iCalendar URL. Can be repeated.",
    )
    sync_ics.add_argument("-o", "--output", help="Output file. Defaults to stdout.")
    sync_ics.add_argument(
        "--cache-dir",
        help="Directory for raw downloaded .ics snapshots.",
    )
    sync_ics.add_argument(
        "--dry-run",
        action="store_true",
        help="Fetch and print generated life.txt without writing output or cache files.",
    )
    sync_ics.add_argument(
        "--merge-existing",
        action="store_true",
        help="Merge generated events into the existing output file by id: instead of replacing the file.",
    )
    sync_ics.add_argument(
        "--soft-delete-missing",
        action="store_true",
        help="With --merge-existing, mark existing source:ics events missing from the feed as canceled.",
    )
    sync_ics.add_argument(
        "--project",
        help="Add this project: detail to every synced event.",
    )
    sync_ics.add_argument(
        "--tag",
        action="append",
        default=[],
        help="Add this tag: detail to every synced event. Can be repeated.",
    )
    sync_ics.add_argument(
        "--expand-rrule",
        action="store_true",
        help="Write one record per occurrence instead of a single record with repeat:RRULE:.",
    )
    sync_ics.add_argument(
        "--expand-until",
        help="Expand occurrences up to this date. Defaults to one year out.",
    )
    sync_ics.add_argument(
        "--expand-count",
        type=int,
        help="Maximum occurrences per recurring event. Capped at 500.",
    )
    sync_ics.add_argument(
        "--timeout",
        type=float,
        default=30.0,
        help="Fetch timeout in seconds. Defaults to 30.",
    )
    sync_ics.add_argument(
        "--user-agent",
        default="lifetxt/ics-sync",
        help="HTTP User-Agent header.",
    )
    sync_ics.set_defaults(func=command_sync_ics)

    serve = subparsers.add_parser(
        "serve",
        help="Run the optional FastAPI REST API and browser GUI.",
        description="Run the optional FastAPI REST API and browser GUI.",
    )
    serve.add_argument(
        "paths",
        nargs="*",
        metavar="path",
        help="life.txt file(s) to read. Defaults to life.txt.",
    )
    serve.add_argument(
        "--write-file",
        help="File used for create, update, and delete operations. Defaults to the first path.",
    )
    serve.add_argument("--host", help="Bind host.")
    serve.add_argument("--port", type=int, help="Bind port.")
    serve.add_argument(
        "--read-only",
        action="store_true",
        help="Disable all write endpoints (POST/PUT/DELETE) except /api/check-line. Safe for public deployments.",
    )
    serve.add_argument(
        "--token-env",
        metavar="ENVVAR",
        help="Read the API bearer token from ENVVAR instead of storing it in config.",
    )
    serve.add_argument(
        "--insecure-public",
        action="store_true",
        help="Allow a non-loopback writable Web server without a bearer token. Not recommended.",
    )
    serve.add_argument(
        "--mcp",
        action="store_true",
        help="Run the stdio MCP server instead of the FastAPI HTTP server.",
    )
    serve.set_defaults(func=command_serve)

    mcp = subparsers.add_parser(
        "mcp",
        help="Run the stdio MCP server for AI clients.",
        description="Run a JSON-RPC stdio MCP server exposing life.txt tools.",
    )
    mcp.add_argument(
        "paths",
        nargs="*",
        metavar="path",
        help="life.txt file(s) to read. Defaults to life.txt or config paths.",
    )
    mcp.add_argument(
        "--write-file",
        help="File used for create, update, and delete tools. Defaults to config write_file or the first path.",
    )
    mcp.add_argument(
        "--read-only",
        action="store_true",
        help="Disable MCP write tools.",
    )
    mcp.set_defaults(func=command_mcp)

    config_command = subparsers.add_parser(
        "config",
        help="Create or inspect an external JSON config file.",
    )
    config_subparsers = config_command.add_subparsers(dest="config_command")
    config_init = config_subparsers.add_parser(
        "init",
        help="Write a starter config file.",
    )
    config_init.add_argument(
        "-o",
        "--output",
        default=".lifetxt.json",
        help="Config file to write. Defaults to .lifetxt.json.",
    )
    config_init.add_argument(
        "--force",
        action="store_true",
        help="Overwrite the output file if it already exists.",
    )
    config_init.set_defaults(func=command_config_init)
    config_show = config_subparsers.add_parser(
        "show",
        help="Print the loaded config as JSON.",
    )
    config_show.set_defaults(func=command_config_show)

    config_effective = config_subparsers.add_parser(
        "effective",
        help="Print effective config after defaults, profile, and env precedence.",
    )
    config_effective.add_argument("--profile", help="Named profile to apply.")
    config_effective.set_defaults(func=command_config_effective)

    config_sources = config_subparsers.add_parser(
        "sources",
        help="Show each effective key with its value and provenance.",
    )
    config_sources.add_argument("--profile", help="Named profile to apply.")
    config_sources.add_argument(
        "--json", action="store_true", help="Emit machine-readable JSON rows."
    )
    config_sources.set_defaults(func=command_config_sources)

    config_get = config_subparsers.add_parser(
        "get", help="Print one effective value by dotted path (a.b.c)."
    )
    config_get.add_argument("path", help="Dotted config path, e.g. defaults.timezone.")
    config_get.add_argument("--profile", help="Named profile to apply.")
    config_get.set_defaults(func=command_config_get)

    config_set = config_subparsers.add_parser(
        "set", help="Set one config value by dotted path and write the file."
    )
    config_set.add_argument("path", help="Dotted config path, e.g. web.port.")
    config_set.add_argument("value", help="New value (parsed as JSON, else string).")
    config_set.add_argument(
        "-o", "--output", help="Config file to write. Defaults to the loaded file."
    )
    config_set.add_argument(
        "--expected-revision",
        help="Refuse the write unless the file still has this revision "
        "(see: lifetxt config revision).",
    )
    config_set.set_defaults(func=command_config_set)

    config_unset = config_subparsers.add_parser(
        "unset", help="Remove one config value by dotted path and write the file."
    )
    config_unset.add_argument("path", help="Dotted config path to remove.")
    config_unset.add_argument(
        "-o", "--output", help="Config file to write. Defaults to the loaded file."
    )
    config_unset.add_argument(
        "--expected-revision",
        help="Refuse the write unless the file still has this revision "
        "(see: lifetxt config revision).",
    )
    config_unset.set_defaults(func=command_config_unset)

    config_revision_cmd = config_subparsers.add_parser(
        "revision",
        help="Print the exact revision of the configuration file.",
    )
    config_revision_cmd.add_argument(
        "-o", "--output", help="Config file to inspect. Defaults to the loaded file."
    )
    config_revision_cmd.set_defaults(func=command_config_revision)

    config_explain = config_subparsers.add_parser(
        "explain", help="Explain a config key using the authoritative registry."
    )
    config_explain.add_argument("path", help="Dotted config path to explain.")
    config_explain.set_defaults(func=command_config_explain)

    config_check = config_subparsers.add_parser(
        "check", help="Validate the config against config-v1 and the credential policy."
    )
    config_check.add_argument("--json", action="store_true", help="Emit JSON.")
    config_check.set_defaults(func=command_config_check)

    config_migrate = config_subparsers.add_parser(
        "migrate",
        help="Migrate legacy paths/write_file into the versioned workspace model.",
    )
    config_migrate.add_argument(
        "--dry-run", action="store_true", help="Show changes without writing."
    )
    config_migrate.add_argument(
        "-o", "--output", help="Config file to write. Defaults to the loaded file."
    )
    config_migrate.add_argument(
        "--expected-revision",
        help="Refuse the write unless the file still has this revision "
        "(see: lifetxt config revision).",
    )
    config_migrate.set_defaults(func=command_config_migrate)

    workspace_command = subparsers.add_parser(
        "workspace",
        help="Inspect and validate named workspaces and their source manifests.",
    )
    workspace_subparsers = workspace_command.add_subparsers(dest="workspace_command")
    ws_list = workspace_subparsers.add_parser(
        "list", help="List configured workspaces."
    )
    ws_list.add_argument("--json", action="store_true", help="Emit JSON.")
    ws_list.set_defaults(func=command_workspace_list)

    ws_show = workspace_subparsers.add_parser(
        "show", help="Show one workspace's resolved source manifest."
    )
    ws_show.add_argument(
        "name", nargs="?", help="Workspace name. Defaults to the default workspace."
    )
    ws_show.add_argument("--json", action="store_true", help="Emit JSON.")
    ws_show.set_defaults(func=command_workspace_show)

    ws_files = workspace_subparsers.add_parser(
        "files", help="List the files a workspace resolves to."
    )
    ws_files.add_argument(
        "name", nargs="?", help="Workspace name. Defaults to the default workspace."
    )
    ws_files.add_argument(
        "--resolved",
        action="store_true",
        help="Show role, mode, origin, and resolved path for each file.",
    )
    ws_files.add_argument("--json", action="store_true", help="Emit JSON.")
    ws_files.set_defaults(func=command_workspace_files)

    ws_validate = workspace_subparsers.add_parser(
        "validate", help="Validate a workspace and report diagnostics."
    )
    ws_validate.add_argument(
        "name", nargs="?", help="Workspace name. Defaults to the default workspace."
    )
    ws_validate.add_argument(
        "--all", action="store_true", help="Validate every workspace."
    )
    ws_validate.add_argument("--json", action="store_true", help="Emit JSON.")
    ws_validate.set_defaults(func=command_workspace_validate)

    ws_doctor = workspace_subparsers.add_parser(
        "doctor", help="Aggregate health of every workspace and shared files."
    )
    ws_doctor.add_argument("--json", action="store_true", help="Emit JSON.")
    ws_doctor.set_defaults(func=command_workspace_doctor)

    project_command = subparsers.add_parser(
        "project",
        help="List, inspect, and manage projects built from project: records.",
    )
    project_subparsers = project_command.add_subparsers(dest="project_command")

    proj_list = project_subparsers.add_parser(
        "list", help="List projects with progress and health."
    )
    _add_input_paths(proj_list)
    proj_list.add_argument(
        "--all", action="store_true", help="Include archived projects."
    )
    proj_list.add_argument("--area", help="Only projects in this area.")
    proj_list.add_argument("--owner", help="Only projects with this owner.")
    proj_list.add_argument("--json", action="store_true", help="Emit JSON.")
    proj_list.set_defaults(func=command_project_list)

    proj_show = project_subparsers.add_parser(
        "show", help="Show one project's aggregated hub."
    )
    proj_show.add_argument("name", help="Project name.")
    _add_input_paths(proj_show)
    proj_show.add_argument("--json", action="store_true", help="Emit JSON.")
    proj_show.set_defaults(func=command_project_show)

    proj_health = project_subparsers.add_parser(
        "health", help="Show project health with formula."
    )
    proj_health.add_argument("name", nargs="?", help="Project name; omit with --all.")
    proj_health.add_argument(
        "--all", action="store_true", help="Health for every project."
    )
    _add_input_paths(proj_health)
    proj_health.add_argument("--json", action="store_true", help="Emit JSON.")
    proj_health.set_defaults(func=command_project_health)

    proj_timeline = project_subparsers.add_parser(
        "timeline", help="Show dated project items in order."
    )
    proj_timeline.add_argument("name", help="Project name.")
    _add_input_paths(proj_timeline)
    proj_timeline.add_argument("--json", action="store_true", help="Emit JSON.")
    proj_timeline.set_defaults(func=command_project_timeline)

    proj_workload = project_subparsers.add_parser(
        "workload", help="Show per-assignee workload."
    )
    proj_workload.add_argument("name", help="Project name.")
    _add_input_paths(proj_workload)
    proj_workload.add_argument("--json", action="store_true", help="Emit JSON.")
    proj_workload.set_defaults(func=command_project_workload)

    proj_risks = project_subparsers.add_parser(
        "risks", help="List project risks by severity."
    )
    proj_risks.add_argument("name", help="Project name.")
    _add_input_paths(proj_risks)
    proj_risks.add_argument("--json", action="store_true", help="Emit JSON.")
    proj_risks.set_defaults(func=command_project_risks)

    proj_new = project_subparsers.add_parser(
        "new", help="Append a project metadata record."
    )
    proj_new.add_argument("name", help="Project name.")
    proj_new.add_argument("--owner", help="Project owner.")
    proj_new.add_argument("--area", help="Project area.")
    proj_new.add_argument(
        "--state", default="active", help="Project state. Default active."
    )
    proj_new.add_argument("--due", help="Target/due date.")
    proj_new.add_argument("--start", help="Start date.")
    proj_new.add_argument("--visibility", help="Visibility classification.")
    proj_new.add_argument(
        "--to", help="File to append to. Defaults to the write target."
    )
    proj_new.add_argument(
        "--dry-run", action="store_true", help="Print the line without writing."
    )
    proj_new.set_defaults(func=command_project_new)

    proj_add = project_subparsers.add_parser(
        "add", help="Append a milestone/risk/decision/meeting record."
    )
    proj_add.add_argument(
        "record_type", choices=["milestone", "risk", "decision", "meeting"]
    )
    proj_add.add_argument("project", help="Project name.")
    proj_add.add_argument("title", help="Record title.")
    proj_add.add_argument("--due", help="Due date (milestone).")
    proj_add.add_argument(
        "--severity", default="medium", help="Risk severity. Default medium."
    )
    proj_add.add_argument("--state", default="open", help="Risk state. Default open.")
    proj_add.add_argument("--owner", help="Owner/assignee.")
    proj_add.add_argument("--on", help="Decision/meeting date.")
    proj_add.add_argument("--at", help="Meeting time.")
    proj_add.add_argument(
        "--to", help="File to append to. Defaults to the write target."
    )
    proj_add.add_argument(
        "--dry-run", action="store_true", help="Print the line without writing."
    )
    proj_add.set_defaults(func=command_project_add)

    proj_archive = project_subparsers.add_parser(
        "archive",
        help="Move a project's done/canceled records to the workspace's archive source.",
    )
    proj_archive.add_argument("name", help="Project name.")
    _add_input_paths(proj_archive)
    proj_archive.add_argument(
        "--dest",
        help="Archive file to append items to. Defaults to the active workspace's "
        "role: archive source.",
    )
    proj_archive.add_argument(
        "--revision",
        action="append",
        default=[],
        metavar="PATH=SHA256",
        help="Expected revision for a source or destination path. Can be repeated.",
    )
    proj_archive.add_argument(
        "--status",
        action="append",
        dest="statuses",
        metavar="STATUS",
        help=(
            "Only archive items with this status. Can be repeated or comma-separated. "
            "Defaults to done,canceled."
        ),
    )
    proj_archive.add_argument(
        "--before",
        metavar="DATE",
        help="Only archive items whose done: or updated: date is before DATE (YYYY-MM-DD).",
    )
    proj_archive.add_argument(
        "--max-items",
        type=int,
        dest="max_items",
        metavar="N",
        help="Maximum number of items to archive.",
    )
    proj_archive.add_argument(
        "--dry-run",
        action="store_true",
        dest="dry_run",
        help="Show which items would be archived without writing any changes.",
    )
    proj_archive.add_argument(
        "--copy",
        action="store_true",
        help="Copy items to the archive without removing them from the source file.",
    )
    proj_archive.add_argument(
        "--yes",
        action="store_true",
        help="Skip the confirmation prompt.",
    )
    proj_archive.add_argument(
        "--orphan-children",
        dest="orphan_children",
        choices=("block", "adopt", "promote"),
        default="block",
        help=(
            "How to handle open children of archived parents: "
            "block (default) refuses to archive, "
            "adopt archives open children together (marking them [-]), "
            "promote archives the parent only and removes parent: from orphaned children."
        ),
    )
    proj_archive.add_argument(
        "--preserve-structure",
        action="store_true",
        dest="preserve_structure",
        help=(
            "Copy comment lines and blank lines verbatim to both the archive file "
            "and the source remainder so section headings remain intact."
        ),
    )
    proj_archive.add_argument(
        "--block-on-external-refs",
        action="store_true",
        dest="block_on_external_refs",
        help=(
            "Treat cross-file or intra-file references to archived items as errors "
            "instead of warnings. Requires --dry-run or a live run to check."
        ),
    )
    proj_archive.set_defaults(func=command_project_archive)

    portfolio_command = subparsers.add_parser(
        "portfolio", help="Compare projects by state, progress, risk, and workload."
    )
    _add_input_paths(portfolio_command)
    portfolio_command.add_argument(
        "--all", action="store_true", help="Include archived projects."
    )
    portfolio_command.add_argument("--json", action="store_true", help="Emit JSON.")
    portfolio_command.set_defaults(func=command_portfolio)

    today_command = subparsers.add_parser(
        "today",
        help="Daily command center: overdue, due, blocked, messages, and project attention.",
    )
    _add_input_paths(today_command)
    today_command.add_argument(
        "--mode",
        choices=["today", "morning", "evening"],
        default="today",
        help="Brief mode label. Default today.",
    )
    today_command.add_argument(
        "--horizon", type=int, default=3, help="Upcoming horizon in days. Default 3."
    )
    today_command.add_argument(
        "--person", help="Scope unacknowledged messages to a recipient."
    )
    today_command.add_argument("--json", action="store_true", help="Emit JSON.")
    today_command.set_defaults(func=command_today)

    area_command = subparsers.add_parser(
        "area", help="Group tasks and projects by area:."
    )
    area_subparsers = area_command.add_subparsers(dest="area_command")
    area_list = area_subparsers.add_parser("list", help="List areas with progress.")
    _add_input_paths(area_list)
    area_list.add_argument("--json", action="store_true", help="Emit JSON.")
    area_list.set_defaults(func=command_area_list)
    area_show = area_subparsers.add_parser(
        "show", help="Show one area's projects and open work."
    )
    area_show.add_argument("name", help="Area name.")
    _add_input_paths(area_show)
    area_show.add_argument("--json", action="store_true", help="Emit JSON.")
    area_show.set_defaults(func=command_area_show)

    backlinks_command = subparsers.add_parser(
        "backlinks", help="Show items that reference a given ID (incoming links)."
    )
    backlinks_command.add_argument("id", help="Target item ID.")
    _add_input_paths(backlinks_command)
    backlinks_command.add_argument("--json", action="store_true", help="Emit JSON.")
    backlinks_command.set_defaults(func=command_backlinks)

    query_command = subparsers.add_parser(
        "query", help="Filter items with the shared query language."
    )
    query_command.add_argument(
        "query", help="Query string, e.g. 'open project:web due<2026-08-01'."
    )
    _add_input_paths(query_command)
    query_command.add_argument(
        "--sort", help="Sort key (line, due, status, title, ...)."
    )
    query_command.add_argument(
        "--order", default="asc", choices=["asc", "desc"], help="Sort order."
    )
    query_command.add_argument("--limit", type=int, help="Maximum items to return.")
    query_command.add_argument(
        "--format",
        default="life",
        choices=["life", "json", "jsonl", "table"],
        help="Output format.",
    )
    query_command.add_argument(
        "--pretty", action="store_true", help="Pretty-print JSON."
    )
    query_command.add_argument(
        "--canonical", action="store_true", help="Canonical life.txt output."
    )
    query_command.add_argument("--width", type=int, default=0, help="Table width.")
    query_command.add_argument(
        "-o", "--output", help="Write to a file instead of stdout."
    )
    query_command.set_defaults(func=command_query)

    view_command = subparsers.add_parser(
        "view", help="List, inspect, and run saved views (named queries)."
    )
    view_subparsers = view_command.add_subparsers(dest="view_command")
    view_list = view_subparsers.add_parser("list", help="List saved views.")
    view_list.add_argument("--json", action="store_true", help="Emit JSON.")
    view_list.set_defaults(func=command_view_list)
    view_show = view_subparsers.add_parser(
        "show", help="Show one saved view definition."
    )
    view_show.add_argument("name", help="Saved view name.")
    view_show.add_argument("--json", action="store_true", help="Emit JSON.")
    view_show.set_defaults(func=command_view_show)
    view_validate = view_subparsers.add_parser(
        "validate", help="Validate saved view queries."
    )
    view_validate.add_argument("--json", action="store_true", help="Emit JSON.")
    view_validate.set_defaults(func=command_view_validate)
    view_run = view_subparsers.add_parser("run", help="Run a saved view.")
    view_run.add_argument("name", help="Saved view name.")
    _add_input_paths(view_run)
    view_run.add_argument(
        "--format",
        default="life",
        choices=["life", "json", "jsonl", "table"],
        help="Output format.",
    )
    view_run.add_argument("--pretty", action="store_true", help="Pretty-print JSON.")
    view_run.add_argument(
        "--canonical", action="store_true", help="Canonical life.txt output."
    )
    view_run.add_argument("--width", type=int, default=0, help="Table width.")
    view_run.add_argument("-o", "--output", help="Write to a file instead of stdout.")
    view_run.set_defaults(func=command_view_run)

    group_command = subparsers.add_parser(
        "group", help="Inspect and validate messaging groups."
    )
    group_subparsers = group_command.add_subparsers(dest="group_command")
    group_list = group_subparsers.add_parser(
        "list", help="List groups with member counts."
    )
    group_list.add_argument("--json", action="store_true", help="Emit JSON.")
    group_list.set_defaults(func=command_group_list)
    group_show = group_subparsers.add_parser(
        "show", help="Show one group's resolved members."
    )
    group_show.add_argument("name", help="Group name.")
    group_show.add_argument("--json", action="store_true", help="Emit JSON.")
    group_show.set_defaults(func=command_group_show)
    group_validate = group_subparsers.add_parser(
        "validate", help="Validate all groups."
    )
    group_validate.add_argument("--json", action="store_true", help="Emit JSON.")
    group_validate.set_defaults(func=command_group_validate)

    message_command = subparsers.add_parser(
        "message", help="Compose messages and inspect recipients and delivery state."
    )
    message_subparsers = message_command.add_subparsers(dest="message_command")

    msg_recipients = message_subparsers.add_parser(
        "recipients", help="Preview the resolved recipient set for references."
    )
    msg_recipients.add_argument("to", help="Comma-separated people/teams/groups.")
    msg_recipients.add_argument("--json", action="store_true", help="Emit JSON.")
    msg_recipients.set_defaults(func=command_message_recipients)

    msg_send = message_subparsers.add_parser(
        "send", help="Append a message item with resolved recipients."
    )
    msg_send.add_argument("title", help="Message title.")
    msg_send.add_argument(
        "--sender", help="Sender person. Defaults to the config user."
    )
    msg_send.add_argument(
        "--to", required=True, help="Comma-separated people/teams/groups."
    )
    msg_send.add_argument(
        "--ack-policy",
        default="any",
        help="Acknowledgement policy: any, all, or a count.",
    )
    msg_send.add_argument("--body", help="Message body.")
    msg_send.add_argument(
        "--output", help="File to append to. Defaults to the write target."
    )
    msg_send.add_argument(
        "--dry-run", action="store_true", help="Print the line without writing."
    )
    msg_send.set_defaults(func=command_message_send)

    msg_status = message_subparsers.add_parser(
        "status", help="Show per-recipient delivery state."
    )
    msg_status.add_argument("--id", help="Restrict to one message ID.")
    _add_input_paths(msg_status)
    msg_status.add_argument("--policy", help="Override the acknowledgement policy.")
    msg_status.add_argument("--json", action="store_true", help="Emit JSON.")
    msg_status.set_defaults(func=command_message_status)

    person_command = subparsers.add_parser(
        "person",
        help="Overview of a person's work, messages, meetings, and memberships.",
    )
    person_subparsers = person_command.add_subparsers(dest="person_command")
    person_list = person_subparsers.add_parser("list", help="List people with counts.")
    _add_input_paths(person_list)
    person_list.add_argument("--json", action="store_true", help="Emit JSON.")
    person_list.set_defaults(func=command_person_list)
    person_show = person_subparsers.add_parser(
        "show", help="Show one person's overview."
    )
    person_show.add_argument("name", help="Person name or alias.")
    _add_input_paths(person_show)
    person_show.add_argument("--json", action="store_true", help="Emit JSON.")
    person_show.set_defaults(func=command_person_show)
    person_group = person_subparsers.add_parser(
        "group", help="Overview of a group's members."
    )
    person_group.add_argument("name", help="Group name.")
    _add_input_paths(person_group)
    person_group.add_argument("--json", action="store_true", help="Emit JSON.")
    person_group.set_defaults(func=command_person_group)

    proposal_command = subparsers.add_parser(
        "proposal",
        help="Unified Inbox: review, edit, accept, or reject staged proposals.",
    )
    proposal_subparsers = proposal_command.add_subparsers(dest="proposal_command")

    prop_list = proposal_subparsers.add_parser("list", help="List staged proposals.")
    prop_list.add_argument(
        "--status",
        choices=["pending", "accepted", "rejected", "deferred"],
        help="Filter by status.",
    )
    prop_list.add_argument("--json", action="store_true", help="Emit JSON.")
    prop_list.set_defaults(func=command_proposal_list)

    prop_add = proposal_subparsers.add_parser("add", help="Stage a create proposal.")
    prop_add.add_argument("title", help="Item title.")
    prop_add.add_argument("--kind", default="T", help="Item type. Default T.")
    prop_add.add_argument("--project", help="project: value.")
    prop_add.add_argument("--due", help="due: value.")
    prop_add.add_argument("--assignee", help="assignee: value.")
    prop_add.add_argument("--priority", help="priority: value.")
    prop_add.add_argument("--tag", action="append", help="tag: value (repeatable).")
    prop_add.add_argument(
        "--source", default="manual", help="Proposal source. Default manual."
    )
    prop_add.set_defaults(func=command_proposal_add)

    prop_show = proposal_subparsers.add_parser("show", help="Show one proposal.")
    prop_show.add_argument("id", help="Proposal ID.")
    prop_show.set_defaults(func=command_proposal_show)

    prop_edit = proposal_subparsers.add_parser("edit", help="Edit a pending proposal.")
    prop_edit.add_argument("id", help="Proposal ID.")
    prop_edit.add_argument("--title", help="New title.")
    prop_edit.add_argument("--kind", help="New type.")
    prop_edit.add_argument("--project", help="project: value.")
    prop_edit.add_argument("--due", help="due: value.")
    prop_edit.add_argument("--assignee", help="assignee: value.")
    prop_edit.add_argument("--priority", help="priority: value.")
    prop_edit.set_defaults(func=command_proposal_edit)

    prop_accept = proposal_subparsers.add_parser(
        "accept", help="Accept and append a proposal."
    )
    prop_accept.add_argument("ids", nargs="+", help="Proposal ID(s).")
    prop_accept.add_argument("--to", help="Target file. Defaults to the write target.")
    prop_accept.set_defaults(func=command_proposal_accept)

    prop_reject = proposal_subparsers.add_parser("reject", help="Reject a proposal.")
    prop_reject.add_argument("id", help="Proposal ID.")
    prop_reject.set_defaults(func=command_proposal_reject)

    prop_defer = proposal_subparsers.add_parser("defer", help="Defer a proposal.")
    prop_defer.add_argument("id", help="Proposal ID.")
    prop_defer.set_defaults(func=command_proposal_defer)

    find_command = subparsers.add_parser(
        "find",
        help="Global search across items, projects, people, groups, areas, and proposals.",
    )
    find_command.add_argument("term", help="Case-insensitive search term.")
    _add_input_paths(find_command)
    find_command.add_argument(
        "--type",
        dest="types",
        action="append",
        help="Limit to an entity type (item, project, person, group, area, proposal). Repeatable.",
    )
    find_command.add_argument(
        "--limit", type=int, help="Maximum results per entity type."
    )
    find_command.add_argument("--json", action="store_true", help="Emit JSON.")
    find_command.set_defaults(func=command_find)

    ticket_command = subparsers.add_parser(
        "ticket",
        help="Development tickets (record:ticket): new, list, show, edit, transitions, links.",
    )
    ticket_subparsers = ticket_command.add_subparsers(dest="ticket_command")

    tk_new = ticket_subparsers.add_parser("new", help="Create a ticket.")
    tk_new.add_argument("subject", help="Ticket subject.")
    tk_new.add_argument("--tracker", help="Tracker (bug, feature, task, support).")
    tk_new.add_argument("--priority", help="Priority.")
    tk_new.add_argument("--severity", help="Severity.")
    tk_new.add_argument("--assignee", help="Assignee.")
    tk_new.add_argument("--reporter", help="Reporter.")
    tk_new.add_argument("--component", help="Component.")
    tk_new.add_argument("--version", help="Target version.")
    tk_new.add_argument("--sprint", help="Sprint.")
    tk_new.add_argument("--project", help="Project.")
    tk_new.add_argument("--due", help="Due date.")
    tk_new.add_argument("--est", help="Estimate.")
    tk_new.add_argument(
        "--status", default="new", help="Initial ticket_status. Default new."
    )
    tk_new.add_argument("--watcher", action="append", help="Watcher (repeatable).")
    tk_new.add_argument(
        "--id", help="Explicit ticket id. Defaults to the next generated id."
    )
    tk_new.add_argument("--to", help="Target file. Defaults to the write target.")
    tk_new.add_argument(
        "--dry-run", action="store_true", help="Print the line without writing."
    )
    _add_input_paths(tk_new)
    tk_new.set_defaults(func=command_ticket_new)

    tk_list = ticket_subparsers.add_parser("list", help="List tickets.")
    _add_input_paths(tk_list)
    for flag in (
        "tracker",
        "status",
        "priority",
        "severity",
        "assignee",
        "component",
        "version",
        "sprint",
        "project",
    ):
        tk_list.add_argument("--%s" % flag, help="Filter by %s." % flag)
    tk_list.add_argument(
        "--open", dest="open_only", action="store_true", help="Only open tickets."
    )
    tk_list.add_argument("--json", action="store_true", help="Emit JSON.")
    tk_list.set_defaults(func=command_ticket_list)

    tk_show = ticket_subparsers.add_parser(
        "show", help="Show one ticket with relations."
    )
    tk_show.add_argument("id", help="Ticket id.")
    _add_input_paths(tk_show)
    tk_show.add_argument("--json", action="store_true", help="Emit JSON.")
    tk_show.set_defaults(func=command_ticket_show)

    tk_edit = ticket_subparsers.add_parser("edit", help="Set or unset ticket fields.")
    tk_edit.add_argument("id", help="Ticket id.")
    tk_edit.add_argument(
        "--set",
        dest="set_fields",
        action="append",
        metavar="KEY=VALUE",
        help="Set a field (repeatable).",
    )
    tk_edit.add_argument(
        "--unset", action="append", metavar="KEY", help="Remove a field (repeatable)."
    )
    _add_input_paths(tk_edit)
    tk_edit.add_argument(
        "--dry-run", action="store_true", help="Preview without writing."
    )
    tk_edit.set_defaults(func=command_ticket_edit)

    tk_assign = ticket_subparsers.add_parser("assign", help="Assign a ticket.")
    tk_assign.add_argument("id", help="Ticket id.")
    tk_assign.add_argument("assignee", help="Assignee person.")
    _add_input_paths(tk_assign)
    tk_assign.set_defaults(func=command_ticket_assign)

    tk_close = ticket_subparsers.add_parser("close", help="Close/resolve a ticket.")
    tk_close.add_argument("id", help="Ticket id.")
    tk_close.add_argument(
        "--status",
        default="closed",
        help="Terminal status: closed, resolved, rejected, duplicate, wont_fix.",
    )
    tk_close.add_argument("--resolution", help="Resolution note.")
    tk_close.add_argument(
        "--by", help="Actor recorded as closed_by. Defaults to config user."
    )
    _add_input_paths(tk_close)
    tk_close.set_defaults(func=command_ticket_close)

    tk_reopen = ticket_subparsers.add_parser("reopen", help="Reopen a ticket.")
    tk_reopen.add_argument("id", help="Ticket id.")
    tk_reopen.add_argument(
        "--status", default="new", help="Reopen status. Default new."
    )
    _add_input_paths(tk_reopen)
    tk_reopen.set_defaults(func=command_ticket_reopen)

    tk_link = ticket_subparsers.add_parser("link", help="Add a relation to a ticket.")
    tk_link.add_argument("id", help="Ticket id.")
    tk_link.add_argument(
        "relation",
        choices=[
            "parent",
            "depends_on",
            "blocks",
            "related",
            "duplicate_of",
            "replaced_by",
        ],
    )
    tk_link.add_argument("target", help="Target id.")
    _add_input_paths(tk_link)
    tk_link.set_defaults(func=command_ticket_link)

    tk_unlink = ticket_subparsers.add_parser(
        "unlink", help="Remove a relation from a ticket."
    )
    tk_unlink.add_argument("id", help="Ticket id.")
    tk_unlink.add_argument(
        "relation",
        choices=[
            "parent",
            "depends_on",
            "blocks",
            "related",
            "duplicate_of",
            "replaced_by",
        ],
    )
    tk_unlink.add_argument("target", help="Target id to remove.")
    _add_input_paths(tk_unlink)
    tk_unlink.set_defaults(func=command_ticket_unlink)

    tk_validate = ticket_subparsers.add_parser("validate", help="Validate all tickets.")
    _add_input_paths(tk_validate)
    tk_validate.add_argument("--json", action="store_true", help="Emit JSON.")
    tk_validate.set_defaults(func=command_ticket_validate)

    tui = subparsers.add_parser(
        "tui",
        help="Run a terminal dashboard for tasks, agenda, and status.",
    )
    tui.add_argument(
        "paths",
        nargs="*",
        metavar="path",
        help="life.txt file(s) to read. Defaults to config paths or life.txt.",
    )
    tui.add_argument(
        "--theme",
        choices=("auto", "dark", "light", "mono"),
        help="TUI color theme. Defaults to config tui.theme or auto.",
    )
    tui.add_argument(
        "--keymap",
        choices=("prompt", "vim", "arrows"),
        help="TUI keymap preset. prompt keeps the input bar focused; vim uses single-key navigation. Defaults to config tui.keymap or prompt.",
    )
    tui.add_argument(
        "--glyphs",
        choices=("auto", "unicode", "ascii"),
        help="Box-drawing character set. Defaults to config tui.glyphs or auto.",
    )
    tui.add_argument(
        "--plain",
        action="store_true",
        help="Print one plain-text dashboard snapshot instead of running the interactive workspace.",
    )
    tui.add_argument(
        "--limit",
        type=int,
        help="Maximum rows per TUI section. Defaults to config tui.limit or 10.",
    )
    tui.add_argument(
        "--agenda-window",
        help="Agenda window around now, such as 6h, 12h, 1d. Defaults to config tui.agenda_window or 12h.",
    )
    tui.set_defaults(func=command_tui)

    fzf = subparsers.add_parser(
        "fzf",
        help="Select filtered items with fzf or peco and run an action.",
    )
    _add_input_paths(fzf)
    _add_item_filter_arguments(fzf)
    fzf.add_argument(
        "--action",
        choices=("done", "edit", "delete", "show"),
        help="Action to run on selected items. Defaults to an interactive prompt.",
    )
    fzf.add_argument(
        "--tool",
        choices=("fzf", "peco"),
        help="Selection tool. Defaults to fzf or peco from PATH.",
    )
    fzf.add_argument(
        "--preview",
        dest="preview",
        action="store_true",
        default=True,
        help="Enable fzf preview. This is the default.",
    )
    fzf.add_argument(
        "--no-preview",
        dest="preview",
        action="store_false",
        help="Disable fzf preview.",
    )
    fzf.add_argument(
        "--print-query",
        action="store_true",
        help="Print only the fzf query string.",
    )
    fzf.set_defaults(func=command_fzf)

    timer = subparsers.add_parser(
        "timer",
        help="Start, stop, inspect, or summarize a single task timer.",
    )
    timer_subparsers = timer.add_subparsers(dest="timer_command")
    timer_start = timer_subparsers.add_parser(
        "start", help="Start a timer for an item ID."
    )
    timer_start.add_argument("path", help="life.txt file containing the item.")
    timer_start.add_argument(
        "--id", dest="item_id", required=True, help="Item ID to time."
    )
    timer_start.add_argument("--note", help="Optional note stored in timer state.")
    timer_start.add_argument(
        "--item-revision", help="Expected SHA-256 revision of life.txt."
    )
    timer_start.add_argument(
        "--timer-revision",
        help="Expected timer-state revision; use <missing> when idle.",
    )
    timer_start.set_defaults(func=command_timer)
    timer_pause = timer_subparsers.add_parser("pause", help="Pause the running timer.")
    timer_pause.add_argument(
        "--timer-revision", help="Expected timer-state SHA-256 revision."
    )
    timer_pause.set_defaults(func=command_timer)
    timer_resume = timer_subparsers.add_parser("resume", help="Resume a paused timer.")
    timer_resume.add_argument(
        "--timer-revision", help="Expected timer-state SHA-256 revision."
    )
    timer_resume.set_defaults(func=command_timer)
    timer_stop = timer_subparsers.add_parser("stop", help="Stop the running timer.")
    timer_stop.add_argument(
        "path",
        nargs="?",
        help="life.txt file. Defaults to the file stored in timer state.",
    )
    timer_stop.add_argument("--id", dest="item_id", help="Expected running item ID.")
    timer_stop.add_argument(
        "--item-revision", help="Expected SHA-256 revision of life.txt."
    )
    timer_stop.add_argument(
        "--timer-revision", help="Expected timer-state SHA-256 revision."
    )
    timer_stop.set_defaults(func=command_timer)
    timer_status = timer_subparsers.add_parser("status", help="Show the running timer.")
    timer_status.add_argument(
        "paths",
        nargs="*",
        metavar="path",
        help="Optional life.txt files used to resolve the title.",
    )
    timer_status.set_defaults(func=command_timer)
    timer_summary = timer_subparsers.add_parser(
        "summary", help="Summarize elapsed: details."
    )
    timer_summary.add_argument(
        "paths", nargs="+", metavar="path", help="life.txt file(s) to summarize."
    )
    timer_summary.add_argument("--from", dest="start", help="Start date or datetime.")
    timer_summary.add_argument("--to", dest="end", help="End date or datetime.")
    timer_summary.add_argument("--project", help="Filter by project.")
    timer_summary.add_argument(
        "--format", choices=("text", "json"), default="text", help="Output format."
    )
    timer_summary.set_defaults(func=command_timer)
    timer_cancel = timer_subparsers.add_parser(
        "cancel", help="Cancel the running timer without updating an item."
    )
    timer_cancel.add_argument(
        "--timer-revision", help="Expected timer-state SHA-256 revision."
    )
    timer_cancel.set_defaults(func=command_timer)

    stats = subparsers.add_parser(
        "stats",
        help="Show task, habit, mood, and project statistics.",
    )
    _add_input_paths(stats)
    stats.add_argument(
        "--from", dest="start", help="Start date. Defaults to 29 days before --to."
    )
    stats.add_argument("--to", dest="end", help="End date. Defaults to today.")
    _add_item_filter_arguments(stats)
    stats.add_argument(
        "--group",
        choices=("daily", "weekly", "monthly"),
        default="daily",
        help="Aggregation bucket size.",
    )
    stats.add_argument(
        "--format", choices=("text", "json"), default="text", help="Output format."
    )
    stats.add_argument(
        "--width", type=int, help="Render text output for a specific terminal width."
    )
    stats.set_defaults(func=command_stats)

    git_hook = subparsers.add_parser(
        "git-hook",
        help="Install, uninstall, or inspect lifetxt Git hooks.",
    )
    git_hook_subparsers = git_hook.add_subparsers(dest="git_hook_command")
    git_hook_install = git_hook_subparsers.add_parser(
        "install", help="Install Git hooks."
    )
    git_hook_install.add_argument(
        "--repo-dir",
        default=".",
        help="Git repository root. Defaults to current directory.",
    )
    git_hook_install.add_argument(
        "--files", nargs="*", help="life.txt files checked by hooks."
    )
    git_hook_install.add_argument(
        "--no-commit-msg", action="store_true", help="Do not install commit-msg hook."
    )
    git_hook_install.add_argument(
        "--force", action="store_true", help="Overwrite non-lifetxt hooks."
    )
    git_hook_install.set_defaults(func=command_git_hook)
    git_hook_uninstall = git_hook_subparsers.add_parser(
        "uninstall", help="Uninstall lifetxt Git hooks."
    )
    git_hook_uninstall.add_argument(
        "--repo-dir",
        default=".",
        help="Git repository root. Defaults to current directory.",
    )
    git_hook_uninstall.set_defaults(func=command_git_hook)
    git_hook_status = git_hook_subparsers.add_parser(
        "status", help="Show Git hook installation status."
    )
    git_hook_status.add_argument(
        "--repo-dir",
        default=".",
        help="Git repository root. Defaults to current directory.",
    )
    git_hook_status.add_argument(
        "--files", nargs="*", help="life.txt files checked by hooks."
    )
    git_hook_status.set_defaults(func=command_git_hook)

    completion = subparsers.add_parser(
        "completion",
        help="Generate shell completion scripts.",
    )
    completion_subparsers = completion.add_subparsers(dest="completion_command")
    for shell in ("bash", "zsh", "fish"):
        shell_parser = completion_subparsers.add_parser(
            shell, help="Generate %s completion." % shell
        )
        shell_parser.add_argument(
            "-o", "--output", help="Output file. Defaults to stdout."
        )
        shell_parser.set_defaults(func=command_completion)
    completion_install = completion_subparsers.add_parser(
        "install", help="Print installation instructions."
    )
    completion_install.add_argument(
        "--shell",
        choices=("bash", "zsh", "fish", "powershell"),
        help="Shell to show instructions for.",
    )
    completion_install.add_argument(
        "-o", "--output", help="Output file. Defaults to stdout."
    )
    completion_install.set_defaults(func=command_completion)
    # Called by the generated scripts while the user is typing, so it prints
    # bare candidates and stays quiet when the file is missing or unreadable.
    from .completion import VALUE_KINDS

    completion_values = completion_subparsers.add_parser(
        "values",
        help="Print completion candidates read from a life.txt file.",
    )
    completion_values.add_argument(
        "--kind",
        choices=VALUE_KINDS,
        required=True,
        help="Candidate kind to print, one per line.",
    )
    completion_values.add_argument(
        "path", nargs="*", help="life.txt file(s) to read. Defaults to config paths."
    )
    completion_values.add_argument(
        "-o", "--output", help="Output file. Defaults to stdout."
    )
    completion_values.set_defaults(func=command_completion)

    filter_command = subparsers.add_parser(
        "filter",
        aliases=["f"],
        help="Filter life.txt items and output life.txt, JSON, or JSONL.",
    )
    _add_input_paths(filter_command)
    _add_item_filter_arguments(filter_command)
    filter_command.add_argument(
        "--format",
        choices=("life", "json", "jsonl", "table"),
        default="life",
        help="Output format. Defaults to life.",
    )
    filter_command.add_argument(
        "--width",
        type=int,
        default=0,
        metavar="N",
        help="Table column width in characters (0 = detect terminal width). Only used with --format table.",
    )
    filter_command.add_argument(
        "-o", "--output", help="Output file. Defaults to stdout."
    )
    filter_command.add_argument(
        "--pretty",
        action="store_true",
        help="Pretty-print JSON output.",
    )
    filter_command.add_argument(
        "--canonical",
        action="store_true",
        help="Regenerate unindented life.txt lines with explicit parent: links where inferable.",
    )
    filter_command.add_argument(
        "--limit",
        type=int,
        default=0,
        metavar="N",
        help="Return at most N items (0 = no limit).",
    )
    filter_command.set_defaults(func=command_filter)

    status = subparsers.add_parser(
        "status",
        help="Show the latest status / presence item for each person.",
    )
    _add_input_paths(status)
    status.add_argument(
        "--format",
        choices=("text", "json", "jsonl"),
        default="text",
        help="Output format.",
    )
    status.add_argument(
        "--person",
        help="Only show the latest status for this person. Missing person: defaults to self.",
    )
    status.add_argument(
        "--active",
        action="store_true",
        help="Only consider active status items without to:.",
    )
    status.add_argument(
        "--pretty", action="store_true", help="Pretty-print JSON output."
    )
    status.set_defaults(func=command_status)

    notify = subparsers.add_parser(
        "notify",
        help="Show or watch due message notifications.",
    )
    _add_input_paths(notify)
    notify.add_argument(
        "--recipient",
        help="Notification recipient. Defaults to notifications.recipient or user.name.",
    )
    notify.add_argument(
        "--lookahead",
        help="Future notification window, e.g. 0m, 5m, or 1h.",
    )
    notify.add_argument(
        "--grace",
        help="Past grace window for missed notifications, e.g. 2m.",
    )
    notify.add_argument(
        "--watch",
        action="store_true",
        help="Stay running and poll for notifications.",
    )
    notify.add_argument(
        "--once",
        action="store_true",
        help="With --watch, poll once, emit new notifications, update seen-state, and exit.",
    )
    notify.add_argument(
        "--interval",
        type=int,
        help="Watch poll interval in seconds.",
    )
    notify.add_argument(
        "--desktop",
        action="store_true",
        help="Also show a simple desktop notification when supported.",
    )
    notify.add_argument(
        "--email",
        action="store_true",
        help="Also send due notifications as a plain-text email batch.",
    )
    notify.add_argument(
        "--email-to",
        help="Recipient email address(es), comma-separated. Defaults to notifications.email.to.",
    )
    notify.add_argument(
        "--email-subject",
        help="Base subject for notification email. Defaults to notifications.email.subject.",
    )
    notify.add_argument(
        "--smtp-host-env",
        metavar="ENVVAR",
        help="Environment variable with the SMTP host for --email.",
    )
    notify.add_argument(
        "--smtp-user-env",
        metavar="ENVVAR",
        help="Environment variable with the SMTP username for --email.",
    )
    notify.add_argument(
        "--smtp-pass-env",
        metavar="ENVVAR",
        help="Environment variable with the SMTP password for --email.",
    )
    notify.add_argument(
        "--dry-run",
        action="store_true",
        help="For --email, print the email that would be sent without using SMTP.",
    )
    notify.add_argument(
        "--state-file",
        help="Persist seen notification IDs in this JSON file when watching.",
    )
    notify.add_argument(
        "--no-state",
        action="store_true",
        help="Do not persist seen notification IDs when watching.",
    )
    notify.add_argument(
        "--format",
        choices=("text", "json", "jsonl"),
        default="text",
        help="Output format for one-shot mode.",
    )
    notify.add_argument(
        "--pretty", action="store_true", help="Pretty-print JSON output."
    )
    notify.set_defaults(func=command_notify)

    agenda = subparsers.add_parser(
        "agenda",
        aliases=["a"],
        help="Show items related to a datetime range.",
    )
    _add_input_paths(agenda)
    agenda.add_argument(
        "--from",
        dest="start",
        help="Range start: now, YYYY-MM-DD, or ISO-like datetime with optional seconds, fraction, and timezone.",
    )
    agenda.add_argument(
        "--to",
        dest="end",
        help="Range end: now, YYYY-MM-DD, or ISO-like datetime with optional seconds, fraction, and timezone.",
    )
    agenda.add_argument(
        "--around",
        help="Center of a range: now, YYYY-MM-DD, or ISO-like datetime. Defaults to now.",
    )
    agenda.add_argument(
        "--window",
        default="1h",
        help="Half-width for --around, e.g. 30m, 2h, 1d, 1w, 1mo, or 1y.",
    )
    agenda.add_argument(
        "--width",
        type=int,
        help="Render text output for a specific terminal width.",
    )
    agenda.add_argument(
        "--format",
        choices=("text", "life", "json", "jsonl"),
        default="text",
        help="Output format.",
    )
    agenda.add_argument("-o", "--output", help="Output file. Defaults to stdout.")
    _add_item_filter_arguments(agenda)
    agenda.add_argument(
        "--blocked",
        nargs="?",
        const="only",
        choices=("only", "hide", "all", "true", "false"),
        help=(
            "Filter dependency-blocked records: --blocked or --blocked only "
            "shows blocked records, --blocked hide hides them, --blocked all "
            "shows all records."
        ),
    )
    agenda.add_argument(
        "--unblocked",
        action="store_true",
        help="Backward-compatible alias for --blocked hide.",
    )
    agenda.add_argument(
        "--pretty", action="store_true", help="Pretty-print JSON output."
    )
    agenda.set_defaults(func=command_agenda)

    from_json = subparsers.add_parser("from-json", help="Convert JSON to life.txt.")
    _add_input_paths(from_json)
    from_json.add_argument("-o", "--output", help="Output file. Defaults to stdout.")
    from_json.add_argument(
        "--canonical",
        action="store_true",
        help="Write explicit parent: links and remove indentation from output.",
    )
    from_json.set_defaults(func=command_from_json)

    from_jsonl = subparsers.add_parser("from-jsonl", help="Convert JSONL to life.txt.")
    _add_input_paths(from_jsonl)
    from_jsonl.add_argument("-o", "--output", help="Output file. Defaults to stdout.")
    from_jsonl.add_argument(
        "--canonical",
        action="store_true",
        help="Write explicit parent: links and remove indentation from output.",
    )
    from_jsonl.set_defaults(func=command_from_jsonl)

    from_csv = subparsers.add_parser("from-csv", help="Convert CSV to life.txt.")
    _add_input_paths(from_csv)
    from_csv.add_argument("-o", "--output", help="Output file. Defaults to stdout.")
    from_csv.add_argument(
        "--canonical",
        action="store_true",
        help="Write explicit parent: links and remove indentation from output.",
    )
    from_csv.set_defaults(func=command_from_csv)

    assist = subparsers.add_parser(
        "assist", help="Create a life.txt line interactively or from flags."
    )
    assist.add_argument(
        "-i", "--interactive", action="store_true", help="Prompt for fields."
    )
    assist.add_argument(
        "-s", "--status", help="Status or alias, e.g. '[ ]', done, note."
    )
    assist.add_argument(
        "-t",
        "--type",
        dest="kind",
        help="Type or alias, e.g. T, task, event, note, diary.",
    )
    assist.add_argument("--title", help="Item title.")
    assist.add_argument(
        "-d",
        "--detail",
        action="append",
        default=[],
        help="Detail as key=value or key:value. Can be repeated.",
    )
    assist.add_argument(
        "-o",
        "--output",
        help="Append generated line to a file. With --update, write the updated file.",
    )
    assist.add_argument("--append", help="Append the generated line to a file.")
    assist.add_argument(
        "--update",
        help="Update an existing life.txt file in-place, unless --output is also set.",
    )
    assist.add_argument("--line", type=int, help="Line number to update with --update.")
    assist.add_argument(
        "--match-id", help="Update the item whose id: contains this value."
    )
    assist.add_argument(
        "--add-detail",
        action="append",
        default=[],
        help="Append detail as key=value or key:value when updating. Can be repeated.",
    )
    assist.add_argument(
        "--remove-detail",
        action="append",
        default=[],
        help="Remove all values for a detail key when updating. Can be repeated.",
    )
    assist.add_argument(
        "--no-check",
        action="store_true",
        help="Do not validate the generated line before output.",
    )
    assist.add_argument(
        "--no-completion",
        action="store_true",
        help="Disable interactive completion and line editing helpers.",
    )
    assist.add_argument(
        "--body-file",
        action="append",
        help="Read a body: detail from a UTF-8 text file. Can be repeated.",
    )
    assist.add_argument(
        "--body-stdin",
        action="store_true",
        help="Read a body: detail from standard input.",
    )
    assist.add_argument(
        "--rrule",
        action="append",
        help="Set repeat:RRULE:...; accepts either FREQ=... or RRULE:FREQ=.... Can be repeated.",
    )
    for key in DETAIL_FLAGS:
        dest = "from_" if key == "from" else key
        option_strings = ["--" + key]
        if "_" in key:
            option_strings.append("--" + key.replace("_", "-"))
        assist.add_argument(
            *option_strings,
            dest=dest,
            action="append",
            help="Set %s: detail. Can be repeated." % key,
        )
    assist.set_defaults(func=command_assist)

    archive = subparsers.add_parser(
        "archive",
        help="Move or copy completed/canceled items to a separate archive file.",
    )
    archive.add_argument(
        "paths", nargs="+", metavar="path", help="Source life.txt file(s)."
    )
    archive.add_argument(
        "--dest", required=True, metavar="DEST", help="Archive file to append items to."
    )
    archive.add_argument(
        "--revision",
        action="append",
        default=[],
        metavar="PATH=SHA256",
        help="Expected revision for a source or destination path. Can be repeated.",
    )
    archive.add_argument(
        "--status",
        action="append",
        dest="statuses",
        metavar="STATUS",
        help=(
            "Only archive items with this status. Can be repeated or comma-separated. "
            "Defaults to done,canceled."
        ),
    )
    archive.add_argument(
        "--before",
        metavar="DATE",
        help="Only archive items whose done: or updated: date is before DATE (YYYY-MM-DD).",
    )
    archive.add_argument(
        "--max-items",
        type=int,
        dest="max_items",
        metavar="N",
        help="Maximum number of items to archive.",
    )
    archive.add_argument(
        "--dry-run",
        action="store_true",
        dest="dry_run",
        help="Show which items would be archived without writing any changes.",
    )
    archive.add_argument(
        "--copy",
        action="store_true",
        help="Copy items to the archive without removing them from the source file.",
    )
    archive.add_argument(
        "--yes",
        action="store_true",
        help="Skip the confirmation prompt.",
    )
    archive.add_argument(
        "--orphan-children",
        dest="orphan_children",
        choices=("block", "adopt", "promote"),
        default="block",
        help=(
            "How to handle open children of archived parents: "
            "block (default) refuses to archive, "
            "adopt archives open children together (marking them [-]), "
            "promote archives the parent only and removes parent: from orphaned children."
        ),
    )
    archive.add_argument(
        "--preserve-structure",
        action="store_true",
        dest="preserve_structure",
        help=(
            "Copy comment lines and blank lines verbatim to both the archive file "
            "and the source remainder so section headings remain intact."
        ),
    )
    archive.add_argument(
        "--block-on-external-refs",
        action="store_true",
        dest="block_on_external_refs",
        help=(
            "Treat cross-file or intra-file references to archived items as errors "
            "instead of warnings. Requires --dry-run or a live run to check."
        ),
    )
    archive.set_defaults(func=command_archive)

    quick = subparsers.add_parser(
        "quick",
        aliases=["q"],
        help="Quickly capture a new item and append it to a file.",
    )
    quick.add_argument(
        "title",
        help=(
            "Item title. Use - to read a single line from stdin. Capture shorthand is "
            "expanded: @project #tag !priority ^due."
        ),
    )
    quick.add_argument(
        "--no-shorthand",
        action="store_true",
        help="Keep @ # ! ^ tokens in the title instead of expanding them into details.",
    )
    quick.add_argument(
        "--type",
        dest="kind",
        default=None,
        help="Item type. Defaults to T (task).",
    )
    quick.add_argument(
        "--append",
        metavar="FILE",
        help="File to append the new item to. Defaults to write_file in config.",
    )
    quick.add_argument(
        "--revision", help="Expected SHA-256 revision of the append target."
    )
    quick.add_argument(
        "--no-check",
        action="store_true",
        dest="no_check",
        help="Skip validation before writing.",
    )
    quick.add_argument("--status", default=None, help=argparse.SUPPRESS)
    for key in DETAIL_FLAGS:
        dest = "from_" if key == "from" else key
        quick.add_argument(
            "--" + key,
            dest=dest,
            action="append",
            help="Set %s: detail. Can be repeated. Accepts relative dates for due/do/until (today, tomorrow, friday, next_week)."
            % key,
        )
    quick.set_defaults(
        func=command_quick, detail=None, add_detail=None, remove_detail=None
    )

    done_cmd = subparsers.add_parser(
        "done",
        aliases=["d"],
        help=(
            "Mark a task as complete and append done:TODAY. For habit (H) items, "
            "append done:DATE to the completion log instead of changing status."
        ),
    )
    done_cmd.add_argument("path", help="life.txt file containing the item.")
    done_cmd.add_argument(
        "id",
        nargs="?",
        default=None,
        help="ID of the item to mark done.",
    )
    done_cmd.add_argument(
        "--line", type=int, default=None, help="Line number of the item."
    )
    done_cmd.add_argument("--text", default=None, help="Title substring to search for.")
    done_cmd.add_argument(
        "--date",
        default=None,
        help="Completion date (YYYY-MM-DD). Defaults to today.",
    )
    done_cmd.add_argument(
        "--now",
        action="store_true",
        help="Record done: with the current time, not just the date.",
    )
    done_cmd.add_argument(
        "--date-only",
        action="store_true",
        help="Record done: with the date only, overriding config done.precision.",
    )
    done_cmd.add_argument(
        "--force",
        action="store_true",
        help="Allow logging a duplicate same-day habit completion.",
    )
    done_cmd.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would change without writing to the file.",
    )
    done_cmd.set_defaults(func=command_done)

    files_cmd = subparsers.add_parser(
        "files",
        help="Inspect, verify, and hash file: and dir: attachments.",
    )
    _add_input_paths(files_cmd)
    files_cmd.add_argument(
        "--check",
        action="store_true",
        help="Exit non-zero when an attachment is missing, changed, or the wrong type.",
    )
    files_cmd.add_argument(
        "--update",
        action="store_true",
        help="Write or refresh the #sha256= hash on every resolvable attachment.",
    )
    files_cmd.add_argument(
        "--problems",
        action="store_true",
        help="Only show attachments that are missing, changed, or non-portable.",
    )
    files_cmd.add_argument(
        "--no-verify",
        action="store_true",
        help="Skip hashing; only resolve and check existence. Much faster on large trees.",
    )
    files_cmd.add_argument(
        "--id",
        dest="item_id",
        default=None,
        help="Only inspect attachments on this item id.",
    )
    files_cmd.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="Output format.",
    )
    files_cmd.add_argument(
        "--dry-run",
        action="store_true",
        help="With --update, show what would change without writing.",
    )
    files_cmd.set_defaults(func=command_files)

    rrule_cmd = subparsers.add_parser(
        "rrule",
        help="Expand a recurrence rule into concrete occurrences.",
    )
    rrule_cmd.add_argument(
        "rule",
        nargs="?",
        default=None,
        help='Rule to expand, such as daily or "RRULE:FREQ=WEEKLY;BYDAY=MO,WE".',
    )
    rrule_cmd.add_argument(
        "--path",
        default=None,
        help="life.txt file to read a rule from instead of passing one.",
    )
    rrule_cmd.add_argument(
        "--id",
        dest="item_id",
        default=None,
        help="Expand the repeat: of this item id (requires --path).",
    )
    rrule_cmd.add_argument(
        "--from",
        dest="start",
        default=None,
        help="Series start (YYYY-MM-DD or with a time). Defaults to today, or the item's due/do/from.",
    )
    rrule_cmd.add_argument(
        "--after", default=None, help="Only show occurrences on or after this date."
    )
    rrule_cmd.add_argument(
        "--before", default=None, help="Only show occurrences on or before this date."
    )
    rrule_cmd.add_argument(
        "--count",
        type=int,
        default=None,
        help="Maximum occurrences to print. Defaults to 10.",
    )
    rrule_cmd.add_argument(
        "--format",
        choices=("text", "json", "life"),
        default="text",
        help="Output format. life emits one deadline record per occurrence.",
    )
    rrule_cmd.add_argument(
        "--type",
        dest="kind",
        default="D",
        help="Item type for --format life. Defaults to D.",
    )
    rrule_cmd.add_argument(
        "--title",
        default=None,
        help="Title for --format life. Defaults to the source item's title.",
    )
    rrule_cmd.set_defaults(func=command_rrule)

    state_cmd = subparsers.add_parser(
        "state",
        aliases=["s"],
        help=(
            "Record a presence status, closing the previous open one. "
            "Use `status` to read the current state."
        ),
    )
    state_cmd.add_argument(
        "state",
        nargs="?",
        default=None,
        help="New presence state, such as busy, focus, away, or offline.",
    )
    state_cmd.add_argument(
        "path",
        nargs="?",
        default=None,
        help="life.txt file to write to. Defaults to config write_file.",
    )
    state_cmd.add_argument(
        "--title", default=None, help="Status title. Defaults to the state name."
    )
    state_cmd.add_argument(
        "--person", default=None, help="Person the status belongs to. Defaults to self."
    )
    state_cmd.add_argument(
        "--note", default=None, help="Free-text note stored as note:."
    )
    state_cmd.add_argument(
        "--project", default=None, help="Associated project stored as project:."
    )
    state_cmd.add_argument(
        "--service", default=None, help="Service stored as service:."
    )
    state_cmd.add_argument(
        "--visibility", default=None, help="Visibility stored as visibility:."
    )
    state_cmd.add_argument(
        "--at",
        default=None,
        help="Transition time (YYYY-MM-DDTHH:MM). Defaults to now.",
    )
    state_cmd.add_argument(
        "--end",
        action="store_true",
        help="Close the current status without opening a new one.",
    )
    state_cmd.add_argument(
        "--force",
        action="store_true",
        help="Record a new record even when the state is already open.",
    )
    state_cmd.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would change without writing to the file.",
    )
    state_cmd.set_defaults(func=command_state)

    start_cmd = subparsers.add_parser(
        "start",
        help="Start work on a task: set it in progress, start the timer, and set presence.",
    )
    start_cmd.add_argument("path", help="life.txt file containing the item.")
    start_cmd.add_argument(
        "id", nargs="?", default=None, help="ID of the item to start."
    )
    start_cmd.add_argument(
        "--line", type=int, default=None, help="Line number of the item."
    )
    start_cmd.add_argument(
        "--text", default=None, help="Title substring to search for."
    )
    start_cmd.add_argument(
        "--state",
        default="busy",
        help="Presence state to record while working. Defaults to busy.",
    )
    start_cmd.add_argument(
        "--no-presence",
        action="store_true",
        help="Do not record a presence status.",
    )
    start_cmd.add_argument(
        "--no-timer",
        action="store_true",
        help="Do not start the task timer.",
    )
    start_cmd.add_argument(
        "--item-revision", help="Expected SHA-256 revision of life.txt."
    )
    start_cmd.add_argument(
        "--timer-revision",
        help="Expected timer-state revision; use <missing> when idle.",
    )
    start_cmd.add_argument(
        "--require-revisions",
        action="store_true",
        help="Reject missing item/timer revisions.",
    )
    start_cmd.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would change without writing.",
    )
    start_cmd.set_defaults(func=command_start)

    stop_cmd = subparsers.add_parser(
        "stop",
        help="Stop work: stop the timer, write elapsed:, close presence, and optionally finish the task.",
    )
    stop_cmd.add_argument(
        "path",
        nargs="?",
        default=None,
        help="life.txt file. Defaults to the file recorded by the running timer.",
    )
    stop_cmd.add_argument(
        "--done",
        action="store_true",
        help="Also mark the task complete and record done:.",
    )
    stop_cmd.add_argument(
        "--no-presence",
        action="store_true",
        help="Leave the presence status open.",
    )
    stop_cmd.add_argument(
        "--item-revision", help="Expected SHA-256 revision of life.txt."
    )
    stop_cmd.add_argument(
        "--timer-revision", help="Expected timer-state SHA-256 revision."
    )
    stop_cmd.add_argument(
        "--require-revisions",
        action="store_true",
        help="Reject missing item/timer revisions.",
    )
    stop_cmd.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would change without writing.",
    )
    stop_cmd.set_defaults(func=command_stop)

    complete_cmd = subparsers.add_parser(
        "complete",
        help=(
            "Complete a repeat-enabled task instance and materialize the next occurrence "
            "(Taskwarrior-style). Non-repeating items behave like `done`."
        ),
    )
    complete_cmd.add_argument("path", help="life.txt file containing the item.")
    complete_cmd.add_argument(
        "id",
        nargs="?",
        default=None,
        help="ID of the item to complete.",
    )
    complete_cmd.add_argument(
        "--line", type=int, default=None, help="Line number of the item."
    )
    complete_cmd.add_argument(
        "--text", default=None, help="Title substring to search for."
    )
    complete_cmd.add_argument(
        "--date",
        default=None,
        help="Completion date (YYYY-MM-DD), used as the repeat_base:done anchor. Defaults to today.",
    )
    complete_cmd.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would change without writing to the file.",
    )
    complete_cmd.set_defaults(func=command_complete)

    batch_cmd = subparsers.add_parser(
        "batch",
        help="Apply a simple item command across multiple life.txt files.",
    )
    batch_cmd.add_argument(
        "action",
        choices=("done", "assign", "tag-rename", "tag-merge", "migrate"),
        help="Action to apply.",
    )
    batch_cmd.add_argument(
        "paths", nargs="+", help="Input file(s), directories, or glob patterns."
    )
    batch_cmd.add_argument(
        "--id", action="append", dest="ids", help="Item ID to target. Can be repeated."
    )
    batch_cmd.add_argument(
        "--text",
        action="append",
        dest="texts",
        help="Title substring to target. Can be repeated.",
    )
    batch_cmd.add_argument("--to", help="Assignee for action=assign.")
    batch_cmd.add_argument("--old", help="Old tag value for tag-rename/tag-merge.")
    batch_cmd.add_argument("--new", help="New tag value for tag-rename/tag-merge.")
    batch_cmd.add_argument(
        "--migration",
        action="append",
        dest="migrations",
        help="Migration to apply for action=migrate. Can be repeated.",
    )
    batch_cmd.add_argument(
        "--backup",
        action="store_true",
        help="Write backups for actions that support it.",
    )
    batch_cmd.add_argument(
        "--dry-run", action="store_true", help="Preview actions without writing."
    )
    batch_cmd.set_defaults(func=command_batch)

    summary = subparsers.add_parser(
        "summary",
        help="Show a fast overview of a life.txt file.",
    )
    summary.add_argument(
        "paths",
        nargs="*",
        metavar="path",
        help="life.txt file(s). Reads stdin when omitted.",
    )
    summary.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="Output format.",
    )
    summary.add_argument(
        "--pretty", action="store_true", help="Pretty-print JSON output."
    )
    summary.add_argument(
        "--compare",
        metavar="PATH",
        help="Compare summary of this file against a second file side-by-side.",
    )
    summary.set_defaults(func=command_summary)

    init_cmd = subparsers.add_parser(
        "init",
        help="Interactive first-time setup: create life.txt and .lifetxt.json.",
    )
    init_cmd.add_argument(
        "--file",
        default="life.txt",
        help="life.txt file to create. Defaults to life.txt.",
    )
    init_cmd.add_argument(
        "--config-output",
        dest="config_output",
        default=".lifetxt.json",
        help="Config file to create. Defaults to .lifetxt.json.",
    )
    init_cmd.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing files without prompting.",
    )
    init_cmd.add_argument("--name", help="Your name (for #! self: directive).")
    init_cmd.add_argument(
        "--timezone", help="Your timezone (for #! timezone: directive)."
    )
    init_cmd.add_argument(
        "--project", help="Default project name (for #! project: directive)."
    )
    init_cmd.add_argument(
        "--yes",
        action="store_true",
        help="Run fully non-interactively using defaults (self, UTC, no project).",
    )
    init_cmd.set_defaults(func=command_init)

    doctor_cmd = subparsers.add_parser(
        "doctor",
        help="Check Python version, files, dependencies, and data issues.",
    )
    doctor_cmd.add_argument(
        "paths",
        nargs="*",
        metavar="path",
        help="life.txt file(s) to check. Defaults to config paths or life.txt.",
    )
    doctor_cmd.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="Output format.",
    )
    doctor_cmd.add_argument(
        "--pretty", action="store_true", help="Pretty-print JSON output."
    )
    doctor_cmd.add_argument(
        "--check-update",
        action="store_true",
        help=(
            "Also check GitHub for a newer lifetxt release or tag "
            "(read-only network request; adds an 'update' row). Off by "
            "default so plain doctor never requires network access."
        ),
    )
    doctor_cmd.add_argument(
        "--repo",
        metavar="OWNER/NAME",
        help=(
            "Repository --check-update queries. Overrides the "
            "update.repository config key and the built-in default "
            "(Eruhitsuji/lifetxt). Ignored without --check-update."
        ),
    )
    doctor_cmd.add_argument(
        "--update-timeout",
        type=int,
        default=5,
        metavar="SECONDS",
        help="Network timeout for --check-update (default 5).",
    )
    doctor_cmd.set_defaults(func=command_doctor)

    update_check_cmd = subparsers.add_parser(
        "update-check",
        help="Check GitHub for a newer lifetxt release or tag (read-only).",
    )
    update_check_cmd.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="Output format.",
    )
    update_check_cmd.add_argument(
        "--timeout",
        type=int,
        default=10,
        metavar="SECONDS",
        help="Network timeout for the GitHub API request.",
    )
    update_check_cmd.add_argument(
        "--repo",
        metavar="OWNER/NAME",
        help=(
            "GitHub repository to check, e.g. a fork's own owner/name. "
            "Overrides the update.repository config key and the built-in "
            "default (Eruhitsuji/lifetxt)."
        ),
    )
    update_check_cmd.set_defaults(func=command_update_check)

    update_cmd = subparsers.add_parser(
        "update",
        help=(
            "Fast-forward the running lifetxt git install to a newer "
            "release, tag, or ref. Requires git; dry-run by default."
        ),
    )
    update_cmd.add_argument(
        "--yes",
        action="store_true",
        help=(
            "Actually fast-forward the working tree. Without this, update "
            "only fetches and reports what would happen."
        ),
    )
    update_cmd.add_argument(
        "--ref",
        metavar="REF",
        help=(
            "Git ref (tag, branch, or commit) to update to. Defaults to "
            "the latest published GitHub release or tag."
        ),
    )
    update_cmd.add_argument(
        "--remote",
        metavar="NAME",
        help="Local git remote to fetch from. Defaults to 'origin'.",
    )
    update_cmd.add_argument(
        "--repo",
        metavar="OWNER/NAME",
        help=(
            "GitHub repository to look up the latest release/tag from "
            "(read-only; does not change which git remote is fetched). "
            "Overrides the update.repository config key and the built-in "
            "default (Eruhitsuji/lifetxt)."
        ),
    )
    update_cmd.add_argument(
        "--timeout",
        type=int,
        default=10,
        metavar="SECONDS",
        help="Timeout for the GitHub API request and each git subprocess.",
    )
    update_cmd.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="Output format.",
    )
    update_cmd.set_defaults(func=command_update)

    assign_cmd = subparsers.add_parser(
        "assign",
        help="Change the assignee: on an existing item.",
    )
    assign_cmd.add_argument("path", help="life.txt file containing the item.")
    assign_cmd.add_argument("id", nargs="?", help="ID of the item to reassign.")
    assign_cmd.add_argument(
        "--text",
        metavar="QUERY",
        help="Select item by title substring instead of ID.",
    )
    assign_cmd.add_argument(
        "--to",
        required=True,
        metavar="PERSON",
        help="New assignee name.",
    )
    assign_cmd.add_argument(
        "--notify",
        action="store_true",
        help="Append an M notification item to the new assignee.",
    )
    assign_cmd.add_argument(
        "--from-user",
        dest="from_user",
        metavar="NAME",
        help="Override sender name in --notify M-items (default: config user name).",
    )
    assign_cmd.set_defaults(func=command_assign)

    health_cmd = subparsers.add_parser(
        "health",
        help="Operational sanity checks: stale tasks, missed habits, upcoming deadlines.",
    )
    _add_input_paths(health_cmd)
    health_cmd.add_argument(
        "--since",
        type=int,
        default=30,
        metavar="DAYS",
        help="Days threshold for stale-task and habit checks. Defaults to 30.",
    )
    health_cmd.add_argument(
        "--lookahead",
        type=int,
        default=7,
        metavar="DAYS",
        help="Days lookahead for upcoming deadlines. Defaults to 7.",
    )
    health_cmd.add_argument(
        "--ignore",
        action="append",
        help="Suppress a health code, e.g. W301. Can be repeated or comma-separated.",
    )
    health_cmd.add_argument(
        "--type",
        action="append",
        dest="health_types",
        metavar="TYPE",
        help="Restrict checks to items of this type (T, H, E, etc.). Can be repeated or comma-separated.",
    )
    health_cmd.add_argument(
        "--format",
        choices=("text", "json", "jsonl"),
        default="text",
        help="Output format.",
    )
    health_cmd.add_argument(
        "--pretty", action="store_true", help="Pretty-print JSON output."
    )
    health_cmd.set_defaults(func=command_health)

    inbox_cmd = subparsers.add_parser(
        "inbox",
        help="List open tasks with no project, due date, or assignee.",
    )
    _add_input_paths(inbox_cmd)
    inbox_cmd.add_argument(
        "--type",
        dest="kinds",
        action="append",
        help="Filter by type. Defaults to T (task). Can be repeated or comma-separated.",
    )
    inbox_cmd.add_argument(
        "--text",
        help="Case-insensitive title substring filter.",
    )
    inbox_cmd.add_argument(
        "--format",
        choices=("text", "json", "jsonl"),
        default="text",
        help="Output format.",
    )
    inbox_cmd.add_argument(
        "--pretty", action="store_true", help="Pretty-print JSON output."
    )
    inbox_cmd.add_argument(
        "--process",
        action="store_true",
        help="Interactive one-by-one triage: prompts for project, due, and assignee for each inbox item.",
    )
    inbox_cmd.add_argument(
        "--fzf",
        action="store_true",
        help="Select an inbox item with fzf or peco and print the selected record.",
    )
    inbox_cmd.set_defaults(func=command_inbox)

    cleanup_cmd = subparsers.add_parser(
        "cleanup",
        help="Guided file-maintenance navigator: report issues and suggest next commands.",
    )
    _add_input_paths(cleanup_cmd)
    cleanup_cmd.add_argument(
        "--ignore",
        action="append",
        help="Suppress a diagnostic code. Can be repeated or comma-separated.",
    )
    cleanup_cmd.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="Output format.",
    )
    cleanup_cmd.add_argument(
        "--pretty", action="store_true", help="Pretty-print JSON output."
    )
    cleanup_cmd.set_defaults(func=command_cleanup)

    undo_cmd = subparsers.add_parser(
        "undo",
        help="Restore a file to its state before the most recent write operation.",
    )
    undo_cmd.add_argument("path", help="life.txt file to restore.")
    undo_cmd.add_argument(
        "--revision", help="Expected current SHA-256 revision before restoring."
    )
    undo_cmd.add_argument(
        "--list",
        action="store_true",
        help="List the undo stack with timestamps and operation names.",
    )
    undo_cmd.set_defaults(func=command_undo)

    review_cmd = subparsers.add_parser(
        "review",
        help="Human-readable period summary: completed tasks, habits, mood, and elapsed time.",
    )
    _add_input_paths(review_cmd)
    review_cmd.add_argument(
        "--week",
        action="store_true",
        help="Review the current ISO week (Monday to today).",
    )
    review_cmd.add_argument(
        "--month",
        metavar="YYYY-MM",
        help="Review a specific calendar month.",
    )
    review_cmd.add_argument(
        "--from",
        dest="from_date",
        metavar="DATE",
        help="Start date for custom range (YYYY-MM-DD).",
    )
    review_cmd.add_argument(
        "--to",
        dest="to_date",
        metavar="DATE",
        help="End date for custom range (YYYY-MM-DD).",
    )
    review_cmd.add_argument(
        "--project",
        help="Restrict review to a specific project.",
    )
    review_cmd.add_argument(
        "--format",
        choices=("text", "json", "jsonl", "markdown", "html"),
        default="text",
        help="Output format.",
    )
    review_cmd.add_argument(
        "--pretty", action="store_true", help="Pretty-print JSON output."
    )
    review_cmd.set_defaults(func=command_review)

    who_cmd = subparsers.add_parser(
        "who",
        help="Team presence summary: latest active S item per person across loaded files.",
    )
    _add_input_paths(who_cmd)
    who_cmd.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="Output format.",
    )
    who_cmd.add_argument(
        "--pretty", action="store_true", help="Pretty-print JSON output."
    )
    who_cmd.set_defaults(func=command_who)

    search_cmd = subparsers.add_parser(
        "search",
        help="Search life.txt items by substring or regex match in title or field values.",
    )
    _add_input_paths(search_cmd)
    search_cmd.add_argument("pattern", help="Substring or regex pattern to match.")
    search_cmd.add_argument(
        "--regex",
        action="store_true",
        help="Treat pattern as a regular expression (case-insensitive).",
    )
    search_cmd.add_argument(
        "--in",
        dest="in_fields",
        action="append",
        metavar="FIELD",
        help="Scope search to a detail field (e.g. title, body, note). Can be repeated or comma-separated.",
    )
    search_cmd.add_argument(
        "--format",
        choices=("text", "life", "json", "jsonl"),
        default="text",
        help="Output format.",
    )
    search_cmd.add_argument(
        "--pretty", action="store_true", help="Pretty-print JSON output."
    )
    search_cmd.add_argument(
        "--highlight",
        action="store_true",
        help="Highlight matched text with ANSI color in text output.",
    )
    search_cmd.add_argument(
        "--count",
        action="store_true",
        help="Print only the count of matching items, not the items themselves.",
    )
    search_cmd.set_defaults(func=command_search)

    snapshot_cmd = subparsers.add_parser(
        "snapshot",
        help="Copy a life.txt file to a timestamped snapshot for point-in-time backups.",
    )
    snapshot_cmd.add_argument("path", help="Source life.txt file to snapshot.")
    snapshot_cmd.add_argument(
        "-o",
        "--output",
        dest="output",
        help="Output path. Defaults to <dir>/snapshots/YYYY-MM-DD_<basename>.",
    )
    snapshot_cmd.add_argument(
        "--dir",
        dest="snapshot_dir",
        default=None,
        help="Directory to write the snapshot. Defaults to a 'snapshots/' subdir next to the source.",
    )
    snapshot_cmd.add_argument(
        "--diff",
        action="store_true",
        help="Show a semantic diff between the new snapshot and the most recent previous snapshot in the same directory.",
    )
    snapshot_cmd.set_defaults(func=command_snapshot)

    lint_cmd = subparsers.add_parser(
        "lint",
        help="Check life.txt for style issues: key-name typos, tag casing, and duplicate keys.",
    )
    _add_input_paths(lint_cmd)
    lint_cmd.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="Output format.",
    )
    lint_cmd.add_argument(
        "--fix",
        action="store_true",
        help="Auto-correct safe issues in-place (writes to the writable path only).",
    )
    lint_cmd.add_argument(
        "--pretty",
        action="store_true",
        help="Pretty-print JSON output.",
    )
    lint_cmd.add_argument(
        "--ruleset",
        dest="ruleset",
        metavar="FILE",
        help="JSON file with custom rules (list of {pattern, replacement, message}).",
    )
    lint_cmd.set_defaults(func=command_lint)

    # diff command
    diff_cmd = subparsers.add_parser(
        "diff",
        help="Semantic diff between two life.txt files: added, removed, status-changed, detail-changed.",
    )
    diff_cmd.add_argument("before", help="Base life.txt file (older state).")
    diff_cmd.add_argument("after", help="Updated life.txt file (newer state).")
    diff_cmd.add_argument(
        "--format",
        choices=("text", "json", "jsonl"),
        default="text",
        help="Output format.",
    )
    diff_cmd.add_argument(
        "--pretty", action="store_true", help="Pretty-print JSON output."
    )
    diff_cmd.add_argument(
        "--type",
        dest="kinds",
        action="append",
        help="Filter diff by item type. Can be repeated.",
    )
    diff_cmd.add_argument(
        "--project",
        action="append",
        help="Filter diff by project. Can be repeated.",
    )
    diff_cmd.add_argument(
        "--status",
        dest="change_types",
        action="append",
        choices=(
            "added",
            "removed",
            "completed",
            "canceled",
            "status-changed",
            "detail-changed",
        ),
        help="Limit output to specific change types. Can be repeated.",
    )
    diff_cmd.add_argument(
        "--since",
        metavar="DATE",
        help="Auto-select the most recent snapshot from this date (YYYY-MM-DD) as the base file.",
    )
    diff_cmd.set_defaults(func=command_diff)

    # plot command
    plot_cmd = subparsers.add_parser(
        "plot",
        help="Render task/habit/mood/elapsed statistics as Unicode bar charts.",
    )
    _add_input_paths(plot_cmd)
    plot_cmd.add_argument(
        "--chart",
        choices=("tasks", "habits", "mood", "elapsed", "deadlines", "all"),
        default="all",
        help="Which chart to render (default: all).",
    )
    plot_cmd.add_argument(
        "--sparkline",
        action="store_true",
        help="Output sparklines (single-row Unicode trend) instead of full bar charts.",
    )
    plot_cmd.add_argument(
        "--group",
        choices=("daily", "weekly", "monthly"),
        default="weekly",
        help="Time bucket size for trend charts.",
    )
    plot_cmd.add_argument(
        "--from", dest="start", metavar="DATE", help="Start date (YYYY-MM-DD)."
    )
    plot_cmd.add_argument(
        "--to", dest="end", metavar="DATE", help="End date (YYYY-MM-DD)."
    )
    plot_cmd.add_argument("--project", help="Restrict to a single project.")
    plot_cmd.add_argument(
        "--width",
        type=int,
        default=0,
        help="Chart width in characters (0 = auto-detect terminal width).",
    )
    plot_cmd.add_argument(
        "--format",
        choices=("text", "svg", "png"),
        default="text",
        help="Output format. SVG is dependency-free; PNG requires matplotlib.",
    )
    plot_cmd.add_argument(
        "-o", "--output", help="Output file for SVG/PNG. Text defaults to stdout."
    )
    plot_cmd.set_defaults(func=command_plot)

    heatmap_cmd = subparsers.add_parser(
        "export-heatmap",
        help="Export task or habit activity as a dependency-free SVG heatmap.",
    )
    _add_input_paths(heatmap_cmd)
    heatmap_cmd.add_argument(
        "--from", dest="start", metavar="DATE", help="Start date (YYYY-MM-DD)."
    )
    heatmap_cmd.add_argument(
        "--to", dest="end", metavar="DATE", help="End date (YYYY-MM-DD)."
    )
    heatmap_cmd.add_argument(
        "--type",
        dest="kind",
        choices=("task", "habit", "all"),
        default="all",
        help="Activity source: task done dates, habit done dates, or all.",
    )
    heatmap_cmd.add_argument("--project", help="Restrict to a single project.")
    heatmap_cmd.add_argument("--title", default="lifetxt activity", help="SVG title.")
    heatmap_cmd.add_argument(
        "-o", "--output", help="Output SVG file. Defaults to stdout."
    )
    heatmap_cmd.set_defaults(func=command_export_heatmap)

    # migrate command
    migrate_cmd = subparsers.add_parser(
        "migrate",
        help="Apply in-place format migrations to a life.txt file.",
    )
    migrate_cmd.add_argument("path", help="File to migrate.")
    migrate_cmd.add_argument(
        "--migration",
        action="append",
        dest="migrations",
        metavar="NAME[=ARG]",
        help=(
            "Migration to apply. Can be repeated. "
            "Built-in names: normalize-elapsed, rename-key OLD=NEW, add-id, "
            "normalize-status, strip-empty-details, canonicalize-dates."
        ),
    )
    migrate_cmd.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without writing to the file.",
    )
    migrate_cmd.add_argument(
        "--backup",
        action="store_true",
        help="Write a .bak file before modifying.",
    )
    migrate_cmd.set_defaults(func=command_migrate)

    # from-markdown command
    frommd_cmd = subparsers.add_parser(
        "from-markdown",
        help="Convert a Markdown task list (- [ ] title) to life.txt items.",
    )
    _add_input_paths(frommd_cmd)
    frommd_cmd.add_argument("-o", "--output", help="Output file (default: stdout).")
    frommd_cmd.add_argument("--project", help="Assign project: to all imported items.")
    frommd_cmd.add_argument(
        "--type",
        dest="kind",
        default="T",
        help="Item type for imported items (default: T).",
    )
    frommd_cmd.add_argument(
        "--append",
        action="store_true",
        help="Append to output file instead of overwrite.",
    )
    frommd_cmd.add_argument(
        "--preset",
        choices=("github",),
        help="Source format preset. 'github' maps GitHub Issues Markdown (checkbox lists with #NNN refs) to life.txt items with ref: set to the issue number.",
    )
    frommd_cmd.set_defaults(func=command_from_markdown)

    # deps command
    deps_cmd = subparsers.add_parser(
        "deps",
        help="Show dependency chains (depends_on:/blocks:) as an indented tree.",
    )
    _add_input_paths(deps_cmd)
    deps_cmd.add_argument(
        "--blocked",
        action="store_true",
        help="Only show items with unresolved (open) blockers.",
    )
    deps_cmd.add_argument(
        "--root",
        metavar="ID",
        help="Trace dependency chain from a specific item ID.",
    )
    deps_cmd.add_argument(
        "--format",
        choices=("text", "json", "mermaid", "dot"),
        default="text",
        help="Output format (default: text).",
    )
    deps_cmd.add_argument(
        "--depth",
        type=int,
        help="Maximum dependency depth to render. Depth 0 shows only root nodes.",
    )
    deps_cmd.add_argument(
        "--pretty", action="store_true", help="Pretty-print JSON output."
    )
    deps_cmd.set_defaults(func=command_deps)

    # tag command
    tag_cmd = subparsers.add_parser("tag", help="Tag management: list, rename.")
    tag_subparsers = tag_cmd.add_subparsers(dest="tag_action")
    tag_list_cmd = tag_subparsers.add_parser("list", help="List all tags with counts.")
    _add_input_paths(tag_list_cmd)
    tag_list_cmd.add_argument("--format", choices=("text", "json"), default="text")
    tag_list_cmd.set_defaults(func=command_tag_list)
    tag_rename_cmd = tag_subparsers.add_parser("rename", help="Rename a tag in-place.")
    tag_rename_cmd.add_argument("old", help="Old tag value.")
    tag_rename_cmd.add_argument("new", help="New tag value.")
    tag_rename_cmd.add_argument("path", help="File to update.")
    tag_rename_cmd.add_argument(
        "--dry-run", action="store_true", help="Preview without writing."
    )
    tag_rename_cmd.set_defaults(func=command_tag_rename)
    tag_merge_cmd = tag_subparsers.add_parser(
        "merge", help="Rename a tag in-place and record alias in config."
    )
    tag_merge_cmd.add_argument("old", help="Old tag value to merge away.")
    tag_merge_cmd.add_argument("new", help="Canonical tag value to merge into.")
    tag_merge_cmd.add_argument("path", help="File to update.")
    tag_merge_cmd.add_argument(
        "--dry-run", action="store_true", help="Preview without writing."
    )
    tag_merge_cmd.add_argument("--revision", help="Expected life.txt SHA-256 revision.")
    tag_merge_cmd.add_argument(
        "--config-revision", help="Expected config JSON SHA-256 revision."
    )
    tag_merge_cmd.set_defaults(func=command_tag_merge)
    tag_cmd.set_defaults(func=lambda args: tag_cmd.print_help())

    # watch command
    watch_cmd = subparsers.add_parser(
        "watch",
        help="Watch life.txt files for changes and re-run a command on each change.",
    )
    _add_input_paths(watch_cmd)
    watch_cmd.add_argument(
        "--run",
        metavar="CMD",
        default="summary",
        help="lifetxt sub-command to re-run on change (default: summary).",
    )
    watch_cmd.add_argument(
        "--interval",
        type=float,
        default=1.0,
        help="Polling interval in seconds (default: 1.0).",
    )
    watch_cmd.add_argument(
        "--clear", action="store_true", help="Clear screen before each re-run."
    )
    watch_cmd.add_argument(
        "--timestamp",
        action="store_true",
        help="Print a timestamped header before each run.",
    )
    watch_cmd.add_argument(
        "--notify",
        action="store_true",
        help="Send a desktop notification or terminal bell when command exit status changes.",
    )
    watch_cmd.set_defaults(func=command_watch)

    # encrypt command
    encrypt_cmd = subparsers.add_parser(
        "encrypt",
        help="Encrypt selected field values in-place using a passphrase.",
    )
    encrypt_cmd.add_argument("path", help="File to encrypt.")
    encrypt_cmd.add_argument(
        "--field",
        action="append",
        dest="fields",
        metavar="FIELD",
        help="Field key to encrypt (e.g. body, note). Can be repeated.",
    )
    encrypt_cmd.add_argument(
        "--type",
        action="append",
        dest="kinds",
        metavar="TYPE",
        help="Only encrypt items of this type (e.g. J, M). Can be repeated.",
    )
    encrypt_cmd.add_argument(
        "--key-env",
        metavar="ENVVAR",
        default="LIFETXT_KEY",
        help="Environment variable containing the passphrase (default: LIFETXT_KEY).",
    )
    encrypt_cmd.add_argument(
        "--key-file",
        help="Read the passphrase from a UTF-8 text file. Overrides --key-env.",
    )
    encrypt_cmd.add_argument(
        "--algorithm",
        choices=("xsk", "aesgcm"),
        default="xsk",
        help="Encryption algorithm. xsk is dependency-free; aesgcm requires cryptography.",
    )
    encrypt_cmd.add_argument(
        "--dry-run", action="store_true", help="Preview without writing."
    )
    encrypt_cmd.add_argument(
        "--backup", action="store_true", help="Write .bak before modifying."
    )
    encrypt_cmd.set_defaults(func=command_encrypt)

    # decrypt command
    decrypt_cmd = subparsers.add_parser(
        "decrypt",
        help="Decrypt enc:-tagged field values in-place using a passphrase.",
    )
    decrypt_cmd.add_argument("path", help="File to decrypt.")
    decrypt_cmd.add_argument(
        "--field",
        action="append",
        dest="fields",
        metavar="FIELD",
        help="Field key to decrypt. Can be repeated (default: all enc: fields).",
    )
    decrypt_cmd.add_argument(
        "--key-env",
        metavar="ENVVAR",
        default="LIFETXT_KEY",
        help="Environment variable containing the passphrase (default: LIFETXT_KEY).",
    )
    decrypt_cmd.add_argument(
        "--key-file",
        help="Read the passphrase from a UTF-8 text file. Overrides --key-env.",
    )
    decrypt_cmd.add_argument(
        "--algorithm",
        choices=("auto", "xsk", "aesgcm"),
        default="auto",
        help="Expected algorithm. auto dispatches from the enc: tag.",
    )
    decrypt_cmd.add_argument(
        "--dry-run", action="store_true", help="Preview without writing."
    )
    decrypt_cmd.add_argument(
        "--backup", action="store_true", help="Write .bak before modifying."
    )
    decrypt_cmd.set_defaults(func=command_decrypt)

    # share command
    share_cmd = subparsers.add_parser(
        "share",
        help="Export a self-contained HTML or Markdown report combining filtered items and charts.",
    )
    _add_input_paths(share_cmd)
    _add_item_filter_arguments(share_cmd)
    share_cmd.add_argument(
        "--week",
        action="store_true",
        help="Restrict range label to the current ISO week (Monday to today).",
    )
    share_cmd.add_argument(
        "--month",
        metavar="YYYY-MM",
        help="Restrict range label to a specific calendar month.",
    )
    share_cmd.add_argument(
        "--format",
        choices=("html", "markdown"),
        default="html",
        help="Output format. Defaults to html.",
    )
    share_cmd.add_argument(
        "-o", "--output", help="Output file. Defaults to share.html or share.md."
    )
    share_cmd.add_argument(
        "--title", help="Report title. Defaults to 'lifetxt share report'."
    )
    share_cmd.set_defaults(func=command_share)

    # digest command
    digest_cmd = subparsers.add_parser(
        "digest",
        help="Deliver a review summary to Slack, email, or a local file.",
    )
    _add_input_paths(digest_cmd)
    digest_cmd.add_argument(
        "--week",
        action="store_true",
        help="Digest the current ISO week (Monday to today).",
    )
    digest_cmd.add_argument(
        "--month", metavar="YYYY-MM", help="Digest a specific calendar month."
    )
    digest_cmd.add_argument("--project", help="Restrict digest to a specific project.")
    digest_cmd.add_argument(
        "--format",
        dest="channel",
        choices=("slack-webhook", "email", "file"),
        required=True,
        help="Delivery channel.",
    )
    digest_cmd.add_argument(
        "--url-env",
        metavar="ENVVAR",
        help="Environment variable with the Slack incoming webhook URL (--format slack-webhook).",
    )
    digest_cmd.add_argument("--to", help="Recipient email address (--format email).")
    digest_cmd.add_argument(
        "--smtp-host-env",
        metavar="ENVVAR",
        default="LIFETXT_SMTP_HOST",
        help="Environment variable with the SMTP host (--format email).",
    )
    digest_cmd.add_argument(
        "--smtp-user-env",
        metavar="ENVVAR",
        default="LIFETXT_SMTP_USER",
        help="Environment variable with the SMTP username (--format email).",
    )
    digest_cmd.add_argument(
        "--smtp-pass-env",
        metavar="ENVVAR",
        default="LIFETXT_SMTP_PASS",
        help="Environment variable with the SMTP password (--format email).",
    )
    digest_cmd.add_argument(
        "--path",
        dest="digest_path",
        help="Local file to append Markdown to (--format file).",
    )
    digest_cmd.add_argument(
        "--revision", help="Expected SHA-256 revision of the local digest file."
    )
    digest_cmd.add_argument(
        "--dry-run",
        action="store_true",
        help="Build the digest and print what would be sent without making a network request or writing.",
    )
    digest_cmd.set_defaults(func=command_digest)

    # template command
    template_cmd = subparsers.add_parser(
        "template",
        help="List and apply reusable named item templates from config.",
    )
    template_subparsers = template_cmd.add_subparsers(dest="template_command")
    template_list_cmd = template_subparsers.add_parser(
        "list", help="List available templates."
    )
    template_list_cmd.set_defaults(func=command_template_list)
    template_apply_cmd = template_subparsers.add_parser(
        "apply", help="Expand a template and append the result to a file."
    )
    template_apply_cmd.add_argument(
        "name", help="Template name (key under config templates)."
    )
    template_apply_cmd.add_argument(
        "--append",
        metavar="FILE",
        required=True,
        help="File to append the expanded template to.",
    )
    template_apply_cmd.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview the expanded template without writing.",
    )
    template_apply_cmd.add_argument(
        "--revision", help="Expected SHA-256 revision of the append target."
    )
    template_apply_cmd.set_defaults(func=command_template_apply)

    return parser


def _add_input_paths(parser):
    parser.add_argument(
        "paths",
        nargs="*",
        metavar="path",
        help="Input file(s), or - for stdin. Reads stdin when omitted.",
    )


def _add_item_filter_arguments(parser):
    parser.add_argument(
        "--open",
        action="store_true",
        help="Keep unfinished workflow items only: [ ], [/], [>], or [?].",
    )
    parser.add_argument(
        "--status",
        action="append",
        help="Filter by status or alias. Can be repeated or comma-separated.",
    )
    parser.add_argument(
        "--type",
        dest="kinds",
        action="append",
        help="Filter by type or alias. Can be repeated or comma-separated.",
    )
    parser.add_argument(
        "--project",
        action="append",
        help="Filter by project detail. Can be repeated or comma-separated.",
    )
    parser.add_argument(
        "--tag",
        action="append",
        help="Filter by tag detail. Can be repeated or comma-separated.",
    )
    parser.add_argument(
        "--tag-all",
        action="append",
        help="Require every listed tag value. Can be repeated or comma-separated.",
    )
    parser.add_argument(
        "--exclude-tag",
        action="append",
        help="Exclude items containing any listed tag value. Can be repeated or comma-separated.",
    )
    parser.add_argument(
        "--user",
        action="append",
        help="Filter by any user-related detail. Can be repeated or comma-separated.",
    )
    parser.add_argument(
        "--team",
        action="append",
        help="Filter by team/group detail or config-defined team membership.",
    )
    parser.add_argument(
        "--person",
        action="append",
        help="Filter by person detail. Missing person on S items defaults to self.",
    )
    parser.add_argument(
        "--owner",
        action="append",
        help="Filter by owner detail. Can be repeated or comma-separated.",
    )
    parser.add_argument(
        "--assignee",
        action="append",
        help="Filter by assignee detail. Can be repeated or comma-separated.",
    )
    parser.add_argument(
        "--attendee",
        action="append",
        help="Filter by attendee detail. Can be repeated or comma-separated.",
    )
    parser.add_argument(
        "--sender",
        action="append",
        help="Filter by sender detail. Can be repeated or comma-separated.",
    )
    parser.add_argument(
        "--recipient",
        action="append",
        help="Filter by recipient detail. Can be repeated or comma-separated.",
    )
    parser.add_argument(
        "--detail",
        action="append",
        default=[],
        help="Filter by detail key or key=value. Repeated filters are ANDed.",
    )
    parser.add_argument(
        "--text",
        help="Case-insensitive substring filter across title, line, and detail values.",
    )
    parser.add_argument(
        "--after",
        help="Keep items related to this time or later: now, YYYY-MM-DD, or ISO-like datetime.",
    )
    parser.add_argument(
        "--before",
        help="Keep items related to this time or earlier: now, YYYY-MM-DD, or ISO-like datetime.",
    )


def _add_occurrence_export_arguments(parser):
    parser.add_argument(
        "--occurrences",
        action="store_true",
        help=(
            "Export generated agenda occurrence records instead of stored items. "
            "Requires --after and --before to bound recurrence expansion."
        ),
    )


_W225_GUIDANCE = (
    "  Hint: To resolve W225, either (1) close children manually, "
    "(2) run archive --orphan-children adopt, or (3) run archive --orphan-children promote."
)


def command_check(args):
    config = _config(args)
    items, diagnostics = _parse_life_inputs(args.paths, config)
    diagnostics = diagnostics + _attachment_diagnostics_for_check(items, config, args)
    ignore_codes = getattr(args, "ignore_codes", None)
    filtered_diagnostics = filter_diagnostics(
        diagnostics,
        severities=getattr(args, "diagnostic_severities", None),
        codes=getattr(args, "diagnostic_codes", None),
        categories=getattr(args, "diagnostic_categories", None),
        ignore_codes=ignore_codes,
    )
    has_filter = any(
        getattr(args, name, None)
        for name in (
            "diagnostic_severities",
            "diagnostic_codes",
            "diagnostic_categories",
            "ignore_codes",
        )
    )

    if args.format == "json":
        output = json.dumps(
            [
                diagnostic_to_output_dict(diagnostic)
                for diagnostic in filtered_diagnostics
            ],
            ensure_ascii=False,
            indent=2,
        )
        write_text(None, output + "\n")
    else:
        if filtered_diagnostics:
            for diagnostic in filtered_diagnostics:
                write_text(None, diagnostic.format() + "\n")
                if str(getattr(diagnostic, "code", "")).upper() == "W225":
                    write_text(None, _W225_GUIDANCE + "\n")
        elif has_filter:
            write_text(None, "OK: %d item(s), 0 matching diagnostic(s)\n" % len(items))
        else:
            write_text(None, "OK: %d item(s)\n" % len(items))

    return _exit_code(filtered_diagnostics, args.warnings_as_errors)


def command_ids(args):
    if args.assign:
        return command_ids_assign(args)

    items, diagnostics = _parse_or_exit(args.paths, _config(args))
    key = args.key or id_key_from_config(_config(args))
    audit = id_audit(items, key=key)

    if args.format == "json":
        output = json.dumps(
            _id_audit_output(audit, args.only),
            ensure_ascii=False,
            indent=2 if args.pretty else None,
            separators=None if args.pretty else (",", ":"),
        )
        write_text(None, output + "\n")
    elif args.format == "jsonl":
        records = _id_audit_jsonl_records(audit, args.only)
        output = "\n".join(
            json.dumps(record, ensure_ascii=False, separators=(",", ":"))
            for record in records
        )
        if output:
            output += "\n"
        write_text(None, output)
    else:
        write_text(None, format_id_audit(audit, args.only))

    _print_warnings(diagnostics)
    return 0


def command_links(args):
    items, diagnostics = _parse_or_exit(args.paths, _config(args))
    key = args.key or id_key_from_config(_config(args))
    if getattr(args, "chain", None):
        if args.item_id:
            raise ValueError("Use either --chain or --id, not both.")
        if args.direction != "both":
            raise ValueError("--direction is only valid with --id, not --chain.")
        if args.relation:
            raise ValueError("--relation is only valid for link records, not --chain.")
        if args.format in ("mermaid", "dot"):
            raise ValueError("--chain supports text, json, or jsonl output.")
        chains = dependency_chain_records(items, key=key, root_id=args.chain)
        if args.format == "json":
            write_text(
                None,
                json.dumps(
                    chains,
                    ensure_ascii=False,
                    indent=2 if args.pretty else None,
                    separators=None if args.pretty else (",", ":"),
                )
                + "\n",
            )
        elif args.format == "jsonl":
            output = "\n".join(
                json.dumps(record, ensure_ascii=False, separators=(",", ":"))
                for record in chains
            )
            if output:
                output += "\n"
            write_text(None, output)
        else:
            write_text(None, format_dependency_chain(chains))
        _print_warnings(diagnostics)
        return 0

    records = link_records(
        items,
        key=key,
        focus_id=args.item_id,
        direction=args.direction,
        relations=_split_csv_args(args.relation),
    )

    if args.format == "json":
        write_text(None, links_to_json(records, pretty=args.pretty) + "\n")
    elif args.format == "jsonl":
        output = links_to_jsonl(records)
        if output:
            output += "\n"
        write_text(None, output)
    elif args.format == "mermaid":
        write_text(None, links_to_mermaid(records))
    elif args.format == "dot":
        write_text(None, links_to_dot(records))
    else:
        write_text(None, format_link_table(records))

    _print_warnings(diagnostics)
    return 0


def command_sources(args):
    key = args.key or id_key_from_config(_config(args))
    normalized = _normalize_paths(args.paths, _config(args))
    file_directives = OrderedDict()
    for path in normalized:
        source = "stdin" if path == "-" else path
        text = read_text(path)
        file_directives[source] = parse_directives(text)
    records, diagnostics = source_ownership_records(args.paths, _config(args), key)
    if _has_error(diagnostics):
        _print_diagnostics(diagnostics)
        return 1

    if args.missing_id:
        records = [record for record in records if not record.get("id")]

    if args.format == "json":
        payload = OrderedDict([("items", records), ("directives", file_directives)])
        output = json.dumps(
            payload,
            ensure_ascii=False,
            indent=2 if args.pretty else None,
            separators=None if args.pretty else (",", ":"),
        )
        write_text(None, output + "\n")
    elif args.format == "jsonl":
        output = "\n".join(
            json.dumps(record, ensure_ascii=False, separators=(",", ":"))
            for record in records
        )
        if output:
            output += "\n"
        write_text(None, output)
    else:
        lines = []
        for source, directives in file_directives.items():
            if directives:
                lines.append("Directives (%s):" % source)
                for k, v in directives.items():
                    lines.append("  #! %s: %s" % (k, v))
        if lines:
            write_text(None, "\n".join(lines) + "\n")
        write_text(None, format_source_ownership_table(records, key))

    _print_warnings(diagnostics)
    return 0


def _split_csv_args(values):
    result = []
    for raw in values or []:
        for value in str(raw).split(","):
            value = value.strip()
            if value:
                result.append(value)
    return result


def command_ids_assign(args):
    key = args.key or id_key_from_config(_config(args))
    records = assign_missing_ids(
        args.paths,
        _config(args),
        key,
        args.dry_run,
        args.backup,
        prefix=args.prefix,
    )

    if args.format == "json":
        output = json.dumps(
            records,
            ensure_ascii=False,
            indent=2 if args.pretty else None,
            separators=None if args.pretty else (",", ":"),
        )
        write_text(None, output + "\n")
    elif args.format == "jsonl":
        output = "\n".join(
            json.dumps(record, ensure_ascii=False, separators=(",", ":"))
            for record in records
        )
        if output:
            output += "\n"
        write_text(None, output)
    else:
        write_text(None, format_id_assignments(records, args.dry_run))
    return 0


def command_to_json(args):
    items, diagnostics = _parse_or_exit(args.paths, _config(args))
    if getattr(args, "occurrences", False):
        records = _occurrence_export_records(items, args)
        output = agenda_records_to_json(records, pretty=args.pretty)
    else:
        items = _filter_items_from_args(items, args)
        output = items_to_json(items, pretty=args.pretty)
    write_text(args.output, output + "\n")
    _print_warnings(diagnostics)
    return 0


def command_to_jsonl(args):
    items, diagnostics = _parse_or_exit(args.paths, _config(args))
    if getattr(args, "occurrences", False):
        records = _occurrence_export_records(items, args)
        output = agenda_records_to_jsonl(records)
    else:
        items = _filter_items_from_args(items, args)
        output = items_to_jsonl(items)
    if output:
        output += "\n"
    write_text(args.output, output)
    _print_warnings(diagnostics)
    return 0


def command_to_csv(args):
    items, diagnostics = _parse_or_exit(args.paths, _config(args))
    if getattr(args, "occurrences", False):
        records = _occurrence_export_records(items, args)
        output = occurrence_records_to_csv(records)
    else:
        items = _filter_items_from_args(items, args)
        output = items_to_csv(items)
    write_text(args.output, output)
    _print_warnings(diagnostics)
    return 0


def command_demo(args):
    if args.count < 0:
        raise ValueError("--count must be zero or greater.")
    if args.append and not args.output:
        raise ValueError("--append requires --output.")
    base_datetime = parse_demo_base_datetime(args.date)
    kinds = parse_demo_types(args.types)
    start_index = args.start_index
    if start_index is None:
        start_index = _next_demo_start_index(args.output) if args.append else 1
    if start_index < 1:
        raise ValueError("--start-index must be 1 or greater.")
    output = demo_text(
        count=args.count,
        base_datetime=base_datetime,
        types=kinds,
        seed=args.seed,
        project=args.project,
        people=args.person,
        start_index=start_index,
    )

    if not args.no_check:
        items, diagnostics = parse_text(output)
        if len(items) != args.count:
            diagnostics.append(
                Diagnostic(
                    "error",
                    "E301",
                    "Generated %d item(s), expected %d." % (len(items), args.count),
                )
            )
        if _has_error(diagnostics):
            _print_diagnostics(diagnostics)
            return 1
        _print_warnings(diagnostics)

    if args.output:
        _ensure_writable_path(args.output, _config(args), "demo")
        if args.append:
            append_text(args.output, output)
            action = "Appended"
        else:
            write_text(args.output, output)
            action = "Generated"
        sys.stdout.write(
            "%s %d demo item(s) to %s\n" % (action, args.count, args.output)
        )
    else:
        write_text(None, output)
    return 0


def _next_demo_start_index(path):
    if not path:
        return 1
    try:
        text = read_text(path)
    except FileNotFoundError:
        return 1
    import re as _re

    numbers = [
        int(match.group(1)) for match in _re.finditer(r"\bdemo_[a-z]+_(\d+)\b", text)
    ]
    return (max(numbers) + 1) if numbers else 1


def command_markdown(args):
    items, diagnostics = _parse_or_exit(args.paths, _config(args))
    items = _filter_items_from_args(items, args)
    records = markdown_records(items, fields=args.field)

    if args.format == "json":
        output = json.dumps(
            records,
            ensure_ascii=False,
            indent=2 if args.pretty else None,
            separators=None if args.pretty else (",", ":"),
        )
        write_text(args.output, output + "\n")
    elif args.format == "jsonl":
        output = "\n".join(
            json.dumps(record, ensure_ascii=False, separators=(",", ":"))
            for record in records
        )
        if output:
            output += "\n"
        write_text(args.output, output)
    elif args.format == "text":
        write_text(args.output, markdown_records_to_text(records))
    else:
        write_text(args.output, markdown_records_to_html(records))

    _print_warnings(diagnostics)
    return 0


def _occurrence_export_records(items, args):
    if not getattr(args, "after", None) or not getattr(args, "before", None):
        raise ValueError("--occurrences requires both --after and --before.")
    range_start, range_end = parse_optional_time_range(args.after, args.before)
    records = agenda_records(items, range_start, range_end)
    filtered = filter_agenda_records(
        records,
        open_only=getattr(args, "open", False),
        statuses=getattr(args, "status", None),
        kinds=getattr(args, "kinds", None),
        projects=getattr(args, "project", None),
        tags=getattr(args, "tag", None),
        tag_all=getattr(args, "tag_all", None),
        exclude_tags=getattr(args, "exclude_tag", None),
        users=getattr(args, "user", None),
        persons=getattr(args, "person", None),
        owners=getattr(args, "owner", None),
        assignees=getattr(args, "assignee", None),
        attendees=getattr(args, "attendee", None),
        senders=getattr(args, "sender", None),
        recipients=getattr(args, "recipient", None),
        teams=getattr(args, "team", None),
        detail_filters=getattr(args, "detail", None),
        text=getattr(args, "text", None),
        user_aliases=config_user_aliases(_config(args)),
        team_members=config_team_members(_config(args)),
        team_aliases=config_team_aliases(_config(args)),
        tag_aliases=config_tag_aliases(_config(args)),
    )
    return _flatten_occurrence_records(filtered)


def _flatten_occurrence_records(records):
    flattened = []
    occurrence_keys = {
        "when",
        "key",
        "matches",
        "generated",
        "occurrence_start",
        "occurrence_end",
        "occurrence_index",
        "repeat_rule",
    }
    for record in records:
        matches = record.get("matches") or []
        if not matches:
            flattened.append(record)
            continue
        for match in matches:
            occurrence = OrderedDict()
            occurrence["when"] = format_match_time(match)
            occurrence["key"] = match.get("key", record.get("key", ""))
            for key, value in record.items():
                if key not in occurrence_keys:
                    occurrence[key] = value
            occurrence["matches"] = [match]
            occurrence["generated"] = bool(
                "occurrence_index" in match or "repeat" in match
            )
            start = match.get("start")
            end = match.get("end")
            if start:
                occurrence["occurrence_start"] = start
            if end:
                occurrence["occurrence_end"] = end
            if "occurrence_index" in match:
                occurrence["occurrence_index"] = match["occurrence_index"]
            if "repeat" in match:
                occurrence["repeat_rule"] = match["repeat"]
            flattened.append(occurrence)
    flattened.sort(
        key=lambda record: (
            record.get("occurrence_start") or record.get("when") or "",
            record.get("line") or 0,
        )
    )
    return flattened


def occurrence_records_to_csv(records):
    import csv as _csv
    import io as _io

    fields = (
        "when",
        "key",
        "line",
        "source_id",
        "occurrence_start",
        "occurrence_end",
        "occurrence_index",
        "repeat_rule",
        "status",
        "type",
        "title",
        "blocked",
        "blocked_by",
        "details",
        "text",
    )
    output = _io.StringIO()
    writer = _csv.DictWriter(output, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for record in records:
        row = OrderedDict()
        for field in fields:
            value = record.get(field, "")
            if field in ("details", "blocked_by") and value:
                value = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
            elif isinstance(value, bool):
                value = "true" if value else "false"
            elif value is None:
                value = ""
            row[field] = value
        writer.writerow(row)
    return output.getvalue()


def markdown_records(items, fields=None):
    selected_fields = _markdown_fields(fields)
    records = []
    for item in items:
        for field in selected_fields:
            if field == "title":
                raw_values = [item.title]
            else:
                raw_values = item.details.get(field) or []
            for index, raw in enumerate(raw_values):
                inline = field == "title"
                records.append(
                    OrderedDict(
                        [
                            ("source", getattr(item, "source", None)),
                            ("line", item.line),
                            ("type", item.kind),
                            ("status", item.status),
                            ("title", item.title),
                            ("field", field),
                            ("index", index),
                            ("raw", raw),
                            ("html", markdown_to_html(raw, inline=inline)),
                            ("text", markdown_to_plain(raw)),
                        ]
                    )
                )
    return records


def markdown_records_to_html(records):
    lines = []
    for record in records:
        title = markdown_to_html(record.get("title", ""), inline=True)
        location = _markdown_location(record)
        field = html.escape(str(record.get("field") or ""), quote=True)
        kind = html.escape(str(record.get("type") or ""), quote=True)
        status = html.escape(str(record.get("status") or ""), quote=True)
        lines.append(
            '<article class="lifetxt-markdown" data-field="%s" data-type="%s" data-status="%s">'
            % (field, kind, status)
        )
        lines.append(
            '<header><span class="lifetxt-markdown-meta">%s</span><span class="lifetxt-markdown-title">%s</span></header>'
            % (html.escape(location), title)
        )
        lines.append(
            '<div class="lifetxt-markdown-content">%s</div>'
            % (record.get("html") or "")
        )
        lines.append("</article>")
    if lines:
        return "\n".join(lines) + "\n"
    return ""


def markdown_records_to_text(records):
    chunks = []
    for record in records:
        header = "%s %s %s %s" % (
            _markdown_location(record),
            record.get("status") or "",
            record.get("type") or "",
            record.get("field") or "",
        )
        text = markdown_to_plain(record.get("raw") or "")
        chunks.append("%s\n%s" % (header.strip(), text))
    if chunks:
        return "\n\n".join(chunks) + "\n"
    return ""


def _markdown_fields(fields):
    raw_fields = _split_csv_args(fields) or ["body"]
    selected = []
    for field in raw_fields:
        key = field.strip().lower()
        if key == "all":
            candidates = ("title", "body", "note")
        elif key in ("title", "body", "note"):
            candidates = (key,)
        else:
            raise ValueError("--field must be title, body, note, or all.")
        for candidate in candidates:
            if candidate not in selected:
                selected.append(candidate)
    return selected


def _markdown_location(record):
    source = record.get("source") or ""
    line = record.get("line")
    if source and line:
        return "%s:%s" % (source, line)
    if line:
        return "line %s" % line
    if source:
        return source
    return "item"


def _expand_horizon(args):
    """The date recurring events are materialized up to, or None for the default."""
    value = getattr(args, "expand_until", None)
    if not value:
        return None
    parsed = parse_date_or_datetime(str(value))
    if parsed is None:
        raise ValueError("--expand-until %r is not a date." % value)
    if isinstance(parsed, datetime.datetime):
        return parsed
    return datetime.datetime(parsed.year, parsed.month, parsed.day, 23, 59, 59)


def command_import_ics(args):
    if args.append and not args.output:
        raise ValueError("--append requires --output.")

    items = []
    preset = getattr(args, "preset", "ics") or "ics"
    for path in _normalize_paths(args.paths):
        text = read_text(path)
        if preset == "ics":
            items.extend(
                items_from_ics_text(
                    text,
                    project=args.project,
                    tags=args.tag,
                    expand=bool(getattr(args, "expand_rrule", False)),
                    expand_until=_expand_horizon(args),
                    expand_count=getattr(args, "expand_count", None),
                )
            )
        elif preset == "markdown":
            items.extend(
                _items_from_markdown_task_text(
                    text,
                    project=args.project,
                    kind="T",
                    tags=args.tag,
                    source="markdown",
                )
            )
        elif preset == "todoist":
            items.extend(
                _items_from_todoist_csv_text(
                    text,
                    project=args.project,
                    tags=args.tag,
                )
            )
        elif preset == "github":
            items.extend(
                _items_from_github_issues_json_text(
                    text,
                    project=args.project,
                    tags=args.tag,
                )
            )
        else:
            raise ValueError("Unsupported import preset: %s" % preset)

    diagnostics = []
    for item in items:
        diagnostics.extend(validate_item(item))
    if _has_error(diagnostics):
        _print_diagnostics(diagnostics)
        return 1
    _print_warnings(diagnostics)

    output = _items_to_life_text(items, canonical=True)
    if args.append:
        _ensure_writable_path(args.output, _config(args), "import-ics")
        append_text(args.output, output)
    else:
        _ensure_writable_path(args.output, _config(args), "import-ics")
        write_text(args.output, output)
    return 0


def _items_from_markdown_task_text(
    text, project=None, kind="T", tags=None, source=None, github_refs=False
):
    import re as _re

    status_map = {
        " ": "[ ]",
        "x": "[x]",
        "X": "[x]",
        "-": "[-]",
        "/": "[/]",
    }
    task_re = _re.compile(
        r"^(?P<indent>\s*)[-*+]\s+\[(?P<check>[xX \-/])\]\s+(?P<title>.+)$"
    )
    github_ref_re = _re.compile(r"#(\d+)")
    items = []
    for line in text.splitlines():
        match = task_re.match(line)
        if not match:
            continue
        raw_title = match.group("title").strip()
        title = raw_title
        details = OrderedDict()
        _add_preset_detail(details, "source", source)
        if project:
            _add_preset_detail(details, "project", project)
        for tag in tags or []:
            _add_preset_detail(details, "tag", tag)
        if github_refs:
            refs = github_ref_re.findall(raw_title)
            title = github_ref_re.sub("", raw_title).strip()
            for ref in refs:
                _add_preset_detail(
                    details, "ref", "github-%s" % ref if source == "github" else ref
                )
        slug = title.replace(" ", "_") if title else raw_title.replace(" ", "_")
        items.append(
            Item(status_map.get(match.group("check"), "[ ]"), kind, slug, details)
        )
    return items


def _items_from_todoist_csv_text(text, project=None, tags=None):
    import csv as _csv

    reader = _csv.DictReader(text.splitlines())
    items = []
    for row in reader:
        normalized = {
            _normalize_import_key(key): (value or "").strip()
            for key, value in row.items()
            if key is not None
        }
        title = _first_import_value(normalized, "content", "task", "title", "name")
        if not title:
            continue
        details = OrderedDict()
        _add_preset_detail(details, "source", "todoist")
        uid = _first_import_value(normalized, "id", "task_id", "uid")
        _add_preset_detail(details, "uid", uid)
        if uid:
            _add_preset_detail(details, "id", "todoist-%s" % uid)
        _add_preset_detail(
            details,
            "project",
            project or _first_import_value(normalized, "project", "project_name"),
        )
        _add_preset_detail(
            details,
            "note",
            _first_import_value(normalized, "description", "comment", "note"),
        )
        _add_preset_detail(
            details,
            "due",
            _first_import_value(normalized, "date", "due", "due_date", "deadline"),
        )
        _add_preset_detail(
            details,
            "assignee",
            _first_import_value(normalized, "responsible", "assignee", "assigned_to"),
        )
        _add_preset_detail(
            details,
            "owner",
            _first_import_value(normalized, "author", "creator", "created_by"),
        )
        _add_preset_detail(
            details,
            "priority",
            _todoist_priority(
                _first_import_value(normalized, "priority", "priority_name")
            ),
        )
        for label in _split_preset_list(
            _first_import_value(normalized, "labels", "label", "tags")
        ):
            _add_preset_detail(details, "tag", label)
        for tag in tags or []:
            _add_preset_detail(details, "tag", tag)
        _add_preset_detail(
            details,
            "created",
            _date_prefix(
                _first_import_value(normalized, "created", "created_at", "date_added")
            ),
        )
        completed = _date_prefix(
            _first_import_value(
                normalized, "completed", "completed_at", "date_completed", "done"
            )
        )
        if completed:
            _add_preset_detail(details, "done", completed)
        status = (
            "[x]"
            if completed
            or _looks_done(
                _first_import_value(
                    normalized, "status", "state", "complete", "completed"
                )
            )
            else "[ ]"
        )
        items.append(Item(status, "T", title.replace(" ", "_"), details))
    return items


def _items_from_github_issues_json_text(text, project=None, tags=None):
    payload = json.loads(text)
    if isinstance(payload, dict):
        issues = (
            payload.get("items") or payload.get("issues") or payload.get("data") or []
        )
    else:
        issues = payload
    if not isinstance(issues, list):
        raise ValueError(
            "GitHub preset expects a JSON array or an object containing items/issues/data."
        )

    items = []
    for issue in issues:
        if not isinstance(issue, dict) or "pull_request" in issue:
            continue
        number = issue.get("number")
        title = str(issue.get("title") or "").strip()
        if not title:
            continue
        state = str(issue.get("state") or "open").lower()
        status = "[x]" if state in ("closed", "completed", "done") else "[ ]"
        details = OrderedDict()
        _add_preset_detail(details, "source", "github")
        if number is not None:
            _add_preset_detail(details, "id", "github-%s" % number)
            _add_preset_detail(details, "ref", "github-%s" % number)
        _add_preset_detail(details, "url", issue.get("html_url") or issue.get("url"))
        _add_preset_detail(details, "project", project)
        _add_preset_detail(details, "note", issue.get("body"))
        user = issue.get("user") if isinstance(issue.get("user"), dict) else None
        _add_preset_detail(details, "owner", user.get("login") if user else None)
        for assignee in _github_people(issue):
            _add_preset_detail(details, "assignee", assignee)
        for label in _github_labels(issue):
            _add_preset_detail(details, "tag", label)
        for tag in tags or []:
            _add_preset_detail(details, "tag", tag)
        _add_preset_detail(details, "created", _date_prefix(issue.get("created_at")))
        _add_preset_detail(details, "updated", _date_prefix(issue.get("updated_at")))
        closed_at = _date_prefix(issue.get("closed_at"))
        if closed_at:
            _add_preset_detail(details, "done", closed_at)
        items.append(Item(status, "T", title.replace(" ", "_"), details))
    return items


def _normalize_import_key(key):
    return str(key or "").strip().lower().replace(" ", "_").replace("-", "_")


def _first_import_value(row, *keys):
    for key in keys:
        value = row.get(key)
        if value:
            return value
    return None


def _split_preset_list(value):
    if not value:
        return []
    parts = []
    for raw in str(value).replace(";", ",").split(","):
        cleaned = raw.strip()
        if cleaned:
            parts.append(cleaned)
    return parts


def _todoist_priority(value):
    if not value:
        return None
    raw = str(value).strip().lower()
    mapping = {
        "p1": "A",
        "4": "A",
        "urgent": "A",
        "p2": "B",
        "3": "B",
        "high": "B",
        "p3": "C",
        "2": "C",
        "medium": "C",
        "p4": "D",
        "1": "D",
        "low": "D",
        "normal": "D",
    }
    return mapping.get(raw, str(value).strip())


def _looks_done(value):
    if value is None:
        return False
    return str(value).strip().lower() in (
        "1",
        "yes",
        "true",
        "done",
        "completed",
        "complete",
        "closed",
        "x",
    )


def _date_prefix(value):
    if not value:
        return None
    raw = str(value).strip()
    if not raw:
        return None
    if len(raw) >= 10 and raw[4:5] == "-" and raw[7:8] == "-":
        if len(raw) >= 16 and ("T" in raw[:20] or " " in raw[:20]):
            return raw.replace(" ", "T")[:16].rstrip("Z")
        return raw[:10]
    return raw


def _github_people(issue):
    people = []
    assignee = issue.get("assignee")
    if isinstance(assignee, dict) and assignee.get("login"):
        people.append(assignee["login"])
    for entry in issue.get("assignees") or []:
        if (
            isinstance(entry, dict)
            and entry.get("login")
            and entry["login"] not in people
        ):
            people.append(entry["login"])
    return people


def _github_labels(issue):
    labels = []
    for label in issue.get("labels") or []:
        if isinstance(label, dict):
            value = label.get("name")
        else:
            value = label
        if value:
            labels.append(str(value))
    return labels


def _add_preset_detail(details, key, value):
    if value is None:
        return
    if isinstance(value, bool):
        value = "true" if value else "false"
    text = str(value).strip()
    if not text:
        return
    details.setdefault(key, []).append(text)


def command_sync_ics(args):
    sources = _ics_sync_sources(args)
    items = []
    for index, source in enumerate(sources, 1):
        data = fetch_url(source["url"], args.timeout, args.user_agent, index)
        cache_dir = args.cache_dir or _sync_config(args).get("cache_dir")
        if cache_dir and not args.dry_run:
            cache_name = _ics_cache_name(source, index)
            write_bytes(os.path.join(cache_dir, cache_name), data)
        project = args.project if args.project is not None else source.get("project")
        if project is None:
            project = _sync_config(args).get("project")
        tags = list(args.tag) if args.tag else list(source.get("tags", []))
        if not tags:
            tags = list(_sync_config(args).get("tags", []))
        items.extend(
            items_from_ics_text(
                decode_ics_bytes(data),
                project=project,
                tags=tags,
                expand=bool(getattr(args, "expand_rrule", False)),
                expand_until=_expand_horizon(args),
                expand_count=getattr(args, "expand_count", None),
            )
        )

    items = _dedupe_items_by_detail_id(items)
    output = _validated_life_text_or_exit(items)
    if output is None:
        return 1
    output_path = args.output or _sync_config(args).get("output")
    if getattr(args, "merge_existing", False):
        if not output_path:
            raise ValueError(
                "--merge-existing requires --output or sync_ics.output in config."
            )
        existing_text = read_text(output_path) if os.path.exists(output_path) else ""
        output = _merge_generated_items_into_text(
            existing_text,
            items,
            id_key=id_key_from_config(_config(args)),
            soft_delete_missing=getattr(args, "soft_delete_missing", False),
        )
    if args.dry_run:
        write_text(None, output)
    else:
        if output_path:
            ensure_parent_dir(output_path)
            _ensure_writable_path(
                output_path, _config(args), "sync-ics", allow_generated=True
            )
        write_text(output_path, output)
    return 0


def _dedupe_items_by_detail_id(items, id_key="id"):
    by_id = OrderedDict()
    no_id = []
    for item in items:
        values = item.details.get(id_key, [])
        item_id = str(values[0]) if values else ""
        if not item_id:
            no_id.append(item)
            continue
        by_id[item_id] = item
    return no_id + list(by_id.values())


def _merge_generated_items_into_text(
    existing_text, generated_items, id_key="id", soft_delete_missing=False
):
    if not existing_text:
        return _items_to_life_text(generated_items, canonical=True)
    existing_items, diagnostics = parse_text(
        existing_text, id_key=id_key, check_ids=False, check_references=False
    )
    if _has_error(diagnostics):
        raise ValueError("Existing sync output has parse errors; refusing to merge.")

    generated_by_id = OrderedDict()
    for item in generated_items:
        item_ids = item.details.get(id_key, [])
        if item_ids:
            generated_by_id[str(item_ids[0])] = item

    used_ids = set()
    replacements = {}
    for item in existing_items:
        item_ids = item.details.get(id_key, [])
        item_id = str(item_ids[0]) if item_ids else ""
        if not item_id:
            continue
        if item_id in generated_by_id:
            replacements[item.line] = (
                getattr(item, "end_line", item.line),
                item_to_line(generated_by_id[item_id]) + "\n",
            )
            used_ids.add(item_id)
            continue
        if (
            soft_delete_missing
            and item.kind == "E"
            and "ics" in item.details.get("source", [])
        ):
            from copy import deepcopy as _deepcopy

            canceled = _deepcopy(item)
            canceled.status = "[-]"
            if not canceled.details.get("reason"):
                canceled.details["reason"] = ["missing_from_feed"]
            canceled.source_text = None
            replacements[item.line] = (
                getattr(item, "end_line", item.line),
                item_to_line(canceled) + "\n",
            )

    lines = existing_text.splitlines(keepends=True)
    merged = []
    index = 1
    while index <= len(lines):
        replacement = replacements.get(index)
        if replacement:
            end_line, text = replacement
            merged.append(text)
            index = end_line + 1
            continue
        merged.append(lines[index - 1])
        index += 1

    new_lines = []
    for item_id, item in generated_by_id.items():
        if item_id not in used_ids:
            new_lines.append(item_to_line(item))
    if new_lines:
        if merged and merged[-1] and not merged[-1].endswith(("\n", "\r")):
            merged.append("\n")
        if merged and any(line.strip() for line in merged):
            merged.append("\n")
        merged.append("\n".join(new_lines) + "\n")
    return "".join(merged)


def command_serve(args):
    if getattr(args, "mcp", False):
        return command_mcp(args)
    try:
        import uvicorn

        from .webapp import create_app
    except ImportError as exc:
        raise ValueError(
            "Web dependencies are not installed. Run: pip install -r requirements-web.txt"
        ) from exc

    web_config = config_section(_config(args), "web")
    paths = _normalize_paths(
        list(args.paths)
        if args.paths
        else (config_paths(_config(args)) or ["life.txt"]),
        _config(args),
        stdin_when_empty=False,
    )
    writable_path = args.write_file or config_write_file(_config(args)) or paths[0]
    host = args.host or web_config.get("host") or "127.0.0.1"
    port = args.port or int(web_config.get("port") or 8000)
    read_only = getattr(args, "read_only", False) or _truthy_config(
        web_config.get("read_only")
    )
    config = _config(args)
    token_env = getattr(args, "token_env", None) or web_config.get("token_env")
    if token_env:
        token = os.environ.get(str(token_env), "")
        if not token:
            raise ValueError(
                "Environment variable %s (API bearer token) is not set." % token_env
            )
        config = _config_with_api_token(config, token)
    if _is_public_bind_host(host) and not read_only and not _config_api_token(config):
        if not getattr(args, "insecure_public", False) and not _truthy_config(
            web_config.get("insecure_public")
        ):
            raise ValueError(
                "Refusing to start a writable public Web server without an API token. "
                "Use --token-env ENVVAR, --read-only, or --insecure-public."
            )
    _preflight_bind(host, port)
    app = create_app(
        paths=paths, writable_path=writable_path, config=config, read_only=read_only
    )
    # uvicorn.Config independently reads WEB_CONCURRENCY from the environment
    # and sets its own workers count from it, regardless of caller intent
    # (uvicorn/config.py). serve has no --workers flag and passes an
    # in-memory app object rather than an import string, which uvicorn
    # cannot fan out to worker subprocesses -- left alone, a stray
    # WEB_CONCURRENCY > 1 (e.g. inherited from an unrelated gunicorn
    # environment) makes uvicorn refuse to start with a warning that names
    # neither lifetxt nor WEB_CONCURRENCY as the cause. serve is
    # single-process by design, so pin workers=1 explicitly rather than
    # let the environment decide.
    uvicorn.run(app, host=host, port=port, workers=1)
    return 0


def _preflight_bind(host, port):
    """Fail with an actionable message when the port cannot be bound.

    uvicorn reports the raw OS error after it has already printed "Application
    startup complete", which reads like a successful start. Checking first lets
    the message name the actual cause, including the Windows case where a port
    is administratively reserved even though nothing is listening on it.
    """
    import socket

    probe = socket.socket(
        socket.AF_INET6 if ":" in str(host) else socket.AF_INET, socket.SOCK_STREAM
    )
    try:
        if os.name != "nt":
            # POSIX needs SO_REUSEADDR so a socket left in TIME_WAIT does not
            # look like a conflict. On Windows the same option lets a probe
            # bind a port another server is already listening on, which would
            # make this check silently useless.
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        probe.bind((host, int(port)))
    except OSError as exc:
        raise ValueError(_bind_error_message(host, port, exc))
    finally:
        probe.close()


def _suggest_port(port):
    """A different port to try, never the one that just failed."""
    try:
        number = int(port)
    except (TypeError, ValueError):
        return 8080
    candidate = 8080 if number != 8080 else 8090
    return candidate if candidate != number else number + 1


def _bind_error_message(host, port, exc):
    errno = getattr(exc, "errno", None)
    winerror = getattr(exc, "winerror", None)
    lines = ["Cannot bind %s:%s (%s)." % (host, port, exc)]

    in_use = errno in (48, 98) or winerror == 10048
    forbidden = errno == 13 or winerror == 10013

    suggestion = _suggest_port(port)

    if in_use:
        lines.append("Another process is already using that port.")
        lines.append(
            "Stop it, or start on a different port: lifetxt serve --port %d"
            % suggestion
        )
    elif forbidden and os.name == "nt":
        # Hyper-V, WSL, and Docker reserve blocks of ports on Windows. Nothing
        # is listening, so "port in use" advice sends people down a dead end.
        lines.append(
            "Windows is reserving that port, so nothing can bind it even though "
            "nothing is listening."
        )
        lines.append("Check the reserved ranges with:")
        lines.append("  netsh interface ipv4 show excludedportrange protocol=tcp")
        lines.append("Then start outside those ranges, for example:")
        lines.append("  lifetxt serve --port %d" % suggestion)
    elif forbidden:
        lines.append("Ports below 1024 need elevated privileges on this system.")
        lines.append(
            "Use a port above 1024, for example: lifetxt serve --port %d" % suggestion
        )
    else:
        lines.append("Try a different --port, or --host 127.0.0.1.")
    return "\n".join(lines)


def _truthy_config(value):
    if isinstance(value, bool):
        return value
    text = str(value or "").strip().lower()
    return text in ("1", "true", "yes", "on")


def _is_public_bind_host(host):
    text = str(host or "").strip().lower()
    return text not in ("", "127.0.0.1", "localhost", "::1")


def _config_api_token(config):
    api = config_section(config or {}, "api")
    return str(api.get("token") or "").strip()


def _config_with_api_token(config, token):
    from copy import deepcopy as _deepcopy

    copied = _deepcopy(config or {})
    api = copied.setdefault("api", {})
    if not isinstance(api, dict):
        api = {}
        copied["api"] = api
    api["token"] = token
    return copied


def command_mcp(args):
    from .mcp import cmd_mcp

    return cmd_mcp(args)


def _split_archive_text(
    raw_text, items, archive_id_set, archive_overrides=None, remainder_overrides=None
):
    """Split raw_text into (archive_text, remainder_text) preserving non-item lines.

    Non-item lines (comments, blanks, directives) appear in BOTH outputs.
    archive_overrides: {id(item): str} replacement text for an archived item.
    remainder_overrides: {id(item): Item|None} replacement/exclusion for remainder items.
    """
    archive_overrides = archive_overrides or {}
    remainder_overrides = remainder_overrides or {}

    raw_lines = raw_text.splitlines(keepends=True)

    line_to_item = {}
    for item in items:
        start = getattr(item, "line", 0)
        end = getattr(item, "end_line", start)
        for ln in range(max(1, start), end + 1):
            line_to_item[ln] = item

    archive_out = []
    remainder_out = []
    custom_written = set()

    for i, raw_line in enumerate(raw_lines):
        lineno = i + 1
        item = line_to_item.get(lineno)

        if item is None:
            archive_out.append(raw_line)
            remainder_out.append(raw_line)
        elif id(item) in archive_id_set:
            item_id = id(item)
            if item_id in custom_written:
                pass
            elif item_id in archive_overrides:
                text = archive_overrides[item_id]
                if text is not None:
                    archive_out.append(text if text.endswith("\n") else text + "\n")
                custom_written.add(item_id)
            else:
                archive_out.append(raw_line)
        else:
            item_id = id(item)
            if item_id in custom_written:
                pass
            elif item_id in remainder_overrides:
                modified = remainder_overrides[item_id]
                if modified is not None:
                    text = getattr(modified, "source_text", None) or item_to_line(
                        modified
                    )
                    remainder_out.append(text if text.endswith("\n") else text + "\n")
                custom_written.add(item_id)
            else:
                remainder_out.append(raw_line)

    return "".join(archive_out), "".join(remainder_out)


def _path_revision_map(values):
    result = {}
    for raw in values or []:
        text = str(raw)
        if "=" not in text:
            raise ValueError("--revision must use PATH=SHA256.")
        path, revision = text.rsplit("=", 1)
        if not path.strip() or not revision.strip():
            raise ValueError("--revision must use PATH=SHA256.")
        result[os.path.abspath(path.strip())] = revision.strip()
    return result


def command_archive(args):
    config = _config(args)
    paths = _normalize_paths(args.paths, config, stdin_when_empty=False)
    if not paths:
        raise ValueError("No source files specified.")

    mode = "copy" if args.copy else "move"
    if mode == "move" and "-" in paths:
        raise ValueError(
            "Cannot use move mode with stdin input. Use --copy or specify a file path."
        )

    before_date = None
    if args.before:
        before_date = parse_date_or_datetime(args.before, is_end=False)
        if before_date is None:
            raise ValueError(
                "Invalid --before date %r. Use YYYY-MM-DD or YYYY-MM-DDTHH:MM."
                % args.before
            )

    if args.max_items is not None and args.max_items < 1:
        raise ValueError("--max-items must be a positive integer.")

    id_key = id_key_from_config(config)
    from .mutation import read_text_snapshot

    file_texts = OrderedDict()
    file_snapshots = OrderedDict()
    file_items = OrderedDict()
    for path in paths:
        snapshot = read_text_snapshot(path)
        text = snapshot.text
        file_snapshots[path] = snapshot
        file_texts[path] = text
        items, _diags = parse_text(
            text, id_key=id_key, check_ids=False, check_references=False
        )
        for item in items:
            item.source = path
        file_items[path] = items

    all_items = [item for items in file_items.values() for item in items]

    statuses_arg = args.statuses or ["done,canceled"]
    try:
        candidates = filter_items(all_items, statuses=statuses_arg)
    except ValueError as exc:
        raise ValueError("Invalid --status: %s" % exc)

    project_filter = getattr(args, "project_filter", None)
    if project_filter:
        candidates = [
            item
            for item in candidates
            if project_filter in item.details.get("project", [])
        ]

    if before_date is not None:
        candidates = [
            item for item in candidates if _archive_item_date_before(item, before_date)
        ]

    if args.max_items is not None:
        candidates = candidates[: args.max_items]

    if not candidates:
        sys.stdout.write("No items match the archive criteria.\n")
        return 0

    orphan_mode = getattr(args, "orphan_children", "block")
    open_statuses_set = {"[ ]", "[/]", "[>]", "[?]"}
    candidate_ids = set()
    for item in candidates:
        for val in item.details.get(id_key, []):
            candidate_ids.add(str(val))

    open_children_by_parent = {}
    if candidate_ids:
        candidate_id_set = {id(item) for item in candidates}
        for item in all_items:
            if id(item) in candidate_id_set:
                continue
            if item.status not in open_statuses_set:
                continue
            for parent_val in item.details.get("parent", []):
                pid = str(parent_val)
                if pid in candidate_ids:
                    open_children_by_parent.setdefault(pid, []).append(item)

    if open_children_by_parent:
        if orphan_mode == "block":
            sys.stdout.write(
                "Cannot archive: the following candidates have open children:\n"
            )
            for pid, children in open_children_by_parent.items():
                child_ids = (
                    ", ".join(
                        str(v) for c in children for v in c.details.get(id_key, [])
                    )
                    or "(no id)"
                )
                sys.stdout.write("  parent %s: open children %s\n" % (pid, child_ids))
            sys.stdout.write(
                "Use --orphan-children adopt or --orphan-children promote to proceed.\n"
            )
            return 1

        elif orphan_mode == "adopt":
            already = {id(item) for item in candidates}
            for children in open_children_by_parent.values():
                for child in children:
                    if id(child) not in already:
                        candidates.append(child)
                        already.add(id(child))

        # promote: archive parent only; children lose parent: in source (handled below)

    if project_filter:
        # Ticket history (record:ticket_event / record:time_entry Notes) has no
        # "done"/"canceled" status of its own, so it never matches the status
        # filter above; follow it unconditionally via parent: so a ticket's
        # history moves with it instead of being left behind as a dangling log.
        history_ids = {id(item) for item in candidates}
        for item in all_items:
            if id(item) in history_ids:
                continue
            markers = item.details.get("record", [])
            if not markers or markers[0] not in ("ticket_event", "time_entry"):
                continue
            if any(
                str(value) in candidate_ids for value in item.details.get("parent", [])
            ):
                candidates.append(item)
                history_ids.add(id(item))

    multi_source = len(paths) > 1
    sys.stdout.write(
        "Items to archive (%d, %s -> %s):\n" % (len(candidates), mode, args.dest)
    )
    for item in candidates:
        source_label = ("  [%s]" % item.source) if multi_source else ""
        sys.stdout.write(
            "  %s %s %s%s\n" % (item.status, item.kind, item.title, source_label)
        )

    _ext_ref_keys = ("depends_on", "blocks", "parent", "ref", "related")
    candidate_obj_ids = {id(c) for c in candidates}
    external_refs = []
    for item in all_items:
        if id(item) in candidate_obj_ids:
            continue
        for key in _ext_ref_keys:
            for val in item.details.get(key, []):
                if str(val) in candidate_ids:
                    external_refs.append((item, key, str(val)))

    if external_refs:
        sys.stdout.write("Warning: the following items reference IDs being archived:\n")
        for ref_item, key, ref_id in external_refs:
            location = getattr(ref_item, "source", None) or "?"
            sys.stdout.write(
                "  %s:%d %s %s:%s\n"
                % (location, ref_item.line, ref_item.title, key, ref_id)
            )
        if getattr(args, "block_on_external_refs", False):
            sys.stdout.write(
                "Blocked by %d external reference(s). Remove references or archive referencing items first.\n"
                % len(external_refs)
            )
            return 1

    if args.dry_run:
        sys.stdout.write("(dry run - no changes made)\n")
        return 0

    if not args.yes:
        sys.stdout.write("Archive %d item(s)? [y/N] " % len(candidates))
        sys.stdout.flush()
        answer = sys.stdin.readline().strip().lower()
        if answer not in ("y", "yes"):
            sys.stdout.write("Aborted.\n")
            return 0

    adopted_ids = set()
    if orphan_mode == "adopt":
        for children in open_children_by_parent.values():
            for child in children:
                adopted_ids.add(id(child))

    preserve = getattr(args, "preserve_structure", False)

    if preserve:
        from copy import deepcopy as _deepcopy

        archive_parts = []
        for path, items in file_items.items():
            path_archive_ids = {
                id(item) for item in candidates if getattr(item, "source", None) == path
            }
            if not path_archive_ids:
                continue
            ao = {}
            for item in candidates:
                if getattr(item, "source", None) == path and id(item) in adopted_ids:
                    adopted = _deepcopy(item)
                    adopted.status = "[-]"
                    ao[id(item)] = item_to_line(adopted)
            archive_part, _ = _split_archive_text(
                file_texts[path], items, path_archive_ids, archive_overrides=ao
            )
            archive_parts.append(archive_part)
        archive_text = "".join(archive_parts)
    else:
        if orphan_mode == "adopt":

            def _adopt_item_text(item):
                if id(item) in adopted_ids:
                    from copy import deepcopy as _deepcopy

                    adopted = _deepcopy(item)
                    adopted.status = "[-]"
                    return item_to_line(adopted)
                return getattr(item, "source_text", None) or item_to_line(item)

            archive_lines = [_adopt_item_text(item) for item in candidates]
            archive_text = "\n".join(archive_lines)
            if archive_text:
                archive_text += "\n"
        else:
            archive_text = _items_to_life_text(candidates)

    from .mutation import MISSING_HASH, read_text_snapshot
    from .transaction_journal import journal_directory
    from .write_operations import commit_text_replacements

    revisions = _path_revision_map(getattr(args, "revision", None))
    destination = os.path.abspath(args.dest)
    source_absolutes = [os.path.abspath(path) for path in paths]
    if destination in source_absolutes:
        raise ValueError(
            "Archive destination must be different from every source file."
        )

    _ensure_writable_path(args.dest, config, "archive")
    _pre_write_backup(args.dest, config, "archive")
    dest_snapshot = read_text_snapshot(args.dest, allow_missing=True)
    prefix = (
        ""
        if not dest_snapshot.text or dest_snapshot.text.endswith(("\n", "\r"))
        else dest_snapshot.newline
    )
    replacements = {
        destination: {
            "text": dest_snapshot.text + prefix + archive_text,
            "expected_revision": revisions.get(destination, dest_snapshot.content_hash),
            "create": dest_snapshot.content_hash == MISSING_HASH,
            "validate_life": True,
        }
    }

    if mode == "move":
        archive_ids = {id(item) for item in candidates}
        promote_parent_ids = candidate_ids if orphan_mode == "promote" else set()

        for path, items in file_items.items():

            def _promote_item(item):
                if promote_parent_ids and item.details.get("parent"):
                    new_parents = [
                        p
                        for p in item.details["parent"]
                        if str(p) not in promote_parent_ids
                    ]
                    if len(new_parents) < len(item.details["parent"]):
                        from copy import deepcopy as _deepcopy

                        promoted = _deepcopy(item)
                        if new_parents:
                            promoted.details["parent"] = new_parents
                        else:
                            del promoted.details["parent"]
                        promoted.source_text = None
                        return promoted
                return item

            remainder_text = None
            needs_write = False
            if preserve:
                path_archive_ids = {
                    id(item)
                    for item in candidates
                    if getattr(item, "source", None) == path
                }
                ro = {}
                for item in items:
                    if id(item) not in path_archive_ids:
                        modified = _promote_item(item)
                        if id(modified) != id(item):
                            ro[id(item)] = modified
                _, remainder_text = _split_archive_text(
                    file_texts[path], items, path_archive_ids, remainder_overrides=ro
                )
                needs_write = bool(path_archive_ids) or bool(ro)
            else:
                remaining_raw = [item for item in items if id(item) not in archive_ids]
                remaining = [_promote_item(item) for item in remaining_raw]
                needs_write = len(remaining) < len(items) or any(
                    id(r) != id(o) for r, o in zip(remaining, remaining_raw)
                )
                if needs_write:
                    remainder_text = _items_to_life_text(remaining)
            if needs_write:
                _ensure_writable_path(path, config, "archive")
                _pre_write_backup(path, config, "archive")
                absolute = os.path.abspath(path)
                source_snapshot = file_snapshots[path]
                replacements[absolute] = {
                    "text": remainder_text,
                    "expected_revision": revisions.get(
                        absolute, source_snapshot.content_hash
                    ),
                    "create": False,
                    "validate_life": True,
                }

    result = commit_text_replacements(
        replacements,
        operation="archive.%s" % mode,
        journal_dir=journal_directory(config, writable_path=args.dest),
        config=config,
    )
    sys.stdout.write(
        "Archived %d item(s) to %s (transaction %s).\n"
        % (len(candidates), args.dest, result.transaction_id)
    )
    return 0


def _archive_item_date_before(item, before_date):
    for key in ("done", "updated", "created"):
        for value in item.details.get(key, []):
            parsed = parse_date_or_datetime(str(value))
            if parsed is not None:
                return parsed < before_date
    return False


def _parse_date_only(value):
    """Parse a YYYY-MM-DD string to datetime.date, returning None on failure."""
    s = str(value)
    if len(s) >= 10 and s[4:5] == "-" and s[7:8] == "-":
        try:
            return datetime.date(int(s[:4]), int(s[5:7]), int(s[8:10]))
        except (ValueError, IndexError):
            pass
    return None


def _latest_item_date(item):
    """Return the most recent parsed date from common date detail keys."""
    best = None
    for key in ("updated", "created", "done", "do", "due", "on"):
        for val in item.details.get(key, []):
            parsed = _parse_date_only(str(val))
            if parsed and (best is None or parsed > best):
                best = parsed
    return best


def _load_file_directives(path):
    """Read #! directives from a file, returning an empty dict on any error."""
    if not path or path == "-":
        return {}
    try:
        return parse_directives(read_text(path))
    except OSError:
        return {}


def _resolve_relative_date(value, today=None):
    """Resolve relative date keywords to ISO YYYY-MM-DD strings.

    Thin wrapper over shorthand.resolve_date_token so the CLI, TUI, Web UI, and
    MCP all accept exactly the same tokens. Unknown values are returned
    unchanged for backward compatibility.
    """
    from .shorthand import resolve_date_token

    return resolve_date_token(value, today=today, strict=False)


def _merge_capture_shorthand(item, args):
    """Expand @project #tag !priority ^due out of a captured title.

    Explicit flags win for single-valued keys; tags accumulate, because
    `--tag a` plus `#b` on the same capture clearly means both.
    """
    if getattr(args, "no_shorthand", False):
        return
    from .shorthand import ShorthandError, parse_capture

    try:
        title, details = parse_capture(item.title, strict_dates=True)
    except ShorthandError as exc:
        raise ValueError(str(exc))
    if not details:
        return
    if not title:
        raise ValueError(
            "Capture shorthand consumed the whole title. Quote it or pass --no-shorthand."
        )
    item.title = title
    for key, values in details.items():
        if key == "tag":
            existing = item.details.setdefault(key, [])
            for value in values:
                if value not in existing:
                    existing.append(value)
        elif key not in item.details:
            item.details[key] = list(values)


def command_quick(args):
    config = _config(args)
    today = timezone_today()

    if args.title == "-":
        stdin_title = sys.stdin.readline().rstrip("\r\n")
        if not stdin_title:
            raise ValueError("quick - requires a non-empty title on stdin.")
        args.title = stdin_title

    if args.due:
        args.due = [_resolve_relative_date(v, today) for v in args.due]
    if args.do:
        args.do = [_resolve_relative_date(v, today) for v in args.do]
    if args.until:
        args.until = [_resolve_relative_date(v, today) for v in args.until]

    if not args.kind:
        args.kind = "T"
    if args.status is None:
        args.status = None

    item = build_item_from_args(args)
    _merge_capture_shorthand(item, args)
    dest = args.append or config_write_file(config)
    file_directives = _load_file_directives(dest)
    apply_config_defaults_to_item(item, args, file_directives)
    apply_auto_id_to_item(item, args)
    line = item_to_assisted_line(item)

    if not args.no_check:
        parsed_items, diagnostics = parse_text(line + "\n")
        if not parsed_items:
            diagnostics.append(
                Diagnostic("error", "E301", "Generated line did not produce an item.")
            )
        if _has_error(diagnostics):
            _print_diagnostics(diagnostics)
            return 1
        _print_warnings(diagnostics)

    if not dest:
        raise ValueError(
            "No output file. Use --append FILE or configure write_file in config."
        )

    _ensure_writable_path(dest, config, "quick")
    _pre_write_backup(dest, config, "quick")
    from .write_operations import append_life_records

    append_life_records(
        dest,
        line + "\n",
        expected_revision=getattr(args, "revision", None),
        operation="quick.capture",
    )
    sys.stdout.write("%s\n" % line)
    return 0


def _resolve_target_item(items, id_key, args, prompt_verb="Select"):
    """Locate one item by --line, id, or --text. Returns (item, aborted).

    aborted is True when a --text query matched multiple items and the
    user declined to pick one; callers should print nothing further and
    return 0 in that case.
    """
    if getattr(args, "line", None) is not None:
        matches = [item for item in items if item.line == args.line]
        if not matches:
            raise ValueError("No item at line %d." % args.line)
        return matches[0], False

    item_id = getattr(args, "id", None)
    if item_id:
        matches = [
            item
            for item in items
            if item_id in [str(v) for v in item.details.get(id_key, [])]
        ]
        if not matches:
            raise ValueError("No item with %s:%s." % (id_key, item_id))
        if len(matches) > 1:
            raise ValueError("Multiple items with %s:%s." % (id_key, item_id))
        return matches[0], False

    text_query = getattr(args, "text", None)
    if text_query:
        query = text_query.lower()
        matches = [item for item in items if query in item.title.lower()]
        if not matches:
            raise ValueError("No item matching %r." % text_query)
        if len(matches) > 1:
            sys.stdout.write("Multiple items match:\n")
            for i, m in enumerate(matches):
                sys.stdout.write(
                    "  [%d] %s %s %s\n" % (i + 1, m.status, m.kind, m.title)
                )
            sys.stdout.write("%s which item? (1-%d) " % (prompt_verb, len(matches)))
            sys.stdout.flush()
            answer = sys.stdin.readline().strip()
            try:
                idx = int(answer) - 1
                if idx < 0 or idx >= len(matches):
                    raise ValueError()
                return matches[idx], False
            except (ValueError, IndexError):
                sys.stdout.write("Aborted.\n")
                return None, True
        return matches[0], False

    raise ValueError("Specify an ID, --line N, or --text QUERY.")


def _done_precision(args, config):
    """Decide whether done: carries a time, honouring flags then config."""
    if getattr(args, "date_only", False):
        return "date"
    if getattr(args, "now", False):
        return "datetime"
    section = config_section(config, "done")
    value = str(section.get("precision") or "date").strip().lower()
    if value not in ("date", "datetime"):
        raise ValueError(
            "config done.precision must be date or datetime, not %r."
            % section.get("precision")
        )
    return value


def _completion_stamp(args, config, moment=None):
    """Build the done: value at the configured precision.

    Returns (value_written, date_object). The date object is what habit
    duplicate-detection and repeat anchoring compare on, so adding a time never
    changes which calendar day a completion belongs to.
    """
    date_arg = getattr(args, "date", None)
    if date_arg:
        parsed = parse_date_or_datetime(date_arg, is_end=False)
        if parsed is None:
            raise ValueError("Invalid --date %r. Use YYYY-MM-DD." % date_arg)
        if _done_precision(args, config) == "datetime" and "T" in str(date_arg):
            return parsed.strftime("%Y-%m-%dT%H:%M"), parsed.date()
        return parsed.date().isoformat(), parsed.date()
    moment = moment or local_now_naive()
    if _done_precision(args, config) == "datetime":
        return moment.strftime("%Y-%m-%dT%H:%M"), moment.date()
    return moment.date().isoformat(), moment.date()


def _state_write_path(args, config):
    path = getattr(args, "path", None) or config_write_file(config)
    if not path:
        raise ValueError(
            "No output file. Pass a path or configure write_file in your config."
        )
    return path


def _attachment_diagnostics_for_check(items, config, args):
    """Attachment warnings for `check`.

    Existence and portability are always checked because they are cheap.
    Hash verification touches every referenced file and can walk whole
    directory trees, so it stays opt-in behind --verify-files; `lifetxt files`
    is the command for that.
    """
    from .attachments import ATTACHMENT_KEYS, attachment_diagnostics

    if not any(item.details.get(key) for item in items for key in ATTACHMENT_KEYS):
        return []
    if getattr(args, "no_files", False):
        return []
    return attachment_diagnostics(
        items, config=config, verify=bool(getattr(args, "verify_files", False))
    )


def command_files(args):
    """Inspect, verify, and refresh file:/dir: attachments."""
    from .attachments import (
        ATTACHMENT_KEYS,
        STATUS_CHANGED,
        STATUS_ERROR,
        STATUS_MISSING,
        STATUS_WRONG_TYPE,
        attachment_records,
        item_base_dir,
        update_item_hashes,
    )

    config = _config(args)
    id_key = id_key_from_config(config)
    paths = _normalize_paths(args.paths, config)
    verify = not getattr(args, "no_verify", False)
    problem_statuses = (STATUS_MISSING, STATUS_CHANGED, STATUS_WRONG_TYPE, STATUS_ERROR)

    rows = []
    problems = 0
    updates = []
    file_revisions = {}

    for path in paths:
        from .mutation import read_text_snapshot

        _snapshot = read_text_snapshot(path)
        text = _snapshot.text
        file_revisions[path] = _snapshot.content_hash
        items, diagnostics = parse_text(
            text, id_key=id_key, check_ids=False, check_references=False
        )
        if _has_error(diagnostics):
            _print_diagnostics(diagnostics)
            return 1
        for item in items:
            item.source = path
        wanted = getattr(args, "item_id", None)
        targets = [
            item
            for item in items
            if not wanted or wanted in [str(v) for v in item.details.get(id_key, [])]
        ]

        if getattr(args, "update", False):
            changed_any = False
            for item in targets:
                changes = update_item_hashes(
                    item, base_dir=item_base_dir(item), config=config
                )
                for key, old, new in changes:
                    updates.append(
                        {
                            "path": path,
                            "item": item.title,
                            "key": key,
                            "from": old,
                            "to": new,
                        }
                    )
                    changed_any = True
            if changed_any and not getattr(args, "dry_run", False):
                _ensure_writable_path(path, config, "files")
                _pre_write_backup(path, config, "files")
                from .mutation import write_text as mutation_write_text

                mutation_write_text(
                    path,
                    _render_items_preserving(text, items),
                    expected_hash=file_revisions[path],
                    operation="files.update_hashes",
                    create=False,
                )

        for item in targets:
            base_dir = item_base_dir(item)
            for record in attachment_records(
                item, base_dir=base_dir, config=config, verify=verify
            ):
                is_problem = record["status"] in problem_statuses or record["notes"]
                if record["status"] in problem_statuses:
                    problems += 1
                if getattr(args, "problems", False) and not is_problem:
                    continue
                rows.append(
                    OrderedDict(
                        [
                            ("source", path),
                            ("id", (item.details.get(id_key) or [""])[0]),
                            ("title", item.title),
                            ("key", record["key"]),
                            ("path", record["path"]),
                            ("resolved", record["resolved"]),
                            ("status", record["status"]),
                            ("hash", record["hash"]),
                            ("actual_hash", record["actual_hash"]),
                            ("notes", record["notes"]),
                        ]
                    )
                )

    if getattr(args, "format", "text") == "json":
        payload = {"count": len(rows), "problems": problems, "attachments": rows}
        if updates:
            payload["updates"] = updates
        write_text(None, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    else:
        for update in updates:
            prefix = "[dry-run] " if getattr(args, "dry_run", False) else ""
            sys.stdout.write(
                "%shashed %s: %s\n" % (prefix, update["key"], update["to"])
            )
        if rows:
            table = [
                OrderedDict(
                    [
                        ("status", row["status"]),
                        ("key", row["key"]),
                        ("path", row["path"]),
                        ("id", row["id"]),
                        ("title", row["title"]),
                    ]
                )
                for row in rows
            ]
            columns = ["status", "key", "path", "id", "title"]
            sys.stdout.write("\n".join(_format_table(table, columns)) + "\n")
            for row in rows:
                for note in row["notes"]:
                    sys.stdout.write(
                        "  note %s:%s %s\n" % (row["key"], row["path"], note)
                    )
        elif not updates:
            sys.stdout.write("No file: or dir: attachments found.\n")

    if getattr(args, "check", False) and problems:
        sys.stderr.write("%d attachment problem(s).\n" % problems)
        return 1
    return 0


def _render_items_preserving(original_text, items):
    """Re-render only the lines that own an item, leaving everything else alone."""
    lines = original_text.splitlines(True)
    ending = "\r\n" if original_text.count("\r\n") else "\n"
    for item in items:
        if item.line is None:
            continue
        start = item.line - 1
        end = getattr(item, "end_line", item.line) or item.line
        lines[start:end] = (item_to_line(item) + ending).splitlines(True)
    return "".join(lines)


def command_rrule(args):
    """Expand a recurrence rule into occurrences."""
    from .recurrence import (
        WEEKDAY_NAMES,
        RecurrenceError,
        describe,
        expand,
        parse_rule,
        rule_for_item,
    )

    config = _config(args)
    source_item = None
    rule = None
    start_text = getattr(args, "start", None)

    if getattr(args, "item_id", None):
        if not args.path:
            raise ValueError("--id requires --path FILE.")
        id_key = id_key_from_config(config)
        items, _diagnostics = _parse_life_inputs([args.path], config)
        matches = [
            item
            for item in items
            if args.item_id in [str(v) for v in item.details.get(id_key, [])]
        ]
        if not matches:
            raise ValueError(
                "No item with %s:%s in %s." % (id_key, args.item_id, args.path)
            )
        source_item = matches[0]
        try:
            rule = rule_for_item(source_item)
        except RecurrenceError as exc:
            raise ValueError(str(exc))
        if rule is None:
            raise ValueError("Item %s has no repeat: value." % args.item_id)
        if not start_text:
            for key in ("due", "do", "from"):
                values = source_item.details.get(key)
                if values:
                    start_text = str(values[0])
                    break
    elif args.rule:
        try:
            rule = parse_rule(args.rule)
        except RecurrenceError as exc:
            raise ValueError(str(exc))
    else:
        raise ValueError(
            "Pass a rule, or --path FILE --id ID to expand an item's repeat:."
        )

    start = local_now_naive().replace(second=0, microsecond=0)
    if start_text:
        parsed = parse_date_or_datetime(
            _resolve_relative_date(start_text), is_end=False
        )
        if parsed is None:
            raise ValueError("Invalid --from %r." % start_text)
        start = parsed

    after = _rrule_boundary(getattr(args, "after", None), is_end=False)
    before = _rrule_boundary(getattr(args, "before", None), is_end=True)
    limit = args.count if args.count and args.count > 0 else 10

    try:
        occurrences = expand(rule, start, after=after, before=before, limit=limit)
        description = describe(rule)
    except RecurrenceError as exc:
        raise ValueError(str(exc))

    if args.format == "json":
        payload = OrderedDict(
            [
                ("rule", rule["label"]),
                ("description", description),
                ("frequency", rule["name"]),
                ("interval", rule["interval"]),
                ("count", rule["count"]),
                ("until", rule["until"].isoformat() if rule["until"] else None),
                # Two rules differing only in WKST produce different dates, so
                # the week start has to be visible when comparing output.
                ("week_start", WEEKDAY_NAMES[rule["wkst"]]),
                ("unsupported", list(rule["unsupported"])),
                ("start", start.isoformat()),
                ("occurrences", [moment.isoformat() for moment in occurrences]),
            ]
        )
        write_text(None, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
        return 0

    if args.format == "life":
        title = args.title or (source_item.title if source_item else "Occurrence")
        lines = []
        for moment in occurrences:
            item = Item(
                "[ ]",
                args.kind,
                title,
                OrderedDict([("due", [_rrule_stamp(moment)])]),
                0,
            )
            lines.append(item_to_line(item))
        write_text(None, "\n".join(lines) + ("\n" if lines else ""))
        return 0

    sys.stdout.write("%s\n" % description)
    if rule["unsupported"]:
        sys.stderr.write(
            "Ignoring unsupported RRULE part(s): %s\n" % ", ".join(rule["unsupported"])
        )
    if not occurrences:
        sys.stdout.write("No occurrences in range.\n")
        return 0
    for index, moment in enumerate(occurrences, 1):
        sys.stdout.write(
            "%3d  %s  %s\n" % (index, _rrule_stamp(moment), moment.strftime("%a"))
        )
    return 0


def _rrule_stamp(moment):
    if moment.hour or moment.minute:
        return moment.strftime("%Y-%m-%dT%H:%M")
    return moment.date().isoformat()


def _rrule_boundary(value, is_end):
    if not value:
        return None
    parsed = parse_date_or_datetime(_resolve_relative_date(value), is_end=is_end)
    if parsed is None:
        raise ValueError("Invalid date %r." % value)
    return parsed


def command_state(args):
    """Record a presence status, closing the previously open one."""
    from .presence import COMMON_STATES, format_timestamp, status_transition

    config = _config(args)
    path = _state_write_path(args, config)

    if not getattr(args, "end", False) and not args.state:
        raise ValueError(
            "Pass a state such as: %s ... or use --end to close the current status."
            % ", ".join(COMMON_STATES[:4])
        )

    moment = None
    if getattr(args, "at", None):
        parsed = parse_date_or_datetime(args.at, is_end=False)
        if parsed is None:
            raise ValueError("Invalid --at %r. Use YYYY-MM-DDTHH:MM." % args.at)
        moment = parsed

    details = OrderedDict()
    for key in ("note", "project", "service", "visibility"):
        value = getattr(args, key, None)
        if value:
            details[key] = [value]

    from .mutation import read_text_snapshot

    snapshot = read_text_snapshot(path, allow_missing=True)
    result = status_transition(
        snapshot.text,
        state=args.state,
        title=getattr(args, "title", None),
        person=getattr(args, "person", None) or "self",
        moment=moment,
        details=details,
        id_key=id_key_from_config(config),
        close_only=bool(getattr(args, "end", False)),
        force=bool(getattr(args, "force", False)),
    )
    closed, opened = result.closed, result.opened

    if result.unchanged:
        sys.stdout.write(
            "Already %s. Nothing written; use --force to start a new record.\n"
            % result.unchanged
        )
        return 0

    if getattr(args, "dry_run", False):
        for line in closed:
            sys.stdout.write("[dry-run] Would close: %s\n" % line)
        if opened:
            sys.stdout.write("[dry-run] Would open: %s\n" % opened)
        if not closed and not opened:
            sys.stdout.write("[dry-run] No open status to close.\n")
        return 0

    _ensure_writable_path(path, config, "state")
    _pre_write_backup(path, config, "state")
    from .presence import status_transition_file

    written = status_transition_file(
        path,
        expected_hash=snapshot.content_hash,
        operation="state.transition",
        state=args.state,
        title=getattr(args, "title", None),
        person=getattr(args, "person", None) or "self",
        moment=moment,
        details=details,
        id_key=id_key_from_config(config),
        close_only=bool(getattr(args, "end", False)),
        force=bool(getattr(args, "force", False)),
    )
    closed, opened = written.transition.closed, written.transition.opened

    for line in closed:
        sys.stdout.write("Closed: %s\n" % line)
    if opened:
        sys.stdout.write("Opened: %s\n" % opened)
    elif not closed:
        sys.stdout.write("No open status to close at %s.\n" % format_timestamp(moment))
    return 0


def command_start(args):
    """Start task, optional timer, and presence as one recoverable operation."""
    from .work_session import start_work_transaction

    config = _config(args)
    path = args.path
    if not path or path == "-":
        raise ValueError("start requires a file path, not stdin.")
    id_key = id_key_from_config(config)
    text = read_text(path)
    items, _ = parse_text(text, id_key=id_key, check_ids=False, check_references=False)
    target, aborted = _resolve_target_item(items, id_key, args, prompt_verb="Start:")
    if aborted:
        return 0
    item_id = (target.details.get(id_key) or [""])[0]
    if not item_id:
        raise ValueError(
            "Item %r has no %s:. Run `lifetxt ids --assign` first."
            % (target.title, id_key)
        )
    if getattr(args, "dry_run", False):
        sys.stdout.write(
            "[dry-run] Would start work on %s as one transaction.\n" % item_id
        )
        return 0
    result = start_work_transaction(
        path,
        item_id,
        state=args.state,
        use_timer=not getattr(args, "no_timer", False),
        use_presence=not getattr(args, "no_presence", False),
        config=config,
        expected_item_revision=getattr(args, "item_revision", None),
        expected_timer_revision=getattr(args, "timer_revision", None),
        require_revisions=bool(getattr(args, "require_revisions", False)),
    )
    sys.stdout.write(
        "Started: %s (%s) transaction:%s\n"
        % (item_id, target.title, result.get("transaction_id"))
    )
    return 0


def command_stop(args):
    """Stop timer, update task, and close presence in one transaction."""
    from .work_session import stop_work_transaction

    config = _config(args)
    if getattr(args, "dry_run", False):
        sys.stdout.write(
            "[dry-run] Would stop the active work session as one transaction.\n"
        )
        return 0
    result = stop_work_transaction(
        path=getattr(args, "path", None),
        done=bool(getattr(args, "done", False)),
        close_presence=not getattr(args, "no_presence", False),
        config=config,
        expected_item_revision=getattr(args, "item_revision", None),
        expected_timer_revision=getattr(args, "timer_revision", None),
        require_revisions=bool(getattr(args, "require_revisions", False)),
    )
    sys.stdout.write(
        "Stopped: %s +%s total %s transaction:%s\n"
        % (
            result["id"],
            result["elapsed_added"],
            result["elapsed_total"],
            result.get("transaction_id"),
        )
    )
    return 0


@contextlib.contextmanager
def _captured_stdout():
    """Swallow a helper command's stdout so the caller controls the output."""
    buffer = io.StringIO()
    original = sys.stdout
    sys.stdout = buffer
    try:
        yield buffer
    finally:
        sys.stdout = original


def command_done(args):
    config = _config(args)
    path = args.path
    if not path or path == "-":
        raise ValueError("done command requires a file path, not stdin.")
    text = read_text(path)
    id_key = id_key_from_config(config)
    items, _ = parse_text(text, id_key=id_key, check_ids=False, check_references=False)

    target, aborted = _resolve_target_item(
        items, id_key, args, prompt_verb="Mark done:"
    )
    if aborted:
        return 0

    date_iso, completion_date = _completion_stamp(args, config)

    if target.kind == "H":
        # Habit logs stay date-only: the log is one entry per calendar day, and
        # a time would break same-day duplicate detection.
        return _command_done_habit(
            path, text, target, completion_date.isoformat(), config, args
        )

    if target.status == "[x]":
        sys.stdout.write("Already done: %s\n" % target.title)
        return 0

    update_args = _build_mark_done_args(target, date_iso)
    updated_text, updated_line, diagnostics = update_text(text, update_args)
    if _has_error(diagnostics):
        _print_diagnostics(diagnostics)
        return 1

    dry_run = getattr(args, "dry_run", False)
    if dry_run:
        sys.stdout.write("[dry-run] Would mark done: %s\n" % updated_line)
        return 0

    _ensure_writable_path(path, config, "done")
    _pre_write_backup(path, config, "done")
    atomic_write_text(path, updated_text)
    sys.stdout.write("Done: %s\n" % updated_line)
    return 0


def _build_mark_done_args(target, date_iso):
    """Build update_text() args that mark an item [x] with done:DATE."""
    update_args = types.SimpleNamespace(
        line=target.line,
        match_id=None,
        status="[x]",
        kind=None,
        title=None,
        done=[date_iso],
        detail=None,
        add_detail=None,
        remove_detail=None,
    )
    for flag in DETAIL_FLAGS:
        dest = "from_" if flag == "from" else flag
        if not hasattr(update_args, dest):
            setattr(update_args, dest, None)
    return update_args


def _command_done_habit(path, text, target, date_iso, config, args):
    """Append a completion date to a habit item's done: log without changing status.

    Habit definitions stay on one line and open (status unchanged); streaks are
    computed from the accumulated done: values, matching item_completion_dates().
    """
    existing_dates = target.details.get("done", [])
    force = getattr(args, "force", False)
    if date_iso in existing_dates and not force:
        raise ValueError(
            "Habit already has done:%s. Use --force to log a duplicate same-day completion."
            % date_iso
        )

    update_args = types.SimpleNamespace(
        line=target.line,
        match_id=None,
        status=None,
        kind=None,
        title=None,
        add_detail=["done:%s" % date_iso],
        detail=None,
        remove_detail=None,
    )
    for flag in DETAIL_FLAGS:
        dest = "from_" if flag == "from" else flag
        if not hasattr(update_args, dest):
            setattr(update_args, dest, None)

    updated_text, updated_line, diagnostics = update_text(text, update_args)
    if _has_error(diagnostics):
        _print_diagnostics(diagnostics)
        return 1

    from .stats import streak_days

    completion_date = _parse_date_only(date_iso)
    dates = {_parse_date_only(v) for v in existing_dates}
    dates.discard(None)
    dates.add(completion_date)
    streak = streak_days(dates, completion_date)

    dry_run = getattr(args, "dry_run", False)
    if dry_run:
        sys.stdout.write(
            "[dry-run] Would log habit completion: %s (streak: %d day(s))\n"
            % (updated_line, streak)
        )
        return 0

    _ensure_writable_path(path, config, "done")
    _pre_write_backup(path, config, "done")
    atomic_write_text(path, updated_text)
    sys.stdout.write("Logged: %s (streak: %d day(s))\n" % (updated_line, streak))
    return 0


def command_complete(args):
    """Complete a repeat-enabled task instance, materializing the next occurrence.

    Non-repeating items fall back to the same behavior as `done`. Repeat-enabled
    items mark the current instance [x] and append a fresh [ ] instance with the
    next due date, Taskwarrior-style, so file growth is handled by `archive`.
    """
    config = _config(args)
    path = args.path
    if not path or path == "-":
        raise ValueError("complete command requires a file path, not stdin.")
    text = read_text(path)
    id_key = id_key_from_config(config)
    items, _ = parse_text(text, id_key=id_key, check_ids=False, check_references=False)

    target, aborted = _resolve_target_item(items, id_key, args, prompt_verb="Complete:")
    if aborted:
        return 0

    if target.status == "[x]":
        sys.stdout.write("Already done: %s\n" % target.title)
        return 0

    date_arg = getattr(args, "date", None)
    if date_arg:
        completion_dt = parse_date_or_datetime(date_arg, is_end=False)
        if completion_dt is None:
            raise ValueError("Invalid --date %r. Use YYYY-MM-DD." % date_arg)
        completion_date = completion_dt.date()
    else:
        completion_date = timezone_today()
    date_iso = completion_date.isoformat()

    repeat_value = _first_detail_value(target, "repeat")
    dry_run = getattr(args, "dry_run", False)

    if not repeat_value:
        # No repeat rule: complete behaves exactly like done for tasks.
        update_args = _build_mark_done_args(target, date_iso)
        updated_text, updated_line, diagnostics = update_text(text, update_args)
        if _has_error(diagnostics):
            _print_diagnostics(diagnostics)
            return 1
        if dry_run:
            sys.stdout.write("[dry-run] Would mark done: %s\n" % updated_line)
            return 0
        _ensure_writable_path(path, config, "complete")
        _pre_write_backup(path, config, "complete")
        atomic_write_text(path, updated_text)
        sys.stdout.write("Done: %s\n" % updated_line)
        return 0

    next_anchor_key, next_dt, rule = _compute_next_occurrence(
        target, config, completion_date
    )

    update_args = _build_mark_done_args(target, date_iso)
    updated_text, updated_line, diagnostics = update_text(text, update_args)
    if _has_error(diagnostics):
        _print_diagnostics(diagnostics)
        return 1

    if next_dt is None:
        # Series ended (until reached): mark done, do not materialize a new instance.
        if dry_run:
            sys.stdout.write(
                "[dry-run] Would mark done (series complete, no new occurrence): %s\n"
                % updated_line
            )
            return 0
        _ensure_writable_path(path, config, "complete")
        _pre_write_backup(path, config, "complete")
        atomic_write_text(path, updated_text)
        sys.stdout.write("Completed (series ended): %s\n" % updated_line)
        return 0

    new_details = OrderedDict()
    for key, values in target.details.items():
        if key in (id_key, "done"):
            continue
        new_details[key] = list(values)

    if next_dt.time() == datetime.time():
        next_value = next_dt.date().isoformat()
    else:
        next_value = format_datetime(next_dt)
    new_details[next_anchor_key] = [next_value]

    new_item = Item("[ ]", target.kind, target.title, new_details)
    existing_ids = collect_item_ids(items, key=id_key)
    ensure_item_id(
        new_item,
        existing_ids=existing_ids,
        key=id_key,
        prefix=id_prefix_for_item(new_item, config),
    )
    new_line = item_to_assisted_line(new_item)

    parsed_new, new_diagnostics = parse_text(new_line + "\n")
    if not parsed_new or _has_error(new_diagnostics):
        _print_diagnostics(new_diagnostics)
        raise ValueError(
            "Generated next occurrence did not produce a valid item: %s" % new_line
        )

    if dry_run:
        sys.stdout.write("[dry-run] Would complete: %s\n" % updated_line)
        sys.stdout.write("[dry-run] Would add next occurrence: %s\n" % new_line)
        return 0

    end_line = getattr(target, "end_line", target.line) or target.line
    text_lines = updated_text.splitlines(True)
    ending = "\n"
    if text_lines and not text_lines[-1].endswith(("\n", "\r")):
        text_lines[-1] += ending
    insert_at = min(end_line, len(text_lines))
    text_lines.insert(insert_at, new_line + ending)
    final_text = "".join(text_lines)

    _ensure_writable_path(path, config, "complete")
    _pre_write_backup(path, config, "complete")
    atomic_write_text(path, final_text)
    sys.stdout.write("Completed: %s\n" % updated_line)
    sys.stdout.write("Next: %s\n" % new_line)
    return 0


def resolve_repeat_base(item, config):
    """Resolve the effective repeat_base ('due' or 'done') for an item.

    Item-level repeat_base: overrides the config defaults.repeat_base setting,
    which defaults to 'due' when unset.
    """
    repeat_base = _first_detail_value(item, "repeat_base")
    if not repeat_base:
        defaults = config_section(config, "defaults")
        repeat_base = defaults.get("repeat_base") or "due"
    return str(repeat_base).strip().lower()


def _compute_next_occurrence(item, config, completion_date):
    """Return (anchor_key, next_datetime_or_None, rule) for repeat materialization.

    Thin wrapper around agenda.next_repeat_occurrence() that resolves
    repeat_base from the item or config first, so CLI, Web API, and MCP
    share one calculation.
    """
    repeat_base = resolve_repeat_base(item, config)
    return next_repeat_occurrence(item, repeat_base, completion_date)


def command_batch(args):
    config = _config(args)
    paths = _normalize_paths(getattr(args, "paths", None) or [], config)
    selectors = []
    selectors.extend(("id", value) for value in (getattr(args, "ids", None) or []))
    selectors.extend(("text", value) for value in (getattr(args, "texts", None) or []))
    action = getattr(args, "action", "")
    if action in ("done", "assign") and not selectors:
        raise ValueError("batch requires at least one --id or --text selector.")
    if action == "assign" and not getattr(args, "to", None):
        raise ValueError("batch assign requires --to.")
    if action in ("tag-rename", "tag-merge") and (
        not getattr(args, "old", None) or not getattr(args, "new", None)
    ):
        raise ValueError("batch %s requires --old and --new." % action)
    if action == "migrate" and not getattr(args, "migrations", None):
        raise ValueError("batch migrate requires at least one --migration.")
    if not paths:
        raise ValueError("batch requires at least one file path.")

    status_code = 0
    applied = 0
    failed = 0
    for path in paths:
        if path == "-":
            raise ValueError("batch does not support stdin.")
        try:
            if action in ("done", "assign"):
                for selector_kind, selector_value in selectors:
                    if action == "done":
                        child_args = types.SimpleNamespace(
                            path=path,
                            id=selector_value if selector_kind == "id" else None,
                            line=None,
                            text=selector_value if selector_kind == "text" else None,
                            dry_run=getattr(args, "dry_run", False),
                            config_data=config,
                        )
                        result = command_done(child_args)
                        status_code = status_code or result
                        applied += 1
                        continue
                    if getattr(args, "dry_run", False):
                        sys.stdout.write(
                            "[dry-run] Would assign %s=%s to %s in %s.\n"
                            % (selector_kind, selector_value, args.to, path)
                        )
                        applied += 1
                        continue
                    child_args = types.SimpleNamespace(
                        path=path,
                        id=selector_value if selector_kind == "id" else None,
                        text=selector_value if selector_kind == "text" else None,
                        to=args.to,
                        notify=False,
                        from_user=None,
                        config_data=config,
                    )
                    result = command_assign(child_args)
                    status_code = status_code or result
                    applied += 1
                continue
            if action == "tag-rename":
                child_args = types.SimpleNamespace(
                    path=path,
                    old=args.old,
                    new=args.new,
                    dry_run=getattr(args, "dry_run", False),
                    config_data=config,
                )
                result = command_tag_rename(child_args)
                status_code = status_code or result
                applied += 1
                continue
            if action == "tag-merge":
                child_args = types.SimpleNamespace(
                    path=path,
                    old=args.old,
                    new=args.new,
                    dry_run=getattr(args, "dry_run", False),
                    config=getattr(args, "config", None),
                    config_data=config,
                )
                result = command_tag_merge(child_args)
                status_code = status_code or result
                applied += 1
                continue
            if action == "migrate":
                child_args = types.SimpleNamespace(
                    path=path,
                    migrations=args.migrations,
                    dry_run=getattr(args, "dry_run", False),
                    backup=getattr(args, "backup", False),
                    config_data=config,
                )
                result = command_migrate(child_args)
                status_code = status_code or result
                applied += 1
                continue
            raise ValueError("Unsupported batch action: %s" % action)
        except Exception as exc:
            failed += 1
            status_code = 1
            sys.stderr.write(
                "ERROR: batch %s failed for %s: %s\n" % (action, path, exc)
            )
    if getattr(args, "dry_run", False):
        sys.stdout.write(
            "[dry-run] Planned %d batch operation(s), %d failed.\n" % (applied, failed)
        )
    else:
        sys.stdout.write(
            "Applied %d batch operation(s), %d failed.\n" % (applied, failed)
        )
    return status_code


def command_summary(args):
    config = _config(args)
    compare_path = getattr(args, "compare", None)
    if compare_path:
        # Side-by-side comparison mode
        primary_paths = args.paths if args.paths else ["-"]
        _summary_compare(primary_paths, compare_path, _config(args))
        return 0
    paths = args.paths if args.paths else ["-"]
    id_key = id_key_from_config(config)
    all_results = []

    for path in paths:
        text = read_text(path)
        items, _ = parse_text(
            text, id_key=id_key, check_ids=False, check_references=False
        )

        line_count = len(text.splitlines())
        type_counts = {}
        status_counts = {}
        ids_present = 0
        ids_missing = 0
        dates = []

        for item in items:
            type_counts[item.kind] = type_counts.get(item.kind, 0) + 1
            status_counts[item.status] = status_counts.get(item.status, 0) + 1
            if item.details.get(id_key):
                ids_present += 1
            else:
                ids_missing += 1
            for date_key in ("done", "updated", "created", "due", "do", "on"):
                for val in item.details.get(date_key, []):
                    s = str(val)
                    if len(s) >= 10 and s[:10].count("-") == 2:
                        dates.append(s[:10])

        date_min = min(dates) if dates else None
        date_max = max(dates) if dates else None

        mtime = None
        if path != "-" and os.path.exists(path):
            stat = os.stat(path)
            mtime = datetime.datetime.fromtimestamp(stat.st_mtime).strftime(
                "%Y-%m-%dT%H:%M"
            )

        all_results.append(
            OrderedDict(
                [
                    ("source", path),
                    ("line_count", line_count),
                    ("item_count", len(items)),
                    ("type_counts", type_counts),
                    ("status_counts", status_counts),
                    ("id_key", id_key),
                    ("ids_present", ids_present),
                    ("ids_missing", ids_missing),
                    ("date_min", date_min),
                    ("date_max", date_max),
                    ("modified", mtime),
                ]
            )
        )

    if args.format == "json":
        payload = all_results[0] if len(all_results) == 1 else all_results
        write_text(
            None,
            json.dumps(
                payload,
                ensure_ascii=False,
                indent=2 if args.pretty else None,
                separators=None if args.pretty else (",", ":"),
            )
            + "\n",
        )
    else:
        try:
            import shutil as _shutil

            term_width = _shutil.get_terminal_size((80, 24)).columns
        except Exception:
            term_width = 80
        compact = term_width < 60
        for result in all_results:
            if compact:
                type_str = " ".join(
                    "%s:%d" % (k, v) for k, v in sorted(result["type_counts"].items())
                )
                status_str = " ".join(
                    "%s:%d" % (k.strip("[]"), v)
                    for k, v in sorted(result["status_counts"].items())
                )
                lines = [
                    "%s  %d items  %s  [%s]"
                    % (result["source"], result["item_count"], type_str, status_str)
                ]
            else:
                lines = ["Summary: %s" % result["source"]]
                lines.append("  Lines:    %d" % result["line_count"])
                lines.append("  Items:    %d" % result["item_count"])
                if result["type_counts"]:
                    lines.append(
                        "  Types:    "
                        + "  ".join(
                            "%s:%d" % (k, v)
                            for k, v in sorted(result["type_counts"].items())
                        )
                    )
                if result["status_counts"]:
                    lines.append(
                        "  Statuses: "
                        + "  ".join(
                            "%s:%d" % (k.strip("[]"), v)
                            for k, v in sorted(result["status_counts"].items())
                        )
                    )
                lines.append(
                    "  IDs (%s):  %d present, %d missing"
                    % (
                        result["id_key"],
                        result["ids_present"],
                        result["ids_missing"],
                    )
                )
                if result["date_min"] or result["date_max"]:
                    lines.append(
                        "  Dates:    %s .. %s"
                        % (
                            result["date_min"] or "?",
                            result["date_max"] or "?",
                        )
                    )
                if result["modified"]:
                    lines.append("  Modified: %s" % result["modified"])
            write_text(None, "\n".join(lines) + "\n")
    return 0


def command_undo(args):
    config = _config(args)
    path = args.path
    if not path or path == "-":
        raise ValueError("undo requires a file path.")
    basename = os.path.basename(path)
    undo_dir = os.path.join(_undo_cache_dir(config), basename)

    try:
        entries = sorted(e for e in os.listdir(undo_dir) if e.endswith(".txt"))
    except OSError:
        entries = []

    if not entries:
        sys.stdout.write("No undo history for: %s\n" % path)
        return 0

    if args.list:
        sys.stdout.write(
            "Undo history for %s (%d snapshot(s)):\n" % (path, len(entries))
        )
        for i, name in enumerate(reversed(entries)):
            parts = name.rsplit(".", 2)
            if len(parts) == 3:
                ts_raw, op, _ = parts
                try:
                    dt = datetime.datetime.strptime(ts_raw, "%Y%m%d_%H%M%S")
                    ts_str = dt.strftime("%Y-%m-%d %H:%M:%S")
                except ValueError:
                    ts_str = ts_raw
                    op = "?"
                sys.stdout.write("  [%d] %s  op=%s\n" % (i + 1, ts_str, op))
            else:
                sys.stdout.write("  [%d] %s\n" % (i + 1, name))
        return 0

    snapshot = entries[-1]
    snapshot_path = os.path.join(undo_dir, snapshot)
    try:
        content = read_text(snapshot_path)
    except OSError as exc:
        raise ValueError("Failed to read undo snapshot: %s" % exc)

    from .write_operations import restore_text

    restore_text(
        path,
        content,
        expected_revision=getattr(args, "revision", None),
        operation="undo.restore",
    )
    try:
        os.unlink(snapshot_path)
    except OSError:
        pass

    sys.stdout.write("Restored: %s (from %s)\n" % (path, snapshot))
    return 0


def command_init(args):
    life_file = getattr(args, "file", None) or "life.txt"
    config_file = getattr(args, "config_output", None) or ".lifetxt.json"

    life_exists = os.path.exists(life_file)
    config_exists = os.path.exists(config_file)

    yes = getattr(args, "yes", False) or args.force

    if (life_exists or config_exists) and not yes:
        existing = [p for p in (life_file, config_file) if os.path.exists(p)]
        sys.stdout.write("File(s) already exist: %s\n" % ", ".join(existing))
        sys.stdout.write("Overwrite? [y/N] ")
        sys.stdout.flush()
        answer = sys.stdin.readline().strip().lower()
        if answer not in ("y", "yes"):
            sys.stdout.write("Aborted.\n")
            return 0

    name = getattr(args, "name", None)
    if not name and not yes:
        sys.stdout.write("Your name (for S presence records) [self]: ")
        sys.stdout.flush()
        name = sys.stdin.readline().strip() or "self"
    if not name:
        name = "self"

    timezone_val = getattr(args, "timezone", None)
    if not timezone_val and not yes:
        sys.stdout.write("Timezone (e.g. Asia/Tokyo, UTC) [UTC]: ")
        sys.stdout.flush()
        timezone_val = sys.stdin.readline().strip() or "UTC"
    if not timezone_val:
        timezone_val = "UTC"

    project = getattr(args, "project", None)
    if project is None and not yes:
        sys.stdout.write("Default project name (leave blank to skip): ")
        sys.stdout.flush()
        project = sys.stdin.readline().strip()

    today = timezone_today().isoformat()

    life_lines = []
    life_lines.append("#! self: %s" % name)
    life_lines.append("#! timezone: %s" % timezone_val)
    if project:
        life_lines.append("#! project: %s" % project)
    life_lines.append("")
    project_detail = (" project:%s" % project) if project else ""
    life_lines.append("[ ] T First_Task%s due:%s" % (project_detail, today))
    life_text = "\n".join(life_lines) + "\n"

    defaults = OrderedDict()
    defaults["person"] = name
    defaults["timezone"] = timezone_val
    if project:
        defaults["project"] = project
    config_data = OrderedDict([("defaults", defaults)])
    config_text = json.dumps(config_data, ensure_ascii=False, indent=2) + "\n"

    write_text(life_file, life_text)
    sys.stdout.write("Wrote %s\n" % life_file)
    write_text(config_file, config_text)
    sys.stdout.write("Wrote %s\n" % config_file)
    sys.stdout.write("Next: python -m lifetxt check %s\n" % life_file)
    return 0


#: Optional dependencies not covered by a pyproject.toml extras group; the
#: plain-`pip install PKG` hint is the accurate one for these.
_STANDALONE_OPTIONAL_DEPENDENCY_HINT = "pip install %s"
#: Optional dependencies covered by an extras group -- installing the group
#: is the documented, correct way to get them, not `pip install PKG` alone.
_EXTRAS_GROUP_BY_DEPENDENCY = {
    "fastapi": "web",
    "uvicorn": "web",
    "textual": "tui",
    "watchdog": "tui",
}


#: Repository queried by `lifetxt update-check` and `lifetxt update`.
_UPDATE_CHECK_REPO = "Eruhitsuji/lifetxt"


def _parse_simple_version(text):
    """Parse a dotted numeric version into a comparable tuple.

    Accepts an optional leading "v" (GitHub tag convention) and ignores any
    pre-release or build-metadata suffix after the dotted numeric prefix
    (e.g. "v1.2.3-rc1" -> (1, 2, 3)). This is an informational "is this
    newer" comparison, not a strict PEP 440 or semver parser. Returns None
    when no leading dotted-numeric prefix can be found.
    """
    import re

    text = str(text or "").strip()
    if text[:1] in ("v", "V"):
        text = text[1:]
    match = re.match(r"^(\d+(?:\.\d+)*)", text)
    if not match:
        return None
    return tuple(int(part) for part in match.group(1).split("."))


def _github_api_get(url, timeout):
    request = Request(
        url,
        headers={
            "User-Agent": "lifetxt-update-check",
            "Accept": "application/vnd.github+json",
        },
    )
    return urlopen(request, timeout=timeout)


def _github_latest_release_or_tag(repo, timeout=10):
    """Find the latest published release, falling back to the newest tag.

    Returns (version_text, kind, url) where kind is "release" or "tag", or
    (None, None, None) when the repository has no releases or tags at all.
    Raises ValueError on a network or API failure so the caller fails loudly
    rather than silently reporting "up to date".
    """
    try:
        with _github_api_get(
            "https://api.github.com/repos/%s/releases/latest" % repo, timeout
        ) as response:
            payload = json.loads(response.read().decode("utf-8"))
        version = payload.get("tag_name") or payload.get("name")
        return version, "release", payload.get("html_url", "")
    except HTTPError as exc:
        if exc.code != 404:
            raise ValueError("GitHub release lookup failed: HTTP %s." % exc.code)
    except URLError as exc:
        raise ValueError("GitHub release lookup failed: %s." % exc.reason)

    # No published release. Fall back to the most recently created tag.
    try:
        with _github_api_get(
            "https://api.github.com/repos/%s/tags" % repo, timeout
        ) as response:
            tags = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raise ValueError("GitHub tag lookup failed: HTTP %s." % exc.code)
    except URLError as exc:
        raise ValueError("GitHub tag lookup failed: %s." % exc.reason)
    if not tags:
        return None, None, None
    name = tags[0].get("name")
    return name, "tag", "https://github.com/%s/releases/tag/%s" % (repo, name)


def _resolve_update_check_repo(args, config):
    """Resolve which GitHub repository to check: --repo, then config, then the built-in default.

    A fork should never be silently pointed at the upstream project's
    releases: `_UPDATE_CHECK_REPO` is only the last-resort fallback, not the
    only option. `--repo` (a one-off override) takes precedence over
    `update.repository` (a persistent, per-install default).
    """
    import re

    explicit = getattr(args, "repo", None)
    configured = config_section(config, "update").get("repository")
    repo = str(explicit or configured or _UPDATE_CHECK_REPO).strip()
    if not re.match(r"^[^/\s]+/[^/\s]+$", repo):
        raise ValueError(
            "Invalid repository %r; expected OWNER/NAME (e.g. Eruhitsuji/lifetxt)."
            % repo
        )
    return repo


def command_update_check(args):
    """Report whether a newer lifetxt release or tag exists on GitHub.

    Read-only: makes one or two GET requests to the public GitHub API and
    never writes anything or installs anything. lifetxt has no PyPI
    distribution, so "the latest release" means the latest GitHub Release,
    falling back to the latest tag when no Release has been published.
    """
    from . import __version__

    current = _parse_simple_version(__version__)
    if current is None:
        raise ValueError(
            "Cannot parse the running lifetxt version %r as a dotted version."
            % __version__
        )

    repo = _resolve_update_check_repo(args, _config(args))
    timeout = getattr(args, "timeout", 10)
    latest_text, kind, url = _github_latest_release_or_tag(repo, timeout=timeout)

    result = OrderedDict(
        [
            ("current_version", __version__),
            ("repository", repo),
            ("latest_version", latest_text),
            ("kind", kind),
            ("url", url or None),
        ]
    )

    if latest_text is None:
        result["status"] = "no_release_found"
        message = (
            "No published releases or tags found for %s; nothing to compare "
            "against." % repo
        )
    else:
        latest = _parse_simple_version(latest_text)
        if latest is None:
            result["status"] = "unparseable"
            message = (
                "Found %s %s but could not parse it as a version. Compare "
                "manually at %s" % (kind, latest_text, url)
            )
        elif latest > current:
            result["status"] = "update_available"
            message = "Update available: running %s, latest %s is %s. %s" % (
                __version__,
                kind,
                latest_text,
                url,
            )
        elif latest < current:
            result["status"] = "ahead_of_latest"
            message = "Running %s, ahead of the latest published %s %s." % (
                __version__,
                kind,
                latest_text,
            )
        else:
            result["status"] = "up_to_date"
            message = "Up to date: %s." % __version__

    if getattr(args, "format", "text") == "json":
        write_text(None, json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    else:
        write_text(None, message + "\n")
    return 0


#: Argument-injection defense: a git ref/remote beginning with "-" could be
#: misread as a command-line option by git itself (e.g. a tag literally
#: named "--upload-pack=..."). Neither a real branch nor a real remote name
#: legitimately starts with "-", so refusing this is not a functional
#: restriction.
def _reject_option_like_git_arg(value, label):
    if str(value or "").startswith("-"):
        raise ValueError(
            "Refusing %s %r: it looks like a command-line option, not a "
            "name." % (label, value)
        )
    return value


def _run_git_for_update(args_list, cwd, timeout):
    import subprocess

    try:
        return subprocess.run(
            ["git"] + list(args_list),
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            # Decode explicitly as UTF-8 rather than the platform locale
            # codec (e.g. cp932 on ja-JP Windows): git's own output is not
            # guaranteed to be representable in that codec, and letting the
            # default decoder raise mid-read would crash this command on a
            # path or ref it never gets to evaluate. errors="replace" keeps
            # this diagnostic-only -- the exact bytes are never parsed for
            # control flow, only shown to the user or embedded in an error.
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
    except FileNotFoundError:
        raise ValueError("git executable not found; `lifetxt update` requires git.")
    except subprocess.TimeoutExpired:
        raise ValueError("git %s timed out after %ss." % (" ".join(args_list), timeout))
    except OSError as exc:
        raise ValueError("Failed to run git %s: %s" % (" ".join(args_list), exc))


def _lifetxt_install_root():
    import lifetxt

    return os.path.dirname(os.path.dirname(os.path.abspath(lifetxt.__file__)))


#: Maximum commits listed in update's dry-run preview. Bounded so a large
#: gap (e.g. --ref pointing far ahead) still prints a short, readable
#: summary rather than flooding the terminal.
_UPDATE_LOG_PREVIEW_LIMIT = 20


def _git_commit_summary(
    repo_root, current, target, timeout, limit=_UPDATE_LOG_PREVIEW_LIMIT
):
    """List commits between current and target, newest first, capped at limit.

    Returns (commits, total_count). commits is a list of "hash subject"
    strings for at most limit commits; total_count is the true number of
    commits in the range (from git rev-list --count), so the caller can
    report "and N more" when the list was truncated. Returns ([], 0) on any
    git failure rather than raising -- this is a preview, not a safety
    check, and must never block update on a log lookup that failed.
    """
    range_spec = "%s..%s" % (current, target)
    log = _run_git_for_update(
        ["log", "--oneline", "--max-count=%d" % limit, range_spec],
        cwd=repo_root,
        timeout=timeout,
    )
    if log.returncode != 0:
        return [], 0
    commits = [line for line in log.stdout.splitlines() if line.strip()]
    count = _run_git_for_update(
        ["rev-list", "--count", range_spec], cwd=repo_root, timeout=timeout
    )
    try:
        total = int(count.stdout.strip()) if count.returncode == 0 else len(commits)
    except ValueError:
        total = len(commits)
    return commits, total


def command_update(args):
    """Fast-forward the running lifetxt install's git checkout.

    Security/High: this is the only lifetxt command that mutates the git
    working tree the running install lives in, and the project has no PyPI
    distribution, so this is git-based rather than a package-manager update.

    Safety rails, all fail-loud (raise ValueError, never silent):
      - Refuses when the install is not inside a git working tree.
      - Refuses when the working tree has any uncommitted change (tracked or
        untracked) -- `git status --porcelain` must be empty.
      - Refuses when HEAD is detached (must be on a real branch).
      - Only ever runs `git fetch` (which touches only remote-tracking refs
        and the object database, not the working tree or current branch)
        and `git merge --ff-only` (which refuses anything that is not a
        clean fast-forward, and never rewrites history). Never resets,
        rebases, or force-pushes.
      - Defaults to a dry run: fetches and reports what would happen without
        merging. Only `--yes` performs the merge.
      - Never runs `pip install` or any other build/setup code after
        updating -- picking up dependency changes is left to the operator,
        printed as an explicit follow-up instruction instead of executed.

    The --repo/update.repository resolution (shared with `update-check`)
    only chooses which ref *name* to ask for; the actual git operations
    always go through the local `origin` (or --remote)'s already-configured,
    user-trusted URL, never a URL derived from --repo.
    """
    timeout = getattr(args, "timeout", 10)
    install_root = _lifetxt_install_root()

    toplevel = _run_git_for_update(
        ["rev-parse", "--show-toplevel"], cwd=install_root, timeout=timeout
    )
    if toplevel.returncode != 0:
        raise ValueError(
            "`lifetxt update` requires a git-based install. The running "
            "install at %s does not appear to be inside a git working "
            "tree." % install_root
        )
    repo_root = toplevel.stdout.strip()

    status = _run_git_for_update(
        ["status", "--porcelain"], cwd=repo_root, timeout=timeout
    )
    if status.returncode != 0:
        raise ValueError(
            "git status failed: %s" % (status.stderr.strip() or status.stdout.strip())
        )
    if status.stdout.strip():
        raise ValueError(
            "Refusing to update: %s has uncommitted changes. Commit, stash, "
            "or discard them first." % repo_root
        )

    branch = _run_git_for_update(
        ["symbolic-ref", "-q", "--short", "HEAD"], cwd=repo_root, timeout=timeout
    )
    if branch.returncode != 0:
        raise ValueError(
            "Refusing to update: %s is not on a branch (detached HEAD). "
            "Check out a branch first." % repo_root
        )
    branch_name = branch.stdout.strip()

    remote = _reject_option_like_git_arg(
        getattr(args, "remote", None) or "origin", "remote"
    )
    ref = getattr(args, "ref", None)
    if not ref:
        repo = _resolve_update_check_repo(args, _config(args))
        latest_text, _kind, _url = _github_latest_release_or_tag(repo, timeout=timeout)
        if latest_text is None:
            write_text(
                None,
                "No published releases or tags found for %s; nothing to "
                "update to. Pass --ref to update to a specific branch or "
                "commit.\n" % repo,
            )
            return 0
        ref = latest_text
    _reject_option_like_git_arg(ref, "ref")

    fetch = _run_git_for_update(["fetch", remote, ref], cwd=repo_root, timeout=timeout)
    if fetch.returncode != 0:
        raise ValueError(
            "git fetch %s %s failed: %s"
            % (remote, ref, fetch.stderr.strip() or fetch.stdout.strip())
        )

    current = _run_git_for_update(
        ["rev-parse", "HEAD"], cwd=repo_root, timeout=timeout
    ).stdout.strip()
    target = _run_git_for_update(
        ["rev-parse", "FETCH_HEAD"], cwd=repo_root, timeout=timeout
    ).stdout.strip()

    result = OrderedDict(
        [
            ("install_root", repo_root),
            ("branch", branch_name),
            ("remote", remote),
            ("ref", ref),
            ("current_commit", current),
            ("target_commit", target),
        ]
    )
    fmt = getattr(args, "format", "text")

    def emit(status_key, message):
        result["status"] = status_key
        if fmt == "json":
            write_text(None, json.dumps(result, ensure_ascii=False, indent=2) + "\n")
        else:
            write_text(None, message + "\n")

    if current == target:
        emit(
            "up_to_date",
            "Already up to date on %s (%s)." % (branch_name, current[:12]),
        )
        return 0

    commits, commit_count = _git_commit_summary(repo_root, current, target, timeout)
    result["commits"] = commits
    result["commit_count"] = commit_count

    def _commit_lines():
        lines = ["  %s" % line for line in commits]
        if commit_count > len(commits):
            lines.append("  ... and %d more" % (commit_count - len(commits)))
        return lines

    if not getattr(args, "yes", False):
        message_lines = [
            "Update available on %s: %s -> %s (fetched %s from %s). Dry "
            "run: no changes made. Re-run with --yes to fast-forward."
            % (branch_name, current[:12], target[:12], ref, remote)
        ]
        message_lines.extend(_commit_lines())
        emit("update_available_dry_run", "\n".join(message_lines))
        return 0

    merge = _run_git_for_update(
        ["merge", "--ff-only", "FETCH_HEAD"], cwd=repo_root, timeout=timeout
    )
    if merge.returncode != 0:
        raise ValueError(
            "git merge --ff-only failed (not a fast-forward): %s"
            % (merge.stderr.strip() or merge.stdout.strip())
        )

    message_lines = [
        "Updated %s: %s -> %s. Dependencies may have changed -- run "
        'pip install -e "." (or the extras you use) to pick them up.'
        % (branch_name, current[:12], target[:12])
    ]
    message_lines.extend(_commit_lines())
    emit("updated", "\n".join(message_lines))
    return 0


def command_doctor(args):
    import platform

    from . import __version__
    from .doctor import optional_dependency_report

    checks = []
    any_fail = [False]

    def add_check(symbol, label, message):
        checks.append((symbol, label, message))
        if symbol == "FAIL":
            any_fail[0] = True

    major, minor = sys.version_info[:2]
    if (major, minor) >= (3, 10):
        add_check("OK", "python", "Python %d.%d" % (major, minor))
    else:
        add_check("FAIL", "python", "Python %d.%d (3.10+ required)" % (major, minor))
    add_check(
        "OK",
        "system",
        "lifetxt %s, Python %s, %s %s"
        % (
            __version__,
            platform.python_version(),
            platform.system() or "unknown OS",
            platform.release() or "",
        ),
    )

    config = _config(args)

    if getattr(args, "check_update", False):
        # Off by default: plain `doctor` must never require network access.
        # A failure here is reported as WARN, never FAIL -- it says nothing
        # about the health of the local install.
        try:
            update_repo = _resolve_update_check_repo(args, config)
            latest_text, kind, _url = _github_latest_release_or_tag(
                update_repo, timeout=getattr(args, "update_timeout", 5)
            )
        except ValueError as exc:
            add_check("WARN", "update", "Could not check for updates: %s" % exc)
        else:
            if latest_text is None:
                add_check(
                    "OK",
                    "update",
                    "No published releases or tags found for %s" % update_repo,
                )
            else:
                latest = _parse_simple_version(latest_text)
                current_version = _parse_simple_version(__version__)
                if latest is None or current_version is None:
                    add_check(
                        "OK",
                        "update",
                        "Found %s %s but could not parse it as a version"
                        % (kind, latest_text),
                    )
                elif latest > current_version:
                    add_check(
                        "WARN",
                        "update",
                        "Update available: %s -> %s -- run: lifetxt update"
                        % (__version__, latest_text),
                    )
                else:
                    add_check("OK", "update", "Up to date: %s" % __version__)

    arg_paths = getattr(args, "paths", None) or []
    life_paths = _normalize_paths(arg_paths, config, stdin_when_empty=False) or [
        "life.txt"
    ]
    for path in life_paths:
        if not os.path.exists(path):
            add_check("FAIL", "life.txt", "Not found: %s -- run: lifetxt init" % path)
        elif not os.access(path, os.R_OK):
            add_check("FAIL", "life.txt", "Not readable: %s" % path)
        else:
            add_check("OK", "life.txt", "Found: %s" % path)

    config_path = getattr(args, "config", None) or ".lifetxt.json"
    if not os.path.exists(config_path):
        add_check(
            "WARN", "config", "Not found: %s -- run: lifetxt config init" % config_path
        )
    else:
        add_check("OK", "config", "Found: %s" % config_path)

    import shutil

    disk_check_dir = os.path.dirname(os.path.abspath(life_paths[0])) or os.getcwd()
    try:
        free_bytes = shutil.disk_usage(disk_check_dir).free
    except OSError as exc:
        add_check("WARN", "disk", "Could not check free space: %s" % exc)
    else:
        free_mib = free_bytes / (1024.0 * 1024.0)
        # 100 MiB is a conservative floor: transaction journals, atomic-write
        # temp files, and config backups all need real headroom to avoid a
        # mid-write failure, not just enough for the life.txt file itself.
        if free_bytes < 100 * 1024 * 1024:
            add_check(
                "WARN",
                "disk",
                "%.1f MiB free on %s (below the 100 MiB safety floor)"
                % (free_mib, disk_check_dir),
            )
        else:
            add_check("OK", "disk", "%.1f MiB free on %s" % (free_mib, disk_check_dir))

    for tool in ("fzf", "peco"):
        if shutil.which(tool):
            add_check("OK", tool, "Found in PATH")
        else:
            add_check("WARN", tool, "Not found (optional)")

    for pkg, installed in optional_dependency_report().items():
        if installed:
            add_check("OK", pkg, "Installed")
            continue
        group = _EXTRAS_GROUP_BY_DEPENDENCY.get(pkg)
        hint = (
            'pip install -e ".[%s]"' % group
            if group
            else _STANDALONE_OPTIONAL_DEPENDENCY_HINT % pkg
        )
        add_check("WARN", pkg, "Not installed (optional) -- %s" % hint)

    existing_paths = [p for p in life_paths if os.path.exists(p)]
    if existing_paths:
        items, diagnostics = _parse_life_inputs(existing_paths, config)
        errors = [d for d in diagnostics if d.severity == "error"]
        warnings_list = [d for d in diagnostics if d.severity == "warning"]
        if errors:
            add_check(
                "FAIL",
                "check",
                "%d error(s) -- run: lifetxt check %s"
                % (len(errors), existing_paths[0]),
            )
        elif warnings_list:
            add_check(
                "WARN",
                "check",
                "%d warning(s) -- run: lifetxt check %s"
                % (len(warnings_list), existing_paths[0]),
            )
        else:
            add_check("OK", "check", "%d item(s), no errors" % len(items))

        id_key = id_key_from_config(config)
        missing_count = sum(1 for item in items if not item.details.get(id_key))
        if missing_count:
            add_check(
                "WARN",
                "ids",
                "%d item(s) missing %s: -- run: lifetxt ids --assign --dry-run %s"
                % (missing_count, id_key, existing_paths[0]),
            )
        else:
            add_check("OK", "ids", "All items have %s:" % id_key)

    _fmt = getattr(args, "format", "text")
    _pretty = getattr(args, "pretty", False)
    if _fmt == "json":
        records = [
            OrderedDict([("status", s), ("check", l), ("message", m)])
            for s, l, m in checks
        ]
        write_text(
            None,
            json.dumps(
                records,
                ensure_ascii=False,
                indent=2 if _pretty else None,
                separators=None if _pretty else (",", ":"),
            )
            + "\n",
        )
    else:
        symbols = {"OK": "[OK]", "WARN": "[!!]", "FAIL": "[XX]"}
        for symbol, label, message in checks:
            write_text(
                None, "%s %-12s %s\n" % (symbols.get(symbol, symbol), label, message)
            )

    return 1 if any_fail[0] else 0


def command_assign(args):
    config = _config(args)
    path = args.path
    if not path or path == "-":
        raise ValueError("assign command requires a file path, not stdin.")
    text = read_text(path)
    id_key = id_key_from_config(config)
    items, _ = parse_text(text, id_key=id_key, check_ids=False, check_references=False)

    item_id = getattr(args, "id", None)
    item_text = getattr(args, "text", None)

    if item_id:
        matches = [
            item
            for item in items
            if item_id in [str(v) for v in item.details.get(id_key, [])]
        ]
        if not matches:
            raise ValueError("No item with %s:%s." % (id_key, item_id))
        if len(matches) > 1:
            raise ValueError("Multiple items with %s:%s." % (id_key, item_id))
        target = matches[0]
    elif item_text:
        query = item_text.lower()
        matches = [item for item in items if query in item.title.lower()]
        if not matches:
            raise ValueError("No item matching %r." % item_text)
        if len(matches) > 1:
            sys.stdout.write("Multiple items match:\n")
            for i, m in enumerate(matches):
                sys.stdout.write(
                    "  [%d] %s %s %s\n" % (i + 1, m.status, m.kind, m.title)
                )
            sys.stdout.write("Assign which item? (1-%d) " % len(matches))
            sys.stdout.flush()
            answer = sys.stdin.readline().strip()
            try:
                idx = int(answer) - 1
                if idx < 0 or idx >= len(matches):
                    raise ValueError()
                target = matches[idx]
            except (ValueError, IndexError):
                sys.stdout.write("Aborted.\n")
                return 0
        else:
            target = matches[0]
    else:
        raise ValueError("Specify an ID positional argument or --text QUERY.")

    update_args = types.SimpleNamespace(
        line=target.line,
        match_id=None,
        status=None,
        kind=None,
        title=None,
        assignee=[args.to],
        detail=None,
        add_detail=None,
        remove_detail=["assignee"],
    )
    for flag in DETAIL_FLAGS:
        dest_attr = "from_" if flag == "from" else flag
        if not hasattr(update_args, dest_attr):
            setattr(update_args, dest_attr, None)

    updated_text, updated_line, diagnostics = update_text(text, update_args)
    if _has_error(diagnostics):
        _print_diagnostics(diagnostics)
        return 1

    _ensure_writable_path(path, config, "assign")
    _pre_write_backup(path, config, "assign")
    atomic_write_text(path, updated_text)
    sys.stdout.write("Assigned to %s: %s\n" % (args.to, updated_line))

    if args.notify:
        today = timezone_today().isoformat()
        sender = getattr(args, "from_user", None) or config_user_name(config) or "self"
        target_ids = target.details.get(id_key, [])
        ref_val = str(target_ids[0]) if target_ids else (item_id or "(no-id)")
        notif_line = "[ ] M Assigned_to_%s sender:%s recipient:%s ref:%s on:%s" % (
            args.to.replace(" ", "_"),
            sender,
            args.to,
            ref_val,
            today,
        )
        append_text(path, notif_line + "\n")
        sys.stdout.write("Notification: %s\n" % notif_line)

    return 0


def command_health(args):
    config = _config(args)
    items, diagnostics = _parse_or_exit(args.paths, config)
    today = timezone_today()
    since_days = getattr(args, "since", 30)
    lookahead_days = getattr(args, "lookahead", 7)
    ignore_codes = set(
        c.upper() for c in _split_csv_args(getattr(args, "ignore", None))
    )
    type_filter = set(_split_csv_args(getattr(args, "health_types", None)))

    open_statuses = {"[ ]", "[/]", "[>]", "[?]"}

    habit_completions = {}
    for item in items:
        if item.kind == "H" and item.status == "[x]":
            latest = _latest_item_date(item)
            if latest:
                title = item.title
                if title not in habit_completions or latest > habit_completions[title]:
                    habit_completions[title] = latest

    recent_persons = set()
    for item in items:
        if item.kind == "S":
            person_vals = item.details.get("person", [])
            if not person_vals:
                continue
            person = str(person_vals[0])
            latest = _latest_item_date(item)
            if latest and (today - latest).days <= since_days:
                recent_persons.add(person)
            elif item.status in open_statuses and not item.details.get("to"):
                recent_persons.add(person)

    health_issues = []
    dependency_records = []
    if "W305" not in ignore_codes:
        dependency_records = dependency_blocker_records(
            items, key=id_key_from_config(config)
        )

    for item in items:
        if type_filter and item.kind not in type_filter:
            continue
        location = getattr(item, "source", None)
        line_no = item.line

        if "W301" not in ignore_codes:
            if (
                item.kind == "T"
                and item.status in open_statuses
                and item.status != "[>]"
            ):
                latest = _latest_item_date(item)
                if latest and (today - latest).days > since_days:
                    health_issues.append(
                        OrderedDict(
                            [
                                ("code", "W301"),
                                (
                                    "message",
                                    "Task open for %d days without update"
                                    % (today - latest).days,
                                ),
                                ("line", line_no),
                                ("source", location),
                                ("title", item.title),
                            ]
                        )
                    )

        if "W302" not in ignore_codes:
            if item.kind == "H" and item.status in open_statuses:
                last_done = habit_completions.get(item.title)
                if last_done is None or (today - last_done).days > since_days:
                    health_issues.append(
                        OrderedDict(
                            [
                                ("code", "W302"),
                                (
                                    "message",
                                    "Habit has no completion within %d days"
                                    % since_days,
                                ),
                                ("line", line_no),
                                ("source", location),
                                ("title", item.title),
                            ]
                        )
                    )

        if "W303" not in ignore_codes:
            if item.status in open_statuses:
                for val in item.details.get("due", []):
                    parsed = _parse_date_only(str(val))
                    if parsed:
                        days_until = (parsed - today).days
                        if days_until < 0:
                            health_issues.append(
                                OrderedDict(
                                    [
                                        ("code", "W303"),
                                        (
                                            "message",
                                            "Overdue by %d day(s) since %s"
                                            % (-days_until, val),
                                        ),
                                        ("line", line_no),
                                        ("source", location),
                                        ("title", item.title),
                                    ]
                                )
                            )
                        elif days_until <= lookahead_days:
                            health_issues.append(
                                OrderedDict(
                                    [
                                        ("code", "W303"),
                                        (
                                            "message",
                                            "Due in %d day(s) on %s"
                                            % (days_until, val),
                                        ),
                                        ("line", line_no),
                                        ("source", location),
                                        ("title", item.title),
                                    ]
                                )
                            )

        if "W304" not in ignore_codes:
            if item.status in open_statuses:
                for key in ("assignee", "owner"):
                    for val in item.details.get(key, []):
                        person = str(val)
                        if person not in recent_persons:
                            health_issues.append(
                                OrderedDict(
                                    [
                                        ("code", "W304"),
                                        (
                                            "message",
                                            "%s:%s has no recent S presence record within %d days"
                                            % (key, person, since_days),
                                        ),
                                        ("line", line_no),
                                        ("source", location),
                                        ("title", item.title),
                                    ]
                                )
                            )

    for record in dependency_records:
        health_issues.append(
            OrderedDict(
                [
                    ("code", "W305"),
                    (
                        "message",
                        "Blocked by %s via %s"
                        % (
                            record["blocker_id"] or record["blocker_location"],
                            record["relation"],
                        ),
                    ),
                    ("line", record["blocked_line"]),
                    ("source", record["blocked_source"]),
                    ("title", record["blocked_title"]),
                    ("blocked_by", record["blocker_id"] or record["blocker_location"]),
                    ("relation", record["relation"]),
                ]
            )
        )

    _fmt = getattr(args, "format", "text")
    _pretty = getattr(args, "pretty", False)
    if _fmt == "json":
        write_text(
            None,
            json.dumps(
                health_issues,
                ensure_ascii=False,
                indent=2 if _pretty else None,
                separators=None if _pretty else (",", ":"),
            )
            + "\n",
        )
    elif _fmt == "jsonl":
        output = "\n".join(
            json.dumps(issue, ensure_ascii=False, separators=(",", ":"))
            for issue in health_issues
        )
        if output:
            output += "\n"
        write_text(None, output)
    else:
        if not health_issues:
            write_text(None, "OK: No health issues found.\n")
        else:
            for issue in health_issues:
                prefix = ""
                if issue.get("source"):
                    prefix = "%s:" % issue["source"]
                if issue.get("line"):
                    prefix += "%d: " % issue["line"]
                write_text(
                    None,
                    "%s%s %s %s\n"
                    % (prefix, issue["code"], issue["title"], issue["message"]),
                )

    _print_warnings(diagnostics)
    return 1 if health_issues else 0


def command_inbox(args):
    config = _config(args)
    items, diagnostics = _parse_or_exit(args.paths, config)

    open_statuses = {"[ ]", "[/]", "[>]", "[?]"}
    kinds_filter = set(_split_csv_args(getattr(args, "kinds", None))) or {"T"}
    text_filter = getattr(args, "text", None)

    inbox_items = []
    for item in items:
        if item.status not in open_statuses:
            continue
        if item.kind not in kinds_filter:
            continue
        if item.details.get("project"):
            continue
        if item.details.get("due"):
            continue
        if item.details.get("assignee"):
            continue
        if text_filter and text_filter.lower() not in item.title.lower():
            continue
        inbox_items.append(item)

    if getattr(args, "fzf", False):
        return _run_inbox_selector(inbox_items)

    _fmt = getattr(args, "format", "text")
    _pretty = getattr(args, "pretty", False)
    if _fmt == "json":
        write_text(None, items_to_json(inbox_items, pretty=_pretty) + "\n")
    elif _fmt == "jsonl":
        output = items_to_jsonl(inbox_items)
        if output:
            output += "\n"
        write_text(None, output)
    else:
        if not inbox_items:
            write_text(None, "Inbox is empty.\n")
        else:
            rows = []
            for item in inbox_items:
                src = getattr(item, "source", None)
                location = (
                    ("%s:%d" % (src, item.line)) if src else ("line:%d" % item.line)
                )
                rows.append(
                    OrderedDict(
                        [
                            ("location", location),
                            ("type", item.kind),
                            ("status", item.status),
                            ("title", item.title),
                        ]
                    )
                )
            lines = ["Inbox: %d unclassified item(s)" % len(inbox_items)]
            lines.extend(_format_table(rows, ("location", "type", "status", "title")))
            write_text(None, "\n".join(lines) + "\n")

    if getattr(args, "process", False):
        writable_path = None
        for p in args.paths if args.paths else []:
            if p != "-" and os.path.exists(p):
                writable_path = p
                break
        if not writable_path:
            sys.stderr.write("ERROR: --process requires a writable file path.\n")
            return 1
        if not inbox_items:
            sys.stdout.write("Inbox is empty. Nothing to process.\n")
            return 0
        sys.stdout.write(
            "Processing %d inbox item(s). Press Enter to skip a field.\n\n"
            % len(inbox_items)
        )
        processed = 0
        for item in inbox_items:
            sys.stdout.write("  [%s %s] %s\n" % (item.status, item.kind, item.title))
            try:
                project = input("    project: ").strip()
                due = input("    due:     ").strip()
                assignee = input("    assignee:").strip()
            except (EOFError, KeyboardInterrupt):
                sys.stdout.write("\nAborted.\n")
                break
            if not project and not due and not assignee:
                sys.stdout.write("    (skipped)\n\n")
                continue
            # Build update using assign command internals
            text = read_text(writable_path)
            lines_list = text.splitlines(keepends=True)
            ln = item.line
            if ln and 0 < ln <= len(lines_list):
                import re as _re

                line = lines_list[ln - 1].rstrip("\n").rstrip("\r")
                if project:
                    line = line + "  project:%s" % project
                if due:
                    line = line + "  due:%s" % due
                if assignee:
                    line = line + "  assignee:%s" % assignee
                lines_list[ln - 1] = line + "\n"
                atomic_write_text(writable_path, "".join(lines_list))
                sys.stdout.write("    updated.\n\n")
                processed += 1
            else:
                sys.stdout.write("    (could not locate line)\n\n")
        sys.stdout.write("Processed %d/%d item(s).\n" % (processed, len(inbox_items)))
        return 0

    _print_warnings(diagnostics)
    return 0


def _run_inbox_selector(inbox_items):
    import shutil
    import subprocess

    if not inbox_items:
        write_text(None, "Inbox is empty.\n")
        return 0
    selector = shutil.which("fzf") or shutil.which("peco")
    if not selector:
        sys.stderr.write("ERROR: --fzf requires fzf or peco in PATH.\n")
        return 1
    rows = []
    for item in inbox_items:
        src = getattr(item, "source", None)
        location = ("%s:%d" % (src, item.line)) if src else ("line:%d" % item.line)
        ids = item.details.get("id", [])
        item_id = str(ids[0]) if ids else ""
        rows.append(
            "%s\t%s\t%s\t%s\t%s"
            % (location, item.kind, item.status, item_id, item.title)
        )
    proc = subprocess.run(
        [selector],
        input="\n".join(rows) + "\n",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
    )
    if proc.returncode != 0:
        return proc.returncode
    selected = proc.stdout.strip()
    if selected:
        write_text(None, selected + "\n")
    return 0


def command_cleanup(args):
    config = _config(args)
    ignore_codes = set(
        c.upper() for c in _split_csv_args(getattr(args, "ignore", None))
    )

    items, diagnostics = _parse_life_inputs(args.paths, config)
    errors = [
        d
        for d in diagnostics
        if d.severity == "error" and str(d.code).upper() not in ignore_codes
    ]
    warnings_list = [
        d
        for d in diagnostics
        if d.severity == "warning" and str(d.code).upper() not in ignore_codes
    ]
    path_label = " ".join(str(p) for p in (_normalize_paths(args.paths, config) or []))

    suggestions = []

    if errors:
        suggestions.append(
            OrderedDict(
                [
                    ("priority", 1),
                    ("check", "errors"),
                    ("count", len(errors)),
                    ("message", "%d syntax/validation error(s)" % len(errors)),
                    ("action", "lifetxt check %s" % path_label),
                ]
            )
        )

    if warnings_list:
        suggestions.append(
            OrderedDict(
                [
                    ("priority", 2),
                    ("check", "warnings"),
                    ("count", len(warnings_list)),
                    ("message", "%d warning(s)" % len(warnings_list)),
                    ("action", "lifetxt check %s" % path_label),
                ]
            )
        )

    id_key = id_key_from_config(config)
    missing_id_items = [item for item in items if not item.details.get(id_key)]
    if missing_id_items:
        suggestions.append(
            OrderedDict(
                [
                    ("priority", 3),
                    ("check", "ids"),
                    ("count", len(missing_id_items)),
                    (
                        "message",
                        "%d item(s) missing %s:" % (len(missing_id_items), id_key),
                    ),
                    ("action", "lifetxt ids --assign --dry-run %s" % path_label),
                ]
            )
        )

    ref_issue_codes = {"W215", "W216", "W217", "W218"}
    ref_issues = [
        d
        for d in diagnostics
        if str(d.code).upper() in ref_issue_codes
        and str(d.code).upper() not in ignore_codes
    ]
    if ref_issues:
        suggestions.append(
            OrderedDict(
                [
                    ("priority", 2),
                    ("check", "links"),
                    ("count", len(ref_issues)),
                    ("message", "%d broken reference(s)" % len(ref_issues)),
                    ("action", "lifetxt links %s" % path_label),
                ]
            )
        )

    open_statuses = {"[ ]", "[/]", "[>]", "[?]"}
    inbox_count = sum(
        1
        for item in items
        if item.kind == "T"
        and item.status in open_statuses
        and not item.details.get("project")
        and not item.details.get("due")
        and not item.details.get("assignee")
    )
    if inbox_count:
        suggestions.append(
            OrderedDict(
                [
                    ("priority", 4),
                    ("check", "inbox"),
                    ("count", inbox_count),
                    (
                        "message",
                        "%d unclassified task(s) without project/due/assignee"
                        % inbox_count,
                    ),
                    ("action", "lifetxt inbox %s" % path_label),
                ]
            )
        )

    today_date = timezone_today()
    cutoff = today_date - datetime.timedelta(days=90)
    old_done_count = sum(
        1
        for item in items
        if item.status in ("[x]", "[-]")
        and _archive_item_date_before(
            item,
            datetime.datetime.combine(cutoff, datetime.time.min),
        )
    )
    if old_done_count >= 10:
        suggestions.append(
            OrderedDict(
                [
                    ("priority", 5),
                    ("check", "archive"),
                    ("count", old_done_count),
                    (
                        "message",
                        "%d completed/canceled item(s) older than 90 days"
                        % old_done_count,
                    ),
                    (
                        "action",
                        "lifetxt archive --dest archive.txt --before %s --yes %s"
                        % (
                            cutoff.isoformat(),
                            path_label,
                        ),
                    ),
                ]
            )
        )

    _fmt = getattr(args, "format", "text")
    _pretty = getattr(args, "pretty", False)
    if _fmt == "json":
        write_text(
            None,
            json.dumps(
                suggestions,
                ensure_ascii=False,
                indent=2 if _pretty else None,
                separators=None if _pretty else (",", ":"),
            )
            + "\n",
        )
    else:
        if not suggestions:
            write_text(None, "OK: No cleanup actions needed.\n")
        else:
            write_text(None, "Cleanup suggestions (%d):\n" % len(suggestions))
            for sg in sorted(suggestions, key=lambda x: x["priority"]):
                write_text(
                    None,
                    "  [%d] %s: %s\n" % (sg["priority"], sg["check"], sg["message"]),
                )
                write_text(None, "      Run: %s\n" % sg["action"])

    return 0


def command_review(args):
    from .review import build_review, resolve_review_range

    config = _config(args)
    paths = _normalize_paths(getattr(args, "paths", None) or [], config)
    items, _ = _parse_life_inputs(paths, config)

    start, end = resolve_review_range(
        week=getattr(args, "week", False),
        month=getattr(args, "month", None),
        from_date=getattr(args, "from_date", None),
        to_date=getattr(args, "to_date", None),
    )
    result = build_review(
        items,
        start,
        end,
        project=getattr(args, "project", None),
        id_key=id_key_from_config(config),
    )
    completed_tasks = result["completed"]

    fmt = getattr(args, "format", "text") or "text"
    if fmt == "json":
        indent = 2 if getattr(args, "pretty", False) else None
        sys.stdout.write(json.dumps(result, ensure_ascii=False, indent=indent) + "\n")
        return 0
    if fmt == "jsonl":
        sys.stdout.write(
            json.dumps(result, ensure_ascii=False, separators=(",", ":")) + "\n"
        )
        return 0
    if fmt == "markdown":
        lines = ["# Review: %s" % result["range"], ""]
        lines.append("## Tasks")
        lines.append("- Completed: **%d**" % result["completed_tasks"])
        lines.append("- Open: %d" % result["open_tasks"])
        if completed_tasks:
            lines.append("")
            lines.append("### Completed")
            for t in completed_tasks:
                done_val = t["done"]
                lines.append(
                    "- [x] %s%s"
                    % (t["title"], (" (%s)" % done_val) if done_val else "")
                )
        if result["habits"]:
            lines.append("")
            lines.append("## Habits")
            for title, h in result["habits"].items():
                bar = "#" * h["done"] + "." * h["open"]
                lines.append(
                    "- **%s**: %d/%d (%d%%) %s"
                    % (
                        title,
                        h["done"],
                        h["done"] + h["open"],
                        h["completion_rate"],
                        bar,
                    )
                )
        if result["journals"]:
            lines.append("")
            lines.append("## Journal (%d entries)" % result["journals"])
            for entry in result["journal_entries"]:
                lines.append("- **%s** %s" % (entry["date"], entry["title"]))
                if entry["excerpt"]:
                    lines.append("  > %s" % entry["excerpt"][:120])
        if result["mood_trend"]:
            lines.append("")
            lines.append("## Mood")
            for entry in result["mood_trend"]:
                lines.append("- %s: %s" % (entry["date"], entry["mood"]))
        if result["elapsed_by_project"]:
            lines.append("")
            lines.append("## Elapsed by Project")
            for proj, elapsed in result["elapsed_by_project"].items():
                lines.append("- **%s**: %s" % (proj, elapsed))
        sys.stdout.write("\n".join(lines) + "\n")
        return 0
    if fmt == "html":

        def esc(value):
            return html.escape(str(value), quote=True)

        lines = [
            "<!doctype html>",
            '<html lang="en">',
            "<head>",
            '<meta charset="utf-8">',
            "<title>lifetxt review</title>",
            "<style>",
            "body{font-family:system-ui,-apple-system,sans-serif;line-height:1.5;max-width:900px;margin:32px auto;padding:0 16px;color:#1f2937}",
            "h1,h2{line-height:1.2} table{border-collapse:collapse;width:100%;margin:12px 0}",
            "th,td{border:1px solid #d1d5db;padding:6px 8px;text-align:left} th{background:#f3f4f6}",
            ".meta{color:#6b7280}.card{border:1px solid #e5e7eb;border-radius:8px;padding:12px;margin:12px 0}",
            "</style>",
            "</head>",
            "<body>",
            "<h1>Review</h1>",
            '<p class="meta">%s</p>' % esc(result["range"]),
            "<h2>Tasks</h2>",
            "<ul>",
            "<li>Completed: <strong>%d</strong></li>" % result["completed_tasks"],
            "<li>Open: %d</li>" % result["open_tasks"],
            "</ul>",
        ]
        if completed_tasks:
            lines.extend(["<h3>Completed</h3>", "<ul>"])
            for task in completed_tasks:
                done_val = task["done"]
                suffix = " (%s)" % esc(done_val) if done_val else ""
                lines.append("<li>%s%s</li>" % (esc(task["title"]), suffix))
            lines.append("</ul>")
        if result["habits"]:
            lines.extend(
                [
                    "<h2>Habits</h2>",
                    "<table><thead><tr><th>Habit</th><th>Done</th><th>Total</th><th>Rate</th></tr></thead><tbody>",
                ]
            )
            for title, habit in result["habits"].items():
                total = habit["done"] + habit["open"]
                lines.append(
                    "<tr><td>%s</td><td>%d</td><td>%d</td><td>%d%%</td></tr>"
                    % (esc(title), habit["done"], total, habit["completion_rate"])
                )
            lines.append("</tbody></table>")
        if result["journal_entries"]:
            lines.append("<h2>Journal</h2>")
            for entry in result["journal_entries"]:
                lines.append(
                    '<article class="card"><h3>%s %s</h3>'
                    % (esc(entry["date"]), esc(entry["title"]))
                )
                if entry["excerpt"]:
                    lines.append("<p>%s</p>" % esc(entry["excerpt"]))
                lines.append("</article>")
        if result["mood_trend"]:
            lines.extend(["<h2>Mood</h2>", "<ul>"])
            for entry in result["mood_trend"]:
                lines.append(
                    "<li>%s: %s</li>" % (esc(entry["date"]), esc(entry["mood"]))
                )
            lines.append("</ul>")
        if result["elapsed_by_project"]:
            lines.extend(["<h2>Elapsed by Project</h2>", "<ul>"])
            for project, elapsed in result["elapsed_by_project"].items():
                lines.append(
                    "<li><strong>%s</strong>: %s</li>" % (esc(project), esc(elapsed))
                )
            lines.append("</ul>")
        lines.extend(["</body>", "</html>"])
        sys.stdout.write("\n".join(lines) + "\n")
        return 0

    sys.stdout.write("Review: %s\n" % result["range"])
    sys.stdout.write("\nTasks:\n")
    sys.stdout.write("  Completed: %d\n" % result["completed_tasks"])
    sys.stdout.write("  Open: %d\n" % result["open_tasks"])

    if result["habits"]:
        sys.stdout.write("\nHabits:\n")
        for title, h in result["habits"].items():
            sys.stdout.write(
                "  %s: %d/%d (%d%%)\n"
                % (title, h["done"], h["done"] + h["open"], h["completion_rate"])
            )

    if result["journals"]:
        sys.stdout.write("\nJournal entries: %d\n" % result["journals"])
        for entry in result["journal_entries"]:
            sys.stdout.write("  %s %s\n" % (entry["date"], entry["title"]))
            if entry["excerpt"]:
                sys.stdout.write("    %s\n" % entry["excerpt"])

    if result["mood_trend"]:
        sys.stdout.write("\nMood trend:\n")
        for entry in result["mood_trend"]:
            sys.stdout.write("  %s: %s\n" % (entry["date"], entry["mood"]))

    if result["elapsed_by_project"]:
        sys.stdout.write("\nElapsed by project:\n")
        for proj, elapsed in result["elapsed_by_project"].items():
            sys.stdout.write("  %s: %s\n" % (proj, elapsed))

    return 0


def command_filter(args):
    items, diagnostics = _parse_or_exit(args.paths, _config(args))
    items = _filter_items_from_args(items, args)
    id_key = id_key_from_config(_config(args))
    limit = getattr(args, "limit", 0)
    if limit and limit > 0:
        items = items[:limit]

    if args.format == "json":
        output = items_to_json(items, pretty=args.pretty)
        write_text(args.output, output + "\n")
    elif args.format == "jsonl":
        output = items_to_jsonl(items)
        if output:
            output += "\n"
        write_text(args.output, output)
    elif args.format == "table":
        write_text(
            args.output, _format_filter_table(items, width=getattr(args, "width", 0))
        )
    else:
        write_text(
            args.output,
            _items_to_life_text(items, canonical=args.canonical, key=id_key),
        )

    _print_warnings(diagnostics)
    return 0


_FILTER_TABLE_COLUMNS = (
    ("status", "STATUS"),
    ("kind", "TYPE"),
    ("title", "TITLE"),
    ("project", "PROJECT"),
)


def _format_filter_table(items, width=None):
    if not items:
        return "No matching items.\n"

    width = int(width or 0)
    if width <= 0:
        try:
            import shutil as _shutil

            width = _shutil.get_terminal_size((80, 24)).columns
        except Exception:
            width = 80

    rows = []
    for item in items:
        project = (
            str(item.details.get("project", [""])[0])
            if item.details.get("project")
            else ""
        )
        rows.append(
            OrderedDict(
                [
                    ("status", _agenda_table_cell(item.status)),
                    ("kind", _agenda_table_cell(item.kind)),
                    ("title", _agenda_table_cell(item.title)),
                    ("project", _agenda_table_cell(project)),
                ]
            )
        )

    # Narrow terminals: compact single-line form instead of a bordered table.
    if width < 80:
        lines = []
        for row in rows:
            prefix = "%s %s " % (row["status"], row["kind"])
            max_title = max(10, width - len(prefix) - 1)
            title = row["title"]
            if len(title) > max_title:
                title = title[: max_title - 3] + "..."
            lines.append(prefix + title)
        return "\n".join(lines) + "\n"

    widths = []
    for key, heading in _FILTER_TABLE_COLUMNS:
        col_width = len(heading)
        for row in rows:
            col_width = max(col_width, len(row[key]))
        widths.append(col_width)

    lines = [
        _agenda_format_table_row(
            [heading for _key, heading in _FILTER_TABLE_COLUMNS], widths
        ),
        _agenda_format_table_row(["-" * w for w in widths], widths),
    ]
    for row in rows:
        lines.append(
            _agenda_format_table_row(
                [row[key] for key, _heading in _FILTER_TABLE_COLUMNS], widths
            )
        )
    return "\n".join(lines) + "\n"


def command_status(args):
    items, diagnostics = _parse_or_exit(args.paths, _config(args))
    records = latest_status_records(items, person=args.person, active_only=args.active)

    if args.format == "json":
        output = status_records_to_json(records, pretty=args.pretty)
        write_text(None, output + "\n")
    elif args.format == "jsonl":
        output = status_records_to_jsonl(records)
        if output:
            output += "\n"
        write_text(None, output)
    else:
        write_text(None, format_status_table(records))

    _print_warnings(diagnostics)
    return 0


def command_who(args):
    items, diagnostics = _parse_or_exit(args.paths, _config(args))
    records = latest_status_records(items, active_only=True)

    if args.format == "json":
        write_text(None, status_records_to_json(records, pretty=args.pretty) + "\n")
    else:
        if not records:
            write_text(None, "No active presence records found.\n")
        else:
            for record in records:
                person = str(record.get("person", "?"))
                state = str(record.get("state", ""))
                title = str(record.get("title", ""))
                display = state if state else title
                from_val = str(record.get("from", ""))
                write_text(None, "%-20s  %-16s  %s\n" % (person, display, from_val))

    _print_warnings(diagnostics)
    return 0


def command_search(args):
    import re as _re

    items, diagnostics = _parse_or_exit(args.paths, _config(args))
    pattern = args.pattern
    use_regex = getattr(args, "regex", False)
    in_fields = _split_csv_args(getattr(args, "in_fields", None))

    if use_regex:
        try:
            compiled = _re.compile(pattern, _re.IGNORECASE)
        except _re.error as exc:
            sys.stderr.write("ERROR: Invalid regex %r: %s\n" % (pattern, exc))
            return 1

        def _matches(text):
            return bool(compiled.search(str(text)))
    else:
        pat_lower = pattern.lower()

        def _matches(text):
            return pat_lower in str(text).lower()

    results = []
    for item in items:
        found_field = None
        if in_fields:
            for field in in_fields:
                if field == "title":
                    if _matches(item.title):
                        found_field = "title"
                        break
                else:
                    if any(_matches(v) for v in item.details.get(field, [])):
                        found_field = field
                        break
        else:
            if _matches(item.title):
                found_field = "title"
            else:
                for key, vals in item.details.items():
                    if any(_matches(v) for v in vals):
                        found_field = key
                        break
        if found_field is not None:
            results.append((item, found_field))

    if args.format == "json":
        data = [
            OrderedDict(
                [
                    ("source", getattr(item, "source", None)),
                    ("line", item.line),
                    ("status", item.status),
                    ("type", item.kind),
                    ("title", item.title),
                    ("match_field", field),
                ]
            )
            for item, field in results
        ]
        write_text(
            None,
            json.dumps(
                data,
                ensure_ascii=False,
                indent=2 if args.pretty else None,
                separators=None if args.pretty else (",", ":"),
            )
            + "\n",
        )
    elif args.format == "jsonl":
        for item, field in results:
            write_text(
                None,
                json.dumps(
                    OrderedDict(
                        [
                            ("source", getattr(item, "source", None)),
                            ("line", item.line),
                            ("status", item.status),
                            ("type", item.kind),
                            ("title", item.title),
                            ("match_field", field),
                        ]
                    ),
                    ensure_ascii=False,
                    separators=(",", ":"),
                )
                + "\n",
            )
    elif args.format == "life":
        for item, _field in results:
            src = getattr(item, "source_text", None)
            write_text(None, (src if src is not None else item_to_line(item)) + "\n")
    elif getattr(args, "count", False):
        write_text(None, "%d\n" % len(results))
    else:
        highlight = getattr(args, "highlight", False)
        if not results:
            write_text(None, "No matches found.\n")
        else:
            for item, _field in results:
                source = getattr(item, "source", None)
                line = item.line
                loc = (
                    ("%s:%d" % (source, line))
                    if source and line
                    else ("line %d" % line if line else "?")
                )
                title = item.title
                if highlight:
                    if use_regex:
                        title = compiled.sub("\033[1;33m\\g<0>\033[0m", title)
                    else:
                        idx = title.lower().find(pat_lower)
                        if idx >= 0:
                            title = (
                                title[:idx]
                                + "\033[1;33m"
                                + title[idx : idx + len(pattern)]
                                + "\033[0m"
                                + title[idx + len(pattern) :]
                            )
                write_text(
                    None, "%s  %s %s %s\n" % (loc, item.status, item.kind, title)
                )

    _print_warnings(diagnostics)
    return 0 if results else 1


def _summary_single(path, config):
    """Compute summary data for one file path."""
    id_key = id_key_from_config(config)
    text = read_text(path)
    items, _ = parse_text(text, id_key=id_key, check_ids=False, check_references=False)
    type_counts = {}
    status_counts = {}
    ids_present = 0
    ids_missing = 0
    for item in items:
        type_counts[item.kind] = type_counts.get(item.kind, 0) + 1
        status_counts[item.status] = status_counts.get(item.status, 0) + 1
        if item.details.get(id_key):
            ids_present += 1
        else:
            ids_missing += 1
    return {
        "source": path,
        "lines": len(text.splitlines()),
        "items": len(items),
        "type_counts": type_counts,
        "status_counts": status_counts,
        "ids_present": ids_present,
        "ids_missing": ids_missing,
    }


def _summary_compare(primary_paths, compare_path, config):
    a = _summary_single(
        primary_paths[0] if len(primary_paths) == 1 else primary_paths[0], config
    )
    b = _summary_single(compare_path, config)

    def _col(label, a_val, b_val):
        delta = ""
        try:
            diff = int(b_val) - int(a_val)
            delta = " (%+d)" % diff if diff != 0 else ""
        except (TypeError, ValueError):
            pass
        sys.stdout.write(
            "  %-14s %-20s %-20s%s\n" % (label, str(a_val), str(b_val), delta)
        )

    sys.stdout.write(
        "%-14s %-20s %-20s\n"
        % ("", os.path.basename(a["source"]), os.path.basename(b["source"]))
    )
    sys.stdout.write("-" * 60 + "\n")
    _col("Lines:", a["lines"], b["lines"])
    _col("Items:", a["items"], b["items"])
    all_types = sorted(
        set(list(a["type_counts"].keys()) + list(b["type_counts"].keys()))
    )
    for t in all_types:
        _col("  Type %s:" % t, a["type_counts"].get(t, 0), b["type_counts"].get(t, 0))
    all_statuses = sorted(
        set(list(a["status_counts"].keys()) + list(b["status_counts"].keys()))
    )
    for s in all_statuses:
        label = s.strip("[]")
        _col(
            "  [%s]:" % label,
            a["status_counts"].get(s, 0),
            b["status_counts"].get(s, 0),
        )
    _col("IDs present:", a["ids_present"], b["ids_present"])
    _col("IDs missing:", a["ids_missing"], b["ids_missing"])


def command_diff(args):
    config = _config(args)
    id_key = id_key_from_config(config)

    since_date = getattr(args, "since", None)
    if since_date:
        after_path = args.after
        after_dir = os.path.dirname(os.path.abspath(after_path))
        basename = os.path.basename(after_path)
        since_prefix = since_date[:10] if since_date else ""
        try:
            candidates = sorted(
                f
                for f in os.listdir(after_dir)
                if f.startswith(since_prefix)
                and f.endswith("_" + basename)
                and f != basename
            )
        except OSError:
            candidates = []
        if not candidates:
            sys.stderr.write(
                "ERROR: No snapshot found for date %s in %s\n" % (since_date, after_dir)
            )
            return 1
        args.before = os.path.join(after_dir, candidates[-1])
        sys.stdout.write("Using snapshot: %s\n" % args.before)

    before_text = read_text(args.before)
    after_text = read_text(args.after)
    before_items, _ = parse_text(
        before_text, id_key=id_key, check_ids=False, check_references=False
    )
    after_items, _ = parse_text(
        after_text, id_key=id_key, check_ids=False, check_references=False
    )

    kind_filter = set(_split_csv_args(getattr(args, "kinds", None)))
    proj_filter = set(_split_csv_args(getattr(args, "project", None)))
    change_type_filter = set(getattr(args, "change_types", None) or [])

    def _item_key(item):
        id_vals = item.details.get(id_key, [])
        if id_vals:
            return ("id", str(id_vals[0]))
        return ("title_type", "%s|%s" % (item.kind, item.title))

    def _item_passes_filter(item):
        if kind_filter and item.kind not in kind_filter:
            return False
        if proj_filter and not any(
            str(v) in proj_filter for v in item.details.get("project", [])
        ):
            return False
        return True

    before_map = {_item_key(i): i for i in before_items}
    after_map = {_item_key(i): i for i in after_items}
    before_keys = set(before_map.keys())
    after_keys = set(after_map.keys())

    changes = []

    for key in sorted(after_keys - before_keys, key=lambda k: k[1]):
        item = after_map[key]
        if not _item_passes_filter(item):
            continue
        changes.append(
            OrderedDict(
                [
                    ("change", "added"),
                    ("title", item.title),
                    ("type", item.kind),
                    ("status", item.status),
                    ("line", item.line),
                    ("source", getattr(item, "source", None)),
                ]
            )
        )

    for key in sorted(before_keys - after_keys, key=lambda k: k[1]):
        item = before_map[key]
        if not _item_passes_filter(item):
            continue
        changes.append(
            OrderedDict(
                [
                    ("change", "removed"),
                    ("title", item.title),
                    ("type", item.kind),
                    ("status", item.status),
                    ("line", item.line),
                    ("source", getattr(item, "source", None)),
                ]
            )
        )

    for key in sorted(before_keys & after_keys, key=lambda k: k[1]):
        b = before_map[key]
        a = after_map[key]
        if not _item_passes_filter(b):
            continue
        if b.status != a.status:
            change_type = (
                "completed"
                if a.status == "[x]"
                else ("canceled" if a.status == "[-]" else "status-changed")
            )
            changes.append(
                OrderedDict(
                    [
                        ("change", change_type),
                        ("title", a.title),
                        ("type", a.kind),
                        ("before", b.status),
                        ("after", a.status),
                        ("line", a.line),
                        ("source", getattr(a, "source", None)),
                    ]
                )
            )
        elif b.details != a.details:
            changed_keys = []
            all_keys = set(list(b.details.keys()) + list(a.details.keys()))
            for dk in all_keys:
                bv = b.details.get(dk, [])
                av = a.details.get(dk, [])
                if bv != av:
                    changed_keys.append(dk)
            changes.append(
                OrderedDict(
                    [
                        ("change", "detail-changed"),
                        ("title", a.title),
                        ("type", a.kind),
                        ("changed_keys", changed_keys),
                        ("line", a.line),
                        ("source", getattr(a, "source", None)),
                    ]
                )
            )

    if change_type_filter:
        changes = [c for c in changes if c.get("change") in change_type_filter]

    fmt = getattr(args, "format", "text")
    if fmt == "json":
        write_text(
            None,
            json.dumps(
                changes,
                ensure_ascii=False,
                indent=2 if args.pretty else None,
                separators=None if args.pretty else (",", ":"),
            )
            + "\n",
        )
    elif fmt == "jsonl":
        for c in changes:
            write_text(
                None, json.dumps(c, ensure_ascii=False, separators=(",", ":")) + "\n"
            )
    else:
        if not changes:
            write_text(None, "No differences found.\n")
        else:
            _DIFF_COLORS = {
                "added": "\033[32m+ ",
                "removed": "\033[31m- ",
                "completed": "\033[32m* ",
                "canceled": "\033[33m~ ",
                "status-changed": "\033[36m~ ",
                "detail-changed": "\033[36m^ ",
            }
            for c in changes:
                pfx = _DIFF_COLORS.get(c["change"], "  ")
                title = c.get("title", "")
                ctype = c.get("type", "")
                change = c.get("change", "")
                extra = ""
                if "before" in c:
                    extra = " (%s → %s)" % (c["before"], c["after"])
                elif "changed_keys" in c:
                    extra = " [%s]" % ", ".join(c["changed_keys"])
                write_text(
                    None,
                    "%s[%s] %s (%s)%s\033[0m\n" % (pfx, change, title, ctype, extra),
                )

    return 0 if not changes else 0


def _plot_bar(value, max_value, width=40, char="#"):
    if max_value == 0:
        return ""
    filled = int(round(value / max_value * width))
    return char * filled + "." * (width - filled)


def _plot_data_to_svg(plot_data, title="lifetxt plot"):
    chart_items = [
        (chart_title, data) for chart_title, data in plot_data.items() if data
    ]
    width = 900
    row_height = 24
    chart_gap = 46
    margin = 24
    title_height = 38
    height = title_height + margin
    for _chart_title, data in chart_items:
        height += 32 + max(1, len(data)) * row_height + chart_gap
    height = max(height, 160)

    parts = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" viewBox="0 0 %d %d">'
        % (width, height, width, height),
        "<style>text{font-family:Arial,sans-serif;font-size:13px;fill:#1f2937}.title{font-size:20px;font-weight:700}.section{font-size:15px;font-weight:700}.axis{fill:#6b7280}.bar{fill:#2563eb}.track{fill:#e5e7eb}</style>",
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        '<text class="title" x="%d" y="30">%s</text>'
        % (margin, html.escape(title, quote=True)),
    ]
    y = 64
    label_width = 190
    bar_x = margin + label_width
    bar_max_width = width - bar_x - 80
    for chart_title, data in chart_items:
        parts.append(
            '<text class="section" x="%d" y="%d">%s</text>'
            % (margin, y, html.escape(chart_title, quote=True))
        )
        y += 22
        max_value = max(data.values()) or 1
        for label, value in data.items():
            bar_width = int(round((value / float(max_value)) * bar_max_width))
            safe_label = html.escape(str(label), quote=True)
            parts.append(
                '<text x="%d" y="%d">%s</text>' % (margin, y + 15, safe_label[:42])
            )
            parts.append(
                '<rect class="track" x="%d" y="%d" width="%d" height="14" rx="3"/>'
                % (bar_x, y + 3, bar_max_width)
            )
            parts.append(
                '<rect class="bar" x="%d" y="%d" width="%d" height="14" rx="3"/>'
                % (bar_x, y + 3, bar_width)
            )
            parts.append(
                '<text class="axis" x="%d" y="%d">%s</text>'
                % (bar_x + bar_max_width + 10, y + 15, value)
            )
            y += row_height
        y += chart_gap
    if not chart_items:
        parts.append('<text x="%d" y="%d">No plot data.</text>' % (margin, y))
    parts.append("</svg>")
    return "\n".join(parts)


def _plot_data_to_png(plot_data, output_path):
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        raise ValueError(
            "--format png requires matplotlib. Install matplotlib or use --format svg."
        )

    chart_items = [
        (chart_title, data) for chart_title, data in plot_data.items() if data
    ]
    if not chart_items:
        chart_items = [("No plot data", OrderedDict([("none", 0)]))]
    fig, axes = plt.subplots(
        len(chart_items), 1, figsize=(10, max(3, len(chart_items) * 3))
    )
    if len(chart_items) == 1:
        axes = [axes]
    for axis, (chart_title, data) in zip(axes, chart_items):
        labels = list(data.keys())
        values = list(data.values())
        axis.barh(labels, values, color="#2563eb")
        axis.set_title(chart_title)
        axis.invert_yaxis()
    fig.tight_layout()
    fig.savefig(output_path)
    plt.close(fig)


def command_plot(args):
    from .timeutil import parse_elapsed as _parse_elapsed

    config = _config(args)
    paths = _normalize_paths(getattr(args, "paths", None) or [], config) or ["life.txt"]
    items, _ = _parse_life_inputs(paths, config)

    chart = getattr(args, "chart", "all")
    group = getattr(args, "group", "weekly")
    project_filter = getattr(args, "project", None)
    output_format = getattr(args, "format", "text")
    plot_data = OrderedDict()
    term_width = getattr(args, "width", 0)
    if not term_width:
        try:
            term_width = os.get_terminal_size().columns
        except OSError:
            term_width = 80
    bar_width = max(10, min(40, term_width - 30))

    start_str = getattr(args, "start", None)
    end_str = getattr(args, "end", None)
    today = timezone_today()
    start = (
        _parse_date_only(start_str)
        if start_str
        else (today - datetime.timedelta(days=90))
    )
    end = _parse_date_only(end_str) if end_str else today

    if project_filter:
        items = [
            i
            for i in items
            if project_filter in [str(v) for v in i.details.get("project", [])]
        ]

    def _bucket_key(d):
        if group == "daily":
            return d.isoformat()
        elif group == "monthly":
            return "%d-%02d" % (d.year, d.month)
        else:
            iso = d.isocalendar()
            return "%d-W%02d" % (iso[0], iso[1])

    def _print_bar_chart(title, data):
        if not data:
            return
        plot_data[title] = OrderedDict(
            (str(label), int(value)) for label, value in sorted(data.items())
        )
        if output_format != "text":
            return
        sys.stdout.write("\n## %s\n" % title)
        max_v = max(data.values()) if data else 1
        for label, val in sorted(data.items()):
            bar = _plot_bar(val, max_v, width=bar_width)
            sys.stdout.write("  %-12s %s %d\n" % (label[:12], bar, val))

    # tasks chart: completed tasks per bucket
    if chart in ("tasks", "all"):
        task_buckets = {}
        for item in items:
            if item.kind == "T" and item.status == "[x]":
                for val in item.details.get("done", []):
                    d = _parse_date_only(str(val))
                    if d and start <= d <= end:
                        k = _bucket_key(d)
                        task_buckets[k] = task_buckets.get(k, 0) + 1
        _print_bar_chart("Tasks Completed (%s)" % group, task_buckets)

    # habits chart: completions per habit
    if chart in ("habits", "all"):
        habit_counts = {}
        for item in items:
            if item.kind == "H" and item.status == "[x]":
                for val in item.details.get("done", []):
                    d = _parse_date_only(str(val))
                    if d and start <= d <= end:
                        habit_counts[item.title] = habit_counts.get(item.title, 0) + 1
        _print_bar_chart(
            "Habit Completions (total, %s to %s)" % (start, end), habit_counts
        )

    # mood chart: mood value distribution
    if chart in ("mood", "all"):
        mood_counts = {}
        for item in items:
            if item.kind == "J":
                for val in item.details.get("mood", []):
                    d = _latest_item_date(item) or today
                    if start <= d <= end:
                        m = str(val)
                        mood_counts[m] = mood_counts.get(m, 0) + 1
        _print_bar_chart("Mood Distribution (%s to %s)" % (start, end), mood_counts)

    # elapsed chart: total elapsed per project
    if chart in ("elapsed", "all"):
        proj_elapsed = {}
        for item in items:
            for val in item.details.get("elapsed", []):
                minutes = _parse_elapsed(str(val))
                if minutes:
                    proj = str(item.details.get("project", ["(no project)"])[0])
                    proj_elapsed[proj] = proj_elapsed.get(proj, 0) + minutes
        if proj_elapsed:
            plot_data["Elapsed Time by Project"] = OrderedDict(
                (str(project), int(minutes))
                for project, minutes in sorted(
                    proj_elapsed.items(), key=lambda x: -x[1]
                )
            )
        if proj_elapsed and output_format == "text":
            sys.stdout.write("\n## Elapsed Time by Project\n")
            max_v = max(proj_elapsed.values())
            for proj, minutes in sorted(proj_elapsed.items(), key=lambda x: -x[1]):
                bar = _plot_bar(minutes, max_v, width=bar_width)
                h, m = divmod(minutes, 60)
                label = ("%dh%dm" % (h, m)) if h else ("%dm" % m)
                sys.stdout.write("  %-14s %s %s\n" % (proj[:14], bar, label))

    # deadlines chart: items due per bucket
    if chart in ("deadlines", "all"):
        deadline_buckets = {}
        for item in items:
            for key in ("due", "do"):
                for val in item.details.get(key, []):
                    d = _parse_date_only(str(val))
                    if d and start <= d <= end:
                        k = _bucket_key(d)
                        deadline_buckets[k] = deadline_buckets.get(k, 0) + 1
        if deadline_buckets:
            _print_bar_chart("Deadline Density (%s)" % group, deadline_buckets)

    # sparkline output: single row of Unicode block chars
    if getattr(args, "sparkline", False) and output_format == "text":
        SPARKS = " ▁▂▃▄▅▆▇█"

        def _sparkline(data_dict):
            if not data_dict:
                return "(empty)"
            keys = sorted(data_dict.keys())
            vals = [data_dict.get(k, 0) for k in keys]
            max_v = max(vals) or 1
            spark = "".join(SPARKS[int(v / max_v * (len(SPARKS) - 1))] for v in vals)
            return spark + "  (%d..%d)" % (min(vals), max(vals))

        sys.stdout.write("\n## Sparklines\n")
        if chart in ("tasks", "all"):
            sys.stdout.write(
                "  Tasks:     %s\n"
                % _sparkline(task_buckets if "task_buckets" in locals() else {})
            )
        if chart in ("habits", "all"):
            habit_agg = {}
            for item in items:
                if item.kind == "H":
                    for val in item.details.get("done", []):
                        d = _parse_date_only(str(val))
                        if d and start <= d <= end:
                            k = _bucket_key(d)
                            habit_agg[k] = habit_agg.get(k, 0) + 1
            sys.stdout.write("  Habits:    %s\n" % _sparkline(habit_agg))
        if chart in ("deadlines", "all"):
            sys.stdout.write(
                "  Deadlines: %s\n"
                % _sparkline(deadline_buckets if "deadline_buckets" in locals() else {})
            )

    if output_format == "svg":
        svg = _plot_data_to_svg(plot_data, title="lifetxt plot")
        write_text(getattr(args, "output", None), svg + "\n")
        return 0
    if output_format == "png":
        output = getattr(args, "output", None)
        if not output:
            raise ValueError("--format png requires -o/--output.")
        _plot_data_to_png(plot_data, output)
        return 0

    sys.stdout.write("\n")
    return 0


def command_export_heatmap(args):
    config = _config(args)
    paths = _normalize_paths(getattr(args, "paths", None) or [], config) or ["life.txt"]
    items, _ = _parse_life_inputs(paths, config)
    today = timezone_today()
    end = (
        _parse_date_only(getattr(args, "end", None))
        if getattr(args, "end", None)
        else today
    )
    start = (
        _parse_date_only(getattr(args, "start", None))
        if getattr(args, "start", None)
        else end - datetime.timedelta(days=364)
    )
    if end < start:
        raise ValueError("--to must not be earlier than --from.")
    project = getattr(args, "project", None)
    kind = getattr(args, "kind", "all")
    counts = _activity_counts(items, start, end, kind=kind, project=project)
    svg = _activity_heatmap_svg(
        counts, start, end, title=getattr(args, "title", "lifetxt activity")
    )
    write_text(getattr(args, "output", None), svg + "\n")
    return 0


def _activity_counts(items, start, end, kind="all", project=None):
    counts = OrderedDict()
    current = start
    while current <= end:
        counts[current] = 0
        current += datetime.timedelta(days=1)

    for item in items:
        if project and project not in [
            str(value) for value in item.details.get("project", [])
        ]:
            continue
        include_task = kind in ("all", "task") and item.kind == "T"
        include_habit = kind in ("all", "habit") and item.kind == "H"
        if not include_task and not include_habit:
            continue
        for value in item.details.get("done", []):
            day = _parse_date_only(str(value))
            if day and start <= day <= end:
                counts[day] += 1
        if item.status == "[x]" and not item.details.get("done"):
            day = _latest_item_date(item)
            if day and start <= day <= end:
                counts[day] += 1
    return counts


def _activity_heatmap_svg(counts, start, end, title="lifetxt activity"):
    cell = 12
    gap = 3
    left = 42
    top = 54
    days = list(counts.keys())
    weeks = ((len(days) + start.weekday()) + 6) // 7
    width = left + weeks * (cell + gap) + 24
    height = top + 7 * (cell + gap) + 42
    max_count = max(counts.values()) if counts else 0

    def color(value):
        if value <= 0 or max_count <= 0:
            return "#ebedf0"
        ratio = value / float(max_count)
        if ratio < 0.25:
            return "#9be9a8"
        if ratio < 0.5:
            return "#40c463"
        if ratio < 0.75:
            return "#30a14e"
        return "#216e39"

    parts = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" viewBox="0 0 %d %d">'
        % (width, height, width, height),
        "<style>text{font-family:Arial,sans-serif;font-size:12px;fill:#374151}.title{font-size:18px;font-weight:700}.meta{fill:#6b7280}</style>",
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        '<text class="title" x="16" y="28">%s</text>'
        % html.escape(str(title), quote=True),
        '<text class="meta" x="16" y="46">%s to %s</text>'
        % (start.isoformat(), end.isoformat()),
    ]
    for row, label in enumerate(("Mon", "", "Wed", "", "Fri", "", "Sun")):
        if label:
            parts.append(
                '<text x="12" y="%d">%s</text>' % (top + row * (cell + gap) + 10, label)
            )
    for day, value in counts.items():
        offset = (day - start).days + start.weekday()
        week = offset // 7
        row = day.weekday()
        x = left + week * (cell + gap)
        y = top + row * (cell + gap)
        parts.append(
            '<rect x="%d" y="%d" width="%d" height="%d" rx="2" fill="%s">'
            "<title>%s: %d</title></rect>"
            % (x, y, cell, cell, color(value), day.isoformat(), value)
        )
    parts.append("</svg>")
    return "\n".join(parts)


def command_migrate(args):
    """Apply in-place format migrations to a life.txt file."""
    import re as _re
    from .timeutil import (
        parse_elapsed as _parse_elapsed,
        format_elapsed as _format_elapsed,
    )

    path = args.path
    if not os.path.exists(path):
        sys.stderr.write("ERROR: File not found: %s\n" % path)
        return 1
    migrations = args.migrations or []
    if not migrations:
        sys.stderr.write("ERROR: No --migration specified.\n")
        return 1

    text = read_text(path)
    original_text = text
    total_changes = 0

    for migration_spec in migrations:
        name, _, arg = migration_spec.partition("=")
        name = name.strip()

        if name == "normalize-elapsed":
            lines = text.splitlines(keepends=True)
            new_lines = []
            for line in lines:

                def _repl_elapsed(m):
                    raw = m.group(1)
                    minutes = _parse_elapsed(raw)
                    if minutes is None:
                        return m.group(0)
                    normalized = _format_elapsed(minutes)
                    return "elapsed:" + normalized

                new_line = _re.sub(r"elapsed:(\S+)", _repl_elapsed, line)
                if new_line != line:
                    total_changes += 1
                new_lines.append(new_line)
            text = "".join(new_lines)

        elif name == "rename-key":
            if "=" not in migration_spec:
                sys.stderr.write("ERROR: rename-key requires OLD=NEW format.\n")
                return 1
            _, _, rest = migration_spec.partition("=")
            if "=" in rest:
                old_key, _, new_key = rest.partition("=")
            else:
                old_key = arg
                new_key = rest.replace(arg + "=", "")
            # Get old_key=new_key from full spec: rename-key=old_key=new_key
            parts = migration_spec.split("=", 1)
            if len(parts) < 2:
                sys.stderr.write("ERROR: rename-key requires OLD=NEW argument.\n")
                return 1
            kv = parts[1]
            if "=" not in kv:
                sys.stderr.write("ERROR: rename-key argument must be OLD=NEW.\n")
                return 1
            old_key, _, new_key = kv.partition("=")
            old_key = old_key.strip()
            new_key = new_key.strip()
            if not old_key or not new_key:
                sys.stderr.write("ERROR: rename-key OLD and NEW must not be empty.\n")
                return 1
            lines = text.splitlines(keepends=True)
            new_lines = []
            for line in lines:
                new_line = _re.sub(
                    r"\b" + _re.escape(old_key) + r":",
                    new_key + ":",
                    line,
                )
                if new_line != line:
                    total_changes += 1
                new_lines.append(new_line)
            text = "".join(new_lines)

        elif name == "add-id":
            config = _config(args)
            id_key = id_key_from_config(config)
            parsed_items, _ = parse_text(
                text, id_key=id_key, check_ids=False, check_references=False
            )
            lines = text.splitlines(keepends=True)
            import secrets as _secrets

            for item in parsed_items:
                if not item.details.get(id_key):
                    if item.line and 0 < item.line <= len(lines):
                        new_id = _secrets.token_hex(4)
                        lines[item.line - 1] = lines[item.line - 1].rstrip("\n").rstrip(
                            "\r"
                        ) + ("  %s:%s\n" % (id_key, new_id))
                        total_changes += 1
            text = "".join(lines)

        elif name == "normalize-status":
            from .model import VALID_STATUSES, STATUS_ALIASES

            lines = text.splitlines(keepends=True)
            new_lines = []
            for line in lines:
                new_line = line
                for alias, canonical in STATUS_ALIASES.items():
                    new_line = _re.sub(
                        r"\[" + _re.escape(alias) + r"\]",
                        canonical,
                        new_line,
                    )
                if new_line != line:
                    total_changes += 1
                new_lines.append(new_line)
            text = "".join(new_lines)

        elif name == "strip-empty-details":
            lines = text.splitlines(keepends=True)
            new_lines = []
            for line in lines:
                new_line = (
                    _re.sub(r"\s+\w[\w-]*:\s*(?=\s+\w[\w-]*:|$)", "", line).rstrip()
                    + "\n"
                    if line.strip() and not line.strip().startswith("#")
                    else line
                )
                # more precise: remove detail key:value pairs where value is empty
                new_line = _re.sub(r"(\s{2,})(\w[\w-]*):\s+(?=(\s{2,}|$))", "", line)
                if new_line != line:
                    total_changes += 1
                new_lines.append(new_line)
            text = "".join(new_lines)

        elif name == "canonicalize-dates":
            lines = text.splitlines(keepends=True)
            new_lines = []

            def _normalize_date_str(s):
                # Try to parse and reformat common non-standard date formats
                for fmt in ("%Y/%m/%d", "%d/%m/%Y", "%m/%d/%Y", "%Y.%m.%d", "%d-%m-%Y"):
                    try:
                        return datetime.datetime.strptime(s, fmt).date().isoformat()
                    except ValueError:
                        pass
                return None

            date_key_pattern = _re.compile(
                r"(?<!\w)((?:due|do|on|created|updated|done|from|to|at|notify_at|notify_from|notify_to|ack|snooze_until|until|moved_to):)(\S+)"
            )

            def _repl_date(m):
                key = m.group(1)
                val = m.group(2)
                normed = _normalize_date_str(val)
                if normed and normed != val:
                    return key + normed
                return m.group(0)

            for line in lines:
                new_line = date_key_pattern.sub(_repl_date, line)
                if new_line != line:
                    total_changes += 1
                new_lines.append(new_line)
            text = "".join(new_lines)

        else:
            sys.stderr.write(
                "ERROR: Unknown migration %r. Known: normalize-elapsed, rename-key OLD=NEW, add-id, normalize-status, strip-empty-details, canonicalize-dates.\n"
                % name
            )
            return 1

    dry_run = getattr(args, "dry_run", False)
    if dry_run:
        if text == original_text:
            sys.stdout.write("No changes would be made.\n")
        else:
            import difflib

            diff = list(
                difflib.unified_diff(
                    original_text.splitlines(keepends=True),
                    text.splitlines(keepends=True),
                    fromfile=path + " (before)",
                    tofile=path + " (after)",
                )
            )
            sys.stdout.write("".join(diff[:60]))
            if len(diff) > 60:
                sys.stdout.write("... (%d more lines)\n" % (len(diff) - 60))
        sys.stdout.write("[dry-run] %d change(s) would be applied.\n" % total_changes)
        return 0

    if text == original_text:
        sys.stdout.write("No changes made.\n")
        return 0

    _ensure_writable_path(path, _config(args), "migrate")
    if getattr(args, "backup", False):
        import shutil as _shutil

        backup_path = path + ".bak"
        _shutil.copy2(path, backup_path)
        sys.stdout.write("Backup: %s\n" % backup_path)

    atomic_write_text(path, text)
    sys.stdout.write("Applied %d change(s) to %s\n" % (total_changes, path))
    return 0


def command_from_markdown(args):
    """Convert Markdown task list items (- [ ] title) to life.txt items."""
    paths = args.paths if args.paths else ["-"]
    project = getattr(args, "project", None)
    kind = getattr(args, "kind", "T") or "T"
    do_append = getattr(args, "append", False)
    output_path = getattr(args, "output", None)
    preset = getattr(args, "preset", None)

    items = []
    for path in paths:
        text = read_text(path)
        items.extend(
            _items_from_markdown_task_text(
                text,
                project=project,
                kind=kind,
                github_refs=preset == "github",
            )
        )

    if not items:
        sys.stderr.write("WARNING: No Markdown task list items found.\n")
        return 0

    output = _items_to_life_text(items, canonical=True)

    if output_path:
        _ensure_writable_path(output_path, _config(args), "from-markdown")
        if do_append:
            append_text(output_path, output)
        else:
            write_text(output_path, output)
    else:
        write_text(None, output)

    sys.stdout.write("Imported %d item(s).\n" % len(items))
    return 0


def command_snapshot(args):
    import shutil

    src = args.path
    if not os.path.exists(src):
        sys.stderr.write("ERROR: File not found: %s\n" % src)
        return 1
    if args.output:
        dest = args.output
    else:
        src_dir = os.path.dirname(os.path.abspath(src))
        snap_dir = args.snapshot_dir or os.path.join(src_dir, "snapshots")
        os.makedirs(snap_dir, exist_ok=True)
        date_prefix = timezone_today().isoformat()
        basename = os.path.basename(src)
        dest = os.path.join(snap_dir, "%s_%s" % (date_prefix, basename))
    if os.path.abspath(dest) == os.path.abspath(src):
        sys.stderr.write("ERROR: Destination is the same as source: %s\n" % dest)
        return 1
    do_diff = getattr(args, "diff", False)
    prev_snapshot = None
    if do_diff:
        snap_dir_for_diff = os.path.dirname(dest)
        basename_for_diff = os.path.basename(src)
        candidates = sorted(
            (
                f
                for f in os.listdir(snap_dir_for_diff)
                if f.endswith("_" + basename_for_diff) and f != os.path.basename(dest)
            ),
            reverse=True,
        )
        if candidates:
            prev_snapshot = os.path.join(snap_dir_for_diff, candidates[0])
    shutil.copy2(src, dest)
    sys.stdout.write("Snapshot: %s -> %s\n" % (src, dest))
    if do_diff and prev_snapshot:
        sys.stdout.write("Diff vs %s:\n" % prev_snapshot)

        class _FakeArgs:
            before = prev_snapshot
            after = dest
            format = "text"
            pretty = False
            kinds = None
            project = None
            change_types = None

        command_diff(_FakeArgs())
    elif do_diff:
        sys.stdout.write("(No previous snapshot found to diff against.)\n")
    return 0


# Key-name typo map: common misspellings -> canonical key
_LINT_KEY_VARIANTS = {
    "proj": "project",
    "projects": "project",
    "date": "due",
    "deadline": "due",
    "assign": "assignee",
    "assigned": "assignee",
    "assigned_to": "assignee",
    "owners": "owner",
    "tags": "tag",
    "bodies": "body",
    "note": "note",  # not a typo but capture for casing
    "prio": "priority",
    "priorities": "priority",
    "loc": "loc",  # fine, keep
    "attend": "attendee",
    "attendees": "attendee",
    "ref_id": "id",
    "item_id": "id",
    "do_by": "due",
    "scheduled": "do",
    "repeat_every": "repeat",
    "interval": "interval",
    "until": "until",
    "count": "count",
    "depend": "depends_on",
    "dep": "depends_on",
    "dependency": "depends_on",
    "block": "blocks",
    "related_to": "related",
    "mood_score": "mood",
    "elapsed_time": "elapsed",
    "spent": "elapsed",
    "estimate": "est",
    "sender_email": "sender",
    "recipient_email": "recipient",
    "notify": "notify_at",
}
# Non-canonical casings to flag
_LINT_CASING_VARIANTS = {
    k.upper(): k
    for k in list(_LINT_KEY_VARIANTS.values()) + list(_LINT_KEY_VARIANTS.keys())
}


def command_lint(args):
    from .model import RECOMMENDED_KEYS_BY_TYPE

    paths = args.paths if args.paths else ["-"]
    config = _config(args)
    id_key = id_key_from_config(config)
    do_fix = getattr(args, "fix", False)
    issues = []

    path_texts = {}
    for path in paths:
        text = read_text(path)
        path_texts[path] = text
        items, parse_diags = parse_text(
            text, id_key=id_key, check_ids=False, check_references=False
        )
        for item in items:
            for key in list(item.details.keys()):
                canonical = _LINT_KEY_VARIANTS.get(key)
                if canonical and canonical != key:
                    issues.append(
                        OrderedDict(
                            [
                                ("source", getattr(item, "source", path) or path),
                                ("line", item.line),
                                ("code", "L001"),
                                ("severity", "warning"),
                                (
                                    "message",
                                    "Key %r looks like a typo for %r."
                                    % (key, canonical),
                                ),
                                ("fix", canonical),
                                ("key", key),
                            ]
                        )
                    )
                elif key.upper() == key and key.lower() in _LINT_KEY_VARIANTS:
                    issues.append(
                        OrderedDict(
                            [
                                ("source", getattr(item, "source", path) or path),
                                ("line", item.line),
                                ("code", "L002"),
                                ("severity", "warning"),
                                (
                                    "message",
                                    "Key %r uses non-standard casing; expected %r."
                                    % (key, key.lower()),
                                ),
                                ("fix", key.lower()),
                                ("key", key),
                            ]
                        )
                    )
            # Check for duplicate keys
            seen = {}
            for key in item.details.keys():
                seen[key] = seen.get(key, 0) + 1
            for key, n in seen.items():
                if n > 1:
                    issues.append(
                        OrderedDict(
                            [
                                ("source", getattr(item, "source", path) or path),
                                ("line", item.line),
                                ("code", "L003"),
                                ("severity", "warning"),
                                (
                                    "message",
                                    "Duplicate key %r (%d values). Consider using a multi-value list."
                                    % (key, n),
                                ),
                                ("fix", None),
                                ("key", key),
                            ]
                        )
                    )

    # --ruleset: load custom rules from a JSON file
    ruleset_file = getattr(args, "ruleset", None)
    if ruleset_file:
        try:
            with open(ruleset_file, encoding="utf-8") as _rf:
                custom_rules = json.load(_rf)
            if not isinstance(custom_rules, list):
                sys.stderr.write("ERROR: Ruleset must be a JSON array.\n")
                return 2
        except (OSError, ValueError) as exc:
            sys.stderr.write(
                "ERROR: Cannot load ruleset %r: %s\n" % (ruleset_file, exc)
            )
            return 2
        for path in paths:
            text = path_texts.get(path, read_text(path))
            path_items, _ = parse_text(
                text, id_key=id_key, check_ids=False, check_references=False
            )
            for item in path_items:
                for key in item.details.keys():
                    for rule in custom_rules:
                        pattern = rule.get("pattern", "")
                        replacement = rule.get("replacement")
                        message = rule.get(
                            "message", "Key %r matches custom rule." % key
                        )
                        import re as _re2

                        if _re2.fullmatch(pattern, key):
                            issues.append(
                                OrderedDict(
                                    [
                                        (
                                            "source",
                                            getattr(item, "source", path) or path,
                                        ),
                                        ("line", item.line),
                                        ("code", "L100"),
                                        ("severity", "warning"),
                                        ("message", message.replace("{key}", key)),
                                        ("fix", replacement),
                                        ("key", key),
                                    ]
                                )
                            )

    # --fix: auto-rename typo keys in fixable issues (L001, L002)
    if do_fix:
        fixable = [
            i for i in issues if i.get("fix") and i.get("code") in ("L001", "L002")
        ]
        fixed_count = 0
        # Group by source file
        by_path = {}
        for issue in fixable:
            src = issue.get("source") or "-"
            by_path.setdefault(src, []).append(issue)
        for path, path_issues in by_path.items():
            if path == "-":
                sys.stderr.write("WARNING: Cannot fix stdin; skipping.\n")
                continue
            text = path_texts.get(path, read_text(path))
            lines = text.splitlines(keepends=True)
            for issue in path_issues:
                ln = issue.get("line")
                old_key = issue.get("key", "")
                new_key = issue.get("fix", "")
                if ln and 0 < ln <= len(lines):
                    import re as _re

                    lines[ln - 1] = _re.sub(
                        r"\b" + _re.escape(old_key) + r":",
                        new_key + ":",
                        lines[ln - 1],
                    )
                    fixed_count += 1
            new_text = "".join(lines)
            atomic_write_text(path, new_text)
        sys.stdout.write(
            "Fixed %d issue(s) in %d file(s).\n" % (fixed_count, len(by_path))
        )
        # Re-run lint to report remaining issues
        remaining = [i for i in issues if i.get("code") == "L003" or not i.get("fix")]
        return 1 if remaining else 0

    if args.format == "json":
        write_text(
            None,
            json.dumps(
                issues,
                ensure_ascii=False,
                indent=2 if args.pretty else None,
                separators=None if args.pretty else (",", ":"),
            )
            + "\n",
        )
    else:
        if not issues:
            write_text(None, "No lint issues found.\n")
        else:
            for issue in issues:
                src = issue.get("source") or ""
                ln = issue.get("line") or "?"
                code = issue.get("code", "")
                msg = issue.get("message", "")
                fix = issue.get("fix")
                fix_hint = (
                    " (fix: %r -> %r)" % (issue.get("key", ""), fix) if fix else ""
                )
                loc = ("%s:%s" % (src, ln)) if src else ("line %s" % ln)
                sys.stdout.write("%s  %s  %s%s\n" % (loc, code, msg, fix_hint))

    return 1 if issues else 0


def command_notify(args):
    notification_config = config_section(_config(args), "notifications")
    recipient = args.recipient or config_notification_recipient(_config(args))
    lookahead = args.lookahead or notification_config.get("lookahead") or "0m"
    grace = args.grace or notification_config.get("grace") or "2m"
    interval = args.interval or int(notification_config.get("poll_seconds") or 30)
    desktop = args.desktop or bool(notification_config.get("desktop"))
    email_config = _notification_email_config(notification_config)
    email_enabled = bool(args.email or email_config.get("enabled"))
    state_file = None
    if not args.no_state:
        state_file = args.state_file or notification_config.get("state_file")

    def load_records():
        items, diagnostics = _parse_or_exit(args.paths, _config(args))
        _print_warnings(diagnostics)
        return notification_records(
            items,
            recipient=recipient,
            lookahead=lookahead,
            grace=grace,
        )

    if args.watch:
        deliver = None
        if email_enabled:
            deliver = lambda records: _send_notification_email_batch(
                records,
                recipient=recipient,
                args=args,
                email_config=email_config,
                output=sys.stdout,
            )
        return watch_notifications(
            load_records,
            interval_seconds=interval,
            desktop=desktop,
            deliver=deliver,
            once=bool(getattr(args, "once", False)),
            state_file=state_file,
        )

    records = load_records()
    if email_enabled:
        _send_notification_email_batch(
            records,
            recipient=recipient,
            args=args,
            email_config=email_config,
            output=sys.stdout,
        )
    if args.format == "json":
        write_text(None, notifications_to_json(records, pretty=args.pretty) + "\n")
    elif args.format == "jsonl":
        output = notifications_to_jsonl(records)
        if output:
            output += "\n"
        write_text(None, output)
    else:
        write_text(None, format_notification_table(records))
    return 0


def _notification_email_config(notification_config):
    raw = (
        notification_config.get("email")
        if isinstance(notification_config, dict)
        else None
    )
    if isinstance(raw, dict):
        return raw
    return OrderedDict()


def _split_email_addresses(value):
    if isinstance(value, (list, tuple)):
        values = []
        for part in value:
            values.extend(_split_email_addresses(part))
        return values
    return [part.strip() for part in str(value or "").split(",") if part.strip()]


def _send_notification_email_batch(records, recipient, args, email_config, output=None):
    if output is None:
        output = sys.stdout
    if not records:
        output.write("No notification email sent; no notifications found.\n")
        output.flush()
        return False

    to_value = getattr(args, "email_to", None) or email_config.get("to")
    to_addrs = _split_email_addresses(to_value)
    if not to_addrs:
        raise ValueError(
            "--email-to or notifications.email.to is required with --email."
        )

    host_env = (
        getattr(args, "smtp_host_env", None)
        or email_config.get("smtp_host_env")
        or "LIFETXT_SMTP_HOST"
    )
    user_env = (
        getattr(args, "smtp_user_env", None)
        or email_config.get("smtp_user_env")
        or "LIFETXT_SMTP_USER"
    )
    pass_env = (
        getattr(args, "smtp_pass_env", None)
        or email_config.get("smtp_pass_env")
        or "LIFETXT_SMTP_PASS"
    )
    base_subject = (
        getattr(args, "email_subject", None)
        or email_config.get("subject")
        or "lifetxt notifications"
    )
    subject = notification_email_subject(records, base=base_subject)
    message = format_notification_email(records, recipient=recipient)

    if getattr(args, "dry_run", False):
        output.write(
            "[dry-run] Would email %d notification(s) to %s via $%s:\n%s\n"
            % (len(records), ", ".join(to_addrs), host_env, message)
        )
        output.flush()
        return True

    smtp_host = os.environ.get(host_env, "")
    smtp_user = os.environ.get(user_env, "")
    smtp_pass = os.environ.get(pass_env, "")
    if not smtp_host:
        raise ValueError("Environment variable %s (SMTP host) is not set." % host_env)
    if not smtp_user or not smtp_pass:
        raise ValueError(
            "Environment variables %s and %s (SMTP credentials) must be set."
            % (user_env, pass_env)
        )

    import smtplib
    from email.mime.text import MIMEText

    mime = MIMEText(message, "plain", "utf-8")
    mime["Subject"] = subject
    mime["From"] = smtp_user
    mime["To"] = ", ".join(to_addrs)
    with smtplib.SMTP(smtp_host, timeout=10) as smtp:
        smtp.starttls()
        smtp.login(smtp_user, smtp_pass)
        smtp.sendmail(smtp_user, to_addrs, mime.as_string())
    output.write("Sent notification email to %s.\n" % ", ".join(to_addrs))
    output.flush()
    return True


def command_agenda(args):
    blocked_filter = _agenda_blocked_filter(args.blocked, args.unblocked)
    if args.blocked and args.unblocked:
        raise ValueError("Use either --blocked or --unblocked, not both.")
    items, diagnostics = _parse_or_exit(args.paths, _config(args))
    start_text, end_text = _agenda_range_texts(args)
    range_start, range_end = parse_agenda_range(
        start_text=start_text,
        end_text=end_text,
        around_text=args.around,
        window_text=args.window,
    )
    records = agenda_records(items, range_start, range_end)
    records = filter_agenda_records(
        records,
        open_only=args.open,
        statuses=args.status,
        kinds=args.kinds,
        projects=args.project,
        tags=args.tag,
        tag_all=args.tag_all,
        exclude_tags=args.exclude_tag,
        users=args.user,
        persons=args.person,
        owners=args.owner,
        assignees=args.assignee,
        attendees=args.attendee,
        senders=args.sender,
        recipients=args.recipient,
        teams=args.team,
        detail_filters=args.detail,
        text=args.text,
        blocked=blocked_filter,
        user_aliases=config_user_aliases(_config(args)),
        team_members=config_team_members(_config(args)),
        team_aliases=config_team_aliases(_config(args)),
        tag_aliases=config_tag_aliases(_config(args)),
    )

    if args.format == "json":
        output = agenda_records_to_json(records, pretty=args.pretty)
        write_text(args.output, output + "\n")
    elif args.format == "jsonl":
        output = agenda_records_to_jsonl(records)
        if output:
            output += "\n"
        write_text(args.output, output)
    elif args.format == "life":
        output = agenda_records_to_life(records)
        if output:
            output += "\n"
        write_text(args.output, output)
    else:
        write_text(args.output, format_agenda_table(records, width=args.width))

    _print_warnings(diagnostics)
    return 0


def _agenda_blocked_filter(blocked_value, unblocked):
    if unblocked:
        return False
    if blocked_value in (None, "all", "false"):
        return None
    if blocked_value in (True, "only", "true"):
        return True
    if blocked_value == "hide":
        return False
    return None


def _agenda_range_texts(args):
    if getattr(args, "start", None) and getattr(args, "after", None):
        raise ValueError(
            "Use either --from or --after for agenda range start, not both."
        )
    if getattr(args, "end", None) and getattr(args, "before", None):
        raise ValueError("Use either --to or --before for agenda range end, not both.")
    start_text = getattr(args, "start", None) or getattr(args, "after", None)
    end_text = getattr(args, "end", None) or getattr(args, "before", None)
    return start_text, end_text


def command_from_json(args):
    items = _items_from_json_paths(args.paths)
    return _write_life_items(
        items,
        args.output,
        canonical=args.canonical,
        key=id_key_from_config(_config(args)),
    )


def command_from_jsonl(args):
    items = _items_from_jsonl_paths(args.paths)
    return _write_life_items(
        items,
        args.output,
        canonical=args.canonical,
        key=id_key_from_config(_config(args)),
    )


def command_from_csv(args):
    items = _items_from_csv_paths(args.paths)
    return _write_life_items(
        items,
        args.output,
        canonical=args.canonical,
        key=id_key_from_config(_config(args)),
    )


def command_assist(args):
    if args.update:
        return command_assist_update(args)

    if args.output and args.append:
        raise ValueError("Use either --output or --append, not both.")

    if args.interactive or not args.title:
        item = prompt_item(args)
    else:
        item = build_item_from_args(args)
    file_directives = _load_file_directives(args.append or args.output)
    apply_config_defaults_to_item(item, args, file_directives)
    apply_auto_id_to_item(item, args)
    line = item_to_assisted_line(item)

    if not args.no_check:
        parsed_items, diagnostics = parse_text(line + "\n")
        if not parsed_items:
            diagnostics.append(
                Diagnostic("error", "E301", "Generated line did not produce an item.")
            )
        if _has_error(diagnostics):
            _print_diagnostics(diagnostics)
            return 1
        _print_warnings(diagnostics)

    if args.append:
        _ensure_writable_path(args.append, _config(args), "assist")
        append_line(args.append, line)
    if args.output:
        _ensure_writable_path(args.output, _config(args), "assist")
        append_line(args.output, line)
    write_text(None, line + "\n")
    return 0


_CONFIG_RESOLUTION_ORDER_NOTE = """\
Settings are resolved in this order, highest priority first:
  1. CLI flag (e.g. --project, --person) on the command you run.
  2. This config file's JSON values (e.g. defaults.person, defaults.timezone).
  3. `#!` file-level directives at the top of a life.txt file (e.g. #! self:, #! project:, #! timezone:).
  4. Built-in defaults (e.g. person "self", timezone "UTC").
See the "Configuration" section of docs/en/cli.md (or docs/ja/cli.md) for details.
"""


def command_config_init(args):
    if os.path.exists(args.output) and not args.force:
        raise ValueError(
            "Config file already exists. Use --force to overwrite: %s" % args.output
        )
    write_text(args.output, config_template_text())
    write_text(None, "Wrote %s\n" % args.output)
    write_text(None, "\n" + _CONFIG_RESOLUTION_ORDER_NOTE)
    return 0


def command_config_show(args):
    output = json.dumps(_public_config(_config(args)), ensure_ascii=False, indent=2)
    write_text(None, output + "\n")
    return 0


def command_config_effective(args):
    from .config_layers import redacted_effective

    merged, _provenance = redacted_effective(
        _config(args), profile=getattr(args, "profile", None)
    )
    write_text(None, json.dumps(merged, ensure_ascii=False, indent=2) + "\n")
    return 0


def command_config_sources(args):
    from .config_layers import flatten_provenance

    rows = flatten_provenance(_config(args), profile=getattr(args, "profile", None))
    if getattr(args, "json", False):
        payload = [
            OrderedDict((("path", path), ("value", value), ("source", source)))
            for path, value, source in rows
        ]
        write_text(None, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
        return 0
    width = max((len(path) for path, _v, _s in rows), default=0)
    for path, value, source in rows:
        write_text(
            None,
            "%-*s  %-18s  %s\n"
            % (width, path, source, json.dumps(value, ensure_ascii=False)),
        )
    return 0


def command_config_get(args):
    from .config_layers import effective_config, get_dotted

    merged, _provenance = effective_config(
        _config(args), profile=getattr(args, "profile", None)
    )
    _sentinel = object()
    value = get_dotted(merged, args.path, _sentinel)
    if value is _sentinel:
        sys.stderr.write("ERROR: No such config key: %s\n" % args.path)
        return 1
    if isinstance(value, (dict, list)):
        write_text(None, json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    else:
        write_text(None, "%s\n" % json.dumps(value, ensure_ascii=False))
    return 0


def command_config_set(args):
    from .config_layers import set_dotted

    config = _config(args)
    target = args.output or config.get("_path")
    if not target:
        raise ValueError(
            "No config file to write. Run config init first or pass --output."
        )
    data = _config_without_runtime(
        config, getattr(args, "_workspace_injected_keys", None)
    )
    try:
        value = json.loads(args.value)
    except (ValueError, TypeError):
        value = args.value
    set_dotted(data, args.path, value)
    report, code = _commit_config(args, config, target, data)
    if code:
        return code
    write_text(None, "Set %s in %s\n" % (args.path, target))
    _print_config_write_notes(report)
    return 0


def command_config_unset(args):
    from .config_layers import unset_dotted

    config = _config(args)
    target = args.output or config.get("_path")
    if not target:
        raise ValueError(
            "No config file to write. Run config init first or pass --output."
        )
    data = _config_without_runtime(
        config, getattr(args, "_workspace_injected_keys", None)
    )
    if not unset_dotted(data, args.path):
        sys.stderr.write("ERROR: No such config key: %s\n" % args.path)
        return 1
    report, code = _commit_config(args, config, target, data)
    if code:
        return code
    write_text(None, "Removed %s from %s\n" % (args.path, target))
    _print_config_write_notes(report)
    return 0


def command_config_check(args):
    from .config_validation import validation_report
    from .config_writer import rejected_candidates

    config = _config(args)
    report = validation_report(config)
    # Retained candidates are never removed automatically, so report them here
    # rather than let them sit unnoticed beside the configuration.
    retained = rejected_candidates(config.get("_path"))
    if getattr(args, "json", False):
        report = OrderedDict(report)
        report["rejected_candidates"] = retained
        write_text(None, json.dumps(report, ensure_ascii=False, indent=2) + "\n")
        return 0 if report["ok"] else 1
    status = "OK" if report["ok"] else "ERRORS"
    write_text(
        None,
        "config check: %s (config_version=%s, writable=%s)\n"
        % (status, report["config_version"], report["writable"]),
    )
    for candidate in retained:
        write_text(
            None,
            "  [NOTE] refused write retained at %s (review, then delete)\n" % candidate,
        )
    for row in report["diagnostics"]:
        location = (" @ %s" % row["path"]) if row.get("path") else ""
        write_text(
            None,
            "  [%s] %s: %s%s\n"
            % (row["severity"].upper(), row["code"], row["message"], location),
        )
    return 0 if report["ok"] else 1


def command_config_migrate(args):
    from .config_migration import migrate_config

    config = _config(args)
    source = _config_without_runtime(
        config, getattr(args, "_workspace_injected_keys", None)
    )
    migrated, changes = migrate_config(source)
    if not changes:
        write_text(None, "Configuration is already current; no changes.\n")
        return 0
    write_text(None, "Planned changes:\n")
    for change in changes:
        write_text(None, "  - %s\n" % change)
    if getattr(args, "dry_run", False):
        write_text(None, "(dry run: nothing written)\n")
        return 0
    target = args.output or config.get("_path")
    if not target:
        raise ValueError(
            "No config file to write. Run config init first or pass --output."
        )
    report, code = _commit_config(args, config, target, migrated)
    if code:
        return code
    write_text(None, "Wrote migrated config to %s\n" % target)
    _print_config_write_notes(report)
    return 0


def command_workspace_doctor(args):
    from .workspace import workspace_doctor

    report = workspace_doctor(_config(args))
    if getattr(args, "json", False):
        write_text(None, json.dumps(report, ensure_ascii=False, indent=2) + "\n")
        return 0 if report["ok"] else 1
    write_text(
        None,
        "workspace doctor: %s (%d workspace(s), default=%s)\n"
        % (
            "OK" if report["ok"] else "ERRORS",
            report["workspace_count"],
            report["default_workspace"],
        ),
    )
    for entry in report["workspaces"]:
        marker = "*" if entry["default"] else " "
        write_text(
            None,
            "%s %s: %s (%d file(s)) -> %s\n"
            % (
                marker,
                entry["name"],
                "OK" if entry["ok"] else "ERRORS",
                entry["input_count"],
                entry["write_file"] or "(none)",
            ),
        )
        for row in entry["diagnostics"]:
            write_text(
                None,
                "    [%s] %s: %s\n"
                % (row["severity"].upper(), row["code"], row["message"]),
            )
    for shared in report["shared_files"]:
        write_text(
            None,
            "shared: %s (%s)\n" % (shared["path"], ", ".join(shared["workspaces"])),
        )
    return 0 if report["ok"] else 1


def _project_items(args):
    paths = _normalize_paths(
        getattr(args, "paths", None), _config(args), stdin_when_empty=False
    ) or ["life.txt"]
    items, _diagnostics = _parse_or_exit(paths, _config(args))
    return items


def _project_today():
    try:
        return timezone_today()
    except Exception:
        return None


def command_project_list(args):
    from .projects import project_list

    rows = project_list(
        _project_items(args),
        _config(args),
        _project_today(),
        include_archived=getattr(args, "all", False),
    )
    if getattr(args, "area", None):
        rows = [r for r in rows if r["area"] == args.area]
    if getattr(args, "owner", None):
        rows = [r for r in rows if r["owner"] == args.owner]
    if getattr(args, "json", False):
        write_text(None, json.dumps(rows, ensure_ascii=False, indent=2) + "\n")
        return 0
    if not rows:
        write_text(None, "No projects found.\n")
        return 0
    for row in rows:
        pct = (
            "%.0f%%" % row["progress_percent"]
            if row["progress_percent"] is not None
            else "n/a"
        )
        write_text(
            None,
            "[%s] %-20s %s  %d/%d done (%s)  open=%d overdue=%d blocked=%d risks=%d\n"
            % (
                row["health"][0].upper(),
                row["name"],
                row["state"],
                row["task_done"],
                row["task_total"],
                pct,
                row["open_count"],
                row["overdue_count"],
                row["blocked_count"],
                row["open_risk_count"],
            ),
        )
    return 0


def command_project_show(args):
    from .projects import project_hub

    try:
        hub = project_hub(
            _project_items(args), _config(args), args.name, _project_today()
        )
    except ValueError as exc:
        sys.stderr.write("ERROR: %s\n" % exc)
        return 1
    if getattr(args, "json", False):
        write_text(None, json.dumps(hub, ensure_ascii=False, indent=2) + "\n")
        return 0
    write_text(None, "%s (%s)\n" % (hub["display_name"], hub["name"]))
    write_text(
        None,
        "  state=%s owner=%s area=%s due=%s\n"
        % (hub["state"], hub["owner"], hub["area"], hub["due"]),
    )
    prog = hub["progress"]
    pct = "%.0f%%" % prog["percent"] if prog["percent"] is not None else "n/a"
    write_text(
        None,
        "  progress: %d/%d (%s)  health=%s (%s)\n"
        % (
            prog["done"],
            prog["total"],
            pct,
            hub["health"]["label"],
            "; ".join(hub["health"]["reasons"]),
        ),
    )
    _project_section("open tasks", hub["open_tasks"])
    _project_section("overdue", hub["overdue_tasks"])
    _project_section("blocked", hub["blocked_tasks"])
    _project_section("milestones", hub["milestones"])
    _project_section("risks", hub["risks"], risk=True)
    _project_section("decisions", hub["decisions"])
    _project_section("meetings", hub["meetings"])
    for note in hub["health"]["limitations"]:
        write_text(None, "  note: %s\n" % note)
    return 0


def _project_section(label, rows, risk=False):
    if not rows:
        return
    write_text(None, "  %s (%d):\n" % (label, len(rows)))
    for row in rows:
        if risk:
            write_text(
                None,
                "    - [%s/%s] %s\n" % (row["severity"], row["state"], row["title"]),
            )
        else:
            extra = ""
            if row.get("due"):
                extra = " due:%s" % row["due"]
            elif row.get("on"):
                extra = " on:%s" % row["on"]
            write_text(None, "    - %s%s\n" % (row["title"], extra))


def command_project_health(args):
    from .projects import alias_map, collect_projects, compute_health

    config = _config(args)
    projects = collect_projects(_project_items(args), config, _project_today())
    if getattr(args, "all", False) or not getattr(args, "name", None):
        names = list(projects.keys())
    else:
        canonical = alias_map(config).get(args.name, args.name)
        if canonical not in projects:
            sys.stderr.write("ERROR: Unknown project %r\n" % args.name)
            return 1
        names = [canonical]
    reports = OrderedDict()
    for name in names:
        reports[name] = compute_health(projects[name], _project_today())
    if getattr(args, "json", False):
        write_text(None, json.dumps(reports, ensure_ascii=False, indent=2) + "\n")
        return 0
    for name, health in reports.items():
        write_text(
            None,
            "%s: %s (%s)\n" % (name, health["label"], "; ".join(health["reasons"])),
        )
        write_text(None, "  formula: %s\n" % health["formula"])
        for note in health["limitations"]:
            write_text(None, "  note: %s\n" % note)
    return 0


def command_project_timeline(args):
    from .projects import project_timeline

    try:
        rows = project_timeline(
            _project_items(args), _config(args), args.name, _project_today()
        )
    except ValueError as exc:
        sys.stderr.write("ERROR: %s\n" % exc)
        return 1
    if getattr(args, "json", False):
        write_text(None, json.dumps(rows, ensure_ascii=False, indent=2) + "\n")
        return 0
    for row in rows:
        item = row["item"]
        write_text(
            None, "%s  %s %s\n" % (row["when"], item.get("kind", ""), item["title"])
        )
    return 0


def command_project_workload(args):
    from .projects import project_workload

    try:
        rows = project_workload(
            _project_items(args), _config(args), args.name, _project_today()
        )
    except ValueError as exc:
        sys.stderr.write("ERROR: %s\n" % exc)
        return 1
    if getattr(args, "json", False):
        write_text(None, json.dumps(rows, ensure_ascii=False, indent=2) + "\n")
        return 0
    for row in rows:
        write_text(
            None,
            "%-20s open=%d done=%d overdue=%d\n"
            % (row["assignee"], row["open"], row["done"], row["overdue"]),
        )
    return 0


def command_project_risks(args):
    from .projects import project_risks

    try:
        rows = project_risks(
            _project_items(args), _config(args), args.name, _project_today()
        )
    except ValueError as exc:
        sys.stderr.write("ERROR: %s\n" % exc)
        return 1
    if getattr(args, "json", False):
        write_text(None, json.dumps(rows, ensure_ascii=False, indent=2) + "\n")
        return 0
    if not rows:
        write_text(None, "No risks recorded.\n")
        return 0
    for row in rows:
        write_text(
            None,
            "[%s/%s] %s (owner=%s)\n"
            % (row["severity"], row["state"], row["title"], row["owner"]),
        )
    return 0


def _project_write_target(args):
    config = _config(args)
    target = getattr(args, "to", None) or config_write_file(config)
    if not target:
        paths = config_paths(config)
        if paths:
            target = paths[0]
    if not target:
        target = "life.txt"
    return target


def command_project_new(args):
    from .projects import build_project_record_line

    line = build_project_record_line(
        args.name,
        owner=args.owner,
        area=args.area,
        state=args.state,
        due=args.due,
        start=args.start,
        visibility=args.visibility,
    )
    return _emit_project_line(args, line)


def command_project_add(args):
    from .projects import (
        build_decision_line,
        build_meeting_line,
        build_milestone_line,
        build_risk_line,
    )

    if args.record_type == "milestone":
        line = build_milestone_line(
            args.project, args.title, due=args.due, owner=args.owner
        )
    elif args.record_type == "risk":
        line = build_risk_line(
            args.project,
            args.title,
            severity=args.severity,
            owner=args.owner,
            state=args.state,
        )
    elif args.record_type == "decision":
        line = build_decision_line(
            args.project, args.title, on=args.on, owner=args.owner
        )
    else:
        line = build_meeting_line(args.project, args.title, on=args.on, at=args.at)
    return _emit_project_line(args, line)


def command_project_archive(args):
    """Move one project's records to the workspace's configured archive source.

    Reuses ``command_archive``'s candidate filtering, external-reference
    warnings, and transactional multi-file write unchanged; this only adds a
    ``project:`` filter and workspace-based source/destination resolution so
    the write target is never outside the resolved source manifest.
    """
    config = _config(args)
    from .workspace import resolve_workspace, workspace_resolution_active

    workspace_name = getattr(args, "workspace", None)
    archive_paths = []
    scan_paths = None
    if workspace_resolution_active(config, workspace_name):
        resolution = resolve_workspace(config, workspace_name)
        archive_paths = resolution["archive_paths"]
        # Never scan the archive destination itself as a source: it would
        # self-include (command_archive rejects that) or, worse, be read
        # before it exists.
        archive_path_set = {os.path.normcase(path) for path in archive_paths}
        scan_paths = [
            path
            for path in resolution["input_paths"]
            if os.path.normcase(path) not in archive_path_set
        ]

    dest = getattr(args, "dest", None)
    if not dest:
        if not archive_paths:
            raise ValueError(
                "No archive-role workspace source is configured. Add a source "
                "with role: archive to the active workspace, or pass --dest "
                "explicitly."
            )
        dest = archive_paths[0]

    explicit_paths = getattr(args, "paths", None)
    if explicit_paths:
        paths = _normalize_paths(explicit_paths, config, stdin_when_empty=False)
    elif scan_paths:
        paths = scan_paths
    else:
        paths = _normalize_paths(None, config, stdin_when_empty=False)
    if not paths:
        raise ValueError("No source files specified.")

    archive_args = argparse.Namespace(
        paths=paths,
        dest=dest,
        revision=getattr(args, "revision", None) or [],
        statuses=getattr(args, "statuses", None),
        before=getattr(args, "before", None),
        max_items=getattr(args, "max_items", None),
        dry_run=getattr(args, "dry_run", False),
        copy=getattr(args, "copy", False),
        yes=getattr(args, "yes", False),
        orphan_children=getattr(args, "orphan_children", "block"),
        preserve_structure=getattr(args, "preserve_structure", False),
        block_on_external_refs=getattr(args, "block_on_external_refs", False),
        project_filter=args.name,
        config=getattr(args, "config", None),
        config_data=config,
        workspace=workspace_name,
    )
    return command_archive(archive_args)


def _emit_project_line(args, line):
    if getattr(args, "dry_run", False):
        write_text(None, line + "\n")
        return 0
    target = _project_write_target(args)
    _ensure_writable_path(target, _config(args), "project")
    append_line(target, line)
    write_text(None, "Appended to %s:\n  %s\n" % (target, line))
    return 0


def command_portfolio(args):
    from .projects import portfolio

    report = portfolio(
        _project_items(args),
        _config(args),
        _project_today(),
        include_archived=getattr(args, "all", False),
    )
    if getattr(args, "json", False):
        write_text(None, json.dumps(report, ensure_ascii=False, indent=2) + "\n")
        return 0
    write_text(None, "Portfolio (%d project(s)):\n" % report["count"])
    for row in report["projects"]:
        pct = (
            "%.0f%%" % row["progress_percent"]
            if row["progress_percent"] is not None
            else "n/a"
        )
        write_text(
            None,
            "[%s] %-20s %-8s progress=%s open=%d overdue=%d blocked=%d risk=%s\n"
            % (
                row["health"][0].upper(),
                row["name"],
                row["state"],
                pct,
                row["open_count"],
                row["overdue_count"],
                row["blocked_count"],
                row["top_risk_severity"] or "-",
            ),
        )
    write_text(
        None,
        "legend: progress=%s; health=%s\n"
        % (report["legend"]["progress"], report["legend"]["health"]),
    )
    return 0


def command_today(args):
    from .command_center import command_center

    report = command_center(
        _project_items(args),
        _config(args),
        _project_today(),
        horizon_days=getattr(args, "horizon", 3),
        person=getattr(args, "person", None),
        mode=getattr(args, "mode", "today"),
    )
    if getattr(args, "json", False):
        write_text(None, json.dumps(report, ensure_ascii=False, indent=2) + "\n")
        return 0
    counts = report["counts"]
    header = "%s brief" % report["mode"].capitalize()
    if report["reference_date"]:
        header += " for %s" % report["reference_date"]
    write_text(None, header + "\n")
    if not report["safety"]["ok"]:
        write_text(
            None, "  ! config has %d error(s)\n" % report["safety"]["config_errors"]
        )
    _today_section("Overdue", report["overdue"])
    _today_section("Due today", report["due_today"])
    _today_section("Upcoming (%dd)" % report["horizon_days"], report["upcoming"])
    _today_section("Blocked", report["blocked"])
    _today_section("Waiting", report["waiting"])
    _today_section("Messages", report["messages"])
    _today_section("Habits", report["habits"])
    _today_section("Captures (untriaged)", report["captures"])
    if report["project_attention"]:
        write_text(
            None,
            "Projects needing attention (%d):\n" % len(report["project_attention"]),
        )
        for row in report["project_attention"]:
            write_text(
                None,
                "  [%s] %s: %s\n"
                % (row["health"][0].upper(), row["name"], "; ".join(row["reasons"])),
            )
    if all(v == 0 for v in counts.values()):
        write_text(None, "All clear.\n")
    return 0


def _today_section(label, rows, limit=10):
    if not rows:
        return
    write_text(None, "%s (%d):\n" % (label, len(rows)))
    for row in rows[:limit]:
        due = " due:%s" % row["due"] if row.get("due") else ""
        project = " @%s" % row["project"] if row.get("project") else ""
        write_text(
            None, "  - %s %s%s%s\n" % (row["status"], row["title"], project, due)
        )
    if len(rows) > limit:
        write_text(None, "  ... and %d more\n" % (len(rows) - limit))


def command_area_list(args):
    from .areas import area_list

    rows = area_list(_project_items(args), _config(args))
    if getattr(args, "json", False):
        write_text(None, json.dumps(rows, ensure_ascii=False, indent=2) + "\n")
        return 0
    if not rows:
        write_text(None, "No areas found.\n")
        return 0
    for row in rows:
        pct = (
            "%.0f%%" % row["progress_percent"]
            if row["progress_percent"] is not None
            else "n/a"
        )
        write_text(
            None,
            "%-16s %d/%d done (%s)  open=%d projects=%d\n"
            % (
                row["name"],
                row["task_done"],
                row["task_total"],
                pct,
                row["task_open"],
                row["project_count"],
            ),
        )
    return 0


def command_area_show(args):
    from .areas import area_show

    try:
        summary = area_show(_project_items(args), _config(args), args.name)
    except ValueError as exc:
        sys.stderr.write("ERROR: %s\n" % exc)
        return 1
    if getattr(args, "json", False):
        write_text(None, json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
        return 0
    write_text(None, "%s\n" % summary["name"])
    pct = (
        "%.0f%%" % summary["progress_percent"]
        if summary["progress_percent"] is not None
        else "n/a"
    )
    write_text(
        None,
        "  tasks: %d/%d done (%s) open=%d\n"
        % (summary["task_done"], summary["task_total"], pct, summary["task_open"]),
    )
    if summary["projects"]:
        write_text(None, "  projects: %s\n" % ", ".join(summary["projects"]))
    for row in summary["open_items"]:
        write_text(None, "  - %s %s\n" % (row["status"], row["title"]))
    return 0


def command_backlinks(args):
    from .links import backlink_records

    items, _diagnostics = _parse_or_exit(
        _normalize_paths(
            getattr(args, "paths", None), _config(args), stdin_when_empty=False
        )
        or ["life.txt"],
        _config(args),
    )
    key = id_key_from_config(_config(args))
    records = backlink_records(items, args.id, key=key)
    if getattr(args, "json", False):
        write_text(None, json.dumps(records, ensure_ascii=False, indent=2) + "\n")
        return 0
    if not records:
        write_text(None, "No items reference %s.\n" % args.id)
        return 0
    write_text(None, "Items referencing %s (%d):\n" % (args.id, len(records)))
    for row in records:
        write_text(
            None,
            "  %s <- %s (%s) %s\n"
            % (
                row["relation"],
                row["source_id"] or "(no id)",
                row["source_status"],
                row["source_title"],
            ),
        )
    return 0


def _emit_query_items(args, items, diagnostics=None):
    id_key = id_key_from_config(_config(args))
    fmt = getattr(args, "format", "life")
    if fmt == "json":
        write_text(
            args.output,
            items_to_json(items, pretty=getattr(args, "pretty", False)) + "\n",
        )
    elif fmt == "jsonl":
        output = items_to_jsonl(items)
        if output:
            output += "\n"
        write_text(args.output, output)
    elif fmt == "table":
        write_text(
            args.output, _format_filter_table(items, width=getattr(args, "width", 0))
        )
    else:
        write_text(
            args.output,
            _items_to_life_text(
                items, canonical=getattr(args, "canonical", False), key=id_key
            ),
        )
    for row in diagnostics or []:
        if row.get("severity") == "error":
            sys.stderr.write("ERROR: %s %s\n" % (row.get("code"), row.get("message")))
        else:
            sys.stderr.write("WARNING: %s %s\n" % (row.get("code"), row.get("message")))


def command_query(args):
    from .query import run_query

    items, _diagnostics = _parse_or_exit(
        _normalize_paths(
            getattr(args, "paths", None), _config(args), stdin_when_empty=False
        )
        or ["life.txt"],
        _config(args),
    )
    filtered, query_diags = run_query(
        items,
        args.query,
        config=_config(args),
        sort=getattr(args, "sort", None),
        order=getattr(args, "order", "asc"),
        limit=getattr(args, "limit", None),
    )
    if any(d["severity"] == "error" for d in query_diags):
        for d in query_diags:
            if d["severity"] == "error":
                sys.stderr.write("ERROR: %s %s\n" % (d["code"], d["message"]))
        return 1
    _emit_query_items(args, filtered, query_diags)
    return 0


def command_view_list(args):
    from .saved_views import list_saved_views

    views = list_saved_views(_config(args))
    if getattr(args, "json", False):
        write_text(None, json.dumps(views, ensure_ascii=False, indent=2) + "\n")
        return 0
    if not views:
        write_text(None, "No saved views configured.\n")
        return 0
    for view in views:
        sort = ",".join(view["sort"]) or "-"
        write_text(
            None,
            "%-20s %s  (sort=%s limit=%s)\n"
            % (view["name"], view["query"], sort, view["limit"]),
        )
    return 0


def command_view_show(args):
    from .saved_views import get_saved_view

    try:
        view = get_saved_view(_config(args), args.name)
    except ValueError as exc:
        sys.stderr.write("ERROR: %s\n" % exc)
        return 1
    write_text(None, json.dumps(view, ensure_ascii=False, indent=2) + "\n")
    return 0


def command_view_validate(args):
    from .saved_views import validate_saved_views

    rows = validate_saved_views(_config(args))
    if getattr(args, "json", False):
        write_text(None, json.dumps(rows, ensure_ascii=False, indent=2) + "\n")
        return 0 if not rows else 1
    if not rows:
        write_text(None, "All saved views are valid.\n")
        return 0
    for row in rows:
        write_text(
            None,
            "[%s] %s: %s\n" % (row["severity"].upper(), row["code"], row["message"]),
        )
    return 1


def command_view_run(args):
    from .saved_views import run_saved_view

    items, _diagnostics = _parse_or_exit(
        _normalize_paths(
            getattr(args, "paths", None), _config(args), stdin_when_empty=False
        )
        or ["life.txt"],
        _config(args),
    )
    try:
        filtered, query_diags = run_saved_view(items, _config(args), args.name)
    except ValueError as exc:
        sys.stderr.write("ERROR: %s\n" % exc)
        return 1
    _emit_query_items(args, filtered, query_diags)
    return 0


def command_group_list(args):
    from .groups import group_summaries

    summaries = group_summaries(_config(args))
    if getattr(args, "json", False):
        write_text(None, json.dumps(summaries, ensure_ascii=False, indent=2) + "\n")
        return 0
    if not summaries:
        write_text(None, "No groups configured.\n")
        return 0
    for row in summaries:
        flag = "" if row["ok"] else " [errors]"
        write_text(
            None,
            "%-20s %d member(s), %d disabled%s\n"
            % (row["name"], row["resolved_members"], row["disabled"], flag),
        )
    return 0


def command_group_show(args):
    from .groups import expand_group, group_directory

    config = _config(args)
    directory = group_directory(config)
    if args.name not in directory:
        sys.stderr.write("ERROR: Unknown group %r\n" % args.name)
        return 1
    diagnostics = []
    members = expand_group(config, args.name, diagnostics=diagnostics)
    if getattr(args, "json", False):
        payload = OrderedDict(
            (
                ("name", args.name),
                ("members", members),
                ("definition", directory[args.name]),
                ("diagnostics", diagnostics),
            )
        )
        write_text(None, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
        return 0
    write_text(None, "%s (%d resolved member(s)):\n" % (args.name, len(members)))
    for member in members:
        write_text(None, "  - %s\n" % member)
    for row in diagnostics:
        write_text(
            None,
            "  [%s] %s: %s\n" % (row["severity"].upper(), row["code"], row["message"]),
        )
    return 0


def command_group_validate(args):
    from .groups import validate_groups

    rows = validate_groups(_config(args))
    if getattr(args, "json", False):
        write_text(None, json.dumps(rows, ensure_ascii=False, indent=2) + "\n")
        return 0 if not any(r["severity"] == "error" for r in rows) else 1
    if not rows:
        write_text(None, "All groups are valid.\n")
        return 0
    for row in rows:
        write_text(
            None,
            "[%s] %s: %s\n" % (row["severity"].upper(), row["code"], row["message"]),
        )
    return 0 if not any(r["severity"] == "error" for r in rows) else 1


def command_message_recipients(args):
    from .groups import resolve_recipients

    refs = [r.strip() for r in str(args.to).split(",") if r.strip()]
    result = resolve_recipients(_config(args), refs)
    if getattr(args, "json", False):
        write_text(None, json.dumps(result, ensure_ascii=False, indent=2) + "\n")
        return (
            0 if not any(d["severity"] == "error" for d in result["diagnostics"]) else 1
        )
    write_text(
        None, "Resolved %d recipient(s) from %s:\n" % (result["count"], ", ".join(refs))
    )
    for recipient in result["recipients"]:
        write_text(None, "  - %s\n" % recipient)
    for row in result["diagnostics"]:
        write_text(
            None,
            "  [%s] %s: %s\n" % (row["severity"].upper(), row["code"], row["message"]),
        )
    return 0 if not any(d["severity"] == "error" for d in result["diagnostics"]) else 1


def command_message_send(args):
    from .groups import resolve_recipients

    refs = [r.strip() for r in str(args.to).split(",") if r.strip()]
    config = _config(args)
    result = resolve_recipients(config, refs)
    errors = [d for d in result["diagnostics"] if d["severity"] == "error"]
    if errors:
        for row in errors:
            sys.stderr.write("ERROR: %s %s\n" % (row["code"], row["message"]))
        return 1
    if not result["recipients"]:
        sys.stderr.write("ERROR: No recipients resolved.\n")
        return 1
    sender = args.sender or config_user_name(config)
    line = _build_message_line(
        args.title,
        sender,
        result,
        refs,
        ack_policy=getattr(args, "ack_policy", "any"),
        body=getattr(args, "body", None),
    )
    if getattr(args, "dry_run", False):
        write_text(None, line + "\n")
        return 0
    target = getattr(args, "output", None) or config_write_file(config)
    if not target:
        paths = config_paths(config)
        target = paths[0] if paths else "life.txt"
    _ensure_writable_path(target, config, "message send")
    append_line(target, line)
    write_text(
        None,
        "Appended message to %s (%d recipient(s)):\n  %s\n"
        % (target, result["count"], line),
    )
    return 0


def _build_message_line(title, sender, resolution, refs, ack_policy="any", body=None):
    parts = ["[ ] M", "_".join(str(title).split()), "sender:%s" % sender]
    for recipient in resolution["recipients"]:
        parts.append("recipient:%s" % recipient)
    # Preserve the original group/team references for audit without losing the
    # readable resolved recipient list above. A reference is a group/team when
    # its expansion is not simply the literal name itself.
    expansion = resolution.get("expansion", {})
    for ref in refs:
        _prefix, bare = _split_group_ref(ref)
        expanded = expansion.get(ref, [ref])
        if expanded != [bare]:
            parts.append("group:%s" % bare)
    if ack_policy and ack_policy != "any":
        parts.append("ack_policy:%s" % ack_policy)
    if body:
        parts.append("body:%s" % "_".join(str(body).split()))
    return " ".join(parts)


def _split_group_ref(ref):
    text = str(ref)
    for prefix in ("group:", "team:", "user:", "person:"):
        if text.startswith(prefix):
            return prefix[:-1], text[len(prefix) :]
    return None, text


def command_message_status(args):
    from .delivery import delivery_summary
    from .groups import resolve_recipients

    items, _diagnostics = _parse_or_exit(
        _normalize_paths(
            getattr(args, "paths", None), _config(args), stdin_when_empty=False
        )
        or ["life.txt"],
        _config(args),
    )
    config = _config(args)
    target_id = getattr(args, "id", None)
    policy = getattr(args, "policy", None)
    summaries = []
    for item in items:
        if item.kind != "M":
            continue
        if target_id and (item.details.get("id", [None])[0] != target_id):
            continue
        summaries.append(delivery_summary(item, config, resolve_recipients, policy))
    if getattr(args, "json", False):
        write_text(None, json.dumps(summaries, ensure_ascii=False, indent=2) + "\n")
        return 0
    if not summaries:
        write_text(None, "No messages found.\n")
        return 0
    for summary in summaries:
        ack = summary["acknowledgement"]
        write_text(
            None,
            "%s [%s] recipients=%d ack=%d/%d (%s) %s\n"
            % (
                summary["title"],
                summary["message_id"] or "no-id",
                summary["recipient_count"],
                ack["acknowledged"],
                ack["required"],
                ack["policy"],
                "COMPLETE" if ack["complete"] else "open",
            ),
        )
        for state in summary["states"]:
            write_text(None, "    %-16s %s\n" % (state["recipient"], state["state"]))
    return 0


def command_person_list(args):
    from .people import people_list

    rows = people_list(_project_items(args), _config(args), _project_today())
    if getattr(args, "json", False):
        write_text(None, json.dumps(rows, ensure_ascii=False, indent=2) + "\n")
        return 0
    if not rows:
        write_text(None, "No people found.\n")
        return 0
    for row in rows:
        write_text(
            None,
            "%-20s open=%d messages=%d meetings=%d\n"
            % (row["person"], row["assigned_open"], row["messages"], row["meetings"]),
        )
    return 0


def command_person_show(args):
    from .people import person_overview

    ov = person_overview(
        _project_items(args), _config(args), args.name, _project_today()
    )
    if getattr(args, "json", False):
        write_text(None, json.dumps(ov, ensure_ascii=False, indent=2) + "\n")
        return 0
    write_text(
        None,
        "%s%s\n"
        % (ov["person"], (" (%s)" % ", ".join(ov["aliases"])) if ov["aliases"] else ""),
    )
    if ov["presence"]:
        write_text(
            None,
            "  presence: %s %s\n"
            % (ov["presence"].get("state") or "", ov["presence"].get("from") or ""),
        )
    counts = ov["counts"]
    write_text(
        None,
        "  open=%d waiting=%d overdue=%d sent=%d received=%d meetings=%d\n"
        % (
            counts["assigned_open"],
            counts["waiting"],
            counts["overdue"],
            counts["messages_sent"],
            counts["messages_received"],
            counts["meetings"],
        ),
    )
    mem = ov["memberships"]
    if mem["teams"] or mem["groups"]:
        write_text(
            None,
            "  teams: %s  groups: %s\n"
            % (", ".join(mem["teams"]) or "-", ", ".join(mem["groups"]) or "-"),
        )
    _person_section("Assigned (open)", ov["assigned_open"])
    _person_section("Overdue", ov["overdue"])
    _person_section("Waiting", ov["waiting"])
    _person_section("Meetings", ov["meetings"])
    if ov["projects"]:
        write_text(None, "  projects:\n")
        for proj in ov["projects"]:
            role = "owner" if proj["owner"] else "member"
            write_text(
                None,
                "    - %s (%s, %d task(s))\n"
                % (proj["name"], role, proj["assigned_tasks"]),
            )
    return 0


def _person_section(label, rows, limit=10):
    if not rows:
        return
    write_text(None, "  %s (%d):\n" % (label, len(rows)))
    for row in rows[:limit]:
        due = " due:%s" % row["due"] if row.get("due") else ""
        project = " @%s" % row["project"] if row.get("project") else ""
        write_text(
            None, "    - %s %s%s%s\n" % (row["status"], row["title"], project, due)
        )


def command_person_group(args):
    from .people import group_overview

    try:
        report = group_overview(
            _project_items(args), _config(args), args.name, _project_today()
        )
    except ValueError as exc:
        sys.stderr.write("ERROR: %s\n" % exc)
        return 1
    if getattr(args, "json", False):
        write_text(None, json.dumps(report, ensure_ascii=False, indent=2) + "\n")
        return 0
    write_text(
        None,
        "%s (%d member(s)) open=%d overdue=%d\n"
        % (
            report["group"],
            report["member_count"],
            report["total_assigned_open"],
            report["total_overdue"],
        ),
    )
    for member in report["members"]:
        write_text(
            None,
            "  %-20s open=%d overdue=%d received=%d\n"
            % (
                member["person"],
                member["assigned_open"],
                member["overdue"],
                member["messages_received"],
            ),
        )
    for row in report["diagnostics"]:
        write_text(
            None,
            "  [%s] %s: %s\n" % (row["severity"].upper(), row["code"], row["message"]),
        )
    return 0


def _proposal_target(args):
    config = _config(args)
    target = getattr(args, "to", None) or config_write_file(config)
    if not target:
        paths = config_paths(config)
        target = paths[0] if paths else "life.txt"
    return target


def command_proposal_list(args):
    from .inbox import inbox_summary, list_proposals, proposal_to_line

    config = _config(args)
    proposals = list_proposals(config, status=getattr(args, "status", None))
    if getattr(args, "json", False):
        write_text(None, json.dumps(proposals, ensure_ascii=False, indent=2) + "\n")
        return 0
    if not proposals:
        write_text(None, "No proposals.\n")
        return 0
    for proposal in proposals:
        try:
            preview = proposal_to_line(proposal)
        except ValueError:
            preview = proposal.get("operation", "?")
        write_text(
            None,
            "%-12s [%-8s] %-8s %s\n"
            % (
                proposal["id"],
                proposal.get("status", "pending"),
                proposal.get("source", ""),
                preview,
            ),
        )
    summary = inbox_summary(config)
    write_text(
        None,
        "(%d total: %s)\n"
        % (
            summary["total"],
            ", ".join("%s=%d" % (k, v) for k, v in summary["counts"].items() if v),
        ),
    )
    return 0


def _proposal_details_from_args(args):
    details = OrderedDict()
    for key in ("project", "due", "assignee", "priority"):
        value = getattr(args, key, None)
        if value:
            details[key] = value
    tags = getattr(args, "tag", None)
    if tags:
        details["tag"] = tags
    return details


def command_proposal_add(args):
    from .inbox import stage_create

    proposal = stage_create(
        _config(args),
        args.title,
        kind=getattr(args, "kind", "T"),
        details=_proposal_details_from_args(args),
        source=getattr(args, "source", "manual"),
    )
    write_text(None, "Staged proposal %s\n" % proposal["id"])
    return 0


def command_proposal_show(args):
    from .inbox import get_proposal

    proposal = get_proposal(_config(args), args.id)
    if proposal is None:
        sys.stderr.write("ERROR: Unknown proposal %r\n" % args.id)
        return 1
    write_text(None, json.dumps(proposal, ensure_ascii=False, indent=2) + "\n")
    return 0


def command_proposal_edit(args):
    from .inbox import edit_proposal

    try:
        edit_proposal(
            _config(args),
            args.id,
            title=getattr(args, "title", None),
            kind=getattr(args, "kind", None),
            details=_proposal_details_from_args(args),
        )
    except ValueError as exc:
        sys.stderr.write("ERROR: %s\n" % exc)
        return 1
    write_text(None, "Edited proposal %s\n" % args.id)
    return 0


def command_proposal_accept(args):
    from .inbox import batch_apply

    config = _config(args)
    target = _proposal_target(args)
    _ensure_writable_path(target, config, "proposal accept")
    report = batch_apply(config, args.ids, target)
    for result in report["results"]:
        if result.get("applied"):
            write_text(
                None,
                "Accepted %s -> %s\n  %s\n" % (result["id"], target, result["line"]),
            )
        else:
            sys.stderr.write("ERROR: %s: %s\n" % (result["id"], result.get("error")))
    write_text(None, "Applied %d/%d.\n" % (report["applied"], report["total"]))
    return 0 if report["applied"] == report["total"] else 1


def command_proposal_reject(args):
    from .inbox import reject

    try:
        reject(_config(args), args.id)
    except ValueError as exc:
        sys.stderr.write("ERROR: %s\n" % exc)
        return 1
    write_text(None, "Rejected %s\n" % args.id)
    return 0


def command_proposal_defer(args):
    from .inbox import defer

    try:
        defer(_config(args), args.id)
    except ValueError as exc:
        sys.stderr.write("ERROR: %s\n" % exc)
        return 1
    write_text(None, "Deferred %s\n" % args.id)
    return 0


def command_find(args):
    from .global_search import global_search

    items, _diagnostics = _parse_or_exit(
        _normalize_paths(
            getattr(args, "paths", None), _config(args), stdin_when_empty=False
        )
        or ["life.txt"],
        _config(args),
    )
    types = _split_csv_args(getattr(args, "types", None)) or None
    result = global_search(
        items, _config(args), args.term, types=types, limit=getattr(args, "limit", None)
    )
    if getattr(args, "json", False):
        write_text(None, json.dumps(result, ensure_ascii=False, indent=2) + "\n")
        return 0
    if not result["total"]:
        write_text(None, "No matches for %r.\n" % args.term)
        return 0
    write_text(None, "%d match(es) for %r:\n" % (result["total"], args.term))
    for entity, rows in result["groups"].items():
        write_text(None, "%s (%d):\n" % (entity, len(rows)))
        for row in rows:
            location = ""
            if row.get("source") and row.get("line"):
                location = " (%s:%s)" % (row["source"], row["line"])
            write_text(None, "  %-20s %s%s\n" % (row["name"], row["snippet"], location))
    return 0


def _ticket_paths(args):
    return _normalize_paths(
        getattr(args, "paths", None), _config(args), stdin_when_empty=False
    ) or ["life.txt"]


def _ticket_write_file(args, ticket_id=None):
    from .tickets import find_ticket_file

    config = _config(args)
    if ticket_id:
        found = find_ticket_file(
            _ticket_paths(args), ticket_id, key=id_key_from_config(config)
        )
        if found:
            return found
    target = getattr(args, "to", None) or config_write_file(config)
    if not target:
        paths = config_paths(config)
        target = paths[0] if paths else "life.txt"
    return target


def command_ticket_new(args):
    from .tickets import build_ticket_line, next_ticket_id

    config = _config(args)
    key = id_key_from_config(config)
    items, _diags = _parse_or_exit(_ticket_paths(args), config)
    ticket_id = getattr(args, "id", None) or next_ticket_id(items, config)
    line = build_ticket_line(
        config,
        args.subject,
        tracker=args.tracker,
        priority=args.priority,
        severity=args.severity,
        assignee=args.assignee,
        reporter=args.reporter,
        component=args.component,
        version=args.version,
        sprint=args.sprint,
        project=args.project,
        due=args.due,
        est=args.est,
        ticket_status=getattr(args, "status", "new"),
        watchers=getattr(args, "watcher", None),
        ticket_id=ticket_id,
    )
    if getattr(args, "dry_run", False):
        write_text(None, line + "\n")
        return 0
    target = getattr(args, "to", None) or config_write_file(config)
    if not target:
        paths = config_paths(config)
        target = paths[0] if paths else "life.txt"
    _ensure_writable_path(target, config, "ticket new")
    append_line(target, line)
    write_text(None, "Created %s in %s:\n  %s\n" % (ticket_id, target, line))
    return 0


def command_ticket_list(args):
    from .tickets import ticket_list

    config = _config(args)
    items, _diags = _parse_or_exit(_ticket_paths(args), config)
    filters = {}
    for field in (
        "tracker",
        "status",
        "priority",
        "severity",
        "assignee",
        "component",
        "version",
        "sprint",
        "project",
    ):
        value = getattr(args, field, None)
        if value:
            filters["ticket_status" if field == "status" else field] = value
    if getattr(args, "open_only", False):
        filters["open_only"] = True
    rows = ticket_list(items, config, filters, key=id_key_from_config(config))
    if getattr(args, "json", False):
        write_text(None, json.dumps(rows, ensure_ascii=False, indent=2) + "\n")
        return 0
    if not rows:
        write_text(None, "No tickets.\n")
        return 0
    for row in rows:
        write_text(
            None,
            "%-10s %-8s %-10s %-8s %-10s %s\n"
            % (
                row["id"] or "-",
                row["tracker"] or "-",
                row["ticket_status"] or "-",
                row["priority"] or "-",
                row["assignee"] or "-",
                row["title"],
            ),
        )
    return 0


def command_ticket_show(args):
    from .tickets import ticket_view

    config = _config(args)
    key = id_key_from_config(config)
    items, _diags = _parse_or_exit(_ticket_paths(args), config)
    from .tickets import is_ticket, ticket_id_of

    target = None
    for item in items:
        if is_ticket(item) and str(ticket_id_of(item, key)) == args.id:
            target = item
            break
    if target is None:
        sys.stderr.write("ERROR: Ticket %r not found.\n" % args.id)
        return 1
    view = ticket_view(target, config, items, key=key)
    if getattr(args, "json", False):
        write_text(None, json.dumps(view, ensure_ascii=False, indent=2) + "\n")
        return 0
    s = view["summary"]
    write_text(None, "%s  %s\n" % (s["id"], s["title"]))
    write_text(
        None,
        "  tracker=%s status=%s (%s) priority=%s severity=%s\n"
        % (s["tracker"], s["ticket_status"], s["status"], s["priority"], s["severity"]),
    )
    write_text(
        None,
        "  assignee=%s reporter=%s project=%s component=%s version=%s sprint=%s\n"
        % (
            s["assignee"],
            s["reporter"],
            s["project"],
            s["component"],
            s["version"],
            s["sprint"],
        ),
    )
    if s["watchers"]:
        write_text(None, "  watchers: %s\n" % ", ".join(s["watchers"]))
    if view["relations"]:
        write_text(None, "  relations:\n")
        for relation, targets in view["relations"].items():
            write_text(None, "    %s: %s\n" % (relation, ", ".join(targets)))
    if view["incoming_links"]:
        write_text(None, "  referenced by:\n")
        for row in view["incoming_links"]:
            write_text(
                None,
                "    %s <- %s %s\n"
                % (row["relation"], row["source_id"] or "?", row["source_title"]),
            )
    return 0


def _ticket_patch_and_report(
    args, ticket_id, detail_updates, status=None, verb="Updated"
):
    from .tickets import apply_ticket_patch

    config = _config(args)
    key = id_key_from_config(config)
    target = _ticket_write_file(args, ticket_id)
    _ensure_writable_path(target, config, "ticket edit")
    try:
        apply_ticket_patch(target, ticket_id, detail_updates, status=status, key=key)
    except ValueError as exc:
        sys.stderr.write("ERROR: %s\n" % exc)
        return 1
    write_text(None, "%s %s in %s\n" % (verb, ticket_id, target))
    return 0


def command_ticket_edit(args):
    updates = OrderedDict()
    for pair in getattr(args, "set_fields", None) or []:
        if "=" not in pair:
            sys.stderr.write("ERROR: --set expects KEY=VALUE, got %r\n" % pair)
            return 1
        k, v = pair.split("=", 1)
        updates[k.strip()] = v.strip()
    for key in getattr(args, "unset", None) or []:
        updates[key.strip()] = None
    if not updates:
        sys.stderr.write("ERROR: nothing to change; use --set or --unset.\n")
        return 1
    if getattr(args, "dry_run", False):
        write_text(
            None,
            "Would update %s: %s\n"
            % (args.id, json.dumps(updates, ensure_ascii=False)),
        )
        return 0
    return _ticket_patch_and_report(args, args.id, updates, verb="Edited")


def command_ticket_assign(args):
    return _ticket_patch_and_report(
        args, args.id, {"assignee": args.assignee}, verb="Assigned"
    )


def command_ticket_close(args):
    from .tickets import TERMINAL_STATUSES, transition_updates

    status = getattr(args, "status", "closed")
    if status not in TERMINAL_STATUSES:
        sys.stderr.write(
            "ERROR: %r is not a terminal status (%s).\n"
            % (status, ", ".join(TERMINAL_STATUSES))
        )
        return 1
    actor = getattr(args, "by", None) or config_user_name(_config(args))
    updates, life = transition_updates(_config(args), status, actor=actor)
    if getattr(args, "resolution", None):
        updates["resolution"] = args.resolution
    return _ticket_patch_and_report(args, args.id, updates, status=life, verb="Closed")


def command_ticket_reopen(args):
    from .tickets import transition_updates

    status = getattr(args, "status", "new")
    updates, life = transition_updates(_config(args), status)
    updates["closed_by"] = None
    updates["resolution"] = None
    return _ticket_patch_and_report(
        args, args.id, updates, status=life, verb="Reopened"
    )


def _ticket_relation_edit(args, add):
    from .tickets import apply_ticket_patch, is_ticket, ticket_id_of

    config = _config(args)
    key = id_key_from_config(config)
    items, _diags = _parse_or_exit(_ticket_paths(args), config)
    current = None
    for item in items:
        if is_ticket(item) and str(ticket_id_of(item, key)) == args.id:
            current = item
            break
    if current is None:
        sys.stderr.write("ERROR: Ticket %r not found.\n" % args.id)
        return 1
    existing = [str(v) for v in current.details.get(args.relation, [])]
    if add:
        if args.target in existing:
            write_text(
                None, "%s already has %s:%s\n" % (args.id, args.relation, args.target)
            )
            return 0
        new_values = existing + [args.target]
    else:
        if args.target not in existing:
            sys.stderr.write(
                "ERROR: %s has no %s:%s\n" % (args.id, args.relation, args.target)
            )
            return 1
        new_values = [v for v in existing if v != args.target]
    target = _ticket_write_file(args, args.id)
    _ensure_writable_path(target, config, "ticket link")
    apply_ticket_patch(target, args.id, {args.relation: new_values or None}, key=key)
    write_text(
        None,
        "%s %s %s:%s\n"
        % ("Linked" if add else "Unlinked", args.id, args.relation, args.target),
    )
    return 0


def command_ticket_link(args):
    return _ticket_relation_edit(args, add=True)


def command_ticket_unlink(args):
    return _ticket_relation_edit(args, add=False)


def command_ticket_validate(args):
    from .tickets import iter_tickets, validate_ticket

    config = _config(args)
    key = id_key_from_config(config)
    items, _diags = _parse_or_exit(_ticket_paths(args), config)
    rows = []
    for item in iter_tickets(items):
        rows.extend(validate_ticket(item, config, key=key))
    if getattr(args, "json", False):
        write_text(None, json.dumps(rows, ensure_ascii=False, indent=2) + "\n")
        return 0 if not any(r["severity"] == "error" for r in rows) else 1
    if not rows:
        write_text(None, "All tickets are valid.\n")
        return 0
    for row in rows:
        loc = " (%s:%s)" % (row["source"], row["line"]) if row.get("source") else ""
        write_text(
            None,
            "[%s] %s: %s%s\n"
            % (row["severity"].upper(), row["code"], row["message"], loc),
        )
    return 0 if not any(r["severity"] == "error" for r in rows) else 1


def command_config_revision(args):
    """Print the exact revision of the configuration file.

    This is what ``--expected-revision`` compares against, so a script can read
    it, build its change, and write back without racing another writer.
    """
    from .config_writer import config_revision

    config = _config(args)
    target = getattr(args, "output", None) or config.get("_path")
    if not target:
        sys.stderr.write("ERROR: No configuration file to inspect.\n")
        return 1
    write_text(None, "%s\n" % config_revision(target))
    return 0


def command_config_explain(args):
    from .config_registry import explain_key

    entry = explain_key(args.path)
    if entry is None:
        sys.stderr.write("ERROR: No registered metadata for %s\n" % args.path)
        return 1
    write_text(None, "%s\n" % args.path)
    for key, value in entry.items():
        if value is None:
            continue
        label = key.replace("_", " ")
        write_text(None, "  %-16s %s\n" % (label + ":", value))
    return 0


def _config_without_runtime(config, injected_keys=None):
    data = OrderedDict()
    for key, value in (config or {}).items():
        if key in ("_path", "_active_workspace"):
            continue
        if injected_keys and key in injected_keys:
            continue
        data[key] = value
    return data


def _write_config_file(
    path,
    data,
    expected_revision=None,
    dry_run=False,
    require_revision=False,
    audit_log=None,
    audit_max_bytes=None,
):
    from .config_writer import write_config

    return write_config(
        path,
        data,
        expected_revision=expected_revision,
        dry_run=dry_run,
        require_revision=require_revision,
        audit_log=audit_log,
        audit_max_bytes=audit_max_bytes,
    )


def _config_write_section(config):
    config_section_value = config.get("config") if isinstance(config, dict) else None
    config_section_value = (
        config_section_value if isinstance(config_section_value, dict) else {}
    )
    write = config_section_value.get("write")
    return write if isinstance(write, dict) else {}


def _config_write_requires_revision(config):
    return _truthy_config(_config_write_section(config).get("require_revision"))


def _config_write_audit_settings(config):
    write = _config_write_section(config)
    return write.get("audit_log"), write.get("audit_max_bytes")


def _config_write_revision(args, config, target):
    """Expected revision for a config write, or None when CAS cannot apply.

    An explicit ``--expected-revision`` always wins. Otherwise the revision of
    the file that was actually loaded is used, so a concurrent writer between
    load and write is caught rather than silently overwritten. When ``--output``
    names a different file we never read it, so there is nothing to compare
    against and the write proceeds without a precondition.
    """
    explicit = getattr(args, "expected_revision", None)
    if explicit:
        return explicit
    source = (config or {}).get("_path")
    if not source or not target:
        return None
    if os.path.abspath(source) != os.path.abspath(target):
        return None
    from .config_writer import config_revision

    return config_revision(target)


def _commit_config(args, config, target, data):
    """Write configuration under compare-and-set. Returns ``(report, code)``."""
    from .config_writer import ConfigRevisionRequired, StaleConfigRevision

    audit_log, audit_max_bytes = _config_write_audit_settings(config)
    try:
        report = _write_config_file(
            target,
            data,
            _config_write_revision(args, config, target),
            require_revision=_config_write_requires_revision(config),
            audit_log=audit_log,
            audit_max_bytes=audit_max_bytes,
        )
    except ConfigRevisionRequired as exc:
        sys.stderr.write("ERROR: %s\n" % exc)
        return None, 1
    except StaleConfigRevision as exc:
        sys.stderr.write("ERROR: %s\n" % exc)
        if exc.retained:
            sys.stderr.write("Your unwritten change was kept at %s\n" % exc.retained)
        return None, 1
    return report, 0


def _print_config_write_notes(report):
    if not report:
        return
    if report.get("revision"):
        write_text(None, "  revision: %s\n" % report["revision"])
    if report.get("backup"):
        write_text(None, "  backup: %s\n" % report["backup"])
    for row in report.get("warnings") or []:
        location = (" @ %s" % row["path"]) if row.get("path") else ""
        write_text(
            None, "  [WARNING] %s: %s%s\n" % (row["code"], row["message"], location)
        )


def _workspace_diag_line(row):
    return "  [%s] %s: %s" % (row["severity"].upper(), row["code"], row["message"])


def command_workspace_list(args):
    from .workspace import workspace_summaries

    summaries = workspace_summaries(_config(args))
    if getattr(args, "json", False):
        write_text(None, json.dumps(summaries, ensure_ascii=False, indent=2) + "\n")
        return 0
    if not summaries:
        write_text(None, "No workspaces configured.\n")
        return 0
    for summary in summaries:
        marker = "*" if summary["default"] else " "
        tags = []
        if summary["legacy"]:
            tags.append("legacy")
        if not summary["ok"]:
            tags.append("has-errors")
        suffix = (" [%s]" % ", ".join(tags)) if tags else ""
        write_text(
            None,
            "%s %s  (%d source(s), %d file(s)) -> %s%s\n"
            % (
                marker,
                summary["name"],
                summary["source_count"],
                summary["input_count"],
                summary["write_file"] or "(none)",
                suffix,
            ),
        )
    return 0


def command_workspace_show(args):
    from .workspace import resolve_workspace

    try:
        resolution = resolve_workspace(
            _config(args),
            getattr(args, "name", None) or getattr(args, "workspace", None),
        )
    except ValueError as exc:
        sys.stderr.write("ERROR: %s\n" % exc)
        return 1
    if getattr(args, "json", False):
        write_text(None, json.dumps(resolution, ensure_ascii=False, indent=2) + "\n")
        return 0
    write_text(
        None,
        "workspace: %s%s\n"
        % (resolution["name"], " (legacy)" if resolution["legacy"] else ""),
    )
    write_text(None, "base_dir: %s\n" % resolution["base_dir"])
    write_text(None, "write_file: %s\n" % (resolution["write_file"] or "(none)"))
    write_text(None, "sources:\n")
    for record in resolution["sources"]:
        write_text(
            None,
            "  - %s  role=%s writable=%s visible=%s priority=%d\n"
            % (
                record["path"],
                record["role"],
                record["writable"],
                record["default_visible"],
                record["priority"],
            ),
        )
    if resolution["diagnostics"]:
        write_text(None, "diagnostics:\n")
        for row in resolution["diagnostics"]:
            write_text(None, _workspace_diag_line(row) + "\n")
    return 0


def command_workspace_files(args):
    from .workspace import resolve_workspace

    try:
        resolution = resolve_workspace(
            _config(args),
            getattr(args, "name", None) or getattr(args, "workspace", None),
        )
    except ValueError as exc:
        sys.stderr.write("ERROR: %s\n" % exc)
        return 1
    from .workspace import source_reason

    rows = []
    for record in resolution["sources"]:
        reason = source_reason(record)
        for path in record["files"]:
            rows.append(
                OrderedDict(
                    (
                        ("path", path),
                        ("role", record["role"]),
                        ("mode", "rw" if record["writable"] else "ro"),
                        ("origin", record["path"]),
                        ("matched_glob", record["matched_glob"]),
                        ("reason", reason),
                        ("exists", os.path.exists(path)),
                    )
                )
            )
    if getattr(args, "json", False):
        write_text(None, json.dumps(rows, ensure_ascii=False, indent=2) + "\n")
        return 0
    if getattr(args, "resolved", False):
        for row in rows:
            write_text(
                None,
                "%s  role=%s mode=%s origin=%s exists=%s reason=(%s)\n"
                % (
                    row["path"],
                    row["role"],
                    row["mode"],
                    row["origin"],
                    row["exists"],
                    row["reason"],
                ),
            )
    else:
        for row in rows:
            write_text(None, "%s\n" % row["path"])
    return 0


def command_workspace_validate(args):
    from .workspace import resolve_workspace, iter_workspace_definitions

    config = _config(args)
    if getattr(args, "all", False):
        names = list(iter_workspace_definitions(config).keys())
    else:
        names = [getattr(args, "name", None) or getattr(args, "workspace", None)]
    reports = []
    overall_ok = True
    for name in names:
        try:
            resolution = resolve_workspace(config, name)
        except ValueError as exc:
            sys.stderr.write("ERROR: %s\n" % exc)
            return 1
        overall_ok = overall_ok and resolution["ok"]
        reports.append(resolution)
    if getattr(args, "json", False):
        payload = [
            OrderedDict(
                (
                    ("name", r["name"]),
                    ("ok", r["ok"]),
                    ("diagnostics", r["diagnostics"]),
                )
            )
            for r in reports
        ]
        write_text(None, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
        return 0 if overall_ok else 1
    for resolution in reports:
        status = "OK" if resolution["ok"] else "ERRORS"
        write_text(None, "workspace %s: %s\n" % (resolution["name"], status))
        for row in resolution["diagnostics"]:
            write_text(None, _workspace_diag_line(row) + "\n")
    return 0 if overall_ok else 1


def command_tui(args):
    args.paths = _normalize_paths(
        args.paths, _config(args), stdin_when_empty=False
    ) or ["life.txt"]
    from .tui import cmd_tui

    return cmd_tui(args)


def command_fzf(args):
    args.paths = _normalize_paths(
        args.paths, _config(args), stdin_when_empty=False
    ) or ["life.txt"]
    from .fzf_helper import cmd_fzf

    return cmd_fzf(args)


def command_timer(args):
    config = _config(args)
    if getattr(args, "timer_command", None) == "summary":
        args.paths = _normalize_paths(args.paths, config, stdin_when_empty=False)
    elif getattr(args, "timer_command", None) == "status" and getattr(
        args, "paths", None
    ):
        args.paths = _normalize_paths(args.paths, config, stdin_when_empty=False)
    from .timer import cmd_timer

    return cmd_timer(args)


def command_stats(args):
    args.paths = _normalize_paths(
        args.paths, _config(args), stdin_when_empty=False
    ) or ["life.txt"]
    args.filter_items_func = _filter_items_from_args
    from .stats import cmd_stats

    return cmd_stats(args)


def command_git_hook(args):
    from .git_hook import cmd_git_hook

    return cmd_git_hook(args)


def command_completion(args):
    from .completion import cmd_completion

    return cmd_completion(args)


def command_assist_update(args):
    if args.interactive:
        raise ValueError("--interactive is not supported with --update.")
    if args.append:
        raise ValueError(
            "--append is only for creating new items. Use --output for update copies."
        )
    if not has_update_fields(args):
        raise ValueError("No update fields were specified.")

    text = read_text(args.update)
    updated_text, updated_line, diagnostics = update_text(text, args)
    if _has_error(diagnostics):
        _print_diagnostics(diagnostics)
        return 1
    if not args.no_check:
        _print_warnings(diagnostics)

    output = args.output if args.output else args.update
    _ensure_writable_path(output, _config(args), "assist --update")
    write_text(output, updated_text)
    write_text(None, updated_line + "\n")
    return 0


def _write_life_items(items, output, canonical=False, key="id"):
    text = _validated_life_text_or_exit(items, canonical=canonical, key=key)
    if text is None:
        return 1
    write_text(output, text)
    return 0


def _validated_life_text_or_exit(items, canonical=False, key="id"):
    if canonical:
        items = _canonical_hierarchy_items(items, key=key)
    diagnostics = []
    lines = []
    for item in items:
        diagnostics.extend(validate_item(item))
        lines.append(item_to_line(item))
    if _has_error(diagnostics):
        _print_diagnostics(diagnostics)
        return None
    _print_warnings(diagnostics)
    text = "\n".join(lines)
    if text:
        text += "\n"
    return text


def _items_to_life_text(items, canonical=False, key="id"):
    if canonical:
        items = _canonical_hierarchy_items(items, key=key)
    lines = []
    for item in items:
        if canonical:
            lines.append(item_to_line(item))
        else:
            lines.append(getattr(item, "source_text", None) or item_to_line(item))
    text = "\n".join(lines)
    if text:
        text += "\n"
    return text


def _canonical_hierarchy_items(items, key="id"):
    """Return item copies with explicit parent: links and no indentation."""
    canonical = []
    stack = []
    for item in items:
        cloned = _copy_item(item)
        indent = int(getattr(item, "indent", 0) or 0)
        while stack and stack[-1][0] >= indent:
            stack.pop()

        if indent > 0 and not cloned.details.get("parent") and stack:
            parent = stack[-1][1]
            parent_ids = parent.details.get(key, [])
            if parent_ids:
                cloned.details.setdefault("parent", []).append(parent_ids[0])

        cloned.indent = 0
        canonical.append(cloned)
        stack.append((indent, cloned))
    return canonical


def _copy_item(item):
    cloned = Item(
        item.status,
        item.kind,
        item.title,
        OrderedDict((key, list(values)) for key, values in item.details.items()),
        line=item.line,
        source_text=getattr(item, "source_text", None),
        source=getattr(item, "source", None),
        indent=getattr(item, "indent", 0),
    )
    if hasattr(item, "end_line"):
        cloned.end_line = item.end_line
    return cloned


def format_id_audit(audit, only="all"):
    lines = []
    cross_file_count = audit.get("cross_file_duplicate_count", 0)
    cross_file_note = (", %d cross-file" % cross_file_count) if cross_file_count else ""
    lines.append(
        "ID audit (%s): %d item(s), %d id(s), %d duplicate id(s)%s, %d missing id item(s)"
        % (
            audit.get("key", "id"),
            audit.get("total_items", 0),
            audit.get("id_count", 0),
            audit.get("duplicate_count", 0),
            cross_file_note,
            audit.get("missing_count", 0),
        )
    )

    if only in ("all", "duplicates"):
        lines.append("")
        lines.extend(_format_id_duplicate_section(audit.get("duplicates", [])))

    if only in ("all", "missing"):
        lines.append("")
        lines.extend(_format_id_missing_section(audit.get("missing", [])))

    if only == "present":
        lines.append("")
        lines.extend(_format_id_present_section(audit.get("present", [])))

    return "\n".join(lines).rstrip() + "\n"


def assign_missing_ids(paths, config, key, dry_run=False, backup=False, prefix=None):
    normalized = _normalize_paths(paths, config)
    if any(path == "-" for path in normalized):
        raise ValueError("ids --assign requires real file paths, not stdin.")

    existing = set()
    parsed_by_path = []
    for path in normalized:
        text = read_text(path)
        items, diagnostics = parse_text(text)
        if _has_error(diagnostics):
            raise ValueError(
                "Cannot assign IDs because %s has validation errors." % path
            )
        parsed_by_path.append((path, text, items))
        existing.update(collect_item_ids(items, key=key))

    records = []
    for path, text, _items in parsed_by_path:
        changed, new_text, path_records = _assign_missing_ids_in_text(
            path,
            text,
            key,
            existing,
            config,
            prefix,
        )
        records.extend(path_records)
        if changed and not dry_run:
            if backup:
                write_text(path + ".bak", text)
            write_text(path, new_text)
    return records


def _assign_missing_ids_in_text(path, text, key, existing, config, prefix=None):
    raw_lines = text.splitlines(True)
    changed = False
    records = []
    new_lines = []
    for line_no, raw_line in enumerate(raw_lines, 1):
        body, ending = split_line_ending(raw_line)
        item, diagnostics = parse_line(body, line_no)
        if item is None or _has_error(diagnostics) or item.details.get(key):
            new_lines.append(raw_line)
            continue
        assigned = ensure_item_id(
            item,
            existing_ids=existing,
            key=key,
            prefix=prefix or id_prefix_for_item(item, config),
        )
        new_line = item_to_line(item) + ending
        new_lines.append(new_line)
        changed = True
        records.append(
            OrderedDict(
                [
                    ("path", path),
                    ("line", line_no),
                    ("id", assigned),
                    ("type", item.kind),
                    ("status", item.status),
                    ("title", item.title),
                    ("text", item_to_line(item)),
                ]
            )
        )
    if not raw_lines and text:
        new_lines.append(text)
    return changed, "".join(new_lines), records


def format_id_assignments(records, dry_run=False):
    heading = "Planned ID assignments" if dry_run else "ID assignments"
    lines = ["%s: %d item(s)" % (heading, len(records))]
    if not records:
        return lines[0] + "\n"
    rows = []
    for record in records:
        rows.append(
            OrderedDict(
                [
                    ("path", record["path"]),
                    ("line", str(record["line"])),
                    ("id", record["id"]),
                    ("type", record["type"]),
                    ("title", record["title"]),
                ]
            )
        )
    lines.extend(_format_table(rows, ("path", "line", "id", "type", "title")))
    return "\n".join(lines) + "\n"


def _format_id_duplicate_section(records):
    lines = ["Duplicate IDs:"]
    if not records:
        lines.append("No duplicate IDs.")
        return lines
    rows = []
    for record in records:
        cross_marker = "*" if record.get("cross_file") else ""
        rows.append(
            OrderedDict(
                [
                    ("id", record["id"] + cross_marker),
                    ("count", str(record["count"])),
                    (
                        "locations",
                        "; ".join(item["location"] for item in record["items"]),
                    ),
                    ("titles", "; ".join(item["title"] for item in record["items"])),
                ]
            )
        )
    result = lines + _format_table(rows, ("id", "count", "locations", "titles"))
    if any(r.get("cross_file") for r in records):
        result.append("* = duplicate spans multiple files")
    return result


def _format_id_missing_section(records):
    lines = ["Missing IDs:"]
    if not records:
        lines.append("No missing IDs.")
        return lines
    rows = []
    for item in records:
        rows.append(
            OrderedDict(
                [
                    ("location", item["location"]),
                    ("type", item["type"]),
                    ("status", item["status"]),
                    ("title", item["title"]),
                ]
            )
        )
    return lines + _format_table(rows, ("location", "type", "status", "title"))


def _format_id_present_section(records):
    lines = ["Present IDs:"]
    if not records:
        lines.append("No IDs found.")
        return lines
    rows = []
    for record in records:
        rows.append(
            OrderedDict(
                [
                    ("id", record["id"]),
                    ("count", str(record["count"])),
                    (
                        "locations",
                        "; ".join(item["location"] for item in record["items"]),
                    ),
                ]
            )
        )
    return lines + _format_table(rows, ("id", "count", "locations"))


def _format_table(rows, columns):
    widths = []
    for column in columns:
        width = len(column)
        for row in rows:
            width = max(width, len(str(row.get(column, ""))))
        widths.append(width)
    lines = []
    lines.append(_format_table_row(columns, widths))
    lines.append(_format_table_row(["-" * width for width in widths], widths))
    for row in rows:
        lines.append(
            _format_table_row([row.get(column, "") for column in columns], widths)
        )
    return lines


def _format_table_row(values, widths):
    cells = []
    for index, value in enumerate(values):
        cells.append(str(value).ljust(widths[index]))
    return "| " + " | ".join(cells) + " |"


def _id_audit_output(audit, only):
    if only == "all":
        return audit
    data = OrderedDict()
    for key in (
        "key",
        "total_items",
        "id_count",
        "duplicate_count",
        "cross_file_duplicate_count",
        "missing_count",
    ):
        if key in audit:
            data[key] = audit[key]
    data[only] = audit[only]
    return data


def _id_audit_jsonl_records(audit, only):
    records = []
    if only == "all":
        records.append(
            OrderedDict(
                [
                    ("kind", "summary"),
                    ("key", audit["key"]),
                    ("total_items", audit["total_items"]),
                    ("id_count", audit["id_count"]),
                    ("duplicate_count", audit["duplicate_count"]),
                    (
                        "cross_file_duplicate_count",
                        audit.get("cross_file_duplicate_count", 0),
                    ),
                    ("missing_count", audit["missing_count"]),
                ]
            )
        )
    if only in ("all", "duplicates"):
        for record in audit["duplicates"]:
            entry = OrderedDict(record)
            entry["kind"] = "duplicate"
            records.append(entry)
    if only in ("all", "missing"):
        for item in audit["missing"]:
            entry = OrderedDict(item)
            entry["kind"] = "missing"
            records.append(entry)
    if only == "present":
        for record in audit["present"]:
            entry = OrderedDict(record)
            entry["kind"] = "present"
            records.append(entry)
    return records


def source_ownership_records(paths, config=None, key="id"):
    normalized = _normalize_paths(paths, config)
    records = []
    items = []
    diagnostics = []
    for source_index, path in enumerate(normalized, 1):
        source = "stdin" if path == "-" else path
        text = read_text(path)
        path_items, path_diagnostics = parse_text(
            text,
            id_key=key,
            check_ids=False,
            check_references=False,
        )
        _set_source(path_items, path_diagnostics, source)
        items.extend(path_items)
        diagnostics.extend(path_diagnostics)
        for item in path_items:
            records.append(_source_ownership_record(item, source, source_index, key))
    diagnostics.extend(duplicate_id_diagnostics(items, key=key))
    diagnostics.extend(reference_diagnostics(items, key=key))
    return records, diagnostics


def _source_ownership_record(item, source, source_index, key):
    id_values = [str(value) for value in item.details.get(key, []) if value]
    parent_values = [str(value) for value in item.details.get("parent", []) if value]
    record = OrderedDict()
    record["source"] = source
    record["source_index"] = source_index
    record["line"] = item.line
    record["end_line"] = getattr(item, "end_line", item.line) or item.line
    record["id_key"] = key
    record["id"] = id_values[0] if id_values else ""
    record["ids"] = id_values
    record["parent"] = parent_values[0] if parent_values else ""
    record["status"] = item.status
    record["type"] = item.kind
    record["title"] = item.title
    record["indent"] = item.indent
    record["detail_count"] = sum(len(values) for values in item.details.values())
    return record


def format_source_ownership_table(records, key):
    lines = [
        "Source ownership (%s): %d item(s) across %d source(s)"
        % (key, len(records), len(set(record["source"] for record in records)))
    ]
    if not records:
        return lines[0] + "\n"

    rows = []
    for record in records:
        line_value = str(record["line"])
        if record.get("end_line") and record["end_line"] != record["line"]:
            line_value = "%s-%s" % (record["line"], record["end_line"])
        rows.append(
            OrderedDict(
                [
                    ("source", record["source"]),
                    ("line", line_value),
                    ("id", record["id"]),
                    ("parent", record["parent"]),
                    ("type", record["type"]),
                    ("status", record["status"]),
                    ("title", record["title"]),
                ]
            )
        )
    lines.extend(
        _format_table(
            rows, ("source", "line", "id", "parent", "type", "status", "title")
        )
    )
    return "\n".join(lines) + "\n"


def _completed_parent_diagnostics(items, key="id"):
    """W225: completed/canceled parent has open children."""
    diagnostics = []
    _open_statuses = frozenset(("[ ]", "[/]", "[>]", "[?]"))
    _closed_statuses = frozenset(("[x]", "[-]"))

    id_to_item = {}
    for item in items:
        for val in item.details.get(key, []):
            id_to_item[str(val)] = item

    children_by_parent = {}
    for item in items:
        for parent_id in item.details.get("parent", []):
            pid = str(parent_id)
            children_by_parent.setdefault(pid, []).append(item)

    for parent_id, children in children_by_parent.items():
        parent = id_to_item.get(parent_id)
        if parent is None or parent.status not in _closed_statuses:
            continue
        open_children = [c for c in children if c.status in _open_statuses]
        if not open_children:
            continue
        child_ids = (
            ", ".join(str(v) for c in open_children for v in c.details.get(key, []))
            or "(no id)"
        )
        diagnostics.append(
            Diagnostic(
                "warning",
                "W225",
                "Completed/canceled parent %s:%s has %d open child(ren): %s."
                % (key, parent_id, len(open_children), child_ids),
                parent.line,
            )
        )
    return diagnostics


def _parse_or_exit(paths, config=None):
    items, diagnostics = _parse_life_inputs(paths, config)
    if _has_error(diagnostics):
        _print_diagnostics(diagnostics)
        raise SystemExit(1)
    return items, diagnostics


def _parse_life_inputs(paths, config=None):
    normalized = _normalize_paths(paths, config)
    include_source = len(normalized) > 1
    id_key = id_key_from_config(config or {})
    items = []
    diagnostics = []
    for path in normalized:
        text = read_text(path)
        path_items, path_diagnostics = parse_text(
            text,
            id_key=id_key,
            check_ids=False,
            check_references=False,
        )
        if include_source or path != "-":
            source = "stdin" if path == "-" else path
            _set_source(path_items, path_diagnostics, source)
        items.extend(path_items)
        diagnostics.extend(path_diagnostics)
    diagnostics.extend(duplicate_id_diagnostics(items, key=id_key))
    diagnostics.extend(reference_diagnostics(items, key=id_key))
    diagnostics.extend(_completed_parent_diagnostics(items, key=id_key))
    return items, diagnostics


def _set_source(items, diagnostics, source):
    for item in items:
        item.source = source
    for diagnostic in diagnostics:
        diagnostic.source = source


def _filter_items_from_args(items, args):
    range_start, range_end = parse_optional_time_range(
        after_text=getattr(args, "after", None),
        before_text=getattr(args, "before", None),
    )
    config = _config(args)
    return filter_items(
        items,
        open_only=getattr(args, "open", False),
        statuses=getattr(args, "status", None),
        kinds=getattr(args, "kinds", None),
        projects=getattr(args, "project", None),
        tags=getattr(args, "tag", None),
        tag_all=getattr(args, "tag_all", None),
        exclude_tags=getattr(args, "exclude_tag", None),
        users=getattr(args, "user", None),
        persons=getattr(args, "person", None),
        owners=getattr(args, "owner", None),
        assignees=getattr(args, "assignee", None),
        attendees=getattr(args, "attendee", None),
        senders=getattr(args, "sender", None),
        recipients=getattr(args, "recipient", None),
        teams=getattr(args, "team", None),
        detail_filters=getattr(args, "detail", None),
        text=getattr(args, "text", None),
        range_start=range_start,
        range_end=range_end,
        user_aliases=config_user_aliases(config),
        team_members=config_team_members(config),
        team_aliases=config_team_aliases(config),
        tag_aliases=config_tag_aliases(config),
    )


def apply_config_defaults_to_item(item, args, directives=None):
    config = _config(args)
    directives = directives or {}

    if item.kind == "S" and "person" not in item.details:
        defaults = config_section(config, "defaults")
        user_section = config_section(config, "user")
        message_section = config_section(config, "message")
        configured_person = (
            defaults.get("person")
            or user_section.get("name")
            or message_section.get("default_sender")
        )
        person = configured_person or directives.get("self") or "self"
        item.details["person"] = [str(person)]

    if "project" not in item.details:
        defaults = config_section(config, "defaults")
        project = defaults.get("project") or directives.get("project")
        if project:
            item.details["project"] = [str(project)]

    if item.kind == "M":
        message = config_section(config, "message")
        sender = message.get("default_sender") or config_user_name(config)
        if sender and "sender" not in item.details:
            item.details["sender"] = [str(sender)]

        channel = message.get("default_channel")
        if channel and "channel" not in item.details:
            item.details["channel"] = [str(channel)]

        service = message.get("default_service")
        if service and "service" not in item.details:
            item.details["service"] = [str(service)]


def apply_auto_id_to_item(item, args):
    config = _config(args)
    if not auto_ids_enabled(config):
        return None

    key = id_key_from_config(config)
    if item.details.get(key):
        return item.details[key][0]

    existing = collect_item_ids(_auto_id_scan_items(args), key=key)
    return ensure_item_id(
        item,
        existing_ids=existing,
        key=key,
        prefix=id_prefix_for_item(item, config),
    )


def _auto_id_scan_items(args):
    items = []
    for path in _auto_id_scan_paths(args):
        if not path or path == "-" or not os.path.exists(path):
            continue
        path_items, _diagnostics = parse_text(read_text(path))
        items.extend(path_items)
    return items


def _auto_id_scan_paths(args):
    config = _config(args)
    candidates = []
    for path in config_paths(config) or []:
        candidates.append(path)
    write_file = config_write_file(config)
    if write_file:
        candidates.append(write_file)
    output = getattr(args, "output", None)
    append = getattr(args, "append", None)
    if output:
        candidates.append(output)
    if append:
        candidates.append(append)

    paths = []
    seen = set()
    for path in candidates:
        key = os.path.abspath(path) if path not in (None, "-") else path
        if key in seen:
            continue
        seen.add(key)
        paths.append(path)
    return expand_paths(paths, stdin_when_empty=False)


def _config(args):
    return getattr(args, "config_data", None) or {}


def _workspace_resolution_active(config, workspace_name):
    from .workspace import workspace_resolution_active

    return workspace_resolution_active(config, workspace_name)


def _maybe_apply_workspace(args):
    """Inject resolved workspace inputs/write target into the loaded config.

    Legacy top-level ``paths`` / ``write_file`` configurations are left byte
    identical: resolution only activates when a workspace is requested with
    ``--workspace`` or the config declares ``workspaces`` / ``default_workspace``.
    Downstream ``config_paths`` / ``config_write_file`` then transparently see
    the resolved sources without every command needing to change.

    The keys this function actually overwrites or adds are recorded on
    ``args._workspace_injected_keys`` so a later configuration *write* (
    ``config set|unset|migrate``) can exclude them: they are resolution
    output, not user-declared content, and must never be persisted back to
    the file (#136).
    """
    config = getattr(args, "config_data", None)
    workspace_name = getattr(args, "workspace", None)
    if not config or not _workspace_resolution_active(config, workspace_name):
        return
    from .workspace import resolve_workspace

    resolution = resolve_workspace(config, workspace_name or None)
    injected_keys = set()
    config["paths"] = list(resolution["input_paths"])
    injected_keys.add("paths")
    if resolution["write_file"]:
        config["write_file"] = resolution["write_file"]
        injected_keys.add("write_file")
    if resolution["generated_paths"] and "generated_paths" not in config:
        config["generated_paths"] = list(resolution["generated_paths"])
        injected_keys.add("generated_paths")
    config["_active_workspace"] = resolution["name"]
    args._workspace_injected_keys = injected_keys


def _config_generated_paths(config):
    values = []
    if config:
        raw = config.get("generated_paths")
        if isinstance(raw, str):
            values.append(raw)
        elif isinstance(raw, (list, tuple)):
            values.extend(str(value) for value in raw if str(value))
        sync_raw = config_section(config, "sync_ics").get("generated_paths")
        if isinstance(sync_raw, str):
            values.append(sync_raw)
        elif isinstance(sync_raw, (list, tuple)):
            values.extend(str(value) for value in sync_raw if str(value))
    return values


def _ensure_writable_path(path, config, operation, allow_generated=False):
    if not path or path == "-":
        return
    abs_path = os.path.abspath(path)
    if not allow_generated and _path_matches_config_patterns(
        abs_path, _config_generated_paths(config), config
    ):
        raise ValueError("%s refuses to modify generated file: %s" % (operation, path))
    if os.path.exists(path):
        import stat

        mode = os.stat(path).st_mode
        if not (mode & stat.S_IWRITE):
            raise ValueError(
                "%s refuses to modify read-only file: %s" % (operation, path)
            )
        if not os.access(path, os.W_OK):
            raise ValueError(
                "%s refuses to modify non-writable file: %s" % (operation, path)
            )


def _path_matches_config_patterns(abs_path, patterns, config):
    if not patterns:
        return False
    import fnmatch

    bases = [os.getcwd()]
    config_path = config.get("_path") if config else None
    if config_path:
        bases.insert(0, os.path.dirname(os.path.abspath(config_path)) or os.getcwd())
    target = os.path.normcase(abs_path)
    for pattern in patterns:
        candidates = []
        if os.path.isabs(pattern):
            candidates.append(os.path.abspath(pattern))
        else:
            for base in bases:
                candidates.append(os.path.abspath(os.path.join(base, pattern)))
        for candidate in candidates:
            normalized = os.path.normcase(candidate)
            if target == normalized or fnmatch.fnmatch(target, normalized):
                return True
    return False


def _sync_config(args):
    return config_section(_config(args), "sync_ics")


def _public_config(config):
    if isinstance(config, dict):
        data = {}
        for key, value in config.items():
            if key == "_path":
                continue
            data[key] = _public_config(value)
        return data
    if isinstance(config, list):
        return [_public_config(value) for value in config]
    return config


def _items_from_json_paths(paths):
    items = []
    for path in _normalize_paths(paths):
        items.extend(items_from_json_text(read_text(path)))
    return items


def _items_from_jsonl_paths(paths):
    items = []
    for path in _normalize_paths(paths):
        items.extend(items_from_jsonl_text(read_text(path)))
    return items


def _items_from_csv_paths(paths):
    items = []
    for path in _normalize_paths(paths):
        items.extend(items_from_csv_text(read_text(path)))
    return items


def _normalize_paths(paths, config=None, stdin_when_empty=True):
    if paths is None:
        configured = config_paths(config)
        if configured:
            return expand_paths(configured, stdin_when_empty=stdin_when_empty)
        return ["-"] if stdin_when_empty else []
    if isinstance(paths, str):
        return expand_paths([paths], stdin_when_empty=stdin_when_empty)
    paths = list(paths)
    if not paths:
        configured = config_paths(config)
        if configured:
            return expand_paths(configured, stdin_when_empty=stdin_when_empty)
        return ["-"] if stdin_when_empty else []
    return expand_paths(paths, stdin_when_empty=stdin_when_empty)


def read_text(path):
    if path is None or path == "-":
        return sys.stdin.read()
    with open(path, "r", encoding="utf-8-sig") as handle:
        return handle.read()


def write_text(path, text):
    if path is None:
        sys.stdout.write(text)
        return
    atomic_write_text(path, text)


def atomic_write_text(path, text):
    ensure_parent_dir(path)
    _shared_atomic_write_text(path, text)


def write_bytes(path, data):
    ensure_parent_dir(path)
    _shared_atomic_write_bytes(path, data)


def ensure_parent_dir(path):
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)


def append_line(path, line):
    append_text(path, line + "\n")


def append_text(path, text):
    if not text:
        return
    from .write_operations import append_text as semantic_append_text

    return semantic_append_text(path, text, operation="cli.append", create=True)


def _undo_cache_dir(config):
    undo_cfg = config_section(config, "undo")
    return undo_cfg.get("dir") or os.path.join(".cache", "lifetxt", "undo")


def _backup_cache_dir(config):
    backup_cfg = config_section(config, "backup")
    return backup_cfg.get("dir") or os.path.join(".cache", "lifetxt", "backup")


def _undo_keep(config):
    undo_cfg = config_section(config, "undo")
    keep = undo_cfg.get("keep", 20)
    try:
        return max(1, int(keep))
    except (TypeError, ValueError):
        return 20


def _evict_old_snapshots(directory, keep=20):
    try:
        entries = sorted(os.listdir(directory))
        excess = entries[: max(0, len(entries) - keep)]
        for name in excess:
            try:
                os.unlink(os.path.join(directory, name))
            except OSError:
                pass
    except OSError:
        pass


def _pre_write_backup(path, config, op):
    """Save current file content as an undo snapshot before a write operation."""
    if not path or path == "-":
        return
    try:
        content = read_text(path)
    except FileNotFoundError:
        return

    ts = local_now_naive().strftime("%Y%m%d_%H%M%S")
    basename = os.path.basename(path)

    undo_root = _undo_cache_dir(config)
    undo_dir = os.path.join(undo_root, basename)
    snapshot_name = "%s.%s.txt" % (ts, op)
    snapshot_path = os.path.join(undo_dir, snapshot_name)
    try:
        ensure_parent_dir(snapshot_path)
        with open(snapshot_path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(content)
        _evict_old_snapshots(undo_dir, keep=_undo_keep(config))
    except OSError:
        pass

    backup_cfg = config_section(config, "backup")
    if backup_cfg.get("auto"):
        backup_root = _backup_cache_dir(config)
        backup_dir = os.path.join(backup_root, basename)
        backup_path = os.path.join(backup_dir, "%s.txt" % ts)
        try:
            ensure_parent_dir(backup_path)
            with open(backup_path, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(content)
            keep_b = backup_cfg.get("keep", 20)
            try:
                keep_b = max(1, int(keep_b))
            except (TypeError, ValueError):
                keep_b = 20
            _evict_old_snapshots(backup_dir, keep=keep_b)
        except OSError:
            pass


def split_line_ending(line):
    if line.endswith("\r\n"):
        return line[:-2], "\r\n"
    if line.endswith("\n"):
        return line[:-1], "\n"
    if line.endswith("\r"):
        return line[:-1], "\r"
    return line, ""


def fetch_url(url, timeout, user_agent, index):
    request = Request(url, headers={"User-Agent": user_agent})
    try:
        with urlopen(request, timeout=timeout) as response:
            return response.read()
    except HTTPError as exc:
        raise ValueError(
            "Failed to fetch iCalendar source #%d: HTTP %s." % (index, exc.code)
        )
    except URLError as exc:
        raise ValueError(
            "Failed to fetch iCalendar source #%d: %s." % (index, exc.reason)
        )
    except OSError as exc:
        raise ValueError("Failed to fetch iCalendar source #%d: %s." % (index, exc))


def decode_ics_bytes(data):
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        return data.decode("utf-8", errors="replace")


def _ics_sync_sources(args):
    sources = []
    for url in args.url:
        sources.append({"kind": "url", "name": "url", "url": url})
    for env_name in args.url_env:
        url = os.environ.get(env_name)
        if not url:
            raise ValueError("Environment variable %s is not set or empty." % env_name)
        sources.append({"kind": "env", "name": env_name, "url": url})
    for source in _sync_config(args).get("sources", []) or []:
        if not isinstance(source, dict):
            raise ValueError("sync_ics.sources entries must be objects.")
        url = source.get("url")
        kind = "url"
        name = source.get("name") or "config"
        if not url and source.get("url_env"):
            env_name = source.get("url_env")
            url = os.environ.get(env_name)
            kind = "env"
            name = env_name
            if not url:
                raise ValueError(
                    "Environment variable %s is not set or empty." % env_name
                )
        if not url:
            raise ValueError("sync_ics.sources entry requires url or url_env.")
        tags = source.get("tags", source.get("tag", []))
        if isinstance(tags, str):
            tags = [tags]
        sources.append(
            {
                "kind": kind,
                "name": name,
                "url": url,
                "project": source.get("project"),
                "tags": tags,
            }
        )
    if not sources:
        raise ValueError("Specify at least one --url or --url-env.")
    return sources


def _ics_cache_name(source, index):
    digest = hashlib.sha256(source["url"].encode("utf-8")).hexdigest()[:12]
    if source["kind"] == "env":
        base = _safe_cache_part(source["name"])
    else:
        base = "source_%d" % index
    return "%s_%s.ics" % (base, digest)


def _safe_cache_part(value):
    chars = []
    for char in value:
        if char.isalnum() or char in ("-", "_"):
            chars.append(char)
        else:
            chars.append("_")
    return "".join(chars) or "source"


def _exit_code(diagnostics, warnings_as_errors):
    has_warning = False
    for diagnostic in diagnostics:
        if diagnostic.severity == "error":
            return 1
        if diagnostic.severity == "warning":
            has_warning = True
    if warnings_as_errors and has_warning:
        return 1
    return 0


def filter_diagnostics(
    diagnostics, severities=None, codes=None, categories=None, ignore_codes=None
):
    severity_filter = _diagnostic_severity_filter(severities)
    code_filter = _diagnostic_code_filter(codes)
    category_filter = _diagnostic_category_filter(categories)
    ignore_set = set(c.upper() for c in _split_csv_args(ignore_codes))

    filtered = []
    for diagnostic in diagnostics:
        if ignore_set and str(diagnostic.code).upper() in ignore_set:
            continue
        if severity_filter and str(diagnostic.severity).lower() not in severity_filter:
            continue
        if code_filter and str(diagnostic.code).upper() not in code_filter:
            continue
        if category_filter and diagnostic_category(diagnostic) not in category_filter:
            continue
        filtered.append(diagnostic)
    return filtered


def _diagnostic_severity_filter(values):
    severities = set(value.lower() for value in _split_csv_args(values))
    allowed = set(("error", "warning"))
    invalid = sorted(severities - allowed)
    if invalid:
        raise ValueError("Unknown diagnostic severity: %s." % ", ".join(invalid))
    return severities


def _diagnostic_code_filter(values):
    return set(value.upper() for value in _split_csv_args(values))


def _diagnostic_category_filter(values):
    categories = set(value.lower() for value in _split_csv_args(values))
    allowed = set(DIAGNOSTIC_CATEGORIES)
    invalid = sorted(categories - allowed)
    if invalid:
        raise ValueError("Unknown diagnostic category: %s." % ", ".join(invalid))
    return categories


def _has_error(diagnostics):
    for diagnostic in diagnostics:
        if diagnostic.severity == "error":
            return True
    return False


def _print_diagnostics(diagnostics):
    for diagnostic in diagnostics:
        sys.stderr.write(diagnostic.format() + "\n")


def _print_warnings(diagnostics):
    for diagnostic in diagnostics:
        if diagnostic.severity == "warning":
            sys.stderr.write(diagnostic.format() + "\n")


def command_deps(args):
    config = _config(args)
    id_key = id_key_from_config(config)
    paths = args.paths if args.paths else ["-"]
    items, diags = _parse_or_exit(paths, config)
    _print_warnings(diags)
    roots = dependency_chain_records(
        items,
        key=id_key,
        root_id=getattr(args, "root", None),
        blocked_only=getattr(args, "blocked", False),
        max_depth=getattr(args, "depth", None),
    )

    if args.format == "json":
        write_text(
            None,
            json.dumps(
                roots,
                ensure_ascii=False,
                indent=2 if args.pretty else None,
                separators=None if args.pretty else (",", ":"),
            )
            + "\n",
        )
        return 0

    if args.format == "mermaid":
        write_text(None, dependency_chains_to_mermaid(roots))
        return 0

    if args.format == "dot":
        write_text(None, dependency_chains_to_dot(roots))
        return 0

    write_text(None, format_dependency_chain(roots))
    return 0


def command_tag_list(args):
    config = _config(args)
    paths = args.paths if args.paths else ["-"]
    items, diags = _parse_or_exit(paths, config)
    _print_warnings(diags)
    counts = {}
    for item in items:
        for tag in item.details.get("tag", []):
            counts[tag] = counts.get(tag, 0) + 1
    sorted_tags = sorted(counts.items(), key=lambda x: (-x[1], x[0]))
    fmt = getattr(args, "format", "text")
    if fmt == "json":
        write_text(
            None,
            json.dumps(
                [{"tag": t, "count": c} for t, c in sorted_tags],
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
        )
    else:
        if not sorted_tags:
            sys.stdout.write("No tags found.\n")
        else:
            for tag, count in sorted_tags:
                sys.stdout.write("%4d  %s\n" % (count, tag))
    return 0


def command_tag_rename(args):
    old_tag = args.old
    new_tag = args.new
    path = args.path
    dry_run = getattr(args, "dry_run", False)
    text = read_text(path)
    id_key = id_key_from_config(_config(args))
    items, _ = parse_text(text, id_key=id_key, check_ids=False, check_references=False)
    lines = text.splitlines(keepends=True)
    changed = 0
    import re as _re

    for item in items:
        if old_tag in item.details.get("tag", []):
            ln = item.line
            if ln and 0 < ln <= len(lines):
                new_line = _re.sub(
                    r"(\btag:\s*)" + _re.escape(old_tag) + r"(\b|$)",
                    r"\g<1>" + new_tag,
                    lines[ln - 1],
                )
                if new_line != lines[ln - 1]:
                    lines[ln - 1] = new_line
                    changed += 1
    if changed == 0:
        sys.stdout.write("Tag %r not found in %s.\n" % (old_tag, path))
        return 0
    new_text = "".join(lines)
    if dry_run:
        sys.stdout.write(
            "Would rename %d occurrence(s) of tag %r -> %r in %s.\n"
            % (changed, old_tag, new_tag, path)
        )
    else:
        _ensure_writable_path(path, _config(args), "tag rename")
        atomic_write_text(path, new_text)
        sys.stdout.write(
            "Renamed %d occurrence(s) of tag %r -> %r in %s.\n"
            % (changed, old_tag, new_tag, path)
        )
    return 0


def command_watch(args):
    import time

    paths = args.paths if args.paths else ["-"]
    run_cmd = getattr(args, "run", "summary")
    interval = getattr(args, "interval", 1.0)
    do_clear = getattr(args, "clear", False)
    show_timestamp = getattr(args, "timestamp", False)
    do_notify = getattr(args, "notify", False)
    last_exit = [None]

    if "-" in paths:
        sys.stderr.write("ERROR: watch does not support stdin. Specify file paths.\n")
        return 1

    def _mtimes():
        result = {}
        for p in paths:
            try:
                result[p] = os.path.getmtime(p)
            except OSError:
                result[p] = None
        return result

    def _rerun():
        if do_clear:
            sys.stdout.write("\033[2J\033[H")
            sys.stdout.flush()
        import subprocess

        cmd = [sys.executable, "-m", "lifetxt"] + [run_cmd] + paths
        if show_timestamp:
            sys.stdout.write(
                "\n[watch] %s  running: %s\n"
                % (local_now_naive().isoformat(timespec="seconds"), " ".join(cmd))
            )
            sys.stdout.flush()
        try:
            result = subprocess.run(cmd)
            exit_code = result.returncode
            if exit_code:
                marker = "[watch] command exited with %d" % exit_code
                if sys.stderr.isatty():
                    marker = "\033[31m%s\033[0m" % marker
                sys.stderr.write(marker + "\n")
            if do_notify and last_exit[0] is not None and exit_code != last_exit[0]:
                _watch_status_notify(run_cmd, exit_code)
            last_exit[0] = exit_code
        except Exception as exc:
            sys.stderr.write("Watch run error: %s\n" % exc)
            if do_notify:
                _watch_status_notify(run_cmd, 1, message=str(exc))

    sys.stdout.write("Watching %s (Ctrl-C to stop)...\n" % ", ".join(paths))
    last_mtimes = _mtimes()
    _rerun()
    try:
        while True:
            time.sleep(interval)
            current_mtimes = _mtimes()
            if current_mtimes != last_mtimes:
                last_mtimes = current_mtimes
                _rerun()
    except KeyboardInterrupt:
        sys.stdout.write("\nStopped.\n")
    return 0


def _watch_status_notify(command_name, exit_code, message=None):
    text = message or ("lifetxt %s exited with %d" % (command_name, exit_code))
    try:
        from .notifier import notify_desktop

        if notify_desktop({"title": "lifetxt watch", "body": text}):
            return
    except Exception:
        pass
    sys.stdout.write("\a")
    sys.stdout.flush()


def command_tag_merge(args):
    old_tag = args.old
    new_tag = args.new
    path = args.path
    dry_run = getattr(args, "dry_run", False)
    config = _config(args)
    from .write_operations import merge_tag_and_alias
    from .transaction_journal import journal_directory

    # Dry-run computes the semantic transform against an isolated temporary copy.
    if dry_run:
        from .write_operations import transform_items_text

        text = read_text(path)
        id_key = id_key_from_config(config)
        items, diagnostics = parse_text(
            text, id_key=id_key, check_ids=False, check_references=False
        )
        if _has_error(diagnostics):
            _print_diagnostics(diagnostics)
            return 1
        changes = []
        for item in items:
            values = [str(value) for value in item.details.get("tag", [])]
            if old_tag not in values:
                continue
            ids = item.details.get(id_key) or []
            if not ids:
                raise ValueError("Cannot merge tag on an item without %s:." % id_key)
            merged = []
            for value in values:
                candidate = new_tag if value == old_tag else value
                if candidate not in merged:
                    merged.append(candidate)
            changes.append({"id": str(ids[0]), "set_details": {"tag": merged}})
        if not changes:
            sys.stdout.write("Tag %r not found in %s.\n" % (old_tag, path))
            return 0
        transform_items_text(text, changes, id_key=id_key)
        sys.stdout.write(
            "Would merge %d item(s): tag %r -> %r in %s.\n"
            % (len(changes), old_tag, new_tag, path)
        )
        return 0

    _ensure_writable_path(path, config, "tag merge")
    config_path = getattr(args, "config", None) or ".lifetxt.json"
    result, changed = merge_tag_and_alias(
        path,
        old_tag,
        new_tag,
        config_path=config_path,
        life_revision=getattr(args, "revision", None),
        config_revision=getattr(args, "config_revision", None),
        id_key=id_key_from_config(config),
        journal_dir=journal_directory(config, writable_path=path),
        config=config,
    )
    if changed == 0:
        sys.stdout.write("Tag %r not found in %s.\n" % (old_tag, path))
        return 0
    sys.stdout.write(
        "Merged %d item(s): tag %r -> %r in %s.\n" % (changed, old_tag, new_tag, path)
    )
    sys.stdout.write(
        "Updated alias in %s (transaction %s).\n" % (config_path, result.transaction_id)
    )
    return 0


def _derive_key(passphrase, salt, length=32):
    import hashlib

    return hashlib.pbkdf2_hmac(
        "sha256", passphrase.encode("utf-8"), salt, 100000, dklen=length
    )


def _xsk_encrypt(plaintext, passphrase):
    import hashlib, hmac as _hmac, secrets, base64

    salt = secrets.token_bytes(16)
    key = _derive_key(passphrase, salt)
    pt = plaintext.encode("utf-8")
    keystream = b""
    counter = 0
    while len(keystream) < len(pt):
        keystream += hashlib.sha256(key + counter.to_bytes(4, "big")).digest()
        counter += 1
    ciphertext = bytes(a ^ b for a, b in zip(pt, keystream[: len(pt)]))
    payload = salt + ciphertext
    mac = _hmac.new(key, payload, "sha256").digest()
    encoded = base64.b64encode(mac + payload).decode("ascii")
    return "enc:XSK:" + encoded


def _xsk_decrypt(enc_value, passphrase):
    import hashlib, hmac as _hmac, base64

    parts = enc_value.split(":", 2)
    if len(parts) != 3 or parts[0] != "enc" or parts[1] != "XSK":
        raise ValueError("Not an XSK-encrypted value: %r" % enc_value)
    raw = base64.b64decode(parts[2])
    if len(raw) < 48:
        raise ValueError("Truncated ciphertext.")
    mac = raw[:32]
    payload = raw[32:]
    salt = payload[:16]
    ciphertext = payload[16:]
    key = _derive_key(passphrase, salt)
    expected_mac = _hmac.new(key, payload, "sha256").digest()
    if not _hmac.compare_digest(mac, expected_mac):
        raise ValueError("MAC mismatch — wrong passphrase or tampered data.")
    keystream = b""
    counter = 0
    while len(keystream) < len(ciphertext):
        keystream += hashlib.sha256(key + counter.to_bytes(4, "big")).digest()
        counter += 1
    return bytes(
        a ^ b for a, b in zip(ciphertext, keystream[: len(ciphertext)])
    ).decode("utf-8")


def _aesgcm_key(passphrase, salt):
    try:
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    except ImportError as exc:
        raise ValueError(
            "AES-GCM requires the optional 'cryptography' package."
        ) from exc
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=200000,
    )
    return kdf.derive(passphrase.encode("utf-8"))


def _aesgcm_encrypt(plaintext, passphrase):
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    except ImportError as exc:
        raise ValueError(
            "AES-GCM requires the optional 'cryptography' package."
        ) from exc
    import base64
    import secrets

    salt = secrets.token_bytes(16)
    nonce = secrets.token_bytes(12)
    key = _aesgcm_key(passphrase, salt)
    ciphertext = AESGCM(key).encrypt(nonce, plaintext.encode("utf-8"), None)
    return "enc:GCM:" + base64.b64encode(salt + nonce + ciphertext).decode("ascii")


def _aesgcm_decrypt(enc_value, passphrase):
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    except ImportError as exc:
        raise ValueError(
            "AES-GCM requires the optional 'cryptography' package."
        ) from exc
    import base64

    parts = enc_value.split(":", 2)
    if len(parts) != 3 or parts[0] != "enc" or parts[1] != "GCM":
        raise ValueError("Not a GCM-encrypted value: %r" % enc_value)
    raw = base64.b64decode(parts[2])
    if len(raw) < 44:
        raise ValueError("Truncated AES-GCM ciphertext.")
    salt = raw[:16]
    nonce = raw[16:28]
    ciphertext = raw[28:]
    key = _aesgcm_key(passphrase, salt)
    return AESGCM(key).decrypt(nonce, ciphertext, None).decode("utf-8")


def _encrypt_field_value(plaintext, passphrase, algorithm):
    if algorithm == "xsk":
        return _xsk_encrypt(plaintext, passphrase)
    if algorithm == "aesgcm":
        return _aesgcm_encrypt(plaintext, passphrase)
    raise ValueError("Unsupported encryption algorithm: %s" % algorithm)


def _decrypt_field_value(enc_value, passphrase, algorithm="auto"):
    if algorithm == "auto":
        if enc_value.startswith("enc:XSK:"):
            algorithm = "xsk"
        elif enc_value.startswith("enc:GCM:"):
            algorithm = "aesgcm"
        else:
            raise ValueError("Unsupported encrypted value tag: %r" % enc_value)
    if algorithm == "xsk":
        return _xsk_decrypt(enc_value, passphrase)
    if algorithm == "aesgcm":
        return _aesgcm_decrypt(enc_value, passphrase)
    raise ValueError("Unsupported encryption algorithm: %s" % algorithm)


def _read_passphrase_arg(args):
    key_file = getattr(args, "key_file", None)
    key_env = getattr(args, "key_env", "LIFETXT_KEY")
    if key_file:
        passphrase = read_text(key_file).strip()
        if not passphrase:
            sys.stderr.write("ERROR: Passphrase file is empty: %s\n" % key_file)
            return ""
        return passphrase
    passphrase = os.environ.get(key_env, "")
    if not passphrase:
        sys.stderr.write(
            "ERROR: Passphrase not set. Set environment variable %s or use --key-file.\n"
            % key_env
        )
    return passphrase


def command_encrypt(args):
    import re as _re

    path = args.path
    fields = args.fields or ["body", "note"]
    kinds = set(args.kinds or [])
    algorithm = getattr(args, "algorithm", "xsk")
    dry_run = getattr(args, "dry_run", False)
    do_backup = getattr(args, "backup", False)
    passphrase = _read_passphrase_arg(args)
    if not passphrase:
        return 1
    text = read_text(path)
    id_key = id_key_from_config({})
    items, _ = parse_text(text, id_key=id_key, check_ids=False, check_references=False)
    lines = text.splitlines(keepends=True)
    total_changed = 0
    for item in items:
        if kinds and item.kind not in kinds:
            continue
        for field in fields:
            for val in item.details.get(field, []):
                sv = str(val)
                if sv.startswith("enc:"):
                    continue
                try:
                    enc_val = _encrypt_field_value(sv, passphrase, algorithm)
                except ValueError as exc:
                    sys.stderr.write("ERROR: %s\n" % exc)
                    return 1
                ln = item.line
                if ln and 0 < ln <= len(lines):
                    pattern = r"(\b" + _re.escape(field) + r":)" + _re.escape(sv)
                    new_line = _re.sub(
                        pattern, r"\g<1>" + enc_val, lines[ln - 1], count=1
                    )
                    if new_line != lines[ln - 1]:
                        lines[ln - 1] = new_line
                        total_changed += 1
    if dry_run:
        sys.stdout.write(
            "[dry-run] Would encrypt %d field value(s) in %s.\n" % (total_changed, path)
        )
        return 0
    if total_changed == 0:
        sys.stdout.write("No fields to encrypt (already encrypted or not found).\n")
        return 0
    _ensure_writable_path(path, _config(args), "encrypt")
    if do_backup:
        import shutil as _sh

        _sh.copy2(path, path + ".bak")
    atomic_write_text(path, "".join(lines))
    sys.stdout.write("Encrypted %d field value(s) in %s.\n" % (total_changed, path))
    return 0


def command_decrypt(args):
    import re as _re

    path = args.path
    fields_filter = set(args.fields or [])
    algorithm = getattr(args, "algorithm", "auto")
    dry_run = getattr(args, "dry_run", False)
    do_backup = getattr(args, "backup", False)
    passphrase = _read_passphrase_arg(args)
    if not passphrase:
        return 1
    text = read_text(path)
    lines = text.splitlines(keepends=True)
    total_changed = 0
    errors = 0
    ENC_RE = _re.compile(r"\b([\w-]+):(enc:(?:XSK|GCM):[A-Za-z0-9+/=]+)")
    for i, line in enumerate(lines):
        new_line = line
        for m in ENC_RE.finditer(line):
            field_key = m.group(1)
            enc_val = m.group(2)
            if fields_filter and field_key not in fields_filter:
                continue
            try:
                plaintext = _decrypt_field_value(enc_val, passphrase, algorithm)
                new_line = new_line.replace(enc_val, plaintext, 1)
                total_changed += 1
            except Exception as exc:
                sys.stderr.write(
                    "WARNING: line %d field %r: %s\n" % (i + 1, field_key, exc)
                )
                errors += 1
        lines[i] = new_line
    if dry_run:
        sys.stdout.write(
            "[dry-run] Would decrypt %d field value(s) in %s.\n" % (total_changed, path)
        )
        return 0
    if total_changed == 0:
        sys.stdout.write("No encrypted fields found.\n")
        return 1 if errors else 0
    _ensure_writable_path(path, _config(args), "decrypt")
    if do_backup:
        import shutil as _sh

        _sh.copy2(path, path + ".bak")
    atomic_write_text(path, "".join(lines))
    sys.stdout.write("Decrypted %d field value(s) in %s.\n" % (total_changed, path))
    return 1 if errors else 0


def _share_range_label(args):
    today = timezone_today()
    if getattr(args, "week", False):
        start = today - datetime.timedelta(days=today.weekday())
        end = start + datetime.timedelta(days=6)
        return "%s to %s" % (start.isoformat(), end.isoformat())
    if getattr(args, "month", None):
        import calendar as _calendar

        try:
            year_s, month_s = args.month.split("-")
            year_i, month_i = int(year_s), int(month_s)
            start = datetime.date(year_i, month_i, 1)
            last_day = _calendar.monthrange(year_i, month_i)[1]
            end = datetime.date(year_i, month_i, last_day)
        except (ValueError, AttributeError):
            raise ValueError("Invalid --month format. Use YYYY-MM.")
        return "%s to %s" % (start.isoformat(), end.isoformat())
    return "all matching items"


def _share_plot_data(items):
    from .timeutil import parse_elapsed as _parse_elapsed

    status_counts = OrderedDict()
    project_counts = OrderedDict()
    elapsed_by_project = OrderedDict()
    for item in items:
        status_counts[item.status] = status_counts.get(item.status, 0) + 1
        project = (
            str(item.details.get("project", [""])[0])
            if item.details.get("project")
            else "(no project)"
        )
        project_counts[project] = project_counts.get(project, 0) + 1
        elapsed_vals = item.details.get("elapsed", [])
        if elapsed_vals:
            minutes = _parse_elapsed(str(elapsed_vals[0]))
            if minutes:
                elapsed_by_project[project] = (
                    elapsed_by_project.get(project, 0) + minutes
                )

    plot_data = OrderedDict()
    if status_counts:
        plot_data["Items by status"] = OrderedDict(
            sorted(status_counts.items(), key=lambda kv: -kv[1])
        )
    if project_counts:
        plot_data["Items by project"] = OrderedDict(
            sorted(project_counts.items(), key=lambda kv: -kv[1])
        )
    if elapsed_by_project:
        plot_data["Elapsed minutes by project"] = OrderedDict(
            sorted(elapsed_by_project.items(), key=lambda kv: -kv[1])
        )
    return plot_data


def _share_to_html(title, range_label, items, plot_data):
    def esc(value):
        return html.escape(str(value), quote=True)

    lines = [
        "<!doctype html>",
        '<html lang="en">',
        "<head>",
        '<meta charset="utf-8">',
        "<title>%s</title>" % esc(title),
        "<style>",
        "body{font-family:system-ui,-apple-system,sans-serif;line-height:1.5;max-width:960px;margin:32px auto;padding:0 16px;color:#1f2937}",
        "h1,h2{line-height:1.2} table{border-collapse:collapse;width:100%;margin:12px 0}",
        "th,td{border:1px solid #d1d5db;padding:6px 8px;text-align:left} th{background:#f3f4f6}",
        ".meta{color:#6b7280} svg{max-width:100%;height:auto}",
        "</style>",
        "</head>",
        "<body>",
        "<h1>%s</h1>" % esc(title),
        '<p class="meta">%s &middot; %d item(s)</p>' % (esc(range_label), len(items)),
    ]
    if plot_data:
        lines.append(_plot_data_to_svg(plot_data, title="Summary"))
    lines.append("<h2>Items</h2>")
    if items:
        lines.append(
            "<table><thead><tr><th>Status</th><th>Type</th><th>Title</th><th>Project</th></tr></thead><tbody>"
        )
        for item in items:
            project = (
                str(item.details.get("project", [""])[0])
                if item.details.get("project")
                else ""
            )
            lines.append(
                "<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>"
                % (esc(item.status), esc(item.kind), esc(item.title), esc(project))
            )
        lines.append("</tbody></table>")
    else:
        lines.append("<p>No matching items.</p>")
    lines.extend(["</body>", "</html>"])
    return "\n".join(lines) + "\n"


def _share_to_markdown(title, range_label, items, plot_data):
    lines = ["# %s" % title, "", "%s — %d item(s)" % (range_label, len(items)), ""]
    for chart_title, data in plot_data.items():
        lines.append("## %s" % chart_title)
        lines.append("")
        max_value = max(data.values()) if data else 1
        for label, value in data.items():
            bar = _plot_bar(value, max_value, width=30)
            lines.append("- `%s` %s %s" % (label, bar, value))
        lines.append("")
    lines.append("## Items")
    lines.append("")
    if items:
        lines.append("| Status | Type | Title | Project |")
        lines.append("|---|---|---|---|")
        for item in items:
            project = (
                str(item.details.get("project", [""])[0])
                if item.details.get("project")
                else ""
            )
            lines.append(
                "| %s | %s | %s | %s |"
                % (item.status, item.kind, item.title.replace("|", "\\|"), project)
            )
    else:
        lines.append("No matching items.")
    return "\n".join(lines) + "\n"


def command_share(args):
    config = _config(args)
    paths = _normalize_paths(getattr(args, "paths", None) or [], config)
    items, diagnostics = _parse_life_inputs(paths, config)
    items = _filter_items_from_args(items, args)

    range_label = _share_range_label(args)
    plot_data = _share_plot_data(items)

    fmt = getattr(args, "format", "html") or "html"
    title = getattr(args, "title", None) or "lifetxt share report"
    output_path = getattr(args, "output", None) or (
        "share.html" if fmt == "html" else "share.md"
    )

    if fmt == "markdown":
        text = _share_to_markdown(title, range_label, items, plot_data)
    else:
        text = _share_to_html(title, range_label, items, plot_data)

    write_text(output_path, text)
    sys.stdout.write("Wrote %s (%d item(s)).\n" % (output_path, len(items)))
    _print_warnings(diagnostics)
    return 0


def command_digest(args):
    import contextlib
    import io

    review_args = argparse.Namespace(
        paths=getattr(args, "paths", None) or [],
        week=getattr(args, "week", False),
        month=getattr(args, "month", None),
        from_date=None,
        to_date=None,
        project=getattr(args, "project", None),
        format="json",
        pretty=False,
        config=getattr(args, "config", None),
        config_data=getattr(args, "config_data", None),
    )
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        command_review(review_args)
    result = json.loads(buffer.getvalue())

    lines = ["*lifetxt digest: %s*" % result["range"], ""]
    lines.append("Completed tasks: %d" % result["completed_tasks"])
    lines.append("Open tasks: %d" % result["open_tasks"])
    if result["habits"]:
        lines.append("")
        lines.append("Habits:")
        for habit_title, habit in result["habits"].items():
            lines.append(
                "- %s: %d/%d (%d%%)"
                % (
                    habit_title,
                    habit["done"],
                    habit["done"] + habit["open"],
                    habit["completion_rate"],
                )
            )
    if result["elapsed_by_project"]:
        lines.append("")
        lines.append("Elapsed by project:")
        for project, elapsed in result["elapsed_by_project"].items():
            lines.append("- %s: %s" % (project, elapsed))
    message = "\n".join(lines)

    channel = args.channel
    dry_run = getattr(args, "dry_run", False)

    if channel == "slack-webhook":
        url_env = getattr(args, "url_env", None)
        if not url_env:
            raise ValueError("--url-env is required with --format slack-webhook.")
        webhook_url = os.environ.get(url_env, "")
        if not webhook_url:
            raise ValueError("Environment variable %s is not set." % url_env)
        if dry_run:
            sys.stdout.write(
                "[dry-run] Would POST to Slack webhook from $%s:\n%s\n"
                % (url_env, message)
            )
            return 0
        payload = json.dumps({"text": message}).encode("utf-8")
        request = Request(
            webhook_url, data=payload, headers={"Content-Type": "application/json"}
        )
        try:
            urlopen(request, timeout=10)
        except (HTTPError, URLError) as exc:
            raise ValueError("Slack webhook request failed: %s" % exc)
        sys.stdout.write("Sent digest to Slack webhook.\n")
        return 0

    if channel == "email":
        to_addr = getattr(args, "to", None)
        if not to_addr:
            raise ValueError("--to is required with --format email.")
        host_env = getattr(args, "smtp_host_env", "LIFETXT_SMTP_HOST")
        user_env = getattr(args, "smtp_user_env", "LIFETXT_SMTP_USER")
        pass_env = getattr(args, "smtp_pass_env", "LIFETXT_SMTP_PASS")
        smtp_host = os.environ.get(host_env, "")
        smtp_user = os.environ.get(user_env, "")
        smtp_pass = os.environ.get(pass_env, "")
        if not smtp_host:
            raise ValueError(
                "Environment variable %s (SMTP host) is not set." % host_env
            )
        if not smtp_user or not smtp_pass:
            raise ValueError(
                "Environment variables %s and %s (SMTP credentials) must be set."
                % (user_env, pass_env)
            )
        if dry_run:
            sys.stdout.write(
                "[dry-run] Would email digest to %s via %s:\n%s\n"
                % (to_addr, smtp_host, message)
            )
            return 0
        import smtplib
        from email.mime.text import MIMEText

        mime = MIMEText(message, "plain", "utf-8")
        mime["Subject"] = "lifetxt digest: %s" % result["range"]
        mime["From"] = smtp_user
        mime["To"] = to_addr
        with smtplib.SMTP(smtp_host, timeout=10) as smtp:
            smtp.starttls()
            smtp.login(smtp_user, smtp_pass)
            smtp.sendmail(smtp_user, [to_addr], mime.as_string())
        sys.stdout.write("Sent digest email to %s.\n" % to_addr)
        return 0

    if channel == "file":
        digest_path = getattr(args, "digest_path", None)
        if not digest_path:
            raise ValueError("--path is required with --format file.")
        if dry_run:
            sys.stdout.write(
                "[dry-run] Would append digest to %s:\n%s\n" % (digest_path, message)
            )
            return 0
        from .write_operations import append_text as semantic_append_text

        semantic_append_text(
            digest_path,
            "\n" + message + "\n",
            expected_revision=getattr(args, "revision", None),
            operation="digest.append",
            create=True,
        )
        sys.stdout.write("Appended digest to %s.\n" % digest_path)
        return 0

    raise ValueError("Unsupported digest channel: %s" % channel)


def _resolve_template_placeholders(text, today=None):
    today = today or timezone_today()
    days_to_next_monday = (7 - today.weekday()) % 7 or 7
    next_monday = today + datetime.timedelta(days=days_to_next_monday)
    next_week = today + datetime.timedelta(days=7)
    replacements = (
        ("{today}", today.isoformat()),
        ("{next_monday}", next_monday.isoformat()),
        ("{next_week}", next_week.isoformat()),
    )
    for placeholder, value in replacements:
        text = text.replace(placeholder, value)
    return text


def command_template_list(args):
    templates = config_templates(_config(args))
    if not templates:
        sys.stdout.write(
            'No templates configured. Add a "templates" section to your config file.\n'
        )
        return 0
    for name, lines in templates.items():
        sys.stdout.write("%s (%d line(s))\n" % (name, len(lines)))
    return 0


def command_template_apply(args):
    templates = config_templates(_config(args))
    name = args.name
    if name not in templates:
        raise ValueError(
            "Template not found: %s. Run `lifetxt template list` to see available templates."
            % name
        )
    expanded_lines = [_resolve_template_placeholders(line) for line in templates[name]]
    expanded = "\n".join(expanded_lines) + "\n"

    if getattr(args, "dry_run", False):
        sys.stdout.write("[dry-run] Would append to %s:\n%s" % (args.append, expanded))
        return 0

    target = args.append
    from .write_operations import append_life_records

    append_life_records(
        target,
        expanded,
        expected_revision=getattr(args, "revision", None),
        operation="template.apply",
    )
    sys.stdout.write(
        "Appended template %r (%d line(s)) to %s.\n"
        % (name, len(expanded_lines), target)
    )
    return 0
