"""Dispatcher for compatibility-preserving extended CLI commands."""

import argparse
import os
import sys

from .extra_common import _load_config, _resolved_input_paths
from .extra_core import (command_next, command_show, command_edit, command_path, command_count, command_workload, command_files_open, command_someday)
from .extra_reports import command_invoice, command_standup
from .extra_convert import command_to_ics, command_from_todo, command_from_markdown
from .extra_shell import command_completion, command_quick_journal
from .extra_safety import command_capabilities, command_doctor, command_format, command_safety
from .extra_attachment import command_attachment
from .safety_foundation import read_text_exact
from .timezone_policy import resolve_timezone_name, timezone_context


def _add_output(parser, choices=("text", "json"), default="json"):
    parser.add_argument("--format", choices=choices, default=default)
    parser.add_argument("--pretty", action="store_true")
    parser.add_argument("-o", "--output")


def _add_timezone_policy(parser):
    parser.add_argument("--timezone")
    parser.add_argument("--fold-policy", choices=("error", "earlier", "later"), default="error")
    parser.add_argument("--gap-policy", choices=("error", "next", "previous"), default="error")


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
        parser.add_argument("--dry-run", action="store_true", help="Print the editor command without launching it.")
        parser.add_argument("--review-only", action="store_true", help="Open a temporary copy and print the diff without applying it.")
        parser.add_argument("--reconcile", action="store_true", help="Conservatively merge non-overlapping external changes made while the editor is open.")
        parser.add_argument("--keep-temp", action="store_true", help="Keep the edited temporary copy for manual recovery.")
        parser.add_argument("--show-diff", action="store_true", help="Print the applied diff after a successful edit.")
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
        parser.add_argument("--someday", action="store_true", required=True)
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
        parser.add_argument("--revision", help="Expected SHA-256 revision of the journal target.")
        parser.add_argument("--dry-run", action="store_true")
    elif command == "attachment":
        subparsers = parser.add_subparsers(dest="attachment_action", required=True)
        for action in ("put", "reference", "delete", "status", "directory-reference", "package", "reconcile", "open"):
            child = subparsers.add_parser(action)
            child.add_argument("path", help="life.txt file containing the item.")
            if action not in ("status", "open"):
                child.add_argument("--id", required=True, help="Item ID receiving the attachment reference.")
            child.add_argument("--file", required=True, help="Stored attachment path relative to life.txt.")
            if action == "put":
                child.add_argument("--source", required=True, help="Source file copied into the attachment target with a bounded reader.")
                child.add_argument("--allow-executable", action="store_true")
            if action == "package":
                child.add_argument("--source", required=True, help="Source directory packaged as a deterministic ZIP attachment.")
                child.add_argument("--include-hidden", action="store_true")
            if action == "reconcile":
                child.add_argument("--key", choices=("file", "dir"), default="file")
                child.add_argument("--recorded-revision", help="Hash currently stored on the item; stale values are rejected.")
            if action == "open":
                child.add_argument("--metadata-revision", help="Expected open-metadata state revision.")
                child.add_argument("--no-record", action="store_true", help="Do not update the local open-reference metadata state.")
                child.add_argument("--execute", action="store_true", help="Run the platform opener after validation. Default only returns the command plan.")
            child.add_argument("--item-revision", help="Expected life.txt SHA-256 revision.")
            child.add_argument("--attachment-revision", help="Expected attachment SHA-256 revision or <missing>.")
            child.add_argument("--transaction-id", help="Stable transaction id for retry/restart recovery.")
            child.add_argument("--require-revisions", action="store_true", help="Reject missing required revisions.")
            child.add_argument("--allow-symlink", action="store_true")
            _add_output(child)
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
        _add_timezone_policy(timezone)
        timezone.add_argument("--sample")
        _add_output(timezone)
        delegated = subparsers.add_parser("delegated")
        delegated.add_argument("delegated_action", choices=("prepare", "inspect", "apply", "reject"))
        delegated.add_argument("--path", help="Authoritative life.txt path for prepare.")
        delegated.add_argument("--proposal", required=True, help="Persistent delegated proposal JSON path.")
        delegated.add_argument("--command", help="Command for prepare; use {file} for the temporary copy.")
        delegated.add_argument("--timeout", type=float, default=300.0)
        delegated.add_argument("--keep-temp", action="store_true")
        delegated.add_argument("--expected-revision")
        delegated.add_argument("--expected-proposal-revision")
        delegated.add_argument("--unsafe", action="store_true")
        delegated.add_argument("--reason")
        _add_output(delegated)
        revisions = subparsers.add_parser("revisions")
        revisions.add_argument("paths", nargs="*")
        revisions.add_argument("--metrics-path")
        revisions.add_argument("--reset", action="store_true")
        revisions.add_argument("--expected-hash")
        revisions.add_argument("--export-evidence")
        revisions.add_argument("--relocate")
        revisions.add_argument("--delete-source", action="store_true")
        _add_output(revisions)
        transactions = subparsers.add_parser("transactions")
        transactions.add_argument(
            "transaction_action",
            nargs="?",
            default="list",
            choices=("list", "inspect", "resume", "compensate", "abandon", "export", "cleanup", "policy", "policy-write", "policy-migrate", "preflight", "archive", "rotate-archives", "verify-backup", "restore-backup", "audit", "drill"),
        )
        transactions.add_argument("--journal-dir")
        transactions.add_argument("--journal")
        transactions.add_argument("--backup-dir")
        transactions.add_argument("--archive-dir")
        transactions.add_argument("--older-than-days", type=float)
        transactions.add_argument("--policy-file")
        transactions.add_argument("--expected-revision")
        transactions.add_argument("--operator")
        transactions.add_argument("--set", action="append", default=[], metavar="KEY=VALUE")
        transactions.add_argument("--max-archives", type=int)
        transactions.add_argument("--max-archive-bytes", type=int)
        transactions.add_argument("--audit-file")
        transactions.add_argument("--event")
        transactions.add_argument("--details-json")
        transactions.add_argument("--point")
        transactions.add_argument("--recovery", choices=("inspect", "resume", "compensate", "cleanup-orphan", "auto"), default="inspect")
        transactions.add_argument("--matrix", action="store_true")
        transactions.add_argument("--repeat-recovery", action="store_true")
        transactions.add_argument("--restore-action", choices=("inspect", "resume", "compensate"), default="inspect")
        transactions.add_argument("--working-dir")
        transactions.add_argument("--keep-workspace", action="store_true")
        transactions.add_argument("--force", action="store_true")
        _add_output(transactions)
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
    elif command == "doctor":
        parser.add_argument("--workspace-safety", action="store_true", required=True)
        parser.add_argument("paths", nargs="*")
        parser.add_argument("--write-file")
        parser.add_argument("--archive", action="append", default=[])
        parser.add_argument("--timer-state", action="append", default=[])
        parser.add_argument("--revision-metrics")
        parser.add_argument("--journal-dir")
        parser.add_argument("--support-bundle")
        parser.add_argument("--cleanup-transactions", action="store_true")
        parser.add_argument("--transaction-retention-days", type=float, default=30.0)
        parser.add_argument("--stale-after", type=float, default=300.0)
        parser.add_argument("--cleanup-stale", action="store_true")
        parser.add_argument("--force", action="store_true")
        _add_timezone_policy(parser)
        _add_output(parser)
    else:
        raise ValueError("Unsupported extended command: %s" % command)
    return parser


