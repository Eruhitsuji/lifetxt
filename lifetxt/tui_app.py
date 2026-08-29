"""Prompt-first terminal workspace for lifetxt.

This module implements the interactive TUI that ``lifetxt tui`` runs on a real
terminal. It is deliberately independent from the plain-text dashboard in
``lifetxt.tui``: that renderer stays as the dependency-free fallback used when
stdout is not a TTY, while everything here targets an interactive screen.

The design follows the shape of modern agent CLIs: a persistent input bar at the
bottom, a slash-command palette with fuzzy completion, live filtering as you
type, and a single scrollable result list with an inspector panel. Frames are
built as styled spans (``[(text, style), ...]`` per line) instead of guessing a
style from a line prefix, so the layout is testable without curses.
"""

import contextlib
import datetime
import os
import sys
from collections import OrderedDict

from .command_center import command_center
from .config import config_section
from .timezone_policy import today as timezone_today
from .tui import (
    TUI_SECTIONS,
    _char_display_width,
    _clip_display_width,
    dashboard_model,
    load_items,
    row_project,
    tui_options,
)
from .workspace import active_workspace_name
from .tui_layout import display_width, fit, fit_spans, frame_to_text, pad, spans_to_text


WORKSPACE_VIEWS = ("all",) + TUI_SECTIONS + ("next", "today")
#: Bounded rows shown per Today section before "... and N more".
TODAY_SECTION_LIMIT = 8
WORKSPACE_SORTS = ("natural", "due", "priority", "title", "status")
WORKSPACE_POLL_SECONDS = 0.25
TOAST_SECONDS = 6.0
ROW_SCAN_LIMIT = 5000

STYLES = (
    "default",
    "chrome",
    "brand",
    "tagline",
    "counter",
    "counter_warn",
    "tab",
    "tab_active",
    "section",
    "row",
    "row_selected",
    "status_open",
    "status_active",
    "status_done",
    "meta",
    "match",
    "marked",
    "input",
    "input_prefix",
    "palette",
    "palette_active",
    "palette_hint",
    "hint",
    "key",
    "toast_info",
    "toast_success",
    "toast_error",
    "panel_title",
    "detail_key",
    "detail_value",
    "empty",
)

UNICODE_GLYPHS = {
    "tl": "╭",
    "tr": "╮",
    "bl": "╰",
    "br": "╯",
    "h": "─",
    "v": "│",
    "dot": "·",
    "open": "□",
    "active": "◐",
    "done": "■",
    "blocked": "△",
    "cursor": "▌",
    "marked": "◉",
    "prompt": "›",
    "flag": "⚑",
    "ellipsis": "…",
    "bullet": "●",
}

ASCII_GLYPHS = {
    "tl": "+",
    "tr": "+",
    "bl": "+",
    "br": "+",
    "h": "-",
    "v": "|",
    "dot": "-",
    "open": "[ ]",
    "active": "[/]",
    "done": "[x]",
    "blocked": "[!]",
    "cursor": ">",
    "marked": "*",
    "prompt": ">",
    "flag": "!",
    "ellipsis": "..",
    "bullet": "*",
}

PRIORITY_ORDER = {
    "high": 0,
    "urgent": 0,
    "a": 0,
    "1": 0,
    "p1": 0,
    "med": 1,
    "medium": 1,
    "normal": 1,
    "b": 1,
    "2": 1,
    "p2": 1,
    "low": 2,
    "c": 2,
    "3": 2,
    "p3": 2,
}

STATUS_ORDER = {"[/]": 0, "[ ]": 1, "[>]": 2, "[?]": 3, "[-]": 4, "[x]": 5}

DONE_KINDS = ("T", "D", "R", "H")


def supports_unicode(stream=None):
    stream = stream if stream is not None else sys.stdout
    encoding = getattr(stream, "encoding", None) or ""
    if not encoding:
        return False
    try:
        UNICODE_GLYPHS["tl"].encode(encoding)
    except (LookupError, UnicodeError):
        return False
    return True


def glyph_set(mode="auto", stream=None):
    mode = str(mode or "auto").lower()
    if mode == "ascii":
        return ASCII_GLYPHS
    if mode == "unicode":
        return UNICODE_GLYPHS
    return UNICODE_GLYPHS if supports_unicode(stream) else ASCII_GLYPHS


# ---------------------------------------------------------------------------
# fuzzy matching
# ---------------------------------------------------------------------------


