import os
import sys
import threading
import unicodedata

from .agenda import agenda_records, filter_items, parse_agenda_range
from .config import config_section
from .ids import id_key_from_config
from .nextaction import ACTIONABLE_KINDS, blocked_map
from .parser import parse_text
from .serializer import item_to_line
from .status_summary import latest_status_records


TUI_SECTIONS = ("tasks", "agenda", "status")
TUI_POLL_SECONDS = 0.5
TUI_COLOR_STYLES = (
    "default",
    "title",
    "rule",
    "focus",
    "section",
    "open",
    "active",
    "done",
    "agenda",
    "status",
    "muted",
    "error",
    "footer",
    "help",
    "search",
    "inspector",
    "selected",
)
TUI_THEMES = ("auto", "dark", "light", "mono")
TUI_KEYMAPS = ("prompt", "vim", "arrows")
TUI_GLYPH_MODES = ("auto", "unicode", "ascii")
DEFAULT_TUI_LIMIT = 10
DEFAULT_TUI_AGENDA_WINDOW = "12h"


def cmd_tui(args):
    """Run the interactive workspace on a real terminal, plain text otherwise.

    The prompt-first workspace in ``lifetxt.tui_app`` is the primary interface.
    It needs a TTY and curses, so piping or redirecting `lifetxt tui` still
    produces the dependency-free dashboard snapshot below.
    """
    if getattr(args, "plain", False) or not _stdout_is_tty():
        sys.stdout.write(render_dashboard_safe(args))
        return 0
    try:
        import curses  # noqa: F401
    except ImportError:
        curses = None
    try:
        if curses is not None:
            from .tui_app import run_workspace

            return run_workspace(args)
        if _textual_available():
            return run_textual(args)
        return run_curses_or_plain(args)
    except KeyboardInterrupt:
        # Quitting with Ctrl-C is a normal way to leave a TUI, not a crash.
        return 0


def _stdout_is_tty():
    try:
        return bool(sys.stdout.isatty())
    except Exception:
        return False


def tui_options(args):
    config = getattr(args, "config_data", None) or {}
    tui_config = config_section(config, "tui")
    theme = getattr(args, "theme", None) or tui_config.get("theme") or "auto"
    keymap = getattr(args, "keymap", None) or tui_config.get("keymap") or "prompt"
    glyphs = getattr(args, "glyphs", None) or tui_config.get("glyphs") or "auto"
    limit = getattr(args, "limit", None) or tui_config.get("limit") or DEFAULT_TUI_LIMIT
    agenda_window = (
        getattr(args, "agenda_window", None)
        or tui_config.get("agenda_window")
        or DEFAULT_TUI_AGENDA_WINDOW
    )
    theme = str(theme).lower()
    keymap = str(keymap).lower()
    glyphs = str(glyphs).lower()
    if theme not in TUI_THEMES:
        theme = "auto"
    if keymap not in TUI_KEYMAPS:
        keymap = "prompt"
    if glyphs not in TUI_GLYPH_MODES:
        glyphs = "auto"
    try:
        limit = max(1, int(limit))
    except (TypeError, ValueError):
        limit = DEFAULT_TUI_LIMIT
    return {
        "theme": theme,
        "keymap": keymap,
        "glyphs": glyphs,
        "limit": limit,
        "agenda_window": str(agenda_window),
        "id_key": id_key_from_config(config),
    }


