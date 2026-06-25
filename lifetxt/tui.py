import sys

from .agenda import agenda_records, filter_items, parse_agenda_range
from .parser import parse_text
from .status_summary import latest_status_records


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

    class LifeTxtApp(App):
        def compose(self):
            self.dashboard = Static(render_dashboard(args))
            yield self.dashboard

        def on_key(self, event):
            if event.key == "q":
                self.exit()
            elif event.key == "r":
                self.dashboard.update(render_dashboard(args))

    LifeTxtApp().run()
    return 0


def run_curses_or_plain(args):
    try:
        import curses
    except ImportError:
        sys.stdout.write(render_dashboard(args))
        return 0

    def main(stdscr):
        stdscr.nodelay(False)
        while True:
            stdscr.erase()
            stdscr.addstr(0, 0, render_dashboard(args))
            stdscr.addstr(curses.LINES - 1, 0, "q quit  r reload")
            stdscr.refresh()
            key = stdscr.getch()
            if key in (ord("q"), ord("Q")):
                break
            if key in (ord("r"), ord("R")):
                continue

    curses.wrapper(main)
    return 0


def render_dashboard(args):
    items = load_items(args.paths)
    tasks = filter_items(items, open_only=True, kinds=["T"])[:10]
    start, end = parse_agenda_range(around_text="now", window_text="12h")
    agenda = agenda_records(items, start, end)[:10]
    statuses = latest_status_records(items, active_only=True)
    lines = []
    lines.append("lifetxt TUI                                  [q]uit  [r]eload")
    lines.append("=" * 72)
    lines.append("TASKS (open)")
    if tasks:
        for item in tasks:
            lines.append("  %s %s %s" % (item.status, item.kind, item.title))
    else:
        lines.append("  No open tasks.")
    lines.append("")
    lines.append("AGENDA (next 12h and active intervals)")
    if agenda:
        for record in agenda:
            lines.append("  %s  %s (%s)" % (record.get("when", ""), record.get("title", ""), record.get("type", "")))
    else:
        lines.append("  No agenda items.")
    lines.append("")
    lines.append("STATUS")
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
    lines.append("Reload with r. Install textual for a richer TUI:")
    lines.append('  pip install "lifetxt[tui]"')
    return "\n".join(lines) + "\n"


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