def _timezone_for_args(args, config_data):
    paths = []
    if hasattr(args, "paths"):
        try:
            paths = _resolved_input_paths(args.paths, config_data)
        except Exception:
            paths = []
    text = ""
    for path in paths:
        if path and path != "-" and os.path.exists(path):
            try:
                text, _raw, _bom = read_text_exact(path)
                break
            except OSError:
                continue
    return resolve_timezone_name(
        config_data,
        text=text,
        cli_timezone=getattr(args, "timezone", None),
    )


def main(argv=None, config_path=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        raise ValueError("An extended command is required.")
    command = argv[0]
    parser = _build_parser(command)
    args = parser.parse_args(argv[1:])
    config_data = _load_config(config_path)
    timezone_name = _timezone_for_args(args, config_data)
    with timezone_context(timezone_name):
        return _dispatch(command, args, config_data, config_path)


def _dispatch(command, args, config_data, config_path):
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
    if command == "attachment":
        return command_attachment(args, config_data)
    if command == "safety":
        return command_safety(args, config_data)
    if command == "format":
        return command_format(args, config_data)
    if command == "capabilities":
        return command_capabilities(args, config_data)
    if command == "doctor":
        return command_doctor(args, config_data)
    raise ValueError("Unsupported extended command: %s" % command)
