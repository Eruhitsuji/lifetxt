# life.txt CLI Guide

This document describes the command-line interface provided by:

```sh
python -m lifetxt
```

The CLI is dependency-free and reads UTF-8 `life.txt`, JSON, or JSONL files.
Most file-reading commands accept one or more paths. Use `-` or omit paths to
read from standard input.

## 1. Command Overview

```sh
python -m lifetxt check [path ...]
python -m lifetxt to-json [path ...]
python -m lifetxt to-jsonl [path ...]
python -m lifetxt filter [path ...]
python -m lifetxt from-json [path ...]
python -m lifetxt from-jsonl [path ...]
python -m lifetxt status [path ...]
python -m lifetxt agenda [path ...]
python -m lifetxt assist [options]
```

| Command | Purpose |
|---|---|
| `check` | Validate life.txt syntax and semantic warnings |
| `to-json` | Convert life.txt to a JSON array |
| `to-jsonl` | Convert life.txt to JSONL |
| `filter` | Filter items and output life.txt, JSON, or JSONL |
| `from-json` | Convert JSON to life.txt |
| `from-jsonl` | Convert JSONL to life.txt |
| `status` | Show the latest `S` status / presence record for each person |
| `agenda` | Show items related to a datetime range |
| `assist` | Create or update life.txt items from prompts or flags |

## 2. Common Conventions

### 2.1 Input Paths

For commands that read files, `path ...` is optional and may contain multiple
files. Multiple inputs are read in order.

```sh
python -m lifetxt check life.txt
python -m lifetxt check work.life.txt home.life.txt
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

### 4.5 Export Filter Options

`to-json` and `to-jsonl` can filter items before writing output.

| Option | Meaning |
|---|---|
| `--open` | Keep unfinished workflow items only: `[ ]`, `[/]`, `[>]`, `[?]` |
| `--status VALUE` | Filter by status or alias; repeatable or comma-separated |
| `--type VALUE` | Filter by type or alias; repeatable or comma-separated |
| `--project VALUE` | Filter by `project:`; repeatable or comma-separated |
| `--tag VALUE` | Filter by `tag:`; repeatable or comma-separated |
| `--person VALUE` | Filter by `person:`; missing `person:` on `S` items means `self` |
| `--detail FILTER` | Filter by detail key or `key=value`; repeatable and ANDed |
| `--text TEXT` | Case-insensitive substring search over title, line, and details |
| `--after VALUE` | Keep items related to this time or later |
| `--before VALUE` | Keep items related to this time or earlier |

`--after` and `--before` accept `now`, `YYYY-MM-DD`, or
`YYYY-MM-DDTHH:MM`. They use the same time matching rules as `agenda`.
Time-only `at:HH:MM` values without an `on:` date are not matched by one-sided
`--after` or `--before` filters, because they have no date anchor.

Examples:

```sh
python -m lifetxt to-json life.txt --open --type task --pretty
python -m lifetxt to-jsonl work.life.txt home.life.txt --project research
python -m lifetxt to-json life.txt --after now --type event -o future_events.json
```

## 5. `filter`

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
python -m lifetxt filter life.txt --after now --type event -o future_schedule.life.txt
python -m lifetxt filter life.txt --type status --person self -o my_status.life.txt
python -m lifetxt filter work.life.txt home.life.txt --project research --format json --pretty
```

## 6. `status`

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

## 7. `agenda`

Show items related to a datetime range.

```sh
python -m lifetxt agenda [path ...] [range options] [filter options] [output options]
```

Range matching rules:

- `from/to` is treated as an interval.
- `on` is treated as an all-day interval.
- `due`, `do`, `at`, and `moved_to` are treated as point times or all-day spans.
- Type `S` records without `to:` are treated as ongoing from `from:`.
- `at:HH:MM` is combined with `on:` when present, otherwise with each date in the requested range.

### 7.1 Range Options

| Option | Meaning |
|---|---|
| `--from VALUE` | Range start: `now`, `YYYY-MM-DD`, or `YYYY-MM-DDTHH:MM` |
| `--to VALUE` | Range end: `now`, `YYYY-MM-DD`, or `YYYY-MM-DDTHH:MM` |
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
python -m lifetxt agenda life.txt --around now --window 2h
python -m lifetxt agenda life.txt --around now --window 1w
```

### 7.2 Filter Options

| Option | Meaning |
|---|---|
| `--open` | Show unfinished workflow items only: `[ ]`, `[/]`, `[>]`, `[?]` |
| `--status VALUE` | Filter by status or alias; repeatable or comma-separated |
| `--type VALUE` | Filter by type or alias; repeatable or comma-separated |
| `--project VALUE` | Filter by `project:`; repeatable or comma-separated |
| `--tag VALUE` | Filter by `tag:`; repeatable or comma-separated |
| `--person VALUE` | Filter by `person:`; repeatable or comma-separated |
| `--detail FILTER` | Filter by detail key or `key=value`; repeatable and ANDed |
| `--text TEXT` | Case-insensitive substring search over title, line, and details |

Examples:

```sh
python -m lifetxt agenda life.txt --from 2026-06-06 --to 2026-06-06 --open
python -m lifetxt agenda life.txt --from 2026-06-06 --to 2026-06-06 --status todo --type task
python -m lifetxt agenda life.txt --from 2026-06-06 --to 2026-06-06 --project research --tag urgent
python -m lifetxt agenda life.txt --from 2026-06-06 --to 2026-06-06 --detail priority=A --text report
python -m lifetxt agenda life.txt --from 2026-06-06 --to 2026-06-06 --person alice
```

`--detail key` checks that the key exists. `--detail key=value` checks for an
exact detail value. Multiple `--detail` filters are ANDed.

### 7.3 Output Options

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

## 8. `assist`

Create or update life.txt items from flags or prompts.

```sh
python -m lifetxt assist [options]
```

### 8.1 Create Non-Interactively

```sh
python -m lifetxt assist --type task --title "Write Report" --due 2026-06-12 --project university
python -m lifetxt assist --type status --title "Working" --from 2026-06-06T14:00 --state busy --person self
```

Core options:

| Option | Meaning |
|---|---|
| `-s`, `--status` | Status or alias, such as `[ ]`, `done`, or `note` |
| `-t`, `--type` | Type or alias, such as `T`, `task`, or `status` |
| `--title` | Item title |
| `-d`, `--detail` | Detail as `key=value` or `key:value`; repeatable |
| `-o`, `--output` | Append generated line to a file |
| `--append` | Append generated line to a file |
| `--no-check` | Skip validation of the generated line |

Known detail keys also have direct flags. Each can be repeated:

```txt
--id --parent --created --updated --done --due --do --from --to
--state --person --service --visibility --on --at --repeat
--project --context --loc --priority --est --tag --note --url
--reason --moved_to
```

### 8.2 Interactive Create

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

### 8.3 Update Existing Items

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

## 9. Aliases

Status aliases include:

| Alias | Status |
|---|---|
| `todo`, `open` | `[ ]` |
| `progress`, `doing`, `in_progress` | `[/]` |
| `done`, `complete`, `completed` | `[x]` |
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

## 10. Practical Workflows

Validate and convert:

```sh
python -m lifetxt check life.txt
python -m lifetxt to-json life.txt --pretty -o life.json
python -m lifetxt to-jsonl life.txt --open --type task -o open_tasks.jsonl
```

Create filtered life.txt files:

```sh
python -m lifetxt filter life.txt --open --type task -o open_tasks.life.txt
python -m lifetxt filter life.txt --after now --type event -o future_schedule.life.txt
python -m lifetxt filter life.txt --type status --person self -o my_status.life.txt
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
