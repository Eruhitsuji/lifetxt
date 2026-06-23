# life.txt CLI Guide

This document describes the command-line interface provided by:

```sh
python -m lifetxt
```

The CLI is dependency-free and reads UTF-8 `life.txt`, JSON, JSONL, or CSV files.
Most file-reading commands accept one or more paths. Use `-` or omit paths to
read from standard input.

## 1. Command Overview

```sh
python -m lifetxt check [path ...]
python -m lifetxt ids [path ...]
python -m lifetxt links [path ...]
python -m lifetxt to-json [path ...]
python -m lifetxt to-jsonl [path ...]
python -m lifetxt import-ics [path ...]
python -m lifetxt sync-ics --url-env ENVVAR
python -m lifetxt filter [path ...]
python -m lifetxt from-json [path ...]
python -m lifetxt from-jsonl [path ...]
python -m lifetxt status [path ...]
python -m lifetxt notify [path ...]
python -m lifetxt agenda [path ...]
python -m lifetxt assist [options]
python -m lifetxt serve [path ...]
python -m lifetxt config init
```

| Command | Purpose |
|---|---|
| `check` | Validate life.txt syntax and semantic warnings |
| `ids` | Audit present, missing, and duplicate item IDs |
| `links` | Inspect ID-based references between items |
| `to-json` | Convert life.txt to a JSON array |
| `to-jsonl` | Convert life.txt to JSONL |
| `to-csv` | Convert life.txt to CSV |
| `import-ics` | Convert iCalendar `.ics` events to life.txt event items |
| `sync-ics` | Fetch iCalendar URLs and regenerate life.txt event items |
| `filter` | Filter items and output life.txt, JSON, or JSONL |
| `from-json` | Convert JSON to life.txt |
| `from-jsonl` | Convert JSONL to life.txt |
| `from-csv` | Convert CSV to life.txt |
| `status` | Show the latest `S` status / presence record for each person |
| `notify` | Show or watch due type `M` message notifications |
| `agenda` | Show items related to a datetime range |
| `assist` | Create or update life.txt items from prompts or flags |
| `serve` | Run the optional FastAPI REST API and browser GUI |
| `config` | Create or inspect an external JSON config file |

## 2. Common Conventions

### 2.0 External Config

Any command may receive `--config FILE` before or after the subcommand. If it is
omitted, the CLI checks `LIFETXT_CONFIG`, `.lifetxt.json`, and
`lifetxt.config.json` in that order.

```sh
python -m lifetxt config init -o .lifetxt.json
python -m lifetxt --config .lifetxt.json check
python -m lifetxt agenda --config .lifetxt.json --around now --window 1d
```

`paths` supplies default input files for life.txt-reading commands, `write_file`
supplies the default writable file for `serve`, `web` supplies server defaults,
`message` supplies assist defaults for type `M`, and `sync_ics` supplies default
calendar sync sources and output.

### 2.1 Input Paths

For commands that read files, `path ...` is optional and may contain multiple
files. Multiple inputs are read in order. Paths may be glob patterns such as
`*.life.txt` or `projects/**/*.life.txt`. When a directory is passed, the CLI
reads life.txt-like `.txt` files in that directory.

```sh
python -m lifetxt check life.txt
python -m lifetxt check work.life.txt home.life.txt
python -m lifetxt check "projects/**/*.life.txt"
python -m lifetxt check examples
python -m lifetxt check -
type life.txt | python -m lifetxt check
```

If paths are omitted or the path is `-`, the command reads from stdin.
When multiple input paths are used, diagnostics include the source path before
the line and column number.

### 2.2 Output Paths

Commands with `-o` / `--output` write to a file. Without `--output`, output is
written to stdout.

For `assist` create mode, `--output FILE` appends the generated line to `FILE`.
It does not overwrite the file. In `assist --update` mode, `--output FILE`
writes the updated whole file to `FILE`.
Whole-file writes use a temporary file and atomic replace. For bulk ID backfill,
use `ids --assign --backup` to keep a `FILE.bak` copy before writing.

### 2.3 Output Formats

Several commands support machine-readable output.

| Format | Meaning |
|---|---|
| `text` | Human-readable table or diagnostics |
| `life` | life.txt lines |
| `json` | JSON array |
| `jsonl` | One JSON object per line |

### 2.4 Exit Codes

| Code | Meaning |
|---|---|
| `0` | Success |
| `1` | Validation error or command error |
| `2` | CLI usage error, such as missing subcommand |

## 3. `check`

