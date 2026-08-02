"""Version and sprint planning records for development tickets."""

from __future__ import unicode_literals

import copy
import re
from collections import OrderedDict, defaultdict

from . import mutation
from .model import Item
from .serializer import item_to_line
from .surface_runtime import normalize_revision
from .ticket_activity import _first
from .ticket_activity_mutation import apply_ticket_activity
from .timeutil import parse_iso_date

VERSION_MARKER = "version"
SPRINT_MARKER = "sprint"
VERSION_SCHEMA = "ticket-version-v1.schema.json"
SPRINT_SCHEMA = "ticket-sprint-v1.schema.json"
PLANNING_SCHEMA = "ticket-planning-v1.schema.json"
VERSION_STATES = ("open", "locked", "released", "closed")
SPRINT_STATES = ("planned", "active", "closed")


def _values(item, key):
    return [str(value) for value in (getattr(item, "details", {}).get(key) or [])]


def _marker(item, marker):
    return marker in _values(item, "record")


def is_ticket_version(item):
    return getattr(item, "kind", None) == "N" and _marker(item, VERSION_MARKER)


def is_ticket_sprint(item):
    return getattr(item, "kind", None) == "N" and _marker(item, SPRINT_MARKER)


def iter_versions(items, project=None):
    rows = [item for item in items if is_ticket_version(item)]
    if project not in (None, ""):
        rows = [item for item in rows if str(project) in _values(item, "project")]
    return rows


def iter_sprints(items, project=None):
    rows = [item for item in items if is_ticket_sprint(item)]
    if project not in (None, ""):
        rows = [item for item in rows if str(project) in _values(item, "project")]
    return rows


def _date(value, key, required=False):
    if value in (None, ""):
        if required:
            raise ValueError("%s is required." % key)
        return None
    parsed = parse_iso_date(str(value))
    if parsed is None:
        raise ValueError("%s must be YYYY-MM-DD." % key)
    return parsed.isoformat()


def _positive_number(value, key):
    if value in (None, ""):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValueError("%s must be numeric." % key)
    if number < 0:
        raise ValueError("%s must be zero or greater." % key)
    return str(int(number)) if number.is_integer() else str(number)


def _safe(value):
    return re.sub(r"[^A-Za-z0-9_.-]+", "-", str(value)).strip("-") or "plan"


def _next_id(items, prefix):
    highest = 0
    for item in items:
        identifier = str(_first(item, "id", ""))
        if identifier.startswith(prefix + "-"):
            suffix = identifier[len(prefix) + 1 :]
            if suffix.isdigit():
                highest = max(highest, int(suffix))
    return "%s-%d" % (prefix, highest + 1)


def build_version(
    title,
    project,
    identifier,
    state="open",
    due=None,
    release=None,
    description=None,
    parent=None,
):
    state = str(state or "open")
    if state not in VERSION_STATES:
        raise ValueError(
            "Version state must be one of: %s." % ", ".join(VERSION_STATES)
        )
    details = OrderedDict(
        (
            ("record", [VERSION_MARKER]),
            ("id", [str(identifier)]),
            ("project", [str(project)]),
            ("state", [state]),
        )
    )
    if due:
        details["due"] = [_date(due, "due")]
    if release:
        details["release"] = [_date(release, "release")]
    if description:
        details["body"] = [str(description)]
    if parent:
        details["parent_version"] = [str(parent)]
    return Item("[N]", "N", str(title), details)


def build_sprint(
    title,
    project,
    identifier,
    start,
    end,
    state="planned",
    goal=None,
    capacity=None,
    version=None,
):
    state = str(state or "planned")
    if state not in SPRINT_STATES:
        raise ValueError("Sprint state must be one of: %s." % ", ".join(SPRINT_STATES))
    start_value = _date(start, "start", required=True)
    end_value = _date(end, "end", required=True)
    if end_value < start_value:
        raise ValueError("Sprint end must not be before start.")
    details = OrderedDict(
        (
            ("record", [SPRINT_MARKER]),
            ("id", [str(identifier)]),
            ("project", [str(project)]),
            ("state", [state]),
            ("start", [start_value]),
            ("end", [end_value]),
        )
    )
    if goal:
        details["goal"] = [str(goal)]
    normalized_capacity = _positive_number(capacity, "capacity")
    if normalized_capacity is not None:
        details["capacity"] = [normalized_capacity]
    if version:
        details["version"] = [str(version)]
    return Item("[N]", "N", str(title), details)


