"""CLI adapters for ticket versions, sprints, backlog, and roadmap."""
from __future__ import unicode_literals

import argparse
import json
from collections import OrderedDict

from . import mutation
from .ticket_planning import (
    VERSION_MARKER,
    SPRINT_MARKER,
    iter_versions,
    iter_sprints,
    planning_report,
    sprint_view,
    validate_planning,
    version_view,
)
from .ticket_planning_mutation import (
    assign_planning,
    create_sprint,
    create_version,
    update_planning_state,
)

_INSTALLED = False
_ORIGINALS = {}


def _subparsers(parser):
    for action in getattr(parser, "_actions", []):
        if isinstance(action, argparse._SubParsersAction):
            return action
    return None


def _json(cli_module, value, pretty=False):
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


def _target(args, cli_module):
    config = cli_module._config(args)
    path = getattr(args, "path", None) or cli_module.config_write_file(config)
    if not path:
        paths = cli_module.config_paths(config)
        path = paths[0] if paths else "life.txt"
    cli_module._ensure_writable_path(path, config, getattr(args, "planning_operation", "ticket planning"))
    return config, cli_module.id_key_from_config(config), path


def _read(args, cli_module):
    config = cli_module._config(args)
    paths = list(getattr(args, "paths", None) or []) or cli_module.config_paths(config)
    items, diagnostics = cli_module._parse_or_exit(paths, config)
    cli_module._print_warnings(diagnostics)
    return config, cli_module.id_key_from_config(config), items


def _actor(args, config, cli_module):
    return str(getattr(args, "actor", None) or cli_module.config_user_name(config) or "local")


def _write_result(args, cli_module, result):
    if getattr(args, "json", False):
        _json(cli_module, result, pretty=getattr(args, "pretty", False))
    else:
        record = result.get("record") or {}
        details = record.get("details") or {}
        identifier = (details.get("id") or ["-"])[0]
        cli_module.write_text(
            None,
            "%s %s\n  revision: %s -> %s%s\n"
            % (
                "Would update" if result.get("dry_run") else "Updated",
                identifier,
                result.get("revision_before"),
                result.get("revision_after"),
                " [dry-run]" if result.get("dry_run") else "",
            ),
        )
    return 0


def _write_options(parser):
    parser.add_argument("--revision", "--expected-revision", dest="expected_revision", required=True)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--pretty", action="store_true")


def _input(parser, cli_module):
    cli_module._add_input_paths(parser)



def _safe_write_command(function):
    def command(args):
        from . import cli as cli_module

        try:
            return function(args)
        except mutation.MutationConflict as exc:
            cli_module.sys.stderr.write("ERROR: %s\n" % exc)
            return 1

    command.__name__ = getattr(function, "__name__", "ticket_planning_write")
    return command


def _command_version_new(args):
    from . import cli as cli_module

    _config, key, path = _target(args, cli_module)
    result = create_version(
        path,
        args.title,
        args.project,
        args.expected_revision,
        identifier=args.id,
        state=args.state,
        due=args.due,
        release=args.release,
        description=args.description,
        parent=args.parent_version,
        key=key,
        dry_run=args.dry_run,
    )
    return _write_result(args, cli_module, result)


def _command_version_list(args):
    from . import cli as cli_module
    from .tickets import iter_tickets

    _config, _key, items = _read(args, cli_module)
    tickets = iter_tickets(items)
    rows = [version_view(item, tickets) for item in iter_versions(items, args.project)]
    rows.sort(key=lambda row: (row["release"] or row["due"] or "9999-12-31", row["id"] or ""))
    if args.format == "json":
        _json(cli_module, {"count": len(rows), "versions": rows}, pretty=args.pretty)
    else:
        for row in rows:
            cli_module.write_text(
                None,
                "%-12s %-10s %-14s due=%-10s release=%-10s tickets=%d %s\n"
                % (
                    row["id"] or "-",
                    row["state"] or "-",
                    row["project"] or "-",
                    row["due"] or "-",
                    row["release"] or "-",
                    row["ticket_count"],
                    row["title"],
                ),
            )
        if not rows:
            cli_module.write_text(None, "No versions.\n")
    return 0


