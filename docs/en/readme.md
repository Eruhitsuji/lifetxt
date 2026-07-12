# life.txt

`life.txt` is a plain-text format for managing tasks, events, deadlines,
reminders, habits, status / presence records, messages, notes, and journal /
diary entries in one human-readable file.

See [life_txt_format_spec.md](./life_txt_format_spec.md) for the format
specification.
See [cli.md](./cli.md) for command compatibility, filters, output formats, and
conversion rules.

## Minimal life.txt

```txt
[ ] T Write_Report due:2026-06-12 project:university assignee:alice
[ ] E Seminar from:2026-06-08T13:00 to:2026-06-08T14:30 loc:university attendee:alice
[/] S Working from:2026-06-06T14:00 state:busy person:self
[ ] M "Review slides" sender:self recipient:alice notify_at:2026-06-06T09:00 channel:teams
[N] J "Research day" on:2026-06-23 mood:good tag:lab
| Read papers in the morning.
| Wrote parser tests in the afternoon.
[N] N Research_Memo project:research
```

## Examples

Sample files are available in [../../examples/](../../examples/):

- [minimal_life.txt](../../examples/minimal_life.txt): a compact starter file
- [tasks_life.txt](../../examples/tasks_life.txt): tasks, deadlines, and notes
- [events_life.txt](../../examples/events_life.txt): calendar-style event records
- [habits_reminders_life.txt](../../examples/habits_reminders_life.txt): habits and reminders
- [status_presence.txt](../../examples/status_presence.txt): personal presence records
- [team_status_life.txt](../../examples/team_status_life.txt): multi-person status records
- [messages_life.txt](../../examples/messages_life.txt): message and notification records
- [diary_life.txt](../../examples/diary_life.txt): journal / diary entries with multiline body text
- [markdown_life.txt](../../examples/markdown_life.txt): safe Markdown title/body/note rendering examples
- [linked_life.txt](../../examples/linked_life.txt): id-based links with `parent`, `ref`, `depends_on`, `blocks`, and `related`
- [recurrence_time_life.txt](../../examples/recurrence_time_life.txt): timezones, fractional seconds, simple recurrence, body, and dependency examples
- [hierarchy_life.txt](../../examples/hierarchy_life.txt): indented nested records that infer `parent:` links
- [agenda_life.txt](../../examples/agenda_life.txt): data for the `agenda` command
- [json_roundtrip_life.txt](../../examples/json_roundtrip_life.txt): repeated keys and quoted values
- [calendar_import.ics](../../examples/calendar_import.ics): sample iCalendar input for `import-ics`

## CLI

This repository includes a dependency-free Python CLI:
See [cli.md](./cli.md) for detailed command usage and option reference.
See [web.md](./web.md) for the optional FastAPI REST API and browser GUI.

