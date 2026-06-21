# life.txt

`life.txt` is a plain-text format for managing tasks, events, deadlines,
reminders, habits, status / presence records, messages, and notes in one
human-readable file.

See [life_txt_format_spec.md](./life_txt_format_spec.md) for the format
specification.

## Minimal life.txt

```txt
[ ] T Write_Report due:2026-06-12 project:university assignee:alice
[ ] E Seminar from:2026-06-08T13:00 to:2026-06-08T14:30 loc:university attendee:alice
[/] S Working from:2026-06-06T14:00 state:busy person:self
[ ] M "Review slides" sender:self recipient:alice notify_at:2026-06-06T09:00 channel:teams
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
python -m lifetxt import-ics google_calendar.ics -o life.txt --append --tag google
python -m lifetxt sync-ics --url-env LIFETXT_GOOGLE_CAL_ICS -o .generated/google_calendar.life.txt --cache-dir .cache/lifetxt --tag google
python -m lifetxt filter life.txt --open --type task -o open_tasks.life.txt
python -m lifetxt filter life.txt --open --type task --canonical -o canonical_tasks.life.txt
python -m lifetxt filter life.txt --assignee alice -o alice_items.life.txt
python -m lifetxt filter life.txt --after now --type event -o future_schedule.life.txt
python -m lifetxt filter life.txt --type status --person self -o my_status.life.txt
python -m lifetxt filter life.txt --type message --recipient alice -o alice_messages.life.txt
python -m lifetxt status life.txt
python -m lifetxt status life.txt --active
python -m lifetxt status life.txt --format json --pretty
python -m lifetxt notify life.txt --recipient self
python -m lifetxt notify life.txt --watch --interval 30
python -m lifetxt ids life.txt --assign --dry-run
python -m lifetxt agenda life.txt --from 2026-06-06T13:00 --to 2026-06-06T18:00
python -m lifetxt agenda life.txt --around now --window 1w --format life -o agenda.life.txt
python -m lifetxt agenda life.txt --from 2026-06-06 --to 2026-06-06 --open
python -m lifetxt agenda life.txt --from 2026-06-06 --to 2026-06-06 --type task --project research
python -m lifetxt from-json life.json -o life.txt
python -m lifetxt from-jsonl life.jsonl -o life.txt
python -m lifetxt serve life.txt --host 127.0.0.1 --port 8000
python -m lifetxt config init -o .lifetxt.json
```

Install locally as a command:

```sh
python -m pip install -e .
lifetxt check examples/minimal_life.txt
```

Most file-reading commands accept multiple input paths. The `filter`,
`to-json`, and `to-jsonl` commands support item filters such as `--open`,
`--status`, `--type`, `--project`, `--tag`, `--person`, `--owner`,
`--assignee`, `--attendee`, `--sender`, `--recipient`, `--detail`, `--text`,
`--after`, and `--before`.
`filter --format life` preserves original matching item lines by default; use
`--canonical` to regenerate normalized life.txt lines. Use `person:` for
status / presence targets, `assignee:` for assigned work, `owner:` for
accountability, and `attendee:` for event participants.

The `import-ics` command converts iCalendar `.ics` files, such as Google
Calendar exports, to `E` event items. Timed events become `from:` / `to:`,
all-day events become `on:`, participants become `attendee:`, and `--append`
can add imported events to an existing `life.txt`.

For periodic calendar sync, use `sync-ics` with a secret iCalendar URL stored in
an environment variable. Keep manually edited items in `life.txt`, write
ICS-derived items to a generated file such as `.generated/google_calendar.life.txt`,
and pass both files to commands such as `agenda` or `check`.

The optional web interface is installed separately:

```sh
pip install -r requirements-web.txt
python -m lifetxt serve life.txt
```

## Assist

Input assistance is available in both non-interactive and interactive modes:

```sh
python -m lifetxt assist --type task --title "Write Report" --due 2026-06-12 --project university --tag report
python -m lifetxt assist --type status --title "Working" --from 2026-06-06T14:00 --state busy --person self
python -m lifetxt assist --type message --title "Review Slides" --sender self --recipient alice --notify_at 2026-06-06T09:00
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

Agenda filters can be combined:

```sh
python -m lifetxt agenda life.txt --from 2026-06-06 --to 2026-06-06 --open
python -m lifetxt agenda life.txt --from 2026-06-06 --to 2026-06-06 --status todo --type task
python -m lifetxt agenda life.txt --from 2026-06-06 --to 2026-06-06 --project research --tag urgent
python -m lifetxt agenda life.txt --from 2026-06-06 --to 2026-06-06 --detail priority=A --text report
```

`--open` means unfinished workflow items only: `[ ]`, `[/]`, `[>]`, and `[?]`.
Repeated `--detail key=value` filters are ANDed. `--window` accepts seconds,
minutes, hours, days, weeks, months approximated as 30 days, and years
approximated as 365 days.

Message records use type `M`. They require `sender:` and `recipient:` and can
use `notify_at:` for one notification time or `notify_from:` / `notify_to:` for
a notification window. The web API also provides `/api/messages` for convenient
message listing and creation. `/api/items/id/{id}` and `/api/messages/id/{id}`
support id-based access, while `/api/messages/thread/{id}` and
`/api/messages/id/{id}/reply` support message threads via `parent:`.

Use `python -m lifetxt notify life.txt --watch` as a resident notification
watcher. The browser GUI also has an `Enable Notifications` button that polls
`/api/notifications` and uses browser notifications after permission is granted.
Message notifications can be acknowledged with `ack:` or snoozed with
`snooze_until:`. The watcher can persist seen notification IDs with
`notifications.state_file`.

External JSON config is available with `--config FILE`, `LIFETXT_CONFIG`,
`.lifetxt.json`, or `lifetxt.config.json`. Use `python -m lifetxt config init`
to create a starter file with default paths, web settings, message defaults,
notification settings, user name, automatic ID settings, and iCalendar sync
sources. With `ids.auto: true`, created items receive an `id:` when omitted;
existing IDs are checked across configured input files and `write_file` before
writing. Duplicate IDs are reported as warning `W213`. Use `python -m lifetxt ids
life.txt` to audit present, missing, and duplicate IDs. Use `ids --assign` with
`--dry-run` first to backfill IDs safely.

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
