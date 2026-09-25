"""Protocol-v2 exact-revision ordinary-item mutations for Remote Safe Mode."""

from __future__ import unicode_literals

import copy
import hashlib
import json
import os
from collections import OrderedDict

from . import mutation
from .ids import (
    collect_item_ids,
    ensure_item_id,
    id_key_from_config,
    id_prefix_for_item,
)
from .native_history import build_item_event, iter_item_events
from .parser import parse_text
from .remote_access import (
    RemoteAccessError,
    can_access,
    require_exact_revision,
    require_scope,
)
from .remote_backend import source_revision
from .remote_ticket_write_core import TOKEN_RE, access_for_item
from .serializer import item_from_dict, item_to_line
from .timezone_policy import utcnow
from .web_read_service import assert_unique_ids
from .webapp import merge_item_payload

ROUTE = "/api/remote/v1/item-mutations"
OPERATIONS = ("create", "update", "delete")
_INSTALLED = False


def _section(config):
    value = (config or {}).get("remote")
    return value if isinstance(value, dict) else {}


def enabled(config):
    return bool(_section(config).get("item_writes_enabled", False))


def _request_hash(operation, payload):
    value = dict(payload or {})
    value.pop("transaction_id", None)
    value["operation"] = operation
    return hashlib.sha256(
        json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()


def _transaction_id(payload):
    value = str((payload or {}).get("transaction_id") or "").strip()
    if not value:
        raise RemoteAccessError(
            "REMOTE_TRANSACTION_REQUIRED", "transaction_id is required.", 428
        )
    if not TOKEN_RE.match(value):
        raise RemoteAccessError(
            "REMOTE_TRANSACTION_INVALID",
            "transaction_id contains unsupported characters.",
            400,
        )
    return value


def _parse(text, key):
    items, diagnostics = parse_text(
        text, id_key=key, check_ids=False, check_references=False
    )
    errors = [row for row in diagnostics if row.severity == "error"]
    if errors:
        raise RemoteAccessError("REMOTE_ITEM_INVALID", errors[0].format(), 400)
    return items


def _values(item, key):
    return [str(value) for value in (item.details.get(key) or [])]


def _find(items, item_id, key, required=True):
    matches = [
        item
        for item in items
        if not list(iter_item_events([item])) and item_id in _values(item, key)
    ]
    if len(matches) != (1 if required else 0):
        code = "REMOTE_ITEM_NOT_FOUND" if not matches else "REMOTE_ITEM_ID_AMBIGUOUS"
        status = 404 if not matches else 409
        raise RemoteAccessError(
            code, "The item ID must resolve to exactly one ordinary item.", status
        )
    return matches[0] if matches else None


def _event_by_transaction(items, txid):
    matches = [
        event
        for event in iter_item_events(items)
        if txid in _values(event, "transaction")
    ]
    if len(matches) > 1:
        raise RemoteAccessError(
            "REMOTE_TRANSACTION_AMBIGUOUS",
            "The transaction ID appears more than once.",
            409,
        )
    return matches[0] if matches else None


def _append(text, item):
    newline = "\r\n" if "\r\n" in text else "\n"
    prefix = text + ("" if not text or text.endswith(("\n", "\r")) else newline)
    return prefix + item_to_line(item).replace("\n", newline) + newline


def _replace(text, item, replacement=None):
    lines = text.splitlines(True)
    start = item.line - 1
    end = getattr(item, "end_line", item.line) or item.line
    if replacement is None:
        del lines[start:end]
    else:
        ending = "\r\n" if lines[end - 1].endswith("\r\n") else "\n"
        lines[start:end] = [(item_to_line(replacement) + ending)]
    return "".join(lines)


def _require_access(item, principal):
    if not can_access(principal, **access_for_item(item)):
        raise RemoteAccessError(
            "REMOTE_ITEM_FORBIDDEN", "The principal cannot access this item.", 403
        )


def _timestamp():
    return utcnow().replace(microsecond=0).isoformat().replace("+00:00", "Z")


def apply(path, paths, config, principal, operation, payload, expected, txid, digest):
    key = id_key_from_config(config or {})
    holder = {}

    def transform(current):
        items = _parse(current, key)
        replay = _event_by_transaction(items, txid)
        if replay is not None:
            if _values(replay, "remote_operation") == [operation] and _values(
                replay, "remote_request_hash"
            ) == [digest]:
                holder.update(replayed=True, item=None, event=replay)
                return current
            raise RemoteAccessError(
                "REMOTE_TRANSACTION_REUSED",
                "The transaction ID was already used for a different request.",
                409,
            )
        item_id = str(payload.get("item_id") or "").strip()
        if operation == "create":
            raw = payload.get("item")
            if not isinstance(raw, dict):
                raise RemoteAccessError(
                    "REMOTE_ITEM_INVALID", "item must be an object.", 400
                )
            after = item_from_dict(raw)
            if after.details.get(key):
                raise RemoteAccessError(
                    "REMOTE_ITEM_ID_SERVER_ASSIGNED",
                    "Create IDs are assigned by the authority.",
                    400,
                )
            ensure_item_id(
                after,
                existing_ids=collect_item_ids(items, key=key),
                key=key,
                prefix=id_prefix_for_item(after, config or {}),
            )
            item_id = _values(after, key)[0]
            _require_access(after, principal)
            changed = _append(current, after)
            event_type, status_field = "created", "after_status"
        else:
            if not item_id:
                raise RemoteAccessError(
                    "REMOTE_ITEM_ID_REQUIRED", "item_id is required.", 428
                )
            before = _find(items, item_id, key)
            _require_access(before, principal)
            if operation == "update":
                patch = payload.get("item")
                if not isinstance(patch, dict):
                    raise RemoteAccessError(
                        "REMOTE_ITEM_INVALID", "item must be an object.", 400
                    )
                after = merge_item_payload(copy.deepcopy(before), patch)
                if _values(after, key) != [item_id]:
                    raise RemoteAccessError(
                        "REMOTE_ITEM_ID_IMMUTABLE",
                        "The canonical item ID cannot change.",
                        409,
                    )
                _require_access(after, principal)
                changed = _replace(current, before, after)
                event_type, status_field = "edited", "after_status"
            else:
                after = before
                changed = _replace(current, before)
                event_type, status_field = "deleted", "before_status"
        parsed = _parse(changed, key)
        if operation != "delete":
            _find(parsed, item_id, key)
        sequence = (
            max(
                [
                    int(_values(e, "sequence")[0])
                    for e in iter_item_events(items, item_id)
                ]
                or [0]
            )
            + 1
        )
        event = build_item_event(
            item_id,
            event_type,
            _timestamp(),
            sequence,
            txid,
            expected,
            actor=principal.get("id"),
            source="remote",
            remote_operation=operation,
            remote_request_hash=digest,
            item_kind=after.kind,
            item_title=after.title,
            **{status_field: after.status},
        )
        final = _append(changed, event)
        _parse(final, key)
        holder.update(replayed=False, item=after, item_id=item_id, event=event)
        return final

    result = mutation.mutate_text(
        path, transform, expected_hash=expected, operation="remote.item.%s" % operation
    )
    return holder, result


def _response(operation, txid, holder, before, after, result):
    return OrderedDict(
        (
            ("schema", "remote-item-mutation-v1"),
            ("operation", operation),
            ("transaction_id", txid),
            ("replayed", bool(holder.get("replayed"))),
            ("revision_before", before),
            ("revision_after", after),
            ("target_revision_before", result.before_hash),
            ("target_revision_after", result.after_hash),
            ("item_id", holder.get("item_id")),
        )
    )


def _replay_response(path, paths, key, operation, txid, digest):
    target = mutation.read_text_snapshot(path)
    event = _event_by_transaction(_parse(target.text, key), txid)
    if event is None:
        return None
    if _values(event, "remote_operation") != [operation] or _values(
        event, "remote_request_hash"
    ) != [digest]:
        raise RemoteAccessError(
            "REMOTE_TRANSACTION_REUSED",
            "The transaction ID was already used for a different request.",
            409,
        )
    revision = source_revision(paths)
    return OrderedDict(
        (
            ("schema", "remote-item-mutation-v1"),
            ("operation", operation),
            ("transaction_id", txid),
            ("replayed", True),
            ("revision_before", revision),
            ("revision_after", revision),
            ("target_revision_before", target.content_hash),
            ("target_revision_after", target.content_hash),
            ("item_id", _values(event, "parent")[0]),
        )
    )


def install_remote_item_writes():
    global _INSTALLED
    if _INSTALLED:
        return
    from . import config_registry, remote_access, remote_web, surface_runtime, webapp

    config_registry.CONFIG_REGISTRY.setdefault(
        "remote.item_writes_enabled",
        config_registry._entry(
            "boolean",
            False,
            "Enable protocol-v2 exact-revision ordinary-item Remote mutations.",
            restart_required=True,
        ),
    )
    surface_runtime._WEB_NO_REVISION_PATHS = frozenset(
        set(surface_runtime._WEB_NO_REVISION_PATHS) | {ROUTE}
    )
    original_capability = remote_access.capability

    def capability(config, protocol_version=None):
        value = OrderedDict(original_capability(config, protocol_version))
        if int(protocol_version or 1) >= 2:
            features = list(value.get("features") or [])
            if "item-mutations" not in features:
                features.append("item-mutations")
            value["features"] = features
            policy = OrderedDict(value.get("mutation_policy") or {})
            policy["item_mutations_enabled"] = enabled(config)
            policy["item_operations"] = list(OPERATIONS)
            value["mutation_policy"] = policy
            value["capability_revision"] = hashlib.sha256(
                json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest()
        return value

    remote_access.capability = capability
    remote_access.capability_revision = lambda config: capability(config, 2)[
        "capability_revision"
    ]
    remote_web.capability = capability
    original_create_app = webapp.create_app

    def create_app(paths=None, writable_path=None, config=None, read_only=False):
        from fastapi import Body, Request

        app = original_create_app(
            paths=paths, writable_path=writable_path, config=config, read_only=read_only
        )

        @app.post(ROUTE)
        def remote_item_mutation(request: Request, payload=Body(default={})):
            try:
                if int(getattr(request.state, "remote_protocol", 1)) < 2:
                    raise RemoteAccessError(
                        "REMOTE_VERSION_REQUIRED",
                        "Item mutations require protocol version 2.",
                        426,
                    )
                principal = request.state.remote_principal
                require_scope(principal, "write")
                if read_only or not enabled(app.state.config):
                    raise RemoteAccessError(
                        "REMOTE_ITEM_WRITES_DISABLED",
                        "Remote item mutations are disabled.",
                        403,
                    )
                operation = str(payload.get("operation") or "").lower()
                if operation not in OPERATIONS:
                    raise RemoteAccessError(
                        "REMOTE_ITEM_OPERATION_UNKNOWN",
                        "Unsupported item operation.",
                        400,
                    )
                txid, digest = (
                    _transaction_id(payload),
                    _request_hash(operation, payload),
                )
                key = id_key_from_config(app.state.config)
                prior = _replay_response(
                    app.state.writable_path,
                    app.state.paths,
                    key,
                    operation,
                    txid,
                    digest,
                )
                if prior is not None:
                    return prior
                from .remote_backend import _read

                workspace_items, _diagnostics = _read(app.state.paths, app.state.config)
                assert_unique_ids(
                    workspace_items, key=id_key_from_config(app.state.config)
                )
                before = source_revision(app.state.paths)
                require_exact_revision(request.headers, before)
                expected = mutation.read_text_snapshot(
                    app.state.writable_path
                ).content_hash
                holder, result = apply(
                    app.state.writable_path,
                    app.state.paths,
                    app.state.config,
                    principal,
                    operation,
                    payload,
                    expected,
                    txid,
                    digest,
                )
                after = source_revision(app.state.paths)
                return _response(operation, txid, holder, before, after, result)
            except mutation.MutationConflict as exc:
                raise RemoteAccessError(
                    "REVISION_CONFLICT",
                    "The authoritative revision changed.",
                    409,
                    {
                        "expected_revision": exc.expected_hash,
                        "current_revision": exc.actual_hash,
                    },
                )
            except RemoteAccessError:
                raise
            except ValueError as exc:
                raise RemoteAccessError("REMOTE_ITEM_INVALID", str(exc), 400)

        return app

    webapp.create_app = create_app
    _INSTALLED = True