def _find_version(items, identifier):
    matches = [item for item in iter_versions(items) if str((item.details.get("id") or [""])[0]) == str(identifier)]
    if not matches:
        raise ValueError("Version %r not found." % identifier)
    return matches[0]


def _command_version_show(args):
    from . import cli as cli_module
    from .tickets import iter_tickets

    _config, _key, items = _read(args, cli_module)
    row = version_view(_find_version(items, args.id), iter_tickets(items))
    if args.format == "json":
        _json(cli_module, row, pretty=args.pretty)
    else:
        cli_module.write_text(
            None,
            "%s %s\n  project=%s state=%s due=%s release=%s tickets=%d\n"
            % (
                row["id"], row["title"], row["project"], row["state"],
                row["due"] or "-", row["release"] or "-", row["ticket_count"],
            ),
        )
        if row["ticket_ids"]:
            cli_module.write_text(None, "  tickets: %s\n" % ", ".join(row["ticket_ids"]))
    return 0


def _command_version_state(args, state):
    from . import cli as cli_module

    _config, key, path = _target(args, cli_module)
    result = update_planning_state(
        path,
        args.id,
        VERSION_MARKER,
        state,
        args.expected_revision,
        key=key,
        force=getattr(args, "force", False),
        dry_run=args.dry_run,
    )
    return _write_result(args, cli_module, result)


def _command_sprint_new(args):
    from . import cli as cli_module

    _config, key, path = _target(args, cli_module)
    result = create_sprint(
        path,
        args.title,
        args.project,
        args.start,
        args.end,
        args.expected_revision,
        identifier=args.id,
        state=args.state,
        goal=args.goal,
        capacity=args.capacity,
        version=args.version,
        key=key,
        dry_run=args.dry_run,
    )
    return _write_result(args, cli_module, result)


def _command_sprint_list(args):
    from . import cli as cli_module
    from .tickets import iter_tickets

    _config, _key, items = _read(args, cli_module)
    tickets = iter_tickets(items)
    rows = [sprint_view(item, tickets) for item in iter_sprints(items, args.project)]
    rows.sort(key=lambda row: (row["start"] or "", row["id"] or ""))
    if args.format == "json":
        _json(cli_module, {"count": len(rows), "sprints": rows}, pretty=args.pretty)
    else:
        for row in rows:
            cli_module.write_text(
                None,
                "%-12s %-9s %s..%s tickets=%d open=%d points=%s capacity=%s %s\n"
                % (
                    row["id"] or "-",
                    row["state"] or "-",
                    row["start"] or "-",
                    row["end"] or "-",
                    row["ticket_count"],
                    row["open_ticket_count"],
                    row["story_points"],
                    row["capacity"] or "-",
                    row["title"],
                ),
            )
        if not rows:
            cli_module.write_text(None, "No sprints.\n")
    return 0


def _find_sprint(items, identifier):
    matches = [item for item in iter_sprints(items) if str((item.details.get("id") or [""])[0]) == str(identifier)]
    if not matches:
        raise ValueError("Sprint %r not found." % identifier)
    return matches[0]


def _command_sprint_show(args):
    from . import cli as cli_module
    from .tickets import iter_tickets

    _config, _key, items = _read(args, cli_module)
    row = sprint_view(_find_sprint(items, args.id), iter_tickets(items))
    if args.format == "json":
        _json(cli_module, row, pretty=args.pretty)
    else:
        cli_module.write_text(
            None,
            "%s %s\n  project=%s state=%s range=%s..%s capacity=%s points=%s\n"
            % (
                row["id"], row["title"], row["project"], row["state"],
                row["start"], row["end"], row["capacity"] or "-", row["story_points"],
            ),
        )
        if row["open_ticket_ids"]:
            cli_module.write_text(None, "  unresolved: %s\n" % ", ".join(row["open_ticket_ids"]))
        if row["warnings"]:
            cli_module.write_text(None, "  warnings: %s\n" % ", ".join(row["warnings"]))
    return 0


def _command_sprint_state(args, state):
    from . import cli as cli_module

    _config, key, path = _target(args, cli_module)
    result = update_planning_state(
        path,
        args.id,
        SPRINT_MARKER,
        state,
        args.expected_revision,
        key=key,
        force=getattr(args, "force", False),
        dry_run=args.dry_run,
    )
    return _write_result(args, cli_module, result)


