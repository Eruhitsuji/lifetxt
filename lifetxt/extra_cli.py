"""Dispatcher for compatibility-preserving extended CLI commands."""

import argparse
import sys

from .extra_common import _load_config
from .extra_core import (command_next, command_show, command_edit, command_path, command_count, command_workload, command_files_open, command_someday)
from .extra_reports import command_invoice, command_standup
from .extra_convert import command_to_ics, command_from_todo, command_from_markdown
from .extra_shell import command_completion, command_quick_journal
from .extra_safety import command_capabilities, command_format, command_safety


def _add_output(parser, choices=("text", "json"), default="json"):
    parser.add_argument("--format", choices=choices, default=default)
    parser.add_argument("--pretty", action="store_true")
    parser.add_argument("-o", "--output")


def _build_parser(command):
    parser = argparse.ArgumentParser(prog="python -m lifetxt %s" % command)
    if command == "next":
        parser.add_argument("paths", nargs="*")
        parser.add_argument("--user")
        parser.add_argument("--project")
        parser.add_argument("--context")
        parser.add_argument("--limit", type=int, default=20)
        parser.add_argument("--format", choices=("text", "json", "life"), default="text")
        parser.add_argument("--pretty", action="store_true")
        parser.add_argument("-o", "--output")
    elif command == "show":
        parser.add_argument("id")
        parser.add_argument("paths", nargs="*")
        parser.add_argument("--format", choices=("text", "json", "life"), default="text")
        parser.add_argument("--pretty", action="store_true")
        parser.add_argument("-o", "--output")
    elif command == "edit":
        parser.add_argument("id")
        parser.add_argument("paths", nargs="*")
        parser.add_argument("--editor")
        parser.add_argument("--dry-run", action="store_true")
    elif command == "path":
        parser.add_argument("--format", choices=("text", "json"), default="text")
        parser.add_argument("--pretty", action="store_true")
    elif command == "count":
        parser.add_argument("paths", nargs="*")
        parser.add_argument("--by", choices=("status", "type", "tag", "person", "project", "context", "assignee"), required=True)
        parser.add_argument("--format", choices=("text", "json", "csv"), default="text")
        parser.add_argument("--pretty", action="store_true")
        parser.add_argument("-o", "--output")
    elif command == "invoice":
        parser.add_argument("paths", nargs="*")
        parser.add_argument("--from", dest="start")
        parser.add_argument("--to", dest="end")
        parser.add_argument("--project")
        parser.add_argument("--rate", dest="rates", action="append", default=[])
        parser.add_argument("--default-rate", default="0")
        parser.add_argument("--round-minutes", "--round", dest="round_minutes", type=int, default=0)
        parser.add_argument("--currency", default="JPY")
        parser.add_argument("--format", choices=("text", "markdown", "csv", "json"), default="text")
        parser.add_argument("--pretty", action="store_true")
        parser.add_argument("-o", "--output")
    elif command == "standup":
        parser.add_argument("paths", nargs="*")
        parser.add_argument("--user")
        parser.add_argument("--date")
        parser.add_argument("--include-unassigned", action="store_true")
        parser.add_argument("--format", choices=("text", "markdown", "slack", "json"), default="text")
        parser.add_argument("--pretty", action="store_true")
        parser.add_argument("-o", "--output")
    elif command == "to-ics":
        parser.add_argument("paths", nargs="*")
        parser.add_argument("--calendar-name", default="lifetxt")
        parser.add_argument("-o", "--output")
    elif command == "from-todo":
        parser.add_argument("paths", nargs="*")
        parser.add_argument("--project")
        parser.add_argument("--tag", dest="tags", action="append", default=[])
        parser.add_argument("--append", action="store_true")
        parser.add_argument("-o", "--output")
    elif command == "from-markdown":
        parser.add_argument("paths", nargs="*")
        parser.add_argument("--preset", choices=("github",), default="github")
        parser.add_argument("--project")
        parser.add_argument("--tag", dest="tags", action="append", default=[])
        parser.add_argument("--append", action="store_true")
        parser.add_argument("-o", "--output")
    elif command == "files":
        parser.add_argument("paths", nargs="*")
        parser.add_argument("--open", dest="open_id", required=True)
        parser.add_argument("--index", type=int, default=1)
        parser.add_argument("--allow-outside", action="store_true")
        parser.add_argument("--allow-unsafe", action="store_true")
        parser.add_argument("--dry-run", action="store_true")
    elif command == "who":
        parser.add_argument("paths", nargs="*")
        parser.add_argument("--workload", action="store_true", required=True)
        parser.add_argument("--due-soon-days", "--due-soon", dest="due_soon_days", type=int, default=7)
        parser.add_argument("--format", choices=("text", "json"), default="text")
        parser.add_argument("--pretty", action="store_true")
    elif command == "review":
        parser.add_argument("paths", nargs="*")
        parser.add_argument("--someday", action="store_true",required=True)
        parser.add_argument("--days", "--older-than", dest="days", type=int, default=30)
        parser.add_argument("--format", choices=("text", "json", "life"), default="text")
        parser.add_argument("--pretty", action="store_true")
        parser.add_argument("-o", "--output")
    elif command == "completion":
        subparsers = parser.add_subparsers(dest="mode")
        powershell = subparsers.add_parser("powershell")
        powershell.add_argument("-o", "--output")
        install = subparsers.add_parser("install")
        install.add_argument("--shell", choices=("powershell",), required=True)
        install.add_argument("-o", "--output")
    elif command == "quick":
        parser.add_argument("--journal", action="store_true", required=True)
        parser.add_argument("--append")
        parser.add_argument("--date")
        parser.add_argument("--title")
        parser.add_argument("--mood")
        parser.add_argument("--project")
        parser.add_argument("--tag", dest="tags", action="append", default=[])
        parser.add_argument("--editor")
        parser.add_argument("--body-file")
        parser.add_argument("--dry-run", action="store_true")
    elif command == "safety":
        subparsers = parser.add_subparsers(dest="safety_action", required=True)
        locks = subparsers.add_parser("locks")
        locks.add_argument("paths", nargs="*")
        locks.add_argument("--stale-after", type=float, default=300.0)
        _add_output(locks)
        target = subparsers.add_parser("serve-target")
        target.add_argument("paths", nargs="*")
        target.add_argument("--write-file")
        _add_output(target)
        timezone = subparsers.add_parser("timezone")
        timezone.add_argument("paths", nargs="*")
        timezone.add_argument("--timezone")
        _add_output(timezone)
        routes = subparsers.add_parser("write-routes")
        routes.add_argument("--root")
        routes.add_argument("--strict", action="store_true")
        _add_output(routes)
        gate = subparsers.add_parser("release-gate")
        gate.add_argument("paths", nargs="*")
        gate.add_argument("--root")
        _add_output(gate)
    elif command == "format":
        subparsers = parser.add_subparsers(dest="format_action", required=True)
        info = subparsers.add_parser("info")
        info.add_argument("path")
        _add_output(info)
        check = subparsers.add_parser("check")
        check.add_argument("path")
        _add_output(check)
        canon = subparsers.add_parser("canon")
        canon.add_argument("path")
        canon.add_argument("--write", action="store_true")
        canon.add_argument("--strict", action="store_true")
        _add_output(canon)
        schemas = subparsers.add_parser("schemas")
        schemas.add_argument("directory", nargs="?", default="dist/schemas")
        _add_output(schemas)
    elif command == "capabilities":
        parser.add_argument("--read-only", action="store_true")
        parser.add_argument("--authentication", choices=("token", "session", "proxy", "none"), default="token")
        _add_output(parser)
    else:
        raise ValueError("Unsupported extended command: %s" % command)
    return parser