def run_textual(args):
    # Keep the Textual path deliberately small and optional. The curses/plain
    # fallback below remains the dependency-free implementation used in tests.
    try:
        from textual.app import App
        from textual.widgets import Static
    except ImportError:
        return run_curses_or_plain(args)

    watcher = FileChangeWatcher(args.paths).start()

    class LifeTxtApp(App):
        focus = "tasks"
        help_visible = False
        selected_index = 0
        detail_row = None
        project_filter = None
        search_query = ""

        def compose(self):
            self.dashboard = Static(
                render_dashboard_safe(
                    args,
                    focus=self.focus,
                    help_visible=self.help_visible,
                    selected_index=self.selected_index,
                    detail_row=self.detail_row,
                    project_filter=self.project_filter,
                    search_query=self.search_query,
                )
            )
            yield self.dashboard

        def on_mount(self):
            self.set_interval(TUI_POLL_SECONDS, self.refresh_if_changed)

        def on_unmount(self):
            watcher.stop()

        def refresh_if_changed(self):
            if watcher.consume_changed():
                self.refresh_dashboard()

        def refresh_dashboard(self):
            self.selected_index = normalize_selected_index(
                args,
                self.selected_index,
                self.project_filter,
                self.search_query,
            )
            self.dashboard.update(
                render_dashboard_safe(
                    args,
                    focus=self.focus,
                    help_visible=self.help_visible,
                    selected_index=self.selected_index,
                    detail_row=self.detail_row,
                    project_filter=self.project_filter,
                    search_query=self.search_query,
                )
            )

        def on_key(self, event):
            if event.key == "q":
                self.exit()
            elif event.key == "r":
                self.refresh_dashboard()
            elif event.key in ("question_mark", "H"):
                self.help_visible = not self.help_visible
                self.refresh_dashboard()
            elif event.key == "escape" and self.search_query:
                self.search_query = ""
                self.selected_index = 0
                self.detail_row = None
                self.refresh_dashboard()
            elif event.key in ("tab", "n", "l", "right"):
                self.focus = next_section(self.focus)
                self.selected_index = first_selectable_index_for_section(
                    args,
                    self.focus,
                    self.project_filter,
                    self.search_query,
                )
                self.detail_row = None
                self.refresh_dashboard()
            elif event.key in ("p", "h", "left"):
                self.focus = previous_section(self.focus)
                self.selected_index = first_selectable_index_for_section(
                    args,
                    self.focus,
                    self.project_filter,
                    self.search_query,
                )
                self.detail_row = None
                self.refresh_dashboard()
            elif event.key in ("j", "down"):
                self.selected_index = move_selection(
                    args, self.selected_index, 1, self.project_filter, self.search_query
                )
                self.detail_row = None
                self.refresh_dashboard()
            elif event.key in ("k", "up"):
                self.selected_index = move_selection(
                    args,
                    self.selected_index,
                    -1,
                    self.project_filter,
                    self.search_query,
                )
                self.detail_row = None
                self.refresh_dashboard()
            elif event.key in ("enter", "s"):
                self.detail_row = selected_dashboard_row(
                    args, self.selected_index, self.project_filter, self.search_query
                )
                self.refresh_dashboard()
            elif event.key == "f":
                row = selected_dashboard_row(
                    args, self.selected_index, self.project_filter, self.search_query
                )
                project = row_project(row)
                if project:
                    self.project_filter = (
                        project if self.project_filter != project else None
                    )
                    self.selected_index = 0
                    self.detail_row = None
                    self.search_query = ""
                    self.refresh_dashboard()
            elif event.key == "d":
                row = selected_dashboard_row(
                    args, self.selected_index, self.project_filter, self.search_query
                )
                try:
                    perform_row_action("done", row, args)
                    self.detail_row = {
                        "label": "Marked done: %s" % row.get("id", row.get("title", ""))
                    }
                except Exception as exc:
                    self.detail_row = {"label": "ERROR: %s" % exc}
                self.refresh_dashboard()

    try:
        LifeTxtApp().run()
    finally:
        watcher.stop()
    return 0


