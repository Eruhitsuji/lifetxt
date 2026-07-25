"""Exact-revision contracts for local development-ticket writes.

Ticket writes reuse :mod:`lifetxt.mutation` rather than introducing a ticket-
specific lock or hash.  The complete source file is transformed while the
shared sidecar lock is held; an optional exact SHA-256 precondition rejects a
stale caller before any authoritative bytes are replaced.
"""

from __future__ import unicode_literals

import argparse
import copy
import json
from collections import OrderedDict

from . import mutation
from .mutation import MutationConflict
from .safe_ops import ExpectedRevisionRequired
from .surface_runtime import normalize_revision


_INSTALLED = False
_ORIGINALS = {}
_WRITE_COMMANDS = ("edit", "assign", "close", "reopen", "link", "unlink")


def _truthy(value):
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in ("1", "true", "yes", "on", "required")


def ticket_write_revision_required(config=None):
    """Whether local ticket mutations must receive an exact revision token."""
    config = config or {}
    section = config.get("ticketing") if isinstance(config, dict) else None
    section = section if isinstance(section, dict) else {}
    write = section.get("write")
    write = write if isinstance(write, dict) else {}
    raw = write.get("require_revision")
    if raw is None:
        raw = section.get("require_write_revision")
    return _truthy(raw)


def ticket_file_revision(path):
    """Return the exact SHA-256 revision used by the shared mutation layer."""
    return mutation.read_text_snapshot(path, allow_missing=False).content_hash


def _diagnostic_errors(diagnostics):
    return [
        diagnostic.to_dict()
        for diagnostic in diagnostics
        if getattr(diagnostic, "severity", None) == "error"
    ]


def _find_ticket_in_text(text, ticket_id, key):
    from .parser import parse_text
    from .tickets import is_ticket

    items, diagnostics = parse_text(
        text,
        id_key=key,
        check_ids=False,
        check_references=False,
    )
    errors = _diagnostic_errors(diagnostics)
    if errors:
        raise ValueError(errors)
    matches = []
    for item in items:
        if not is_ticket(item):
            continue
        if str(ticket_id) in [str(value) for value in item.details.get(key, [])]:
            matches.append(item)
    if not matches:
        raise ValueError("Ticket %r not found." % ticket_id)
    if len(matches) > 1:
        raise ValueError("Multiple tickets found with %s:%s." % (key, ticket_id))
    return matches[0]


def _replace_ticket_text(text, ticket_id, key, update_item):
    from .parser import parse_text
    from .serializer import item_to_line
    from .webapp import split_line_ending, _with_line_ending

    item = _find_ticket_in_text(text, ticket_id, key)
    if item.line is None:
        raise ValueError("Ticket %r has no writable source line." % ticket_id)

    updated = copy.copy(item)
    updated.details = OrderedDict(
        (detail_key, list(values)) for detail_key, values in item.details.items()
    )
    update_item(updated)
    line = item_to_line(updated)
    parsed, diagnostics = parse_text(
        line + "\n",
        id_key=key,
        check_ids=False,
        check_references=False,
    )
    errors = _diagnostic_errors(diagnostics)
    if not parsed or errors:
        if not errors:
            errors = [{"severity": "error", "code": "E301", "message": "Updated ticket did not parse."}]
        raise ValueError(errors)

    raw_lines = text.splitlines(True)
    start = item.line - 1
    end_line = getattr(item, "end_line", item.line) or item.line
    if start < 0 or end_line > len(raw_lines):
        raise ValueError("Ticket %r source span is out of range." % ticket_id)
    _body, ending = split_line_ending(raw_lines[end_line - 1])
    replacement = _with_line_ending(line, ending).splitlines(True)
    raw_lines[start:end_line] = replacement

    updated.line = item.line
    updated.end_line = item.line + len(line.splitlines()) - 1
    updated.source_text = line
    return "".join(raw_lines), updated


def _decorate_result(item, before_hash, after_hash, changed, dry_run):
    item.revision_before = before_hash
    item.revision_after = after_hash
    item.revision_changed = bool(changed)
    item.revision_dry_run = bool(dry_run)
    return item


