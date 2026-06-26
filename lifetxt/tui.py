import os
import sys
import threading
import unicodedata

from .agenda import agenda_records, filter_items, parse_agenda_range
from .parser import parse_text
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
)


def cmd_tui(args):
    if _textual_available():
        return run_textual(args)
    return run_curses_or_plain(args)


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

        def compose(self):
            self.dashboard = Static(render_dashboard_safe(args, focus=self.focus, help_visible=self.help_visible))
            yield self.dashboard

        def on_mount(self):
            self.set_interval(TUI_POLL_SECONDS, self.refresh_if_changed)

        def on_unmount(self):
            watcher.stop()

        def refresh_if_changed(self):
            if watcher.consume_changed():
                self.refresh_dashboard()

        def refresh_dashboard(self):
            self.dashboard.update(render_dashboard_safe(args, focus=self.focus, help_visible=self.help_visible))

        def on_key(self, event):
            if event.key == "q":
                self.exit()
            elif event.key == "r":
                self.refresh_dashboard()
            elif event.key in ("question_mark", "H"):
                self.help_visible = not self.help_visible
                self.refresh_dashboard()
            elif event.key in ("tab", "n", "l", "right"):
                self.focus = next_section(self.focus)
                self.refresh_dashboard()
            elif event.key in ("p", "h", "left"):
                self.focus = previous_section(self.focus)
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

    watcher = FileChangeWatcher(args.paths).start()

    def main(stdscr):
        stdscr.timeout(int(TUI_POLL_SECONDS * 1000))
        color_attrs = _init_curses_colors(curses)
        focus = "tasks"
        scroll = 0
        help_visible = False
        dirty = True
        text = ""
        while True:
            if dirty or watcher.consume_changed():
                stdscr.erase()
                text = render_dashboard_safe(args, focus=focus, help_visible=help_visible)
                footer = "q quit  ? help  h/l section  j/k scroll  g/G top/bottom  r reload"
                _draw_curses_text(stdscr, text, footer, scroll=scroll, color_attrs=color_attrs)
                stdscr.refresh()
                dirty = False
            key = stdscr.getch()
            if key == -1:
                continue
            if key in (ord("q"), ord("Q")):
                break
            if key in (ord("r"), ord("R")):
                scroll = 0
                dirty = True
                continue
            if key in (ord("?"), ord("H")):
                help_visible = not help_visible
                scroll = 0
                dirty = True
                continue
            if key in (9, ord("n"), ord("N"), ord("l"), ord("L"), curses.KEY_RIGHT):
                focus = next_section(focus)
                scroll = 0
                dirty = True
                continue
            if key in (ord("p"), ord("P"), ord("h"), curses.KEY_LEFT):
                focus = previous_section(focus)
                scroll = 0
                dirty = True
                continue
            if key in (ord("j"), ord("J"), curses.KEY_DOWN):
                scroll += 1
                dirty = True
                continue
            if key in (ord("k"), ord("K"), curses.KEY_UP):
                scroll = max(0, scroll - 1)
                dirty = True
                continue
            if key in (4, curses.KEY_NPAGE):
                scroll += _page_scroll_amount(stdscr)
                dirty = True
                continue
            if key in (21, curses.KEY_PPAGE):
                scroll = max(0, scroll - _page_scroll_amount(stdscr))
                dirty = True
                continue
            if key in (ord("g"), curses.KEY_HOME):
                scroll = 0
                dirty = True
                continue
            if key in (ord("G"), curses.KEY_END):
                scroll = _max_scroll_for_screen(stdscr, text)
                dirty = True
                continue
            if key == curses.KEY_RESIZE:
                dirty = True
                continue

    try:
        curses.wrapper(main)
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
        _safe_addstr(stdscr, row, 0, _clip_display_width(line, max_columns), _attr_for_style(color_attrs, style))

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


