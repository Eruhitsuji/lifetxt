import argparse
import hashlib
import json
import os
import sys
import tempfile
from collections import OrderedDict
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .config import (
    config_notification_recipient,
    config_paths,
    config_section,
    config_template_text,
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
from .model import Diagnostic
from .notifier import (
    format_notification_table,
    notification_records,
    records_to_json as notifications_to_json,
    records_to_jsonl as notifications_to_jsonl,
    watch_notifications,
)
from .parser import parse_line, parse_text
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
        argv, config_path = _extract_config_arg(argv)
    except ValueError as exc:
        sys.stderr.write("ERROR: %s\n" % exc)
        return 1
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
    ids_command.set_defaults(func=command_ids)

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
        help="Regenerate life.txt lines instead of preserving original item lines.",
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
        help="Range start: now, YYYY-MM-DD, or YYYY-MM-DDTHH:MM.",
    )
    agenda.add_argument(
        "--to",
        dest="end",
        help="Range end: now, YYYY-MM-DD, or YYYY-MM-DDTHH:MM.",
    )
    agenda.add_argument(
        "--around",
        help="Center of a range: now, YYYY-MM-DD, or YYYY-MM-DDTHH:MM. Defaults to now.",
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
    from_json.set_defaults(func=command_from_json)

    from_jsonl = subparsers.add_parser("from-jsonl", help="Convert JSONL to life.txt.")
    _add_input_paths(from_jsonl)
    from_jsonl.add_argument("-o", "--output", help="Output file. Defaults to stdout.")
    from_jsonl.set_defaults(func=command_from_jsonl)

    assist = subparsers.add_parser(
        "assist", help="Create a life.txt line interactively or from flags."
    )
    assist.add_argument("-i", "--interactive", action="store_true", help="Prompt for fields.")
    assist.add_argument("-s", "--status", help="Status or alias, e.g. '[ ]', done, note.")
    assist.add_argument(
        "-t",
        "--type",
        dest="kind",
        help="Type or alias, e.g. T, task, event, note.",
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
        help="Keep items related to this time or later: now, YYYY-MM-DD, or YYYY-MM-DDTHH:MM.",
    )
    parser.add_argument(
        "--before",
        help="Keep items related to this time or earlier: now, YYYY-MM-DD, or YYYY-MM-DDTHH:MM.",
    )


def command_check(args):
    items, diagnostics = _parse_life_inputs(args.paths, _config(args))

    if args.format == "json":
        output = json.dumps(
            [diagnostic.to_dict() for diagnostic in diagnostics],
            ensure_ascii=False,
            indent=2,
        )
        write_text(None, output + "\n")
    else:
        if diagnostics:
            for diagnostic in diagnostics:
                write_text(None, diagnostic.format() + "\n")
        else:
            write_text(None, "OK: %d item(s)\n" % len(items))

    return _exit_code(diagnostics, args.warnings_as_errors)


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


def command_ids_assign(args):
    key = args.key or id_key_from_config(_config(args))
    records = assign_missing_ids(args.paths, _config(args), key, args.dry_run, args.backup)

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
    paths = list(args.paths) if args.paths else config_paths(_config(args)) or ["life.txt"]
    writable_path = args.write_file or config_write_file(_config(args)) or paths[0]
    host = args.host or web_config.get("host") or "127.0.0.1"
    port = args.port or int(web_config.get("port") or 8000)
    app = create_app(paths=paths, writable_path=writable_path, config=_config(args))
    uvicorn.run(app, host=host, port=port)
    return 0


def command_filter(args):
    items, diagnostics = _parse_or_exit(args.paths, _config(args))
    items = _filter_items_from_args(items, args)

    if args.format == "json":
        output = items_to_json(items, pretty=args.pretty)
        write_text(args.output, output + "\n")
    elif args.format == "jsonl":
        output = items_to_jsonl(items)
        if output:
            output += "\n"
        write_text(args.output, output)
    else:
        write_text(args.output, _items_to_life_text(items, canonical=args.canonical))

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
        persons=args.person,
        owners=args.owner,
        assignees=args.assignee,
        attendees=args.attendee,
        senders=args.sender,
        recipients=args.recipient,
        detail_filters=args.detail,
        text=args.text,
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
    return _write_life_items(items, args.output)


def command_from_jsonl(args):
    items = _items_from_jsonl_paths(args.paths)
    return _write_life_items(items, args.output)


def command_assist(args):
    if args.update:
        return command_assist_update(args)

    if args.output and args.append:
        raise ValueError("Use either --output or --append, not both.")

    if args.interactive or not args.title:
        item = prompt_item(args)
    else:
        item = build_item_from_args(args)
    apply_config_defaults_to_item(item, args)
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


def _write_life_items(items, output):
    text = _validated_life_text_or_exit(items)
    if text is None:
        return 1
    write_text(output, text)
    return 0


def _validated_life_text_or_exit(items):
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


def _items_to_life_text(items, canonical=False):
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


def format_id_audit(audit, only="all"):
    lines = []
    lines.append(
        "ID audit (%s): %d item(s), %d id(s), %d duplicate id(s), %d missing id item(s)"
        % (
            audit.get("key", "id"),
            audit.get("total_items", 0),
            audit.get("id_count", 0),
            audit.get("duplicate_count", 0),
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


def assign_missing_ids(paths, config, key, dry_run=False, backup=False):
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
        )
        records.extend(path_records)
        if changed and not dry_run:
            if backup:
                write_text(path + ".bak", text)
            write_text(path, new_text)
    return records


def _assign_missing_ids_in_text(path, text, key, existing, config):
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
            prefix=id_prefix_for_item(item, config),
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
        rows.append(
            OrderedDict(
                [
                    ("id", record["id"]),
                    ("count", str(record["count"])),
                    ("locations", "; ".join(item["location"] for item in record["items"])),
                    ("titles", "; ".join(item["title"] for item in record["items"])),
                ]
            )
        )
    return lines + _format_table(rows, ("id", "count", "locations", "titles"))


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
    for key in ("key", "total_items", "id_count", "duplicate_count", "missing_count"):
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


def _parse_or_exit(paths, config=None):
    items, diagnostics = _parse_life_inputs(paths, config)
    if _has_error(diagnostics):
        _print_diagnostics(diagnostics)
        raise SystemExit(1)
    return items, diagnostics


def _parse_life_inputs(paths, config=None):
    normalized = _normalize_paths(paths, config)
    include_source = len(normalized) > 1
    items = []
    diagnostics = []
    for path in normalized:
        text = read_text(path)
        path_items, path_diagnostics = parse_text(text)
        if include_source:
            source = "stdin" if path == "-" else path
            _set_source(path_items, path_diagnostics, source)
        items.extend(path_items)
        diagnostics.extend(path_diagnostics)
    if include_source:
        diagnostics.extend(
            duplicate_id_diagnostics(
                items,
                key=id_key_from_config(config or {}),
                cross_source_only=True,
            )
        )
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
    return filter_items(
        items,
        open_only=getattr(args, "open", False),
        statuses=getattr(args, "status", None),
        kinds=getattr(args, "kinds", None),
        projects=getattr(args, "project", None),
        tags=getattr(args, "tag", None),
        persons=getattr(args, "person", None),
        owners=getattr(args, "owner", None),
        assignees=getattr(args, "assignee", None),
        attendees=getattr(args, "attendee", None),
        senders=getattr(args, "sender", None),
        recipients=getattr(args, "recipient", None),
        detail_filters=getattr(args, "detail", None),
        text=getattr(args, "text", None),
        range_start=range_start,
        range_end=range_end,
    )


def apply_config_defaults_to_item(item, args):
    config = _config(args)

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
    return paths


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


def _normalize_paths(paths, config=None):
    if paths is None:
        configured = config_paths(config)
        if configured:
            return configured
        return ["-"]
    if isinstance(paths, str):
        return [paths]
    paths = list(paths)
    if not paths:
        configured = config_paths(config)
        if configured:
            return configured
        return ["-"]
    return paths


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
