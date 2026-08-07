"""Shared security, idempotency, and capability helpers for Remote ticket writes."""

from __future__ import unicode_literals

import hashlib
import json
import os
import re
from collections import OrderedDict

from . import mutation
from .remote_access import (
    RemoteAccessError,
    can_access,
    redact_remote_value,
)
from .remote_backend import source_revision
from .ticket_activity import _first, event_view, iter_ticket_events
from .ticket_activity_mutation import _find_ticket, _parse_items
from .tickets import find_ticket_file, id_key

ROUTE = "/api/remote/v1/ticket-mutations"
OPERATIONS = ("create", "edit", "transition", "comment", "log_time")
TOKEN_RE = re.compile(r"^[A-Za-z0-9_.:-]+$")
EDIT_FIELDS = frozenset(
    (
        "priority",
        "severity",
        "assignee",
        "component",
        "category",
        "version",
        "milestone",
        "sprint",
        "est",
        "story_points",
        "branch",
        "build",
        "due",
    )
)


def remote_section(config):
    value = (config or {}).get("remote")
    return value if isinstance(value, dict) else {}


def enabled(config):
    return bool(remote_section(config).get("ticket_writes_enabled", False))


def normalized_change(operation, payload):
    value = {
        str(key): item
        for key, item in (payload or {}).items()
        if key not in ("transaction_id", "dry_run")
    }
    value["operation"] = operation
    return value


def request_hash(operation, payload):
    value = normalized_change(operation, payload)
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def transaction_id(payload):
    value = str((payload or {}).get("transaction_id") or "").strip()
    if not value:
        raise RemoteAccessError(
            "REMOTE_TRANSACTION_REQUIRED",
            "transaction_id is required for authoritative Remote ticket mutations.",
            428,
        )
    if not TOKEN_RE.match(value):
        raise RemoteAccessError(
            "REMOTE_TRANSACTION_INVALID",
            "transaction_id contains unsupported characters.",
            400,
        )
    return value


def event_by_transaction(items, value):
    rows = [
        item
        for item in iter_ticket_events(items)
        if str(_first(item, "transaction", "")) == value
    ]
    if len(rows) > 1:
        raise RemoteAccessError(
            "REMOTE_TRANSACTION_AMBIGUOUS",
            "The transaction ID appears more than once in ticket history.",
            409,
        )
    return rows[0] if rows else None


def event_matches(item, operation, digest):
    return (
        str(_first(item, "remote_operation", "")) == operation
        and str(_first(item, "remote_request_hash", "")) == digest
    )


def access_for_item(item):
    details = getattr(item, "details", {}) or {}

    def first(*keys):
        for key in keys:
            values = details.get(key) or []
            if values:
                return str(values[0])
        return None

    groups = []
    for key in ("group", "groups", "team", "teams"):
        groups.extend(str(value) for value in details.get(key, []) or [])
    return {
        "project": first("project"),
        "visibility": first("visibility") or "shared",
        "owner": first("owner", "assignee", "reporter"),
        "groups": groups,
    }


def require_ticket_access(item, principal):
    if not can_access(principal, **access_for_item(item)):
        raise RemoteAccessError(
            "REMOTE_TICKET_FORBIDDEN",
            "The principal cannot access this ticket.",
            403,
        )


def existing_ticket_path(paths, writable_path, ticket_id_value, key):
    path = find_ticket_file(paths, ticket_id_value, key=key)
    if not path:
        raise RemoteAccessError(
            "REMOTE_TICKET_NOT_FOUND",
            "Ticket %r was not found." % ticket_id_value,
            404,
        )
    if not writable_path or os.path.realpath(path) != os.path.realpath(writable_path):
        raise RemoteAccessError(
            "REMOTE_TICKET_READ_ONLY_SOURCE",
            "The ticket is not stored in the configured writable source.",
            409,
        )
    return path


def edit_updates(payload):
    raw_set = (payload or {}).get("set") or {}
    raw_unset = (payload or {}).get("unset") or []
    if not isinstance(raw_set, dict):
        raise RemoteAccessError("REMOTE_TICKET_INVALID", "set must be an object.", 400)
    if isinstance(raw_unset, str):
        raw_unset = [raw_unset]
    if not isinstance(raw_unset, (list, tuple)):
        raise RemoteAccessError("REMOTE_TICKET_INVALID", "unset must be an array.", 400)
    result = OrderedDict()
    for key, value in raw_set.items():
        key = str(key)
        if key not in EDIT_FIELDS:
            raise RemoteAccessError(
                "REMOTE_TICKET_FIELD_FORBIDDEN",
                "Remote ticket edit cannot set field %r." % key,
                403,
            )
        result[key] = value
    for key in raw_unset:
        key = str(key)
        if key not in EDIT_FIELDS:
            raise RemoteAccessError(
                "REMOTE_TICKET_FIELD_FORBIDDEN",
                "Remote ticket edit cannot unset field %r." % key,
                403,
            )
        result[key] = None
    if not result:
        raise RemoteAccessError(
            "REMOTE_TICKET_INVALID",
            "No ticket field changes were supplied.",
            400,
        )
    return result