```sh
python -m lifetxt check life.txt
python -m lifetxt to-json life.txt --pretty
python -m lifetxt to-jsonl life.txt --open --type task -o open_tasks.jsonl
python -m lifetxt to-csv life.txt --type journal -o journal.csv
python -m lifetxt markdown life.txt --field all --format html -o markdown.html
python -m lifetxt import-ics google_calendar.ics -o life.txt --append --tag google
python -m lifetxt sync-ics --url-env LIFETXT_GOOGLE_CAL_ICS -o .generated/google_calendar.life.txt --cache-dir .cache/lifetxt --tag google
python -m lifetxt filter life.txt --open --type task -o open_tasks.life.txt
python -m lifetxt filter life.txt --open --type task --canonical -o canonical_tasks.life.txt
python -m lifetxt filter life.txt --assignee alice -o alice_items.life.txt
python -m lifetxt filter "projects/**/*.life.txt" --team research --tag-all urgent,review --exclude-tag archived
python -m lifetxt filter life.txt --after now --type event -o future_schedule.life.txt
python -m lifetxt filter life.txt --type status --person self -o my_status.life.txt
python -m lifetxt filter life.txt --type message --recipient alice -o alice_messages.life.txt
python -m lifetxt status life.txt
python -m lifetxt status life.txt --active
python -m lifetxt status life.txt --format json --pretty
python -m lifetxt notify life.txt --recipient self
python -m lifetxt notify life.txt --watch --interval 30
python -m lifetxt ids life.txt --assign --dry-run
python -m lifetxt ids "projects/**/*.life.txt" --assign --prefix item --dry-run
python -m lifetxt links life.txt --id task_report --direction incoming
python -m lifetxt agenda life.txt --from 2026-06-06T13:00 --to 2026-06-06T18:00
python -m lifetxt agenda life.txt --from 2026-06-06T13:00:30+09:00 --to 2026-06-06T18:00:00+09:00
python -m lifetxt agenda life.txt --around now --window 1w --format life -o agenda.life.txt
python -m lifetxt agenda life.txt --from 2026-06-06 --to 2026-06-06 --open
python -m lifetxt agenda life.txt --from 2026-06-06 --to 2026-06-06 --type task --project research
python -m lifetxt tui life.txt
python -m lifetxt fzf life.txt --open --type task --action done
python -m lifetxt timer start life.txt --id task_report
python -m lifetxt timer stop
python -m lifetxt stats life.txt --project research
python -m lifetxt git-hook status
python -m lifetxt completion bash
python -m lifetxt from-json life.json -o life.txt
python -m lifetxt from-jsonl life.jsonl -o life.txt
python -m lifetxt from-csv journal.csv -o journal.life.txt
python -m lifetxt serve life.txt --host 127.0.0.1 --port 8000
python -m lifetxt serve life.txt .generated/google_calendar.life.txt --write-file life.txt --read-only
python -m lifetxt config init -o .lifetxt.json
```

Install locally as a command:

```sh
python -m pip install -e .
lifetxt check examples/minimal_life.txt
```

Most file-reading commands accept multiple input paths, glob patterns, and
directories containing life.txt-like `.txt` files. The `filter`,
`to-json`, `to-jsonl`, `to-csv`, and `markdown` commands support item filters such as `--open`,
`--status`, `--type`, `--project`, `--tag`, `--tag-all`, `--exclude-tag`,
`--user`, `--team`, `--person`, `--owner`,
`--assignee`, `--attendee`, `--sender`, `--recipient`, `--detail`, `--text`,
`--after`, and `--before`.
`filter --format life` preserves original matching item lines by default; use
`--canonical` to regenerate normalized life.txt lines. Use `person:` for
status / presence targets, `assignee:` for assigned work, `owner:` for
accountability, and `attendee:` for event participants.

The `to-csv` command stores repeated detail values as JSON arrays inside CSV
cells. Multiline `body:` values are stored as quoted CSV cells.

The `import-ics` command converts iCalendar `.ics` files, such as Google
Calendar exports, to `E` event items. Timed events become `from:` / `to:`,
all-day events become `on:`, participants become `attendee:`, and `--append`
can add imported events to an existing `life.txt`. Imported calendar events
include `source:ics` and `uid:` metadata. Convenience presets also import
Markdown task lists, Todoist CSV exports, and GitHub Issues JSON exports:

```sh
python -m lifetxt import-ics tasks.md --preset markdown --project inbox
python -m lifetxt import-ics todoist.csv --preset todoist --tag todoist
python -m lifetxt import-ics github_issues.json --preset github --project repo
```

For periodic calendar sync, use `sync-ics` with a secret iCalendar URL stored in
an environment variable. Keep manually edited items in `life.txt`, write
ICS-derived items to a generated file such as `.generated/google_calendar.life.txt`,
and pass both files to commands such as `agenda` or `check`. Use
`--merge-existing --soft-delete-missing` when you want to preserve comments in
the generated output while updating UID-backed records in place.

The optional web interface is installed separately:

```sh
pip install -r requirements-web.txt
python -m lifetxt serve life.txt
```

