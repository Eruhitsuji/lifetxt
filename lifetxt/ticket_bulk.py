"""Frozen local single-file assignment plans and one compare-and-swap apply."""

import hashlib
import json
import os
import re

from . import mutation
from .ticket_activity import (
    _first,
    _utc_text,
    _sequence,
    _changed_fields,
    build_ticket_event,
    event_view,
    iter_ticket_events,
    validate_ticket_history,
)
from .ticket_activity_mutation import _parse_items, _find_ticket, _append_items
from .ticket_revision_writes import _replace_ticket_text
from .tickets import validate_ticket

MAX_IDS = 100
MAX_PLAN_BYTES = 2 * 1024 * 1024


def _digest(value):
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


def _scalar(value, label):
    if (
        not isinstance(value, str)
        or not value.strip()
        or len(value) > 256
        or any(ord(c) < 32 or ord(c) == 127 for c in value)
    ):
        raise ValueError(
            "%s must be a nonblank single-line string (max 256 characters)." % label
        )
    return value


def _target(path, config):
    from . import cli
    from .workspace import resolve_workspace

    if (
        not isinstance(path, str)
        or path == "-"
        or not os.path.isfile(path)
        or os.path.islink(path)
    ):
        raise ValueError(
            "Bulk assignment requires one existing non-symlink local file."
        )
    real = os.path.realpath(path)
    if (
        config.get("workspaces")
        or config.get("default_workspace")
        or config.get("_active_workspace")
    ):
        resolution = resolve_workspace(config, config.get("_active_workspace"))
        if not resolution["ok"]:
            raise ValueError("Invalid workspace; bulk assignment refused.")
        matches = [
            r
            for r in resolution["sources"]
            if real in [os.path.realpath(p) for p in r["files"]]
        ]
        if (
            len(matches) != 1
            or not matches[0]["writable"]
            or matches[0]["role"] in ("generated", "archive", "reference")
        ):
            raise ValueError(
                "Bulk target must be a writable active source, never archive/generated/reference."
            )
        paths = resolution["input_paths"]
    else:
        paths = cli.config_paths(config)
    if paths and {os.path.realpath(p) for p in paths} != {real}:
        raise ValueError(
            "Bulk assignment v1 requires a single-file workspace; cross-file scope is unsupported."
        )
    cli._ensure_writable_path(real, config, "ticket.bulk.assign")
    return real


def _transform(text, params, config):
    key = params["id_key"]
    items = _parse_items(text, key)
    transaction = params["transaction_id"]
    prefix = "BULK-%s-" % transaction
    if any(
        str(_first(event, "transaction", "")).startswith(prefix)
        for event in iter_ticket_events(items)
    ):
        raise ValueError(
            "Bulk transaction already applied or reused with different content."
        )
    # Resolve every target before computing replacements. Nothing is written here.
    before = [_find_ticket(items, target, key) for target in params["ids"]]
    if any(
        len(item.details.get(key, [])) != 1
        or item.details.get("record", []) != ["ticket"]
        for item in before
    ):
        raise ValueError(
            "Bulk targets require unambiguous scalar id and record markers."
        )
    current = text
    events = []
    changes = []
    for target, original in zip(params["ids"], before):
        if original.details.get("assignee", []) == [params["assignee"]]:
            errors = [
                d
                for d in validate_ticket(original, config, key=key)
                if d.get("severity") == "error"
            ]
            if errors:
                raise ValueError(errors)
            changes.append({"ticket_id": target, "changed": False, "event": None})
            continue

        def assign(item):
            item.details["assignee"] = [params["assignee"]]

        current, updated = _replace_ticket_text(current, target, key, assign)
        errors = [
            d
            for d in validate_ticket(updated, config, key=key)
            if d.get("severity") == "error"
        ]
        if errors:
            raise ValueError(errors)
        txid = prefix + hashlib.sha256(target.encode("utf-8")).hexdigest()
        event = build_ticket_event(
            target,
            "assignment",
            params["actor"],
            params["at"],
            _sequence(items, target),
            txid,
            params["revision_before"],
            changes=_changed_fields(original, updated),
            project=_first(updated, "project"),
            tracker=_first(updated, "tracker"),
            from_status=_first(original, "ticket_status"),
            to_status=_first(updated, "ticket_status"),
        )
        events.append(event)
        changes.append(
            {"ticket_id": target, "changed": True, "event": event_view(event)}
        )
    result = _append_items(current, events)
    errors = [
        d
        for d in validate_ticket_history(
            _parse_items(result, key), config=config, key=key
        )
        if d.get("severity") == "error"
    ]
    if errors:
        raise ValueError(errors)
    return result, changes


