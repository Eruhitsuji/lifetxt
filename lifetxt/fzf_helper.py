import base64
import json
import os
import shlex
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


def cmd_fzf_preview(args):
    sys.stdout.write(preview_token(args.token))
    return 0


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
        command.extend(["--delimiter", "\t", "--with-nth", "2"])
        if args.preview:
            command.extend(["--preview", _preview_command()])
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
        write_delete_summary(records)
        sys.stderr.write("Type DELETE to delete %d item(s): " % len(records))
        answer = sys.stdin.readline().strip().lower()
        if answer != "delete":
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
    line = item.line or None
    title = "%s %s %s" % (item.status, item.kind, item.title)
    body = item.details.get("body", [""])[0] if item.details.get("body") else ""
    record = OrderedDict(
        [
            ("id", item_id),
            ("source", source),
            ("line", line),
            ("label", title),
            ("body", body),
            ("text", item_to_line(item)),
        ]
    )
    return "\t".join([encode_record(record), display_label(record)])


def decode_selection(line):
    parts = line.split("\t")
    if parts:
        record = decode_record(parts[0])
        if record is not None:
            return record
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


def encode_record(record):
    raw = json.dumps(record, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii")


def decode_record(token):
    try:
        raw = base64.urlsafe_b64decode(str(token).encode("ascii"))
        data = json.loads(raw.decode("utf-8"), object_pairs_hook=OrderedDict)
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    return OrderedDict(
        [
            ("id", str(data.get("id") or "")),
            ("source", str(data.get("source") or "")),
            ("line", data.get("line") if isinstance(data.get("line"), int) else None),
            ("label", str(data.get("label") or "")),
            ("body", str(data.get("body") or "")),
            ("text", str(data.get("text") or "")),
        ]
    )


def display_label(record):
    location = ""
    if record.get("source"):
        location = "  %s" % record["source"]
        if record.get("line"):
            location += ":%s" % record["line"]
    item_id = "  id:%s" % record["id"] if record.get("id") else ""
    return "%s%s%s" % (record.get("label", ""), item_id, location)


def preview_token(token):
    record = decode_record(token)
    if record is None:
        return str(token) + "\n"
    return preview_text(record)


def preview_text(record):
    lines = []
    lines.append(record.get("label", ""))
    lines.append("=" * 72)
    if record.get("id"):
        lines.append("id: %s" % record["id"])
    if record.get("source"):
        location = record["source"]
        if record.get("line"):
            location += ":%s" % record["line"]
        lines.append("source: %s" % location)
    if record.get("body"):
        lines.append("")
        lines.append("body:")
        lines.extend("  " + line for line in record["body"].splitlines())
    if record.get("text"):
        lines.append("")
        lines.append("life.txt:")
        lines.append("  " + record["text"])
    return "\n".join(lines).rstrip() + "\n"


def write_delete_summary(records):
    sys.stderr.write("Items selected for deletion:\n")
    for index, record in enumerate(records, 1):
        sys.stderr.write("  %d. %s\n" % (index, display_label(record)))


def _preview_command():
    python = sys.executable
    # fzf runs the preview command through the shell it detects: POSIX sh/bash
    # on Unix, WSL, and git-bash/MSYS on Windows (all set $SHELL), but native
    # Windows builds of fzf fall back to cmd.exe, which does not understand
    # POSIX single-quote escaping from shlex.quote and instead expects the
    # whole path wrapped in double quotes.
    if os.name == "nt" and not os.environ.get("SHELL"):
        return '"%s" -m lifetxt fzf-preview {1}' % python
    return "%s -m lifetxt fzf-preview {1}" % shlex.quote(python)


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


def resolve_editor(config=None):
    """Find the editor command, or return None.

    Checks EDITOR, then VISUAL (both standard), then an `editor` key in config.
    The config fallback matters on Windows, where neither variable is normally
    set and exporting one is not the obvious move.
    """
    for name in ("EDITOR", "VISUAL"):
        value = (os.environ.get(name) or "").strip()
        if value:
            return value
    if isinstance(config, dict):
        value = str(config.get("editor") or "").strip()
        if value:
            return value
    return None


def editor_help_message():
    if os.name == "nt":
        return (
            "No editor configured. Set one with:\n"
            '  $env:EDITOR = "code"                 (current PowerShell session)\n'
            '  [Environment]::SetEnvironmentVariable("EDITOR", "code", "User")   (permanent)\n'
            'or add "editor": "code" to your lifetxt config file.'
        )
    return (
        "No editor configured. Set one with:\n"
        "  export EDITOR=vim                    (add to your shell profile to persist)\n"
        'or add "editor": "vim" to your lifetxt config file.'
    )


def editor_command(editor, path, line=1):
    """Build the argv for an editor, honouring extra flags in the setting.

    EDITOR may carry arguments ("code -n"), and on Windows the launcher is
    often a .CMD that CreateProcess cannot start from a bare name, so the
    executable is resolved through PATH (which honours PATHEXT) first.
    """
    parts = shlex.split(str(editor), posix=(os.name != "nt"))
    if not parts:
        raise ValueError(editor_help_message())
    program = parts[0].strip('"')
    extra = parts[1:]
    resolved = shutil.which(program) or program
    name = os.path.basename(program).lower()
    for suffix in (".exe", ".cmd", ".bat"):
        if name.endswith(suffix):
            name = name[: -len(suffix)]

    if name in ("vim", "nvim", "vi", "nano", "helix", "hx"):
        flag = "+%s" % line if name != "nano" else "+%s" % line
        return [resolved] + extra + [flag, path]
    if name in ("code", "code-insiders", "codium", "cursor", "windsurf"):
        # --wait keeps the caller blocked until the tab is closed, which is
        # what "open in $EDITOR and come back" means.
        return [resolved] + extra + ["--wait", "-g", "%s:%s" % (path, line)]
    if name in ("subl", "sublime_text"):
        return [resolved] + extra + ["--wait", "%s:%s" % (path, line)]
    if name in ("emacs", "emacsclient"):
        return [resolved] + extra + ["+%s" % line, path]
    if name in ("micro",):
        return [resolved] + extra + ["%s:%s" % (path, line)]
    return [resolved] + extra + [path]


def open_editor(record, config=None):
    editor = resolve_editor(config)
    if not editor:
        raise ValueError(editor_help_message())
    command = editor_command(editor, record["source"], record.get("line") or 1)
    try:
        return subprocess.call(command)
    except OSError as exc:
        raise ValueError(
            "Could not run editor %r: %s\n%s" % (editor, exc, editor_help_message())
        )


def _read_text(path):
    with open(path, "r", encoding="utf-8-sig") as handle:
        return handle.read()


def _write_text(path, text):
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


def _id_key(args):
    return id_key_from_config(getattr(args, "config_data", None) or {})