Validate life.txt syntax and semantic rules.

```sh
python -m lifetxt check [path ...] [--format text|json] [--warnings-as-errors]
```

Options:

| Option | Meaning |
|---|---|
| `path ...` | Input file(s), or `-` for stdin |
| `--format text` | Print human-readable diagnostics |
| `--format json` | Print diagnostics as JSON |
| `--warnings-as-errors` | Exit non-zero when warnings are present |

Examples:

```sh
python -m lifetxt check life.txt
python -m lifetxt check life.txt --warnings-as-errors
python -m lifetxt check life.txt --format json
```

### 3.1 `ids`

Audit item IDs without changing files.

```sh
python -m lifetxt ids [path ...] [--only all|present|missing|duplicates]
```

Options:

| Option | Meaning |
|---|---|
| `path ...` | Input file(s), or `-` for stdin |
| `--key KEY` | Detail key to audit; defaults to config `ids.key`, `api.id_key`, or `id` |
| `--only all` | Show summary, duplicate IDs, and missing IDs |
| `--only present` | Show all present ID values |
| `--only missing` | Show items without the selected ID key |
| `--only duplicates` | Show duplicate ID values only |
| `--format text|json|jsonl` | Output format |
| `--pretty` | Pretty-print JSON output |
| `--assign` | Assign IDs to items missing the selected ID key |
| `--dry-run` | Show planned assignments without writing files |
| `--backup` | Write `FILE.bak` before modifying a file with `--assign` |
| `--prefix PREFIX` | ID prefix for `--assign`; defaults to the configured type prefix |

Examples:

```sh
python -m lifetxt ids life.txt
python -m lifetxt ids life.txt archive.life.txt --only duplicates
python -m lifetxt ids life.txt --only missing --format json --pretty
python -m lifetxt ids life.txt --assign --dry-run
python -m lifetxt ids life.txt --assign --backup
python -m lifetxt ids "projects/**/*.life.txt" --assign --prefix item --dry-run
```

### 3.2 `links`

Inspect relationships that point to item IDs. The command understands
`parent:`, `ref:`, `depends_on:`, `blocks:`, and `related:`.

```sh
python -m lifetxt links [path ...]
python -m lifetxt links life.txt --id task_report --direction incoming
python -m lifetxt links life.txt --id task_report --direction outgoing --format json --pretty
python -m lifetxt links life.txt --relation depends_on --relation blocks
```

Options:

| Option | Meaning |
|---|---|
| `--id ID` | Show only links connected to this ID |
| `--direction incoming|outgoing|both` | Direction when `--id` is used |
| `--relation RELATION` | Limit to a relation key such as `depends_on`; repeatable or comma-separated |
| `--key KEY` | ID detail key; defaults to config `ids.key`, `api.id_key`, or `id` |
| `--format text|json|jsonl` | Output format |
| `--pretty` | Pretty-print JSON |

`check` reports missing references (`W215`), self references (`W216`),
`parent:` cycles (`W217`), and ambiguous references (`W218`).

## 4. JSON Conversion

### 4.1 `to-json`

Convert life.txt to a JSON array.

```sh
python -m lifetxt to-json [path ...] [-o output.json] [--pretty] [filter options]
```

Options:

| Option | Meaning |
|---|---|
| `path ...` | Input life.txt file(s), or `-` for stdin |
| `-o`, `--output` | Output file; defaults to stdout |
| `--pretty` | Pretty-print JSON |
| `filter options` | Same item filters as `filter` |

### 4.2 `to-jsonl`

Convert life.txt to JSONL.

```sh
python -m lifetxt to-jsonl [path ...] [-o output.jsonl] [filter options]
```

### 4.3 `from-json`

Convert a JSON item, JSON item array, or `{ "items": [...] }` object to
life.txt.

```sh
python -m lifetxt from-json [path ...] [-o life.txt]
```

### 4.4 `from-jsonl`

Convert JSONL to life.txt.

```sh
python -m lifetxt from-jsonl [path ...] [-o life.txt]
```

### 4.5 `to-csv`

Convert life.txt to CSV. The CSV contains `status`, `type`, and `title`
columns plus one column for each detail key found in the selected items.
Repeated detail values are stored as a JSON array inside the cell. Multiline
`body:` values are stored as normal quoted CSV cells.

```sh
python -m lifetxt to-csv [path ...] [-o output.csv] [filter options]
python -m lifetxt to-csv life.txt --type journal --project research -o journal.csv
```

### 4.6 `from-csv`

