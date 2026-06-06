import argparse
import json
import sys

from .agenda import (
    agenda_records,
    agenda_records_to_json,
    agenda_records_to_jsonl,
    agenda_records_to_life,
    filter_agenda_records,
    format_agenda_table,
    parse_agenda_range,
)
from .assist import (
    DETAIL_FLAGS,
    build_item_from_args,
    has_update_fields,
    item_to_assisted_line,
    prompt_item,
    update_text,
)
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
    check.add_argument("path", nargs="?", default="-", help="Input file, or - for stdin.")
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
    to_json.add_argument("path", nargs="?", default="-", help="Input file, or - for stdin.")
    to_json.add_argument("-o", "--output", help="Output file. Defaults to stdout.")
    to_json.add_argument("--pretty", action="store_true", help="Pretty-print JSON.")
    to_json.set_defaults(func=command_to_json)

    to_jsonl = subparsers.add_parser("to-jsonl", help="Convert life.txt to JSONL.")
    to_jsonl.add_argument("path", nargs="?", default="-", help="Input file, or - for stdin.")
    to_jsonl.add_argument("-o", "--output", help="Output file. Defaults to stdout.")
    to_jsonl.set_defaults(func=command_to_jsonl)

    status = subparsers.add_parser(
        "status",
        help="Show the latest status / presence item for each person.",
    )
    status.add_argument("path", nargs="?", default="-", help="Input file, or - for stdin.")
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
    status.add_argument("--pretty", action="store_true", help="Pretty-print JSON output.")
    status.set_defaults(func=command_status)

    agenda = subparsers.add_parser(
        "agenda",
        help="Show items related to a datetime range.",
    )
    agenda.add_argument("path", nargs="?", default="-", help="Input file, or - for stdin.")
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
        help="Half-width for --around, e.g. 30m, 2h, or 1d. Defaults to 1h.",
    )
    agenda.add_argument(
        "--format",
        choices=("text", "life", "json", "jsonl"),
        default="text",
        help="Output format.",
    )
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
    from_json.add_argument("path", nargs="?", default="-", help="Input file, or - for stdin.")
    from_json.add_argument("-o", "--output", help="Output file. Defaults to stdout.")
    from_json.set_defaults(func=command_from_json)

    from_jsonl = subparsers.add_parser("from-jsonl", help="Convert JSONL to life.txt.")
    from_jsonl.add_argument("path", nargs="?", default="-", help="Input file, or - for stdin.")
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


def command_check(args):
    text = read_text(args.path)
    items, diagnostics = parse_text(text)

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
    items, diagnostics = _parse_or_exit(args.path)
    output = items_to_json(items, pretty=args.pretty)
    write_text(args.output, output + "\n")
    _print_warnings(diagnostics)
    return 0


def command_to_jsonl(args):
    items, diagnostics = _parse_or_exit(args.path)
    output = items_to_jsonl(items)
    if output:
        output += "\n"
    write_text(args.output, output)
    _print_warnings(diagnostics)
    return 0


def command_status(args):
    items, diagnostics = _parse_or_exit(args.path)
    records = latest_status_records(items, person=args.person)

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
    items, diagnostics = _parse_or_exit(args.path)
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
        detail_filters=args.detail,
        text=args.text,
    )

    if args.format == "json":
        output = agenda_records_to_json(records, pretty=args.pretty)
        write_text(None, output + "\n")
    elif args.format == "jsonl":
        output = agenda_records_to_jsonl(records)
        if output:
            output += "\n"
        write_text(None, output)
    elif args.format == "life":
        output = agenda_records_to_life(records)
        if output:
            output += "\n"
        write_text(None, output)
    else:
        write_text(None, format_agenda_table(records))

    _print_warnings(diagnostics)
    return 0


def command_from_json(args):
    items = items_from_json_text(read_text(args.path))
    return _write_life_items(items, args.output)


def command_from_jsonl(args):
    items = items_from_jsonl_text(read_text(args.path))
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
    diagnostics = []
    lines = []
    for item in items:
        diagnostics.extend(validate_item(item))
        lines.append(item_to_line(item))
    if _has_error(diagnostics):
        _print_diagnostics(diagnostics)
        return 1
    _print_warnings(diagnostics)
    text = "\n".join(lines)
    if text:
        text += "\n"
    write_text(output, text)
    return 0


def _parse_or_exit(path):
    text = read_text(path)
    items, diagnostics = parse_text(text)
    if _has_error(diagnostics):
        _print_diagnostics(diagnostics)
        raise SystemExit(1)
    return items, diagnostics


def read_text(path):
    if path is None or path == "-":
        return sys.stdin.read()
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read()


def write_text(path, text):
    if path is None:
        sys.stdout.write(text)
        return
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


def append_line(path, line):
    with open(path, "a", encoding="utf-8", newline="\n") as handle:
        handle.write(line + "\n")


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
