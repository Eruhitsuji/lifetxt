"""Permission-aware Remote CLI and interactive TUI ticket operations."""
from __future__ import unicode_literals

import argparse
import json
import sys
import uuid

from .remote_client import get_profile, request, snapshot

MUTATION_ROUTE = "/api/remote/v1/ticket-mutations"
_CONFLICT_CODES = {
    "REVISION_CONFLICT",
    "STALE_REVISION",
    "PRECONDITION_FAILED",
    "REVISION_REQUIRED",
}


class RemoteMutationConflict(RuntimeError):
    """Structured, non-retrying Remote mutation conflict."""

    def __init__(self, message, detail=None, requested_revision=None,
                 current_revision=None, comparison=None):
        super().__init__(message)
        self.detail = dict(detail or {})
        self.requested_revision = requested_revision
        self.current_revision = current_revision
        self.comparison = list(comparison or [])

    def as_dict(self):
        return {
            "error": "REMOTE_MUTATION_CONFLICT",
            "message": str(self),
            "requested_revision": self.requested_revision,
            "current_revision": self.current_revision,
            "comparison": self.comparison,
            "server_detail": self.detail,
            "automatic_retry": False,
            "next_actions": ["refresh", "abandon", "submit_new_transaction"],
        }


def _header(headers, *names):
    lower = dict((str(key).lower(), value) for key, value in (headers or {}).items())
    for name in names:
        value = lower.get(str(name).lower())
        if value is not None:
            return value
    return None


def _grant_list(principal, name):
    value = principal.get(name)
    if value is None:
        value = principal.get(name.rstrip("s"))
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        return [str(item) for item in value]
    return [str(value)]


def remote_permissions(profile):
    """Return authenticated identity, grants, negotiation, and mutation policy."""
    session, session_headers = request(profile, "GET", "/api/remote/v1/session")
    capabilities, capability_headers = request(profile, "GET", "/api/remote/v1/capabilities")
    principal = dict(session.get("principal") or {})
    policy = dict(capabilities.get("mutation_policy") or {})
    scopes = list(principal.get("scopes") or [])
    enabled = bool(policy.get("ticket_mutations_enabled"))
    operations = list(policy.get("ticket_operations") or [])
    limitations = list(policy.get("limitations") or [])
    denial_reasons = []
    if "write" not in scopes:
        denial_reasons.append("principal_missing_write_scope")
    if not enabled:
        denial_reasons.append("ticket_mutations_disabled")
    if enabled and not operations:
        denial_reasons.append("no_ticket_operations_advertised")
    for value in policy.get("denial_reasons") or []:
        if value not in denial_reasons:
            denial_reasons.append(value)
    return {
        "principal": principal,
        "scopes": scopes,
        "grants": {
            "projects": _grant_list(principal, "projects"),
            "groups": _grant_list(principal, "groups"),
            "visibilities": _grant_list(principal, "visibilities"),
        },
        "can_read": "read" in scopes,
        "can_write": "write" in scopes and enabled and bool(operations),
        "can_admin": "admin" in scopes,
        "can_audit": "audit" in scopes,
        "ticket_mutations_enabled": enabled,
        "ticket_operations": operations,
        "limitations": limitations,
        "denial_reasons": denial_reasons,
        "protocol": {
            "session": _header(session_headers, "lifetxt_negotiated_protocol"),
            "capabilities": _header(capability_headers, "lifetxt_negotiated_protocol"),
        },
        "capability_revision": _header(
            capability_headers,
            "X-Lifetxt-Remote-Capability-Revision",
        ),
        "server_read_only": bool(
            policy.get("read_only")
            or capabilities.get("read_only")
            or session.get("read_only")
        ),
    }


def _ticket_id(row):
    return str(row.get("id") or row.get("ticket_id") or "")


def ticket_detail(profile, ticket_id, snapshot_value=None):
    """Return one visible ticket from the same filtered snapshot used for writes."""
    data = snapshot_value or snapshot(profile)
    wanted = str(ticket_id)
    for row in data.get("tickets", []):
        if _ticket_id(row) == wanted:
            return {
                "revision": data.get("revision"),
                "ticket": dict(row),
            }
    raise KeyError("Remote ticket is not visible: %s" % wanted)


def _bounded_comparison(payload, current, limit=20):
    current = dict(current or {})
    rows = []
    ticket_id = payload.get("ticket_id")
    if ticket_id is not None:
        rows.append({"field": "ticket_id", "requested": ticket_id,
                     "current": _ticket_id(current) or None})
    for key, requested in sorted((payload.get("set") or {}).items()):
        rows.append({"field": key, "requested": requested,
                     "current": current.get(key)})
    if payload.get("target_status") is not None:
        rows.append({"field": "status", "requested": payload.get("target_status"),
                     "current": current.get("status")})
    for key in payload.get("unset") or []:
        rows.append({"field": key, "requested": None, "current": current.get(key)})
    return rows[:limit]


