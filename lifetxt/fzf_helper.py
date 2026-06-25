import os
import shutil
import subprocess
import sys
from collections import OrderedDict

from .agenda import filter_items, parse_optional_time_range
from .config import (
    config_tag_aliases,
    config_team_aliases,
    config_team_members,
    config_user_aliases,
)
from .ids import id_key_from_config
from .parser import parse_text
from .serializer import item_to_line


def cmd_fzf(args):
    tool = resolve_tool(args.tool)
    items = load_filtered_items(args)
    if not items:
        sys.stdout.write("No matching items.\n")
        return 0
    selected = select_items(tool, items, args)
    if getattr(args, "print_query", False):
        if selected:
            sys.stdout.write(selected[0] + "\n")
        return 0
    if not selected:
        return 0
    action = args.action or choose_action()
    records = [decode_selection(line) for line in selected if line.strip()]
    return run_action(action, records, args)


def resolve_tool(preferred=None):
    candidates = [preferred] if preferred else ["fzf", "peco"]
    for name in candidates:
        if not name:
            continue
        path = shutil.which(name)
        if path:
            return path
    raise ValueError("fzf or peco was not found in PATH. Install fzf or peco, or pass --tool.")


def load_filtered_items(args):
    items = []
    include_source = len(args.paths or []) != 1
    for path in args.paths:
        with open(path, "r", encoding="utf-8-sig") as handle:
            path_items, diagnostics = parse_text(handle.read(), id_key=_id_key(args))
        errors = [diagnostic for diagnostic in diagnostics if diagnostic.severity == "error"]
        if errors:
            raise ValueError(errors[0].format())
        for item in path_items:
            item.source = path
        items.extend(path_items)

    range_start, range_end = parse_optional_time_range(
        after_text=getattr(args, "after", None),
        before_text=getattr(args, "before", None),
    )
    config = getattr(args, "config_data", None) or {}
    return filter_items(
        items,
        open_only=args.open,
        statuses=args.status,
        kinds=args.kinds,
        projects=args.project,
        tags=args.tag,
        tag_all=args.tag_all,
        exclude_tags=args.exclude_tag,
        users=args.user,
        persons=args.person,
        owners=args.owner,
        assignees=args.assignee,
        attendees=args.attendee,
        senders=args.sender,
        recipients=args.recipient,
        teams=args.team,
        detail_filters=args.detail,
        text=args.text,
        range_start=range_start,
        range_end=range_end,
        user_aliases=config_user_aliases(config),
        team_members=config_team_members(config),
        team_aliases=config_team_aliases(config),
        tag_aliases=config_tag_aliases(config),
    )


def select_items(tool, items, args):
    lines = [encode_item(item, _id_key(args)) for item in items]
    command = [tool]
    base = os.path.basename(tool).lower()
    if base.startswith("fzf"):
        command.append("--multi")
        if args.preview:
            command.extend(["--preview", "echo {}"])
        if args.print_query:
            command.append("--print-query")
    process = subprocess.Popen(
        command,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
    )
    stdout, stderr = process.communicate("\n".join(lines) + "\n")
    if process.returncode not in (0, 1, 130):
        raise ValueError(stderr.strip() or "Selection tool failed.")
    selected = stdout.splitlines()
    if args.print_query and selected:
        return [selected[0]]
    return selected


def run_action(action, records, args):
    if action == "show":
        for record in records:
            sys.stdout.write(record["text"] + "\n")
        return 0
    if action == "done":
        for record in records:
            require_id(record)
            update_item(record["source"], record["id"], _id_key(args), status="[x]")
        sys.stdout.write("Marked %d item(s) done.\n" % len(records))
        return 0
    if action == "delete":
        sys.stderr.write("Delete %d item(s)? [y/N] " % len(records))
        answer = sys.stdin.readline().strip().lower()
        if answer not in ("y", "yes"):
            sys.stdout.write("Canceled.\n")
            return 0
        for record in records:
            require_id(record)
            delete_item(record["source"], record["id"], _id_key(args))
        sys.stdout.write("Deleted %d item(s).\n" % len(records))
        return 0
    if action == "edit":
        if not records:
            return 0
        return open_editor(records[0])
    raise ValueError("Unsupported fzf action: %s" % action)


