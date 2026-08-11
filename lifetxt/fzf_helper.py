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
from .write_operations import current_revision, mutate_item_files, mutate_items


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
    raise ValueError(
        "fzf or peco was not found in PATH. Install fzf or peco, or pass --tool."
    )


def load_filtered_items(args):
    items = []
    include_source = len(args.paths or []) != 1
    for path in args.paths:
        from .mutation import read_text_snapshot

        source_snapshot = read_text_snapshot(path)
        path_items, diagnostics = parse_text(source_snapshot.text, id_key=_id_key(args))
        errors = [
            diagnostic for diagnostic in diagnostics if diagnostic.severity == "error"
        ]
        if errors:
            raise ValueError(errors[0].format())
        for item in path_items:
            item.source = path
            item.source_revision = source_snapshot.content_hash
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
        _apply_record_changes(records, args, status="[x]", operation="fzf.done")
        sys.stdout.write("Marked %d item(s) done.\n" % len(records))
        return 0
    if action == "delete":
        write_delete_summary(records)
        sys.stderr.write("Type DELETE to delete %d item(s): " % len(records))
        answer = sys.stdin.readline().strip().lower()
        if answer != "delete":
            sys.stdout.write("Canceled.\n")
            return 0
        _apply_record_changes(records, args, delete=True, operation="fzf.delete")
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
            ("revision", getattr(item, "source_revision", "") or ""),
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
            ("revision", str(data.get("revision") or "")),
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


def _apply_record_changes(
    records, args, status=None, delete=False, operation="fzf.mutate"
):
    file_changes = OrderedDict()
    for record in records:
        require_id(record)
        path = record.get("source")
        if not path:
            raise ValueError("Selected item has no source file.")
        revision = record.get("revision") or current_revision(path, allow_missing=False)
        spec = file_changes.setdefault(
            path, {"expected_revision": revision, "changes": []}
        )
        if spec["expected_revision"] != revision:
            raise ValueError(
                "Selected rows from %s have inconsistent revisions. Reload and retry."
                % path
            )
        spec["changes"].append({"id": record["id"], "status": status, "delete": delete})
    return mutate_item_files(
        file_changes,
        id_key=_id_key(args),
        operation=operation,
    )


def update_item(
    path, item_id, key, status=None, expected_revision=None, set_details=None
):
    return mutate_items(
        path,
        [{"id": item_id, "status": status, "set_details": set_details or {}}],
        id_key=key,
        expected_revision=expected_revision,
        operation="fzf.item_update",
    )


def delete_item(path, item_id, key, expected_revision=None):
    return mutate_items(
        path,
        [{"id": item_id, "delete": True}],
        id_key=key,
        expected_revision=expected_revision,
        operation="fzf.item_delete",
    )


def replace_item_text(path, original_text, item):
    from .mutation import hash_text, write_text

    lines = original_text.splitlines(True)
    start = item.line - 1
    end = getattr(item, "end_line", item.line) or item.line
    ending = "\n"
    if lines and lines[end - 1].endswith("\r\n"):
        ending = "\r\n"
    elif lines and lines[end - 1].endswith("\r"):
        ending = "\r"
    lines[start:end] = (item_to_line(item) + ending).splitlines(True)
    return write_text(
        path,
        "".join(lines),
        expected_hash=hash_text(original_text),
        operation="fzf.replace_item",
        create=False,
    )


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

    # Editors that take the line as a leading +N argument.
    if name in ("vim", "nvim", "vi", "nano", "emacs", "emacsclient", "micro", "gedit"):
        return [resolved] + extra + ["+%s" % line, path]
    # Editors that take the line as a path:line suffix.
    if name in ("helix", "hx"):
        return [resolved] + extra + ["%s:%s" % (path, line)]
    if name in ("code", "code-insiders", "codium", "vscodium", "cursor", "windsurf"):
        # --wait keeps the caller blocked until the tab is closed, which is
        # what "open in $EDITOR and come back" means.
        return [resolved] + extra + ["--wait", "-g", "%s:%s" % (path, line)]
    if name in ("subl", "sublime_text"):
        return [resolved] + extra + ["--wait", "%s:%s" % (path, line)]
    return [resolved] + extra + [path]


def open_editor(record, config=None):
    result = prepare_editor_proposal(record, config=config)
    from .delegated_mutation import apply_delegated_proposal

    applied = apply_delegated_proposal(result)
    return 0 if applied.get("applied") else 1


def prepare_editor_proposal(
    record, config=None, proposal_path=None, keep_temporary=False
):
    editor = resolve_editor(config)
    if not editor:
        raise ValueError(editor_help_message())
    from .delegated_mutation import prepare_delegated_mutation

    try:
        return prepare_delegated_mutation(
            record["source"],
            editor_command(editor, "{file}", record.get("line") or 1),
            proposal_path=proposal_path,
            keep_temporary=keep_temporary,
            expected_revision=record.get("revision") or None,
            operation="fzf.edit",
            adapter_id="editor.session",
            adapter_kind="editor_session",
        )
    except OSError as exc:
        raise ValueError(
            "Could not run editor %r: %s\n%s" % (editor, exc, editor_help_message())
        )


def _read_text(path):
    from .mutation import read_text_snapshot

    return read_text_snapshot(path).text


def _write_text(path, text):
    from .mutation import read_text_snapshot, write_text

    snap = read_text_snapshot(path, allow_missing=True)
    return write_text(
        path,
        text,
        expected_hash=snap.content_hash,
        operation="fzf_helper.write_text",
        create=not snap.exists,
    )


def _id_key(args):
    return id_key_from_config(getattr(args, "config_data", None) or {})