def _runtime_detail(exc):
    try:
        value = json.loads(str(exc))
    except (TypeError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}


def _error_code(detail):
    candidates = [
        detail.get("code"), detail.get("error"),
        (detail.get("detail") or {}).get("code") if isinstance(detail.get("detail"), dict) else None,
    ]
    return next((str(value).upper() for value in candidates if value), "")


def mutate_ticket(profile, operation, payload, revision=None, transaction_id=None, dry_run=False):
    """Submit one revision-checked mutation without automatic conflict retry."""
    before = snapshot(profile)
    current_revision = revision or before.get("revision")
    if not current_revision:
        raise RuntimeError("Remote snapshot did not include a revision.")
    body = dict(payload or {})
    body["operation"] = str(operation)
    body["transaction_id"] = str(transaction_id or uuid.uuid4())
    if dry_run:
        body["dry_run"] = True
    try:
        return request(
            profile,
            "POST",
            MUTATION_ROUTE,
            payload=body,
            revision=current_revision,
        )[0]
    except RuntimeError as exc:
        detail = _runtime_detail(exc)
        if _error_code(detail) not in _CONFLICT_CODES:
            raise
        after = snapshot(profile)
        current = None
        wanted = str(body.get("ticket_id") or "")
        for row in after.get("tickets", []):
            if _ticket_id(row) == wanted:
                current = row
                break
        raise RemoteMutationConflict(
            "Remote data changed before the mutation could be committed.",
            detail=detail,
            requested_revision=current_revision,
            current_revision=after.get("revision"),
            comparison=_bounded_comparison(body, current),
        )


def create_ticket(profile, ticket_id, subject, tracker=None, project=None, priority=None,
                  visibility=None, transaction_id=None, dry_run=False):
    payload = {"ticket_id": ticket_id, "subject": subject}
    for key, value in (("tracker", tracker), ("project", project),
                       ("priority", priority), ("visibility", visibility)):
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
    return mutate_ticket(profile, "comment", {"ticket_id": ticket_id, "body": body},
                         transaction_id=transaction_id, dry_run=dry_run)


def log_ticket_time(profile, ticket_id, duration, activity=None, date=None, comment=None,
                    corrects=None, transaction_id=None, dry_run=False):
    payload = {"ticket_id": ticket_id, "duration": duration}
    for key, value in (("activity", activity), ("date", date),
                       ("comment", comment), ("corrects", corrects)):
        if value is not None:
            payload[key] = value
    return mutate_ticket(profile, "log_time", payload,
                         transaction_id=transaction_id, dry_run=dry_run)


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
    grants = value.get("grants") or {}
    lines = [
        "principal: %s" % (principal.get("id") or "anonymous"),
        "role: %s" % (principal.get("role") or "-"),
        "scopes: %s" % (", ".join(value.get("scopes") or []) or "-"),
        "projects: %s" % (", ".join(grants.get("projects") or []) or "-"),
        "groups: %s" % (", ".join(grants.get("groups") or []) or "-"),
        "visibilities: %s" % (", ".join(grants.get("visibilities") or []) or "-"),
        "ticket writes: %s" % ("allowed" if value.get("can_write") else "denied"),
        "operations: %s" % (", ".join(value.get("ticket_operations") or []) or "-"),
        "denial reasons: %s" % (", ".join(value.get("denial_reasons") or []) or "-"),
        "capability revision: %s" % (value.get("capability_revision") or "-"),
    ]
    return "\n".join(lines) + "\n"


def render_ticket_detail(value):
    ticket = value.get("ticket") or {}
    lines = [
        "ticket: %s" % (_ticket_id(ticket) or "-"),
        "revision: %s" % (value.get("revision") or "-"),
    ]
    for key in sorted(ticket):
        if key in ("id", "ticket_id"):
            continue
        rendered = json.dumps(ticket[key], ensure_ascii=False, sort_keys=True)
        lines.append("%s: %s" % (key, rendered))
    return "\n".join(lines) + "\n"


def _list_tickets(data, output):
    output.write("revision: %s\n" % (data.get("revision") or "-"))
    for row in data.get("tickets", []):
        output.write("[ticket] %-16s %s\n" % (
            _ticket_id(row) or "-", row.get("title") or row.get("text") or ""))