Convert CSV back to life.txt. CSV input requires `status`, `type`, and `title`
columns. All other non-empty columns become detail keys. Cells containing a JSON
array become repeated detail values.

```sh
python -m lifetxt from-csv [path ...] [-o life.txt]
```

### 4.7 Export Filter Options

`to-json`, `to-jsonl`, and `to-csv` can filter items before writing output.

| Option | Meaning |
|---|---|
| `--open` | Keep unfinished workflow items only: `[ ]`, `[/]`, `[>]`, `[?]` |
| `--status VALUE` | Filter by status or alias; repeatable or comma-separated |
| `--type VALUE` | Filter by type or alias; repeatable or comma-separated |
| `--project VALUE` | Filter by `project:`; repeatable or comma-separated |
| `--tag VALUE` | Filter by `tag:`; repeatable or comma-separated |
| `--tag-all VALUE` | Require every listed `tag:` value |
| `--exclude-tag VALUE` | Exclude items containing any listed `tag:` value |
| `--user VALUE` | Filter across `user`, `person`, `owner`, `assignee`, `attendee`, `sender`, and `recipient` |
| `--team VALUE` | Filter by `team:` / `group:` or config-defined team membership |
| `--person VALUE` | Filter by `person:`; missing `person:` on `S` items means `self` |
| `--owner VALUE` | Filter by `owner:`; repeatable or comma-separated |
| `--assignee VALUE` | Filter by `assignee:`; repeatable or comma-separated |
| `--attendee VALUE` | Filter by `attendee:`; repeatable or comma-separated |
| `--sender VALUE` | Filter by `sender:`; repeatable or comma-separated |
| `--recipient VALUE` | Filter by `recipient:`; repeatable or comma-separated |
| `--detail FILTER` | Filter by detail key or `key=value`; repeatable and ANDed |
| `--text TEXT` | Case-insensitive substring search over title, line, and details |
| `--after VALUE` | Keep items related to this time or later |
| `--before VALUE` | Keep items related to this time or earlier |

`--after` and `--before` accept `now`, `YYYY-MM-DD`, or ISO-like datetimes such
as `YYYY-MM-DDTHH:MM`, `YYYY-MM-DDTHH:MM:SS`,
`YYYY-MM-DDTHH:MM:SS.5`, `YYYY-MM-DDTHH:MM+09:00`, or
`YYYY-MM-DDTHH:MM:SS.25+09:00`. They use the same time matching rules as
`agenda`. Time-only `at:HH:MM` values without an `on:` date are not matched by
one-sided `--after` or `--before` filters, because they have no date anchor.

`--user`, `--team`, and `--tag` use aliases from config `users`, `teams`, and
`tags.aliases` / `tags.groups` when available.

Examples:

```sh
python -m lifetxt to-json life.txt --open --type task --pretty
python -m lifetxt to-jsonl work.life.txt home.life.txt --project research
python -m lifetxt to-json life.txt --assignee alice --pretty
python -m lifetxt to-json life.txt --recipient alice --type message --pretty
python -m lifetxt to-json life.txt --after now --type event -o future_events.json
python -m lifetxt to-json "projects/**/*.life.txt" --team research --tag-all urgent,review
```

## 5. iCalendar Import And Sync

### 5.1 `import-ics`

Convert iCalendar `.ics` files, such as Google Calendar exports, to life.txt
event items.

```sh
python -m lifetxt import-ics [path ...] [-o life.txt] [--append] [--project PROJECT] [--tag TAG]
```

Options:

| Option | Meaning |
|---|---|
| `path ...` | Input `.ics` file(s), or `-` for stdin |
| `-o`, `--output` | Output file; defaults to stdout |
| `--append` | Append to `--output` instead of overwriting it |
| `--project PROJECT` | Add `project:PROJECT` to every imported event |
| `--tag TAG` | Add `tag:TAG` to every imported event; repeatable |

Mapping:

| iCalendar field | life.txt output |
|---|---|
| `VEVENT` | `E` item |
| `SUMMARY` | title |
| `UID` | `id:` |
| `DTSTART` / `DTEND` | `from:` / `to:` for timed events |
| `DTSTART;VALUE=DATE` | `on:` for all-day events |
| `LOCATION` | `loc:` |
| `DESCRIPTION` | `note:` |
| `URL` | `url:` |
| `ORGANIZER` | `owner:` |
| `ATTENDEE` | repeated `attendee:` |
| `CATEGORIES` | repeated `tag:` |
| `RRULE` | `repeat:RRULE:...` |
| `STATUS:CANCELLED` | `[-]` with `reason:canceled` |
| `STATUS:TENTATIVE` | `[?]` |