def _command_ticket_plan(args):
    from . import cli as cli_module
    from .tickets import find_ticket_file

    config = cli_module._config(args)
    key = cli_module.id_key_from_config(config)
    path = find_ticket_file(cli_module._ticket_paths(args), args.id, key=key)
    if not path:
        raise ValueError("Ticket %r not found." % args.id)
    cli_module._ensure_writable_path(path, config, "ticket plan")
    result = assign_planning(
        path,
        args.id,
        args.expected_revision,
        _actor(args, config, cli_module),
        version=args.version,
        sprint=args.sprint,
        clear_version=args.clear_version,
        clear_sprint=args.clear_sprint,
        config=config,
        key=key,
        at=args.at,
        comment=args.comment,
        transaction_id=args.transaction_id,
        dry_run=args.dry_run,
    )
    if args.json:
        _json(cli_module, result, pretty=args.pretty)
    else:
        cli_module.write_text(
            None,
            "%s %s planning\n  transaction: %s\n  revision: %s -> %s%s\n"
            % (
                "Would update" if result["dry_run"] else "Updated",
                args.id,
                result["transaction_id"],
                result["revision_before"],
                result["revision_after"],
                " [dry-run]" if result["dry_run"] else "",
            ),
        )
    return 0


def _command_planning_report(args, mode):
    from . import cli as cli_module

    config, key, items = _read(args, cli_module)
    report = planning_report(items, project=args.project, config=config, key=key)
    if args.format == "json":
        _json(cli_module, report, pretty=args.pretty)
    elif mode == "backlog":
        for row in report["backlog"]:
            cli_module.write_text(
                None,
                "%-12s %-12s %-10s %-12s %s\n"
                % (
                    row["id"] or "-",
                    row["tracker"] or "-",
                    row["priority"] or "-",
                    row["assignee"] or "-",
                    row["title"],
                ),
            )
        if not report["backlog"]:
            cli_module.write_text(None, "Backlog is empty.\n")
    else:
        cli_module.write_text(
            None,
            "Roadmap project=%s versions=%d sprints=%d backlog=%d\n"
            % (
                report["project"] or "*",
                len(report["versions"]),
                len(report["sprints"]),
                len(report["backlog"]),
            ),
        )
        for row in report["versions"]:
            cli_module.write_text(
                None,
                "  version %-12s %-10s due=%-10s tickets=%d %s\n"
                % (row["id"], row["state"], row["due"] or row["release"] or "-", row["ticket_count"], row["title"]),
            )
        for row in report["sprints"]:
            cli_module.write_text(
                None,
                "  sprint  %-12s %-10s %s..%s open=%d/%d %s\n"
                % (
                    row["id"], row["state"], row["start"], row["end"],
                    row["open_ticket_count"], row["ticket_count"], row["title"],
                ),
            )
    return 0 if not any(row["severity"] == "error" for row in report["diagnostics"]) else 1


def _command_planning_validate(args):
    from . import cli as cli_module

    _config, key, items = _read(args, cli_module)
    rows = validate_planning(items, key=key)
    value = {"ok": not rows, "diagnostic_count": len(rows), "diagnostics": rows}
    if args.format == "json":
        _json(cli_module, value, pretty=args.pretty)
    else:
        for row in rows:
            cli_module.write_text(None, "%s %s: %s\n" % (row["severity"].upper(), row["code"], row["message"]))
        if not rows:
            cli_module.write_text(None, "Ticket planning records are valid.\n")
    return 0 if value["ok"] else 1


def _read_options(parser, cli_module):
    _input(parser, cli_module)
    parser.add_argument("--project")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    parser.add_argument("--pretty", action="store_true")