def main(argv=None, config_path=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        raise ValueError("An extended command is required.")
    command = argv[0]
    parser = _build_parser(command)
    args = parser.parse_args(argv[1:])
    config_data = _load_config(config_path)
    if command == "next":
        return command_next(args, config_data)
    if command == "show":
        return command_show(args, config_data)
    if command == "edit":
        return command_edit(args, config_data)
    if command == "path":
        return command_path(args, config_data, config_path)
    if command == "count":
        return command_count(args, config_data)
    if command == "invoice":
        return command_invoice(args, config_data)
    if command == "standup":
        return command_standup(args, config_data)
    if command == "to-ics":
        return command_to_ics(args, config_data)
    if command == "from-todo":
        return command_from_todo(args, config_data)
    if command == "from-markdown":
        return command_from_markdown(args, config_data)
    if command == "files":
        return command_files_open(args, config_data)
    if command == "who":
        return command_workload(args, config_data)
    if command == "review":
        return command_someday(args, config_data)
    if command == "completion":
        return command_completion(args)
    if command == "quick":
        return command_quick_journal(args, config_data)
    if command == "safety":
        return command_safety(args, config_data)
    if command == "format":
        return command_format(args, config_data)
    if command == "capabilities":
        return command_capabilities(args, config_data)
    raise ValueError("Unsupported extended command: %s" % command)