def fuzzy_match(query, text):
    """Score a subsequence match.

    Returns ``(score, indices)`` where a higher score is a better match, or
    ``None`` when the query is not a subsequence of the text. Contiguous runs
    and word-boundary hits score higher, and a literal substring hit wins over
    a scattered subsequence.
    """
    query = str(query or "")
    text = str(text or "")
    if not query:
        return (0, [])
    lowered_query = query.lower()
    lowered_text = text.lower()

    substring = lowered_text.find(lowered_query)
    if substring >= 0:
        indices = list(range(substring, substring + len(lowered_query)))
        score = 1000 - substring
        if substring == 0 or not lowered_text[substring - 1].isalnum():
            score += 200
        return (score, indices)

    indices = []
    score = 0
    position = 0
    previous = None
    for char in lowered_query:
        found = lowered_text.find(char, position)
        if found < 0:
            return None
        if previous is not None and found == previous + 1:
            score += 30
        if found == 0 or not lowered_text[found - 1].isalnum():
            score += 20
        score += max(0, 10 - found // 8)
        indices.append(found)
        previous = found
        position = found + 1
    return (score, indices)


def highlight_spans(text, indices, base_style, match_style="match"):
    """Split text into spans so matched characters can be emphasized."""
    if not indices:
        return [(text, base_style)]
    marked = set(indices)
    spans = []
    buffer = []
    buffer_matched = None
    for index, char in enumerate(str(text)):
        matched = index in marked
        if buffer_matched is None:
            buffer_matched = matched
        if matched != buffer_matched:
            spans.append(
                ("".join(buffer), match_style if buffer_matched else base_style)
            )
            buffer = []
            buffer_matched = matched
        buffer.append(char)
    if buffer:
        spans.append(("".join(buffer), match_style if buffer_matched else base_style))
    return spans


# ---------------------------------------------------------------------------
# row helpers
# ---------------------------------------------------------------------------


def row_key(row):
    return (
        row.get("section", ""),
        row.get("source", ""),
        row.get("line"),
        row.get("id", ""),
        row.get("title", ""),
    )


def row_detail(row, key):
    values = (row.get("details") or {}).get(key) or []
    return values[0] if values else ""


def row_due(row):
    return row_detail(row, "due") or row_detail(row, "do") or row_detail(row, "from")


def row_priority(row):
    return row_detail(row, "priority")


def row_haystack(row):
    parts = [row.get("title"), row.get("id"), row.get("section"), row.get("type")]
    for key, values in (row.get("details") or {}).items():
        parts.append(key)
        parts.extend(str(value) for value in values)
    return " ".join(str(part) for part in parts if part)


# Field weights for scoring. A title hit should always outrank a hit buried in
# a detail value, which a single flattened haystack cannot express.
ROW_FIELD_WEIGHTS = (("title", 3.0), ("id", 2.0), ("project", 1.5), ("details", 1.0))


def score_row(query, row):
    """Score a row per field and keep the best field's match for highlighting."""
    query = str(query or "")
    if not query:
        return (0, [])
    best = None
    for field, weight in ROW_FIELD_WEIGHTS:
        if field == "title":
            text = str(row.get("title") or "")
        elif field == "id":
            text = str(row.get("id") or "")
        elif field == "project":
            text = str(row_project(row) or "")
        else:
            text = row_haystack(row)
        if not text:
            continue
        match = fuzzy_match(query, text)
        if match is None:
            continue
        scaled = match[0] * weight
        if best is None or scaled > best[0]:
            best = (scaled, match[1] if field == "title" else [])
    return best


def is_next_action(row):
    """An actionable next step, using the shared predicate.

    Delegating keeps `/next`, `lifetxt next`, and the MCP next-actions tool
    from drifting apart.
    """
    from .nextaction import is_actionable

    return is_actionable(
        row.get("status"),
        row.get("details") or {},
        blocked=bool(row.get("blocked")),
        kind=row.get("type"),
    )


def sort_rows(rows, sort_key):
    if sort_key == "due":
        return sorted(
            rows,
            key=lambda row: (row_due(row) == "", row_due(row), row.get("title", "")),
        )
    if sort_key == "priority":
        return sorted(
            rows,
            key=lambda row: (
                PRIORITY_ORDER.get(str(row_priority(row)).lower(), 9),
                row_due(row) == "",
                row_due(row),
            ),
        )
    if sort_key == "title":
        return sorted(rows, key=lambda row: str(row.get("title", "")).lower())
    if sort_key == "status":
        return sorted(
            rows,
            key=lambda row: (
                STATUS_ORDER.get(row.get("status", ""), 9),
                str(row.get("title", "")).lower(),
            ),
        )
    return list(rows)


# ---------------------------------------------------------------------------
# state
# ---------------------------------------------------------------------------


class Toast(object):
    def __init__(self, text, level="info", created=None):
        self.text = text
        self.level = level
        self.created = created if created is not None else _now()

    def expired(self, now=None):
        now = now if now is not None else _now()
        return (now - self.created) > TOAST_SECONDS


def _now():
    return datetime.datetime.now().timestamp()


class WorkspaceState(object):
    """All mutable UI state for one TUI session."""

    def __init__(self, args, glyphs=None):
        self.args = args
        self.options = tui_options(args)
        self.active_workspace = active_workspace_name(
            getattr(args, "config_data", None) or {}
        )
        self.glyphs = glyphs or glyph_set(self.options.get("glyphs", "auto"))
        self.keymap = self.options.get("keymap", "prompt")
        self.action_by_key, self.key_bindings = _resolve_bindings_or_fallback(
            self.keymap, self.options.get("bindings")
        )
        self.mode = "input" if self.keymap == "prompt" else "nav"
        self.view = "all"
        self.sort = "natural"
        self.query = ""
        self.project = None
        self.context = None
        self.tag = None
        self.saved_view = None
        self.area = None
        self._saved_view_keys = None
        self._area_keys = None
        self.show_stats = False
        self.help_query = ""
        self.help_scroll = 0
        self.hidden = {}
        # Set by the curses runner; lets commands release the terminal to a
        # child process such as $EDITOR. None outside a curses session.
        self.suspend = None
        self.selected = 0
        self.scroll = 0
        self.input = ""
        self.cursor = 0
        self.palette_index = 0
        self.history = []
        self.history_index = None
        self.marked = set()
        self.show_help = False
        self.show_detail = True
        self.toast = None
        self.undo_stack = []
        self.rows = []
        self.counts = {"tasks": 0, "agenda": 0, "status": 0, "total": 0}
        self.error = ""
        self.running = True
        self.load_count = 0
        self._model = None
        self._today = None

    # -- derived -----------------------------------------------------------

    @property
    def effective_query(self):
        if self.input and not self.input.startswith("/"):
            return self.input
        return self.query

    @property
    def palette_open(self):
        return self.mode == "input" and self.input.startswith("/")

    def notify(self, text, level="info"):
        self.toast = Toast(text, level)

    def selected_row(self):
        if not self.rows:
            return None
        index = max(0, min(self.selected, len(self.rows) - 1))
        return self.rows[index]

    def target_rows(self):
        """Rows a bulk action applies to: every marked row, else the cursor."""
        if self.marked:
            marked = [row for row in self.rows if row_key(row) in self.marked]
            if marked:
                return marked
        row = self.selected_row()
        return [row] if row else []

    # -- data --------------------------------------------------------------

    def load(self):
        """Re-read and re-parse every input file. This is the expensive step."""
        self.options = tui_options(self.args)
        self.keymap = self.options.get("keymap", self.keymap)
        bindings_error = None
        try:
            from .tui_bindings import resolve_bindings

            self.action_by_key, self.key_bindings = resolve_bindings(
                self.keymap, self.options.get("bindings")
            )
        except ValueError as exc:
            # A bad edit mid-session keeps the last-known-good bindings
            # rather than becoming unusable; the message still surfaces via
            # self.error below.
            bindings_error = str(exc)
        try:
            # Load unfiltered: the project filter is a cheap in-memory pass in
            # refresh(), so changing it must not force another parse.
            self._model = dashboard_model(
                self.args,
                project_filter=None,
                search_query="",
                limit=ROW_SCAN_LIMIT,
            )
            self.error = ""
        except Exception as exc:
            self.error = str(exc)
            self._model = None
        if bindings_error:
            self.error = (
                self.error + "; " if self.error else ""
            ) + "tui.bindings: %s" % bindings_error
        self._today = None
        if self.saved_view is not None:
            self._saved_view_keys = frozenset()
        if self.area is not None:
            self._area_keys = frozenset()
        if self._model is not None:
            try:
                # A second, cheap parse: dashboard_model() does not expose the
                # items it already parsed, and command_center() is the single
                # shared aggregation every surface must read unmodified (see
                # lifetxt/command_center.py's module docstring).
                items = load_items(self.args.paths)
                config = getattr(self.args, "config_data", None) or {}
                self._today = command_center(items, config, timezone_today())
            except Exception:
                self._today = None
                items = None
                config = getattr(self.args, "config_data", None) or {}
            if items is not None:
                if self.saved_view is not None:
                    self._saved_view_keys = _saved_view_row_keys(
                        items, config, self.saved_view
                    )
                if self.area is not None:
                    self._area_keys = _area_row_keys(items, config, self.area)
        self.load_count += 1

    def refresh(self):
        """Recompute visible rows from the cached parse. Safe to call per key."""
        if self._model is None:
            self.rows = []
            self.counts = {"tasks": 0, "agenda": 0, "status": 0, "total": 0}
            self.hidden = {}
            return

        counts = {}
        rows = []
        for section in self._model["sections"]:
            section_rows = [row for row in section["rows"] if self._passes_filters(row)]
            counts[section["key"]] = len(section_rows)
            if self.view in ("all", section["key"]) or (
                self.view == "next" and section["key"] == "tasks"
            ):
                rows.extend(section_rows)

        if self.view == "next":
            rows = [row for row in rows if is_next_action(row)]

        query = self.effective_query
        if query:
            scored = []
            for row in rows:
                match = score_row(query, row)
                if match:
                    scored.append((-match[0], len(scored), row))
            scored.sort()
            rows = [entry[2] for entry in scored]
        rows = sort_rows(rows, self.sort)
        rows, self.hidden = _apply_section_limit(rows, self.options.get("limit") or 10)

        self.rows = rows
        counts["total"] = len(rows)
        self.counts = counts
        if self.rows:
            self.selected = max(0, min(self.selected, len(self.rows) - 1))
        else:
            self.selected = 0
        live_keys = set(row_key(row) for row in self.rows)
        self.marked = set(key for key in self.marked if key in live_keys)

    def _passes_filters(self, row):
        if self.project and row_project(row) != self.project:
            return False
        details = row.get("details") or {}
        if self.context and self.context not in [
            str(v) for v in details.get("context") or []
        ]:
            return False
        if self.tag and self.tag not in [
            str(v).lstrip("#") for v in details.get("tag") or []
        ]:
            return False
        if self.saved_view and self._saved_view_keys is not None:
            if (row.get("source"), row.get("line")) not in self._saved_view_keys:
                return False
        if self.area and self._area_keys is not None:
            if (row.get("source"), row.get("line")) not in self._area_keys:
                return False
        return True

    def reload(self):
        self.load()
        self.refresh()


def _apply_section_limit(rows, limit):
    """Cap rows per section and report how many were hidden.

    The count matters: truncating silently would make a filtered list look
    complete when it is not.
    """
    seen = {}
    kept = []
    hidden = {}
    for row in rows:
        section = row.get("section", "")
        seen[section] = seen.get(section, 0) + 1
        if seen[section] <= limit:
            kept.append(row)
        else:
            hidden[section] = hidden.get(section, 0) + 1
    return kept, hidden


# ---------------------------------------------------------------------------
# session persistence
# ---------------------------------------------------------------------------

SESSION_FIELDS = (
    "view",
    "sort",
    "project",
    "context",
    "tag",
    "saved_view",
    "area",
    "show_detail",
    "show_stats",
)
SESSION_FILE = os.path.join(".cache", "lifetxt", "tui_session.json")


def session_path(config=None):
    section = config_section(config or {}, "tui")
    return os.path.expanduser(section.get("session_file") or SESSION_FILE)


def session_payload(state):
    payload = OrderedDict()
    for field in SESSION_FIELDS:
        payload[field] = getattr(state, field)
    payload["history"] = list(state.history[-50:])
    return payload


def session_key(state):
    """Identity of the file set a session belongs to.

    Sessions are keyed per file set. Without this, quitting while filtered to
    one file's `status` view would restore that view over an unrelated
    life.txt, and the workspace would look empty for no visible reason.
    """
    paths = [
        path for path in getattr(state.args, "paths", []) or [] if path and path != "-"
    ]
    if not paths:
        return "(none)"
    return "|".join(sorted(os.path.abspath(path) for path in paths))


def _read_sessions(state):
    import json

    try:
        with open(
            session_path(getattr(state.args, "config_data", None)),
            "r",
            encoding="utf-8",
        ) as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return {}
    if not isinstance(data, dict):
        return {}
    return data.get("sessions") if isinstance(data.get("sessions"), dict) else {}


def save_session(state):
    """Persist view/sort/filter choices so the next run starts where you left."""
    if not _session_enabled(state):
        return False
    from .atomic import atomic_write_json

    sessions = _read_sessions(state)
    sessions[session_key(state)] = session_payload(state)
    # Keep the file from growing without bound as files come and go.
    if len(sessions) > 20:
        sessions = dict(list(sessions.items())[-20:])
    try:
        atomic_write_json(
            session_path(getattr(state.args, "config_data", None)),
            OrderedDict([("version", 2), ("sessions", sessions)]),
        )
        return True
    except OSError:
        # A read-only or missing cache directory must never break quitting.
        return False


def load_session(state):
    if not _session_enabled(state):
        return False
    payload = _read_sessions(state).get(session_key(state))
    if not isinstance(payload, dict):
        return False
    apply_session(state, payload)
    return True


def apply_session(state, payload):
    """Restore a saved session, ignoring any value that is no longer valid."""
    view = payload.get("view")
    if view in WORKSPACE_VIEWS:
        state.view = view
    sort_key = payload.get("sort")
    if sort_key in WORKSPACE_SORTS:
        state.sort = sort_key
    for field in ("project", "context", "tag"):
        value = payload.get(field)
        setattr(state, field, str(value) if isinstance(value, str) and value else None)
    for field in ("show_detail", "show_stats"):
        if isinstance(payload.get(field), bool):
            setattr(state, field, payload[field])
    history = payload.get("history")
    if isinstance(history, list):
        state.history = [str(entry) for entry in history if isinstance(entry, str)][
            -50:
        ]


def _session_enabled(state):
    section = config_section(getattr(state.args, "config_data", None) or {}, "tui")
    value = section.get("session")
    if value is None:
        return True
    return str(value).lower() not in ("0", "false", "no", "off")


# ---------------------------------------------------------------------------
# commands
# ---------------------------------------------------------------------------


class Command(object):
    def __init__(self, name, usage, summary, handler, alias=None, values=None):
        self.name = name
        self.usage = usage
        self.summary = summary
        self.handler = handler
        # A one-or-two letter shorthand. Typing it exactly wins over fuzzy
        # ranking, so /d is always /done and never /detail or /delete.
        self.alias = alias
        # Where Tab gets argument candidates: a tuple of literal words, or a
        # `completion` kind name resolved against the loaded records so the
        # TUI offers the same values the shell and Web UI do.
        self.values = values


def _cmd_help(state, argument):
    query = (argument or "").strip()
    if query:
        state.help_query = query
        state.show_help = True
        matches = help_entries(query)
        if not matches:
            state.help_query = ""
            raise ValueError("Nothing in help matches %r." % query)
        return ("info", "Help: %d entr(ies) matching %r." % (len(matches), query))
    state.show_help = not state.show_help
    state.help_query = ""
    return ("info", "Help %s." % ("opened" if state.show_help else "closed"))


def help_entries(query=""):
    """Rank command help lines against a query using the row fuzzy matcher."""
    entries = []
    for command in COMMANDS:
        usage = "/" + command.name + ((" " + command.usage) if command.usage else "")
        entries.append((usage, command.summary))
    query = str(query or "").strip()
    if not query:
        return entries
    # Deliberately stricter than row search. A loose subsequence over the whole
    # help line matches almost everything ("timer" is a subsequence of "Change
    # the color theme"), which makes the result useless. Match the command name
    # as a subsequence, or require a literal hit in the summary.
    scored = []
    for index, (usage, summary) in enumerate(entries):
        name = usage.split(" ", 1)[0]
        match = fuzzy_match(query, name)
        if match is None and query.lower() in summary.lower():
            match = (500, [])
        if match:
            scored.append((-match[0], index, (usage, summary)))
    scored.sort()
    return [entry[2] for entry in scored]


def _cmd_quit(state, argument):
    state.running = False
    return ("info", "Bye.")


def _cmd_reload(state, argument):
    state.reload()
    return ("success", "Reloaded %d row(s)." % len(state.rows))


def _cmd_view(state, argument):
    value = (argument or "").strip().lower() or "all"
    if value not in WORKSPACE_VIEWS:
        raise ValueError(
            "Unknown view %r. Use one of: %s" % (value, ", ".join(WORKSPACE_VIEWS))
        )
    state.view = value
    state.selected = 0
    state.scroll = 0
    return ("info", "View: %s" % value)


def _cmd_search(state, argument):
    state.query = (argument or "").strip()
    state.selected = 0
    state.scroll = 0
    return ("info", "Search: %s" % (state.query or "(cleared)"))


def _cmd_project(state, argument):
    value = (argument or "").strip()
    state.project = value or None
    state.selected = 0
    state.scroll = 0
    return ("info", "Project filter: %s" % (value or "(cleared)"))


def _cmd_context(state, argument):
    value = (argument or "").strip()
    state.context = value or None
    state.selected = 0
    state.scroll = 0
    return ("info", "Context filter: %s" % (value or "(cleared)"))


def _cmd_tag(state, argument):
    value = (argument or "").strip().lstrip("#")
    state.tag = value or None
    state.selected = 0
    state.scroll = 0
    return ("info", "Tag filter: %s" % (value or "(cleared)"))


def _saved_view_row_keys(items, config, name):
    """(source, line) keys for a saved view's result, reusing run_saved_view.

    Query evaluation stays entirely in lifetxt.saved_views/lifetxt.query; this
    only adapts the result to the (source, line) identity rows already carry.
    """
    from .saved_views import run_saved_view

    filtered, _diagnostics = run_saved_view(items, config, name)
    return frozenset((getattr(it, "source", None), it.line) for it in filtered)


def _area_row_keys(items, config, name):
    """(source, line) keys for every item in one area, reusing collect_areas."""
    from .areas import collect_areas

    bucket = collect_areas(items, config).get(name)
    if bucket is None:
        return frozenset()
    return frozenset((ref.get("source"), ref.get("line")) for ref in bucket["items"])


def _cmd_saved(state, argument):
    """List configured saved views, or apply one as the active row filter."""
    from .saved_views import list_saved_views, run_saved_view

    config = getattr(state.args, "config_data", None) or {}
    name = (argument or "").strip()
    if not name:
        views = list_saved_views(config)
        if not views:
            return ("info", "No saved views configured.")
        return (
            "info",
            "Saved views: %s" % ", ".join(view["name"] for view in views),
        )
    items = load_items(state.args.paths)
    filtered, diagnostics = run_saved_view(items, config, name)
    errors = [d for d in diagnostics if d.get("severity") == "error"]
    if errors:
        raise ValueError("Saved view %r: %s" % (name, errors[0]["message"]))
    state.saved_view = name
    state.area = None
    state._area_keys = None
    state._saved_view_keys = frozenset(
        (getattr(it, "source", None), it.line) for it in filtered
    )
    state.selected = 0
    state.scroll = 0
    return ("info", "Saved view: %s (%d item(s))" % (name, len(filtered)))


def _cmd_area(state, argument):
    """List areas with progress, or filter the active row set to one area."""
    from .areas import area_list, area_show

    config = getattr(state.args, "config_data", None) or {}
    name = (argument or "").strip()
    items = load_items(state.args.paths)
    if not name:
        areas = area_list(items, config)
        if not areas:
            return ("info", "No areas found.")
        summary = ", ".join(
            "%s (%d/%d)" % (area["name"], area["task_done"], area["task_total"])
            for area in areas
        )
        return ("info", "Areas: %s" % summary)
    # area_show() is the shared validation/error-message path: an unknown
    # name raises the exact ValueError lifetxt.areas already defines.
    area_show(items, config, name)
    state.area = name
    state.saved_view = None
    state._saved_view_keys = None
    state._area_keys = _area_row_keys(items, config, name)
    state.selected = 0
    state.scroll = 0
    return ("info", "Area: %s (%d item(s))" % (name, len(state._area_keys)))


def _cmd_next(state, argument):
    """Switch to the actionable-next view: open, unblocked, not someday."""
    state.view = "next"
    state.sort = "priority"
    state.selected = 0
    state.scroll = 0
    return ("info", "Next actions: open, unblocked, not someday/maybe.")


def _cmd_today(state, argument):
    """Switch to the Today view: the shared Daily Command Center."""
    state.view = "today"
    state.selected = 0
    state.scroll = 0
    return ("info", "Today: now, attention, inbox, and upcoming.")


def _cmd_goto(state, argument):
    value = (argument or "").strip()
    if not value:
        raise ValueError("Usage: /goto ID")
    for index, row in enumerate(state.rows):
        if row.get("id") == value:
            state.selected = index
            return ("info", "Jumped to %s." % value)
    for index, row in enumerate(state.rows):
        if value.lower() in str(row.get("id") or "").lower():
            state.selected = index
            return ("info", "Jumped to %s." % row.get("id"))
    raise ValueError(
        "No visible row with id %r. Clear filters with /clear first." % value
    )


def _cmd_sort(state, argument):
    value = (argument or "").strip().lower() or "natural"
    if value not in WORKSPACE_SORTS:
        raise ValueError(
            "Unknown sort %r. Use one of: %s" % (value, ", ".join(WORKSPACE_SORTS))
        )
    state.sort = value
    return ("info", "Sort: %s" % value)


def _cmd_clear(state, argument):
    state.query = ""
    state.project = None
    state.context = None
    state.tag = None
    state.saved_view = None
    state.area = None
    state._saved_view_keys = None
    state._area_keys = None
    state.marked = set()
    state.selected = 0
    state.scroll = 0
    return ("info", "Filters cleared.")


def _cmd_mark(state, argument):
    value = (argument or "").strip().lower() or "toggle"
    if value == "all":
        state.marked = set(row_key(row) for row in state.rows)
    elif value == "none":
        state.marked = set()
    elif value == "toggle":
        row = state.selected_row()
        if not row:
            raise ValueError("No row selected.")
        key = row_key(row)
        if key in state.marked:
            state.marked.discard(key)
        else:
            state.marked.add(key)
    else:
        raise ValueError("Unknown mark mode %r. Use all, none, or toggle." % value)
    return ("info", "%d row(s) marked." % len(state.marked))


def _cmd_detail(state, argument):
    state.show_detail = not state.show_detail
    return ("info", "Inspector %s." % ("shown" if state.show_detail else "hidden"))


def _cmd_done(state, argument):
    rows = state.target_rows()
    ids = ", ".join(row.get("id") or "?" for row in rows)
    stamp = _completion_value(state, argument)

    def change_for_row(row):
        return {"id": row["id"], "status": "[x]", "set_details": {"done": [stamp]}}

    _mutate_rows(state, rows, "done %s" % ids, change_for_row, require_task=True)
    return ("success", "Marked done (%s): %s" % (stamp, ids))


def _completion_value(state, argument):
    """Pick the done: value, honouring /done now and config done.precision."""
    import datetime as _datetime

    from .config import config_section

    choice = (argument or "").strip().lower()
    if choice and choice not in ("now", "today", "date"):
        raise ValueError("Usage: /done [now|today]")
    config = getattr(state.args, "config_data", None) or {}
    precision = str(config_section(config, "done").get("precision") or "date").lower()
    if choice == "now":
        precision = "datetime"
    elif choice in ("today", "date"):
        precision = "date"
    from .timezone_policy import now as timezone_now

    moment = timezone_now().replace(tzinfo=None)
    if precision == "datetime":
        return moment.strftime("%Y-%m-%dT%H:%M")
    return moment.date().isoformat()


def _cmd_status(state, argument):
    from .model import STATUS_ALIASES, VALID_STATUSES

    value = (argument or "").strip()
    if not value:
        raise ValueError("Usage: /status open|active|done|dropped|deferred|pending")
    status = STATUS_ALIASES.get(value.lower(), value)
    if status not in VALID_STATUSES:
        raise ValueError(
            "Unknown status %r. Use one of: %s"
            % (value, ", ".join(sorted(set(STATUS_ALIASES))))
        )
    rows = state.target_rows()
    ids = ", ".join(row.get("id") or "?" for row in rows)

    def change_for_row(row):
        return {"id": row["id"], "status": status}

    count = _mutate_rows(state, rows, "status %s %s" % (status, ids), change_for_row)
    return ("success", "Set %s on %d row(s)." % (status, count))


def _cmd_set(state, argument):
    parts = (argument or "").strip().split(None, 1)
    if not parts:
        raise ValueError("Usage: /set KEY VALUE  (empty VALUE removes the key)")
    key = parts[0].strip()
    value = parts[1].strip() if len(parts) > 1 else ""
    if not key.replace("_", "").isalnum():
        raise ValueError("Detail key %r is not a valid life.txt key." % key)
    rows = state.target_rows()
    details = {key: [value] if value else []}
    count = _set_row_details(
        state, rows, details, "set %s on %d row(s)" % (key, len(rows))
    )
    if value:
        return ("success", "Set %s:%s on %d row(s)." % (key, value, count))
    return ("success", "Removed %s: from %d row(s)." % (key, count))


def _cmd_due(state, argument):
    value = (argument or "").strip()
    rows = state.target_rows()
    if not value:
        count = _set_row_details(state, rows, {"due": []}, "clear due")
        return ("success", "Cleared due: on %d row(s)." % count)
    from .shorthand import ShorthandError

    try:
        # The token set is deliberately closed; guessing at free-form dates
        # would write an unparseable due: value that only surfaces later.
        resolved = _resolve_date_token(value, strict=True)
    except ShorthandError as exc:
        raise ValueError(str(exc))
    count = _set_row_details(state, rows, {"due": [resolved]}, "due %s" % resolved)
    return ("success", "Set due:%s on %d row(s)." % (resolved, count))


def _cmd_assign(state, argument):
    value = (argument or "").strip()
    rows = state.target_rows()
    if not value:
        count = _set_row_details(state, rows, {"assignee": []}, "clear assignee")
        return ("success", "Cleared assignee: on %d row(s)." % count)
    count = _set_row_details(state, rows, {"assignee": [value]}, "assign %s" % value)
    return ("success", "Assigned %d row(s) to %s." % (count, value))


def _cmd_delete(state, argument):
    rows = state.target_rows()
    if not rows:
        raise ValueError("No row selected.")
    confirmed = (argument or "").strip().lower() in ("yes", "force", "confirm")
    if not confirmed:
        titles = ", ".join(row.get("title") or "?" for row in rows[:3])
        more = " and %d more" % (len(rows) - 3) if len(rows) > 3 else ""
        raise ValueError(
            "Deleting %d row(s): %s%s. Re-run as `/delete yes` to confirm."
            % (len(rows), titles, more)
        )
    ids = ", ".join(row.get("id") or "?" for row in rows)

    def change_for_row(row):
        return {"id": row["id"], "delete": True}

    count = _mutate_rows(state, rows, "delete %s" % ids, change_for_row)
    return ("success", "Deleted %d row(s). /undo restores them." % count)


def _resolve_date_token(value, strict=False):
    """Delegate to the shared resolver so every surface accepts one token set."""
    from .shorthand import resolve_date_token

    return resolve_date_token(value, strict=strict)


def _cmd_undo(state, argument):
    if not state.undo_stack:
        raise ValueError("Nothing to undo in this session.")
    snapshots, label = state.undo_stack[-1]
    from .write_operations import commit_text_replacements

    replacements = {}
    for row in snapshots:
        path, text, expected_revision = row
        replacements[path] = {
            "text": text,
            "expected_revision": expected_revision,
            "validate_life": True,
        }
    commit_text_replacements(
        replacements,
        operation="tui.undo",
        journal_dir=_tui_journal_dir(state),
        config=getattr(state.args, "config_data", None) or {},
    )
    state.undo_stack.pop()
    state.reload()
    return ("success", "Undid %s." % label)


def _cmd_edit(state, argument):
    row = state.selected_row()
    if not row:
        raise ValueError("No row selected.")
    if not row.get("source"):
        raise ValueError("Selected row has no source file.")
    from .fzf_helper import open_editor

    record = {
        "id": row.get("id", ""),
        "source": row.get("source", ""),
        "line": row.get("line"),
        "label": row.get("label", ""),
        "body": "",
        "text": row.get("text", ""),
        "revision": row.get("source_revision") or row.get("revision") or "",
    }
    config = getattr(state.args, "config_data", None) or {}
    # A terminal editor draws over the curses screen, so the TUI has to release
    # the terminal for the duration of the child process and take it back after.
    with _suspend_terminal(state):
        open_editor(record, config=config)
    state.reload()
    return (
        "info",
        "Editor closed for %s." % (row.get("id") or row.get("title") or "row"),
    )


@contextlib.contextmanager
def _suspend_terminal(state):
    suspend = getattr(state, "suspend", None)
    if suspend is None:
        yield
        return
    with suspend():
        yield


def _cmd_state(state, argument):
    """Record a presence status, closing the previously open one."""
    from .presence import COMMON_STATES, status_transition

    value = (argument or "").strip()
    path = _write_target(state)
    try:
        with open(path, "r", encoding="utf-8-sig") as handle:
            text = handle.read()
    except OSError:
        text = ""

    close_only = value.lower() in ("end", "off", "close", "")
    if close_only and not value:
        raise ValueError(
            "Usage: /state %s ... or /state end to close the current status."
            % "|".join(COMMON_STATES[:4])
        )

    parts = value.split(None, 1)
    new_state = None if close_only else parts[0]
    title = parts[1].strip() if len(parts) > 1 else None

    from . import mutation

    before = mutation.read_text_snapshot(path, allow_missing=True)
    outcome = {"closed": [], "unchanged": None}

    def transform(current_text):
        result = status_transition(
            current_text,
            state=new_state,
            title=title,
            person="self",
            id_key=state.options["id_key"],
            close_only=close_only,
        )
        outcome["closed"] = list(result.closed or [])
        outcome["unchanged"] = result.unchanged
        return result.text

    write_result = mutation.write_text(
        path,
        expected_hash=before.content_hash,
        operation="tui.state",
        create=not before.exists,
        transform=transform,
        default_text="",
    )
    if outcome["unchanged"]:
        return ("info", "Already %s. Nothing written." % outcome["unchanged"])
    closed = outcome["closed"]
    _remember_undo(
        state,
        {path: before},
        {path: write_result.after_hash},
        "state %s" % (new_state or "end"),
    )
    state.reload()
    if close_only:
        if not closed:
            return ("info", "No open status to close.")
        return ("success", "Closed status: %s" % _status_label(closed[0]))
    if closed:
        return ("success", "Status: %s (closed %d previous)" % (new_state, len(closed)))
    return ("success", "Status: %s" % new_state)


def _status_label(line):
    """Title of a rendered status line, parsed so quoted titles stay intact."""
    from .parser import parse_text

    try:
        items, _diagnostics = parse_text(str(line) + "\n")
    except Exception:
        items = []
    if items:
        return items[0].title
    parts = str(line).split()
    return parts[2] if len(parts) > 2 else str(line)


def _cmd_now(state, argument):
    """Show the current presence status without leaving the workspace."""
    from .presence import active_status_items
    from .parser import parse_text

    path = _write_target(state)
    try:
        with open(path, "r", encoding="utf-8-sig") as handle:
            items, _diagnostics = parse_text(
                handle.read(), id_key=state.options["id_key"]
            )
    except OSError as exc:
        raise ValueError("Could not read %s: %s" % (os.path.basename(path), exc))
    open_items = active_status_items(items, person=(argument or "").strip() or None)
    if not open_items:
        return ("info", "No open status. Set one with /state busy.")
    labels = []
    for item in open_items:
        values = item.details.get("state") or [""]
        person = (item.details.get("person") or ["self"])[0]
        labels.append(
            "%s: %s since %s"
            % (person, values[0], (item.details.get("from") or [""])[0])
        )
    return ("info", "  |  ".join(labels))


def _cmd_add(state, argument):
    title = (argument or "").strip()
    if not title:
        raise ValueError("Usage: /add TITLE")
    path = _write_target(state)
    existing = set(row.get("id") for row in state.rows if row.get("id"))
    line = _quick_add_line(title, state.options["id_key"], existing_ids=existing)
    from . import mutation
    from .write_operations import append_life_records

    before = mutation.read_text_snapshot(path, allow_missing=True)
    result = append_life_records(
        path, line + "\n", expected_revision=before.content_hash, operation="tui.add"
    )
    _remember_undo(state, {path: before}, {path: result.after_hash}, "add %s" % title)
    state.reload()
    return ("success", "Added to %s: %s" % (os.path.basename(path), line))


def _cmd_export(state, argument):
    parts = (argument or "").strip().split(None, 1)
    fmt = (parts[0] if parts else "md").lower()
    if fmt not in EXPORT_FORMATS:
        raise ValueError(
            "Unknown format %r. Use one of: %s" % (fmt, ", ".join(EXPORT_FORMATS))
        )
    if not state.rows:
        raise ValueError("Nothing to export: no visible rows.")
    path = parts[1].strip() if len(parts) > 1 else "lifetxt-export.%s" % fmt
    text = render_export(state.rows, fmt)
    from .atomic import atomic_write_text

    atomic_write_text(path, text)
    return ("success", "Exported %d row(s) to %s." % (len(state.rows), path))


def _cmd_stats(state, argument):
    state.show_stats = not state.show_stats
    return ("info", "Stats %s." % ("shown" if state.show_stats else "hidden"))


def _cmd_timer(state, argument):
    action = (argument or "").strip().lower() or "status"
    if action not in ("start", "stop", "status", "cancel"):
        raise ValueError("Usage: /timer start|stop|status|cancel")
    from . import mutation
    from . import timer as timer_module

    config = getattr(state.args, "config_data", None) or {}
    state_file = timer_module.timer_state_file(config)
    if action == "status":
        data = timer_module.timer_status_data(
            config=config, paths=getattr(state.args, "paths", None)
        )
        if not data.get("running"):
            return ("info", "No running timer.")
        suffix = " (paused)" if data.get("paused") else ""
        return (
            "info",
            "Timer %s: %s%s" % (data.get("id"), data.get("elapsed"), suffix),
        )

    if action == "cancel":
        snapshot = mutation.read_text_snapshot(state_file, allow_missing=True)
        if not snapshot.exists:
            raise ValueError("No running timer to cancel.")
        data = timer_module.cancel_timer_transaction(
            config=config,
            expected_timer_revision=snapshot.content_hash,
            require_revision=True,
        )
        return (
            "success",
            "Canceled timer for %s. No elapsed: was written." % data.get("id"),
        )

    if action == "start":
        row = state.selected_row()
        if not row or not row.get("id") or not row.get("source"):
            raise ValueError("Select a row with an id: to start a timer.")
        item_snapshot = mutation.read_text_snapshot(row["source"])
        timer_snapshot = mutation.read_text_snapshot(state_file, allow_missing=True)
        result = timer_module.start_timer_transaction(
            row["source"],
            row["id"],
            config=config,
            expected_item_revision=item_snapshot.content_hash,
            expected_timer_revision=timer_snapshot.content_hash,
            require_revisions=True,
        )
        state.reload()
        return (
            "success",
            "Started timer for %s (transaction %s)."
            % (row["id"], result.get("transaction_id")),
        )

    status = timer_module.timer_status_data(
        config=config, paths=getattr(state.args, "paths", None)
    )
    if not status.get("running"):
        raise ValueError("No running timer to stop.")
    result = timer_module.stop_timer_transaction(
        path=status.get("file"),
        item_id=status.get("id"),
        config=config,
        expected_item_revision=status.get("item_revision"),
        expected_timer_revision=status.get("timer_revision"),
        require_revisions=True,
    )
    state.reload()
    return (
        "success",
        "Stopped timer for %s: +%s, total %s (transaction %s)."
        % (
            result["id"],
            result["elapsed_added"],
            result["elapsed_total"],
            result.get("transaction_id"),
        ),
    )


EXPORT_FORMATS = ("md", "csv", "json")


def render_export(rows, fmt):
    """Serialize the currently visible rows. Kept independent of the file
    parser so an export always matches exactly what the screen shows."""
    if fmt == "json":
        import json

        payload = [
            {
                "section": row.get("section", ""),
                "status": row.get("status", ""),
                "type": row.get("type", ""),
                "title": row.get("title", ""),
                "id": row.get("id", ""),
                "source": row.get("source", ""),
                "line": row.get("line"),
                "details": dict(row.get("details") or {}),
            }
            for row in rows
        ]
        return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"

    if fmt == "csv":
        import csv
        import io as _io

        buffer = _io.StringIO()
        writer = csv.writer(buffer, lineterminator="\n")
        writer.writerow(
            [
                "section",
                "status",
                "type",
                "title",
                "id",
                "project",
                "due",
                "priority",
                "source",
                "line",
            ]
        )
        for row in rows:
            writer.writerow(
                [
                    row.get("section", ""),
                    row.get("status", ""),
                    row.get("type", ""),
                    row.get("title", ""),
                    row.get("id", ""),
                    row_project(row) or "",
                    row_due(row),
                    row_priority(row),
                    row.get("source", ""),
                    row.get("line") or "",
                ]
            )
        return buffer.getvalue()

    lines = ["# lifetxt export", ""]
    section = None
    for row in rows:
        if row.get("section") != section:
            section = row.get("section")
            lines.append("")
            lines.append("## %s" % str(section).title())
            lines.append("")
        mark = "x" if row.get("status") == "[x]" else " "
        meta = []
        if row_project(row):
            meta.append("project:%s" % row_project(row))
        if row_due(row):
            meta.append("due:%s" % row_due(row))
        if row_priority(row):
            meta.append("priority:%s" % row_priority(row))
        if row.get("id"):
            meta.append("id:%s" % row["id"])
        suffix = ("  _%s_" % " ".join(meta)) if meta else ""
        lines.append("- [%s] %s%s" % (mark, row.get("title") or "(untitled)", suffix))
    return "\n".join(lines).strip() + "\n"


def _cmd_theme(state, argument):
    from .tui import TUI_THEMES

    value = (argument or "").strip().lower()
    if value not in TUI_THEMES:
        raise ValueError(
            "Unknown theme %r. Use one of: %s" % (value, ", ".join(TUI_THEMES))
        )
    state.options["theme"] = value
    setattr(state.args, "theme", value)
    return ("info", "Theme: %s" % value)


def _cmd_limit(state, argument):
    try:
        value = max(1, int((argument or "").strip()))
    except ValueError:
        raise ValueError("Usage: /limit N")
    state.options["limit"] = value
    setattr(state.args, "limit", value)
    return ("info", "Rows per section: %d" % value)


def _cmd_window(state, argument):
    value = (argument or "").strip()
    if not value:
        raise ValueError("Usage: /window 12h")
    state.options["agenda_window"] = value
    setattr(state.args, "agenda_window", value)
    return ("info", "Agenda window: %s" % value)


COMMANDS = (
    Command("help", "[QUERY]", "Toggle the reference, or search it", _cmd_help),
    Command(
        "view",
        "all|tasks|agenda|status|next|today",
        "Switch which sections are listed",
        _cmd_view,
        values=("all", "tasks", "agenda", "status", "next", "today"),
    ),
    Command(
        "next",
        "",
        "Show open, unblocked, non-someday actions by priority",
        _cmd_next,
        alias="n",
    ),
    Command(
        "today",
        "",
        "Show the Daily Command Center: now, attention, inbox, upcoming",
        _cmd_today,
    ),
    Command("search", "TEXT", "Fuzzy filter every listed row", _cmd_search, alias="f"),
    Command(
        "project",
        "NAME",
        "Filter by project: (empty clears)",
        _cmd_project,
        values="project",
    ),
    Command(
        "context",
        "NAME",
        "Filter by context: (empty clears)",
        _cmd_context,
        values="context",
    ),
    Command("tag", "NAME", "Filter by tag: (empty clears)", _cmd_tag, values="tag"),
    Command(
        "saved",
        "[NAME]",
        "List saved views, or apply one as the active filter",
        _cmd_saved,
    ),
    Command(
        "area",
        "[NAME]",
        "List areas with progress, or filter rows to one area",
        _cmd_area,
    ),
    Command(
        "sort",
        "natural|due|priority|title|status",
        "Change row ordering",
        _cmd_sort,
        values=("natural", "due", "priority", "title", "status"),
    ),
    Command("clear", "", "Clear every filter and mark", _cmd_clear),
    Command("goto", "ID", "Move the selection to a record id", _cmd_goto, values="id"),
    Command(
        "mark",
        "toggle|all|none",
        "Mark rows for bulk actions",
        _cmd_mark,
        values=("toggle", "all", "none"),
    ),
    Command(
        "done",
        "[now]",
        "Mark rows done and record done:",
        _cmd_done,
        alias="d",
        values=("now",),
    ),
    Command(
        "state",
        "STATE [TITLE] | end",
        "Record presence, closing the previous status",
        _cmd_state,
        alias="s",
        values="state",
    ),
    Command(
        "now",
        "[PERSON]",
        "Show the current open presence status",
        _cmd_now,
        values="person",
    ),
    Command(
        "status",
        "open|active|done|dropped",
        "Set the status of the marked or selected rows",
        _cmd_status,
        values=("open", "active", "done", "dropped"),
    ),
    Command(
        "set",
        "KEY VALUE",
        "Set a detail on the marked or selected rows",
        _cmd_set,
        values="key",
    ),
    Command(
        "due",
        "DATE",
        "Set due: using today/tomorrow/+3d tokens",
        _cmd_due,
        values="date",
    ),
    Command(
        "assign",
        "USER",
        "Set assignee: on the marked or selected rows",
        _cmd_assign,
        values="person",
    ),
    Command(
        "add", "TITLE", "Append a new open task to the write file", _cmd_add, alias="a"
    ),
    Command(
        "delete",
        "yes",
        "Delete the marked or selected rows (needs confirmation)",
        _cmd_delete,
    ),
    Command("edit", "", "Open the selected row in $EDITOR", _cmd_edit, alias="e"),
    Command(
        "timer",
        "start|stop|status|cancel",
        "Track elapsed time on the selected row",
        _cmd_timer,
        alias="t",
        values=("start", "stop", "status", "cancel"),
    ),
    Command(
        "undo", "", "Undo the last write made in this session", _cmd_undo, alias="u"
    ),
    Command(
        "export",
        "md|csv|json [PATH]",
        "Write the visible rows to a file",
        _cmd_export,
        values=("md", "csv", "json"),
    ),
    Command("stats", "", "Toggle a summary of the visible rows", _cmd_stats),
    Command("detail", "", "Toggle the inspector panel", _cmd_detail),
    Command("reload", "", "Re-read every file now", _cmd_reload),
    Command(
        "theme",
        "auto|dark|light|mono",
        "Change the color theme",
        _cmd_theme,
        values=("auto", "dark", "light", "mono"),
    ),
    Command("limit", "N", "Rows kept per section", _cmd_limit),
    Command("window", "12h", "Agenda window around now", _cmd_window),
    Command("quit", "", "Leave the TUI", _cmd_quit, alias="q"),
)

COMMANDS_BY_NAME = dict((command.name, command) for command in COMMANDS)
COMMANDS_BY_ALIAS = dict(
    (command.alias, command) for command in COMMANDS if command.alias
)


def command_suggestions(text):
    """Rank commands for the palette using the same fuzzy matcher as rows."""
    typed = str(text or "")
    if typed.startswith("/"):
        typed = typed[1:]
    name = typed.split(" ", 1)[0]
    if not name:
        return [(command, []) for command in COMMANDS]
    exact = COMMANDS_BY_ALIAS.get(name.lower())
    if exact is not None:
        rest = [(command, []) for command in COMMANDS if command is not exact]
        return [(exact, list(range(len(exact.name))))] + rest
    scored = []
    for index, command in enumerate(COMMANDS):
        match = fuzzy_match(name, command.name)
        if match:
            scored.append((-match[0], index, command, match[1]))
    scored.sort()
    return [(entry[2], entry[3]) for entry in scored]


#: Date words `due:` accepts. Grammar rather than file content, so they are
#: listed here instead of being read out of the records.
DATE_TOKENS = (
    "today",
    "tomorrow",
    "yesterday",
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
    "next_monday",
    "next_tuesday",
    "next_wednesday",
    "next_thursday",
    "next_friday",
    "next_saturday",
    "next_sunday",
    "next_week",
    "+1d",
    "+3d",
    "+1w",
    "-1w",
    "+1m",
    "+1y",
)


def argument_suggestions(state, text):
    """Candidates for the argument being typed, or [] when there are none.

    Returns (prefix, values): `prefix` is the partial word Tab should replace.
    """
    typed = str(text or "")
    if typed.startswith("/"):
        typed = typed[1:]
    if " " not in typed:
        return ("", [])

    name, _, argument = typed.partition(" ")
    command = COMMANDS_BY_NAME.get(name.lower()) or COMMANDS_BY_ALIAS.get(name.lower())
    if command is None or not command.values:
        return ("", [])

    # Only the word under the cursor is completed; earlier words stay put.
    prefix = argument.rsplit(" ", 1)[-1] if argument else ""

    if isinstance(command.values, tuple):
        pool = list(command.values)
    elif command.values == "date":
        pool = list(DATE_TOKENS)
    else:
        pool = _record_values(state, command.values)

    lowered = prefix.lower()
    starts = [value for value in pool if value.lower().startswith(lowered)]
    contains = [
        value
        for value in pool
        if lowered
        and lowered in value.lower()
        and not value.lower().startswith(lowered)
    ]
    return (prefix, starts + contains)


def _record_values(state, kind):
    """File-derived candidates, from the records the TUI already parsed."""
    try:
        from .completion import candidates

        model = getattr(state, "_model", None) or {}
        return candidates(kind, "", items=model.get("items") or [])
    except Exception:
        # Completion is an assist: a failure must not break the input line.
        return []


def apply_argument_completion(state):
    """Accept the highlighted argument candidate. True when something changed.

    The palette lists the candidates, so this takes whichever one up/down has
    landed on rather than always the first.
    """
    prefix, values = argument_suggestions(state, state.input)
    if not values:
        return False

    index = max(0, min(getattr(state, "palette_index", 0), len(values) - 1))
    base = state.input[: len(state.input) - len(prefix)]
    state.input = base + values[index]
    state.cursor = len(state.input)
    state.palette_index = 0
    return True


def run_command(state, text):
    """Execute a ``/name args`` string. Returns a (level, message) tuple."""
    text = str(text or "").strip()
    if text.startswith("/"):
        text = text[1:]
    if not text:
        raise ValueError("Type a command name after /.")
    name, _, argument = text.partition(" ")
    command = COMMANDS_BY_NAME.get(name.lower()) or COMMANDS_BY_ALIAS.get(name.lower())
    if command is None:
        suggestions = command_suggestions(name)
        hint = ""
        if suggestions:
            hint = " Did you mean /%s?" % suggestions[0][0].name
        raise ValueError("Unknown command /%s.%s" % (name, hint))
    return command.handler(state, argument.strip())


def _mutate_rows(state, rows, label, change_for_row, require_task=False):
    """Apply selected row changes through one revision-aware semantic commit."""
    if not rows:
        raise ValueError("No row selected.")
    from . import mutation
    from .write_operations import mutate_item_files, mutate_items

    grouped = {}
    before = {}
    for row in rows:
        if not row.get("source") or not row.get("id"):
            raise ValueError(
                "%s needs a source file and an id: to edit. Run `lifetxt ids --assign` first."
                % (row.get("title") or "Row")
            )
        if require_task and row.get("type") not in DONE_KINDS:
            raise ValueError(
                "%s is not a task-like record." % (row.get("title") or "Row")
            )
        path = row["source"]
        grouped.setdefault(path, []).append(change_for_row(row))
    for path in sorted(grouped):
        before[path] = mutation.read_text_snapshot(path)

    id_key = state.options["id_key"]
    after = {}
    if len(grouped) == 1:
        path = next(iter(grouped))
        result = mutate_items(
            path,
            grouped[path],
            id_key=id_key,
            expected_revision=before[path].content_hash,
            operation="tui.semantic",
        )
        after[path] = result.after_hash
    else:
        specs = {}
        for path in grouped:
            specs[path] = {
                "changes": grouped[path],
                "expected_revision": before[path].content_hash,
            }
        result = mutate_item_files(
            specs,
            id_key=id_key,
            operation="tui.semantic.multi",
            journal_dir=_tui_journal_dir(state),
        )
        for target in result.targets:
            after[target.path] = target.after_hash
    _remember_undo(state, before, after, label)
    state.marked = set()
    state.reload()
    return len(rows)


def _set_row_details(state, rows, details, label):
    def change_for_row(row):
        return {"id": row["id"], "set_details": details}

    return _mutate_rows(state, rows, label, change_for_row)


def _remember_undo(state, before, after, label):
    snapshots = []
    for path in sorted(before):
        snap = before[path]
        snapshots.append((path, snap.text, after[path]))
    if not snapshots:
        return
    state.undo_stack.append((snapshots, label))
    del state.undo_stack[:-20]


def _push_undo(state, paths, label):
    """Compatibility helper for commands not yet migrated to semantic changes."""
    from . import mutation

    if isinstance(paths, str):
        paths = [paths]
    before = {}
    for path in paths:
        try:
            before[path] = mutation.read_text_snapshot(path)
        except OSError:
            continue
    _remember_undo(
        state,
        before,
        dict((path, snap.content_hash) for path, snap in before.items()),
        label,
    )


def _tui_journal_dir(state):
    config = getattr(state.args, "config_data", None) or {}
    section = config.get("transactions") if isinstance(config, dict) else None
    if isinstance(section, dict) and section.get("journal_dir"):
        return section.get("journal_dir")
    return None


def _write_target(state):
    config = getattr(state.args, "config_data", None) or {}
    from .config import config_write_file

    path = config_write_file(config)
    if path:
        return path
    paths = [
        path for path in getattr(state.args, "paths", []) or [] if path and path != "-"
    ]
    if not paths:
        raise ValueError("No writable file. Set write_file in config or pass a path.")
    return paths[0]


def _quick_add_line(title, id_key, existing_ids=None, shorthand=True):
    from .ids import generate_item_id
    from .model import Item
    from .serializer import item_to_line
    from .shorthand import ShorthandError, parse_capture

    details = {}
    if shorthand:
        try:
            parsed_title, details = parse_capture(title, strict_dates=True)
        except ShorthandError as exc:
            raise ValueError(str(exc))
        if details:
            if not parsed_title:
                raise ValueError("Capture shorthand consumed the whole title.")
            title = parsed_title

    item = Item("[ ]", "T", title, details or None, 0)
    item.details[id_key] = [generate_item_id(item, existing_ids=existing_ids)]
    return item_to_line(item)


# ---------------------------------------------------------------------------
# frame building
# ---------------------------------------------------------------------------


def build_frame(state, width, height):
    """Render the whole screen as a list of styled span lines."""
    width = max(20, int(width))
    height = max(8, int(height))

    header = _build_header(state, width)
    footer = _build_footer(state, width)
    body_height = max(1, height - len(header) - len(footer))

    if state.show_help:
        body = _build_help(state, width, body_height)
    elif state.error:
        body = _build_error(state, width, body_height)
    elif state.view == "today":
        body = _build_today(state, width, body_height)
    else:
        body = _build_body(state, width, body_height)

    frame = header + body[:body_height] + footer
    while len(frame) < height:
        frame.insert(len(header) + len(body[:body_height]), [("", "default")])
    frame = frame[:height]
    return [fit_spans(line, width) for line in frame]


def _build_header(state, width):
    glyphs = state.glyphs
    counts = state.counts
    inner = width - 2

    tagline = " %s workspace" % glyphs["dot"]
    if getattr(state, "active_workspace", None):
        tagline += " %s workspace:%s" % (glyphs["dot"], state.active_workspace)
    title = " lifetxt" + tagline
    summary = "%d task %s %d agenda %s %d status " % (
        counts.get("tasks", 0),
        glyphs["dot"],
        counts.get("agenda", 0),
        glyphs["dot"],
        counts.get("status", 0),
    )
    gap = max(1, inner - display_width(title) - display_width(summary))
    top = [(glyphs["tl"] + glyphs["h"] * inner + glyphs["tr"], "chrome")]
    middle = [
        (glyphs["v"], "chrome"),
        (" lifetxt", "brand"),
        (tagline, "tagline"),
        (" " * gap, "default"),
        (summary, "counter"),
        (glyphs["v"], "chrome"),
    ]
    bottom = [(glyphs["bl"] + glyphs["h"] * inner + glyphs["br"], "chrome")]

    tabs = [("  ", "default")]
    for view in WORKSPACE_VIEWS:
        active = view == state.view
        label = "%s%s" % (glyphs["bullet"] + " " if active else "  ", view)
        tabs.append((label, "tab_active" if active else "tab"))
        tabs.append(("  ", "default"))
    used = display_width(spans_to_text(tabs))
    context = _context_label(state, max(0, width - used - 2))
    tabs.append((" " * max(1, width - used - display_width(context) - 1), "default"))
    tabs.append((context, "meta"))

    return [top, middle, bottom, tabs, [("", "default")]]


def _context_label(state, width=None):
    """Build the right-hand context label, dropping whole parts that do not fit.

    Parts are ordered least to most important so that clipping sheds the file
    name before the active filters, and never leaves a half-written value.
    """
    parts = []
    paths = [
        path for path in getattr(state.args, "paths", []) or [] if path and path != "-"
    ]
    if len(paths) == 1:
        parts.append(os.path.basename(paths[0]))
    elif paths:
        parts.append("%d files" % len(paths))
    if state.sort != "natural":
        parts.append("sort:%s" % state.sort)
    if state.marked:
        parts.append("marked:%d" % len(state.marked))
    if state.project:
        parts.append("project:%s" % state.project)
    if state.context:
        parts.append("context:%s" % state.context)
    if state.tag:
        parts.append("tag:%s" % state.tag)
    if state.saved_view:
        parts.append("saved:%s" % state.saved_view)
    if state.area:
        parts.append("area:%s" % state.area)
    if state.query:
        parts.append("search:%s" % state.query)

    separator = "  %s  " % state.glyphs["dot"]
    if width is None:
        return separator.join(parts)
    while parts:
        label = separator.join(parts)
        if display_width(label) <= width:
            return label
        parts.pop(0)
    return ""


TWO_PANE_MIN_WIDTH = 118
TWO_PANE_SIDE_WIDTH = 44


def _build_body(state, width, height):
    if state.show_stats:
        return _build_stats(state, width, height)
    if state.show_detail and width >= TWO_PANE_MIN_WIDTH:
        return _build_two_pane(state, width, height)

    detail_height = 0
    if state.show_detail and height >= 10:
        detail_height = min(7, max(4, height // 3))
    list_height = max(1, height - detail_height)
    lines = _build_list(state, width, list_height)
    if detail_height:
        lines = lines + _build_inspector(state, width, detail_height)
    return lines


def _build_two_pane(state, width, height):
    """Wide terminals get the list and the inspector side by side."""
    side = TWO_PANE_SIDE_WIDTH
    main_width = width - side - 1
    left = _build_list(state, main_width, height)
    right = _build_inspector(state, side, height)
    lines = []
    for index in range(height):
        left_line = left[index] if index < len(left) else []
        right_line = right[index] if index < len(right) else []
        used = display_width(spans_to_text(left_line))
        lines.append(
            fit_spans(left_line, main_width)
            + [(" " * max(1, main_width - used + 1), "default")]
            + right_line
        )
    return lines


def _build_stats(state, width, height):
    """A compact breakdown of the rows currently visible."""
    glyphs = state.glyphs
    by_status = {}
    by_project = {}
    by_type = {}
    for row in state.rows:
        by_status[row.get("status") or "?"] = (
            by_status.get(row.get("status") or "?", 0) + 1
        )
        by_type[row.get("type") or "?"] = by_type.get(row.get("type") or "?", 0) + 1
        project = row_project(row) or "(none)"
        by_project[project] = by_project.get(project, 0) + 1

    lines = [
        [("  ", "default"), ("STATS", "section"), (" (visible rows)", "hint")],
        [("", "default")],
    ]
    lines.append(
        [
            ("  ", "default"),
            ("total ", "detail_key"),
            (str(len(state.rows)), "detail_value"),
        ]
    )
    lines.append([("", "default")])
    for title, table in (
        ("by status", by_status),
        ("by type", by_type),
        ("by project", by_project),
    ):
        lines.append([("  ", "default"), (title, "panel_title")])
        for key, count in sorted(table.items(), key=lambda pair: (-pair[1], pair[0]))[
            :10
        ]:
            bar_width = max(0, min(30, int(count * 30.0 / max(1, len(state.rows)))))
            lines.append(
                [
                    ("    ", "default"),
                    (pad(fit(str(key), 22, glyphs), 24), "detail_key"),
                    (pad(str(count), 5), "detail_value"),
                    (glyphs["h"] * bar_width, "chrome"),
                ]
            )
        lines.append([("", "default")])
    lines.append([("  ", "default"), ("/stats closes this panel.", "hint")])
    while len(lines) < height:
        lines.append([("", "default")])
    return lines[:height]


def _build_list(state, width, height):
    glyphs = state.glyphs
    if not state.rows:
        return _empty_state(state, width, height)

    entries = list_entries(state.rows, state.hidden)
    selected_entry = _entry_index_for_row(entries, state.selected)
    state.scroll = _clamp_scroll(state.scroll, selected_entry, len(entries), height)

    query = state.effective_query
    lines = []
    for entry in entries[state.scroll : state.scroll + height]:
        if entry["kind"] == "header":
            label = entry["label"].upper()
            hidden = state.hidden.get(entry["section"], 0)
            # The trailing "+N more" row can scroll out of view on a short
            # screen, so the count also rides on the always-visible header.
            shown = sum(
                1 for row in state.rows if row.get("section") == entry["section"]
            )
            count = " %d/%d" % (shown, shown + hidden) if hidden else ""
            rule = max(0, width - display_width(label) - display_width(count) - 5)
            lines.append(
                [
                    ("  ", "default"),
                    (label, "section"),
                    (count, "counter_warn" if hidden else "meta"),
                    (" " + glyphs["h"] * rule, "chrome"),
                ]
            )
            continue
        if entry["kind"] == "more":
            lines.append(
                [
                    ("    ", "default"),
                    (
                        "%s %d more hidden by limit:%s - raise with /limit N"
                        % (
                            glyphs["ellipsis"],
                            entry["count"],
                            state.options.get("limit"),
                        ),
                        "hint",
                    ),
                ]
            )
            continue
        lines.append(
            _row_line(
                state, entry["row"], entry["index"] == state.selected, width, query
            )
        )
    while len(lines) < height:
        lines.append([("", "default")])
    return lines


def _row_line(state, row, selected, width, query):
    glyphs = state.glyphs
    marked = row_key(row) in state.marked
    status = row.get("status", "")
    if status == "[x]":
        status_glyph, status_style = glyphs["done"], "status_done"
    elif status == "[/]":
        status_glyph, status_style = glyphs["active"], "status_active"
    elif status == "[-]":
        status_glyph, status_style = glyphs["blocked"], "status_open"
    else:
        status_glyph, status_style = glyphs["open"], "status_open"

    base_style = "row_selected" if selected else "row"
    spans = [
        (
            glyphs["cursor"] + " " if selected else "  ",
            "row_selected" if selected else "default",
        ),
        (glyphs["marked"] + " " if marked else "  ", "marked" if marked else "default"),
        (status_glyph + " ", status_style),
    ]

    meta = _row_meta(state, row, width)
    meta_width = display_width(spans_to_text(meta))
    used = display_width(spans_to_text(spans))
    title_width = max(8, width - used - meta_width - 2)
    title = fit(row.get("title") or "(untitled)", title_width, glyphs)

    match = score_row(query, row) if query else None
    if match and match[1]:
        spans.extend(highlight_spans(title, match[1], base_style))
    else:
        spans.append((title, base_style))
    spans.append((" " * max(1, title_width - display_width(title) + 1), "default"))
    spans.extend(meta)
    return spans


# Meta cells are fixed width so that columns line up across rows even when a
# record is missing a project, due date, or priority.
META_COLUMNS = (("project", 14), ("due", 18), ("priority", 10))


def meta_columns_for_width(width):
    """Pick which meta columns fit next to the title at this terminal width."""
    if width >= 90:
        return META_COLUMNS
    if width >= 72:
        return META_COLUMNS[:2]
    if width >= 56:
        return META_COLUMNS[1:2]
    return ()


def _row_meta(state, row, width):
    glyphs = state.glyphs
    spans = []
    for name, column_width in meta_columns_for_width(width):
        if name == "project":
            spans.append(
                (
                    pad(
                        fit(row_project(row) or "", column_width - 1, glyphs),
                        column_width,
                    ),
                    "meta",
                )
            )
        elif name == "due":
            due = row_due(row)
            spans.append(
                (
                    pad(
                        fit("due " + str(due) if due else "", column_width - 1, glyphs),
                        column_width,
                    ),
                    "meta",
                )
            )
        else:
            priority = row_priority(row)
            label = "%s %s" % (glyphs["flag"], priority) if priority else ""
            spans.append(
                (
                    pad(fit(label, column_width - 1, glyphs), column_width),
                    "counter_warn",
                )
            )
    if row.get("blocked") and width >= 96:
        spans.append(("blocked ", "toast_error"))
    return spans


def list_entries(rows, hidden=None):
    """Group rows into section headers plus row entries for display."""
    hidden = hidden or {}
    entries = []
    current = None
    for index, row in enumerate(rows):
        section = row.get("section", "")
        if section != current:
            if current is not None and hidden.get(current):
                entries.append(
                    {"kind": "more", "section": current, "count": hidden[current]}
                )
            current = section
            entries.append({"kind": "header", "label": section, "section": section})
        entries.append({"kind": "row", "row": row, "index": index, "section": section})
    if current is not None and hidden.get(current):
        entries.append({"kind": "more", "section": current, "count": hidden[current]})
    return entries


def _entry_index_for_row(entries, row_index):
    for position, entry in enumerate(entries):
        if entry["kind"] == "row" and entry["index"] == row_index:
            return position
    return 0


def _clamp_scroll(scroll, selected_entry, total, height):
    scroll = max(0, min(int(scroll or 0), max(0, total - height)))
    if selected_entry < scroll:
        return selected_entry
    if selected_entry >= scroll + height:
        return max(0, selected_entry - height + 1)
    return scroll


def _empty_state(state, width, height):
    glyphs = state.glyphs
    if state.effective_query:
        headline = "No row matches %r." % state.effective_query
        hint = "Press Esc to clear the filter, or /clear to reset everything."
    elif state.project:
        headline = "No row in project:%s." % state.project
        hint = "Run /project with no value to clear the project filter."
    else:
        headline = "Nothing to show yet."
        hint = "Use /add TITLE to capture your first task."
    lines = [
        [("", "default")],
        [("  " + glyphs["bullet"] + " ", "empty"), (headline, "empty")],
        [("    ", "default"), (hint, "hint")],
    ]
    while len(lines) < height:
        lines.append([("", "default")])
    return lines


def _build_error(state, width, height):
    glyphs = state.glyphs
    lines = [
        [("  ", "default"), ("Could not load life.txt data.", "toast_error")],
        [("", "default")],
    ]
    for text in str(state.error).splitlines():
        lines.append(
            [("  ", "default"), (fit(text, width - 3, glyphs), "detail_value")]
        )
    lines.append([("", "default")])
    lines.append(
        [
            ("  ", "default"),
            ("Fix the file, then run /reload. Files auto-reload on change.", "hint"),
        ]
    )
    while len(lines) < height:
        lines.append([("", "default")])
    return lines


def _build_today(state, width, height):
    """The Today view: a read-only render of the shared Command Center.

    Grouping and every count/row come from ``state._today`` (built in
    ``WorkspaceState.load()`` by calling ``command_center()`` directly), so
    no due/blocked/waiting/next-action/inbox rule is duplicated here.
    """
    glyphs = state.glyphs
    today = state._today
    header = [("  ", "default"), ("TODAY", "section")]
    if today and today.get("reference_date"):
        header.append((" for %s" % today["reference_date"], "meta"))
    lines = [header]

    if today is None:
        lines.append([("", "default")])
        lines.append([("  ", "default"), ("Command center unavailable.", "hint")])
        while len(lines) < height:
            lines.append([("", "default")])
        return lines[:height]

    def item_row(ref):
        due = " due:%s" % ref["due"] if ref.get("due") else ""
        project = " @%s" % ref["project"] if ref.get("project") else ""
        title_width = max(
            10, width - 4 - display_width(due) - display_width(project) - 6
        )
        return [
            ("    ", "default"),
            (pad(fit(ref.get("status") or "", 3, glyphs), 4), "meta"),
            (fit(ref.get("title") or "(untitled)", title_width, glyphs), "row"),
            (project, "meta"),
            (due, "meta"),
        ]

    def section(title, rows, empty_hint=None):
        rows = rows or []
        lines.append([("", "default")])
        lines.append(
            [
                ("  ", "default"),
                (title, "section"),
                (" (%d)" % len(rows), "meta"),
            ]
        )
        if not rows:
            if empty_hint:
                lines.append([("    ", "default"), (empty_hint, "hint")])
            return
        for row in rows[:TODAY_SECTION_LIMIT]:
            lines.append(item_row(row))
        if len(rows) > TODAY_SECTION_LIMIT:
            lines.append(
                [
                    ("    ", "default"),
                    ("... and %d more" % (len(rows) - TODAY_SECTION_LIMIT), "hint"),
                ]
            )

    lines.append([("  ", "default"), ("NOW", "panel_title")])
    section("Due today", today.get("due_today"), "Nothing due today.")
    section("Next actions", today.get("next_actions"), "Nothing actionable.")
    section("Overdue", today.get("overdue"), "Nothing overdue.")

    lines.append([("", "default")])
    lines.append([("  ", "default"), ("ATTENTION", "panel_title")])
    section("Blocked", today.get("blocked"), "Nothing blocked.")
    section("Waiting", today.get("waiting"), "Nothing waiting.")
    section("Projects", today.get("project_attention"), "All projects green.")

    lines.append([("", "default")])
    lines.append([("  ", "default"), ("INBOX", "panel_title")])
    inbox = today.get("inbox") or {}
    pending = inbox.get("pending") or []
    lines.append(
        [
            ("", "default"),
            (
                "  Unified Inbox (%d pending" % inbox.get("pending_count", 0),
                "section",
            ),
            (
                ", %d deferred)" % inbox.get("deferred_count", 0)
                if inbox.get("deferred_count")
                else ")",
                "section",
            ),
        ]
    )
    if not pending:
        lines.append([("    ", "default"), ("Inbox is empty.", "hint")])
    else:
        for proposal in pending[:TODAY_SECTION_LIMIT]:
            summary_width = max(10, width - 6 - 16)
            lines.append(
                [
                    ("    ", "default"),
                    (
                        fit(
                            proposal.get("summary") or proposal.get("id") or "",
                            summary_width,
                            glyphs,
                        ),
                        "row",
                    ),
                    ("  ", "default"),
                    (str(proposal.get("source") or ""), "meta"),
                ]
            )

    lines.append([("", "default")])
    lines.append([("  ", "default"), ("UPCOMING", "panel_title")])
    section(
        "Upcoming (%dd)" % today.get("horizon_days", 0),
        today.get("upcoming"),
        "Nothing upcoming.",
    )
    section("Habits", today.get("habits"), "No open habits.")

    while len(lines) < height:
        lines.append([("", "default")])
    return lines[:height]


def _build_inspector(state, width, height):
    glyphs = state.glyphs
    inner = width - 2
    row = state.selected_row()
    lines = [
        [
            (glyphs["tl"] + glyphs["h"], "chrome"),
            (" selection ", "panel_title"),
            (glyphs["h"] * max(0, inner - 12) + glyphs["tr"], "chrome"),
        ]
    ]
    content = []
    if not row:
        content.append([("no row selected", "hint")])
    else:
        content.append(
            [(fit(row.get("title") or "(untitled)", inner - 2, glyphs), "row_selected")]
        )
        meta = []
        for key in (
            "id",
            "project",
            "due",
            "do",
            "priority",
            "assignee",
            "tag",
            "state",
        ):
            value = row.get("id") if key == "id" else row_detail(row, key)
            if value:
                meta.append((key, str(value)))
        for key, label in (("file", "file"), ("dir", "dir")):
            for value in (row.get("details") or {}).get(key) or []:
                meta.append((label, _attachment_label(value)))
        if row.get("source"):
            location = os.path.basename(row["source"])
            if row.get("line"):
                location += ":%s" % row["line"]
            meta.append(("at", location))
        if inner < 60:
            # A narrow side pane cannot fit the fields on one line, and
            # clipping would hide values entirely, so stack them.
            for key, value in meta:
                content.append(
                    [
                        (pad(key, 10), "detail_key"),
                        (fit(value, inner - 13, glyphs), "detail_value"),
                    ]
                )
        else:
            meta_spans = []
            for key, value in meta:
                meta_spans.append((key + " ", "detail_key"))
                meta_spans.append((value + "   ", "detail_value"))
            if meta_spans:
                content.append(meta_spans)
        body = (row.get("details") or {}).get("body") or []
        for value in body:
            for text in str(value).splitlines():
                content.append([(fit(text, inner - 2, glyphs), "detail_value")])
    for line in content[: height - 2]:
        lines.append(_panel_row(glyphs, line, inner))
    while len(lines) < height - 1:
        lines.append(_panel_row(glyphs, [], inner))
    lines.append([(glyphs["bl"] + glyphs["h"] * inner + glyphs["br"], "chrome")])
    return lines[:height]


def _attachment_label(value):
    """Show the path without the hash fragment, which is noise in a panel."""
    from .attachments import AttachmentError, split_value

    try:
        path, _digest = split_value(value)
    except AttachmentError:
        return str(value)
    return path


def _panel_row(glyphs, spans, inner):
    """Wrap content in the panel borders, padding so the right edge lines up."""
    spans = fit_spans(spans, inner - 2)
    filler = inner - 2 - display_width(spans_to_text(spans))
    return (
        [(glyphs["v"] + " ", "chrome")]
        + list(spans)
        + [(" " * max(0, filler) + " ", "default"), (glyphs["v"], "chrome")]
    )


def _build_footer(state, width):
    glyphs = state.glyphs
    inner = width - 2
    lines = []

    if state.toast and not state.toast.expired():
        style = {"success": "toast_success", "error": "toast_error"}.get(
            state.toast.level, "toast_info"
        )
        lines.append(
            [("  ", "default"), (fit(state.toast.text, width - 3, glyphs), style)]
        )
    else:
        lines.append([("", "default")])

    prefix = glyphs["prompt"]
    placeholder = "" if state.input else _placeholder(state)
    lines.append([(glyphs["tl"] + glyphs["h"] * inner + glyphs["tr"], "chrome")])
    lines.append(
        _panel_row(
            glyphs,
            [
                (prefix + " ", "input_prefix"),
                (state.input, "input") if state.input else (placeholder, "hint"),
            ],
            inner,
        )
    )
    lines.append([(glyphs["bl"] + glyphs["h"] * inner + glyphs["br"], "chrome")])

    if state.palette_open:
        lines.extend(_build_palette(state, width))
    lines.append(_hint_line(state, width))
    return lines


def _placeholder(state):
    if state.mode == "nav":
        return "press / to filter, : for a command, ? for help"
    return "type to filter, / for commands, ? for help"


def _build_argument_palette(state, width, prefix, values):
    """List the values for the argument being typed."""
    glyphs = state.glyphs
    state.palette_index = max(0, min(state.palette_index, len(values) - 1))
    size = max(1, min(6, len(values)))
    start = max(0, min(state.palette_index - size + 1, len(values) - size))
    start = min(start, state.palette_index)

    lines = []
    for offset, value in enumerate(values[start : start + size]):
        index = start + offset
        active = index == state.palette_index
        style = "palette_active" if active else "palette"
        spans = [(glyphs["cursor"] + " " if active else "  ", style)]
        # The typed part is highlighted so it is obvious what is being matched.
        matched = len(prefix) if value.lower().startswith(prefix.lower()) else 0
        spans.extend(highlight_spans(value, list(range(matched)), style))
        lines.append(spans)

    if len(values) > size:
        lines.append([("  ", "default"), ("%d more" % (len(values) - size), "hint")])
    return lines


def _build_palette(state, width):
    glyphs = state.glyphs

    prefix, values = argument_suggestions(state, state.input)
    if values:
        return _build_argument_palette(state, width, prefix, values)

    suggestions = command_suggestions(state.input)
    if not suggestions:
        return [[("  ", "default"), ("no matching command", "hint")]]
    state.palette_index = max(0, min(state.palette_index, len(suggestions) - 1))
    # Scroll the window so the highlighted entry is always on screen.
    size = max(1, min(6, len(suggestions)))
    start = max(0, min(state.palette_index - size + 1, len(suggestions) - size))
    start = min(start, state.palette_index)
    window = suggestions[start : start + size]
    lines = []
    for offset, (command, indices) in enumerate(window):
        index = start + offset
        active = index == state.palette_index
        name_spans = highlight_spans(
            "/" + command.name,
            [position + 1 for position in indices],
            "palette_active" if active else "palette",
        )
        usage = (" " + command.usage) if command.usage else ""
        label_width = display_width(spans_to_text(name_spans)) + display_width(usage)
        spans = [
            (
                glyphs["cursor"] + " " if active else "  ",
                "palette_active" if active else "default",
            )
        ]
        spans.extend(name_spans)
        spans.append((usage, "palette_hint"))
        spans.append((" " * max(2, 28 - label_width), "default"))
        spans.append((fit(command.summary, max(10, width - 34), glyphs), "hint"))
        lines.append(spans)
    return lines


def _hint_line(state, width):
    glyphs = state.glyphs
    if state.show_help:
        pairs = [("?", "close help"), ("q", "quit")]
    elif state.palette_open:
        pairs = [("tab", "complete"), ("enter", "run"), ("esc", "cancel")]
    elif state.mode == "nav":
        pairs = [
            ("j/k", "move"),
            ("space", "mark"),
            ("enter", "inspect"),
            ("d", "done"),
            ("e", "edit"),
            ("u", "undo"),
            ("/", "filter"),
            (":", "command"),
            ("?", "help"),
            ("q", "quit"),
        ]
    else:
        pairs = [
            ("up/down", "move"),
            ("ctrl-t", "mark"),
            ("enter", "apply"),
            ("/", "commands"),
            ("esc", "clear"),
            ("ctrl-c", "quit"),
        ]
    spans = [("  ", "default")]
    for key, label in pairs:
        if display_width(spans_to_text(spans)) + len(key) + len(label) + 4 > width:
            break
        spans.append((key, "key"))
        spans.append((" " + label + "   ", "hint"))
    return spans


def _build_help(state, width, height):
    glyphs = state.glyphs
    entries = help_entries(state.help_query)
    header = [("  ", "default"), ("COMMANDS", "section")]
    if state.help_query:
        header.append((" matching %r " % state.help_query, "match"))
        header.append(("(/help with no query shows all)", "hint"))
    lines = [header]
    for usage, summary in entries:
        lines.append(
            [
                ("    ", "default"),
                (pad(fit(usage, 34, glyphs), 36), "palette"),
                (fit(summary, max(10, width - 42), glyphs), "hint"),
            ]
        )
    if state.help_query:
        lines.append([("", "default")])
        lines.append([("  ", "default"), ("Press ? or Esc to close help.", "hint")])
        while len(lines) < height:
            lines.append([("", "default")])
        return lines[:height]
    lines.append([("", "default")])
    lines.append([("  ", "default"), ("KEYS", "section")])
    for key, label in _key_reference(state):
        lines.append(
            [
                ("    ", "default"),
                (pad(key, 36), "key"),
                (fit(label, max(10, width - 42), glyphs), "hint"),
            ]
        )
    lines.append([("", "default")])
    lines.append(
        [
            ("  ", "default"),
            ("keymap ", "detail_key"),
            (state.keymap + "   ", "detail_value"),
            ("theme ", "detail_key"),
            (str(state.options.get("theme")) + "   ", "detail_value"),
            ("sort ", "detail_key"),
            (state.sort, "detail_value"),
        ]
    )
    return _scroll_help(state, lines, height)


def _scroll_help(state, lines, height):
    """The reference is longer than one screen, so it scrolls like the list."""
    body = max(1, height - 1)
    state.help_scroll = max(0, min(state.help_scroll, max(0, len(lines) - body)))
    visible = lines[state.help_scroll : state.help_scroll + body]
    while len(visible) < body:
        visible.append([("", "default")])
    more = len(lines) - state.help_scroll - body
    if more > 0:
        visible.append(
            [
                ("  ", "default"),
                ("%d more line(s) below - up/down to scroll" % more, "hint"),
            ]
        )
    elif state.help_scroll:
        visible.append([("  ", "default"), ("up/down to scroll", "hint")])
    else:
        visible.append([("", "default")])
    return visible[:height]


def _key_reference(state):
    shared = [
        ("up / down", "move the selection"),
        ("pgup / pgdn", "move half a page"),
        ("home / end", "jump to the first or last row"),
        ("tab", "complete the highlighted command"),
        ("enter", "apply the filter or run the command"),
        ("esc", "clear the input, then the filters"),
        ("ctrl-t", "mark or unmark the selected row"),
        ("ctrl-p / ctrl-n", "recall the previous or next input"),
        ("ctrl-a / ctrl-e", "jump to the start or end of the input"),
        ("ctrl-u / ctrl-k", "delete before or after the cursor"),
        ("ctrl-c", "quit"),
    ]
    if state.keymap == "prompt":
        return shared
    return _effective_binding_rows(state) + shared


def _effective_binding_rows(state):
    """Render the resolved nav-mode bindings (#595): help text generated
    from `state.key_bindings` can never lie after a `tui.bindings`
    customization, because it is not a second, separately maintained copy
    of the default key list.
    """
    from .tui_bindings import ACTION_LABELS, display_key

    def keys_for(action):
        keys = (getattr(state, "key_bindings", None) or {}).get(action) or ()
        return " / ".join(display_key(key) for key in keys) or "(unbound)"

    rows = [(keys_for(action), label) for action, label in ACTION_LABELS.items()]
    # e (edit) and u (undo) stay outside the configurable registry (#595
    # scope: RESERVED_KEYS), so they are documented here directly rather
    # than through the dynamic action-label loop above.
    rows.append(("e / u", "edit, undo"))
    return rows


# ---------------------------------------------------------------------------
# key handling
# ---------------------------------------------------------------------------


def normalize_key(curses_module, key):
    """Translate a curses key code into a stable name used by handle_key."""
    specials = {
        getattr(curses_module, "KEY_UP", -101): "up",
        getattr(curses_module, "KEY_DOWN", -102): "down",
        getattr(curses_module, "KEY_LEFT", -103): "left",
        getattr(curses_module, "KEY_RIGHT", -104): "right",
        getattr(curses_module, "KEY_HOME", -105): "home",
        getattr(curses_module, "KEY_END", -106): "end",
        getattr(curses_module, "KEY_NPAGE", -107): "pgdn",
        getattr(curses_module, "KEY_PPAGE", -108): "pgup",
        getattr(curses_module, "KEY_BACKSPACE", -109): "backspace",
        getattr(curses_module, "KEY_ENTER", -110): "enter",
        getattr(curses_module, "KEY_RESIZE", -111): "resize",
        getattr(curses_module, "KEY_DC", -112): "delete",
    }
    if key in specials:
        return specials[key]
    if key in (10, 13):
        return "enter"
    if key == 9:
        return "tab"
    if key == 27:
        return "escape"
    if key in (8, 127):
        return "backspace"
    if 1 <= key <= 26:
        return "ctrl-" + chr(ord("a") + key - 1)
    if 32 <= key < 0x110000:
        try:
            return chr(key)
        except ValueError:
            return ""
    return ""


def handle_key(state, key, page=5):
    """Apply one normalized key to the state. Returns True when handled."""
    if not key:
        return False
    if key == "resize":
        return True
    if key == "ctrl-c":
        state.running = False
        return True

    if state.show_help:
        if key in ("?", "escape", "q", "enter"):
            state.show_help = False
            state.help_query = ""
            state.help_scroll = 0
            _leave_input_mode(state)
            return True
        if key in ("down", "j", "ctrl-n"):
            state.help_scroll += 1
            return True
        if key in ("up", "k", "ctrl-p"):
            state.help_scroll = max(0, state.help_scroll - 1)
            return True
        if key in ("pgdn", "ctrl-d"):
            state.help_scroll += page
            return True
        if key in ("pgup", "ctrl-u"):
            state.help_scroll = max(0, state.help_scroll - page)
            return True
        if key in ("g", "home"):
            state.help_scroll = 0
            return True
        return True

    if state.mode == "nav":
        return _handle_nav_key(state, key, page)
    return _handle_input_key(state, key, page)


def _action_move_up(state, page):
    _move(state, -1)
    return True


def _action_move_down(state, page):
    _move(state, 1)
    return True


def _action_first(state, page):
    state.selected = 0
    state.scroll = 0
    return True


def _action_last(state, page):
    state.selected = max(0, len(state.rows) - 1)
    return True


def _action_open(state, page):
    state.show_detail = not state.show_detail
    return True


def _action_toggle_mark(state, page):
    _safe_command(state, "/mark toggle")
    return True


def _action_done(state, page):
    _safe_command(state, "/done")
    return True


def _action_search(state, page):
    state.mode = "input"
    state.input = ""
    state.cursor = 0
    return True


def _action_command(state, page):
    state.mode = "input"
    state.input = "/"
    state.cursor = 1
    state.palette_index = 0
    return True


def _action_reload(state, page):
    _safe_command(state, "/reload")
    return True


def _action_help(state, page):
    state.show_help = not state.show_help
    return True


def _action_quit(state, page):
    state.running = False
    return True


#: Action id -> handler(state, page) -> bool. Each handler reproduces
#: exactly the behavior `_handle_nav_key` hard-coded before #595; the
#: registry only decides which physical key reaches which handler, it does
#: not change what any action does. Handlers themselves are not part of
#: `lifetxt.tui_bindings`, which stays protocol-neutral (key/action names
#: only) and has no dependency on curses or WorkspaceState.
_ACTION_HANDLERS = {
    "move_up": _action_move_up,
    "move_down": _action_move_down,
    "first": _action_first,
    "last": _action_last,
    "open": _action_open,
    "toggle_mark": _action_toggle_mark,
    "done": _action_done,
    "search": _action_search,
    "command": _action_command,
    "reload": _action_reload,
    "help": _action_help,
    "quit": _action_quit,
}


def _resolve_bindings_or_fallback(keymap, overrides):
    from .tui_bindings import resolve_bindings

    try:
        return resolve_bindings(keymap, overrides)
    except ValueError:
        return resolve_bindings(keymap, None)


def _handle_nav_key(state, key, page):
    action = (getattr(state, "action_by_key", None) or {}).get(key)
    if action is not None:
        handler = _ACTION_HANDLERS.get(action)
        if handler is not None:
            return handler(state, page)

    # Keys outside the configurable action registry (lifetxt/tui_bindings.py
    # RESERVED_KEYS) stay exactly as before: page moves, edit/undo, the
    # view-cycle key, and the required cancel path are never remappable.
    if key in ("pgdn", "ctrl-d"):
        _move(state, page)
        return True
    if key in ("pgup", "ctrl-u"):
        _move(state, -page)
        return True
    if key == "tab":
        index = (
            WORKSPACE_VIEWS.index(state.view) if state.view in WORKSPACE_VIEWS else 0
        )
        _safe_command(
            state, "/view " + WORKSPACE_VIEWS[(index + 1) % len(WORKSPACE_VIEWS)]
        )
        return True
    if key in ("e", "u"):
        _safe_command(state, {"e": "/edit", "u": "/undo"}[key])
        return True
    if key == "escape":
        if state.query or state.project or state.marked:
            _safe_command(state, "/clear")
        return True
    return False


def _handle_input_key(state, key, page):
    if key == "escape":
        if state.input:
            state.input = ""
            state.cursor = 0
            state.palette_index = 0
        elif state.query or state.project or state.marked:
            _safe_command(state, "/clear")
        else:
            _leave_input_mode(state)
        return True
    if key == "enter":
        _submit(state)
        return True
    if key == "tab":
        if state.palette_open:
            # Past the command name, Tab completes the value being typed
            # rather than re-completing the name that is already there.
            if apply_argument_completion(state):
                return True
            suggestions = command_suggestions(state.input)
            if suggestions:
                command = suggestions[state.palette_index][0]
                state.input = "/" + command.name + (" " if command.usage else "")
                state.cursor = len(state.input)
        return True
    if key == "backspace":
        if state.cursor > 0:
            state.input = state.input[: state.cursor - 1] + state.input[state.cursor :]
            state.cursor -= 1
            state.palette_index = 0
        return True
    if key == "delete":
        state.input = state.input[: state.cursor] + state.input[state.cursor + 1 :]
        return True
    if key == "left":
        state.cursor = max(0, state.cursor - 1)
        return True
    if key == "right":
        state.cursor = min(len(state.input), state.cursor + 1)
        return True
    if key == "ctrl-a":
        state.cursor = 0
        return True
    if key == "ctrl-e":
        state.cursor = len(state.input)
        return True
    if key == "ctrl-u":
        state.input = state.input[state.cursor :]
        state.cursor = 0
        return True
    if key == "ctrl-k":
        state.input = state.input[: state.cursor]
        return True
    if key == "ctrl-t":
        _safe_command(state, "/mark toggle")
        return True
    if key in ("ctrl-p", "ctrl-n"):
        _recall_history(state, -1 if key == "ctrl-p" else 1)
        return True
    if key in ("up", "down"):
        if state.palette_open:
            delta = -1 if key == "up" else 1
            _, argument_values = argument_suggestions(state, state.input)
            options = argument_values or [
                entry[0] for entry in command_suggestions(state.input)
            ]
            if options:
                state.palette_index = max(
                    0, min(state.palette_index + delta, len(options) - 1)
                )
        else:
            _move(state, -1 if key == "up" else 1)
        return True
    if key in ("pgup", "pgdn"):
        _move(state, -page if key == "pgup" else page)
        return True
    if key == "home":
        state.selected = 0
        state.scroll = 0
        return True
    if key == "end":
        state.selected = max(0, len(state.rows) - 1)
        return True
    if key == "?" and not state.input:
        state.show_help = not state.show_help
        return True
    if len(key) == 1:
        state.input = state.input[: state.cursor] + key + state.input[state.cursor :]
        state.cursor += 1
        state.palette_index = 0
        state.selected = 0
        state.scroll = 0
        return True
    return False


def _move(state, delta):
    if not state.rows:
        state.selected = 0
        return
    state.selected = max(0, min(state.selected + delta, len(state.rows) - 1))


def _submit(state):
    text = state.input
    if not text:
        state.show_detail = not state.show_detail
        return
    state.history.append(text)
    del state.history[:-50]
    state.history_index = None
    if text.startswith("/"):
        suggestions = command_suggestions(text)
        name = text[1:].split(" ", 1)[0].lower()
        if name not in COMMANDS_BY_NAME and suggestions:
            chosen = suggestions[state.palette_index][0]
            _, _, argument = text[1:].partition(" ")
            text = "/" + chosen.name + ((" " + argument) if argument else "")
        state.input = ""
        state.cursor = 0
        state.palette_index = 0
        _safe_command(state, text)
        _leave_input_mode(state)
        return
    state.query = text
    state.input = ""
    state.cursor = 0
    state.selected = 0
    state.scroll = 0
    state.notify("Search: %s" % text)
    _leave_input_mode(state)


def _leave_input_mode(state):
    """Return to nav mode after a one-shot `/` or `:` entry.

    Only the prompt keymap keeps the input bar focused permanently. In the vim
    and arrows keymaps the input bar is entered for a single search or command
    and must hand control back, the way `:cmd<Enter>` returns to normal mode.
    """
    if state.keymap != "prompt":
        state.mode = "nav"
        state.palette_index = 0


def _recall_history(state, delta):
    if not state.history:
        return
    if state.history_index is None:
        state.history_index = len(state.history)
    state.history_index = max(0, min(state.history_index + delta, len(state.history)))
    if state.history_index >= len(state.history):
        state.input = ""
    else:
        state.input = state.history[state.history_index]
    state.cursor = len(state.input)


def _safe_command(state, text):
    try:
        level, message = run_command(state, text)
        state.notify(message, level)
    except Exception as exc:
        state.notify(str(exc), "error")


# ---------------------------------------------------------------------------
# curses runner
# ---------------------------------------------------------------------------


def run_workspace(args):
    import curses

    from .tui import FileChangeWatcher

    watcher = FileChangeWatcher(getattr(args, "paths", []) or []).start()

    @contextlib.contextmanager
    def suspend(stdscr):
        """Hand the terminal back to a child process, then reclaim it."""
        curses.def_prog_mode()
        curses.endwin()
        try:
            yield
        finally:
            curses.reset_prog_mode()
            stdscr.redrawwin()
            stdscr.refresh()

    def main(stdscr):
        state = WorkspaceState(args)
        state.suspend = lambda: suspend(stdscr)
        color_attrs = init_colors(curses, state.options.get("theme", "auto"))
        stdscr.timeout(int(WORKSPACE_POLL_SECONDS * 1000))
        try:
            curses.curs_set(1)
        except Exception:
            pass
        load_session(state)
        state.reload()
        theme = state.options.get("theme", "auto")
        dirty = True
        while state.running:
            if watcher.consume_changed():
                state.load()
                dirty = True
            if dirty:
                if state.options.get("theme", "auto") != theme:
                    theme = state.options.get("theme", "auto")
                    color_attrs = init_colors(curses, theme)
                height, width = stdscr.getmaxyx()
                # Only refresh() here: re-parsing every file on each keystroke
                # would make live filtering unusable on large files.
                state.refresh()
                frame = build_frame(state, width, height)
                stdscr.erase()
                draw_frame(stdscr, frame, color_attrs)
                _place_cursor(stdscr, state, frame, width, height)
                stdscr.refresh()
                dirty = False
            try:
                key = stdscr.getch()
            except KeyboardInterrupt:
                # curses.wrapper uses cbreak(), which leaves ISIG enabled, so
                # Ctrl-C arrives as SIGINT rather than as key code 3. Treat it
                # as the quit key instead of unwinding with a traceback.
                state.running = False
                continue
            if key == -1:
                if state.toast and state.toast.expired():
                    state.toast = None
                    dirty = True
                continue
            height, _width = stdscr.getmaxyx()
            name = normalize_key(curses, key)
            if handle_key(state, name, page=max(1, height // 2)):
                dirty = True
        save_session(state)

    try:
        curses.wrapper(main)
    except KeyboardInterrupt:
        # A SIGINT delivered outside getch() (during a redraw, say) must still
        # leave the terminal restored and exit quietly.
        pass
    except curses.error as exc:
        # curses imports on Linux even with no terminal attached, so a failure
        # here means the terminal cannot drive it. Fall back to plain output.
        from .tui import render_dashboard_safe

        sys.stderr.write("Falling back to plain output: %s\n" % exc)
        sys.stdout.write(render_dashboard_safe(args))
    finally:
        watcher.stop()
    return 0


def draw_frame(stdscr, frame, color_attrs=None):
    height, width = stdscr.getmaxyx()
    max_columns = max(0, width - 1)
    for row, line in enumerate(frame):
        if row >= height:
            break
        column = 0
        for text, style in line:
            if column >= max_columns:
                break
            text = _clip_display_width(text, max_columns - column)
            if not text:
                continue
            _addstr(stdscr, row, column, text, (color_attrs or {}).get(style, 0))
            column += display_width(text)


def _addstr(stdscr, row, column, text, attr=0):
    try:
        if attr:
            stdscr.addstr(row, column, text, attr)
        else:
            stdscr.addstr(row, column, text)
    except TypeError:
        try:
            stdscr.addstr(row, column, text)
        except Exception:
            pass
    except Exception:
        # curses raises when writing the last cell of the screen; the frame is
        # best effort, so never let drawing kill the session.
        pass


def _place_cursor(stdscr, state, frame, width, height):
    prompt_row = _prompt_row_index(state, frame)
    if prompt_row is None:
        return
    offset = 4 + display_width(state.input[: state.cursor])
    try:
        stdscr.move(min(height - 1, prompt_row), min(max(0, width - 1), offset))
    except Exception:
        pass


def _prompt_row_index(state, frame):
    """Find the input line by its unique style rather than by its text."""
    for index in range(len(frame) - 1, -1, -1):
        if any(style == "input_prefix" for _text, style in frame[index]):
            return index
    return None


def init_colors(curses_module, theme="auto"):
    """Build a style -> curses attribute map for the workspace palette."""
    attrs = dict((style, 0) for style in STYLES)
    try:
        attrs["brand"] = curses_module.A_BOLD
        attrs["section"] = curses_module.A_BOLD
        attrs["row_selected"] = curses_module.A_BOLD
        attrs["tab_active"] = curses_module.A_BOLD
        attrs["key"] = curses_module.A_BOLD
        attrs["panel_title"] = curses_module.A_BOLD
        attrs["palette_active"] = curses_module.A_BOLD
        attrs["hint"] = curses_module.A_DIM
        attrs["meta"] = curses_module.A_DIM
        attrs["chrome"] = curses_module.A_DIM
        attrs["tagline"] = curses_module.A_DIM
        attrs["empty"] = curses_module.A_DIM
        attrs["match"] = curses_module.A_BOLD | curses_module.A_UNDERLINE
        attrs["toast_error"] = curses_module.A_BOLD
        if theme == "mono" or not curses_module.has_colors():
            return attrs
        curses_module.start_color()
        background = -1
        try:
            curses_module.use_default_colors()
        except Exception:
            background = curses_module.COLOR_BLACK
        if theme == "light":
            palette = (
                ("brand", curses_module.COLOR_BLUE),
                ("tagline", curses_module.COLOR_BLACK),
                ("chrome", curses_module.COLOR_BLUE),
                ("counter", curses_module.COLOR_BLUE),
                ("counter_warn", curses_module.COLOR_RED),
                ("tab", curses_module.COLOR_BLACK),
                ("tab_active", curses_module.COLOR_MAGENTA),
                ("section", curses_module.COLOR_BLUE),
                ("row_selected", curses_module.COLOR_MAGENTA),
                ("status_open", curses_module.COLOR_BLACK),
                ("status_active", curses_module.COLOR_BLUE),
                ("status_done", curses_module.COLOR_GREEN),
                ("meta", curses_module.COLOR_BLUE),
                ("match", curses_module.COLOR_MAGENTA),
                ("marked", curses_module.COLOR_MAGENTA),
                ("input_prefix", curses_module.COLOR_MAGENTA),
                ("palette", curses_module.COLOR_BLUE),
                ("palette_active", curses_module.COLOR_MAGENTA),
                ("palette_hint", curses_module.COLOR_BLACK),
                ("hint", curses_module.COLOR_BLACK),
                ("key", curses_module.COLOR_BLUE),
                ("toast_info", curses_module.COLOR_BLUE),
                ("toast_success", curses_module.COLOR_GREEN),
                ("toast_error", curses_module.COLOR_RED),
                ("panel_title", curses_module.COLOR_BLUE),
                ("detail_key", curses_module.COLOR_BLACK),
                ("detail_value", curses_module.COLOR_BLUE),
                ("empty", curses_module.COLOR_BLACK),
            )
        else:
            palette = (
                ("brand", curses_module.COLOR_CYAN),
                ("tagline", curses_module.COLOR_WHITE),
                ("chrome", curses_module.COLOR_BLUE),
                ("counter", curses_module.COLOR_CYAN),
                ("counter_warn", curses_module.COLOR_YELLOW),
                ("tab", curses_module.COLOR_WHITE),
                ("tab_active", curses_module.COLOR_YELLOW),
                ("section", curses_module.COLOR_BLUE),
                ("row_selected", curses_module.COLOR_YELLOW),
                ("status_open", curses_module.COLOR_WHITE),
                ("status_active", curses_module.COLOR_CYAN),
                ("status_done", curses_module.COLOR_GREEN),
                ("meta", curses_module.COLOR_CYAN),
                ("match", curses_module.COLOR_YELLOW),
                ("marked", curses_module.COLOR_MAGENTA),
                ("input_prefix", curses_module.COLOR_CYAN),
                ("palette", curses_module.COLOR_CYAN),
                ("palette_active", curses_module.COLOR_YELLOW),
                ("palette_hint", curses_module.COLOR_WHITE),
                ("hint", curses_module.COLOR_WHITE),
                ("key", curses_module.COLOR_CYAN),
                ("toast_info", curses_module.COLOR_CYAN),
                ("toast_success", curses_module.COLOR_GREEN),
                ("toast_error", curses_module.COLOR_RED),
                ("panel_title", curses_module.COLOR_CYAN),
                ("detail_key", curses_module.COLOR_WHITE),
                ("detail_value", curses_module.COLOR_CYAN),
                ("empty", curses_module.COLOR_WHITE),
            )
        for index, (style, foreground) in enumerate(palette, 1):
            curses_module.init_pair(index, foreground, background)
            attrs[style] = curses_module.color_pair(index) | attrs.get(style, 0)
    except Exception:
        return dict((style, 0) for style in STYLES)
    return attrs