The Web UI uses a header Workspace for Dashboard, Items, Agenda, Timeline,
Focus, Review, Messages, Team, Status, Notifications, Stats, Graph, Display,
and Kiosk.
The header includes a contextual View Guide for the active workspace, exposes
the workspace switcher as a keyboard-friendly tablist, and provides a
skip-to-content link for dense dashboards.
Records open in centered modals with thread replies, dependency links, due
quick actions, and Markdown previews. Review supports project/custom date
filters and Markdown copy; Timeline preserves `range=today|24h|week` in the
URL, shows guided empty states for ranges with no dated records, and marks
records that overlap the selected range from earlier starts as `ongoing`.
The Items view now has action-oriented empty states, and Team cards include a
`View items` action that opens `user=PERSON&open_only=true` in the shared
Items filter.
Dashboard cards and theme tokens are configurable through `web.dashboard.*`
and `web.theme.*`. Display mode has separate light/dark palettes. The `+ New`
editor exposes viewport-aware hover/focus help for status, type, title, and
detail fields. Press `Ctrl+K` for the fuzzy
command palette, recently opened records, undo history, exports, theme toggles,
and common actions. Use `--read-only` for public or wall-display deployments
and `--write-file FILE` when reading multiple files but writing to a single
hand-maintained file. See
[web.md](./web.md) for URL parameters, API routes, browser notifications, and
kiosk/display modes.

Terminal-oriented helpers are available through `tui`, `fzf`, `timer`, `stats`,
`git-hook`, and `completion`. `fzf` requires `fzf` or `peco` in `PATH`; the
enhanced TUI can use the optional `tui` extra, while a dependency-free fallback
is available by default. TUI now includes top-card summaries, an always-visible
inspector panel, `/` search, configurable themes/keymaps, mark-done, editor
opening, and project filtering.

## Assist

Input assistance is available in both non-interactive and interactive modes:

```sh
python -m lifetxt assist --type task --title "Write Report" --due 2026-06-12 --project university --tag report
python -m lifetxt assist --type status --title "Working" --from 2026-06-06T14:00 --state busy --person self
python -m lifetxt assist --type message --title "Review Slides" --sender self --recipient alice --notify_at 2026-06-06T09:00
python -m lifetxt assist --type diary --title "Research day" --on 2026-06-23 --mood good --body "Read papers."
python -m lifetxt assist --type task --title "Write Report" --due 2026-06-12 --output new_life.txt
python -m lifetxt assist --interactive --append life.txt
```

In create mode, `assist --output FILE` appends the generated line to `FILE`.
Existing data can be updated by line number or by `id:`.

```sh
python -m lifetxt assist --update life.txt --match-id task_001 --status done --done 2026-06-06
python -m lifetxt assist --update life.txt --line 3 --title "New Title" --add-detail tag=important
```

## Status And Agenda Views

The `status` command prints the latest `S` status / presence item for each
`person:`. If `person:` is omitted, it is treated as `self` for this summary.
Use `--active` to ignore finished status logs with `to:`.

The `agenda` command prints items related to a datetime range. `from/to`,
`notify_from/notify_to`, and `on` are treated as intervals, while `due`, `do`,
`at`, `moved_to`, and `notify_at` are treated as points or all-day spans.
Datetime values may include seconds, fractional seconds, and explicit
timezones, such as `2026-06-06T13:00:30.25+09:00`. Simple `repeat:` values
(`daily`, `weekly`, `monthly`, `yearly`, `weekdays`) are expanded by agenda and
time filters, with optional `interval:`, `until:`, and `count:`. A small
dependency-free `repeat:RRULE:...` subset is also expanded for
`FREQ=DAILY|WEEKLY|MONTHLY|YEARLY`, `INTERVAL`, `COUNT`, `UNTIL`, and
daily/weekly `BYDAY`.

Agenda filters can be combined:

```sh
python -m lifetxt agenda life.txt --from 2026-06-06 --to 2026-06-06 --open
python -m lifetxt agenda life.txt --from 2026-06-06 --to 2026-06-06 --status todo --type task
python -m lifetxt agenda life.txt --from 2026-06-06 --to 2026-06-06 --project research --tag urgent
python -m lifetxt agenda life.txt --from 2026-06-06 --to 2026-06-06 --team research --tag-all urgent,review
python -m lifetxt agenda life.txt --from 2026-06-06 --to 2026-06-06 --detail priority=A --text report
```

