import argparse
import json
import sys

from .assist import DETAIL_FLAGS, build_item_from_args, item_to_assisted_line, prompt_item
from .model import Diagnostic
from .parser import parse_text
from .serializer import (
    item_to_line,
    items_from_json_text,
    items_from_jsonl_text,
    items_to_json,
    items_to_jsonl,
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
    assist.add_argument("--append", help="Append the generated line to a file.")
    assist.add_argument(
        "--no-check",
        action="store_true",
        help="Do not validate the generated line before output.",
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


def command_from_json(args):
    items = items_from_json_text(read_text(args.path))
    return _write_life_items(items, args.output)


def command_from_jsonl(args):
    items = items_from_jsonl_text(read_text(args.path))
    return _write_life_items(items, args.output)


def command_assist(args):
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
    write_text(None, line + "\n")
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