def _apply_ticket_transform(
    path,
    ticket_id,
    key,
    update_item,
    expected_revision=None,
    require_revision=False,
    dry_run=False,
    operation="ticket.patch",
):
    supplied = expected_revision is not None
    expected = normalize_revision(expected_revision, supplied=supplied)
    if require_revision and expected is None:
        raise ExpectedRevisionRequired(
            "%s requires --revision. Read the current ticket file revision and retry."
            % operation
        )

    if dry_run:
        before = mutation.read_text_snapshot(path, allow_missing=False)
        if expected is not None and expected != before.content_hash:
            raise MutationConflict(
                path,
                expected,
                before.content_hash,
                operation=operation,
            )
        replacement, updated = _replace_ticket_text(
            before.text, ticket_id, key, update_item
        )
        after_hash = mutation.hash_text(
            replacement,
            encoding=before.encoding,
            bom=before.bom,
        )
        return _decorate_result(
            updated,
            before.content_hash,
            after_hash,
            after_hash != before.content_hash,
            True,
        )

    holder = {}

    def transform(current):
        replacement, updated = _replace_ticket_text(
            current, ticket_id, key, update_item
        )
        holder["item"] = updated
        return replacement

    result = mutation.mutate_text(
        path,
        transform,
        expected_hash=expected,
        operation=operation,
    )
    return _decorate_result(
        holder["item"],
        result.before_hash,
        result.after_hash,
        result.changed,
        False,
    )


def apply_ticket_patch(
    path,
    ticket_id,
    detail_updates=None,
    status=None,
    key="id",
    expected_revision=None,
    require_revision=False,
    dry_run=False,
    operation="ticket.patch",
):
    """Patch ticket fields under the shared lock and optional exact revision."""

    def update_item(item):
        for detail_key, value in (detail_updates or {}).items():
            if value is None:
                item.details.pop(detail_key, None)
            elif isinstance(value, (list, tuple)):
                item.details[detail_key] = [str(entry) for entry in value]
            else:
                item.details[detail_key] = [str(value)]
        if status is not None:
            item.status = str(status)

    return _apply_ticket_transform(
        path,
        ticket_id,
        key,
        update_item,
        expected_revision=expected_revision,
        require_revision=require_revision,
        dry_run=dry_run,
        operation=operation,
    )


def apply_ticket_relation(
    path,
    ticket_id,
    relation,
    target_id,
    add=True,
    key="id",
    expected_revision=None,
    require_revision=False,
    dry_run=False,
    operation=None,
):
    """Add/remove a ticket relation using values re-read inside the lock."""
    from .tickets import RELATION_FIELDS

    relation = str(relation)
    target_id = str(target_id)
    if relation not in RELATION_FIELDS:
        raise ValueError(
            "Unknown ticket relation %r. Use one of: %s."
            % (relation, ", ".join(RELATION_FIELDS))
        )

    def update_item(item):
        existing = [str(value) for value in item.details.get(relation, [])]
        if add:
            if target_id not in existing:
                item.details[relation] = existing + [target_id]
        else:
            if target_id not in existing:
                raise ValueError(
                    "%s has no %s:%s" % (ticket_id, relation, target_id)
                )
            remaining = [value for value in existing if value != target_id]
            if remaining:
                item.details[relation] = remaining
            else:
                item.details.pop(relation, None)

    return _apply_ticket_transform(
        path,
        ticket_id,
        key,
        update_item,
        expected_revision=expected_revision,
        require_revision=require_revision,
        dry_run=dry_run,
        operation=operation or ("ticket.link" if add else "ticket.unlink"),
    )


def ticket_write_revision_contract(config=None):
    return OrderedDict(
        (
            ("contract_version", "1"),
            ("algorithm", "sha256"),
            ("scope", "exact authoritative source-file bytes"),
            ("discover", "ticket revision"),
            ("cli_option", "--revision / --expected-revision"),
            ("require_option", "--require-revision"),
            ("required_by_config", ticket_write_revision_required(config)),
            ("config_key", "ticketing.write.require_revision"),
            ("write_operations", list(_WRITE_COMMANDS)),
            ("lock", "shared sidecar mutation lock"),
            ("stale_behavior", "reject before replacement and preserve current bytes"),
            ("remote_writes_enabled", False),
        )
    )


def _subparsers_action(parser):
    for action in getattr(parser, "_actions", []):
        if isinstance(action, argparse._SubParsersAction):
            return action
    return None