def _operation_payload(operation, input_fn):
    ticket_id = input_fn("ticket id: ").strip()
    if operation == "create":
        return {"ticket_id": ticket_id, "subject": input_fn("subject: ").strip()}
    if operation == "edit":
        return {"ticket_id": ticket_id,
                "set": _pairs([input_fn("field key=value: ").strip()])}
    if operation == "transition":
        return {"ticket_id": ticket_id,
                "target_status": input_fn("target status: ").strip()}
    if operation == "comment":
        return {"ticket_id": ticket_id, "body": input_fn("comment: ")}
    return {"ticket_id": ticket_id, "duration": input_fn("duration: ").strip()}


def interactive_tui(profile, input_fn=input, output=None):
    """Dependency-free loop with detail, refresh, and explicit write confirmation."""
    output = output or sys.stdout
    permissions = remote_permissions(profile)
    output.write("lifetxt remote\n")
    output.write(render_permissions(permissions))
    data = snapshot(profile)
    _list_tickets(data, output)
    writes = list(permissions.get("ticket_operations") or []) if permissions.get("can_write") else []
    allowed = ["show", "refresh", "quit"] + writes
    last_result = None
    while True:
        operation = input_fn("operation [%s]: " % "/".join(allowed)).strip().lower()
        if operation in ("", "quit", "q"):
            if not permissions.get("can_write") and last_result is None:
                return {"mode": "read-only", "permissions": permissions}
            return last_result or {"cancelled": True}
        if operation == "refresh":
            data = snapshot(profile)
            _list_tickets(data, output)
            last_result = {"refreshed": True, "revision": data.get("revision")}
            continue
        if operation == "show":
            value = ticket_detail(profile, input_fn("ticket id: ").strip(), data)
            output.write(render_ticket_detail(value))
            last_result = value
            continue
        if operation not in writes:
            output.write("Operation is not allowed by the server: %s\n" % operation)
            continue
        payload = _operation_payload(operation, input_fn)
        output.write("proposed mutation:\n")
        output.write(json.dumps({"operation": operation, "payload": payload},
                                ensure_ascii=False, indent=2, sort_keys=True) + "\n")
        if input_fn("apply authoritative mutation? [y/N]: ").strip().lower() not in ("y", "yes"):
            last_result = {"cancelled": True, "operation": operation}
            continue
        try:
            last_result = mutate_ticket(profile, operation, payload)
            output.write(json.dumps(last_result, ensure_ascii=False,
                                    indent=2, sort_keys=True) + "\n")
            data = snapshot(profile)
        except RemoteMutationConflict as exc:
            last_result = exc.as_dict()
            output.write(json.dumps(last_result, ensure_ascii=False,
                                    indent=2, sort_keys=True) + "\n")
            data = snapshot(profile)


def install_remote_client_writes_cli():
    from . import cli
    if getattr(cli, "_lifetxt_remote_client_writes_v24", False):
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
        if "ticket-show" not in subs.choices:
            command = subs.add_parser("ticket-show", help="Show one visible Remote ticket.")
            _profile_args(command)
            command.add_argument("ticket_id")
            command.set_defaults(func=_cmd_show)
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
    cli._lifetxt_remote_client_writes_v24 = True


def _profile_args(parser):
    parser.add_argument("profile")
    parser.add_argument("--profiles-file")


def _profile(args):
    return get_profile(args.profile, args.profiles_file)


def _emit(value):
    print(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def _emit_mutation(function, *args):
    try:
        return _emit(function(*args))
    except RemoteMutationConflict as exc:
        print(json.dumps(exc.as_dict(), ensure_ascii=False, indent=2, sort_keys=True),
              file=sys.stderr)
        return 3


def _cmd_permissions(args):
    return _emit(remote_permissions(_profile(args)))


def _cmd_show(args):
    return _emit(ticket_detail(_profile(args), args.ticket_id))


def _cmd_create(args):
    return _emit_mutation(create_ticket, _profile(args), args.ticket_id, args.subject,
                          args.tracker, args.project, args.priority, args.visibility,
                          args.transaction_id, args.dry_run)


def _cmd_edit(args):
    return _emit_mutation(edit_ticket, _profile(args), args.ticket_id, _pairs(args.set),
                          args.unset, args.comment, args.transaction_id, args.dry_run)


def _cmd_transition(args):
    return _emit_mutation(transition_ticket, _profile(args), args.ticket_id,
                          args.target_status, args.comment, args.transaction_id,
                          args.dry_run)


def _cmd_comment(args):
    return _emit_mutation(comment_ticket, _profile(args), args.ticket_id, args.body,
                          args.transaction_id, args.dry_run)


def _cmd_log_time(args):
    return _emit_mutation(log_ticket_time, _profile(args), args.ticket_id, args.duration,
                          args.activity, args.date, args.comment, args.corrects,
                          args.transaction_id, args.dry_run)


def _cmd_tui(args, old):
    if args.interactive:
        interactive_tui(_profile(args))
        return 0
    return old(args)
