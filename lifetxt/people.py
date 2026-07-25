"""Person and group overview aggregation.

Collects everything about a person in one place — assigned work, authored and
received messages, meetings, presence, projects, waiting items, and group/team
memberships — by reusing the existing project, group, delivery, and status
logic rather than duplicating records. Read-only and deterministic given the
same items, config, and reference date.

Names resolve through the configured user aliases, so ``me`` and ``self`` (or
any declared alias) refer to the same person everywhere.
"""

from __future__ import unicode_literals

from collections import OrderedDict

from .config import config_team_members, config_user_aliases
from .timeutil import parse_date_or_datetime


OPEN_STATUSES = ("[ ]", "[/]", "[?]")
DONE_STATUS = "[x]"
CANCELLED_STATUS = "[-]"
WAITING_STATUS = "[?]"
WORK_KINDS = ("T", "D")
ASSIGNEE_KEYS = ("assignee", "owner")


def _values(item, key):
    return [str(v) for v in item.details.get(key, [])]


def _first(item, key, default=None):
    values = item.details.get(key)
    return values[0] if values else default


def _alias_index(config):
    """Return ``alias -> canonical`` and ``canonical -> alias set`` maps."""
    aliases = config_user_aliases(config)
    reverse = OrderedDict()
    for canonical, names in aliases.items():
        reverse[canonical] = canonical
        for alias in names:
            reverse[alias] = canonical
    return aliases, reverse


def resolve_person(config, name):
    _aliases, reverse = _alias_index(config)
    return reverse.get(str(name), str(name))


def _person_alias_set(config, canonical):
    aliases, _reverse = _alias_index(config)
    names = set(aliases.get(canonical, [canonical]))
    names.add(canonical)
    return names


def _matches(values, alias_set):
    return any(value in alias_set for value in values)


def _date_of(value):
    if not value:
        return None
    try:
        parsed = parse_date_or_datetime(value)
    except Exception:
        return None
    if parsed is None:
        return None
    return getattr(parsed, "date", lambda: parsed)()


def _ref(item):
    return OrderedDict(
        (
            ("title", item.title),
            ("kind", item.kind),
            ("status", item.status),
            ("project", _first(item, "project")),
            ("due", _first(item, "due")),
            ("source", item.source),
            ("line", item.line),
        )
    )


def memberships(config, canonical, alias_set):
    """Teams and groups that include this person."""
    from .groups import expand_group, group_directory

    teams = [name for name, members in config_team_members(config).items()
             if _matches(members, alias_set)]
    directory = group_directory(config)
    group_names = []
    for name in directory:
        members = expand_group(config, name)
        if _matches(members, alias_set):
            group_names.append(name)
    return OrderedDict((("teams", sorted(teams)), ("groups", sorted(group_names))))


def person_overview(items, config=None, name=None, today=None):
    """Aggregate one person's work, messages, meetings, presence, and projects."""
    config = config or {}
    canonical = resolve_person(config, name)
    alias_set = _person_alias_set(config, canonical)

    assigned = []
    waiting = []
    overdue = []
    sent = []
    received = []
    meetings = []
    for item in items:
        if item.kind in WORK_KINDS:
            assignee_values = []
            for key in ASSIGNEE_KEYS:
                assignee_values.extend(_values(item, key))
            if _matches(assignee_values, alias_set):
                if item.status in OPEN_STATUSES:
                    assigned.append(_ref(item))
                    if item.status == WAITING_STATUS:
                        waiting.append(_ref(item))
                    due = _date_of(_first(item, "due"))
                    if today is not None and due is not None and due < today:
                        overdue.append(_ref(item))
        elif item.kind == "M":
            if _matches(_values(item, "sender"), alias_set):
                sent.append(_ref(item))
            if _matches(_values(item, "recipient"), alias_set):
                received.append(_ref(item))
        elif item.kind == "E":
            if _matches(_values(item, "attendee"), alias_set):
                meetings.append(_ref(item))

    return OrderedDict(
        (
            ("person", canonical),
            ("aliases", sorted(a for a in alias_set if a != canonical)),
            ("presence", _presence(items, canonical)),
            ("assigned_open", assigned),
            ("waiting", waiting),
            ("overdue", overdue),
            ("messages_sent", sent),
            ("messages_received", received),
            ("meetings", meetings),
            ("projects", _person_projects(items, config, alias_set, today)),
            ("memberships", memberships(config, canonical, alias_set)),
            (
                "counts",
                OrderedDict(
                    (
                        ("assigned_open", len(assigned)),
                        ("waiting", len(waiting)),
                        ("overdue", len(overdue)),
                        ("messages_sent", len(sent)),
                        ("messages_received", len(received)),
                        ("meetings", len(meetings)),
                    )
                ),
            ),
        )
    )


