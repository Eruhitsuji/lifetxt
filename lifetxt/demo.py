import datetime
import random

from .timezone_policy import local_now_naive
from collections import OrderedDict

from .model import Item, VALID_TYPES, normalize_type
from .serializer import item_to_line
from .timeutil import format_datetime, parse_date_or_datetime


DEFAULT_COUNT = 30
DEFAULT_TYPES = ("T", "E", "D", "R", "H", "N", "S", "M", "J")
DEFAULT_PEOPLE = ("self", "alice", "bob", "carol")
PROJECTS = ("demo", "research", "operations", "personal")
TAGS = ("demo", "focus", "team", "home", "review")
PRIORITIES = ("A", "B", "C")
STATUS_STATES = ("available", "busy", "away", "focus", "working", "meeting")
MOODS = ("good", "neutral", "tired", "focused")


def parse_demo_base_datetime(value=None, now=None):
    if value:
        text = str(value).strip()
        parsed_exact = _parse_demo_datetime_preserving_timezone(text)
        if parsed_exact is not None:
            return parsed_exact.replace(microsecond=0)
        parsed = parse_date_or_datetime(value)
        if parsed is None:
            raise ValueError(
                "--date must be YYYY-MM-DD or YYYY-MM-DDTHH:MM with optional seconds, fractional seconds, and timezone."
            )
        return parsed.replace(microsecond=0)
    if now is None:
        now = local_now_naive()
    return now.replace(second=0, microsecond=0)


def parse_demo_types(values):
    if not values:
        return DEFAULT_TYPES
    result = []
    for raw in values:
        for part in str(raw).split(","):
            text = part.strip()
            if not text:
                continue
            kind = normalize_type(text)
            if kind not in VALID_TYPES:
                raise ValueError(
                    "Unknown demo type %r. Use one of: %s."
                    % (text, ", ".join(VALID_TYPES))
                )
            if kind not in result:
                result.append(kind)
    if not result:
        raise ValueError("--types did not contain any item types.")
    return tuple(result)


def demo_items(
    count=DEFAULT_COUNT,
    base_datetime=None,
    types=None,
    seed=1,
    project=None,
    people=None,
    start_index=1,
):
    count = int(count)
    if count < 0:
        raise ValueError("--count must be zero or greater.")
    start_index = int(start_index)
    if start_index < 1:
        raise ValueError("--start-index must be 1 or greater.")
    if base_datetime is None:
        base_datetime = parse_demo_base_datetime()
    selected_types = tuple(types or DEFAULT_TYPES)
    rng = random.Random(seed)
    people = tuple(people or DEFAULT_PEOPLE)
    if not people:
        people = DEFAULT_PEOPLE
    project = project or "demo"

    items = []
    for index in range(count):
        kind = selected_types[index % len(selected_types)]
        item_no = start_index + index
        offset = rng.randint(-2, 6)
        items.append(
            _make_item(kind, item_no, base_datetime, offset, project, people, rng)
        )
    return items


def demo_text(
    count=DEFAULT_COUNT,
    base_datetime=None,
    types=None,
    seed=1,
    project=None,
    people=None,
    start_index=1,
):
    lines = [
        item_to_line(item)
        for item in demo_items(
            count, base_datetime, types, seed, project, people, start_index
        )
    ]
    return ("\n".join(lines) + "\n") if lines else ""


def _make_item(kind, number, base, offset_days, default_project, people, rng):
    if kind == "T":
        return _task(number, base, offset_days, default_project, people, rng)
    if kind == "E":
        return _event(number, base, offset_days, default_project, people, rng)
    if kind == "D":
        return _deadline(number, base, offset_days, default_project, people, rng)
    if kind == "R":
        return _reminder(number, base, offset_days, default_project, rng)
    if kind == "H":
        return _habit(number, base, default_project, rng)
    if kind == "N":
        return _note(number, default_project, rng)
    if kind == "S":
        return _status(number, base, offset_days, people, rng)
    if kind == "M":
        return _message(number, base, offset_days, default_project, people, rng)
    if kind == "J":
        return _journal(number, base, offset_days, default_project, rng)
    raise ValueError("Unsupported demo type: %s" % kind)


def _task(number, base, offset_days, default_project, people, rng):
    status = _pick(("[ ]", "[/]", "[>]", "[?]", "[x]"), number)
    details = _details(
        ("id", _id("task", number)),
        ("do", _date(base, offset_days)),
        ("due", _date(base, offset_days + 2)),
        ("project", _project(default_project, number)),
        ("priority", _pick(PRIORITIES, number)),
        ("assignee", _pick(people, number)),
        ("tag", _pick(TAGS, number)),
    )
    if status == "[x]":
        details["done"] = [_date(base, -1)]
    return Item(status, "T", "Demo_Task_%03d" % number, details)


def _event(number, base, offset_days, default_project, people, rng):
    start = _at(base, offset_days, 9 + (number % 8), 0)
    end = start + datetime.timedelta(minutes=45 + (number % 3) * 15)
    details = _details(
        ("id", _id("event", number)),
        ("from", _format_datetime(start)),
        ("to", _format_datetime(end)),
        ("loc", _pick(("Office", "Lab", "Online", "Room_A"), number)),
        ("attendee", _pick(people, number)),
        ("project", _project(default_project, number)),
    )
    return Item("[ ]", "E", "Demo_Event_%03d" % number, details)


