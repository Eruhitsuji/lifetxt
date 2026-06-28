import argparse
import datetime
import html
import hashlib
import json
import os
import sys
import tempfile
import types
from collections import OrderedDict
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .config import (
    config_notification_recipient,
    config_paths,
    config_section,
    config_tag_aliases,
    config_template_text,
    config_team_aliases,
    config_team_members,
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
    format_agenda_table,
    parse_agenda_range,
    parse_optional_time_range,
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
from .timeutil import parse_date_or_datetime
from .notifier import (
    format_notification_table,
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


DIAGNOSTIC_CATEGORIES = (
    "syntax",
    "schema",
    "style",
    "time",
    "status",
    "message",
    "id",
    "reference",
    "recurrence",
    "duration",
    "workflow",
    "semantic",
)


def main(argv=None):
    try:
        argv, config_path = _extract_config_arg(argv)
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
    try:
        args.config_data = load_config(config_path)
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
        cleaned.append(value)
        index += 1
    return cleaned, config_path


def build_parser():
    parser = argparse.ArgumentParser(
        prog="python -m lifetxt",
        description="Parser, validator, converter, and input helper for life.txt.",
    )
    parser.add_argument(
        "--config",
        help="External JSON config file. May also be set with LIFETXT_CONFIG.",
    )
    subparsers = parser.add_subparsers(dest="command")

    check = subparsers.add_parser("check", help="Check life.txt syntax and warnings.")
    _add_input_paths(check)
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
    ids_command.add_argument("--pretty", action="store_true", help="Pretty-print JSON output.")
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
    links_command.add_argument("--pretty", action="store_true", help="Pretty-print JSON output.")
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
    sources_command.add_argument("--pretty", action="store_true", help="Pretty-print JSON output.")
    sources_command.set_defaults(func=command_sources)

    to_json = subparsers.add_parser("to-json", help="Convert life.txt to JSON array.")
    _add_input_paths(to_json)
    to_json.add_argument("-o", "--output", help="Output file. Defaults to stdout.")
    to_json.add_argument("--pretty", action="store_true", help="Pretty-print JSON.")
    _add_item_filter_arguments(to_json)
    to_json.set_defaults(func=command_to_json)

    to_jsonl = subparsers.add_parser("to-jsonl", help="Convert life.txt to JSONL.")
    _add_input_paths(to_jsonl)
    to_jsonl.add_argument("-o", "--output", help="Output file. Defaults to stdout.")
    _add_item_filter_arguments(to_jsonl)
    to_jsonl.set_defaults(func=command_to_jsonl)

    to_csv = subparsers.add_parser("to-csv", help="Convert life.txt to CSV.")
    _add_input_paths(to_csv)
    to_csv.add_argument("-o", "--output", help="Output file. Defaults to stdout.")
    _add_item_filter_arguments(to_csv)
    to_csv.set_defaults(func=command_to_csv)

    markdown_command = subparsers.add_parser(
        "markdown",
        help="Render the safe life.txt Markdown subset from selected fields.",
    )
    _add_input_paths(markdown_command)
    markdown_command.add_argument("-o", "--output", help="Output file. Defaults to stdout.")
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
    markdown_command.add_argument("--pretty", action="store_true", help="Pretty-print JSON output.")
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
    serve.set_defaults(func=command_serve)

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
    timer_start = timer_subparsers.add_parser("start", help="Start a timer for an item ID.")
    timer_start.add_argument("path", help="life.txt file containing the item.")
    timer_start.add_argument("--id", dest="item_id", required=True, help="Item ID to time.")
    timer_start.add_argument("--note", help="Optional note stored in timer state.")
    timer_start.set_defaults(func=command_timer)
    timer_pause = timer_subparsers.add_parser("pause", help="Pause the running timer.")
    timer_pause.set_defaults(func=command_timer)
    timer_resume = timer_subparsers.add_parser("resume", help="Resume a paused timer.")
    timer_resume.set_defaults(func=command_timer)
    timer_stop = timer_subparsers.add_parser("stop", help="Stop the running timer.")
    timer_stop.add_argument("path", nargs="?", help="life.txt file. Defaults to the file stored in timer state.")
    timer_stop.add_argument("--id", dest="item_id", help="Expected running item ID.")
    timer_stop.set_defaults(func=command_timer)
    timer_status = timer_subparsers.add_parser("status", help="Show the running timer.")
    timer_status.add_argument("paths", nargs="*", metavar="path", help="Optional life.txt files used to resolve the title.")
    timer_status.set_defaults(func=command_timer)
    timer_summary = timer_subparsers.add_parser("summary", help="Summarize elapsed: details.")
    timer_summary.add_argument("paths", nargs="+", metavar="path", help="life.txt file(s) to summarize.")
    timer_summary.add_argument("--from", dest="start", help="Start date or datetime.")
    timer_summary.add_argument("--to", dest="end", help="End date or datetime.")
    timer_summary.add_argument("--project", help="Filter by project.")
    timer_summary.add_argument("--format", choices=("text", "json"), default="text", help="Output format.")
    timer_summary.set_defaults(func=command_timer)
    timer_cancel = timer_subparsers.add_parser("cancel", help="Cancel the running timer without updating an item.")
    timer_cancel.set_defaults(func=command_timer)

    stats = subparsers.add_parser(
        "stats",
        help="Show task, habit, mood, and project statistics.",
    )
    _add_input_paths(stats)
    stats.add_argument("--from", dest="start", help="Start date. Defaults to 29 days before --to.")
    stats.add_argument("--to", dest="end", help="End date. Defaults to today.")
    stats.add_argument("--type", dest="kind", help="Filter by type or alias.")
    stats.add_argument("--project", help="Filter by project.")
    stats.add_argument(
        "--group",
        choices=("daily", "weekly", "monthly"),
        default="daily",
        help="Aggregation bucket size.",
    )
    stats.add_argument("--format", choices=("text", "json"), default="text", help="Output format.")
    stats.set_defaults(func=command_stats)

    git_hook = subparsers.add_parser(
        "git-hook",
        help="Install, uninstall, or inspect lifetxt Git hooks.",
    )
    git_hook_subparsers = git_hook.add_subparsers(dest="git_hook_command")
    git_hook_install = git_hook_subparsers.add_parser("install", help="Install Git hooks.")
    git_hook_install.add_argument("--repo-dir", default=".", help="Git repository root. Defaults to current directory.")
    git_hook_install.add_argument("--files", nargs="*", help="life.txt files checked by hooks.")
    git_hook_install.add_argument("--no-commit-msg", action="store_true", help="Do not install commit-msg hook.")
    git_hook_install.add_argument("--force", action="store_true", help="Overwrite non-lifetxt hooks.")
    git_hook_install.set_defaults(func=command_git_hook)
    git_hook_uninstall = git_hook_subparsers.add_parser("uninstall", help="Uninstall lifetxt Git hooks.")
    git_hook_uninstall.add_argument("--repo-dir", default=".", help="Git repository root. Defaults to current directory.")
    git_hook_uninstall.set_defaults(func=command_git_hook)
    git_hook_status = git_hook_subparsers.add_parser("status", help="Show Git hook installation status.")
    git_hook_status.add_argument("--repo-dir", default=".", help="Git repository root. Defaults to current directory.")
    git_hook_status.add_argument("--files", nargs="*", help="life.txt files checked by hooks.")
    git_hook_status.set_defaults(func=command_git_hook)

    completion = subparsers.add_parser(
        "completion",
        help="Generate shell completion scripts.",
    )
    completion_subparsers = completion.add_subparsers(dest="completion_command")
    for shell in ("bash", "zsh", "fish"):
        shell_parser = completion_subparsers.add_parser(shell, help="Generate %s completion." % shell)
        shell_parser.add_argument("-o", "--output", help="Output file. Defaults to stdout.")
        shell_parser.set_defaults(func=command_completion)
    completion_install = completion_subparsers.add_parser("install", help="Print installation instructions.")
    completion_install.add_argument("--shell", choices=("bash", "zsh", "fish"), help="Shell to show instructions for.")
    completion_install.add_argument("-o", "--output", help="Output file. Defaults to stdout.")
    completion_install.set_defaults(func=command_completion)

    filter_command = subparsers.add_parser(
        "filter",
        help="Filter life.txt items and output life.txt, JSON, or JSONL.",
    )
    _add_input_paths(filter_command)
    _add_item_filter_arguments(filter_command)
    filter_command.add_argument(
        "--format",
        choices=("life", "json", "jsonl"),
        default="life",
        help="Output format. Defaults to life.",
    )
    filter_command.add_argument("-o", "--output", help="Output file. Defaults to stdout.")
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
    status.add_argument("--pretty", action="store_true", help="Pretty-print JSON output.")
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
    notify.add_argument("--pretty", action="store_true", help="Pretty-print JSON output.")
    notify.set_defaults(func=command_notify)

    agenda = subparsers.add_parser(
        "agenda",
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
        "--format",
        choices=("text", "life", "json", "jsonl"),
        default="text",
        help="Output format.",
    )
    agenda.add_argument("-o", "--output", help="Output file. Defaults to stdout.")
    agenda.add_argument(
        "--open",
        action="store_true",
        help="Show unfinished workflow items only: [ ], [/], [>], or [?].",
    )
    agenda.add_argument(
        "--status",
        action="append",
        help="Filter by status or alias. Can be repeated or comma-separated.",
    )
    agenda.add_argument(
        "--type",
        dest="kinds",
        action="append",
        help="Filter by type or alias. Can be repeated or comma-separated.",
    )
    agenda.add_argument(
        "--project",
        action="append",
        help="Filter by project: value. Can be repeated or comma-separated.",
    )
    agenda.add_argument(
        "--tag",
        action="append",
        help="Filter by tag: value. Can be repeated or comma-separated.",
    )
    agenda.add_argument(
        "--tag-all",
        action="append",
        help="Require every listed tag value. Can be repeated or comma-separated.",
    )
    agenda.add_argument(
        "--exclude-tag",
        action="append",
        help="Exclude items containing any listed tag value. Can be repeated or comma-separated.",
    )
    agenda.add_argument(
        "--user",
        action="append",
        help="Filter by any user-related detail: user, person, owner, assignee, attendee, sender, or recipient.",
    )
    agenda.add_argument(
        "--team",
        action="append",
        help="Filter by team/group detail or config-defined team membership.",
    )
    agenda.add_argument(
        "--person",
        action="append",
        help="Filter by person: value. Can be repeated or comma-separated.",
    )
    agenda.add_argument(
        "--owner",
        action="append",
        help="Filter by owner: value. Can be repeated or comma-separated.",
    )
    agenda.add_argument(
        "--assignee",
        action="append",
        help="Filter by assignee: value. Can be repeated or comma-separated.",
    )
    agenda.add_argument(
        "--attendee",
        action="append",
        help="Filter by attendee: value. Can be repeated or comma-separated.",
    )
    agenda.add_argument(
        "--sender",
        action="append",
        help="Filter by sender: value. Can be repeated or comma-separated.",
    )
    agenda.add_argument(
        "--recipient",
        action="append",
        help="Filter by recipient: value. Can be repeated or comma-separated.",
    )
    agenda.add_argument(
        "--detail",
        action="append",
        default=[],
        help="Filter by detail key or key=value. Repeated filters are ANDed.",
    )
    agenda.add_argument(
        "--text",
        help="Case-insensitive substring filter across title, line, and detail values.",
    )
    agenda.add_argument("--pretty", action="store_true", help="Pretty-print JSON output.")
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
    assist.add_argument("-i", "--interactive", action="store_true", help="Prompt for fields.")
    assist.add_argument("-s", "--status", help="Status or alias, e.g. '[ ]', done, note.")
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
    assist.add_argument("--match-id", help="Update the item whose id: contains this value.")
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
    for key in DETAIL_FLAGS:
        dest = "from_" if key == "from" else key
        assist.add_argument(
            "--" + key,
            dest=dest,
            action="append",
            help="Set %s: detail. Can be repeated." % key,
        )
    assist.set_defaults(func=command_assist)

    archive = subparsers.add_parser(
        "archive",
        help="Move or copy completed/canceled items to a separate archive file.",
    )
    archive.add_argument("paths", nargs="+", metavar="path", help="Source life.txt file(s).")
    archive.add_argument("--dest", required=True, metavar="DEST", help="Archive file to append items to.")
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
    quick.add_argument("title", help="Item title.")
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
            help="Set %s: detail. Can be repeated. Accepts relative dates for due/do/until (today, tomorrow, friday, next_week)." % key,
        )
    quick.set_defaults(func=command_quick, detail=None, add_detail=None, remove_detail=None)

    done_cmd = subparsers.add_parser(
        "done",
        help="Mark an item as complete and append done:TODAY.",
    )
    done_cmd.add_argument("path", help="life.txt file containing the item.")
    done_cmd.add_argument(
        "id",
        nargs="?",
        default=None,
        help="ID of the item to mark done.",
    )
    done_cmd.add_argument("--line", type=int, default=None, help="Line number of the item.")
    done_cmd.add_argument("--text", default=None, help="Title substring to search for.")
    done_cmd.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would change without writing to the file.",
    )
    done_cmd.set_defaults(func=command_done)

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
    summary.add_argument("--pretty", action="store_true", help="Pretty-print JSON output.")
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
    init_cmd.add_argument("--timezone", help="Your timezone (for #! timezone: directive).")
    init_cmd.add_argument("--project", help="Default project name (for #! project: directive).")
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
    doctor_cmd.add_argument("--pretty", action="store_true", help="Pretty-print JSON output.")
    doctor_cmd.set_defaults(func=command_doctor)

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
    health_cmd.add_argument("--pretty", action="store_true", help="Pretty-print JSON output.")
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
    inbox_cmd.add_argument("--pretty", action="store_true", help="Pretty-print JSON output.")
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
    cleanup_cmd.add_argument("--pretty", action="store_true", help="Pretty-print JSON output.")
    cleanup_cmd.set_defaults(func=command_cleanup)

    undo_cmd = subparsers.add_parser(
        "undo",
        help="Restore a file to its state before the most recent write operation.",
    )
    undo_cmd.add_argument("path", help="life.txt file to restore.")
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
        choices=("text", "json", "jsonl", "markdown"),
        default="text",
        help="Output format.",
    )
    review_cmd.add_argument("--pretty", action="store_true", help="Pretty-print JSON output.")
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
    who_cmd.add_argument("--pretty", action="store_true", help="Pretty-print JSON output.")
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
    search_cmd.add_argument("--pretty", action="store_true", help="Pretty-print JSON output.")
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
        "-o", "--output",
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
    diff_cmd.add_argument("--pretty", action="store_true", help="Pretty-print JSON output.")
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
        choices=("added", "removed", "completed", "canceled", "status-changed", "detail-changed"),
        help="Limit output to specific change types. Can be repeated.",
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
        choices=("tasks", "habits", "mood", "elapsed", "all"),
        default="all",
        help="Which chart to render (default: all).",
    )
    plot_cmd.add_argument(
        "--group",
        choices=("daily", "weekly", "monthly"),
        default="weekly",
        help="Time bucket size for trend charts.",
    )
    plot_cmd.add_argument("--from", dest="start", metavar="DATE", help="Start date (YYYY-MM-DD).")
    plot_cmd.add_argument("--to", dest="end", metavar="DATE", help="End date (YYYY-MM-DD).")
    plot_cmd.add_argument("--project", help="Restrict to a single project.")
    plot_cmd.add_argument(
        "--width",
        type=int,
        default=0,
        help="Chart width in characters (0 = auto-detect terminal width).",
    )
    plot_cmd.set_defaults(func=command_plot)

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
            "Built-in names: normalize-elapsed, rename-key OLD=NEW, add-id."
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
    frommd_cmd.add_argument("--append", action="store_true", help="Append to output file instead of overwrite.")
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
        choices=("text", "json"),
        default="text",
        help="Output format (default: text).",
    )
    deps_cmd.add_argument("--pretty", action="store_true", help="Pretty-print JSON output.")
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
    tag_rename_cmd.add_argument("--dry-run", action="store_true", help="Preview without writing.")
    tag_rename_cmd.set_defaults(func=command_tag_rename)
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
    watch_cmd.add_argument("--clear", action="store_true", help="Clear screen before each re-run.")
    watch_cmd.set_defaults(func=command_watch)

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