def _presence(items, canonical):
    from .status_summary import latest_status_records

    for record in latest_status_records(items, active_only=False):
        if str(record.get("person")) == canonical:
            return OrderedDict(
                (
                    ("state", record.get("state")),
                    ("title", record.get("title")),
                    ("from", record.get("from")),
                )
            )
    return None


def _person_projects(items, config, alias_set, today):
    from .projects import collect_projects

    rows = []
    for proj in collect_projects(items, config, today).values():
        owner = proj["owner"]
        is_owner = owner is not None and owner in alias_set
        assigned_here = [t for t in proj["tasks"]
                         if t.get("assignee") and t["assignee"] in alias_set]
        if is_owner or assigned_here:
            rows.append(
                OrderedDict(
                    (
                        ("name", proj["name"]),
                        ("owner", is_owner),
                        ("assigned_tasks", len(assigned_here)),
                    )
                )
            )
    return rows


def people_list(items, config=None, today=None):
    """Every person seen in assignee/owner/sender/recipient/presence, with counts."""
    config = config or {}
    _aliases, reverse = _alias_index(config)
    seen = OrderedDict()

    def bucket(name):
        canonical = reverse.get(name, name)
        return seen.setdefault(
            canonical,
            OrderedDict((("person", canonical), ("assigned_open", 0), ("messages", 0), ("meetings", 0))),
        )

    for item in items:
        if item.kind in WORK_KINDS and item.status in OPEN_STATUSES:
            for key in ASSIGNEE_KEYS:
                for value in _values(item, key):
                    bucket(value)["assigned_open"] += 1
        elif item.kind == "M":
            for value in _values(item, "sender") + _values(item, "recipient"):
                bucket(value)["messages"] += 1
        elif item.kind == "E":
            for value in _values(item, "attendee"):
                bucket(value)["meetings"] += 1
        elif item.kind == "S":
            person = _first(item, "person")
            if person:
                bucket(person)
    rows = list(seen.values())
    rows.sort(key=lambda r: r["person"])
    return rows


def group_overview(items, config=None, name=None, today=None):
    """A group's members plus each member's open work and message counts."""
    from .groups import expand_group, group_directory

    config = config or {}
    directory = group_directory(config)
    if name not in directory and name not in _alias_names(directory):
        raise ValueError("Unknown group %r. Known: %s"
                         % (name, ", ".join(directory.keys()) or "(none)"))
    diagnostics = []
    members = expand_group(config, name, diagnostics=diagnostics)
    member_rows = []
    for member in members:
        overview = person_overview(items, config, member, today)
        member_rows.append(
            OrderedDict(
                (
                    ("person", overview["person"]),
                    ("assigned_open", overview["counts"]["assigned_open"]),
                    ("overdue", overview["counts"]["overdue"]),
                    ("messages_received", overview["counts"]["messages_received"]),
                )
            )
        )
    return OrderedDict(
        (
            ("group", name),
            ("member_count", len(members)),
            ("members", member_rows),
            ("total_assigned_open", sum(r["assigned_open"] for r in member_rows)),
            ("total_overdue", sum(r["overdue"] for r in member_rows)),
            ("diagnostics", diagnostics),
        )
    )


def _alias_names(directory):
    names = set()
    for group in directory.values():
        for alias in group.get("aliases", []):
            names.add(alias)
    return names