Notes:

- Only `VEVENT` components are imported.
- Google Calendar all-day `DTEND` values are exclusive. Multi-day all-day
  events become repeated `on:` values.
- `TZID` local wall times are kept as written. UTC `Z` datetimes are converted
  to the machine's local timezone before writing `YYYY-MM-DDTHH:MM`.
- `RRULE` values are preserved but not expanded into individual events.

Examples:

```sh
python -m lifetxt import-ics google_calendar.ics
python -m lifetxt import-ics google_calendar.ics -o imported_events.life.txt
python -m lifetxt import-ics google_calendar.ics -o life.txt --append --tag google
python -m lifetxt import-ics work.ics personal.ics --project calendar
```

Example output:

```txt
[ ] E "Research Meeting" id:event-1@example.com from:2026-06-08T13:00 to:2026-06-08T14:30 loc:"Meeting Room A" owner:"Prof. Smith" attendee:Alice tag:google
```

### 5.2 `sync-ics`

Fetch one or more iCalendar URLs and regenerate a generated life.txt file.
This is the recommended mode for periodic sync because the output file is
overwritten, so events are not duplicated on each run.

```sh
python -m lifetxt sync-ics --url-env LIFETXT_GOOGLE_CAL_ICS -o .generated/google_calendar.life.txt --cache-dir .cache/lifetxt --tag google
```

Options:

| Option | Meaning |
|---|---|
| `--url URL` | iCalendar URL to fetch; repeatable |
| `--url-env ENVVAR` | Environment variable containing an iCalendar URL; repeatable |
| `-o`, `--output` | Generated life.txt output; defaults to stdout |
| `--cache-dir DIR` | Save raw downloaded `.ics` snapshots in this directory |
| `--dry-run` | Fetch and print generated life.txt without writing output or cache files |
| `--project PROJECT` | Add `project:PROJECT` to every synced event |
| `--tag TAG` | Add `tag:TAG` to every synced event; repeatable |
| `--timeout SECONDS` | Fetch timeout; defaults to 30 |
| `--user-agent VALUE` | HTTP User-Agent header |

Use `--url-env` for secret iCalendar URLs so the URL is not stored in shell
history, scripts, or documentation.

PowerShell example:

```powershell
$env:LIFETXT_GOOGLE_CAL_ICS = "https://calendar.google.com/calendar/ical/..."
New-Item -ItemType Directory -Force .generated, .cache/lifetxt
python -m lifetxt sync-ics --url-env LIFETXT_GOOGLE_CAL_ICS -o .generated/google_calendar.life.txt --cache-dir .cache/lifetxt --tag google
python -m lifetxt check life.txt .generated/google_calendar.life.txt
python -m lifetxt agenda life.txt .generated/google_calendar.life.txt --around now --window 1d
```

For periodic sync, put the same commands in a `.ps1` file and run it with
Windows Task Scheduler. Keep manually edited items in your main `life.txt` and
ICS-derived items in `.generated/*.life.txt`; pass both files to commands such
as `agenda`, `filter`, `to-json`, and `check`.

## 6. `filter`

Filter parsed life.txt items and output the result as life.txt, JSON, or JSONL.
This is useful when you want to materialize a subset as another `life.txt`
file.

```sh
python -m lifetxt filter [path ...] [filter options] [--format life|json|jsonl] [-o output]
```

Options:

| Option | Meaning |
|---|---|
| `path ...` | Input life.txt file(s), or `-` for stdin |
| `--format life` | Output matching life.txt lines; this is the default |
| `--format json` | Output a JSON array |
| `--format jsonl` | Output JSONL |
| `-o`, `--output` | Output file; defaults to stdout |
| `--pretty` | Pretty-print JSON output |
| `--canonical` | Regenerate normalized life.txt lines instead of preserving original item lines |

Filter options are the same as the export filter options in section 4.5.
With `--format life`, original matching item lines are preserved by default.
Use `--canonical` when you want normalized quoting and spacing.

Examples:

```sh
python -m lifetxt filter life.txt --open --type task -o open_tasks.life.txt
python -m lifetxt filter life.txt --open --type task --canonical -o canonical_tasks.life.txt
python -m lifetxt filter life.txt --assignee alice -o alice_items.life.txt
python -m lifetxt filter life.txt --recipient alice --type message -o alice_messages.life.txt
python -m lifetxt filter life.txt --after now --type event -o future_schedule.life.txt
python -m lifetxt filter life.txt --type status --person self -o my_status.life.txt
python -m lifetxt filter work.life.txt home.life.txt --project research --format json --pretty
python -m lifetxt filter "projects/**/*.life.txt" --team research --tag-all urgent,review --exclude-tag archived
```