def _has_option(parser, option):
    return any(
        option in getattr(action, "option_strings", [])
        for action in getattr(parser, "_actions", [])
    )


def _add_write_options(parser):
    if not _has_option(parser, "--revision"):
        parser.add_argument(
            "--revision",
            "--expected-revision",
            dest="expected_revision",
            help="Exact SHA-256 from `ticket revision`; stale values are rejected.",
        )
    if not _has_option(parser, "--require-revision"):
        parser.add_argument(
            "--require-revision",
            action="store_true",
            help="Reject the write when --revision is omitted.",
        )
    if not _has_option(parser, "--dry-run"):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Validate the revision and compute the post-write revision without writing.",
        )


def _command_ticket_revision(args):
    from . import cli as cli_module
    from .tickets import find_ticket_file

    config = cli_module._config(args)
    key = cli_module.id_key_from_config(config)
    path = find_ticket_file(cli_module._ticket_paths(args), args.id, key=key)
    if not path:
        raise ValueError("Ticket %r not found." % args.id)
    result = OrderedDict(
        (
            ("id", args.id),
            ("path", path),
            ("algorithm", "sha256"),
            ("revision", ticket_file_revision(path)),
        )
    )
    if getattr(args, "json", False):
        cli_module.write_text(
            None,
            json.dumps(
                result,
                ensure_ascii=False,
                indent=2 if getattr(args, "pretty", False) else None,
                separators=None if getattr(args, "pretty", False) else (",", ":"),
            )
            + "\n",
        )
    else:
        cli_module.write_text(None, result["revision"] + "\n")
    return 0


def _install_cli_arguments(parser, cli_module):
    root = _subparsers_action(parser)
    if root is None:
        return parser
    ticket_parser = root.choices.get("ticket")
    ticket_actions = _subparsers_action(ticket_parser) if ticket_parser else None
    if ticket_actions is None:
        return parser
    for command in _WRITE_COMMANDS:
        command_parser = ticket_actions.choices.get(command)
        if command_parser is not None:
            _add_write_options(command_parser)
    if "revision" not in ticket_actions.choices:
        revision_parser = ticket_actions.add_parser(
            "revision",
            help="Print the exact source-file revision for one ticket.",
        )
        revision_parser.add_argument("id", help="Ticket ID.")
        cli_module._add_input_paths(revision_parser)
        revision_parser.add_argument("--json", action="store_true")
        revision_parser.add_argument("--pretty", action="store_true")
        revision_parser.set_defaults(func=_command_ticket_revision)
    return parser


def _expected_and_required(args, config):
    return (
        getattr(args, "expected_revision", None),
        bool(getattr(args, "require_revision", False))
        or ticket_write_revision_required(config),
    )


