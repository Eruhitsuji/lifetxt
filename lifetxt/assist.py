from collections import OrderedDict

from .model import Item, normalize_status, normalize_type
from .serializer import item_to_line


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

    status = normalize_status(args.status)
    if status is None:
        status = "[N]" if kind == "N" else "[ ]"

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

    return Item(status, kind, args.title, details)


def prompt_item(args):
    kind_default = normalize_type(args.kind) or "T"
    kind = normalize_type(_prompt("type", kind_default))
    if not kind:
        kind = kind_default

    status_default = normalize_status(args.status)
    if status_default is None:
        status_default = "[N]" if kind == "N" else "[ ]"
    status = normalize_status(_prompt("status", status_default)) or status_default

    title_default = args.title or ""
    title = _prompt("title", title_default)
    while not title:
        title = _prompt("title", title_default)

    details = OrderedDict()
    _add_detail_entries(details, getattr(args, "detail", None) or [])

    print("Enter details as key:value or key=value. Leave empty to finish.")
    while True:
        raw = _prompt("detail", "")
        if not raw:
            break
        _add_detail_entries(details, [raw])

    return Item(status, kind, title, details)


def item_to_assisted_line(item):
    return item_to_line(item)


def _prompt(name, default):
    if default:
        value = input("%s [%s]: " % (name, default)).strip()
        return default if value == "" else value
    return input("%s: " % name).strip()


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