def _install_version(root, cli_module):
    if "version" in root.choices:
        return
    parser = root.add_parser("version", help="Manage ticket release versions.")
    actions = parser.add_subparsers(dest="version_command")
    new = actions.add_parser("new", help="Create a version record.")
    new.add_argument("title")
    new.add_argument("--project", required=True)
    new.add_argument("--id")
    new.add_argument("--state", default="open")
    new.add_argument("--due")
    new.add_argument("--release")
    new.add_argument("--description")
    new.add_argument("--parent-version")
    new.add_argument("--path")
    _write_options(new)
    new.set_defaults(func=_safe_write_command(_command_version_new), planning_operation="version new")
    listing = actions.add_parser("list")
    _read_options(listing, cli_module)
    listing.set_defaults(func=_command_version_list)
    show = actions.add_parser("show")
    show.add_argument("id")
    _input(show, cli_module)
    show.add_argument("--format", choices=("text", "json"), default="text")
    show.add_argument("--pretty", action="store_true")
    show.set_defaults(func=_command_version_show)
    for name, state in (("close", "closed"), ("release", "released"), ("lock", "locked"), ("reopen", "open")):
        command = actions.add_parser(name)
        command.add_argument("id")
        command.add_argument("--path")
        command.add_argument("--force", action="store_true")
        _write_options(command)
        command.set_defaults(func=_safe_write_command(lambda args, value=state: _command_version_state(args, value)), planning_operation="version %s" % name)


def _install_sprint(root, cli_module):
    if "sprint" in root.choices:
        return
    parser = root.add_parser("sprint", help="Manage ticket sprints.")
    actions = parser.add_subparsers(dest="sprint_command")
    new = actions.add_parser("new", help="Create a sprint record.")
    new.add_argument("title")
    new.add_argument("--project", required=True)
    new.add_argument("--start", required=True)
    new.add_argument("--end", required=True)
    new.add_argument("--id")
    new.add_argument("--state", default="planned")
    new.add_argument("--goal")
    new.add_argument("--capacity")
    new.add_argument("--version")
    new.add_argument("--path")
    _write_options(new)
    new.set_defaults(func=_safe_write_command(_command_sprint_new), planning_operation="sprint new")
    listing = actions.add_parser("list")
    _read_options(listing, cli_module)
    listing.set_defaults(func=_command_sprint_list)
    show = actions.add_parser("show")
    show.add_argument("id")
    _input(show, cli_module)
    show.add_argument("--format", choices=("text", "json"), default="text")
    show.add_argument("--pretty", action="store_true")
    show.set_defaults(func=_command_sprint_show)
    for name, state in (("start", "active"), ("close", "closed"), ("reopen", "planned")):
        command = actions.add_parser(name)
        command.add_argument("id")
        command.add_argument("--path")
        command.add_argument("--force", action="store_true")
        _write_options(command)
        command.set_defaults(func=_safe_write_command(lambda args, value=state: _command_sprint_state(args, value)), planning_operation="sprint %s" % name)


def _install_ticket(actions, cli_module):
    if "plan" not in actions.choices:
        command = actions.add_parser("plan", help="Assign or clear version/sprint membership with an event.")
        command.add_argument("id")
        _input(command, cli_module)
        command.add_argument("--version")
        command.add_argument("--sprint")
        command.add_argument("--clear-version", action="store_true")
        command.add_argument("--clear-sprint", action="store_true")
        command.add_argument("--actor")
        command.add_argument("--comment")
        command.add_argument("--at")
        command.add_argument("--transaction-id")
        _write_options(command)
        command.set_defaults(func=_safe_write_command(_command_ticket_plan))
    for name in ("backlog", "roadmap"):
        if name in actions.choices:
            continue
        command = actions.add_parser(name, help="Show the shared %s planning view." % name)
        _read_options(command, cli_module)
        command.set_defaults(func=(lambda args, mode=name: _command_planning_report(args, mode)))
    if "validate-planning" not in actions.choices:
        command = actions.add_parser("validate-planning")
        _read_options(command, cli_module)
        command.set_defaults(func=_command_planning_validate)


def _install(parser, cli_module):
    root = _subparsers(parser)
    if root is None:
        return parser
    _install_version(root, cli_module)
    _install_sprint(root, cli_module)
    ticket = root.choices.get("ticket")
    actions = _subparsers(ticket) if ticket else None
    if actions:
        _install_ticket(actions, cli_module)
    return parser


def install_ticket_planning_cli():
    global _INSTALLED
    if _INSTALLED:
        return
    from . import cli as cli_module

    original = cli_module.build_parser
    _ORIGINALS["build_parser"] = original

    def build_parser():
        return _install(original(), cli_module)

    cli_module.build_parser = build_parser
    _INSTALLED = True
