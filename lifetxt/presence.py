"""Presence status transitions.

Recording a status is a two-part edit: the person's currently open ``S`` record
has to be closed (``to:`` plus ``[x]``) and a new one opened (``[/]`` plus
``from:``). Doing that by hand is the tedious part, and forgetting the close
leaves two records that both look current, which silently corrupts every
"who is available" view.

This module owns that transition so the CLI, TUI, Web API, and MCP all produce
the same edit.
"""

import datetime
from collections import OrderedDict, namedtuple

from .model import Item
from .parser import parse_text
from .serializer import item_to_line


STATUS_ACTIVE = "[/]"
STATUS_CLOSED = "[x]"
DEFAULT_PERSON = "self"

# Not a closed set: `state:` is free-form in the format. These are the values
# used across the examples and docs, offered for completion and help output.
COMMON_STATES = (
    "available",
    "busy",
    "focus",
    "meeting",
    "away",
    "commuting",
    "working",
    "offline",
    "sleeping",
)


def format_timestamp(moment=None):
    """Status datetimes are minute precision, matching the format examples."""
    moment = moment or datetime.datetime.now()
    return moment.strftime("%Y-%m-%dT%H:%M")


def active_status_items(items, person=None):
    """Open ``S`` records: kind S with a ``from:`` and no ``to:``."""
    found = []
    for item in items:
        if item.kind != "S":
            continue
        if "to" in item.details:
            continue
        if not item.details.get("from"):
            continue
        owner = _first(item, "person", DEFAULT_PERSON)
        if person is not None and owner != person:
            continue
        found.append(item)
    return found


#: ``unchanged`` is the state name that was already open when a repeat
#: transition was skipped, and empty otherwise. Access fields by name; the
#: tuple has four of them, so positional unpacking into three will fail.
StatusTransition = namedtuple("StatusTransition", "text closed opened unchanged")


def status_transition(
    text,
    state=None,
    title=None,
    person=DEFAULT_PERSON,
    moment=None,
    details=None,
    id_key="id",
    close_only=False,
    item_id=None,
    force=False,
):
    """Close the open status for ``person`` and optionally open a new one.

    Returns a :class:`StatusTransition`. ``closed`` lists the records that were
    closed so callers can report exactly what changed.

    Closing every open record for the person, not just the newest, is
    deliberate: if a file already drifted into two open records, a transition
    should repair it rather than add a third.

    Switching to the state that is already open is a no-op unless ``force`` is
    set. Otherwise a stray repeat of `lifetxt s busy` would split one long busy
    block into a stub plus a new record, quietly losing the real start time.
    """
    person = str(person or DEFAULT_PERSON)
    stamp = format_timestamp(moment)

    if not close_only and not state:
        raise ValueError("A status transition needs a state, for example: busy.")

    items, diagnostics = parse_text(text, id_key=id_key)
    errors = [d for d in diagnostics if d.severity == "error"]
    if errors:
        raise ValueError(errors[0].format())

    open_items = active_status_items(items, person=person)
    if not close_only and not force and len(open_items) == 1:
        current = _first(open_items[0], "state", "")
        if current and current == str(state).strip():
            return StatusTransition(text, [], "", current)

    lines = text.splitlines(True)
    ending = _line_ending(lines)

    closed_lines = []
    for item in open_items:
        if _first(item, "from", "") > stamp:
            raise ValueError(
                "Open status %r starts at %s, which is after %s. Pass an explicit time."
                % (item.title, _first(item, "from", ""), stamp)
            )
        item.status = STATUS_CLOSED
        _set_to_after_from(item, stamp)
        rendered = item_to_line(item)
        start = item.line - 1
        end = getattr(item, "end_line", item.line) or item.line
        lines[start:end] = (rendered + ending).splitlines(True)
        closed_lines.append(rendered)

    opened_line = ""
    if not close_only:
        new_item = _build_status_item(state, title, person, stamp, details, id_key, item_id, items)
        opened_line = item_to_line(new_item)
        if lines and not lines[-1].endswith(("\n", "\r")):
            lines[-1] = lines[-1] + ending
        lines.append(opened_line + ending)

    return StatusTransition("".join(lines), closed_lines, opened_line, "")


def _build_status_item(state, title, person, stamp, details, id_key, item_id, existing_items):
    resolved_title = str(title or "").strip() or str(state).strip().title()
    ordered = OrderedDict()
    ordered["from"] = [stamp]
    ordered["state"] = [str(state).strip()]
    ordered["person"] = [person]
    for key, values in (details or {}).items():
        if key in ("from", "to", "state", "person"):
            continue
        ordered[key] = list(values) if isinstance(values, (list, tuple)) else [values]

    item = Item(STATUS_ACTIVE, "S", resolved_title, ordered, 0)
    if item_id:
        item.details[id_key] = [str(item_id)]
    else:
        from .ids import generate_item_id

        existing = set()
        for other in existing_items:
            for value in other.details.get(id_key, []):
                existing.add(value)
        item.details[id_key] = [generate_item_id(item, existing_ids=existing)]
    return item


def _set_to_after_from(item, stamp):
    """Write ``to:`` immediately after ``from:``, the way the spec examples read."""
    rebuilt = OrderedDict()
    for key, values in item.details.items():
        if key == "to":
            continue
        rebuilt[key] = values
        if key == "from":
            rebuilt["to"] = [stamp]
    if "to" not in rebuilt:
        rebuilt["to"] = [stamp]
    item.details = rebuilt


def _line_ending(lines):
    for line in reversed(lines):
        if line.endswith("\r\n"):
            return "\r\n"
        if line.endswith("\n"):
            return "\n"
    return "\n"


def _first(item, key, default=""):
    values = item.details.get(key) or []
    return str(values[0]) if values else default