def run_curses_or_plain(args):
    try:
        import curses
    except ImportError:
        sys.stdout.write(render_dashboard(args))
        return 0

    # curses imports fine on Linux even with no terminal attached, but
    # initializing it without a TTY fails inside curses.wrapper (cbreak() and
    # then nocbreak() both raise). Check before touching curses rather than
    # relying on the import failing, which only happens on Windows.
    if not _stdout_is_tty():
        sys.stdout.write(render_dashboard_safe(args))
        return 0

    watcher = FileChangeWatcher(args.paths).start()

    def main(stdscr):
        stdscr.timeout(int(TUI_POLL_SECONDS * 1000))
        options = tui_options(args)
        color_attrs = _init_curses_colors(curses, options["theme"])
        focus = "tasks"
        scroll = 0
        selected_index = 0
        help_visible = False
        detail_row = None
        action_row = None
        project_filter = None
        search_query = ""
        search_editing = False
        message = ""
        dirty = True
        text = ""
        while True:
            if dirty or watcher.consume_changed():
                selected_index = normalize_selected_index(
                    args, selected_index, project_filter, search_query
                )
                focus = section_for_selected_index(
                    args, selected_index, focus, project_filter, search_query
                )
                stdscr.erase()
                text = render_dashboard_safe(
                    args,
                    focus=focus,
                    help_visible=help_visible,
                    selected_index=selected_index,
                    detail_row=detail_row,
                    action_row=action_row,
                    project_filter=project_filter,
                    search_query=search_query,
                    message=message,
                )
                scroll = _scroll_to_selected(text, selected_index, scroll, stdscr)
                footer = _footer_text(
                    options["keymap"],
                    action_row is not None,
                    search_query=search_query,
                    search_editing=search_editing,
                )
                _draw_curses_text(
                    stdscr, text, footer, scroll=scroll, color_attrs=color_attrs
                )
                stdscr.refresh()
                dirty = False
            try:
                key = stdscr.getch()
            except KeyboardInterrupt:
                # cbreak() leaves ISIG enabled, so Ctrl-C arrives as SIGINT
                # rather than as a key code. Quit instead of showing a traceback.
                break
            if key == -1:
                continue
            if search_editing:
                if key in (27,):
                    search_editing = False
                    if search_query:
                        search_query = ""
                        selected_index = 0
                        message = "Search cleared."
                    else:
                        message = "Search canceled."
                    dirty = True
                    continue
                if key in (10, 13, curses.KEY_ENTER):
                    search_editing = False
                    selected_index = normalize_selected_index(
                        args, selected_index, project_filter, search_query
                    )
                    focus = section_for_selected_index(
                        args, selected_index, focus, project_filter, search_query
                    )
                    message = "Search: %s" % (search_query or "(empty)")
                    dirty = True
                    continue
                if key in (8, 127, curses.KEY_BACKSPACE):
                    search_query = search_query[:-1]
                    selected_index = normalize_selected_index(
                        args, selected_index, project_filter, search_query
                    )
                    dirty = True
                    continue
                if key == 21:
                    search_query = ""
                    selected_index = 0
                    dirty = True
                    continue
                if 32 <= key <= 126:
                    search_query += chr(key)
                    selected_index = normalize_selected_index(
                        args, selected_index, project_filter, search_query
                    )
                    dirty = True
                    continue
                continue
            if action_row is not None:
                if key in (27, ord("q"), ord("Q")):
                    action_row = None
                    message = "Action canceled."
                    dirty = True
                    continue
                action = _action_for_key(key)
                if action:
                    try:
                        result = perform_row_action(action, action_row, args)
                        if action == "filter-project":
                            project_filter = result.get("project")
                            selected_index = 0
                        elif action == "show":
                            detail_row = action_row
                        message = result.get("message", "")
                    except Exception as exc:
                        message = "ERROR: %s" % exc
                    action_row = None
                    dirty = True
                    continue
            if key in (ord("q"), ord("Q")):
                break
            if key in (ord("r"), ord("R")):
                scroll = 0
                message = "Reloaded."
                dirty = True
                continue
            if key == ord("/"):
                search_editing = True
                message = "Search mode. Type to filter, Enter to apply, Esc to clear."
                dirty = True
                continue
            if key == 27 and search_query:
                search_query = ""
                selected_index = 0
                detail_row = None
                message = "Search cleared."
                dirty = True
                continue
            if key in (ord("?"), ord("H")):
                help_visible = not help_visible
                scroll = 0
                dirty = True
                continue
            if key in (9, ord("n"), ord("N"), ord("l"), ord("L"), curses.KEY_RIGHT):
                focus = next_section(focus)
                selected_index = first_selectable_index_for_section(
                    args, focus, project_filter, search_query
                )
                detail_row = None
                scroll = 0
                dirty = True
                continue
            if key in (ord("p"), ord("P"), ord("h"), curses.KEY_LEFT):
                focus = previous_section(focus)
                selected_index = first_selectable_index_for_section(
                    args, focus, project_filter, search_query
                )
                detail_row = None
                scroll = 0
                dirty = True
                continue
            if key in (ord("j"), ord("J"), curses.KEY_DOWN):
                selected_index = move_selection(
                    args, selected_index, 1, project_filter, search_query
                )
                detail_row = None
                dirty = True
                continue
            if key in (ord("k"), ord("K"), curses.KEY_UP):
                selected_index = move_selection(
                    args, selected_index, -1, project_filter, search_query
                )
                detail_row = None
                dirty = True
                continue
            if key in (4, curses.KEY_NPAGE):
                selected_index = move_selection(
                    args,
                    selected_index,
                    _page_scroll_amount(stdscr),
                    project_filter,
                    search_query,
                )
                detail_row = None
                dirty = True
                continue
            if key in (21, curses.KEY_PPAGE):
                selected_index = move_selection(
                    args,
                    selected_index,
                    -_page_scroll_amount(stdscr),
                    project_filter,
                    search_query,
                )
                detail_row = None
                dirty = True
                continue
            if key in (ord("g"), curses.KEY_HOME):
                selected_index = 0
                scroll = 0
                dirty = True
                continue
            if key in (ord("G"), curses.KEY_END):
                selected_index = max(
                    0,
                    len(selectable_dashboard_rows(args, project_filter, search_query))
                    - 1,
                )
                scroll = _max_scroll_for_screen(stdscr, text)
                dirty = True
                continue
            if key in (10, 13, curses.KEY_ENTER, ord("o"), ord("O")):
                action_row = selected_dashboard_row(
                    args, selected_index, project_filter, search_query
                )
                message = ""
                dirty = True
                continue
            if key in (ord("s"), ord("S")):
                detail_row = selected_dashboard_row(
                    args, selected_index, project_filter, search_query
                )
                message = ""
                dirty = True
                continue
            if key in (ord("d"), ord("D")):
                row = selected_dashboard_row(
                    args, selected_index, project_filter, search_query
                )
                try:
                    message = perform_row_action("done", row, args).get("message", "")
                    detail_row = None
                except Exception as exc:
                    message = "ERROR: %s" % exc
                dirty = True
                continue
            if key in (ord("f"), ord("F")):
                row = selected_dashboard_row(
                    args, selected_index, project_filter, search_query
                )
                try:
                    result = perform_row_action("filter-project", row, args)
                    project_filter = result.get("project")
                    selected_index = 0
                    detail_row = None
                    search_query = ""
                    message = result.get("message", "")
                except Exception as exc:
                    message = "ERROR: %s" % exc
                dirty = True
                continue
            if key in (ord("e"), ord("E")):
                row = selected_dashboard_row(
                    args, selected_index, project_filter, search_query
                )
                try:
                    message = perform_row_action("edit", row, args).get("message", "")
                except Exception as exc:
                    message = "ERROR: %s" % exc
                dirty = True
                continue
            if key == curses.KEY_RESIZE:
                dirty = True
                continue

    try:
        curses.wrapper(main)
    except KeyboardInterrupt:
        pass
    except curses.error as exc:
        # The terminal cannot drive curses (no TTY, unsupported TERM, or a
        # dumb terminal). Degrade to the plain dashboard instead of crashing.
        sys.stderr.write("Falling back to plain output: %s\n" % exc)
        sys.stdout.write(render_dashboard_safe(args))
    finally:
        watcher.stop()
    return 0