def preview_assignment(
    path,
    ids,
    assignee,
    actor,
    expected_revision,
    transaction_id,
    config=None,
    key="id",
    at=None,
):
    config = config or {}
    path = _target(path, config)
    if (
        not isinstance(ids, list)
        or not 1 <= len(ids) <= MAX_IDS
        or len(set(ids)) != len(ids)
    ):
        raise ValueError("Select 1..100 unique explicit ticket ids.")
    ids = [_scalar(value, "Ticket id") for value in ids]
    if not isinstance(transaction_id, str) or not re.fullmatch(
        r"[A-Za-z0-9_.]{1,128}", transaction_id
    ):
        raise ValueError(
            "Transaction id must contain 1..128 letters, digits, underscores or periods."
        )
    snapshot = mutation.read_text_snapshot(path, allow_missing=False)
    if not isinstance(expected_revision, str) or not re.fullmatch(
        r"[0-9a-f]{64}", expected_revision
    ):
        raise ValueError("An exact lowercase SHA-256 revision is required.")
    if snapshot.content_hash != expected_revision:
        raise mutation.MutationConflict(
            path,
            expected_revision,
            snapshot.content_hash,
            operation="ticket.bulk.preview",
        )
    params = {
        "contract_version": "1",
        "operation": "ticket.bulk.assign",
        "path": path,
        "revision_before": expected_revision,
        "config_sha256": _digest(config),
        "id_key": key,
        "ids": ids,
        "assignee": _scalar(assignee, "Assignee"),
        "actor": _scalar(actor, "Actor"),
        "at": _utc_text(at),
        "transaction_id": transaction_id,
    }
    after, changes = _transform(snapshot.text, params, config)
    plan = dict(
        params,
        changes=changes,
        revision_after=mutation.hash_text(
            after, encoding=snapshot.encoding, bom=snapshot.bom
        ),
    )
    plan["plan_sha256"] = _digest(plan)
    return plan


def apply_assignment_plan(plan, expected_plan_sha256, config=None, key="id"):
    config = config or {}
    fields = {
        "contract_version",
        "operation",
        "path",
        "revision_before",
        "config_sha256",
        "id_key",
        "ids",
        "assignee",
        "actor",
        "at",
        "transaction_id",
        "changes",
        "revision_after",
        "plan_sha256",
    }
    if not isinstance(plan, dict) or set(plan) != fields:
        raise ValueError("Unsupported or malformed bulk plan.")
    unsigned = {k: v for k, v in plan.items() if k != "plan_sha256"}
    if (
        plan["plan_sha256"] != expected_plan_sha256
        or _digest(unsigned) != expected_plan_sha256
    ):
        raise ValueError("Plan digest differs from the explicitly reviewed digest.")
    if plan["config_sha256"] != _digest(config) or plan["id_key"] != key:
        raise ValueError("Configuration or id key changed since preview.")
    fresh = preview_assignment(
        plan["path"],
        plan["ids"],
        plan["assignee"],
        plan["actor"],
        plan["revision_before"],
        plan["transaction_id"],
        config,
        key,
        plan["at"],
    )
    if fresh != plan:
        raise ValueError("Frozen plan does not match current deterministic preview.")

    def transform(current):
        after, changes = _transform(current, plan, config)
        if changes != plan["changes"]:
            raise ValueError("Ticket changes differ from frozen preview.")
        return after

    result = mutation.mutate_text(
        plan["path"],
        transform,
        expected_hash=plan["revision_before"],
        operation="ticket.bulk.assign",
    )
    return {
        "operation": plan["operation"],
        "transaction_id": plan["transaction_id"],
        "revision_before": plan["revision_before"],
        "revision_after": plan["revision_after"],
        "changed": result.changed,
        "changes": plan["changes"],
        "plan_sha256": expected_plan_sha256,
    }


def command_bulk(args):
    from . import cli
    from .ticket_workflow_cli import _actor

    try:
        config = cli._config(args)
        key = cli.id_key_from_config(config)
        if args.bulk_command == "assign":
            result = preview_assignment(
                args.path,
                args.ids,
                args.assignee,
                _actor(args, config, cli),
                args.expected_revision,
                args.transaction_id,
                config,
                key,
                args.at,
            )
        else:
            with open(args.plan, "rb") as handle:
                raw = handle.read(MAX_PLAN_BYTES + 1)
            if len(raw) > MAX_PLAN_BYTES:
                raise ValueError("Bulk plan exceeds 2 MiB.")
            result = apply_assignment_plan(
                json.loads(raw), args.plan_sha256, config, key
            )
        cli.write_text(None, json.dumps(result, ensure_ascii=False, indent=2) + "\n")
        return 0
    except (ValueError, TypeError, OSError, mutation.MutationConflict) as exc:
        cli.sys.stderr.write("ERROR: %s\n" % exc)
        return 1


def install_bulk_parser(actions):
    parser = actions.add_parser(
        "bulk",
        help="Frozen single-file assignment preview and atomic apply (local only).",
    )
    commands = parser.add_subparsers(dest="bulk_command", required=True)
    preview = commands.add_parser(
        "assign", help="Preview only; redirect JSON to a separate plan file."
    )
    preview.add_argument("path")
    preview.add_argument("--id", dest="ids", action="append", required=True)
    preview.add_argument("--assignee", required=True)
    preview.add_argument("--actor")
    preview.add_argument("--revision", dest="expected_revision", required=True)
    preview.add_argument("--transaction-id", required=True)
    preview.add_argument("--at")
    preview.add_argument(
        "--dry-run", action="store_true", help="Preview is always read-only."
    )
    apply = commands.add_parser("apply", help="Apply the exact reviewed JSON plan.")
    apply.add_argument("plan")
    apply.add_argument("--plan-sha256", required=True)
    for command in (preview, apply):
        command.set_defaults(func=command_bulk)
