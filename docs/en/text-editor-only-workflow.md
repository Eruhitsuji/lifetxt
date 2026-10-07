# Text-editor-only weekly workflow

This workflow manages tasks and notes using only an approved text editor.
It requires no external application, CLI, Python, Git, Web UI, external SaaS,
or network connection. In restricted workplaces, learning environments, or
offline settings, use lifetxt as a **plain-text task management format**.

**This is an operational pattern, not a requirement of the life.txt format.**
Weekly files and the syntax subset below are optional. They do not change or
restrict ordinary single-file use or the [format specification](./life_txt_format_spec.md).
Like the [5-minute introduction](./getting-started.md), this uses a subset of
existing syntax, not a new format.

## 1. Prepare files

Use the editor's New and Save As actions in an approved storage location.
Save as plain text in UTF-8, with one file for tasks you intend to work on each
week. Keep work with no planned week in `someday.txt`. No configuration file is needed.

```text
2026-W40.txt
2026-W41.txt
2026-W42.txt
someday.txt
```

These are ISO week numbers (Monday start): W40 is September 28–October 4,
W41 is October 5–11, and W42 is October 12–18 in 2026.
If week numbers are inconvenient, use the start date, such as `2026-10-05.txt`.
Filenames do not automatically set dates or record states in the application.

## 2. Minimal syntax

Write one record per line as `status type "title" attributes`, separated by
ordinary spaces. Enclose titles or attribute values containing spaces in straight
double quotes (`"`). Use comments starting with `#` for headings and explanations.

| Task status | Meaning in this workflow |
| --- | --- |
| `[ ]` | Not started / unfinished |
| `[/]` | In progress |
| `[x]` | Completed |
| `[-]` | Cancelled |
| `[>]` | Moved to another week or file (the format means postponed or moved) |

| Type or attribute | Purpose |
| --- | --- |
| `T` | Task |
| `N` | Note |
| `project:alpha` | Project name; supply a value after `project:` |
| `priority:high` | Add only for high-priority tasks |
| `due:2026-10-09` | Deadline in `YYYY-MM-DD` form, when needed |

For notes, use the existing note status `[N]`, separate from the task statuses:
`[N] N "A note"`. The type `N` and status `[N]` occupy different fields.
Attributes are optional. A deadline is not the planned week, so do not change it
just because a task is carried forward.

Starting template for `2026-W41.txt`:

```txt
# 2026-W41: 2026-10-05 - 2026-10-11
# This week
[ ] T "Prepare design review" project:alpha priority:high due:2026-10-09
[/] T "Investigate reproduction conditions" project:alpha
[N] N "Check input order when reproducing the issue" project:alpha

# Inbox
[ ] T "Identify procedure updates" project:alpha
```

`# Inbox` is simply a comment marking where to append unsorted tasks, not a
special feature or syntax. Put items for later in `someday.txt`:

```txt
# Someday
[ ] T "Outline verification improvements" project:alpha
```

## 3. Daily flow

1. Open the current week's file at the start of the day. Search for `[/]` to find ongoing work.
2. If today is October 7, search for `due:2026-10-07`. Also search for `due:` and read the dates for overdue and approaching deadlines; today's exact search will miss overdue work.
3. Search for `priority:high`, inspect each record's status, and select today's work from unfinished tasks.
4. Change `[ ]` to `[/]` when starting a task, and save.
5. Append new tasks under `# Inbox` as `[ ] T "Next action"`.
6. Change `[/]` (or `[ ]`) to `[x]` when finished, and save.
7. Before finishing the day, review Inbox and `[/]` records. Move Inbox items into this week's section or someday, or cancel them. Ongoing work can remain `[/]`.

There are no automatic notifications or deadline checks. Read states and dates
in the editor and make the decisions yourself.

## 4. Weekly review and carry-forward

At the end of the week or start of the next, open the old and new weekly files.

| Old week's record | Action |
| --- | --- |
| `[x]` or `[-]` | Leave in the old file |
| `[ ]` or `[/]`, still planned for next week | Copy to the new file; save and verify the destination before marking the old record `[>]` |
| Not planned soon | Copy to `someday.txt`; save and verify before marking the source `[>]` |
| No longer needed | Mark `[-]` |
| Note | Normally leave in the old file; copy only notes needed for ongoing work |

Use `[ ]` at the destination when planning to start again, or `[/]` if the task
is actually continuing. Review the title, project, priority, and deadline.
Decide whether each task really belongs in the next week instead of carrying
all unfinished work forward indefinitely. Review someday too, moving selected
work into the current week with the same procedure.

After moving a task from W41 to W42, the old file `2026-W41.txt` contains:

```txt
# Moved to: 2026-W42.txt
[>] T "Investigate reproduction conditions" project:alpha due:2026-10-09
[x] T "Prepare design review" project:alpha priority:high due:2026-10-09
[-] T "Run an investigation no longer needed" project:alpha
```

The new file `2026-W42.txt` contains:

```txt
# Moved from: 2026-W41.txt
[ ] T "Investigate reproduction conditions" project:alpha due:2026-10-09
```

The overdue deadline stays visible for a decision in the new week. Neither
`[>]` nor the destination comment automatically links or moves anything. Save
the destination before changing the source. If interrupted, compare both files
and ensure the same task is not left unfinished in both. Keep old weeks as
history; normally work and search in the current week and someday.

## 5. Use text search as a simple UI

Use **literal text search, not regular expressions**. `[ ]` contains one ordinary
space. If the editor cannot search multiple files, open and search them individually.

| Search text | What to inspect |
| --- | --- |
| `[/]` | Work in progress |
| `[ ]` | Not started / unfinished tasks |
| `priority:high` | High-priority lines; inspect status because completed and moved records also match |
| `project:alpha` | Lines for project alpha |
| `project:` | Lines with a project |
| `due:2026-10-07` | Lines with that deadline |
| `due:` | All deadline-bearing lines; read dates for overdue or approaching work |

Search navigates to or highlights matching text. It is not a structured filter:
comments and note text can match too. Check the status at the start of the record
and avoid changing states with Replace All.

## 6. Saving and information handling

Save after edits and at each step of a file transfer. Follow your organization's
rules for storage locations and backups. This guide does not guarantee compliance
with any particular organization's policies. Never store passwords, API keys,
access tokens, private keys, other credentials, or information prohibited by your
organization's rules in life.txt.

Related: [Use cases](./use-cases.md) / [Philosophy](./philosophy.md) /
[Format specification](./life_txt_format_spec.md)
