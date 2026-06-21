from collections import OrderedDict

from .model import Item, normalize_status, normalize_type
from .interactive import (
    PromptSession,
    detail_candidates,
    print_detail_summary,
    print_section,
    print_short_rule,
    status_candidates,
    type_candidates,
)
from .parser import parse_line
from .serializer import item_to_line
from .validator import validate_item


DETAIL_FLAGS = (
    "id",
    "parent",
    "created",
    "updated",
    "done",
    "due",
    "do",
    "from",
    "to",
    "state",
    "person",
    "owner",
    "assignee",
    "attendee",
    "sender",
    "recipient",
    "service",
    "channel",
    "visibility",
    "notify_at",
    "notify_from",
    "notify_to",
    "ack",
    "snooze_until",
    "on",
    "at",
    "repeat",
    "project",
    "context",
    "loc",
    "priority",
    "est",
    "tag",
    "note",
    "url",
    "reason",
    "moved_to",
)


def build_item_from_args(args):
    kind = normalize_type(args.kind)
    if kind is None:
        kind = "T"

    details = collect_details_from_args(args)

    status = normalize_status(args.status)
    if status is None:
        status = _default_status(kind, details)

    return Item(status, kind, args.title, details)


def collect_details_from_args(args):
    details = OrderedDict()
    _add_detail_entries(details, getattr(args, "detail", None) or [])
    for key in DETAIL_FLAGS:
        dest = "from_" if key == "from" else key
        values = getattr(args, dest, None)
        if not values:
            continue
        if not isinstance(values, list):
            values = [values]
        for value in values:
            if value is not None and value != "":
                details.setdefault(key, []).append(value)
    return details


def prompt_item(args):
    session = PromptSession(enable_completion=not getattr(args, "no_completion", False))

    print_section("Type")
    kind_default = normalize_type(args.kind) or "T"
    kind = normalize_type(
        session.read(
            "type",
            kind_default,
            candidates=type_candidates(),
            help_topic="type",
            allow_empty=False,
        )
    )
    if not kind:
        kind = kind_default

    print_section("Status")
    status_default = normalize_status(args.status)
    if status_default is None:
        status_default = _default_status(kind, None)
    status = (
        normalize_status(
            session.read(
                "status",
                status_default,
                candidates=status_candidates(),
                help_topic="status",
                allow_empty=False,
            )
        )
        or status_default
    )

    print_section("Title")
    title_default = args.title or ""
    title = session.read("title", title_default, help_topic="title", allow_empty=False)
    while not title:
        title = session.read("title", title_default, help_topic="title", allow_empty=False)

    details = OrderedDict()
    _add_detail_entries(details, getattr(args, "detail", None) or [])

    print_section("Details")
    print_detail_summary(kind)
    candidates = detail_candidates(kind)
    while True:
        raw = session.read(
            "detail",
            "",
            candidates=candidates,
            help_topic="detail:%s" % kind,
            allow_empty=True,
        )
        if not raw:
            break
        _add_detail_entries(details, [raw])
        print_short_rule(after_prompt=True)

    return Item(status, kind, title, details)


def _default_status(kind, details):
    if kind == "N":
        return "[N]"
    if kind == "S":
        if details and "to" in details:
            return "[x]"
        return "[/]"
    return "[ ]"


def item_to_assisted_line(item):
    return item_to_line(item)


def update_text(text, args):
    raw_lines = text.splitlines(True)
    line_items, diagnostics = _parse_line_items(raw_lines)
    if _has_error(diagnostics):
        return text, None, diagnostics

    line_no, item = _select_update_item(line_items, args)
    updated = apply_updates(item, args)
    updated_line = item_to_line(updated)

    parsed, parsed_diagnostics = parse_line(updated_line, line_no)
    diagnostics.extend(parsed_diagnostics)
    if parsed is None:
        raise ValueError("Updated line did not produce an item.")
    if not args.no_check:
        diagnostics.extend(validate_item(parsed))
    if _has_error(diagnostics):
        return text, None, diagnostics

    index = line_no - 1
    _body, original_ending = _split_line_ending(raw_lines[index])
    raw_lines[index] = updated_line + original_ending
    return "".join(raw_lines), updated_line, diagnostics


def apply_updates(item, args):
    updated = Item(item.status, item.kind, item.title, item.details, item.line)

    if args.status is not None:
        updated.status = normalize_status(args.status)
    if args.kind is not None:
        updated.kind = normalize_type(args.kind)
    if args.title is not None:
        updated.title = args.title

    for key in getattr(args, "remove_detail", None) or []:
        if key in updated.details:
            del updated.details[key]

    replacement_details = collect_details_from_args(args)
    for key, values in replacement_details.items():
        updated.details[key] = list(values)

    additions = OrderedDict()
    _add_detail_entries(additions, getattr(args, "add_detail", None) or [])
    for key, values in additions.items():
        updated.details.setdefault(key, []).extend(values)

    return updated


def has_update_fields(args):
    if args.status is not None or args.kind is not None or args.title is not None:
        return True
    if getattr(args, "detail", None):
        return True
    if getattr(args, "add_detail", None):
        return True
    if getattr(args, "remove_detail", None):
        return True
    for key in DETAIL_FLAGS:
        dest = "from_" if key == "from" else key
        if getattr(args, dest, None):
            return True
    return False


def _parse_line_items(raw_lines):
    diagnostics = []
    line_items = []
    for line_no, raw_line in enumerate(raw_lines, 1):
        body, _ending = _split_line_ending(raw_line)
        item, line_diagnostics = parse_line(body, line_no)
        diagnostics.extend(line_diagnostics)
        if item is not None:
            line_items.append((line_no, item))
    return line_items, diagnostics


def _select_update_item(line_items, args):
    if args.line is not None and args.match_id is not None:
        raise ValueError("Use either --line or --match-id, not both.")
    if args.line is None and args.match_id is None:
        raise ValueError("Update requires --line N or --match-id ID.")

    if args.line is not None:
        for line_no, item in line_items:
            if line_no == args.line:
                return line_no, item
        raise ValueError("Line %s is not a life.txt item." % args.line)

    matches = []
    for line_no, item in line_items:
        if args.match_id in item.details.get("id", []):
            matches.append((line_no, item))
    if not matches:
        raise ValueError("No item found with id:%s." % args.match_id)
    if len(matches) > 1:
        raise ValueError("Multiple items found with id:%s." % args.match_id)
    return matches[0]


def _add_detail_entries(details, entries):
    for entry in entries:
        key, value = _split_detail_entry(entry)
        details.setdefault(key, []).append(value)


def _split_detail_entry(entry):
    if "=" in entry:
        key, value = entry.split("=", 1)
    elif ":" in entry:
        key, value = entry.split(":", 1)
    else:
        raise ValueError("Detail %r must be key=value or key:value." % entry)
    key = key.strip()
    value = value.strip()
    if not key:
        raise ValueError("Detail key must not be empty.")
    return key, value


def _split_line_ending(raw_line):
    if raw_line.endswith("\r\n"):
        return raw_line[:-2], "\r\n"
    if raw_line.endswith("\n"):
        return raw_line[:-1], "\n"
    if raw_line.endswith("\r"):
        return raw_line[:-1], "\r"
    return raw_line, ""


def _has_error(diagnostics):
    for diagnostic in diagnostics:
        if diagnostic.severity == "error":
            return True
    return False