def _patch_cli():
    from . import cli as cli_module

    if "cli_build_parser" in _ORIGINALS:
        return
    _ORIGINALS["cli_build_parser"] = cli_module.build_parser
    _ORIGINALS["ticket_patch_and_report"] = cli_module._ticket_patch_and_report
    _ORIGINALS["command_ticket_edit"] = cli_module.command_ticket_edit
    _ORIGINALS["ticket_relation_edit"] = cli_module._ticket_relation_edit

    def build_parser():
        return _install_cli_arguments(_ORIGINALS["cli_build_parser"](), cli_module)

    def patch_and_report(args, ticket_id, detail_updates, status=None, verb="Updated"):
        config = cli_module._config(args)
        key = cli_module.id_key_from_config(config)
        target = cli_module._ticket_write_file(args, ticket_id)
        cli_module._ensure_writable_path(target, config, "ticket edit")
        expected, required = _expected_and_required(args, config)
        try:
            updated = apply_ticket_patch(
                target,
                ticket_id,
                detail_updates,
                status=status,
                key=key,
                expected_revision=expected,
                require_revision=required,
                dry_run=bool(getattr(args, "dry_run", False)),
                operation="ticket.%s" % str(verb).strip().lower(),
            )
        except (ExpectedRevisionRequired, MutationConflict, ValueError) as exc:
            cli_module.sys.stderr.write("ERROR: %s\n" % exc)
            return 1
        if getattr(args, "dry_run", False):
            cli_module.write_text(
                None,
                "Would %s %s in %s\n  revision: %s -> %s\n"
                % (
                    str(verb).lower(),
                    ticket_id,
                    target,
                    updated.revision_before,
                    updated.revision_after,
                ),
            )
        else:
            cli_module.write_text(
                None,
                "%s %s in %s\n  revision: %s -> %s\n"
                % (
                    verb,
                    ticket_id,
                    target,
                    updated.revision_before,
                    updated.revision_after,
                ),
            )
        return 0

    def command_ticket_edit(args):
        updates = OrderedDict()
        for pair in getattr(args, "set_fields", None) or []:
            if "=" not in pair:
                cli_module.sys.stderr.write(
                    "ERROR: --set expects KEY=VALUE, got %r\n" % pair
                )
                return 1
            field, value = pair.split("=", 1)
            updates[field.strip()] = value.strip()
        for field in getattr(args, "unset", None) or []:
            updates[field.strip()] = None
        if not updates:
            cli_module.sys.stderr.write(
                "ERROR: nothing to change; use --set or --unset.\n"
            )
            return 1
        return patch_and_report(args, args.id, updates, verb="Edited")

    def ticket_relation_edit(args, add):
        config = cli_module._config(args)
        key = cli_module.id_key_from_config(config)
        target = cli_module._ticket_write_file(args, args.id)
        cli_module._ensure_writable_path(
            target, config, "ticket link" if add else "ticket unlink"
        )
        expected, required = _expected_and_required(args, config)
        try:
            updated = apply_ticket_relation(
                target,
                args.id,
                args.relation,
                args.target,
                add=add,
                key=key,
                expected_revision=expected,
                require_revision=required,
                dry_run=bool(getattr(args, "dry_run", False)),
            )
        except (ExpectedRevisionRequired, MutationConflict, ValueError) as exc:
            cli_module.sys.stderr.write("ERROR: %s\n" % exc)
            return 1
        action = "Linked" if add else "Unlinked"
        if getattr(args, "dry_run", False):
            action = "Would link" if add else "Would unlink"
        elif not updated.revision_changed and add:
            cli_module.write_text(
                None,
                "%s already has %s:%s\n" % (args.id, args.relation, args.target),
            )
            return 0
        cli_module.write_text(
            None,
            "%s %s %s:%s\n  revision: %s -> %s\n"
            % (
                action,
                args.id,
                args.relation,
                args.target,
                updated.revision_before,
                updated.revision_after,
            ),
        )
        return 0

    cli_module.build_parser = build_parser
    cli_module._ticket_patch_and_report = patch_and_report
    cli_module.command_ticket_edit = command_ticket_edit
    cli_module._ticket_relation_edit = ticket_relation_edit


def _patch_capabilities():
    from . import safety_foundation, surface_runtime

    if "surface_capability_document_for" in _ORIGINALS:
        return
    original_for = surface_runtime.capability_document_for
    original_base = safety_foundation.capability_document
    _ORIGINALS["surface_capability_document_for"] = original_for
    _ORIGINALS["base_capability_document"] = original_base

    def enrich(data, config=None):
        result = OrderedDict(data)
        result["ticket_write_revision"] = ticket_write_revision_contract(config)
        return result

    def capability_document_for(
        surface,
        read_only=False,
        authentication="token",
        writable_targets=None,
        config=None,
    ):
        return enrich(
            original_for(
                surface,
                read_only=read_only,
                authentication=authentication,
                writable_targets=writable_targets,
                config=config,
            ),
            config=config,
        )

    def capability_document(
        read_only=False,
        authentication="token",
        writable_targets=None,
        config=None,
    ):
        return enrich(
            original_base(
                read_only=read_only,
                authentication=authentication,
                writable_targets=writable_targets,
                config=config,
            ),
            config=config,
        )

    surface_runtime.capability_document_for = capability_document_for
    safety_foundation.capability_document = capability_document


def install_ticket_revision_writes():
    global _INSTALLED
    if _INSTALLED:
        return
    from . import tickets

    tickets.apply_ticket_patch = apply_ticket_patch
    tickets.apply_ticket_relation = apply_ticket_relation
    tickets.ticket_file_revision = ticket_file_revision
    _patch_cli()
    _patch_capabilities()
    _INSTALLED = True
