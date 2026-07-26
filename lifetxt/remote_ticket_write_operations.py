"""Single-file history-preserving operations for Remote ticket writes."""
from __future__ import unicode_literals

from collections import OrderedDict

from . import mutation
from .remote_access import RemoteAccessError, can_access
from .ticket_activity import (
    _first,
    _sequence,
    _utc_text,
    build_ticket_event,
    configured_activities,
    event_view,
    validate_ticket_history,
)
from .ticket_activity_mutation import (
    _append_items,
    _find_ticket,
    _parse_items,
    apply_ticket_activity,
)
from .ticket_workflow import TERMINAL_LIFE_STATUSES, transition_plan
from .tickets import build_ticket_line, is_ticket, ticket_id_of, validate_ticket
from .remote_ticket_write_core import (
    TOKEN_RE,
    edit_updates,
    event_by_transaction,
    event_matches,
    require_ticket_access,
)


def create_ticket(
    path,
    payload,
    principal,
    expected,
    config,
    key,
    digest,
    txid,
    dry_run,
):
    ticket_id_value = str(payload.get("ticket_id") or "").strip()
    subject = str(payload.get("subject") or "").strip()
    if not ticket_id_value or not TOKEN_RE.match(ticket_id_value):
        raise RemoteAccessError(
            "REMOTE_TICKET_ID_REQUIRED",
            "Remote creation requires a stable ticket_id containing only letters, digits, . _ : or -.",
            428,
        )
    if not subject:
        raise RemoteAccessError("REMOTE_TICKET_INVALID", "subject is required.", 400)
    if payload.get("watchers"):
        raise RemoteAccessError(
            "REMOTE_TICKET_FIELD_FORBIDDEN",
            "Remote creation does not accept watchers until delivery and privacy contracts are enabled.",
            403,
        )
    project = payload.get("project")
    visibility = str(payload.get("visibility") or "shared")
    owner = str(payload.get("owner") or principal.get("id"))
    if not can_access(
        principal,
        project=project,
        visibility=visibility,
        owner=owner,
        groups=[],
    ):
        raise RemoteAccessError(
            "REMOTE_TICKET_FORBIDDEN",
            "The principal cannot create a ticket in the requested project or visibility.",
            403,
        )
    if owner != str(principal.get("id")) and principal.get("role") != "owner":
        raise RemoteAccessError(
            "REMOTE_TICKET_FIELD_FORBIDDEN",
            "Only an owner may create a ticket for another owner.",
            403,
        )
    timestamp = _utc_text(payload.get("at"))
    holder = {}

    def transform(current):
        items = _parse_items(current, key)
        previous = event_by_transaction(items, txid)
        if previous is not None:
            if event_matches(previous, "create", digest):
                holder.update(
                    ticket=_find_ticket(items, ticket_id_value, key),
                    event=previous,
                )
                return current
            raise RemoteAccessError(
                "REMOTE_TRANSACTION_REUSED",
                "The transaction ID was already used for a different request.",
                409,
            )
        if any(
            is_ticket(item) and str(ticket_id_of(item, key)) == ticket_id_value
            for item in items
        ):
            raise RemoteAccessError(
                "REMOTE_TICKET_EXISTS",
                "Ticket %r already exists." % ticket_id_value,
                409,
            )
        line = build_ticket_line(
            config,
            subject,
            tracker=payload.get("tracker"),
            priority=payload.get("priority"),
            severity=payload.get("severity"),
            assignee=payload.get("assignee"),
            reporter=payload.get("reporter") or principal.get("id"),
            component=payload.get("component"),
            version=payload.get("version"),
            sprint=payload.get("sprint"),
            ticket_status=payload.get("ticket_status") or "new",
            project=project,
            due=payload.get("due"),
            est=payload.get("est"),
            ticket_id=ticket_id_value,
            extra={"visibility": visibility, "owner": owner},
        )
        newline = "\r\n" if "\r\n" in current else "\n"
        text = current + (
            "" if not current or current.endswith(("\n", "\r")) else newline
        )
        text += line.replace("\n", newline) + newline
        parsed = _parse_items(text, key)
        ticket = _find_ticket(parsed, ticket_id_value, key)
        errors = [
            row
            for row in validate_ticket(ticket, config or {}, key=key)
            if row.get("severity") == "error"
        ]
        if errors:
            raise ValueError(errors)
        event = build_ticket_event(
            ticket_id_value,
            "created",
            principal.get("id"),
            timestamp,
            _sequence(parsed, ticket_id_value),
            txid,
            expected,
            project=project,
            tracker=_first(ticket, "tracker"),
            to_status=_first(ticket, "ticket_status"),
            extra={
                "remote_operation": "create",
                "remote_request_hash": digest,
                "remote_role": principal.get("role"),
            },
        )
        final_text = _append_items(text, [event])
        history_errors = [
            row
            for row in validate_ticket_history(
                _parse_items(final_text, key),
                config=config,
                key=key,
            )
            if row.get("severity") == "error"
        ]
        if history_errors:
            raise ValueError(history_errors)
        holder.update(ticket=ticket, event=event)
        return final_text

    snapshot = mutation.read_text_snapshot(path, allow_missing=False)
    if snapshot.content_hash != expected:
        raise mutation.MutationConflict(
            path,
            expected,
            snapshot.content_hash,
            operation="remote.ticket.create",
        )
    if dry_run:
        replacement = transform(snapshot.text)
        after = mutation.hash_text(
            replacement,
            encoding=snapshot.encoding,
            bom=snapshot.bom,
        )
    else:
        after = mutation.mutate_text(
            path,
            transform,
            expected_hash=expected,
            operation="remote.ticket.create",
        ).after_hash
    return {
        "ticket_id": ticket_id_value,
        "ticket": holder["ticket"].to_dict(),
        "event": event_view(holder["event"]),
        "target_revision_before": expected,
        "target_revision_after": after,
        "dry_run": bool(dry_run),
    }


