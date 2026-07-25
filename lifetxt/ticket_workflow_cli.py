"""CLI adapters for ticket workflow, append-only history, and time entries."""
from __future__ import unicode_literals

import argparse
import json
from collections import OrderedDict

from . import mutation
from .ticket_activity import (
    EVENT_TYPES,
    ticket_activity_report,
    validate_ticket_history,
)
from .ticket_workflow import (
    apply_assignment,
    apply_comment,
    apply_field_change,
    apply_time,
    apply_transition,
    apply_watch,
    workflow_contract,
)

_INSTALLED = False
_ORIGINALS = {}


def _subparsers(parser):
    for action in getattr(parser, "_actions", []):
        if isinstance(action, argparse._SubParsersAction):
            return action
    return None


def _has_option(parser, option):
    return any(option in getattr(action, "option_strings", []) for action in parser._actions)


def _input(parser, cli_module):
    cli_module._add_input_paths(parser)


def _read_options(parser, cli_module):
    _input(parser, cli_module)
    parser.add_argument("--format", choices=("text", "json"), default="text")
    parser.add_argument("--pretty", action="store_true")


def _write_options(parser):
    parser.add_argument(
        "--revision",
        "--expected-revision",
        dest="expected_revision",
        required=True,
        help="Exact authoritative file SHA-256. Activity writes always require it.",
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--transaction-id", help="Stable retry/audit id.")
    parser.add_argument("--at", help="Offset-aware ISO event timestamp.")


def _actor(args, config, cli_module):
    return str(
        getattr(args, "actor", None)
        or getattr(args, "author", None)
        or getattr(args, "user", None)
        or cli_module.config_user_name(config)
        or "local"
    )


def _ticket_target(args, cli_module):
    from .tickets import find_ticket_file

    config = cli_module._config(args)
    key = cli_module.id_key_from_config(config)
    path = find_ticket_file(cli_module._ticket_paths(args), args.id, key=key)
    if not path:
        raise ValueError("Ticket %r not found." % args.id)
    cli_module._ensure_writable_path(path, config, getattr(args, "workflow_operation", "ticket activity"))
    return config, key, path


def _write_json(cli_module, value, pretty=False):
    cli_module.write_text(
        None,
        json.dumps(
            value,
            ensure_ascii=False,
            indent=2 if pretty else None,
            separators=None if pretty else (",", ":"),
        )
        + "\n",
    )


def _write_mutation(args, cli_module, result):
    if getattr(args, "json", False):
        _write_json(cli_module, result, pretty=getattr(args, "pretty", False))
    else:
        event = result.get("event") or {}
        cli_module.write_text(
            None,
            "%s %s (%s)\n  transaction: %s\n  revision: %s -> %s%s\n"
            % (
                "Would update" if result.get("dry_run") else "Updated",
                result.get("ticket_id"),
                event.get("event") or result.get("operation"),
                result.get("transaction_id"),
                result.get("revision_before"),
                result.get("revision_after"),
                " [dry-run]" if result.get("dry_run") else "",
            ),
        )
    return 0



def _safe_write_command(function):
    def command(args):
        from . import cli as cli_module

        try:
            return function(args)
        except mutation.MutationConflict as exc:
            cli_module.sys.stderr.write("ERROR: %s\n" % exc)
            return 1

    command.__name__ = getattr(function, "__name__", "ticket_workflow_write")
    return command


def _command_file_revision(args):
    from . import cli as cli_module

    config = cli_module._config(args)
    path = getattr(args, "path", None) or cli_module.config_write_file(config)
    if not path:
        paths = cli_module.config_paths(config)
        path = paths[0] if paths else "life.txt"
    snapshot = mutation.read_text_snapshot(path, allow_missing=True)
    result = OrderedDict(
        (
            ("path", path),
            ("algorithm", "sha256"),
            ("revision", snapshot.content_hash),
            ("exists", snapshot.exists),
        )
    )
    if getattr(args, "json", False):
        _write_json(cli_module, result, pretty=getattr(args, "pretty", False))
    else:
        cli_module.write_text(None, result["revision"] + "\n")
    return 0


def _command_workflow(args):
    from . import cli as cli_module

    config = cli_module._config(args)
    report = workflow_contract(
        config,
        tracker=getattr(args, "tracker", None),
        project=getattr(args, "project", None),
        role=getattr(args, "role", None),
    )
    if getattr(args, "format", "text") == "json":
        _write_json(cli_module, report, pretty=getattr(args, "pretty", False))
    else:
        cli_module.write_text(
            None,
            "ticket workflow v%s (%s, role=%s)\n"
            % (report["contract_version"], report["source"], report["role"]),
        )
        for target, transition in report["transitions"].items():
            flags = []
            if transition["resolution_required"]:
                flags.append("resolution")
            if transition["comment_required"]:
                flags.append("comment")
            if not transition["allowed_for_role"]:
                flags.append("forbidden-for-role")
            cli_module.write_text(
                None,
                "  %-14s from=%-45s event=%-12s %s\n"
                % (
                    target,
                    ",".join(transition["from"]) or "*",
                    transition["event"],
                    ",".join(flags) or "-",
                ),
            )
        for row in report["diagnostics"]:
            cli_module.sys.stderr.write("%s %s: %s\n" % (row["severity"].upper(), row["code"], row["message"]))
    return 0 if report["valid"] else 1


def _parse_updates(args):
    updates = OrderedDict()
    for pair in getattr(args, "set_fields", None) or []:
        if "=" not in str(pair):
            raise ValueError("--set expects KEY=VALUE, got %r." % pair)
        key, value = str(pair).split("=", 1)
        key = key.strip()
        if not key:
            raise ValueError("--set field name must not be empty.")
        updates[key] = value.strip()
    for key in getattr(args, "unset_fields", None) or []:
        updates[str(key).strip()] = None
    return updates


def _command_transition(args):
    from . import cli as cli_module

    config, key, path = _ticket_target(args, cli_module)
    result = apply_transition(
        path,
        args.id,
        args.status,
        _actor(args, config, cli_module),
        getattr(args, "role", None),
        args.expected_revision,
        config=config,
        key=key,
        comment=getattr(args, "comment", None),
        resolution=getattr(args, "resolution", None),
        extra_updates=_parse_updates(args),
        at=getattr(args, "at", None),
        transaction_id=getattr(args, "transaction_id", None),
        dry_run=bool(getattr(args, "dry_run", False)),
    )
    return _write_mutation(args, cli_module, result)


def _command_comment(args):
    from . import cli as cli_module

    config, key, path = _ticket_target(args, cli_module)
    result = apply_comment(
        path,
        args.id,
        args.body,
        _actor(args, config, cli_module),
        args.expected_revision,
        config=config,
        key=key,
        at=getattr(args, "at", None),
        transaction_id=getattr(args, "transaction_id", None),
        dry_run=bool(getattr(args, "dry_run", False)),
    )
    return _write_mutation(args, cli_module, result)


def _command_watch(args, add):
    from . import cli as cli_module

    config, key, path = _ticket_target(args, cli_module)
    result = apply_watch(
        path,
        args.id,
        args.watcher,
        _actor(args, config, cli_module),
        args.expected_revision,
        add=add,
        config=config,
        key=key,
        at=getattr(args, "at", None),
        transaction_id=getattr(args, "transaction_id", None),
        dry_run=bool(getattr(args, "dry_run", False)),
    )
    return _write_mutation(args, cli_module, result)


def _command_reassign(args):
    from . import cli as cli_module

    config, key, path = _ticket_target(args, cli_module)
    result = apply_assignment(
        path,
        args.id,
        args.assignee,
        _actor(args, config, cli_module),
        args.expected_revision,
        config=config,
        key=key,
        at=getattr(args, "at", None),
        comment=getattr(args, "comment", None),
        transaction_id=getattr(args, "transaction_id", None),
        dry_run=bool(getattr(args, "dry_run", False)),
    )
    return _write_mutation(args, cli_module, result)


def _command_change(args):
    from . import cli as cli_module

    config, key, path = _ticket_target(args, cli_module)
    result = apply_field_change(
        path,
        args.id,
        _parse_updates(args),
        _actor(args, config, cli_module),
        args.expected_revision,
        config=config,
        key=key,
        at=getattr(args, "at", None),
        comment=getattr(args, "comment", None),
        transaction_id=getattr(args, "transaction_id", None),
        dry_run=bool(getattr(args, "dry_run", False)),
    )
    return _write_mutation(args, cli_module, result)


def _command_log_time(args):
    from . import cli as cli_module

    config, key, path = _ticket_target(args, cli_module)
    result = apply_time(
        path,
        args.id,
        args.duration,
        _actor(args, config, cli_module),
        args.activity,
        args.expected_revision,
        config=config,
        key=key,
        date=getattr(args, "date", None),
        comment=getattr(args, "comment", None),
        source=getattr(args, "source", None),
        timer_ref=getattr(args, "timer_ref", None),
        corrects=getattr(args, "corrects", None),
        at=getattr(args, "at", None),
        transaction_id=getattr(args, "transaction_id", None),
        dry_run=bool(getattr(args, "dry_run", False)),
    )
    return _write_mutation(args, cli_module, result)


def _activity(args):
    from . import cli as cli_module

    config = cli_module._config(args)
    items, diagnostics = cli_module._parse_or_exit(cli_module._ticket_paths(args), config)
    cli_module._print_warnings(diagnostics)
    types = getattr(args, "event_types", None)
    return cli_module, ticket_activity_report(
        items,
        args.id,
        config=config,
        key=cli_module.id_key_from_config(config),
        event_types=types,
        limit=getattr(args, "limit", None),
    )


def _command_activity(args):
    cli_module, report = _activity(args)
    if getattr(args, "format", "text") == "json":
        _write_json(cli_module, report, pretty=getattr(args, "pretty", False))
    else:
        summary = report["ticket"]["summary"]
        cli_module.write_text(
            None,
            "%s %s\n  events=%d time=%s entries=%d\n"
            % (
                summary["id"],
                summary["title"],
                len(report["events"]),
                report["time"]["authoritative_duration"],
                report["time"]["entry_count"],
            ),
        )
        for row in report["events"]:
            cli_module.write_text(
                None,
                "  %s #%s %-14s %-12s %s\n"
                % (
                    row["at"] or "-",
                    row["sequence"],
                    row["event"] or "-",
                    row["author"] or "-",
                    row["body"] or "",
                ),
            )
    return 0


def _command_time(args):
    cli_module, report = _activity(args)
    value = OrderedDict(
        (
            ("schema", report["schema"]),
            ("ticket_id", args.id),
            ("time", report["time"]),
            ("entries", report["time_entries"]),
        )
    )
    if getattr(args, "format", "text") == "json":
        _write_json(cli_module, value, pretty=getattr(args, "pretty", False))
    else:
        cli_module.write_text(
            None,
            "%s: %s across %d entries (legacy elapsed=%s)\n"
            % (
                args.id,
                report["time"]["authoritative_duration"],
                report["time"]["entry_count"],
                report["time"]["legacy_elapsed"] or "-",
            ),
        )
        for row in report["time_entries"]:
            cli_module.write_text(
                None,
                "  %s %-12s %-12s %-8s %s\n"
                % (
                    row["date"] or "-",
                    row["user"] or "-",
                    row["activity"] or "-",
                    row["duration"] or "-",
                    row["comment"] or "",
                ),
            )
    return 0


def _command_history_validate(args):
    from . import cli as cli_module

    config = cli_module._config(args)
    items, diagnostics = cli_module._parse_or_exit(args.paths, config)
    cli_module._print_warnings(diagnostics)
    rows = validate_ticket_history(items, config=config, key=cli_module.id_key_from_config(config))
    result = OrderedDict(
        (
            ("ok", not any(row["severity"] == "error" for row in rows)),
            ("diagnostic_count", len(rows)),
            ("diagnostics", rows),
        )
    )
    if getattr(args, "format", "text") == "json":
        _write_json(cli_module, result, pretty=getattr(args, "pretty", False))
    else:
        for row in rows:
            cli_module.write_text(None, "%s %s: %s\n" % (row["severity"].upper(), row["code"], row["message"]))
        if not rows:
            cli_module.write_text(None, "Ticket history is valid.\n")
    return 0 if result["ok"] else 1


def _install_commands(parser, cli_module):
    root = _subparsers(parser)
    ticket = root.choices.get("ticket") if root else None
    actions = _subparsers(ticket) if ticket else None
    if actions is None:
        return parser

    if "file-revision" not in actions.choices:
        command = actions.add_parser("file-revision", help="Print the exact writable-file revision.")
        command.add_argument("path", nargs="?")
        command.add_argument("--json", action="store_true")
        command.add_argument("--pretty", action="store_true")
        command.set_defaults(func=_command_file_revision)

    if "workflow" not in actions.choices:
        command = actions.add_parser("workflow", help="Inspect the effective ticket workflow.")
        command.add_argument("--tracker")
        command.add_argument("--project")
        command.add_argument("--role")
        command.add_argument("--format", choices=("text", "json"), default="text")
        command.add_argument("--pretty", action="store_true")
        command.set_defaults(func=_command_workflow)

    if "transition" not in actions.choices:
        command = actions.add_parser("transition", help="Apply an allowed transition and append its event atomically.")
        command.add_argument("id")
        command.add_argument("status")
        _input(command, cli_module)
        command.add_argument("--actor")
        command.add_argument("--role")
        command.add_argument("--comment")
        command.add_argument("--resolution")
        command.add_argument("--set", action="append", dest="set_fields")
        command.add_argument("--unset", action="append", dest="unset_fields")
        command.add_argument("--json", action="store_true")
        command.add_argument("--pretty", action="store_true")
        _write_options(command)
        command.set_defaults(func=_safe_write_command(_command_transition), workflow_operation="ticket transition")

    specs = (
        ("comment", "Append an immutable ticket comment event.", _command_comment),
        ("reassign", "Change assignee and append an assignment event.", _command_reassign),
        ("change", "Change fields and append a field_change event.", _command_change),
    )
    for name, help_text, function in specs:
        if name in actions.choices:
            continue
        command = actions.add_parser(name, help=help_text)
        command.add_argument("id")
        _input(command, cli_module)
        if name == "comment":
            command.add_argument("body")
            command.add_argument("--author")
        elif name == "reassign":
            command.add_argument("assignee")
            command.add_argument("--actor")
            command.add_argument("--comment")
        else:
            command.add_argument("--set", action="append", dest="set_fields")
            command.add_argument("--unset", action="append", dest="unset_fields")
            command.add_argument("--actor")
            command.add_argument("--comment")
        command.add_argument("--json", action="store_true")
        command.add_argument("--pretty", action="store_true")
        _write_options(command)
        command.set_defaults(func=_safe_write_command(function), workflow_operation="ticket %s" % name)

    for name, add in (("watch", True), ("unwatch", False)):
        if name in actions.choices:
            continue
        command = actions.add_parser(name, help="%s a watcher and append an event." % ("Add" if add else "Remove"))
        command.add_argument("id")
        command.add_argument("watcher")
        _input(command, cli_module)
        command.add_argument("--actor")
        command.add_argument("--json", action="store_true")
        command.add_argument("--pretty", action="store_true")
        _write_options(command)
        command.set_defaults(
            func=_safe_write_command(lambda args, enabled=add: _command_watch(args, enabled)),
            workflow_operation="ticket %s" % name,
        )

    if "log-time" not in actions.choices:
        command = actions.add_parser("log-time", help="Append a time entry and its audit event atomically.")
        command.add_argument("id")
        command.add_argument("duration")
        _input(command, cli_module)
        command.add_argument("--user")
        command.add_argument("--activity", default="development")
        command.add_argument("--date")
        command.add_argument("--comment")
        command.add_argument("--source")
        command.add_argument("--timer-ref")
        command.add_argument("--corrects")
        command.add_argument("--json", action="store_true")
        command.add_argument("--pretty", action="store_true")
        _write_options(command)
        command.set_defaults(func=_safe_write_command(_command_log_time), workflow_operation="ticket log-time")

    if "activity" not in actions.choices:
        command = actions.add_parser("activity", help="Show ticket events and time entries.")
        command.add_argument("id")
        _input(command, cli_module)
        command.add_argument("--event", action="append", dest="event_types", choices=EVENT_TYPES)
        command.add_argument("--limit", type=int)
        command.add_argument("--format", choices=("text", "json"), default="text")
        command.add_argument("--pretty", action="store_true")
        command.set_defaults(func=_command_activity)

    if "time" not in actions.choices:
        command = actions.add_parser("time", help="Show authoritative append-only ticket time.")
        command.add_argument("id")
        _input(command, cli_module)
        command.add_argument("--format", choices=("text", "json"), default="text")
        command.add_argument("--pretty", action="store_true")
        command.set_defaults(func=_command_time)

    if "validate-history" not in actions.choices:
        command = actions.add_parser("validate-history", help="Validate append-only ticket events and time entries.")
        _read_options(command, cli_module)
        command.set_defaults(func=_command_history_validate)
    return parser


def install_ticket_workflow_cli():
    global _INSTALLED
    if _INSTALLED:
        return
    from . import cli as cli_module

    original = cli_module.build_parser
    _ORIGINALS["build_parser"] = original

    def build_parser():
        return _install_commands(original(), cli_module)

    cli_module.build_parser = build_parser
    _INSTALLED = True
