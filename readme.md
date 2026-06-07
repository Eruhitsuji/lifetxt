# life.txt

`life.txt` is a plain-text format for managing tasks, events, deadlines, reminders, habits, status / presence records, and notes in a single human-readable file.
Please refer to [life_txt_format_spec.md](./life_txt_format_spec.md) for the detailed grammar of the `life.txt`.

## Documentation

- [English documentation](./docs/en/readme.md)
- [Japanese documentation](./docs/ja/readme.md)
- [English CLI guide](./docs/en/cli.md)
- [Japanese CLI guide](./docs/ja/cli.md)
- [English format specification](./docs/en/life_txt_format_spec.md)
- [Japanese format specification](./docs/ja/life_txt_format_spec.md)

## Minimal life.txt

```txt
[ ] T Write_Report due:2026-06-12 project:university
[ ] E Seminar from:2026-06-08T13:00 to:2026-06-08T14:30 loc:university
[/] S Working from:2026-06-06T14:00 state:busy person:self
[N] N Research_Memo project:research
```

More sample files are available in [examples/](./examples/):

- [minimal_life.txt](./examples/minimal_life.txt): a compact starter file
- [tasks_life.txt](./examples/tasks_life.txt): tasks, deadlines, and notes
- [events_life.txt](./examples/events_life.txt): calendar-style event records
- [habits_reminders_life.txt](./examples/habits_reminders_life.txt): habits and reminders
- [status_presence.txt](./examples/status_presence.txt): personal presence records
- [team_status_life.txt](./examples/team_status_life.txt): multi-person status records
- [agenda_life.txt](./examples/agenda_life.txt): data for the `agenda` command
- [json_roundtrip_life.txt](./examples/json_roundtrip_life.txt): repeated keys and quoted values

## Tools

This repository includes a dependency-free Python CLI:

```sh
python -m lifetxt check life.txt
python -m lifetxt to-json life.txt --pretty
python -m lifetxt to-jsonl life.txt --open --type task -o open_tasks.jsonl
python -m lifetxt filter life.txt --open --type task -o open_tasks.life.txt
python -m lifetxt filter life.txt --open --type task --canonical -o canonical_tasks.life.txt
python -m lifetxt filter life.txt --after now --type event -o future_schedule.life.txt
python -m lifetxt filter life.txt --type status --person self -o my_status.life.txt
python -m lifetxt status life.txt
python -m lifetxt status life.txt --active
python -m lifetxt status life.txt --format json --pretty
python -m lifetxt agenda life.txt --from 2026-06-06T13:00 --to 2026-06-06T18:00
python -m lifetxt agenda life.txt --around now --window 1w --format life -o agenda.life.txt
python -m lifetxt agenda life.txt --from 2026-06-06 --to 2026-06-06 --open
python -m lifetxt agenda life.txt --from 2026-06-06 --to 2026-06-06 --type task --project research
python -m lifetxt from-json life.json -o life.txt
python -m lifetxt from-jsonl life.jsonl -o life.txt
```

Most file-reading commands accept multiple input paths. The `filter`,
`to-json`, and `to-jsonl` commands support item filters such as `--open`,
`--status`, `--type`, `--project`, `--tag`, `--person`, `--detail`,
`--text`, `--after`, and `--before`. `filter --format life` preserves original
matching item lines by default; use `--canonical` to regenerate normalized
life.txt lines.

The `status` command prints the latest `S` status / presence item for each
`person:`. If `person:` is omitted, it is treated as `self` for this summary.
The latest item is selected by the newest `from:` datetime. Use `--person NAME`
to filter one person, `--active` to ignore finished logs with `to:`, or
`--format json` / `--format jsonl` for machine-readable output.

The `agenda` command prints items related to a datetime range. `from/to` and
`on` are treated as intervals, while `due`, `do`, `at`, and `moved_to` are
treated as points or all-day spans. Use `--around now --window 2h` for a
near-current-time view, or `--format life`, `json`, or `jsonl` for other output.
Use `--open` for unfinished workflow items only, or combine filters such as
`--status`, `--type`, `--project`, `--tag`, `--person`, `--detail key=value`,
and `--text`. `--window` accepts seconds, minutes, hours, days, weeks, months
approximated as 30 days, and years approximated as 365 days.

Input assistance is available in both non-interactive and interactive modes:

```sh
python -m lifetxt assist --type task --title "Write Report" --due 2026-06-12 --project university --tag report
python -m lifetxt assist --type status --title "Working" --from 2026-06-06T14:00 --state busy --person self
python -m lifetxt assist --type task --title "Write Report" --due 2026-06-12 --output new_life.txt
python -m lifetxt assist --type task --title "Write Report" --due 2026-06-12 --append life.txt
python -m lifetxt assist --interactive --append life.txt
```

In create mode, `assist --output FILE` appends the generated line to `FILE`.
It does not overwrite existing content.

In interactive mode, enter `?`, `?type`, `?status`, or `?detail` at a prompt
to show contextual help. At the detail prompt, use `?due` or another `?key`
form for key-specific help. When the terminal supports it, Tab completes type,
status, and detail-key candidates, and Up/Down recall previous inputs. Use
`--no-completion` to disable the line editing helpers.

Existing data can be updated by line number or by `id:`. Updates are written
in-place unless `--output` is specified.

```sh
python -m lifetxt assist --update life.txt --match-id task_001 --status done --done 2026-06-06
python -m lifetxt assist --update life.txt --line 3 --title "New Title" --add-detail tag=important
python -m lifetxt assist --update life.txt --match-id task_001 --remove-detail tag --output updated_life.txt
```

The `check` command reports syntax errors and semantic warnings such as invalid status/type values, malformed `key:value` details, note status/type mismatches, date/time format issues, unusual key style, and event ranges where `to:` is earlier than `from:`.
For `type:S` status / presence records, `from:` and `state:` are required. `[/]` is recommended when the record has no `to:`, and `[x]` is recommended when `to:` is present.

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

Run tests with:

```sh
python -m unittest discover
```
