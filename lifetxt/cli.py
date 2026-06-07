import argparse
import hashlib
import json
import os
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

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
from .model import Diagnostic
from .parser import parse_text
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
    parser = build_parser()
    args = parser.parse_args(argv)
    if not hasattr(args, "func"):
        parser.print_help()
        return 2
    try:
        return args.func(args)
    except ValueError as exc:
        sys.stderr.write("ERROR: %s\n" % exc)
        return 1


def build_parser():
    parser = argparse.ArgumentParser(
        prog="python -m lifetxt",
        description="Parser, validator, converter, and input helper for life.txt.",
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
    items, diagnostics = _parse_life_inputs(args.paths)

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


def command_to_json(args):
    items, diagnostics = _parse_or_exit(args.paths)
    items = _filter_items_from_args(items, args)
    output = items_to_json(items, pretty=args.pretty)
    write_text(args.output, output + "\n")
    _print_warnings(diagnostics)
    return 0


def command_to_jsonl(args):
    items, diagnostics = _parse_or_exit(args.paths)
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
        if args.cache_dir and not args.dry_run:
            cache_name = _ics_cache_name(source, index)
            write_bytes(os.path.join(args.cache_dir, cache_name), data)
        items.extend(
            items_from_ics_text(
                decode_ics_bytes(data),
                project=args.project,
                tags=args.tag,
            )
        )

    output = _validated_life_text_or_exit(items)
    if output is None:
        return 1
    if args.dry_run:
        write_text(None, output)
    else:
        if args.output:
            ensure_parent_dir(args.output)
        write_text(args.output, output)
    return 0


def command_filter(args):
    items, diagnostics = _parse_or_exit(args.paths)
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
    items, diagnostics = _parse_or_exit(args.paths)
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


def command_agenda(args):
    items, diagnostics = _parse_or_exit(args.paths)
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


def _parse_or_exit(paths):
    items, diagnostics = _parse_life_inputs(paths)
    if _has_error(diagnostics):
        _print_diagnostics(diagnostics)
        raise SystemExit(1)
    return items, diagnostics


def _parse_life_inputs(paths):
    normalized = _normalize_paths(paths)
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
        detail_filters=getattr(args, "detail", None),
        text=getattr(args, "text", None),
        range_start=range_start,
        range_end=range_end,
    )


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


def _normalize_paths(paths):
    if paths is None:
        return ["-"]
    if isinstance(paths, str):
        return [paths]
    paths = list(paths)
    if not paths:
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
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


def write_bytes(path, data):
    ensure_parent_dir(path)
    with open(path, "wb") as handle:
        handle.write(data)


def ensure_parent_dir(path):
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)


def append_line(path, line):
    with open(path, "a", encoding="utf-8", newline="\n") as handle:
        handle.write(line + "\n")


def append_text(path, text):
    if not text:
        return
    needs_newline = False
    try:
        with open(path, "rb") as handle:
            handle.seek(0, 2)
            if handle.tell() > 0:
                handle.seek(-1, 2)
                needs_newline = handle.read(1) not in (b"\n", b"\r")
    except FileNotFoundError:
        pass
    with open(path, "a", encoding="utf-8", newline="\n") as handle:
        if needs_newline:
            handle.write("\n")
        handle.write(text)


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