def choose_action():
    sys.stderr.write("Action [done/edit/delete/show]: ")
    action = sys.stdin.readline().strip().lower()
    return action or "show"


def encode_item(item, key):
    item_id = item.details.get(key, [""])[0] if item.details.get(key) else ""
    source = getattr(item, "source", "") or ""
    line = str(item.line or "")
    title = "%s %s %s" % (item.status, item.kind, item.title)
    body = item.details.get("body", [""])[0] if item.details.get("body") else ""
    body = body.replace("\n", "\\n")
    return "\t".join([item_id, source, line, title, body, item_to_line(item)])


def decode_selection(line):
    parts = line.split("\t")
    while len(parts) < 6:
        parts.append("")
    return OrderedDict(
        [
            ("id", parts[0]),
            ("source", parts[1]),
            ("line", int(parts[2]) if parts[2].isdigit() else None),
            ("label", parts[3]),
            ("body", parts[4].replace("\\n", "\n")),
            ("text", parts[5]),
        ]
    )


def require_id(record):
    if not record.get("id"):
        raise ValueError("Selected item has no id:. Run `lifetxt ids --assign` first.")


def update_item(path, item_id, key, status=None):
    text = _read_text(path)
    items, diagnostics = parse_text(text, id_key=key)
    errors = [diagnostic for diagnostic in diagnostics if diagnostic.severity == "error"]
    if errors:
        raise ValueError(errors[0].format())
    matches = [item for item in items if item_id in item.details.get(key, [])]
    if len(matches) != 1:
        raise ValueError("Expected exactly one item with %s:%s." % (key, item_id))
    item = matches[0]
    if status:
        item.status = status
    replace_item_text(path, text, item)


def delete_item(path, item_id, key):
    text = _read_text(path)
    lines = text.splitlines(True)
    items, diagnostics = parse_text(text, id_key=key)
    errors = [diagnostic for diagnostic in diagnostics if diagnostic.severity == "error"]
    if errors:
        raise ValueError(errors[0].format())
    matches = [item for item in items if item_id in item.details.get(key, [])]
    if len(matches) != 1:
        raise ValueError("Expected exactly one item with %s:%s." % (key, item_id))
    item = matches[0]
    start = item.line - 1
    end = getattr(item, "end_line", item.line) or item.line
    del lines[start:end]
    _write_text(path, "".join(lines))


def replace_item_text(path, original_text, item):
    lines = original_text.splitlines(True)
    start = item.line - 1
    end = getattr(item, "end_line", item.line) or item.line
    ending = "\n"
    if lines and lines[end - 1].endswith("\r\n"):
        ending = "\r\n"
    elif lines and lines[end - 1].endswith("\r"):
        ending = "\r"
    lines[start:end] = (item_to_line(item) + ending).splitlines(True)
    _write_text(path, "".join(lines))


def open_editor(record):
    editor = os.environ.get("EDITOR")
    if not editor:
        raise ValueError("EDITOR is not set.")
    path = record["source"]
    line = record.get("line") or 1
    name = os.path.basename(editor).lower()
    if name in ("vim", "nvim", "vi"):
        command = [editor, "+%s" % line, path]
    elif "code" in name:
        command = [editor, "-g", "%s:%s" % (path, line)]
    else:
        command = [editor, path]
    return subprocess.call(command)


def _read_text(path):
    with open(path, "r", encoding="utf-8-sig") as handle:
        return handle.read()


def _write_text(path, text):
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


def _id_key(args):
    return id_key_from_config(getattr(args, "config_data", None) or {})