def _diag(code, message, item=None):
    return OrderedDict(
        (
            ("severity", "error"),
            ("code", code),
            ("message", message),
            ("hint", "Repair the planning record or its ticket membership."),
            ("source", getattr(item, "source", None) if item is not None else None),
            ("line", getattr(item, "line", None) if item is not None else None),
        )
    )


def validate_version(item):
    rows = []
    for key in ("id", "project", "state"):
        if not _values(item, key):
            rows.append(_diag("TK040", "Version is missing %s." % key, item))
    state = str(_first(item, "state", ""))
    if state and state not in VERSION_STATES:
        rows.append(_diag("TK041", "Unknown version state %r." % state, item))
    for key in ("due", "release"):
        if _first(item, key):
            try:
                _date(_first(item, key), key)
            except ValueError as exc:
                rows.append(_diag("TK042", str(exc), item))
    return rows


def validate_sprint(item):
    rows = []
    for key in ("id", "project", "state", "start", "end"):
        if not _values(item, key):
            rows.append(_diag("TK043", "Sprint is missing %s." % key, item))
    state = str(_first(item, "state", ""))
    if state and state not in SPRINT_STATES:
        rows.append(_diag("TK044", "Unknown sprint state %r." % state, item))
    start = end = None
    try:
        start = _date(_first(item, "start"), "start", required=True)
        end = _date(_first(item, "end"), "end", required=True)
    except ValueError as exc:
        rows.append(_diag("TK045", str(exc), item))
    if start and end and end < start:
        rows.append(_diag("TK046", "Sprint end is before start.", item))
    try:
        _positive_number(_first(item, "capacity"), "capacity")
    except ValueError as exc:
        rows.append(_diag("TK047", str(exc), item))
    return rows


def validate_planning(items, key="id"):
    from .tickets import is_ticket, ticket_id_of

    rows = []
    versions = {}
    sprints = {}
    for item in iter_versions(items):
        rows.extend(validate_version(item))
        identifier = str(_first(item, "id", ""))
        if identifier in versions:
            rows.append(_diag("TK048", "Duplicate version id %r." % identifier, item))
        versions[identifier] = item
    for item in iter_sprints(items):
        rows.extend(validate_sprint(item))
        identifier = str(_first(item, "id", ""))
        if identifier in sprints:
            rows.append(_diag("TK049", "Duplicate sprint id %r." % identifier, item))
        sprints[identifier] = item
        version = str(_first(item, "version", ""))
        if version and version not in versions:
            rows.append(
                _diag("TK050", "Sprint references missing version %r." % version, item)
            )
    for item in items:
        if not is_ticket(item):
            continue
        ticket = str(ticket_id_of(item, key) or "")
        version = str(_first(item, "version", ""))
        sprint = str(_first(item, "sprint", ""))
        if version and version not in versions:
            rows.append(
                _diag(
                    "TK051",
                    "Ticket %s references missing version %r." % (ticket, version),
                    item,
                )
            )
        if sprint and sprint not in sprints:
            rows.append(
                _diag(
                    "TK052",
                    "Ticket %s references missing sprint %r." % (ticket, sprint),
                    item,
                )
            )
        if version and sprint and sprint in sprints:
            sprint_version = str(_first(sprints[sprint], "version", ""))
            if sprint_version and sprint_version != version:
                rows.append(
                    _diag(
                        "TK053",
                        "Ticket %s version conflicts with sprint %s version."
                        % (ticket, sprint),
                        item,
                    )
                )
    return rows