def _init_curses_colors(curses_module):
    attrs = {style: 0 for style in TUI_COLOR_STYLES}
    try:
        attrs["title"] = curses_module.A_BOLD
        attrs["focus"] = curses_module.A_BOLD
        attrs["footer"] = curses_module.A_REVERSE
        attrs["error"] = curses_module.A_BOLD
        attrs["help"] = curses_module.A_DIM
        attrs["muted"] = curses_module.A_DIM
        if not curses_module.has_colors():
            return attrs
        curses_module.start_color()
        background = -1
        try:
            curses_module.use_default_colors()
        except Exception:
            background = curses_module.COLOR_BLACK
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
        )
        for index, (style, foreground) in enumerate(pairs, 1):
            curses_module.init_pair(index, foreground, background)
            attrs[style] = curses_module.color_pair(index) | attrs.get(style, 0)
        footer_pair = [style for style, _foreground in pairs].index("footer") + 1
        attrs["footer"] = curses_module.color_pair(footer_pair) | curses_module.A_REVERSE
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
    if stripped and set(stripped) == {"="}:
        return "rule"
    if line.startswith("> "):
        return "focus"
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
    if stripped.startswith(("q", "r", "?", "h", "j", "k", "g", "G", "Ctrl-", "Page", "Tab", "l", "p")):
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


def _max_scroll_for_screen(stdscr, text):
    height, _width = stdscr.getmaxyx()
    body_height = max(0, height - 1)
    return max(0, len(text.splitlines()) - body_height)


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


def render_dashboard(args, focus="tasks", help_visible=False):
    if help_visible:
        return render_help()
    items = load_items(args.paths)
    tasks = filter_items(items, open_only=True, kinds=["T"])[:10]
    start, end = parse_agenda_range(around_text="now", window_text="12h")
    agenda = agenda_records(items, start, end)[:10]
    statuses = latest_status_records(items, active_only=True)
    lines = []
    lines.append("lifetxt TUI                                  [q]uit  [r]eload")
    lines.append("=" * 72)
    lines.append(section_title("tasks", focus, "TASKS (open)"))
    if tasks:
        for item in tasks:
            lines.append("  %s %s %s" % (item.status, item.kind, item.title))
    else:
        lines.append("  No open tasks.")
    lines.append("")
    lines.append(section_title("agenda", focus, "AGENDA (next 12h and active intervals)"))
    if agenda:
        for record in agenda:
            lines.append("  %s  %s (%s)" % (record.get("when", ""), record.get("title", ""), record.get("type", "")))
    else:
        lines.append("  No agenda items.")
    lines.append("")
    lines.append(section_title("status", focus, "STATUS"))
    if statuses:
        for record in statuses:
            state = ""
            details = record.get("details", {})
            if details.get("state"):
                state = " state:%s" % details["state"][0]
            lines.append("  %s %s (%s)%s" % (record.get("status", ""), record.get("title", ""), record.get("person", ""), state))
    else:
        lines.append("  No active status.")
    lines.append("")
    lines.append("Use ? for help. Reload with r. Install textual for a richer TUI:")
    lines.append('  pip install "lifetxt[tui]"')
    return "\n".join(lines) + "\n"


def render_dashboard_safe(args, focus="tasks", help_visible=False):
    try:
        return render_dashboard(args, focus=focus, help_visible=help_visible)
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


def render_help():
    lines = [
        "lifetxt TUI help",
        "=" * 72,
        "q        quit",
        "r        reload files",
        "? / H    toggle this help",
        "h / left focus previous section",
        "l / right focus next section",
        "tab / n  focus next section",
        "p        focus previous section",
        "j / down scroll down",
        "k / up   scroll up",
        "Ctrl-D / PageDown scroll half page down",
        "Ctrl-U / PageUp   scroll half page up",
        "g / gg / home scroll to top",
        "G / end       scroll to bottom",
        "",
        "Sections: tasks, agenda, status",
        "The focused section is marked with > and highlighted when colors are available.",
    ]
    return "\n".join(lines) + "\n"


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
        self.paths = [os.path.abspath(path) for path in paths or [] if path and path != "-"]
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
        errors = [diagnostic for diagnostic in diagnostics if diagnostic.severity == "error"]
        if errors:
            raise ValueError(errors[0].format())
        items.extend(path_items)
    return items


def _textual_available():
    try:
        import textual  # noqa: F401
        return True
    except ImportError:
        return False
