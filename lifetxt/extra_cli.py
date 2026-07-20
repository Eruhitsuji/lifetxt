"""Dispatcher for compatibility-preserving extended CLI commands."""

import argparse
import sys

from .extra_common import _load_config
from .extra_core import (command_next, command_show, command_edit, command_path, command_count, command_workload, command_files_open, command_someday)
from .extra_reports import command_invoice, command_standup
from .extra_convert import command_to_ics, command_from_todo, command_from_markdown
from .extra_shell import command_completion, command_quick_journal


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
    raise ValueError("Unsupported extended command: %s" % command)
