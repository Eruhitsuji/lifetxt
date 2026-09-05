# New CLI Workflows

This guide covers the workflow commands added in the 2026-07-20 roadmap implementation batch. All commands accept `--config FILE` in the same way as the existing CLI. File-reading commands default to configured `paths` or `life.txt` when paths are omitted.

## Actionable work

```sh
lifetxt next life.txt
lifetxt next life.txt --project research --limit 10
lifetxt next life.txt --format json
lifetxt next life.txt --rank
lifetxt next life.txt --why
```

`next` selects open Task, Deferred, Recurring, and Habit records that are not tagged `someday`, `maybe`, or `waiting`, and not blocked by an unfinished (or unresolvable) `depends_on` reference, using the same definition as the TUI `/next` view and the MCP `get_next_actions` tool. Blocking is resolved across every file passed to the command, so a dependency in another file still parks the item. Results are ordered by priority, due date, and age.

Selection previously differed across CLI, TUI, and MCP (Task-only kind coverage, no someday/maybe/waiting exclusion, and file-local rather than workspace-wide blocking in the CLI). This was corrected so all three surfaces agree; a `next` invocation that already worked around the old behavior may now see a different item set.

Add `--rank` to place overdue items first regardless of priority; ties still fall back to `next`'s normal priority, due date, and age ordering. Without `--rank`, output is unchanged.

`--rank` requires every selected item's `due` value to be a valid date; an item with an unparseable `due` (for example `due:not-a-date`) makes `next --rank` fail with an error naming the item instead of silently ranking it as if it had no due date. `next` without `--rank` is unaffected and keeps tolerating an unparseable `due` as it always has.

Add `--why` to show the deterministic evidence for each returned item: its
actionable status and type, parked-tag and dependency checks, and the ordering
fields used to place it in the result. JSON output adds a `why` object to each
item; text and life output include a human-readable `Why:` line. Without
`--why`, output is unchanged.

`next`'s default (table) output shows a **short ID** in the `ID` column
instead of the full `id:` value -- the shortest prefix that still uniquely
identifies the item among every `id:` in the loaded workspace, at least 6
characters. It is derived fresh on every call (there is no separate short-ID
registry) and is guaranteed to resolve back to the same item: pass it
directly to `done`, `start`, `complete`, or `assist --update --match-id`,
which all accept a unique ID prefix (see [cli.md](cli.md#103-update-existing-items)).
`--format json`/`--format life` are unaffected and always show the full
`id:` value.

Human-readable date fields on CLI, TUI, and Web listings include an optional
relative label, such as `due:2026-09-07 (in 2 days)` or `done:2026-09-04
(yesterday)`. The canonical stored value and machine-readable output remain
unchanged.

## Recently changed items

```sh
lifetxt recent life.txt
lifetxt recent life.txt --updated
lifetxt recent life.txt --created
lifetxt recent life.txt --limit 10
lifetxt recent life.txt --format json
```

`recent` is a read-only, newest-first view of recently created or updated
items -- a thin composition over existing parsing, short IDs, and
relative-time display, not a new indexing/cache subsystem. By default it
orders by `updated:`, falling back to `created:` for an item with no
`updated:`; `--updated`/`--created` select one basis explicitly with no
fallback, so an item missing that exact detail is excluded rather than
guessed at. An item with no timestamp at all under the selected basis, or
an unparseable one, is silently excluded rather than crashing the command.

`--limit N` bounds the number of rows (default 20; must be positive).
Text output shows the same short unique ID `next` shows (see above) plus a
relative-time label (`today`, `2 days ago`, ...); `--format json` instead
preserves every item's full `id:` and the raw absolute timestamp actually
used, never a locale-dependent display string.

## Inspect and edit one item

```sh
lifetxt show task_report life.txt
lifetxt show task_report life.txt --format json
lifetxt edit task_report life.txt --editor "code --wait"
lifetxt edit task_report life.txt --dry-run
```

`show` includes source location, hierarchy context, and incoming references. `edit` resolves the editor from `--editor`, the top-level `editor` config key, `VISUAL`, or `EDITOR`.

## Resolved paths

```sh
lifetxt path
lifetxt path --format json
```

`path` reports the loaded config, input files, write target, timer state, notification state, and cache directory.

## Review selectors and stale someday items

```sh
lifetxt review life.txt --last-week
lifetxt review life.txt --last-month
lifetxt review life.txt --year
lifetxt review life.txt --year 2025
lifetxt review life.txt --someday --older-than 90
```

The year selector defaults to the current calendar year. Convenience selectors are mutually exclusive with `--week`, `--month`, `--from`, and `--to`.

## Aggregation and team workload

```sh
lifetxt count life.txt --by status
lifetxt count life.txt --by project --format csv
lifetxt who life.txt --workload --due-soon 7
```

`count` supports `status`, `type`, `tag`, `person`, `project`, `context`, and `assignee`. Workload output groups open, in-progress, due-soon, and overdue work by assignee or owner.

## Standup and invoice reports

```sh
lifetxt standup life.txt --user self
lifetxt standup life.txt --format markdown
lifetxt invoice life.txt --from 2026-07-01 --to 2026-07-31 --rate 5000 --currency JPY
lifetxt invoice life.txt --rate research=6000 --rate consulting=8000 --round 15 --format csv
```

`standup` reports work completed yesterday, work planned for today, and blocked tasks. `invoice` totals `elapsed:` by project, applies optional project-specific rates and minute rounding, and emits text, Markdown, CSV, or JSON.

## Attachments

```sh
lifetxt files life.txt --open task_report --dry-run
lifetxt files life.txt --open task_report
lifetxt files life.txt --open task_report --allow-outside
```

The opener accepts only recorded `file:` and `dir:` targets. It rejects URLs, executable extensions, and paths outside the source file directory unless explicitly allowed. Use `--dry-run` before opening data received from another person.

## Calendar and text interchange

```sh
lifetxt to-ics life.txt -o calendar.ics
lifetxt from-todo todo.txt -o imported.life.txt
lifetxt import-ics todo.txt --preset todo -o imported.life.txt
lifetxt from-markdown issues.md --preset github -o issues.life.txt
```

`to-ics` exports event records with all-day or timed dates, timezone offsets, attendees, recurrence, and stable UID metadata. The todo.txt importer maps completion, priority, projects, contexts, and dates. The GitHub Markdown preset maps task-list state, issue references, assignee mentions, and nested task relationships.

## Journal capture

```sh
lifetxt quick --journal --append life.txt
lifetxt quick --journal --title "Research notes" --mood focused --project thesis
lifetxt quick --journal --body-file notes.md --date 2026-07-20 --dry-run
```

The editor flow opens a temporary Markdown file and appends a `J` record only when non-empty content is saved. The write itself goes through the existing validated quick-capture path.

## PowerShell completion

```powershell
lifetxt completion powershell -o $HOME\Documents\PowerShell\lifetxt-completion.ps1
. $HOME\Documents\PowerShell\lifetxt-completion.ps1
```

Add the dot-source line to your PowerShell profile to enable native command-name completion.

## CI-like local testing

Use the repository helper before pushing:

```sh
python scripts/run_ci_like.py
python scripts/run_ci_like.py --python python3.12 --no-web
python scripts/run_ci_like.py --skip-smoke
```

Pass launcher commands explicitly, for example `--python "py -3.12"` on Windows or `--python python3.12` on Unix-like systems. Each selected interpreter runs in a clean virtual environment.