_W225_GUIDANCE = (
    "  Hint: To resolve W225, either (1) close children manually, "
    "(2) run archive --orphan-children adopt, or (3) run archive --orphan-children promote."
)


def command_check(args):
    items, diagnostics = _parse_life_inputs(args.paths, _config(args))
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
        for name in ("diagnostic_severities", "diagnostic_codes", "diagnostic_categories", "ignore_codes")
    )

    if args.format == "json":
        output = json.dumps(
            [diagnostic_to_output_dict(diagnostic) for diagnostic in filtered_diagnostics],
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
    items = _filter_items_from_args(items, args)
    output = items_to_json(items, pretty=args.pretty)
    write_text(args.output, output + "\n")
    _print_warnings(diagnostics)
    return 0


def command_to_jsonl(args):
    items, diagnostics = _parse_or_exit(args.paths, _config(args))
    items = _filter_items_from_args(items, args)
    output = items_to_jsonl(items)
    if output:
        output += "\n"
    write_text(args.output, output)
    _print_warnings(diagnostics)
    return 0


def command_to_csv(args):
    items, diagnostics = _parse_or_exit(args.paths, _config(args))
    items = _filter_items_from_args(items, args)
    write_text(args.output, items_to_csv(items))
    _print_warnings(diagnostics)
    return 0


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


def command_import_ics(args):
    if args.append and not args.output:
        raise ValueError("--append requires --output.")

    items = []
    for path in _normalize_paths(args.paths):
        items.extend(
            items_from_ics_text(
                read_text(path),
                project=args.project,
                tags=args.tag,
            )
        )

    diagnostics = []
    for item in items:
        diagnostics.extend(validate_item(item))
    if _has_error(diagnostics):
        _print_diagnostics(diagnostics)
        return 1
    _print_warnings(diagnostics)

    output = _items_to_life_text(items, canonical=True)
    if args.append:
        append_text(args.output, output)
    else:
        write_text(args.output, output)
    return 0


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
            )
        )

    output = _validated_life_text_or_exit(items)
    if output is None:
        return 1
    if args.dry_run:
        write_text(None, output)
    else:
        output_path = args.output or _sync_config(args).get("output")
        if output_path:
            ensure_parent_dir(output_path)
        write_text(output_path, output)
    return 0


