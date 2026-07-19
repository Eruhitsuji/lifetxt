"""The shared definition of an actionable next step.

`lifetxt next`, the TUI `/next` view, and the MCP `get_next_actions` tool must
agree on what counts as actionable, otherwise the same file yields three
different answers. The predicate lives here so there is exactly one definition.
"""

from .links import dependency_blockers_by_item


#: Statuses that can still be worked on. `[?]` (someday/maybe) is deliberately
#: excluded: it is a parking lot, not a next step.
ACTIONABLE_STATUSES = ("[ ]", "[/]")

#: Tags that park an item even when its status looks open.
PARKED_TAGS = ("someday", "maybe", "waiting", "blocked")

#: Types that represent something a person does.
ACTIONABLE_KINDS = ("T", "D", "R", "H")

PRIORITY_ORDER = {
    "high": 0, "urgent": 0, "a": 0, "1": 0, "p1": 0,
    "med": 1, "medium": 1, "normal": 1, "b": 1, "2": 1, "p2": 1,
    "low": 2, "c": 2, "3": 2, "p3": 2,
}


def is_actionable(status, details=None, blocked=False, kind=None):
    """Core predicate, expressed on plain fields so any record shape can use it.

    A next action is open or in progress, not blocked by an unfinished
    dependency, and not parked behind a someday/waiting tag.
    """
    if status not in ACTIONABLE_STATUSES:
        return False
    if blocked:
        return False
    if kind is not None and kind not in ACTIONABLE_KINDS:
        return False
    details = details or {}
    if details.get("depends_on"):
        return False
    tags = [str(value).lstrip("#").lower() for value in details.get("tag") or []]
    for parked in PARKED_TAGS:
        if parked in tags:
            return False
    return True


def next_action_items(items, key="id", limit=None, project=None, assignee=None):
    """Actionable items, ordered by priority, then due date, then age.

    Blocking is resolved against the whole item set, so a dependency in another
    file still parks the item.
    """
    blockers = dependency_blockers_by_item(items, key=key)
    actionable = []
    for item in items:
        if not is_actionable(
            item.status,
            item.details,
            blocked=bool(blockers.get(id(item))),
            kind=item.kind,
        ):
            continue
        if project and project not in [str(v) for v in item.details.get("project") or []]:
            continue
        if assignee and assignee not in [str(v) for v in item.details.get("assignee") or []]:
            continue
        actionable.append(item)

    actionable.sort(key=_sort_key)
    if limit:
        actionable = actionable[: max(0, int(limit))]
    return actionable


def _sort_key(item):
    priority = _first(item, "priority").lower()
    due = _first(item, "due") or _first(item, "do")
    return (
        PRIORITY_ORDER.get(priority, 5),
        due == "",
        due,
        item.line if item.line is not None else 0,
    )


def _first(item, key):
    values = item.details.get(key) or []
    return str(values[0]) if values else ""
