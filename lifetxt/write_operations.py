"""Revision-aware semantic write operations shared by CLI, TUI, and fzf.

The public helpers in this module never trust a replacement assembled from a stale
file read.  They re-parse the current in-lock text, identify records by stable ID,
apply typed changes, validate the resulting life.txt, and commit through the common
mutation or journal-backed multi-target contract.
"""

from __future__ import unicode_literals

import copy
import os
from collections import OrderedDict

from . import mutation
from .mutation import MISSING_HASH, MutationConflict
from .multi_target import apply_multi_target, json_plan, text_plan
from .parser import parse_text
from .serializer import item_to_line


class SemanticWriteError(ValueError):
    pass


def snapshot(path, allow_missing=False):
    return mutation.read_text_snapshot(path, allow_missing=allow_missing)


def resolve_expected_revision(path, expected_revision=None, allow_missing=False):
    current = snapshot(path, allow_missing=allow_missing)
    expected = current.content_hash if expected_revision in (None, "") else str(expected_revision)
    return current, expected


def append_text(path, payload, expected_revision=None, operation="semantic.append", create=True):
    current, expected = resolve_expected_revision(path, expected_revision, allow_missing=create)
    value = str(payload)

    def transform(text):
        if not value:
            return text
        prefix = "" if not text or text.endswith(("\n", "\r")) else current.newline
        return text + prefix + value

    return mutation.mutate_text(
        path,
        transform,
        expected_hash=expected,
        operation=operation,
        create=create and expected == MISSING_HASH,
        default_text="",
    )


def append_life_records(path, text, expected_revision=None, operation="semantic.append_records"):
    payload = str(text)
    if payload and not payload.endswith(("\n", "\r")):
        payload += "\n"

    def validate(replacement):
        _parse_or_raise(replacement)
        return True

    current, expected = resolve_expected_revision(path, expected_revision, allow_missing=True)

    def transform(existing):
        prefix = "" if not existing or existing.endswith(("\n", "\r")) else current.newline
        return existing + prefix + payload

    return mutation.mutate_text(
        path,
        transform,
        expected_hash=expected,
        operation=operation,
        create=expected == MISSING_HASH,
        default_text="",
        validate=validate,
    )


def mutate_items(
    path,
    changes,
    id_key="id",
    expected_revision=None,
    operation="items.semantic",
    create=False,
):
    """Apply multiple ID-addressed changes to one life.txt file in one CAS write.

    ``changes`` is an iterable of mappings with ``id`` and optional ``status``,
    ``set_details`` and ``delete`` fields.  Empty detail value lists remove a key.
    Every requested ID must match exactly one record in the current in-lock text.
    """
    normalized = _normalize_changes(changes)
    current, expected = resolve_expected_revision(path, expected_revision, allow_missing=create)

    def transform(text):
        return transform_items_text(text, normalized, id_key=id_key)

    return mutation.mutate_text(
        path,
        transform,
        expected_hash=expected,
        operation=operation,
        create=create and expected == MISSING_HASH,
        default_text="",
        validate=lambda replacement: _parse_or_raise(replacement),
    )


def transform_items_text(text, changes, id_key="id"):
    changes = _normalize_changes(changes)
    items, diagnostics = parse_text(
        text,
        id_key=id_key,
        check_ids=False,
        check_references=False,
    )
    _raise_parse_errors(diagnostics)
    by_id = OrderedDict()
    for item in items:
        for value in item.details.get(id_key, []):
            by_id.setdefault(str(value), []).append(item)

    rows = []
    for change in changes:
        item_id = change["id"]
        matches = by_id.get(item_id, [])
        if len(matches) != 1:
            raise SemanticWriteError(
                "Expected exactly one item with %s:%s, found %d."
                % (id_key, item_id, len(matches))
            )
        item = matches[0]
        start = (item.line or 1) - 1
        end = getattr(item, "end_line", item.line) or item.line or 1
        if change.get("delete"):
            replacement = ""
        else:
            updated = copy.deepcopy(item)
            if change.get("status") is not None:
                updated.status = str(change["status"])
            for key, values in (change.get("set_details") or {}).items():
                if values is None or values == []:
                    updated.details.pop(str(key), None)
                else:
                    if isinstance(values, (list, tuple)):
                        updated.details[str(key)] = [str(value) for value in values]
                    else:
                        updated.details[str(key)] = [str(values)]
            replacement = item_to_line(updated)
        rows.append((start, end, replacement))

    lines = text.splitlines(True)
    default_ending = _preferred_newline(text)
    for start, end, replacement in sorted(rows, reverse=True):
        ending = default_ending
        if 0 <= end - 1 < len(lines):
            ending = _line_ending(lines[end - 1])
        replacement_lines = [] if replacement == "" else (replacement + ending).splitlines(True)
        lines[start:end] = replacement_lines
    result = "".join(lines)
    _parse_or_raise(result)
    return result


