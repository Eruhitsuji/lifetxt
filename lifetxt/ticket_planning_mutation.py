"""Exact-revision mutations for version, sprint, and ticket planning."""
from __future__ import unicode_literals

import copy
from collections import OrderedDict

from . import mutation
from .serializer import item_to_line
from .surface_runtime import normalize_revision
from .ticket_activity import _first
from .ticket_activity_mutation import apply_ticket_activity
from .ticket_planning import (
    VERSION_MARKER, SPRINT_MARKER, VERSION_STATES, SPRINT_STATES,
    iter_versions, iter_sprints, build_version, build_sprint,
    validate_planning, _next_id, _marker,
)

def _parse(text, key):
    from .parser import parse_text

    items, diagnostics = parse_text(text, id_key=key, check_ids=False, check_references=False)
    errors = [d.to_dict() for d in diagnostics if getattr(d, "severity", None) == "error"]
    if errors:
        raise ValueError(errors)
    return items


def _append(text, item):
    newline = "\r\n" if "\r\n" in text else "\n"
    prefix = text
    if prefix and not prefix.endswith(("\n", "\r")):
        prefix += newline
    return prefix + item_to_line(item).replace("\n", newline) + newline


def _find_record(items, identifier, marker):
    matches = [
        item for item in items
        if _marker(item, marker) and str(_first(item, "id", "")) == str(identifier)
    ]
    if not matches:
        raise ValueError("%s %r not found." % (marker, identifier))
    if len(matches) > 1:
        raise ValueError("Multiple %s records found with id:%s." % (marker, identifier))
    return matches[0]


def _replace_record(text, identifier, marker, updater, key):
    from .webapp import split_line_ending, _with_line_ending

    items = _parse(text, key)
    item = _find_record(items, identifier, marker)
    updated = copy.copy(item)
    updated.details = OrderedDict((k, list(v)) for k, v in item.details.items())
    updater(updated)
    line = item_to_line(updated)
    raw_lines = text.splitlines(True)
    start = item.line - 1
    end_line = getattr(item, "end_line", item.line) or item.line
    _body, ending = split_line_ending(raw_lines[end_line - 1])
    raw_lines[start:end_line] = _with_line_ending(line, ending).splitlines(True)
    return "".join(raw_lines), updated


def _apply_text(path, expected_revision, transform, operation, dry_run=False):
    expected = normalize_revision(expected_revision, supplied=expected_revision is not None)
    if expected is None:
        raise ValueError("Planning writes require an exact --revision.")
    snapshot = mutation.read_text_snapshot(path, allow_missing=False)
    if snapshot.content_hash != expected:
        raise mutation.MutationConflict(path, expected, snapshot.content_hash, operation=operation)
    holder = {}
    replacement = transform(snapshot.text, holder)
    after_hash = mutation.hash_text(replacement, encoding=snapshot.encoding, bom=snapshot.bom)
    if not dry_run:
        result = mutation.mutate_text(path, lambda current: transform(current, holder), expected_hash=expected, operation=operation)
        after_hash = result.after_hash
    return OrderedDict(
        (
            ("contract_version", "1"),
            ("operation", operation),
            ("dry_run", bool(dry_run)),
            ("revision_before", expected),
            ("revision_after", after_hash),
            ("record", holder.get("record").to_dict() if holder.get("record") else None),
        )
    )


def create_version(path, title, project, expected_revision, identifier=None, state="open", due=None, release=None, description=None, parent=None, key="id", dry_run=False):
    def transform(text, holder):
        items = _parse(text, key)
        value = identifier or _next_id(iter_versions(items), "VER")
        if any(str(_first(item, "id", "")) == value for item in iter_versions(items)):
            raise ValueError("Version id %r already exists." % value)
        if parent:
            parent_item = next(
                (item for item in iter_versions(items) if str(_first(item, "id", "")) == str(parent)),
                None,
            )
            if parent_item is None:
                raise ValueError("Parent version %r not found." % parent)
            if str(_first(parent_item, "project", "")) != str(project):
                raise ValueError("Parent version %r belongs to another project." % parent)
        record = build_version(title, project, value, state=state, due=due, release=release, description=description, parent=parent)
        holder["record"] = record
        replacement = _append(text, record)
        errors = validate_planning(_parse(replacement, key), key=key)
        if errors:
            raise ValueError(errors)
        return replacement
    return _apply_text(path, expected_revision, transform, "version.new", dry_run=dry_run)


def create_sprint(path, title, project, start, end, expected_revision, identifier=None, state="planned", goal=None, capacity=None, version=None, key="id", dry_run=False):
    def transform(text, holder):
        items = _parse(text, key)
        value = identifier or _next_id(iter_sprints(items), "SPR")
        if any(str(_first(item, "id", "")) == value for item in iter_sprints(items)):
            raise ValueError("Sprint id %r already exists." % value)
        version_item = None
        if version:
            version_item = next(
                (item for item in iter_versions(items) if str(_first(item, "id", "")) == str(version)),
                None,
            )
            if version_item is None:
                raise ValueError("Version %r not found." % version)
            if str(_first(version_item, "project", "")) != str(project):
                raise ValueError("Version %r belongs to another project." % version)
        record = build_sprint(title, project, value, start, end, state=state, goal=goal, capacity=capacity, version=version)
        holder["record"] = record
        replacement = _append(text, record)
        errors = validate_planning(_parse(replacement, key), key=key)
        if errors:
            raise ValueError(errors)
        return replacement
    return _apply_text(path, expected_revision, transform, "sprint.new", dry_run=dry_run)