`--open` means unfinished workflow items only: `[ ]`, `[/]`, `[>]`, and `[?]`.
Repeated `--detail key=value` filters are ANDed. `--window` accepts seconds,
minutes, hours, days, weeks, months approximated as 30 days, and years
approximated as 365 days.

Message records use type `M`. They require `sender:` and `recipient:` and can
use `notify_at:` for one notification time or `notify_from:` / `notify_to:` for
a notification window. Use `body:` for longer message text when the title should
stay short. The web API also provides `/api/messages` for convenient message
listing and creation. `/api/items/id/{id}` and `/api/messages/id/{id}` support
id-based access, while `/api/messages/thread/{id}` and
`/api/messages/id/{id}/reply` support message threads via `parent:`.

Use `python -m lifetxt notify life.txt --watch` as a resident notification
watcher. The browser GUI also has an `Enable Notifications` button that polls
`/api/notifications` and uses browser notifications after permission is granted.
Message notifications can be acknowledged with `ack:` or snoozed with
`snooze_until:`. The watcher can persist seen notification IDs with
`notifications.state_file`. The same `notify` command can send due
notifications as a plain-text email batch:

```sh
python -m lifetxt notify life.txt --recipient self --email --email-to me@example.com --dry-run
python -m lifetxt notify life.txt --watch --email --email-to me@example.com --interval 60
```

SMTP credentials are read from environment variables such as
`LIFETXT_SMTP_HOST`, `LIFETXT_SMTP_USER`, and `LIFETXT_SMTP_PASS`; do not store
SMTP passwords in life.txt content.

Journal / diary records use type `J`; aliases include `journal`, `diary`,
`log`, and `entry`. `[N]` is the recommended status. Use `body:` for long text;
continuation lines beginning with `|` attach multiline body text to the previous
item.
`body:` is also useful outside `J` for detailed tasks, event descriptions,
messages, and notes. Use `note:` for short side notes and `body:` for long-form
content.

External JSON config is available with `--config FILE`, `LIFETXT_CONFIG`,
`.lifetxt.json`, or `lifetxt.config.json`. Use `python -m lifetxt config init`
to create a starter file with default paths, web settings, message defaults,
notification settings, user name, user/team/tag aliases, automatic ID settings, and iCalendar sync
sources. With `ids.auto: true`, created items receive an `id:` when omitted;
existing IDs are checked across configured input files and `write_file` before
writing. Duplicate IDs are reported as warning `W213`. Use `python -m lifetxt ids
life.txt` to audit present, missing, and duplicate IDs. Use `ids --assign` with
`--dry-run` first to backfill IDs safely. Set `ids.key` / `api.id_key` to use a
custom ID detail key.

Items can link to other records by ID. Use `parent:` for hierarchy or message
threads, `ref:` for a generic reference, `depends_on:` for prerequisites,
`blocks:` for blocked downstream work, and `related:` for loose links. The
`check` command warns about missing references, self references, and `parent:`
cycles. It also warns when a completed item still depends on an open
prerequisite. `agenda` and `health` surface open items blocked by open
prerequisites. Use `python -m lifetxt links life.txt` to inspect these relationships.
Use `python -m lifetxt links life.txt --relation depends_on --relation blocks`
to focus on dependency edges.

Indented item lines can also express hierarchy. If a child line is indented and
does not already have `parent:`, the parser infers `parent:` from the nearest
less-indented ancestor that has an `id:`.

```txt
[ ] T Research_Project id:proj_research
  [ ] T Literature_Review id:task_lit
    [N] N Reading_Memo
```

Basic VS Code syntax highlighting and snippets are available in
[../../editors/vscode/lifetxt](../../editors/vscode/lifetxt). See
[editor.md](./editor.md) for editor setup and the planned language-server
direction.

## JSON Shape

Details are always represented as arrays so repeated keys round-trip safely:

```json
{
  "status": "[ ]",
  "type": "T",
  "title": "Create_Slides",
  "details": {
    "project": ["research"],
    "tag": ["important", "thesis"]
  }
}
```

## Tests

```sh
python -m unittest discover
```