## 7. `status`

Show the latest `S` status / presence record for each person.

```sh
python -m lifetxt status [path ...] [--format text|json|jsonl] [--person PERSON] [--active] [--pretty]
```

Selection rules:

- Only type `S` items are considered.
- Records are grouped by `person:`.
- Missing `person:` is treated as `self`.
- The latest record is the item with the newest `from:` datetime.
- With `--active`, finished logs with `to:` are ignored.

Options:

| Option | Meaning |
|---|---|
| `path ...` | Input life.txt file(s), or `-` for stdin |
| `--format text` | Print a table |
| `--format json` | Print a JSON array |
| `--format jsonl` | Print JSONL |
| `--person PERSON` | Show only one person |
| `--active` | Only consider active status items without `to:` |
| `--pretty` | Pretty-print JSON output |

Examples:

```sh
python -m lifetxt status life.txt
python -m lifetxt status life.txt --active
python -m lifetxt status life.txt --person self
python -m lifetxt status life.txt --format json --pretty
```

## 8. `notify`

Show due type `M` message notifications once, or keep a resident watcher
running with `--watch`.

```sh
python -m lifetxt notify [path ...] [--recipient PERSON] [--watch]
```

Selection rules:

- Only type `M` items are considered.
- Only open workflow statuses are considered: `[ ]`, `[/]`, `[>]`, and `[?]`.
- `recipient:` must match the selected recipient.
- `notify_at:` is a one-time notification.
- `notify_from:` / `notify_to:` is an active notification period.
- Items with `ack:` are treated as acknowledged and are not notified.
- Items with future `snooze_until:` are temporarily suppressed.

Options:

| Option | Meaning |
|---|---|
| `path ...` | Input life.txt file(s), or `-` for stdin |
| `--recipient PERSON` | Recipient; defaults to `notifications.recipient` or `user.name` from config |
| `--lookahead VALUE` | Future notification window, such as `0m`, `5m`, or `1h` |
| `--grace VALUE` | Past grace window for missed notifications |
| `--watch` | Stay running and poll repeatedly |
| `--interval SECONDS` | Poll interval for `--watch` |
| `--desktop` | Also show a simple desktop notification when supported |
| `--state-file PATH` | Persist seen notification IDs for `--watch` |
| `--no-state` | Disable persistent seen-state for `--watch` |
| `--format text|json|jsonl` | Output format in one-shot mode |

Examples:

```sh
python -m lifetxt notify life.txt --recipient self
python -m lifetxt notify life.txt --recipient self --format json --pretty
python -m lifetxt notify life.txt --watch --interval 30
```

## 9. `agenda`

Show items related to a datetime range.

```sh
python -m lifetxt agenda [path ...] [range options] [filter options] [output options]
```

Range matching rules:

- `from/to` is treated as an interval.
- `notify_from/notify_to` is treated as a message notification interval.
- `on` is treated as an all-day interval.
- `due`, `do`, `at`, `moved_to`, and `notify_at` are treated as point times or all-day spans.
- Type `S` records without `to:` are treated as ongoing from `from:`.
- `at:HH:MM` is combined with `on:` when present, otherwise with each date in the requested range.
- Simple `repeat:` values are expanded for `daily`, `weekly`, `monthly`, `yearly`, and `weekdays`.
- `interval:`, `until:`, and `count:` constrain simple recurrence expansion.
- Floating repeated `at:` values without `on:` are expanded only inside bounded agenda ranges.

### 9.1 Range Options

| Option | Meaning |
|---|---|
| `--from VALUE` | Range start: `now`, date, or ISO-like datetime |
| `--to VALUE` | Range end: `now`, date, or ISO-like datetime |
| `--around VALUE` | Range center; defaults to `now` |
| `--window VALUE` | Half-width for `--around`; defaults to `1h` |

Use either `--from/--to` or `--around`. If no range is specified, the command
uses `--around now --window 1h`.

Duration values for `--window`:

| Form | Meaning |
|---|---|
| `15s` | 15 seconds |
| `30m` | 30 minutes |
| `2h` | 2 hours |
| `1d` | 1 day |
| `1w` | 1 week |
| `1mo` | 1 month, approximated as 30 days |
| `1y` | 1 year, approximated as 365 days |
| `30` | 30 minutes |