def command_serve(args):
    try:
        import uvicorn

        from .webapp import create_app
    except ImportError as exc:
        raise ValueError(
            "Web dependencies are not installed. Run: pip install -r requirements-web.txt"
        ) from exc

    web_config = config_section(_config(args), "web")
    paths = _normalize_paths(
        list(args.paths) if args.paths else (config_paths(_config(args)) or ["life.txt"]),
        _config(args),
        stdin_when_empty=False,
    )
    writable_path = args.write_file or config_write_file(_config(args)) or paths[0]
    host = args.host or web_config.get("host") or "127.0.0.1"
    port = args.port or int(web_config.get("port") or 8000)
    app = create_app(paths=paths, writable_path=writable_path, config=_config(args))
    uvicorn.run(app, host=host, port=port)
    return 0


def _split_archive_text(raw_text, items, archive_id_set,
                         archive_overrides=None, remainder_overrides=None):
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
                    text = getattr(modified, "source_text", None) or item_to_line(modified)
                    remainder_out.append(text if text.endswith("\n") else text + "\n")
                custom_written.add(item_id)
            else:
                remainder_out.append(raw_line)

    return "".join(archive_out), "".join(remainder_out)


def command_archive(args):
    config = _config(args)
    paths = _normalize_paths(args.paths, config, stdin_when_empty=False)
    if not paths:
        raise ValueError("No source files specified.")

    mode = "copy" if args.copy else "move"
    if mode == "move" and "-" in paths:
        raise ValueError("Cannot use move mode with stdin input. Use --copy or specify a file path.")

    before_date = None
    if args.before:
        before_date = parse_date_or_datetime(args.before, is_end=False)
        if before_date is None:
            raise ValueError(
                "Invalid --before date %r. Use YYYY-MM-DD or YYYY-MM-DDTHH:MM." % args.before
            )

    if args.max_items is not None and args.max_items < 1:
        raise ValueError("--max-items must be a positive integer.")

    id_key = id_key_from_config(config)
    file_texts = OrderedDict()
    file_items = OrderedDict()
    for path in paths:
        text = read_text(path)
        file_texts[path] = text
        items, _diags = parse_text(text, id_key=id_key, check_ids=False, check_references=False)
        for item in items:
            item.source = path
        file_items[path] = items

    all_items = [item for items in file_items.values() for item in items]

    statuses_arg = args.statuses or ["done,canceled"]
    try:
        candidates = filter_items(all_items, statuses=statuses_arg)
    except ValueError as exc:
        raise ValueError("Invalid --status: %s" % exc)

    if before_date is not None:
        candidates = [item for item in candidates if _archive_item_date_before(item, before_date)]

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
            sys.stdout.write("Cannot archive: the following candidates have open children:\n")
            for pid, children in open_children_by_parent.items():
                child_ids = ", ".join(
                    str(v) for c in children for v in c.details.get(id_key, [])
                ) or "(no id)"
                sys.stdout.write("  parent %s: open children %s\n" % (pid, child_ids))
            sys.stdout.write("Use --orphan-children adopt or --orphan-children promote to proceed.\n")
            return 1

        elif orphan_mode == "adopt":
            already = {id(item) for item in candidates}
            for children in open_children_by_parent.values():
                for child in children:
                    if id(child) not in already:
                        candidates.append(child)
                        already.add(id(child))

        # promote: archive parent only; children lose parent: in source (handled below)

    multi_source = len(paths) > 1
    sys.stdout.write("Items to archive (%d, %s -> %s):\n" % (len(candidates), mode, args.dest))
    for item in candidates:
        source_label = ("  [%s]" % item.source) if multi_source else ""
        sys.stdout.write("  %s %s %s%s\n" % (item.status, item.kind, item.title, source_label))

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
                id(item) for item in candidates
                if getattr(item, "source", None) == path
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

    _pre_write_backup(args.dest, config, "archive")
    append_text(args.dest, archive_text)

    if mode == "move":
        archive_ids = {id(item) for item in candidates}
        promote_parent_ids = candidate_ids if orphan_mode == "promote" else set()

        for path, items in file_items.items():
            def _promote_item(item):
                if promote_parent_ids and item.details.get("parent"):
                    new_parents = [
                        p for p in item.details["parent"]
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

            if preserve:
                path_archive_ids = {
                    id(item) for item in candidates
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
                if needs_write:
                    _pre_write_backup(path, config, "archive")
                    atomic_write_text(path, remainder_text)
            else:
                remaining_raw = [item for item in items if id(item) not in archive_ids]
                remaining = [_promote_item(item) for item in remaining_raw]
                needs_write = len(remaining) < len(items) or any(
                    id(r) != id(o) for r, o in zip(remaining, remaining_raw)
                )
                if needs_write:
                    _pre_write_backup(path, config, "archive")
                    atomic_write_text(path, _items_to_life_text(remaining))

    sys.stdout.write("Archived %d item(s) to %s.\n" % (len(candidates), args.dest))
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


_RELATIVE_DATE_WEEKDAYS = {
    "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
    "friday": 4, "saturday": 5, "sunday": 6,
}


def _resolve_relative_date(value, today=None):
    """Resolve relative date keywords to ISO YYYY-MM-DD strings.

    Recognizes: today, tomorrow, weekday names (next occurrence),
    next_WEEKDAY (always next week), next_week (next Monday).
    Unknown values are returned unchanged.
    """
    if today is None:
        today = datetime.date.today()
    text = str(value).lower().strip()
    if text == "today":
        return today.isoformat()
    if text == "tomorrow":
        return (today + datetime.timedelta(days=1)).isoformat()
    if text in _RELATIVE_DATE_WEEKDAYS:
        target_wd = _RELATIVE_DATE_WEEKDAYS[text]
        days_ahead = target_wd - today.weekday()
        if days_ahead <= 0:
            days_ahead += 7
        return (today + datetime.timedelta(days=days_ahead)).isoformat()
    if text.startswith("next_") and text[5:] in _RELATIVE_DATE_WEEKDAYS:
        target_wd = _RELATIVE_DATE_WEEKDAYS[text[5:]]
        days_ahead = target_wd - today.weekday()
        if days_ahead <= 0:
            days_ahead += 7
        days_ahead += 7
        return (today + datetime.timedelta(days=days_ahead)).isoformat()
    if text == "next_week":
        days_to_monday = (7 - today.weekday()) % 7 or 7
        return (today + datetime.timedelta(days=days_to_monday)).isoformat()
    return value


def command_quick(args):
    config = _config(args)
    today = datetime.date.today()

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
    dest = args.append or config_write_file(config)
    file_directives = _load_file_directives(dest)
    apply_config_defaults_to_item(item, args, file_directives)
    apply_auto_id_to_item(item, args)
    line = item_to_assisted_line(item)

    if not args.no_check:
        parsed_items, diagnostics = parse_text(line + "\n")
        if not parsed_items:
            diagnostics.append(Diagnostic("error", "E301", "Generated line did not produce an item."))
        if _has_error(diagnostics):
            _print_diagnostics(diagnostics)
            return 1
        _print_warnings(diagnostics)

    if not dest:
        raise ValueError("No output file. Use --append FILE or configure write_file in config.")

    _pre_write_backup(dest, config, "quick")
    append_text(dest, line + "\n")
    sys.stdout.write("%s\n" % line)
    return 0


def command_done(args):
    config = _config(args)
    path = args.path
    if not path or path == "-":
        raise ValueError("done command requires a file path, not stdin.")
    text = read_text(path)
    id_key = id_key_from_config(config)
    items, _ = parse_text(text, id_key=id_key, check_ids=False, check_references=False)

    if args.line is not None:
        matches = [item for item in items if item.line == args.line]
        if not matches:
            raise ValueError("No item at line %d." % args.line)
        target = matches[0]
    elif args.id:
        matches = [
            item for item in items
            if args.id in [str(v) for v in item.details.get(id_key, [])]
        ]
        if not matches:
            raise ValueError("No item with %s:%s." % (id_key, args.id))
        if len(matches) > 1:
            raise ValueError("Multiple items with %s:%s." % (id_key, args.id))
        target = matches[0]
    elif args.text:
        query = args.text.lower()
        matches = [item for item in items if query in item.title.lower()]
        if not matches:
            raise ValueError("No item matching %r." % args.text)
        if len(matches) > 1:
            sys.stdout.write("Multiple items match:\n")
            for i, m in enumerate(matches):
                sys.stdout.write("  [%d] %s %s %s\n" % (i + 1, m.status, m.kind, m.title))
            sys.stdout.write("Mark which item done? (1-%d) " % len(matches))
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
        raise ValueError("Specify an ID, --line N, or --text QUERY.")

    if target.status == "[x]":
        sys.stdout.write("Already done: %s\n" % target.title)
        return 0

    today = datetime.date.today().isoformat()
    update_args = types.SimpleNamespace(
        line=target.line,
        match_id=None,
        status="[x]",
        kind=None,
        title=None,
        done=[today],
        detail=None,
        add_detail=None,
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

    dry_run = getattr(args, "dry_run", False)
    if dry_run:
        sys.stdout.write("[dry-run] Would mark done: %s\n" % updated_line)
        return 0

    _pre_write_backup(path, config, "done")
    atomic_write_text(path, updated_text)
    sys.stdout.write("Done: %s\n" % updated_line)
    return 0


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
        items, _ = parse_text(text, id_key=id_key, check_ids=False, check_references=False)

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
            mtime = datetime.datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%dT%H:%M")

        all_results.append(OrderedDict([
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
        ]))

    if args.format == "json":
        payload = all_results[0] if len(all_results) == 1 else all_results
        write_text(
            None,
            json.dumps(
                payload,
                ensure_ascii=False,
                indent=2 if args.pretty else None,
                separators=None if args.pretty else (",", ":"),
            ) + "\n",
        )
    else:
        for result in all_results:
            lines = ["Summary: %s" % result["source"]]
            lines.append("  Lines:    %d" % result["line_count"])
            lines.append("  Items:    %d" % result["item_count"])
            if result["type_counts"]:
                lines.append("  Types:    " + "  ".join(
                    "%s:%d" % (k, v) for k, v in sorted(result["type_counts"].items())
                ))
            if result["status_counts"]:
                lines.append("  Statuses: " + "  ".join(
                    "%s:%d" % (k.strip("[]"), v) for k, v in sorted(result["status_counts"].items())
                ))
            lines.append("  IDs (%s):  %d present, %d missing" % (
                result["id_key"], result["ids_present"], result["ids_missing"],
            ))
            if result["date_min"] or result["date_max"]:
                lines.append("  Dates:    %s .. %s" % (
                    result["date_min"] or "?", result["date_max"] or "?",
                ))
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
        sys.stdout.write("Undo history for %s (%d snapshot(s)):\n" % (path, len(entries)))
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

    atomic_write_text(path, content)
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

    today = datetime.date.today().isoformat()

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


def command_doctor(args):
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

    config = _config(args)
    arg_paths = getattr(args, "paths", None) or []
    life_paths = _normalize_paths(arg_paths, config, stdin_when_empty=False) or ["life.txt"]
    for path in life_paths:
        if not os.path.exists(path):
            add_check("FAIL", "life.txt", "Not found: %s -- run: lifetxt init" % path)
        elif not os.access(path, os.R_OK):
            add_check("FAIL", "life.txt", "Not readable: %s" % path)
        else:
            add_check("OK", "life.txt", "Found: %s" % path)

    config_path = getattr(args, "config", None) or ".lifetxt.json"
    if not os.path.exists(config_path):
        add_check("WARN", "config", "Not found: %s -- run: lifetxt config init" % config_path)
    else:
        add_check("OK", "config", "Found: %s" % config_path)

    import shutil
    for tool in ("fzf", "peco"):
        if shutil.which(tool):
            add_check("OK", tool, "Found in PATH")
        else:
            add_check("WARN", tool, "Not found (optional)")

    for pkg in ("textual", "watchdog", "matplotlib", "cryptography"):
        try:
            __import__(pkg)
            add_check("OK", pkg, "Installed")
        except ImportError:
            add_check("WARN", pkg, "Not installed (optional) -- pip install %s" % pkg)

    existing_paths = [p for p in life_paths if os.path.exists(p)]
    if existing_paths:
        items, diagnostics = _parse_life_inputs(existing_paths, config)
        errors = [d for d in diagnostics if d.severity == "error"]
        warnings_list = [d for d in diagnostics if d.severity == "warning"]
        if errors:
            add_check("FAIL", "check", "%d error(s) -- run: lifetxt check %s" % (len(errors), existing_paths[0]))
        elif warnings_list:
            add_check("WARN", "check", "%d warning(s) -- run: lifetxt check %s" % (len(warnings_list), existing_paths[0]))
        else:
            add_check("OK", "check", "%d item(s), no errors" % len(items))

        id_key = id_key_from_config(config)
        missing_count = sum(1 for item in items if not item.details.get(id_key))
        if missing_count:
            add_check("WARN", "ids", "%d item(s) missing %s: -- run: lifetxt ids --assign --dry-run %s" % (missing_count, id_key, existing_paths[0]))
        else:
            add_check("OK", "ids", "All items have %s:" % id_key)

    _fmt = getattr(args, "format", "text")
    _pretty = getattr(args, "pretty", False)
    if _fmt == "json":
        records = [OrderedDict([("status", s), ("check", l), ("message", m)]) for s, l, m in checks]
        write_text(None, json.dumps(records, ensure_ascii=False, indent=2 if _pretty else None, separators=None if _pretty else (",", ":")) + "\n")
    else:
        symbols = {"OK": "[OK]", "WARN": "[!!]", "FAIL": "[XX]"}
        for symbol, label, message in checks:
            write_text(None, "%s %-12s %s\n" % (symbols.get(symbol, symbol), label, message))

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
            item for item in items
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
                sys.stdout.write("  [%d] %s %s %s\n" % (i + 1, m.status, m.kind, m.title))
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

    _pre_write_backup(path, config, "assign")
    atomic_write_text(path, updated_text)
    sys.stdout.write("Assigned to %s: %s\n" % (args.to, updated_line))

    if args.notify:
        today = datetime.date.today().isoformat()
        sender = getattr(args, "from_user", None) or config_user_name(config) or "self"
        target_ids = target.details.get(id_key, [])
        ref_val = str(target_ids[0]) if target_ids else (item_id or "(no-id)")
        notif_line = "[ ] M Assigned_to_%s sender:%s recipient:%s ref:%s on:%s" % (
            args.to.replace(" ", "_"), sender, args.to, ref_val, today
        )
        append_text(path, notif_line + "\n")
        sys.stdout.write("Notification: %s\n" % notif_line)

    return 0


def command_health(args):
    config = _config(args)
    items, diagnostics = _parse_or_exit(args.paths, config)
    today = datetime.date.today()
    since_days = getattr(args, "since", 30)
    lookahead_days = getattr(args, "lookahead", 7)
    ignore_codes = set(c.upper() for c in _split_csv_args(getattr(args, "ignore", None)))
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
        dependency_records = dependency_blocker_records(items, key=id_key_from_config(config))

    for item in items:
        if type_filter and item.kind not in type_filter:
            continue
        location = getattr(item, "source", None)
        line_no = item.line

        if "W301" not in ignore_codes:
            if item.kind == "T" and item.status in open_statuses and item.status != "[>]":
                latest = _latest_item_date(item)
                if latest and (today - latest).days > since_days:
                    health_issues.append(OrderedDict([
                        ("code", "W301"),
                        ("message", "Task open for %d days without update" % (today - latest).days),
                        ("line", line_no),
                        ("source", location),
                        ("title", item.title),
                    ]))

        if "W302" not in ignore_codes:
            if item.kind == "H" and item.status in open_statuses:
                last_done = habit_completions.get(item.title)
                if last_done is None or (today - last_done).days > since_days:
                    health_issues.append(OrderedDict([
                        ("code", "W302"),
                        ("message", "Habit has no completion within %d days" % since_days),
                        ("line", line_no),
                        ("source", location),
                        ("title", item.title),
                    ]))

        if "W303" not in ignore_codes:
            if item.status in open_statuses:
                for val in item.details.get("due", []):
                    parsed = _parse_date_only(str(val))
                    if parsed:
                        days_until = (parsed - today).days
                        if days_until < 0:
                            health_issues.append(OrderedDict([
                                ("code", "W303"),
                                ("message", "Overdue by %d day(s) since %s" % (-days_until, val)),
                                ("line", line_no),
                                ("source", location),
                                ("title", item.title),
                            ]))
                        elif days_until <= lookahead_days:
                            health_issues.append(OrderedDict([
                                ("code", "W303"),
                                ("message", "Due in %d day(s) on %s" % (days_until, val)),
                                ("line", line_no),
                                ("source", location),
                                ("title", item.title),
                            ]))

        if "W304" not in ignore_codes:
            if item.status in open_statuses:
                for key in ("assignee", "owner"):
                    for val in item.details.get(key, []):
                        person = str(val)
                        if person not in recent_persons:
                            health_issues.append(OrderedDict([
                                ("code", "W304"),
                                ("message", "%s:%s has no recent S presence record within %d days" % (key, person, since_days)),
                                ("line", line_no),
                                ("source", location),
                                ("title", item.title),
                            ]))

    for record in dependency_records:
        health_issues.append(OrderedDict([
            ("code", "W305"),
            (
                "message",
                "Blocked by %s via %s"
                % (record["blocker_id"] or record["blocker_location"], record["relation"]),
            ),
            ("line", record["blocked_line"]),
            ("source", record["blocked_source"]),
            ("title", record["blocked_title"]),
            ("blocked_by", record["blocker_id"] or record["blocker_location"]),
            ("relation", record["relation"]),
        ]))

    _fmt = getattr(args, "format", "text")
    _pretty = getattr(args, "pretty", False)
    if _fmt == "json":
        write_text(None, json.dumps(health_issues, ensure_ascii=False, indent=2 if _pretty else None, separators=None if _pretty else (",", ":")) + "\n")
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
                write_text(None, "%s%s %s %s\n" % (prefix, issue["code"], issue["title"], issue["message"]))

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
                location = ("%s:%d" % (src, item.line)) if src else ("line:%d" % item.line)
                rows.append(OrderedDict([
                    ("location", location),
                    ("type", item.kind),
                    ("status", item.status),
                    ("title", item.title),
                ]))
            lines = ["Inbox: %d unclassified item(s)" % len(inbox_items)]
            lines.extend(_format_table(rows, ("location", "type", "status", "title")))
            write_text(None, "\n".join(lines) + "\n")

    _print_warnings(diagnostics)
    return 0


def command_cleanup(args):
    config = _config(args)
    ignore_codes = set(c.upper() for c in _split_csv_args(getattr(args, "ignore", None)))

    items, diagnostics = _parse_life_inputs(args.paths, config)
    errors = [d for d in diagnostics if d.severity == "error" and str(d.code).upper() not in ignore_codes]
    warnings_list = [d for d in diagnostics if d.severity == "warning" and str(d.code).upper() not in ignore_codes]
    path_label = " ".join(str(p) for p in (_normalize_paths(args.paths, config) or []))

    suggestions = []

    if errors:
        suggestions.append(OrderedDict([
            ("priority", 1), ("check", "errors"),
            ("count", len(errors)),
            ("message", "%d syntax/validation error(s)" % len(errors)),
            ("action", "lifetxt check %s" % path_label),
        ]))

    if warnings_list:
        suggestions.append(OrderedDict([
            ("priority", 2), ("check", "warnings"),
            ("count", len(warnings_list)),
            ("message", "%d warning(s)" % len(warnings_list)),
            ("action", "lifetxt check %s" % path_label),
        ]))

    id_key = id_key_from_config(config)
    missing_id_items = [item for item in items if not item.details.get(id_key)]
    if missing_id_items:
        suggestions.append(OrderedDict([
            ("priority", 3), ("check", "ids"),
            ("count", len(missing_id_items)),
            ("message", "%d item(s) missing %s:" % (len(missing_id_items), id_key)),
            ("action", "lifetxt ids --assign --dry-run %s" % path_label),
        ]))

    ref_issue_codes = {"W215", "W216", "W217", "W218"}
    ref_issues = [d for d in diagnostics if str(d.code).upper() in ref_issue_codes and str(d.code).upper() not in ignore_codes]
    if ref_issues:
        suggestions.append(OrderedDict([
            ("priority", 2), ("check", "links"),
            ("count", len(ref_issues)),
            ("message", "%d broken reference(s)" % len(ref_issues)),
            ("action", "lifetxt links %s" % path_label),
        ]))

    open_statuses = {"[ ]", "[/]", "[>]", "[?]"}
    inbox_count = sum(
        1 for item in items
        if item.kind == "T" and item.status in open_statuses
        and not item.details.get("project")
        and not item.details.get("due")
        and not item.details.get("assignee")
    )
    if inbox_count:
        suggestions.append(OrderedDict([
            ("priority", 4), ("check", "inbox"),
            ("count", inbox_count),
            ("message", "%d unclassified task(s) without project/due/assignee" % inbox_count),
            ("action", "lifetxt inbox %s" % path_label),
        ]))

    today_date = datetime.date.today()
    cutoff = today_date - datetime.timedelta(days=90)
    old_done_count = sum(
        1 for item in items
        if item.status in ("[x]", "[-]")
        and _archive_item_date_before(
            item,
            datetime.datetime.combine(cutoff, datetime.time.min),
        )
    )
    if old_done_count >= 10:
        suggestions.append(OrderedDict([
            ("priority", 5), ("check", "archive"),
            ("count", old_done_count),
            ("message", "%d completed/canceled item(s) older than 90 days" % old_done_count),
            ("action", "lifetxt archive --dest archive.txt --before %s --yes %s" % (
                cutoff.isoformat(), path_label,
            )),
        ]))

    _fmt = getattr(args, "format", "text")
    _pretty = getattr(args, "pretty", False)
    if _fmt == "json":
        write_text(None, json.dumps(suggestions, ensure_ascii=False, indent=2 if _pretty else None, separators=None if _pretty else (",", ":")) + "\n")
    else:
        if not suggestions:
            write_text(None, "OK: No cleanup actions needed.\n")
        else:
            write_text(None, "Cleanup suggestions (%d):\n" % len(suggestions))
            for sg in sorted(suggestions, key=lambda x: x["priority"]):
                write_text(None, "  [%d] %s: %s\n" % (sg["priority"], sg["check"], sg["message"]))
                write_text(None, "      Run: %s\n" % sg["action"])

    return 0


def command_review(args):
    import calendar as _calendar
    from .timeutil import parse_elapsed as _parse_elapsed

    config = _config(args)
    paths = _normalize_paths(getattr(args, "paths", None) or [], config)
    items, _ = _parse_life_inputs(paths, config)

    today = datetime.date.today()

    if getattr(args, "week", False):
        start = today - datetime.timedelta(days=today.weekday())
        end = start + datetime.timedelta(days=6)
    elif getattr(args, "month", None):
        try:
            year_s, month_s = args.month.split("-")
            year_i, month_i = int(year_s), int(month_s)
            start = datetime.date(year_i, month_i, 1)
            last_day = _calendar.monthrange(year_i, month_i)[1]
            end = datetime.date(year_i, month_i, last_day)
        except (ValueError, AttributeError):
            raise ValueError("Invalid --month format. Use YYYY-MM.")
    else:
        from_date = getattr(args, "from_date", None)
        to_date = getattr(args, "to_date", None)
        start = _parse_date_only(from_date) if from_date else today - datetime.timedelta(days=today.weekday())
        end = _parse_date_only(to_date) if to_date else today

    project_filter = getattr(args, "project", None)
    if project_filter:
        items = [i for i in items if project_filter in [str(v) for v in i.details.get("project", [])]]

    completed_tasks = []
    open_tasks = []
    habits = {}
    journal_entries = []
    journal_count = 0
    moods = []
    elapsed_by_project = {}

    for item in items:
        if item.kind == "T":
            if item.status == "[x]":
                done_dates = [_parse_date_only(str(v)) for v in item.details.get("done", [])]
                in_range = any(
                    d and d >= start and d <= end for d in done_dates
                ) if done_dates else False
                if in_range:
                    completed_tasks.append(item)
            elif item.status in ("[ ]", "[/]", "[>]", "[?]"):
                open_tasks.append(item)

        elif item.kind == "H":
            title = item.title
            if title not in habits:
                habits[title] = {"done": 0, "open": 0}
            if item.status == "[x]":
                habits[title]["done"] += 1
            elif item.status in ("[ ]", "[/]"):
                habits[title]["open"] += 1

        elif item.kind == "J":
            j_date = _latest_item_date(item) or today
            if j_date >= start and j_date <= end:
                journal_count += 1
                body_vals = item.details.get("body", [])
                excerpt = str(body_vals[0])[:200] if body_vals else ""
                journal_entries.append((j_date, item.title, excerpt))
                mood_vals = item.details.get("mood", [])
                if mood_vals:
                    moods.append((j_date, str(mood_vals[0])))

        elapsed_vals = item.details.get("elapsed", [])
        if elapsed_vals:
            minutes = _parse_elapsed(str(elapsed_vals[0]))
            if minutes:
                proj = str(item.details.get("project", ["(no project)"])[0])
                elapsed_by_project[proj] = elapsed_by_project.get(proj, 0) + minutes

    def _fmt_elapsed(m):
        if m >= 60:
            return "%dh%dm" % (m // 60, m % 60)
        return "%dm" % m

    result = {
        "range": "%s to %s" % (start.isoformat(), end.isoformat()),
        "completed_tasks": len(completed_tasks),
        "open_tasks": len(open_tasks),
        "habits": {
            title: {
                "done": h["done"],
                "open": h["open"],
                "completion_rate": (
                    round(h["done"] / (h["done"] + h["open"]) * 100)
                    if (h["done"] + h["open"] > 0) else 0
                ),
            }
            for title, h in habits.items()
        },
        "journals": journal_count,
        "journal_entries": [
            {"date": d.isoformat(), "title": t, "excerpt": e}
            for d, t, e in sorted(journal_entries)
        ],
        "mood_trend": [
            {"date": d.isoformat(), "mood": m} for d, m in sorted(moods)
        ],
        "elapsed_by_project": {
            proj: _fmt_elapsed(m)
            for proj, m in sorted(elapsed_by_project.items(), key=lambda x: -x[1])
        },
    }

    fmt = getattr(args, "format", "text") or "text"
    if fmt == "json":
        indent = 2 if getattr(args, "pretty", False) else None
        sys.stdout.write(json.dumps(result, ensure_ascii=False, indent=indent) + "\n")
        return 0
    if fmt == "jsonl":
        sys.stdout.write(json.dumps(result, ensure_ascii=False, separators=(",", ":")) + "\n")
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
                done_val = str(t.details.get("done", [""])[0]) if t.details.get("done") else ""
                lines.append("- [x] %s%s" % (t.title, (" (%s)" % done_val) if done_val else ""))
        if result["habits"]:
            lines.append("")
            lines.append("## Habits")
            for title, h in result["habits"].items():
                bar = "#" * h["done"] + "." * h["open"]
                lines.append("- **%s**: %d/%d (%d%%) %s" % (
                    title, h["done"], h["done"] + h["open"], h["completion_rate"], bar,
                ))
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
        for j_date, title, excerpt in sorted(journal_entries):
            sys.stdout.write("  %s %s\n" % (j_date.isoformat(), title))
            if excerpt:
                sys.stdout.write("    %s\n" % excerpt)

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
    else:
        write_text(args.output, _items_to_life_text(items, canonical=args.canonical, key=id_key))

    _print_warnings(diagnostics)
    return 0


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
            OrderedDict([
                ("source", getattr(item, "source", None)),
                ("line", item.line),
                ("status", item.status),
                ("type", item.kind),
                ("title", item.title),
                ("match_field", field),
            ])
            for item, field in results
        ]
        write_text(None, json.dumps(
            data, ensure_ascii=False,
            indent=2 if args.pretty else None,
            separators=None if args.pretty else (",", ":"),
        ) + "\n")
    elif args.format == "jsonl":
        for item, field in results:
            write_text(None, json.dumps(
                OrderedDict([
                    ("source", getattr(item, "source", None)),
                    ("line", item.line),
                    ("status", item.status),
                    ("type", item.kind),
                    ("title", item.title),
                    ("match_field", field),
                ]),
                ensure_ascii=False, separators=(",", ":"),
            ) + "\n")
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
                loc = ("%s:%d" % (source, line)) if source and line else ("line %d" % line if line else "?")
                title = item.title
                if highlight:
                    if use_regex:
                        title = compiled.sub("\033[1;33m\\g<0>\033[0m", title)
                    else:
                        idx = title.lower().find(pat_lower)
                        if idx >= 0:
                            title = title[:idx] + "\033[1;33m" + title[idx:idx + len(pattern)] + "\033[0m" + title[idx + len(pattern):]
                write_text(None, "%s  %s %s %s\n" % (loc, item.status, item.kind, title))

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
    a = _summary_single(primary_paths[0] if len(primary_paths) == 1 else primary_paths[0], config)
    b = _summary_single(compare_path, config)

    def _col(label, a_val, b_val):
        delta = ""
        try:
            diff = int(b_val) - int(a_val)
            delta = " (%+d)" % diff if diff != 0 else ""
        except (TypeError, ValueError):
            pass
        sys.stdout.write("  %-14s %-20s %-20s%s\n" % (label, str(a_val), str(b_val), delta))

    sys.stdout.write("%-14s %-20s %-20s\n" % ("", os.path.basename(a["source"]), os.path.basename(b["source"])))
    sys.stdout.write("-" * 60 + "\n")
    _col("Lines:", a["lines"], b["lines"])
    _col("Items:", a["items"], b["items"])
    all_types = sorted(set(list(a["type_counts"].keys()) + list(b["type_counts"].keys())))
    for t in all_types:
        _col("  Type %s:" % t, a["type_counts"].get(t, 0), b["type_counts"].get(t, 0))
    all_statuses = sorted(set(list(a["status_counts"].keys()) + list(b["status_counts"].keys())))
    for s in all_statuses:
        label = s.strip("[]")
        _col("  [%s]:" % label, a["status_counts"].get(s, 0), b["status_counts"].get(s, 0))
    _col("IDs present:", a["ids_present"], b["ids_present"])
    _col("IDs missing:", a["ids_missing"], b["ids_missing"])


def command_diff(args):
    config = _config(args)
    id_key = id_key_from_config(config)

    before_text = read_text(args.before)
    after_text = read_text(args.after)
    before_items, _ = parse_text(before_text, id_key=id_key, check_ids=False, check_references=False)
    after_items, _ = parse_text(after_text, id_key=id_key, check_ids=False, check_references=False)

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
        changes.append(OrderedDict([
            ("change", "added"),
            ("title", item.title),
            ("type", item.kind),
            ("status", item.status),
            ("line", item.line),
            ("source", getattr(item, "source", None)),
        ]))

    for key in sorted(before_keys - after_keys, key=lambda k: k[1]):
        item = before_map[key]
        if not _item_passes_filter(item):
            continue
        changes.append(OrderedDict([
            ("change", "removed"),
            ("title", item.title),
            ("type", item.kind),
            ("status", item.status),
            ("line", item.line),
            ("source", getattr(item, "source", None)),
        ]))

    for key in sorted(before_keys & after_keys, key=lambda k: k[1]):
        b = before_map[key]
        a = after_map[key]
        if not _item_passes_filter(b):
            continue
        if b.status != a.status:
            change_type = "completed" if a.status == "[x]" else (
                "canceled" if a.status == "[-]" else "status-changed"
            )
            changes.append(OrderedDict([
                ("change", change_type),
                ("title", a.title),
                ("type", a.kind),
                ("before", b.status),
                ("after", a.status),
                ("line", a.line),
                ("source", getattr(a, "source", None)),
            ]))
        elif b.details != a.details:
            changed_keys = []
            all_keys = set(list(b.details.keys()) + list(a.details.keys()))
            for dk in all_keys:
                bv = b.details.get(dk, [])
                av = a.details.get(dk, [])
                if bv != av:
                    changed_keys.append(dk)
            changes.append(OrderedDict([
                ("change", "detail-changed"),
                ("title", a.title),
                ("type", a.kind),
                ("changed_keys", changed_keys),
                ("line", a.line),
                ("source", getattr(a, "source", None)),
            ]))

    if change_type_filter:
        changes = [c for c in changes if c.get("change") in change_type_filter]

    fmt = getattr(args, "format", "text")
    if fmt == "json":
        write_text(None, json.dumps(changes, ensure_ascii=False, indent=2 if args.pretty else None,
                                    separators=None if args.pretty else (",", ":")) + "\n")
    elif fmt == "jsonl":
        for c in changes:
            write_text(None, json.dumps(c, ensure_ascii=False, separators=(",", ":")) + "\n")
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
                write_text(None, "%s[%s] %s (%s)%s\033[0m\n" % (pfx, change, title, ctype, extra))

    return 0 if not changes else 0


def _plot_bar(value, max_value, width=40, char="#"):
    if max_value == 0:
        return ""
    filled = int(round(value / max_value * width))
    return char * filled + "." * (width - filled)


def command_plot(args):
    from .timeutil import parse_elapsed as _parse_elapsed

    config = _config(args)
    paths = _normalize_paths(getattr(args, "paths", None) or [], config) or ["life.txt"]
    items, _ = _parse_life_inputs(paths, config)

    chart = getattr(args, "chart", "all")
    group = getattr(args, "group", "weekly")
    project_filter = getattr(args, "project", None)
    term_width = getattr(args, "width", 0)
    if not term_width:
        try:
            term_width = os.get_terminal_size().columns
        except OSError:
            term_width = 80
    bar_width = max(10, min(40, term_width - 30))

    start_str = getattr(args, "start", None)
    end_str = getattr(args, "end", None)
    today = datetime.date.today()
    start = _parse_date_only(start_str) if start_str else (today - datetime.timedelta(days=90))
    end = _parse_date_only(end_str) if end_str else today

    if project_filter:
        items = [i for i in items if project_filter in [str(v) for v in i.details.get("project", [])]]

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
        _print_bar_chart("Habit Completions (total, %s to %s)" % (start, end), habit_counts)

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
            sys.stdout.write("\n## Elapsed Time by Project\n")
            max_v = max(proj_elapsed.values())
            for proj, minutes in sorted(proj_elapsed.items(), key=lambda x: -x[1]):
                bar = _plot_bar(minutes, max_v, width=bar_width)
                h, m = divmod(minutes, 60)
                label = ("%dh%dm" % (h, m)) if h else ("%dm" % m)
                sys.stdout.write("  %-14s %s %s\n" % (proj[:14], bar, label))

    sys.stdout.write("\n")
    return 0


def command_migrate(args):
    """Apply in-place format migrations to a life.txt file."""
    import re as _re
    from .timeutil import parse_elapsed as _parse_elapsed, format_elapsed as _format_elapsed

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
                new_line = _re.sub(r'elapsed:(\S+)', _repl_elapsed, line)
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
                    r'\b' + _re.escape(old_key) + r':',
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
            parsed_items, _ = parse_text(text, id_key=id_key, check_ids=False, check_references=False)
            lines = text.splitlines(keepends=True)
            import secrets as _secrets
            for item in parsed_items:
                if not item.details.get(id_key):
                    if item.line and 0 < item.line <= len(lines):
                        new_id = _secrets.token_hex(4)
                        lines[item.line - 1] = lines[item.line - 1].rstrip("\n").rstrip("\r") + (
                            "  %s:%s\n" % (id_key, new_id)
                        )
                        total_changes += 1
            text = "".join(lines)

        else:
            sys.stderr.write("ERROR: Unknown migration %r. Known: normalize-elapsed, rename-key OLD=NEW, add-id.\n" % name)
            return 1

    dry_run = getattr(args, "dry_run", False)
    if dry_run:
        if text == original_text:
            sys.stdout.write("No changes would be made.\n")
        else:
            import difflib
            diff = list(difflib.unified_diff(
                original_text.splitlines(keepends=True),
                text.splitlines(keepends=True),
                fromfile=path + " (before)",
                tofile=path + " (after)",
            ))
            sys.stdout.write("".join(diff[:60]))
            if len(diff) > 60:
                sys.stdout.write("... (%d more lines)\n" % (len(diff) - 60))
        sys.stdout.write("[dry-run] %d change(s) would be applied.\n" % total_changes)
        return 0

    if text == original_text:
        sys.stdout.write("No changes made.\n")
        return 0

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
    import re as _re
    paths = args.paths if args.paths else ["-"]
    project = getattr(args, "project", None)
    kind = getattr(args, "kind", "T") or "T"
    do_append = getattr(args, "append", False)
    output_path = getattr(args, "output", None)

    STATUS_MAP = {
        " ": "[ ]",
        "x": "[x]",
        "X": "[x]",
        "-": "[-]",
        "/": "[/]",
    }
    MD_TASK_RE = _re.compile(
        r'^(?P<indent>\s*)[-*+]\s+\[(?P<check>[xX \-/])\]\s+(?P<title>.+)$'
    )

    items = []
    for path in paths:
        text = read_text(path)
        for line in text.splitlines():
            m = MD_TASK_RE.match(line)
            if not m:
                continue
            check = m.group("check")
            title = m.group("title").strip()
            status = STATUS_MAP.get(check, "[ ]")
            title_slug = title.replace(" ", "_")
            details = {}
            if project:
                details["project"] = [project]
            items.append(Item(status, kind, title_slug, details))

    if not items:
        sys.stderr.write("WARNING: No Markdown task list items found.\n")
        return 0

    life_lines = []
    for item in items:
        parts = ["%s %s %s" % (item.status, item.kind, item.title)]
        for k, vals in item.details.items():
            for v in vals:
                parts[0] += "  %s:%s" % (k, v)
        life_lines.append(parts[0])
    output = "\n".join(life_lines) + "\n"

    if output_path:
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
        date_prefix = datetime.date.today().isoformat()
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
            (f for f in os.listdir(snap_dir_for_diff)
             if f.endswith("_" + basename_for_diff) and f != os.path.basename(dest)),
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
    "proj": "project", "projects": "project",
    "date": "due", "deadline": "due",
    "assign": "assignee", "assigned": "assignee", "assigned_to": "assignee",
    "owners": "owner",
    "tags": "tag",
    "bodies": "body",
    "note": "note",  # not a typo but capture for casing
    "prio": "priority", "priorities": "priority",
    "loc": "loc",  # fine, keep
    "attend": "attendee", "attendees": "attendee",
    "ref_id": "id", "item_id": "id",
    "do_by": "due",
    "scheduled": "do",
    "repeat_every": "repeat",
    "interval": "interval",
    "until": "until",
    "count": "count",
    "depend": "depends_on", "dep": "depends_on", "dependency": "depends_on",
    "block": "blocks",
    "related_to": "related",
    "mood_score": "mood",
    "elapsed_time": "elapsed", "spent": "elapsed",
    "estimate": "est",
    "sender_email": "sender",
    "recipient_email": "recipient",
    "notify": "notify_at",
}
# Non-canonical casings to flag
_LINT_CASING_VARIANTS = {
    k.upper(): k for k in list(_LINT_KEY_VARIANTS.values()) + list(_LINT_KEY_VARIANTS.keys())
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
        items, parse_diags = parse_text(text, id_key=id_key, check_ids=False, check_references=False)
        for item in items:
            for key in list(item.details.keys()):
                canonical = _LINT_KEY_VARIANTS.get(key)
                if canonical and canonical != key:
                    issues.append(OrderedDict([
                        ("source", getattr(item, "source", path) or path),
                        ("line", item.line),
                        ("code", "L001"),
                        ("severity", "warning"),
                        ("message", "Key %r looks like a typo for %r." % (key, canonical)),
                        ("fix", canonical),
                        ("key", key),
                    ]))
                elif key.upper() == key and key.lower() in _LINT_KEY_VARIANTS:
                    issues.append(OrderedDict([
                        ("source", getattr(item, "source", path) or path),
                        ("line", item.line),
                        ("code", "L002"),
                        ("severity", "warning"),
                        ("message", "Key %r uses non-standard casing; expected %r." % (key, key.lower())),
                        ("fix", key.lower()),
                        ("key", key),
                    ]))
            # Check for duplicate keys
            seen = {}
            for key in item.details.keys():
                seen[key] = seen.get(key, 0) + 1
            for key, n in seen.items():
                if n > 1:
                    issues.append(OrderedDict([
                        ("source", getattr(item, "source", path) or path),
                        ("line", item.line),
                        ("code", "L003"),
                        ("severity", "warning"),
                        ("message", "Duplicate key %r (%d values). Consider using a multi-value list." % (key, n)),
                        ("fix", None),
                        ("key", key),
                    ]))

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
            sys.stderr.write("ERROR: Cannot load ruleset %r: %s\n" % (ruleset_file, exc))
            return 2
        for path in paths:
            text = path_texts.get(path, read_text(path))
            path_items, _ = parse_text(text, id_key=id_key, check_ids=False, check_references=False)
            for item in path_items:
                for key in item.details.keys():
                    for rule in custom_rules:
                        pattern = rule.get("pattern", "")
                        replacement = rule.get("replacement")
                        message = rule.get("message", "Key %r matches custom rule." % key)
                        import re as _re2
                        if _re2.fullmatch(pattern, key):
                            issues.append(OrderedDict([
                                ("source", getattr(item, "source", path) or path),
                                ("line", item.line),
                                ("code", "L100"),
                                ("severity", "warning"),
                                ("message", message.replace("{key}", key)),
                                ("fix", replacement),
                                ("key", key),
                            ]))

    # --fix: auto-rename typo keys in fixable issues (L001, L002)
    if do_fix:
        fixable = [i for i in issues if i.get("fix") and i.get("code") in ("L001", "L002")]
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
                        r'\b' + _re.escape(old_key) + r':',
                        new_key + ":",
                        lines[ln - 1],
                    )
                    fixed_count += 1
            new_text = "".join(lines)
            atomic_write_text(path, new_text)
        sys.stdout.write("Fixed %d issue(s) in %d file(s).\n" % (fixed_count, len(by_path)))
        # Re-run lint to report remaining issues
        remaining = [i for i in issues if i.get("code") == "L003" or not i.get("fix")]
        return 1 if remaining else 0

    if args.format == "json":
        write_text(None, json.dumps(
            issues, ensure_ascii=False,
            indent=2 if args.pretty else None,
            separators=None if args.pretty else (",", ":"),
        ) + "\n")
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
                fix_hint = " (fix: %r -> %r)" % (issue.get("key", ""), fix) if fix else ""
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
        return watch_notifications(
            load_records,
            interval_seconds=interval,
            desktop=desktop,
            once=False,
            state_file=state_file,
        )

    records = load_records()
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


def command_agenda(args):
    items, diagnostics = _parse_or_exit(args.paths, _config(args))
    range_start, range_end = parse_agenda_range(
        start_text=args.start,
        end_text=args.end,
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
        write_text(args.output, format_agenda_table(records))

    _print_warnings(diagnostics)
    return 0


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
        append_line(args.append, line)
    if args.output:
        append_line(args.output, line)
    write_text(None, line + "\n")
    return 0


def command_config_init(args):
    if os.path.exists(args.output) and not args.force:
        raise ValueError("Config file already exists. Use --force to overwrite: %s" % args.output)
    write_text(args.output, config_template_text())
    write_text(None, "Wrote %s\n" % args.output)
    return 0


def command_config_show(args):
    output = json.dumps(_public_config(_config(args)), ensure_ascii=False, indent=2)
    write_text(None, output + "\n")
    return 0


def command_tui(args):
    args.paths = _normalize_paths(args.paths, _config(args), stdin_when_empty=False) or ["life.txt"]
    from .tui import cmd_tui
    return cmd_tui(args)


def command_fzf(args):
    args.paths = _normalize_paths(args.paths, _config(args), stdin_when_empty=False) or ["life.txt"]
    from .fzf_helper import cmd_fzf
    return cmd_fzf(args)


def command_timer(args):
    config = _config(args)
    if getattr(args, "timer_command", None) == "summary":
        args.paths = _normalize_paths(args.paths, config, stdin_when_empty=False)
    elif getattr(args, "timer_command", None) == "status" and getattr(args, "paths", None):
        args.paths = _normalize_paths(args.paths, config, stdin_when_empty=False)
    from .timer import cmd_timer
    return cmd_timer(args)


def command_stats(args):
    args.paths = _normalize_paths(args.paths, _config(args), stdin_when_empty=False) or ["life.txt"]
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
        raise ValueError("--append is only for creating new items. Use --output for update copies.")
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
            raise ValueError("Cannot assign IDs because %s has validation errors." % path)
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
                    ("locations", "; ".join(item["location"] for item in record["items"])),
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
                    ("locations", "; ".join(item["location"] for item in record["items"])),
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
        lines.append(_format_table_row([row.get(column, "") for column in columns], widths))
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
    for key in ("key", "total_items", "id_count", "duplicate_count", "cross_file_duplicate_count", "missing_count"):
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
                    ("cross_file_duplicate_count", audit.get("cross_file_duplicate_count", 0)),
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
    lines.extend(_format_table(rows, ("source", "line", "id", "parent", "type", "status", "title")))
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
        child_ids = ", ".join(
            str(v)
            for c in open_children
            for v in c.details.get(key, [])
        ) or "(no id)"
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
    directory = os.path.dirname(os.path.abspath(path)) or "."
    handle = None
    temp_path = None
    try:
        handle = tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            newline="\n",
            delete=False,
            dir=directory,
            prefix=".lifetxt-",
            suffix=".tmp",
        )
        temp_path = handle.name
        handle.write(text)
        handle.close()
        os.replace(temp_path, path)
    finally:
        if handle is not None and not handle.closed:
            handle.close()
        if temp_path and os.path.exists(temp_path):
            try:
                os.unlink(temp_path)
            except OSError:
                pass


def write_bytes(path, data):
    ensure_parent_dir(path)
    with open(path, "wb") as handle:
        handle.write(data)


def ensure_parent_dir(path):
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)


def append_line(path, line):
    append_text(path, line + "\n")


def append_text(path, text):
    if not text:
        return
    existing = ""
    try:
        existing = read_text(path)
    except FileNotFoundError:
        pass
    prefix = "\n" if existing and not existing.endswith(("\n", "\r")) else ""
    atomic_write_text(path, existing + prefix + text)


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

    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
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
        raise ValueError(
            "Failed to fetch iCalendar source #%d: %s." % (index, exc)
        )


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
                raise ValueError("Environment variable %s is not set or empty." % env_name)
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


def filter_diagnostics(diagnostics, severities=None, codes=None, categories=None, ignore_codes=None):
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


def diagnostic_to_output_dict(diagnostic):
    data = diagnostic.to_dict()
    output = OrderedDict()
    for key, value in data.items():
        output[key] = value
        if key == "code":
            output["category"] = diagnostic_category(diagnostic)
    return output


def diagnostic_category(diagnostic):
    code = str(getattr(diagnostic, "code", "") or "").upper()
    if code.startswith("E0"):
        return "syntax"
    if code in ("E101", "E102"):
        return "schema"
    if code in ("E201", "E202", "E203", "E204", "W207", "W208", "W209"):
        return "status"
    if code in ("E205", "E206", "W210", "W211", "W212"):
        return "message"
    if code in ("W105", "W106"):
        return "style"
    if code in ("W201", "W202", "W203", "W204", "W206"):
        return "time"
    if code in ("W205", "W219", "W223"):
        return "recurrence"
    if code in ("W213", "W214"):
        return "id"
    if code in ("W215", "W216", "W217", "W218"):
        return "reference"
    if code in ("W101", "W102", "W103", "W104", "W224"):
        return "workflow"
    if code == "W222":
        return "duration"
    return "semantic"


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
    from .links import build_id_index, item_id_values
    config = _config(args)
    id_key = id_key_from_config(config)
    paths = args.paths if args.paths else ["-"]
    items, diags = _parse_or_exit(paths, config)
    _print_warnings(diags)
    id_index = build_id_index(items, id_key=id_key)

    def _id(item):
        vals = item_id_values(item, id_key)
        return vals[0] if vals else None

    def _deps(item):
        return list(item.details.get("depends_on", []))

    def _is_open(item):
        return item.status not in ("[x]", "[-]")

    all_ids = {_id(i): i for i in items if _id(i)}
    root_id = getattr(args, "root", None)
    blocked_only = getattr(args, "blocked", False)

    def _collect(item_id, visited=None):
        if visited is None:
            visited = set()
        if item_id in visited:
            return []
        visited.add(item_id)
        item = all_ids.get(item_id)
        if not item:
            return [{"id": item_id, "title": "(unknown)", "status": "?", "type": "?", "deps": []}]
        dep_ids = _deps(item)
        dep_nodes = []
        for dep_id in dep_ids:
            dep_nodes.extend(_collect(dep_id, visited))
        return [{"id": item_id, "title": item.title, "status": item.status,
                 "type": item.kind, "deps": dep_nodes}]

    if root_id:
        roots = _collect(root_id)
    else:
        roots = []
        for item in items:
            if blocked_only and not any(_is_open(all_ids[d]) for d in _deps(item) if d in all_ids):
                continue
            item_id = _id(item)
            if not item_id:
                continue
            dep_ids = _deps(item)
            if not dep_ids:
                continue
            roots.append(_collect(item_id)[0])

    if args.format == "json":
        write_text(None, json.dumps(roots, ensure_ascii=False,
                                    indent=2 if args.pretty else None,
                                    separators=None if args.pretty else (",", ":")) + "\n")
        return 0

    def _print_node(node, depth=0):
        indent = "  " * depth
        status = node.get("status", "?")
        title = node.get("title", "")
        item_id = node.get("id", "")
        sys.stdout.write("%s%s [%s] %s\n" % (indent, item_id, status, title))
        for dep in node.get("deps", []):
            _print_node(dep, depth + 1)

    if not roots:
        sys.stdout.write("No dependency chains found.\n")
    else:
        for root in roots:
            _print_node(root)
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
        write_text(None, json.dumps([{"tag": t, "count": c} for t, c in sorted_tags],
                                     ensure_ascii=False, indent=2) + "\n")
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
    id_key = id_key_from_config(_config(args) if hasattr(args, "config") else {})
    items, _ = parse_text(text, id_key=id_key, check_ids=False, check_references=False)
    lines = text.splitlines(keepends=True)
    changed = 0
    import re as _re
    for item in items:
        if old_tag in item.details.get("tag", []):
            ln = item.line
            if ln and 0 < ln <= len(lines):
                new_line = _re.sub(
                    r'(\btag:\s*)' + _re.escape(old_tag) + r'(\b|$)',
                    r'\g<1>' + new_tag,
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
        sys.stdout.write("Would rename %d occurrence(s) of tag %r -> %r in %s.\n" % (changed, old_tag, new_tag, path))
    else:
        atomic_write_text(path, new_text)
        sys.stdout.write("Renamed %d occurrence(s) of tag %r -> %r in %s.\n" % (changed, old_tag, new_tag, path))
    return 0


def command_watch(args):
    import time
    paths = args.paths if args.paths else ["-"]
    run_cmd = getattr(args, "run", "summary")
    interval = getattr(args, "interval", 1.0)
    do_clear = getattr(args, "clear", False)

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
        try:
            subprocess.run(cmd)
        except Exception as exc:
            sys.stderr.write("Watch run error: %s\n" % exc)

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
