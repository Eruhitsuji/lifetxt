"""Permission-aware Remote CLI and interactive TUI ticket mutations."""
from __future__ import unicode_literals

import argparse
import json
import sys
import uuid

from .remote_client import get_profile, request, snapshot

MUTATION_ROUTE = "/api/remote/v1/ticket-mutations"


def remote_permissions(profile):
    """Return the authenticated principal and effective Remote mutation policy."""
    session = request(profile, "GET", "/api/remote/v1/session")[0]
    capabilities = request(profile, "GET", "/api/remote/v1/capabilities")[0]
    principal = dict(session.get("principal") or {})
    policy = dict(capabilities.get("mutation_policy") or {})
    scopes = list(principal.get("scopes") or [])
    return {
        "principal": principal,
        "scopes": scopes,
        "can_read": "read" in scopes,
        "can_write": "write" in scopes and bool(policy.get("ticket_mutations_enabled")),
        "can_admin": "admin" in scopes,
        "can_audit": "audit" in scopes,
        "ticket_operations": list(policy.get("ticket_operations") or []),
        "limitations": list(policy.get("limitations") or []),
    }


def mutate_ticket(profile, operation, payload, revision=None, transaction_id=None, dry_run=False):
    """Submit one revision-checked, replay-safe ticket mutation."""
    current = snapshot(profile)
    current_revision = revision or current.get("revision")
    if not current_revision:
        raise RuntimeError("Remote snapshot did not include a revision.")
    body = dict(payload or {})
    body["operation"] = str(operation)
    body["transaction_id"] = str(transaction_id or uuid.uuid4())
    if dry_run:
        body["dry_run"] = True
    return request(
        profile,
        "POST",
        MUTATION_ROUTE,
        payload=body,
        revision=current_revision,
    )[0]


def create_ticket(profile, ticket_id, subject, tracker=None, project=None, priority=None,
                  visibility=None, transaction_id=None, dry_run=False):
    payload = {"ticket_id": ticket_id, "subject": subject}
    for key, value in (
        ("tracker", tracker), ("project", project), ("priority", priority),
        ("visibility", visibility),
    ):
        if value is not None:
            payload[key] = value
    return mutate_ticket(profile, "create", payload, transaction_id=transaction_id, dry_run=dry_run)


def edit_ticket(profile, ticket_id, set_values=None, unset_values=None, comment=None,
                transaction_id=None, dry_run=False):
    payload = {"ticket_id": ticket_id, "set": dict(set_values or {})}
    if unset_values:
        payload["unset"] = list(unset_values)
    if comment:
        payload["comment"] = comment
    return mutate_ticket(profile, "edit", payload, transaction_id=transaction_id, dry_run=dry_run)


def transition_ticket(profile, ticket_id, target_status, comment=None,
                      transaction_id=None, dry_run=False):
    payload = {"ticket_id": ticket_id, "target_status": target_status}
    if comment:
        payload["comment"] = comment
    return mutate_ticket(profile, "transition", payload, transaction_id=transaction_id, dry_run=dry_run)


def comment_ticket(profile, ticket_id, body, transaction_id=None, dry_run=False):
    return mutate_ticket(
        profile, "comment", {"ticket_id": ticket_id, "body": body},
        transaction_id=transaction_id, dry_run=dry_run,
    )


def log_ticket_time(profile, ticket_id, duration, activity=None, date=None, comment=None,
                    corrects=None, transaction_id=None, dry_run=False):
    payload = {"ticket_id": ticket_id, "duration": duration}
    for key, value in (("activity", activity), ("date", date), ("comment", comment), ("corrects", corrects)):
        if value is not None:
            payload[key] = value
    return mutate_ticket(profile, "log_time", payload, transaction_id=transaction_id, dry_run=dry_run)


def _pairs(values):
    result = {}
    for raw in values or []:
        key, separator, value = str(raw).partition("=")
        if not separator or not key:
            raise ValueError("Fields must use key=value syntax: %s" % raw)
        result[key] = value
    return result


def render_permissions(value):
    principal = value.get("principal") or {}
    lines = [
        "principal: %s" % (principal.get("id") or "anonymous"),
        "role: %s" % (principal.get("role") or "-"),
        "scopes: %s" % (", ".join(value.get("scopes") or []) or "-"),
        "ticket writes: %s" % ("allowed" if value.get("can_write") else "denied"),
        "operations: %s" % (", ".join(value.get("ticket_operations") or []) or "-"),
    ]
    return "\n".join(lines) + "\n"