def _draw_curses_text(stdscr, text, footer="", scroll=0, color_attrs=None):
    height, width = stdscr.getmaxyx()
    if height <= 0 or width <= 0:
        return
    max_columns = max(0, width - 1)
    if max_columns <= 0:
        return

    body_height = max(0, height - 1)
    lines = text.splitlines()
    scroll = max(0, min(int(scroll or 0), max(0, len(lines) - body_height)))
    for row, line in enumerate(lines[scroll:]):
        if row >= body_height:
            break
        style = _style_for_line(line)
        _safe_addstr(
            stdscr,
            row,
            0,
            _clip_display_width(line, max_columns),
            _attr_for_style(color_attrs, style),
        )

    if footer and height >= 1:
        if scroll:
            footer = "scroll:%d  %s" % (scroll, footer)
        _safe_addstr(
            stdscr,
            height - 1,
            0,
            _clip_display_width(footer, max_columns),
            _attr_for_style(color_attrs, "footer"),
        )


def _safe_addstr(stdscr, row, column, text, attr=0):
    if not text:
        return
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
        # Some curses implementations raise when drawing exactly at the lower
        # right edge. The dashboard is best-effort; avoid crashing the TUI.
        pass


def _init_curses_colors(curses_module, theme="auto"):
    attrs = {style: 0 for style in TUI_COLOR_STYLES}
    try:
        attrs["title"] = curses_module.A_BOLD
        attrs["focus"] = curses_module.A_BOLD
        attrs["footer"] = curses_module.A_REVERSE
        attrs["selected"] = curses_module.A_REVERSE
        attrs["error"] = curses_module.A_BOLD
        attrs["help"] = curses_module.A_DIM
        attrs["muted"] = curses_module.A_DIM
        if theme == "mono" or not curses_module.has_colors():
            return attrs
        curses_module.start_color()
        background = -1
        try:
            curses_module.use_default_colors()
        except Exception:
            background = curses_module.COLOR_BLACK
        if theme == "light":
            pairs = (
                ("title", curses_module.COLOR_BLUE),
                ("focus", curses_module.COLOR_MAGENTA),
                ("section", curses_module.COLOR_BLUE),
                ("open", curses_module.COLOR_BLACK),
                ("active", curses_module.COLOR_BLUE),
                ("done", curses_module.COLOR_GREEN),
                ("agenda", curses_module.COLOR_MAGENTA),
                ("status", curses_module.COLOR_BLUE),
                ("muted", curses_module.COLOR_BLACK),
                ("error", curses_module.COLOR_RED),
                ("footer", curses_module.COLOR_BLACK),
                ("help", curses_module.COLOR_BLUE),
                ("search", curses_module.COLOR_MAGENTA),
                ("inspector", curses_module.COLOR_BLUE),
                ("selected", curses_module.COLOR_WHITE),
            )
        else:
            pairs = (
                ("title", curses_module.COLOR_CYAN),
                ("focus", curses_module.COLOR_YELLOW),
                ("section", curses_module.COLOR_BLUE),
                ("open", curses_module.COLOR_WHITE),
                ("active", curses_module.COLOR_CYAN),
                ("done", curses_module.COLOR_GREEN),
                ("agenda", curses_module.COLOR_MAGENTA),
                ("status", curses_module.COLOR_CYAN),
                ("muted", curses_module.COLOR_BLACK),
                ("error", curses_module.COLOR_RED),
                ("footer", curses_module.COLOR_BLACK),
                ("help", curses_module.COLOR_BLUE),
                ("search", curses_module.COLOR_YELLOW),
                ("inspector", curses_module.COLOR_CYAN),
                ("selected", curses_module.COLOR_YELLOW),
            )
        for index, (style, foreground) in enumerate(pairs, 1):
            curses_module.init_pair(index, foreground, background)
            attrs[style] = curses_module.color_pair(index) | attrs.get(style, 0)
        footer_pair = [style for style, _foreground in pairs].index("footer") + 1
        attrs["footer"] = (
            curses_module.color_pair(footer_pair) | curses_module.A_REVERSE
        )
        selected_pair = [style for style, _foreground in pairs].index("selected") + 1
        attrs["selected"] = (
            curses_module.color_pair(selected_pair) | curses_module.A_REVERSE
        )
    except Exception:
        return {style: 0 for style in TUI_COLOR_STYLES}
    return attrs


def _style_for_line(line):
    stripped = line.strip()
    if not stripped:
        return "default"
    if stripped.startswith("ERROR:") or stripped.startswith("Could not"):
        return "error"
    if line.startswith("lifetxt TUI"):
        return "title"
    if stripped and set(stripped) in ({"="}, {"-"}):
        return "rule"
    if line.startswith("> "):
        return "focus"
    if line.startswith("* "):
        return "selected"
    if (
        stripped.startswith("Views:")
        or stripped.startswith("Cards:")
        or stripped.startswith("Search:")
    ):
        return "search"
    if stripped.startswith(("INSPECTOR", "ACTIONS", "DETAIL")):
        return "inspector"
    if stripped in ("TASKS (open)", "AGENDA (next 12h and active intervals)", "STATUS"):
        return "section"
    if stripped.startswith("[x]"):
        return "done"
    if stripped.startswith("[/]"):
        return "active"
    if stripped.startswith("[ ]"):
        return "open"
    if " state:" in line:
        return "status"
    if stripped.startswith("No "):
        return "muted"
    if stripped.startswith(
        ("q", "r", "?", "h", "j", "k", "g", "G", "Ctrl-", "Page", "Tab", "l", "p")
    ):
        return "help"
    if line.startswith("  ") and "  " in line[2:] and stripped.endswith(")"):
        return "agenda"
    return "default"