def mutation_response(operation, txid, replayed, before, after, result):
    return OrderedDict(
        (
            ("schema", "remote-ticket-mutation-v1.schema.json"),
            ("contract_version", "1"),
            ("operation", operation),
            ("transaction_id", txid),
            ("replayed", bool(replayed)),
            ("revision_before", before),
            ("revision_after", after),
            ("result", redact_remote_value(result)),
        )
    )


def replay(path, paths, key, operation, ticket_id_value, txid, digest):
    snapshot = mutation.read_text_snapshot(path, allow_missing=False)
    items = _parse_items(snapshot.text, key)
    event = event_by_transaction(items, txid)
    if event is None:
        return None
    if not event_matches(event, operation, digest):
        raise RemoteAccessError(
            "REMOTE_TRANSACTION_REUSED",
            "The transaction ID was already used for a different request.",
            409,
        )
    ticket = _find_ticket(items, ticket_id_value, key)
    revision = source_revision(paths)
    return mutation_response(
        operation,
        txid,
        True,
        revision,
        revision,
        {
            "ticket_id": ticket_id_value,
            "ticket": ticket.to_dict(),
            "event": event_view(event),
            "target_revision_before": snapshot.content_hash,
            "target_revision_after": snapshot.content_hash,
        },
    )


def conflict_current_item(paths, key, ticket_id_value, principal):
    """Return the current ticket dict if the principal can still see it, else None."""
    if not ticket_id_value:
        return None
    path = find_ticket_file(paths, ticket_id_value, key=key)
    if not path:
        return None
    snapshot = mutation.read_text_snapshot(path, allow_missing=True)
    if not snapshot.text:
        return None
    items = _parse_items(snapshot.text, key)
    ticket = _find_ticket(items, ticket_id_value, key)
    if ticket is None:
        return None
    if not can_access(principal, **access_for_item(ticket)):
        return None
    return ticket.to_dict()


def as_remote_error(
    exc,
    payload=None,
    principal=None,
    paths=None,
    key=None,
    ticket_id_value=None,
):
    """Dispatch exc to the Remote error the route should raise.

    payload/principal/paths/key/ticket_id_value are only consulted for a
    conflict: either mutation.MutationConflict (a per-file CAS failure
    inside the mutation itself) or a RemoteAccessError coded
    REVISION_CONFLICT (the earlier, more common aggregate If-Match
    precondition from require_exact_revision). Every other branch is
    unchanged. For a conflict, the detail is built to validate against
    dist/schemas/conflict-v1.schema.json: error="CONFLICT",
    expected_revision, current_revision, attempted_change (payload
    normalized the same way request_hash() normalizes it), and
    current_item (the current ticket's dict form if the principal can
    still see it, else None). Omitted context degrades to an empty
    attempted_change and a None current_item rather than raising.
    """
    is_mutation_conflict = isinstance(exc, mutation.MutationConflict)
    is_precondition_conflict = (
        isinstance(exc, RemoteAccessError) and exc.code == "REVISION_CONFLICT"
    )
    if is_mutation_conflict or is_precondition_conflict:
        operation = str((payload or {}).get("operation") or "")
        if is_mutation_conflict:
            expected_revision = exc.expected_hash
            current_revision = exc.actual_hash
        else:
            expected_revision = exc.detail.get("expected_revision")
            current_revision = exc.detail.get("current_revision")
        detail = OrderedDict(
            (
                ("error", "CONFLICT"),
                ("expected_revision", expected_revision),
                ("current_revision", current_revision),
                ("attempted_change", normalized_change(operation, payload)),
                (
                    "current_item",
                    conflict_current_item(paths, key, ticket_id_value, principal),
                ),
            )
        )
        return RemoteAccessError(
            "REVISION_CONFLICT",
            "The authoritative revision changed.",
            409,
            detail,
        )
    if isinstance(exc, RemoteAccessError):
        return exc
    if isinstance(exc, ValueError):
        detail = (
            {"diagnostics": exc.args[0]}
            if exc.args and isinstance(exc.args[0], list)
            else None
        )
        return RemoteAccessError("REMOTE_TICKET_INVALID", str(exc), 400, detail)
    return RemoteAccessError(
        "REMOTE_TICKET_WRITE_FAILED",
        "The ticket mutation failed.",
        500,
    )


def enrich_capability(original, config, protocol_version=None):
    payload = OrderedDict(original(config, protocol_version))
    if int(protocol_version or 1) < 2:
        return payload
    active = enabled(config)
    features = list(payload.get("features") or [])
    if "ticket-mutations" not in features:
        features.append("ticket-mutations")
    payload["features"] = features
    policy = OrderedDict(payload.get("mutation_policy") or {})
    policy.update(
        {
            "admission_only": not active,
            "authoritative_remote_writes_enabled": active,
            "ticket_mutations_enabled": active,
            "operations": list(OPERATIONS),
            "single_writable_source_only": True,
            "exact_revision_required": True,
            "transaction_id_required": True,
            "append_only_history_required": True,
            "multi_file_mutations_enabled": False,
        }
    )
    payload["mutation_policy"] = policy
    payload["capability_revision"] = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return payload


def ticket_key(config):
    return id_key(config or {})