def mutate_item_files(file_changes, id_key="id", operation="items.multi_file", journal_dir=None):
    """Commit ID-addressed changes across files in one journal-backed transaction."""
    plans = []
    for path in sorted(file_changes):
        spec = file_changes[path]
        expected = spec.get("expected_revision")
        current, expected = resolve_expected_revision(path, expected, allow_missing=False)
        changes = _normalize_changes(spec.get("changes") or [])
        plans.append(
            text_plan(
                path,
                lambda text, _changes=changes: transform_items_text(text, _changes, id_key=id_key),
                expected,
                validate=lambda replacement: _parse_or_raise(replacement),
            )
        )
    return apply_multi_target(plans, operation=operation, journal_dir=journal_dir)



def commit_text_replacements(replacements, operation="text.multi_replace", journal_dir=None, config=None):
    """Commit precomputed replacements with exact source revisions in one journal.

    Each value is a mapping containing ``text`` and optional ``expected_revision``,
    ``create``, and ``validate_life``.  This helper is intended for legacy commands
    whose existing selection logic is complex but whose final writes can still be
    made all-or-none and conflict-aware.
    """
    plans = []
    for path in sorted(replacements):
        spec = replacements[path]
        create = bool(spec.get("create"))
        current, expected = resolve_expected_revision(
            path, spec.get("expected_revision"), allow_missing=create
        )
        replacement = str(spec.get("text") or "")
        validator = (lambda value: _parse_or_raise(value)) if spec.get("validate_life") else None
        plans.append(
            text_plan(
                path,
                lambda _current, value=replacement: value,
                expected,
                create=create and expected == MISSING_HASH,
                default="",
                validate=validator,
            )
        )
    return apply_multi_target(
        plans, operation=operation, journal_dir=journal_dir, config=config
    )


def merge_tag_and_alias(
    life_path, old_tag, new_tag, config_path=None, life_revision=None,
    config_revision=None, id_key="id", journal_dir=None, config=None,
):
    """Merge a tag and update the optional alias configuration atomically."""
    life_current, life_expected = resolve_expected_revision(life_path, life_revision)
    changed = {"count": 0}

    def life_transform(text):
        items, diagnostics = parse_text(
            text, id_key=id_key, check_ids=False, check_references=False
        )
        _raise_parse_errors(diagnostics)
        changes = []
        for item in items:
            values = [str(value) for value in item.details.get("tag", [])]
            if str(old_tag) not in values:
                continue
            ids = item.details.get(id_key) or []
            if not ids:
                raise SemanticWriteError(
                    "Cannot merge tag on %r because it has no %s:."
                    % (item.title, id_key)
                )
            replacement = []
            for value in values:
                candidate = str(new_tag) if value == str(old_tag) else value
                if candidate not in replacement:
                    replacement.append(candidate)
            changes.append({"id": str(ids[0]), "set_details": {"tag": replacement}})
        changed["count"] = len(changes)
        return text if not changes else transform_items_text(text, changes, id_key=id_key)

    plans = [
        text_plan(
            life_path, life_transform, life_expected,
            validate=lambda replacement: _parse_or_raise(replacement),
        )
    ]
    if config_path:
        config_current, config_expected = resolve_expected_revision(
            config_path, config_revision, allow_missing=True
        )

        def config_transform(value):
            value = copy.deepcopy(value if isinstance(value, dict) else {})
            aliases = value.get("tag_aliases")
            if not isinstance(aliases, dict):
                aliases = {}
                value["tag_aliases"] = aliases
            aliases[str(old_tag)] = str(new_tag)
            return value

        plans.append(
            json_plan(
                config_path, config_transform, config_expected,
                create=config_expected == MISSING_HASH, default={},
            )
        )
    result = apply_multi_target(
        plans, operation="tag.merge", journal_dir=journal_dir, config=config
    )
    return result, changed["count"]