Examples:

```sh
python -m lifetxt agenda life.txt --from 2026-06-06 --to 2026-06-06
python -m lifetxt agenda life.txt --from 2026-06-06T13:00 --to 2026-06-06T18:00
python -m lifetxt agenda life.txt --from 2026-06-06T13:00:30.25+09:00 --to 2026-06-06T18:00:00.5+09:00
python -m lifetxt agenda life.txt --around now --window 2h
python -m lifetxt agenda life.txt --around now --window 1w
python -m lifetxt agenda life.txt --from 2026-06-01 --to 2026-06-30 --type habit
```

### 9.2 Filter Options

| Option | Meaning |
|---|---|
| `--open` | Show unfinished workflow items only: `[ ]`, `[/]`, `[>]`, `[?]` |
| `--status VALUE` | Filter by status or alias; repeatable or comma-separated |
| `--type VALUE` | Filter by type or alias; repeatable or comma-separated |
| `--project VALUE` | Filter by `project:`; repeatable or comma-separated |
| `--tag VALUE` | Filter by `tag:`; repeatable or comma-separated |
| `--tag-all VALUE` | Require every listed `tag:` value |
| `--exclude-tag VALUE` | Exclude items containing any listed `tag:` value |
| `--user VALUE` | Filter across user-related details |
| `--team VALUE` | Filter by `team:` / `group:` or config-defined team membership |
| `--person VALUE` | Filter by `person:`; repeatable or comma-separated |
| `--owner VALUE` | Filter by `owner:`; repeatable or comma-separated |
| `--assignee VALUE` | Filter by `assignee:`; repeatable or comma-separated |
| `--attendee VALUE` | Filter by `attendee:`; repeatable or comma-separated |
| `--sender VALUE` | Filter by `sender:`; repeatable or comma-separated |
| `--recipient VALUE` | Filter by `recipient:`; repeatable or comma-separated |
| `--detail FILTER` | Filter by detail key or `key=value`; repeatable and ANDed |
| `--text TEXT` | Case-insensitive substring search over title, line, and details |

Examples:

```sh
python -m lifetxt agenda life.txt --from 2026-06-06 --to 2026-06-06 --open
python -m lifetxt agenda life.txt --from 2026-06-06 --to 2026-06-06 --status todo --type task
python -m lifetxt agenda life.txt --from 2026-06-06 --to 2026-06-06 --project research --tag urgent
python -m lifetxt agenda life.txt --from 2026-06-06 --to 2026-06-06 --team research --tag-all urgent,review
python -m lifetxt agenda life.txt --from 2026-06-06 --to 2026-06-06 --assignee alice
python -m lifetxt agenda life.txt --from 2026-06-06 --to 2026-06-06 --recipient alice
python -m lifetxt agenda life.txt --from 2026-06-06 --to 2026-06-06 --detail priority=A --text report
python -m lifetxt agenda life.txt --from 2026-06-06 --to 2026-06-06 --person alice
```

`--detail key` checks that the key exists. `--detail key=value` checks for an
exact detail value. Multiple `--detail` filters are ANDed.

### 9.3 Output Options

| Option | Meaning |
|---|---|
| `--format text` | Print a table |
| `--format life` | Print matching original life.txt item lines |
| `--format json` | Print a JSON array |
| `--format jsonl` | Print JSONL |
| `-o`, `--output` | Output file; defaults to stdout |
| `--pretty` | Pretty-print JSON output |

Examples:

```sh
python -m lifetxt agenda life.txt --from 2026-06-06 --to 2026-06-06 --format life
python -m lifetxt agenda life.txt --from 2026-06-06 --to 2026-06-06 --format json --pretty
python -m lifetxt agenda life.txt --around now --window 1w --format life -o agenda.life.txt
```

## 10. `assist`

Create or update life.txt items from flags or prompts.

```sh
python -m lifetxt assist [options]
```

### 10.1 Create Non-Interactively

```sh
python -m lifetxt assist --type task --title "Write Report" --due 2026-06-12 --project university
python -m lifetxt assist --type status --title "Working" --from 2026-06-06T14:00 --state busy --person self
python -m lifetxt assist --type message --title "Review Slides" --sender self --recipient alice --notify_at 2026-06-06T09:00
python -m lifetxt assist --type diary --title "Research day" --on 2026-06-23 --mood good --body "Read papers."
```

Core options:

| Option | Meaning |
|---|---|
| `-s`, `--status` | Status or alias, such as `[ ]`, `done`, or `note` |
| `-t`, `--type` | Type or alias, such as `T`, `task`, `status`, or `diary` |
| `--title` | Item title |
| `-d`, `--detail` | Detail as `key=value` or `key:value`; repeatable |
| `-o`, `--output` | Append generated line to a file |
| `--append` | Append generated line to a file |
| `--no-check` | Skip validation of the generated line |

Known detail keys also have direct flags. Each can be repeated:

```txt
--id --parent --ref --depends_on --blocks --related --created --updated --done --due --do --from --to
--state --user --person --owner --assignee --attendee --sender --recipient --team --group --service --channel
--visibility --notify_at --notify_from --notify_to --ack --snooze_until --on --at --repeat --interval --until --count
--project --context --loc --priority --est --tag --note --body --mood --weather --url
--reason --moved_to
```

### 10.2 Interactive Create

```sh
python -m lifetxt assist --interactive
python -m lifetxt assist --interactive --append life.txt
```

Interactive help:

| Input | Meaning |
|---|---|
| `?` | Contextual help for the current prompt |
| `?type` | Type help |
| `?status` | Status help |
| `?detail` | Suggested detail keys |
| `?all` | All known detail keys |
| `?due` | Help for a detail key |

When the terminal supports it, Tab completes type, status, and detail-key
candidates. Up/Down recall previous inputs. Use `--no-completion` to disable
line editing helpers.

### 10.3 Update Existing Items

Update an item by line number or by exact `id:` value.

```sh
python -m lifetxt assist --update life.txt --line 3 --title "New Title"
python -m lifetxt assist --update life.txt --match-id task_001 --status done --done 2026-06-06
python -m lifetxt assist --update life.txt --match-id task_001 --add-detail tag=important
python -m lifetxt assist --update life.txt --match-id task_001 --remove-detail tag
python -m lifetxt assist --update life.txt --match-id task_001 --output updated_life.txt
```

Update options:

| Option | Meaning |
|---|---|
| `--update FILE` | Read and update an existing life.txt file |
| `--line N` | Select the item on line `N` |
| `--match-id ID` | Select the item whose `id:` exactly equals `ID` |
| `--add-detail key=value` | Append a detail value |
| `--remove-detail key` | Remove all values for a detail key |
| `--output FILE` | Write the updated whole file to another file |

Without `--output`, update mode writes back to the input file.

## 11. `serve`

Run the optional FastAPI REST API and browser GUI.

Install web dependencies first:

```sh
pip install -r requirements-web.txt
```

Start the server:

```sh
python -m lifetxt serve life.txt --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000/` in a browser.

Options:

| Option | Meaning |
|---|---|
| `path ...` | life.txt file(s) to read; defaults to `life.txt` |
| `--write-file FILE` | File used for create, update, and delete operations |
| `--host HOST` | Bind host; defaults to `127.0.0.1` |
| `--port PORT` | Bind port; defaults to `8000` |

The REST API includes `/api/items`, `/api/messages`, `/api/agenda`, `/api/status`, and
`/api/health`. See [web.md](./web.md) for the full API and GUI guide.

## 12. `config`

Create or inspect an external JSON config file.

```sh
python -m lifetxt config init -o .lifetxt.json
python -m lifetxt --config .lifetxt.json config show
```

Example config:

```json
{
  "paths": ["life.txt", ".generated/google_calendar.life.txt"],
  "write_file": "life.txt",
  "user": {
    "name": "self",
    "display_name": "Self",
    "aliases": ["me"],
    "teams": []
  },
  "users": {
    "alice": {
      "display_name": "Alice",
      "aliases": ["ali"],
      "teams": ["research"]
    }
  },
  "teams": {
    "research": {
      "display_name": "Research Team",
      "members": ["self", "alice"],
      "aliases": ["lab"]
    }
  },
  "tags": {
    "aliases": {
      "review": ["code-review"]
    },
    "groups": {
      "work": ["research", "writing"]
    }
  },
  "defaults": {
    "person": "self",
    "timezone": "Asia/Tokyo"
  },
  "message": {
    "default_sender": "",
    "default_channel": "lifetxt"
  },
  "notifications": {
    "enabled": true,
    "recipient": "",
    "lookahead": "0m",
    "grace": "2m",
    "poll_seconds": 30,
    "state_file": ".cache/lifetxt/notifications.json",
    "snooze_default": "10m",
    "desktop": false,
    "web": true
  },
  "api": {
    "id_key": "id",
    "allow_id_writes": true
  },
  "ids": {
    "auto": true,
    "key": "id",
    "prefixes": {
      "T": "task",
      "E": "event",
      "D": "deadline",
      "R": "reminder",
      "H": "habit",
      "N": "note",
      "S": "status",
      "M": "msg"
    }
  },
  "web": {
    "host": "127.0.0.1",
    "port": 8000,
    "display_refresh": 60,
    "notification_poll_seconds": 30,
    "notification_lookahead": "0m",
    "default_limit": "",
    "default_sort": "line",
    "default_order": "asc"
  },
  "views": {
    "today": {
      "around": "now",
      "window": "1d",
      "sort": "time",
      "order": "asc"
    },
    "my_messages": {
      "view": "messages",
      "recipient": "self",
      "open_only": "true",
      "sort": "time",
      "order": "asc"
    },
    "team_status": {
      "view": "status",
      "type": "S",
      "active": "true",
      "refresh": "30"
    }
  },
  "sync_ics": {
    "output": ".generated/google_calendar.life.txt",
    "cache_dir": ".cache/lifetxt",
    "generated_paths": [".generated/google_calendar.life.txt"],
    "sources": [
      {
        "name": "google",
        "url_env": "LIFETXT_GOOGLE_CAL_ICS",
        "tags": ["google"]
      }
    ]
  }
}
```

When `ids.auto` is `true`, newly created items from `assist`, `/api/items`,
`/api/messages`, and message replies receive an `id:` if one was not provided.
Existing IDs are collected from every configured input file in `paths`, plus the
configured `write_file` and the command output file when applicable, so generated
IDs avoid collisions across multiple loaded `life.txt` files.
`check` reports duplicate IDs as warning `W213`, including duplicates across
multiple input files.
Set `ids.key` / `api.id_key` to use a custom ID detail key; id-based Web API
operations and `ids --assign --key KEY` use the selected key. Config `users`,
`teams`, and `tags` supply aliases and team membership for `--user`, `--team`,
and tag filters.

## 13. Aliases

Status aliases include:

| Alias | Status |
|---|---|
| `todo`, `open`, `queued`, `scheduled` | `[ ]` |
| `progress`, `doing`, `in_progress`, `active`, `sending` | `[/]` |
| `done`, `complete`, `completed`, `sent`, `delivered` | `[x]` |
| `cancel`, `canceled`, `cancelled` | `[-]` |
| `defer`, `deferred`, `moved` | `[>]` |
| `pending`, `unknown` | `[?]` |
| `note`, `n` | `[N]` |

Type aliases include:

| Alias | Type |
|---|---|
| `task`, `todo` | `T` |
| `event`, `calendar` | `E` |
| `deadline`, `due` | `D` |
| `reminder`, `remind` | `R` |
| `habit`, `recurring` | `H` |
| `note`, `memo` | `N` |
| `status`, `presence`, `presence_status`, `state` | `S` |
| `message`, `msg`, `mail`, `notification` | `M` |
| `journal`, `diary`, `log`, `entry` | `J` |

## 14. Practical Workflows

Validate and convert:

```sh
python -m lifetxt check life.txt
python -m lifetxt to-json life.txt --pretty -o life.json
python -m lifetxt to-jsonl life.txt --open --type task -o open_tasks.jsonl
python -m lifetxt to-csv life.txt --type journal -o journal.csv
```

Create filtered life.txt files:

```sh
python -m lifetxt filter life.txt --open --type task -o open_tasks.life.txt
python -m lifetxt filter life.txt --after now --type event -o future_schedule.life.txt
python -m lifetxt filter life.txt --type status --person self -o my_status.life.txt
python -m lifetxt filter life.txt --type message --recipient alice -o alice_messages.life.txt
```

Import calendar events:

```sh
python -m lifetxt import-ics google_calendar.ics -o life.txt --append --tag google
```

Sync calendar events from a secret iCalendar URL:

```sh
python -m lifetxt sync-ics --url-env LIFETXT_GOOGLE_CAL_ICS -o .generated/google_calendar.life.txt --cache-dir .cache/lifetxt --tag google
```

Show near-current items:

```sh
python -m lifetxt agenda life.txt --around now --window 2h --open
```

Show today's unfinished tasks:

```sh
python -m lifetxt agenda life.txt --from 2026-06-06 --to 2026-06-06 --open --type task
```

Show current team presence:

```sh
python -m lifetxt status life.txt --active
```

Run the browser GUI:

```sh
pip install -r requirements-web.txt
python -m lifetxt serve life.txt
```