def interactive_tui(profile, input_fn=input, output=None):
    """Small dependency-free TUI with explicit confirmation before writes."""
    output = output or sys.stdout
    permissions = remote_permissions(profile)
    output.write("lifetxt remote\n")
    output.write(render_permissions(permissions))
    data = snapshot(profile)
    for row in data.get("tickets", []):
        output.write("[ticket] %-16s %s\n" % (row.get("id", "-"), row.get("title") or row.get("text") or ""))
    if not permissions.get("can_write"):
        output.write("This principal has read-only access.\n")
        return {"mode": "read-only", "permissions": permissions}
    operation = input_fn("operation [create/edit/transition/comment/log_time/quit]: ").strip().lower()
    if operation in ("", "quit", "q"):
        return {"cancelled": True}
    if operation not in permissions.get("ticket_operations", []):
        raise ValueError("Operation is not allowed by the server: %s" % operation)
    ticket_id = input_fn("ticket id: ").strip()
    if operation == "create":
        payload = {"ticket_id": ticket_id, "subject": input_fn("subject: ").strip()}
    elif operation == "edit":
        payload = {"ticket_id": ticket_id, "set": _pairs([input_fn("field key=value: ").strip()])}
    elif operation == "transition":
        payload = {"ticket_id": ticket_id, "target_status": input_fn("target status: ").strip()}
    elif operation == "comment":
        payload = {"ticket_id": ticket_id, "body": input_fn("comment: ")}
    else:
        payload = {"ticket_id": ticket_id, "duration": input_fn("duration: ").strip()}
    if input_fn("apply authoritative mutation? [y/N]: ").strip().lower() not in ("y", "yes"):
        return {"cancelled": True, "operation": operation}
    result = mutate_ticket(profile, operation, payload)
    output.write(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    return result


def install_remote_client_writes_cli():
    from . import cli
    if getattr(cli, "_lifetxt_remote_client_writes_v23", False):
        return
    original = cli.build_parser

    def build_parser():
        parser = original()
        root = next(action for action in parser._actions if isinstance(action, argparse._SubParsersAction))
        remote = root.choices.get("remote")
        if remote is None:
            return parser
        subs = next(action for action in remote._actions if isinstance(action, argparse._SubParsersAction))
        if "permissions" not in subs.choices:
            command = subs.add_parser("permissions", help="Show effective Remote permissions.")
            _profile_args(command)
            command.set_defaults(func=_cmd_permissions)
        definitions = (
            ("ticket-create", _cmd_create), ("ticket-edit", _cmd_edit),
            ("ticket-transition", _cmd_transition), ("ticket-comment", _cmd_comment),
            ("ticket-log-time", _cmd_log_time),
        )
        for name, function in definitions:
            if name in subs.choices:
                continue
            command = subs.add_parser(name)
            _profile_args(command)
            command.add_argument("ticket_id")
            command.add_argument("--transaction-id")
            command.add_argument("--dry-run", action="store_true")
            if name == "ticket-create":
                command.add_argument("subject")
                command.add_argument("--tracker"); command.add_argument("--project")
                command.add_argument("--priority"); command.add_argument("--visibility")
            elif name == "ticket-edit":
                command.add_argument("--set", action="append", default=[])
                command.add_argument("--unset", action="append", default=[])
                command.add_argument("--comment")
            elif name == "ticket-transition":
                command.add_argument("target_status"); command.add_argument("--comment")
            elif name == "ticket-comment":
                command.add_argument("body")
            else:
                command.add_argument("duration"); command.add_argument("--activity")
                command.add_argument("--date"); command.add_argument("--comment"); command.add_argument("--corrects")
            command.set_defaults(func=function)
        tui = subs.choices.get("tui")
        if tui is not None and not any(action.dest == "interactive" for action in tui._actions):
            tui.add_argument("--interactive", action="store_true")
            old = tui.get_default("func")
            tui.set_defaults(func=lambda args, old=old: _cmd_tui(args, old))
        return parser

    cli.build_parser = build_parser
    cli._lifetxt_remote_client_writes_v23 = True


def _profile_args(parser):
    parser.add_argument("profile")
    parser.add_argument("--profiles-file")


def _profile(args):
    return get_profile(args.profile, args.profiles_file)


def _emit(value):
    print(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def _cmd_permissions(args):
    return _emit(remote_permissions(_profile(args)))


def _cmd_create(args):
    return _emit(create_ticket(_profile(args), args.ticket_id, args.subject, args.tracker, args.project,
                               args.priority, args.visibility, args.transaction_id, args.dry_run))


def _cmd_edit(args):
    return _emit(edit_ticket(_profile(args), args.ticket_id, _pairs(args.set), args.unset,
                             args.comment, args.transaction_id, args.dry_run))


def _cmd_transition(args):
    return _emit(transition_ticket(_profile(args), args.ticket_id, args.target_status, args.comment,
                                   args.transaction_id, args.dry_run))


def _cmd_comment(args):
    return _emit(comment_ticket(_profile(args), args.ticket_id, args.body, args.transaction_id, args.dry_run))


def _cmd_log_time(args):
    return _emit(log_ticket_time(_profile(args), args.ticket_id, args.duration, args.activity, args.date,
                                 args.comment, args.corrects, args.transaction_id, args.dry_run))


def _cmd_tui(args, old):
    if args.interactive:
        interactive_tui(_profile(args))
        return 0
    return old(args)