def merge_tag(path, old_tag, new_tag, expected_revision=None, id_key="id"):
    old_tag = str(old_tag)
    new_tag = str(new_tag)
    current, expected = resolve_expected_revision(path, expected_revision)
    changed = {"count": 0}

    def transform(text):
        items, diagnostics = parse_text(text, id_key=id_key, check_ids=False, check_references=False)
        _raise_parse_errors(diagnostics)
        changes = []
        for item in items:
            values = [str(value) for value in item.details.get("tag", [])]
            if old_tag not in values:
                continue
            item_id_values = item.details.get(id_key) or []
            if not item_id_values:
                raise SemanticWriteError(
                    "Cannot merge tag on %r because it has no %s:." % (item.title, id_key)
                )
            replaced = []
            for value in values:
                candidate = new_tag if value == old_tag else value
                if candidate not in replaced:
                    replaced.append(candidate)
            changes.append({"id": str(item_id_values[0]), "set_details": {"tag": replaced}})
        changed["count"] = len(changes)
        if not changes:
            return text
        return transform_items_text(text, changes, id_key=id_key)

    result = mutation.mutate_text(
        path,
        transform,
        expected_hash=expected,
        operation="tag.merge",
        create=False,
        validate=lambda replacement: _parse_or_raise(replacement),
    )
    return result, changed["count"]


def restore_text(path, replacement_text, expected_revision=None, operation="undo.restore"):
    _parse_or_raise(replacement_text)
    _current, expected = resolve_expected_revision(path, expected_revision)
    return mutation.write_text(
        path,
        replacement_text,
        expected_hash=expected,
        operation=operation,
        create=False,
    )


def mutate_config(path, transform, expected_revision=None, create=False, operation="config.semantic"):
    current, expected = resolve_expected_revision(path, expected_revision, allow_missing=create)
    return mutation.mutate_json(
        path,
        transform,
        expected_hash=expected,
        operation=operation,
        create=create and expected == MISSING_HASH,
        default={},
        sort_keys=True,
    )


def current_revision(path, allow_missing=True):
    return snapshot(path, allow_missing=allow_missing).content_hash


def _normalize_changes(changes):
    normalized = []
    seen = set()
    for raw in changes or []:
        if not isinstance(raw, dict):
            raise TypeError("Item changes must be mappings.")
        item_id = str(raw.get("id") or "").strip()
        if not item_id:
            raise SemanticWriteError("Every item change requires id.")
        if item_id in seen:
            raise SemanticWriteError("Duplicate item change for id:%s." % item_id)
        seen.add(item_id)
        normalized.append(
            {
                "id": item_id,
                "status": raw.get("status"),
                "set_details": raw.get("set_details") or {},
                "delete": bool(raw.get("delete")),
            }
        )
    if not normalized:
        raise SemanticWriteError("At least one item change is required.")
    return normalized


def _parse_or_raise(text):
    _items, diagnostics = parse_text(text, check_ids=False, check_references=False)
    _raise_parse_errors(diagnostics)
    return True


def _raise_parse_errors(diagnostics):
    errors = [diagnostic for diagnostic in diagnostics if diagnostic.severity == "error"]
    if errors:
        raise SemanticWriteError(errors[0].format())


def _preferred_newline(text):
    return "\r\n" if "\r\n" in text else "\n"


def _line_ending(line):
    if line.endswith("\r\n"):
        return "\r\n"
    if line.endswith("\r"):
        return "\r"
    return "\n"