def _deadline(number, base, offset_days, default_project, people, rng):
    status = "[x]" if number % 5 == 0 else "[ ]"
    details = _details(
        ("id", _id("deadline", number)),
        ("due", _date(base, offset_days + 4)),
        ("priority", _pick(PRIORITIES, number + 1)),
        ("owner", _pick(people, number + 1)),
        ("project", _project(default_project, number)),
    )
    if status == "[x]":
        details["done"] = [_date(base, -2)]
    return Item(status, "D", "Demo_Deadline_%03d" % number, details)


def _reminder(number, base, offset_days, default_project, rng):
    point = _at(base, offset_days, 8 + (number % 10), 30)
    details = _details(
        ("id", _id("reminder", number)),
        ("at", _format_datetime(point)),
        ("project", _project(default_project, number)),
        ("context", _pick(("home", "office", "online"), number)),
        ("note", "Check_demo_context"),
    )
    return Item("[ ]", "R", "Demo_Reminder_%03d" % number, details)


def _habit(number, base, default_project, rng):
    details = _details(
        ("id", _id("habit", number)),
        ("repeat", _pick(("daily", "weekly", "weekdays"), number)),
        ("at", "%02d:00" % (6 + (number % 12))),
        ("project", _project(default_project, number)),
        ("tag", _pick(("health", "learning", "review"), number)),
    )
    return Item("[ ]", "H", "Demo_Habit_%03d" % number, details)


def _note(number, default_project, rng):
    details = _details(
        ("id", _id("note", number)),
        ("project", _project(default_project, number)),
        ("tag", _pick(TAGS, number)),
        ("note", "Reusable_demo_note"),
        ("body", "This is a generated demo note for CLI and Web UI checks."),
    )
    return Item("[N]", "N", "Demo_Note_%03d" % number, details)


def _status(number, base, offset_days, people, rng):
    started = _at(base, min(offset_days, 0), 9 + (number % 7), 15)
    status = "[x]" if number % 4 == 0 else "[/]"
    details = _details(
        ("id", _id("status", number)),
        ("from", _format_datetime(started)),
        ("state", _pick(STATUS_STATES, number)),
        ("person", _pick(people, number)),
        ("service", _pick(("lifetxt", "teams", "discord", "slack"), number)),
        ("visibility", _pick(("team", "private", "public"), number)),
    )
    if status == "[x]":
        details["to"] = [_format_datetime(started + datetime.timedelta(hours=2))]
    return Item(status, "S", "Demo_Status_%03d" % number, details)


def _message(number, base, offset_days, default_project, people, rng):
    sender = _pick(people, number)
    recipient = _pick(people, number + 1)
    if recipient == sender:
        recipient = "self"
    notify_at = _at(base, offset_days, 10 + (number % 8), 45)
    details = _details(
        ("id", _id("message", number)),
        ("sender", sender),
        ("recipient", recipient),
        ("notify_at", _format_datetime(notify_at)),
        ("project", _project(default_project, number)),
        ("tag", _pick(("notice", "review", "followup"), number)),
        ("body", "Please review this generated demo message."),
    )
    return Item("[ ]", "M", "Demo_Message_%03d" % number, details)


def _journal(number, base, offset_days, default_project, rng):
    details = _details(
        ("id", _id("journal", number)),
        ("on", _date(base, offset_days)),
        ("mood", _pick(MOODS, number)),
        ("project", _project(default_project, number)),
        ("tag", "journal"),
        (
            "body",
            "Generated journal entry.\nReviewed tasks, events, and status updates.",
        ),
    )
    return Item("[N]", "J", "Demo_Journal_%03d" % number, details)


def _details(*pairs):
    data = OrderedDict()
    for key, value in pairs:
        if value is None:
            continue
        data[key] = [str(value)]
    return data


def _pick(values, number):
    return values[(number - 1) % len(values)]


def _project(default_project, number):
    if default_project:
        return default_project
    return _pick(PROJECTS, number)


def _id(prefix, number):
    return "demo_%s_%03d" % (prefix, number)


def _date(base, offset_days):
    return (base.date() + datetime.timedelta(days=offset_days)).isoformat()


def _format_datetime(value):
    if value.tzinfo is None:
        return format_datetime(value)
    if value.microsecond:
        return value.isoformat(timespec="microseconds")
    if value.second:
        return value.isoformat(timespec="seconds")
    return value.isoformat(timespec="minutes")


def _parse_demo_datetime_preserving_timezone(text):
    normalized = _normalize_demo_timezone(text)
    formats = (
        "%Y-%m-%d",
        "%Y-%m-%dT%H:%M",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%dT%H:%M%z",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S.%f%z",
    )
    for fmt in formats:
        try:
            parsed = datetime.datetime.strptime(normalized, fmt)
        except ValueError:
            continue
        return parsed
    return None


def _normalize_demo_timezone(text):
    if text.endswith("Z"):
        return text[:-1] + "+0000"
    if len(text) >= 6 and text[-6] in ("+", "-") and text[-3] == ":":
        return text[:-3] + text[-2:]
    return text


def _at(base, offset_days, hour, minute):
    date = base.date() + datetime.timedelta(days=offset_days)
    return datetime.datetime.combine(
        date, datetime.time(hour % 24, minute, tzinfo=base.tzinfo)
    )