def mutate_ticket(
    operation,
    path,
    payload,
    principal,
    expected,
    config,
    key,
    digest,
    txid,
    dry_run,
):
    snapshot = mutation.read_text_snapshot(path, allow_missing=False)
    ticket_id_value = str(payload.get("ticket_id") or "")
    ticket = _find_ticket(_parse_items(snapshot.text, key), ticket_id_value, key)
    require_ticket_access(ticket, principal)
    actor = str(principal.get("id"))
    extra = {
        "remote_operation": operation,
        "remote_request_hash": digest,
        "remote_role": principal.get("role"),
    }
    common = dict(
        config=config,
        key=key,
        at=payload.get("at"),
        transaction_id=txid,
        dry_run=dry_run,
    )
    if operation == "edit":
        result = apply_ticket_activity(
            path,
            ticket_id_value,
            "field_change",
            actor,
            expected,
            detail_updates=edit_updates(payload),
            comment=payload.get("comment"),
            event_extra=extra,
            operation="remote.ticket.edit",
            **common
        )
    elif operation == "comment":
        body = str(payload.get("body") or "").strip()
        if not body:
            raise RemoteAccessError("REMOTE_TICKET_INVALID", "body is required.", 400)
        result = apply_ticket_activity(
            path,
            ticket_id_value,
            "comment",
            actor,
            expected,
            comment=body,
            event_extra=extra,
            operation="remote.ticket.comment",
            **common
        )
    elif operation == "log_time":
        duration = payload.get("duration")
        activity = str(payload.get("activity") or "development")
        if duration in (None, ""):
            raise RemoteAccessError(
                "REMOTE_TICKET_INVALID",
                "duration is required.",
                400,
            )
        if activity not in configured_activities(config):
            raise RemoteAccessError(
                "REMOTE_TICKET_INVALID",
                "Unknown ticket activity %r." % activity,
                400,
            )
        extra["activity"] = activity
        result = apply_ticket_activity(
            path,
            ticket_id_value,
            "time_entry",
            actor,
            expected,
            comment=payload.get("comment"),
            event_extra=extra,
            time_entry={
                "user": actor,
                "activity": activity,
                "date": payload.get("date"),
                "duration": duration,
                "comment": payload.get("comment"),
                "source": "remote",
                "corrects": payload.get("corrects"),
            },
            operation="remote.ticket.log-time",
            **common
        )
    elif operation == "transition":
        target = str(payload.get("target_status") or "").strip()
        if not target:
            raise RemoteAccessError(
                "REMOTE_TICKET_INVALID",
                "target_status is required.",
                400,
            )
        role = (
            "administrator"
            if principal.get("role") == "owner"
            else str(principal.get("role") or "editor")
        )
        plan = transition_plan(
            ticket,
            target,
            config=config,
            role=role,
            comment=payload.get("comment"),
            resolution=payload.get("resolution"),
            extra_updates=(
                edit_updates({"set": payload.get("set")})
                if payload.get("set")
                else None
            ),
        )
        changes = OrderedDict(plan["detail_updates"])
        if plan["life_status"] in TERMINAL_LIFE_STATUSES:
            changes["closed_by"] = actor
        extra["role"] = plan["role"]
        result = apply_ticket_activity(
            path,
            ticket_id_value,
            plan["event"],
            actor,
            expected,
            detail_updates=changes,
            status=plan["life_status"],
            comment=payload.get("comment"),
            event_extra=extra,
            operation="remote.ticket.transition",
            **common
        )
        result["workflow"] = plan
    else:
        raise RemoteAccessError(
            "REMOTE_TICKET_OPERATION_UNKNOWN",
            "Unsupported operation.",
            400,
        )
    result.pop("path", None)
    result["ticket_id"] = ticket_id_value
    return result