def _attr_for_style(color_attrs, style):
    if not color_attrs:
        return 0
    return color_attrs.get(style, 0)


def _page_scroll_amount(stdscr):
    height, _width = stdscr.getmaxyx()
    return max(1, (height - 1) // 2)


def _scroll_to_selected(text, selected_index, scroll, stdscr):
    if selected_index is None:
        return max(0, int(scroll or 0))
    height, _width = stdscr.getmaxyx()
    body_height = max(1, height - 1)
    selected_line = _line_number_for_selected_row(text, selected_index)
    if selected_line is None:
        return max(0, int(scroll or 0))
    scroll = max(0, int(scroll or 0))
    if selected_line < scroll:
        return selected_line
    if selected_line >= scroll + body_height:
        return max(0, selected_line - body_height + 1)
    return scroll


def _line_number_for_selected_row(text, selected_index):
    for line_number, line in enumerate(text.splitlines()):
        if line.startswith("* "):
            return line_number
    return None


def _max_scroll_for_screen(stdscr, text):
    height, _width = stdscr.getmaxyx()
    body_height = max(0, height - 1)
    return max(0, len(text.splitlines()) - body_height)


def _footer_text(keymap, in_action_menu=False, search_query="", search_editing=False):
    if search_editing:
        return "search: %s  Enter apply  Esc clear  Ctrl-U clear line" % search_query
    if in_action_menu:
        return "action: s show  d done  e edit  f filter  Esc/q cancel"
    if keymap == "arrows":
        return "q quit  / search  ? help  arrows move/section  Enter actions  s detail  d done  r reload"
    return "q quit  / search  ? help  h/l section  j/k select  Enter actions  s detail  d done  r reload"


def _action_for_key(key):
    mapping = {
        ord("s"): "show",
        ord("S"): "show",
        10: "show",
        13: "show",
        ord("d"): "done",
        ord("D"): "done",
        ord("e"): "edit",
        ord("E"): "edit",
        ord("f"): "filter-project",
        ord("F"): "filter-project",
    }
    return mapping.get(key)


def _clip_display_width(text, max_columns):
    if max_columns <= 0:
        return ""
    used = 0
    clipped = []
    for char in text:
        width = _char_display_width(char)
        if used + width > max_columns:
            break
        clipped.append(char)
        used += width
    return "".join(clipped)


def _char_display_width(char):
    if unicodedata.combining(char):
        return 0
    if unicodedata.east_asian_width(char) in ("F", "W"):
        return 2
    return 1


def render_dashboard(
    args,
    focus="tasks",
    help_visible=False,
    selected_index=0,
    detail_row=None,
    action_row=None,
    project_filter=None,
    search_query="",
    message="",
):
    options = tui_options(args)
    if help_visible:
        return render_help(options)
    model = dashboard_model(
        args, project_filter=project_filter, search_query=search_query
    )
    model["focus"] = focus
    selected_index = normalize_selected_index(
        args, selected_index, project_filter, search_query
    )
    selected_row = selected_dashboard_row(
        args, selected_index, project_filter, search_query
    )
    lines = []
    lines.extend(
        render_modern_header(
            model, options, args, project_filter, search_query
        ).splitlines()
    )
    lines.append(
        "Theme:%s  Keymap:%s  Limit:%s  Window:%s"
        % (
            options["theme"],
            options["keymap"],
            options["limit"],
            options["agenda_window"],
        )
    )
    if message:
        lines.append(message)
    lines.append("")

    row_number = 0
    for section in model["sections"]:
        lines.append(section_title(section["key"], focus, section["title"]))
        rows = section["rows"]
        if rows:
            for row in rows:
                marker = "*" if row_number == selected_index else " "
                lines.append("%s %s" % (marker, row["label"]))
                row_number += 1
        else:
            lines.append("  %s" % section["empty"])
        lines.append("")

    if action_row:
        lines.extend(render_action_menu(action_row).splitlines())
    elif detail_row:
        lines.extend(render_row_detail(detail_row).splitlines())
    else:
        lines.extend(
            render_inspector(
                selected_row, project_filter=project_filter, search_query=search_query
            ).splitlines()
        )

    lines.append("")
    lines.append(
        "Use / to search. ? for help. Enter/o opens actions. s detail. d done. f project filter."
    )
    lines.append("Install textual for a richer TUI:")
    lines.append('  pip install "lifetxt[tui]"')
    return "\n".join(lines) + "\n"


def render_dashboard_safe(
    args,
    focus="tasks",
    help_visible=False,
    selected_index=0,
    detail_row=None,
    action_row=None,
    project_filter=None,
    search_query="",
    message="",
):
    try:
        return render_dashboard(
            args,
            focus=focus,
            help_visible=help_visible,
            selected_index=selected_index,
            detail_row=detail_row,
            action_row=action_row,
            project_filter=project_filter,
            search_query=search_query,
            message=message,
        )
    except Exception as exc:
        lines = [
            "lifetxt TUI",
            "=" * 72,
            "Could not load life.txt data.",
            "",
            "ERROR: %s" % exc,
            "",
            "Fix the file, then press r or wait for auto reload.",
        ]
        return "\n".join(lines) + "\n"


def render_help(options=None):
    options = options or {"keymap": "vim", "theme": "auto"}
    lines = [
        "lifetxt TUI help",
        "=" * 72,
        "theme    %s" % options.get("theme", "auto"),
        "keymap   %s" % options.get("keymap", "vim"),
        "",
        "q        quit",
        "r        reload files",
        "/        search visible dashboard rows",
        "Esc      clear active search",
        "? / H    toggle this help",
        "h / left focus previous section",
        "l / right focus next section",
        "tab / n  focus next section",
        "p        focus previous section",
        "j / down move selection down",
        "k / up   move selection up",
        "Ctrl-D / PageDown move half page down",
        "Ctrl-U / PageUp   move half page up",
        "g / home select first row",
        "G / end  select last row",
        "Enter/o  open action menu for the selected row",
        "s        show full detail for the selected row",
        "d        mark selected task-like row done",
        "e        open selected row source in $EDITOR",
        "f        filter by selected row project",
        "",
        "Sections: tasks, agenda, status",
        "The focused section is marked with >. The selected row is marked with *.",
        "The INSPECTOR panel shows the selected row without opening an action menu.",
    ]
    return "\n".join(lines) + "\n"


def render_modern_header(model, options, args, project_filter=None, search_query=""):
    from .workspace import active_workspace_name

    summary = model.get("summary", {})
    path_count = len(
        [path for path in getattr(args, "paths", []) or [] if path and path != "-"]
    )
    cards = [
        "open:%s" % summary.get("tasks", 0),
        "agenda:%s" % summary.get("agenda", 0),
        "status:%s" % summary.get("status", 0),
        "files:%s" % path_count,
    ]
    active_filter = project_filter or "-"
    active_search = search_query or "-"
    header_line = (
        "lifetxt TUI  |  modern terminal workspace  |  [q]uit  [/]search  [r]eload"
    )
    workspace_name = active_workspace_name(getattr(args, "config_data", None) or {})
    if workspace_name:
        header_line += "  |  workspace:%s" % workspace_name
    lines = [
        header_line,
        "=" * 72,
        "Cards: " + "  ".join(cards),
        "Views: "
        + "  ".join(
            "%s%s"
            % (">" if section["key"] == model.get("focus") else " ", section["key"])
            for section in model.get("sections", [])
        ),
        "Search:%s  Project:%s  Rows:%s"
        % (active_search, active_filter, summary.get("rows", 0)),
    ]
    return "\n".join(lines)


def render_inspector(row, project_filter=None, search_query=""):
    lines = ["INSPECTOR", "---------"]
    if project_filter:
        lines.append("project filter: %s" % project_filter)
    if search_query:
        lines.append("search: %s" % search_query)
    if not row:
        lines.append("No row selected.")
        return "\n".join(lines)
    lines.append(row.get("label", ""))
    meta = []
    if row.get("section"):
        meta.append("section:%s" % row["section"])
    if row.get("id"):
        meta.append("id:%s" % row["id"])
    if row_project(row):
        meta.append("project:%s" % row_project(row))
    if row.get("source") and row.get("line"):
        meta.append("%s:%s" % (os.path.basename(row["source"]), row["line"]))
    elif row.get("source"):
        meta.append(os.path.basename(row["source"]))
    if meta:
        lines.append("  " + "  ".join(meta))
    hint_parts = ["Enter actions", "s full detail"]
    if row.get("type") in ("T", "D", "R", "H") and row.get("id"):
        hint_parts.append("d done")
    if row_project(row):
        hint_parts.append("f filter")
    lines.append("  " + " / ".join(hint_parts))
    return "\n".join(lines)


def dashboard_model(args, project_filter=None, search_query="", limit=None):
    options = tui_options(args)
    limit = options["limit"] if limit is None else max(1, int(limit))
    items = load_items(args.paths)
    project_values = [project_filter] if project_filter else None
    blockers = blocked_map(items)
    task_items = filter_items(
        items, open_only=True, kinds=list(ACTIONABLE_KINDS), projects=project_values
    )
    start, end = parse_agenda_range(
        around_text="now", window_text=options["agenda_window"]
    )
    agenda = agenda_records(items, start, end)
    if project_filter:
        agenda = [
            record
            for record in agenda
            if project_filter in record.get("details", {}).get("project", [])
        ]
    statuses = latest_status_records(items, active_only=True)
    task_rows = _filter_rows(
        [
            _task_row(item, options["id_key"], blocked=bool(blockers.get(id(item))))
            for item in task_items
        ],
        search_query,
    )
    agenda_rows = _filter_rows(
        [_agenda_row(record, options["id_key"]) for record in agenda], search_query
    )
    status_rows = _filter_rows(
        [_status_row(record) for record in statuses], search_query
    )
    sections = [
        {
            "key": "tasks",
            "title": "TASKS (open)",
            "empty": "No open tasks.",
            "rows": task_rows[:limit],
        },
        {
            "key": "agenda",
            "title": "AGENDA (next %s and active intervals)" % options["agenda_window"],
            "empty": "No agenda items.",
            "rows": agenda_rows[:limit],
        },
        {
            "key": "status",
            "title": "STATUS",
            "empty": "No active status.",
            "rows": status_rows[:limit],
        },
    ]
    summary = {
        "tasks": len(task_rows),
        "agenda": len(agenda_rows),
        "status": len(status_rows),
        "rows": sum(len(section["rows"]) for section in sections),
    }
    return {
        "focus": "tasks",
        "sections": sections,
        "summary": summary,
        # The parsed records, so argument completion can offer the projects,
        # tags, ids, and people this file actually uses without re-reading it.
        "items": items,
    }


def _filter_rows(rows, search_query=""):
    query = str(search_query or "").strip().lower()
    if not query:
        return rows
    result = []
    for row in rows:
        haystack = " ".join(
            str(part or "")
            for part in (
                row.get("label"),
                row.get("title"),
                row.get("id"),
                row.get("section"),
                row.get("source"),
                item_to_line_like(row),
            )
        ).lower()
        if query in haystack:
            result.append(row)
    return result


def item_to_line_like(row):
    details = row.get("details") or {}
    parts = []
    for key, values in sorted(details.items()):
        for value in values:
            parts.append("%s:%s" % (key, value))
    return " ".join(parts)


def selectable_dashboard_rows(args, project_filter=None, search_query=""):
    rows = []
    for section in dashboard_model(
        args, project_filter=project_filter, search_query=search_query
    )["sections"]:
        rows.extend(section["rows"])
    return rows


def selected_dashboard_row(
    args, selected_index=0, project_filter=None, search_query=""
):
    rows = selectable_dashboard_rows(
        args, project_filter=project_filter, search_query=search_query
    )
    if not rows:
        return None
    selected_index = max(0, min(int(selected_index or 0), len(rows) - 1))
    return rows[selected_index]


def normalize_selected_index(
    args, selected_index=0, project_filter=None, search_query=""
):
    count = len(
        selectable_dashboard_rows(
            args, project_filter=project_filter, search_query=search_query
        )
    )
    if count <= 0:
        return 0
    return max(0, min(int(selected_index or 0), count - 1))


def move_selection(args, selected_index, delta, project_filter=None, search_query=""):
    count = len(
        selectable_dashboard_rows(
            args, project_filter=project_filter, search_query=search_query
        )
    )
    if count <= 0:
        return 0
    return max(0, min(int(selected_index or 0) + int(delta or 0), count - 1))


def first_selectable_index_for_section(
    args, section_key, project_filter=None, search_query=""
):
    rows = selectable_dashboard_rows(
        args, project_filter=project_filter, search_query=search_query
    )
    for index, row in enumerate(rows):
        if row.get("section") == section_key:
            return index
    return 0


def section_for_selected_index(
    args, selected_index, fallback="tasks", project_filter=None, search_query=""
):
    row = selected_dashboard_row(
        args, selected_index, project_filter=project_filter, search_query=search_query
    )
    if row:
        return row.get("section") or fallback
    return fallback


def render_row_detail(row):
    if not row:
        return "DETAIL\n------\nNo row selected."
    lines = ["DETAIL", "------", row.get("label", "")]
    if row.get("id"):
        lines.append("id: %s" % row["id"])
    if row.get("source"):
        location = row["source"]
        if row.get("line"):
            location += ":%s" % row["line"]
        lines.append("source: %s" % location)
    if row.get("text"):
        lines.append("")
        lines.append("life.txt:")
        for line in str(row["text"]).splitlines():
            lines.append("  " + line)
    details = row.get("details") or {}
    body = details.get("body")
    if body:
        lines.append("")
        lines.append("body:")
        for value in body:
            for line in str(value).splitlines():
                lines.append("  " + line)
    return "\n".join(lines)


def render_action_menu(row):
    if not row:
        return "ACTIONS\n-------\nNo row selected."
    actions = row_actions(row)
    lines = ["ACTIONS", "-------", row.get("label", "")]
    for key, description in actions:
        lines.append("%s  %s" % (key, description))
    lines.append("Esc/q  cancel")
    return "\n".join(lines)


def row_actions(row):
    actions = [("s", "show full detail")]
    if (
        row
        and row.get("source")
        and row.get("id")
        and row.get("type") in ("T", "D", "R", "H")
    ):
        actions.append(("d", "mark done"))
    if row and row.get("source"):
        actions.append(("e", "open in $EDITOR"))
    if row_project(row):
        actions.append(("f", "filter by project:%s" % row_project(row)))
    return actions


def perform_row_action(action, row, args):
    if not row:
        raise ValueError("No row selected.")
    if action == "show":
        return {
            "message": "Showing detail for %s." % row.get("title", row.get("id", "row"))
        }
    if action == "done":
        if not row.get("source") or not row.get("id"):
            raise ValueError("Selected row needs source and id to mark done.")
        from .fzf_helper import update_item

        update_item(row["source"], row["id"], tui_options(args)["id_key"], status="[x]")
        return {"message": "Marked done: %s" % row["id"]}
    if action == "edit":
        from .fzf_helper import open_editor

        open_editor(
            {
                "id": row.get("id", ""),
                "source": row.get("source", ""),
                "line": row.get("line"),
                "label": row.get("label", ""),
                "body": "",
                "text": row.get("text", ""),
            }
        )
        return {
            "message": "Opened editor for %s." % row.get("id", row.get("title", "row"))
        }
    if action == "filter-project":
        project = row_project(row)
        if not project:
            raise ValueError("Selected row has no project:.")
        return {"project": project, "message": "Filtered by project:%s" % project}
    raise ValueError("Unknown TUI action: %s" % action)


def row_project(row):
    if not row:
        return None
    details = row.get("details") or {}
    values = details.get("project") or []
    if values:
        return values[0]
    return None


def _task_row(item, id_key, blocked=False):
    item_id = item.details.get(id_key, [""])[0] if item.details.get(id_key) else ""
    bits = [item.status, item.kind, item.title]
    if item_id:
        bits.append("id:%s" % item_id)
    for key in ("project", "due", "do", "priority"):
        if item.details.get(key):
            bits.append("%s:%s" % (key, item.details[key][0]))
    return {
        "section": "tasks",
        "type": item.kind,
        "status": item.status,
        "title": item.title,
        "id": item_id,
        "source": getattr(item, "source", ""),
        "line": item.line,
        "details": item.details,
        "text": item_to_line(item),
        "label": " ".join(bits),
        "blocked": blocked,
    }


def _agenda_row(record, id_key):
    details = record.get("details") or {}
    item_id = (
        details.get(id_key, [""])[0]
        if details.get(id_key)
        else record.get("source_id", "")
    )
    bits = [
        record.get("when", ""),
        record.get("status", ""),
        record.get("type", ""),
        record.get("title", ""),
    ]
    if item_id:
        bits.append("id:%s" % item_id)
    if details.get("project"):
        bits.append("project:%s" % details["project"][0])
    if record.get("blocked"):
        bits.append("blocked")
    return {
        "section": "agenda",
        "type": record.get("type", ""),
        "status": record.get("status", ""),
        "title": record.get("title", ""),
        "id": item_id,
        "source": record.get("source", ""),
        "line": record.get("line"),
        "details": details,
        "text": record.get("text", ""),
        "label": " ".join(str(bit) for bit in bits if str(bit)),
    }


def _status_row(record):
    details = record.get("details") or {}
    bits = [
        record.get("status", ""),
        "S",
        record.get("title", ""),
        "person:%s" % record.get("person", ""),
    ]
    if details.get("state"):
        bits.append("state:%s" % details["state"][0])
    return {
        "section": "status",
        "type": "S",
        "status": record.get("status", ""),
        "title": record.get("title", ""),
        "id": details.get("id", [""])[0] if details.get("id") else "",
        "source": record.get("source", ""),
        "line": record.get("line"),
        "details": details,
        "text": "",
        "label": " ".join(str(bit) for bit in bits if str(bit)),
    }


def section_title(section, focus, title):
    prefix = ">" if section == focus else " "
    return "%s %s" % (prefix, title)


def next_section(current):
    if current not in TUI_SECTIONS:
        return TUI_SECTIONS[0]
    index = TUI_SECTIONS.index(current)
    return TUI_SECTIONS[(index + 1) % len(TUI_SECTIONS)]


def previous_section(current):
    if current not in TUI_SECTIONS:
        return TUI_SECTIONS[-1]
    index = TUI_SECTIONS.index(current)
    return TUI_SECTIONS[(index - 1) % len(TUI_SECTIONS)]


class FileChangeWatcher:
    def __init__(self, paths, use_watchdog=True):
        self.paths = [
            os.path.abspath(path) for path in paths or [] if path and path != "-"
        ]
        self.use_watchdog = use_watchdog
        self._snapshot = self._file_snapshot()
        self._changed = False
        self._lock = threading.Lock()
        self._observer = None

    def start(self):
        if self.use_watchdog:
            self._start_watchdog()
        return self

    def stop(self):
        observer = self._observer
        self._observer = None
        if observer is not None:
            observer.stop()
            observer.join(timeout=1)

    def consume_changed(self):
        with self._lock:
            if self._changed:
                self._changed = False
                self._snapshot = self._file_snapshot()
                return True
        current = self._file_snapshot()
        if current != self._snapshot:
            self._snapshot = current
            return True
        return False

    def mark_changed(self):
        with self._lock:
            self._changed = True

    def _file_snapshot(self):
        snapshot = {}
        for path in self.paths:
            try:
                stat = os.stat(path)
            except OSError:
                snapshot[path] = None
                continue
            snapshot[path] = (stat.st_mtime_ns, stat.st_size)
        return snapshot

    def _start_watchdog(self):
        if not self.paths:
            return
        try:
            from watchdog.events import FileSystemEventHandler
            from watchdog.observers import Observer
        except Exception:
            return

        target_paths = set(self.paths)
        watcher = self

        class Handler(FileSystemEventHandler):
            def on_any_event(self, event):
                paths = [os.path.abspath(getattr(event, "src_path", "") or "")]
                dest_path = getattr(event, "dest_path", None)
                if dest_path:
                    paths.append(os.path.abspath(dest_path))
                for path in paths:
                    if path in target_paths:
                        watcher.mark_changed()
                        break

        observer = Observer()
        directories = sorted(set(os.path.dirname(path) or "." for path in self.paths))
        for directory in directories:
            if os.path.isdir(directory):
                observer.schedule(Handler(), directory, recursive=False)
        if not observer.emitters:
            return
        observer.daemon = True
        observer.start()
        self._observer = observer


def load_items(paths):
    items = []
    for path in paths:
        with open(path, "r", encoding="utf-8-sig") as handle:
            path_items, diagnostics = parse_text(handle.read())
        errors = [
            diagnostic for diagnostic in diagnostics if diagnostic.severity == "error"
        ]
        if errors:
            raise ValueError(errors[0].format())
        for item in path_items:
            item.source = path
        items.extend(path_items)
    return items


def _textual_available():
    try:
        import textual  # noqa: F401

        return True
    except ImportError:
        return False