def version_view(item, tickets=None):
    members = []
    open_members = []
    for ticket in tickets or []:
        if str(_first(ticket, "version", "")) != str(_first(item, "id", "")):
            continue
        identifier = str(_first(ticket, "id", ""))
        members.append(identifier)
        if getattr(ticket, "status", None) in ("[ ]", "[/]", "[?]", "[>]"):
            open_members.append(identifier)
    state = str(_first(item, "state", ""))
    warnings = []
    if open_members and state in ("released", "closed"):
        warnings.append("%s_with_open_tickets" % state)
    return OrderedDict(
        (
            ("id", _first(item, "id")),
            ("title", item.title),
            ("project", _first(item, "project")),
            ("state", _first(item, "state")),
            ("due", _first(item, "due")),
            ("release", _first(item, "release")),
            ("description", _first(item, "body")),
            ("parent_version", _first(item, "parent_version")),
            ("ticket_ids", sorted(value for value in members if value)),
            ("open_ticket_ids", sorted(value for value in open_members if value)),
            ("ticket_count", len(members)),
            ("open_ticket_count", len(open_members)),
            ("warnings", warnings),
            ("source", getattr(item, "source", None)),
            ("line", getattr(item, "line", None)),
        )
    )


def sprint_view(item, tickets=None):
    members = []
    open_members = []
    points = 0.0
    for ticket in tickets or []:
        if str(_first(ticket, "sprint", "")) != str(_first(item, "id", "")):
            continue
        identifier = str(_first(ticket, "id", ""))
        members.append(identifier)
        if getattr(ticket, "status", None) in ("[ ]", "[/]", "[?]", "[>]"):
            open_members.append(identifier)
        try:
            points += float(_first(ticket, "story_points", 0) or 0)
        except (TypeError, ValueError):
            pass
    capacity = _first(item, "capacity")
    capacity_value = float(capacity) if capacity not in (None, "") else None
    warnings = []
    if capacity_value is not None and points > capacity_value:
        warnings.append("story_points_exceed_capacity")
    if len(open_members) > 0 and str(_first(item, "state", "")) == "closed":
        warnings.append("closed_with_open_tickets")
    return OrderedDict(
        (
            ("id", _first(item, "id")),
            ("title", item.title),
            ("project", _first(item, "project")),
            ("state", _first(item, "state")),
            ("start", _first(item, "start")),
            ("end", _first(item, "end")),
            ("goal", _first(item, "goal")),
            ("capacity", capacity),
            ("version", _first(item, "version")),
            ("ticket_ids", sorted(value for value in members if value)),
            ("open_ticket_ids", sorted(value for value in open_members if value)),
            ("ticket_count", len(members)),
            ("open_ticket_count", len(open_members)),
            ("story_points", points),
            ("warnings", warnings),
            ("source", getattr(item, "source", None)),
            ("line", getattr(item, "line", None)),
        )
    )


def planning_report(items, project=None, config=None, key="id"):
    from .tickets import iter_tickets, ticket_summary

    tickets = iter_tickets(items)
    if project not in (None, ""):
        tickets = [item for item in tickets if str(project) in _values(item, "project")]
    versions = [version_view(item, tickets) for item in iter_versions(items, project)]
    sprints = [sprint_view(item, tickets) for item in iter_sprints(items, project)]
    backlog = [
        ticket_summary(item, config or {}, key=key)
        for item in tickets
        if getattr(item, "status", None) in ("[ ]", "[/]", "[?]", "[>]")
        and not _values(item, "sprint")
    ]
    versions.sort(
        key=lambda row: (row["release"] or row["due"] or "9999-12-31", row["id"] or "")
    )
    sprints.sort(key=lambda row: (row["start"] or "", row["id"] or ""))
    backlog.sort(key=lambda row: str(row["id"] or ""))
    return OrderedDict(
        (
            ("schema", PLANNING_SCHEMA),
            ("contract_version", "1"),
            ("project", project),
            ("versions", versions),
            ("sprints", sprints),
            ("backlog", backlog),
            ("diagnostics", validate_planning(items, key=key)),
            (
                "caveats",
                [
                    "story points are optional and are not converted to hours",
                    "capacity warnings are deterministic checks, not commitments",
                    "closed sprints retain ticket membership; carry-over must be explicit",
                ],
            ),
        )
    )
