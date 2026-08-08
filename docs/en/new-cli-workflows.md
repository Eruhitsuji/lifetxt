# New CLI Workflows

This guide covers the workflow commands added in the 2026-07-20 roadmap implementation batch. All commands accept `--config FILE` in the same way as the existing CLI. File-reading commands default to configured `paths` or `life.txt` when paths are omitted.

## Actionable work

```sh
lifetxt next life.txt
lifetxt next life.txt --project research --limit 10
lifetxt next life.txt --format json
lifetxt next life.txt --rank
```

`next` selects open task records that are not deferred, someday/maybe, or blocked by an open dependency. Results are ordered by priority, due date, and age.

Add `--rank` to place overdue items first regardless of priority; ties still fall back to `next`'s normal priority, due date, and age ordering. Without `--rank`, output is unchanged.

`--rank` requires every selected item's `due` value to be a valid date; an item with an unparseable `due` (for example `due:not-a-date`) makes `next --rank` fail with an error naming the item instead of silently ranking it as if it had no due date. `next` without `--rank` is unaffected and keeps tolerating an unparseable `due` as it always has.

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