def update_planning_state(path, identifier, marker, state, expected_revision, key="id", force=False, dry_run=False):
    allowed = VERSION_STATES if marker == VERSION_MARKER else SPRINT_STATES
    if state not in allowed:
        raise ValueError("State must be one of: %s." % ", ".join(allowed))
    def transform(text, holder):
        items = _parse(text, key)
        record = _find_record(items, identifier, marker)
        current_state = str(_first(record, "state", ""))
        if current_state == state:
            raise ValueError("%s %s is already in state %s." % (marker, identifier, state))
        transitions = (
            {
                "open": ("locked", "released", "closed"),
                "locked": ("open", "released", "closed"),
                "released": ("open", "closed"),
                "closed": ("open",),
            }
            if marker == VERSION_MARKER
            else {
                "planned": ("active", "closed"),
                "active": ("planned", "closed"),
                "closed": ("planned",),
            }
        )
        if current_state in transitions and state not in transitions[current_state]:
            raise ValueError(
                "%s state transition %s -> %s is not allowed."
                % (marker, current_state, state)
            )
        if marker == SPRINT_MARKER and state == "closed" and not force:
            open_ids = [
                str(_first(item, "id", ""))
                for item in items
                if str(_first(item, "sprint", "")) == str(identifier)
                and getattr(item, "status", None) in ("[ ]", "[/]", "[?]", "[>]")
            ]
            if open_ids:
                raise ValueError(
                    "Sprint %s has unresolved tickets: %s. Use --force only after reviewing carry-over."
                    % (identifier, ", ".join(open_ids))
                )
        if marker == VERSION_MARKER and state in ("released", "closed") and not force:
            open_ids = [
                str(_first(item, "id", ""))
                for item in items
                if str(_first(item, "version", "")) == str(identifier)
                and getattr(item, "status", None) in ("[ ]", "[/]", "[?]", "[>]")
            ]
            if open_ids:
                raise ValueError(
                    "Version %s has unresolved tickets: %s. Use --force only after reviewing release scope."
                    % (identifier, ", ".join(open_ids))
                )
        replacement, updated = _replace_record(
            text, identifier, marker, lambda item: item.details.__setitem__("state", [state]), key
        )
        holder["record"] = updated
        errors = validate_planning(_parse(replacement, key), key=key)
        if errors:
            raise ValueError(errors)
        return replacement
    return _apply_text(path, expected_revision, transform, "%s.%s" % (marker, state), dry_run=dry_run)


def assign_planning(path, ticket_id, expected_revision, actor, version=None, sprint=None, clear_version=False, clear_sprint=False, config=None, key="id", at=None, comment=None, transaction_id=None, dry_run=False):
    snapshot = mutation.read_text_snapshot(path, allow_missing=False)
    items = _parse(snapshot.text, key)
    from .ticket_activity_mutation import _find_ticket

    ticket = _find_ticket(items, ticket_id, key)
    ticket_project = str(_first(ticket, "project", ""))
    updates = OrderedDict()
    event = "field_change"
    extra = {}
    if clear_version:
        updates["version"] = None
    elif version is not None:
        version_item = next(
            (item for item in iter_versions(items) if str(_first(item, "id", "")) == str(version)),
            None,
        )
        if version_item is None:
            raise ValueError("Version %r not found." % version)
        if ticket_project and str(_first(version_item, "project", "")) != ticket_project:
            raise ValueError("Version %r belongs to another project." % version)
        updates["version"] = str(version)
        event = "version_assigned"
        extra["version"] = str(version)
    if clear_sprint:
        updates["sprint"] = None
    elif sprint is not None:
        sprint_item = next((item for item in iter_sprints(items) if str(_first(item, "id", "")) == str(sprint)), None)
        if sprint_item is None:
            raise ValueError("Sprint %r not found." % sprint)
        if ticket_project and str(_first(sprint_item, "project", "")) != ticket_project:
            raise ValueError("Sprint %r belongs to another project." % sprint)
        updates["sprint"] = str(sprint)
        event = "sprint_assigned"
        extra["sprint"] = str(sprint)
        sprint_version = _first(sprint_item, "version")
        if sprint_version and not clear_version and version is None:
            updates["version"] = str(sprint_version)
            extra["version"] = str(sprint_version)
    if not updates:
        raise ValueError("Specify --version/--sprint or a clear option.")
    return apply_ticket_activity(
        path, ticket_id, event, actor, expected_revision,
        config=config, key=key, detail_updates=updates, comment=comment, at=at,
        event_extra=extra, transaction_id=transaction_id, dry_run=dry_run,
        operation="ticket.plan",
    )
