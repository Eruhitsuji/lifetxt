# life.txt Format Specification

## 1. Overview

`life.txt` is a one-line-per-item plain-text format for tasks, events,
deadlines, reminders, habits, status / presence records, and notes.

```txt
[status] type title key:value key:value ...
```

Blank lines are ignored. Lines beginning with `#` are comments.

## 2. Status Values

| Status | Meaning |
|---|---|
| `[ ]` | Not completed |
| `[/]` | In progress |
| `[x]` | Completed |
| `[-]` | Canceled |
| `[>]` | Deferred or moved |
| `[?]` | Pending or uncertain |
| `[N]` | Note |

## 3. Type Values

| Type | Name | Meaning |
|---|---|---|
| `T` | Task | A task or to-do item |
| `E` | Event | A calendar event |
| `D` | Deadline | A deadline |
| `R` | Reminder | A reminder |
| `H` | Habit | A habit or recurring item |
| `N` | Note | A note or memo |
| `S` | Status / Presence status | A current state or presence-state record |

## 4. Title And Value Rules

Titles and detail values may be bare strings when they contain no spaces or
double quotes.

```txt
[ ] T Write_Report due:2026-06-12
```

Use double quotes when a title or value contains spaces.

```txt
[ ] E "Research Meeting" from:2026-06-08T13:00 to:2026-06-08T14:30
[N] N "Use more figures in the next presentation" project:research
```

Inside quoted strings, escape `"` as `\"` and `\` as `\\`.

## 5. Details

Details must use `key:value`.

```txt
due:2026-06-12
priority:A
project:research
loc:"Meeting Room A"
```

Multiple values are represented by repeating the same key.

```txt
[ ] T Create_Slides project:research tag:important tag:thesis tag:presentation
```

Custom keys are allowed. Parsers should preserve unknown keys when possible.

## 6. Detail Key Policy

The format distinguishes known keys from recommended keys.

- Known keys are recognized by tools for validation, completion, and help.
- Recommended keys are the smaller set that should be shown first for a type or status.
- Custom keys are still valid syntax and should be preserved.

This keeps the format extensible while making interactive help shorter.

## 7. Core Key Groups

These groups explain the common vocabulary. They are not a requirement for every
item.

### 7.1 Common Keys

| Key | Meaning | Example |
|---|---|---|
| `id` | Stable item ID | `id:task_001` |
| `parent` | Parent item ID | `parent:task_001` |
| `project` | Project or larger work area | `project:research` |
| `tag` | Free tag; repeat for multiple tags | `tag:important` |
| `note` | Short human note | `note:"Check later"` |
| `url` | Related URL | `url:https://example.com` |

### 7.2 Time Keys

| Key | Meaning | Example |
|---|---|---|
| `from` | Start datetime for an interval | `from:2026-06-08T13:00` |
| `to` | End datetime for an interval | `to:2026-06-08T14:30` |
| `on` | All-day date | `on:2026-06-08` |
| `at` | Reminder or execution time | `at:18:00` |
| `due` | Deadline date or datetime | `due:2026-06-12` |
| `do` | Planned execution date or datetime | `do:2026-06-10` |
| `done` | Completion date or datetime | `done:2026-06-05` |

### 7.3 Workflow Keys

| Key | Meaning | Example |
|---|---|---|
| `reason` | Reason for cancellation, deferral, or uncertainty | `reason:"Schedule changed"` |
| `moved_to` | New date or replacement item after deferral | `moved_to:2026-06-10` |

### 7.4 System Keys

| Key | Meaning | Example |
|---|---|---|
| `created` | Creation date or datetime | `created:2026-06-06` |
| `updated` | Last updated date or datetime | `updated:2026-06-06T16:30` |

## 8. Date And Time Values

| Form | Meaning | Example |
|---|---|---|
| `YYYY-MM-DD` | Date | `due:2026-06-12` |
| `YYYY-MM-DDTHH:MM` | Local datetime | `from:2026-06-08T13:00` |
| `HH:MM` | Time only | `at:18:00` |

Range-based tools may treat `from/to` and `on` as intervals. They may treat
`due`, `do`, `at`, and `moved_to` as point times or all-day spans.

## 9. Type-Specific Recommended Keys

### 9.1 Task (`T`)

Use `T` for work that can be completed.

Recommended keys:

```txt
do due priority est project tag note id parent
```

| Key | Why it is recommended |
|---|---|
| `do` | When the task should be worked on |
| `due` | When the task must be finished |
| `priority` | Relative importance |
| `est` | Estimated effort |
| `project`, `tag`, `note`, `id`, `parent` | Organization and context |

Example:

```txt
[ ] T Write_Report do:2026-06-10 due:2026-06-12 project:university priority:A
```

### 9.2 Event (`E`)

Use `E` for calendar-like events.

Recommended keys:

```txt
from to on loc project tag note
```

| Key | Why it is recommended |
|---|---|
| `from`, `to` | Timed event interval |
| `on` | All-day event date |
| `loc` | Event location |
| `project`, `tag`, `note` | Organization and context |

Example:

```txt
[ ] E Seminar from:2026-06-08T13:00 to:2026-06-08T14:30 loc:university
```

### 9.3 Deadline (`D`)

Use `D` for important deadlines that are not themselves events.

Recommended keys:

```txt
due priority project tag note
```

| Key | Why it is recommended |
|---|---|
| `due` | Required deadline |
| `priority` | Relative importance |
| `project`, `tag`, `note` | Organization and context |

Example:

```txt
[ ] D Scholarship_Form due:2026-06-20T17:00 project:university priority:A
```

### 9.4 Reminder (`R`)

Use `R` for a reminder at a date, time, or datetime.

Recommended keys:

```txt
at on project context note
```

| Key | Why it is recommended |
|---|---|
| `at` | Reminder time or datetime |
| `on` | Reminder date when `at:` is time-only |
| `project`, `context`, `note` | Organization and context |

Example:

```txt
[ ] R Take_Medicine at:2026-06-06T21:00 project:health
```

### 9.5 Habit (`H`)

Use `H` for recurring actions.

Recommended keys:

```txt
repeat at on project tag note
```

| Key | Why it is recommended |
|---|---|
| `repeat` | Recurrence rule |
| `at`, `on` | Time or date anchor |
| `project`, `tag`, `note` | Organization and context |

Example:

```txt
[ ] H English_Study repeat:daily at:18:00 project:english
```

### 9.6 Note (`N`)

Use `N` for notes and memos.

Recommended keys:

```txt
project context tag note url id parent
```

| Key | Why it is recommended |
|---|---|
| `project`, `context`, `tag` | Organization and retrieval |
| `note` | Extra note text when the title is short |
| `url` | Related reference |
| `id`, `parent` | Linking notes to other items |

Example:

```txt
[N] N Research_Memo project:research note:"Use figures before detailed explanation"
```

### 9.7 Status / Presence Status (`S`)

Use `S` for chat-style current state or presence status.

Required keys:

```txt
from state
```

Recommended keys:

```txt
from state to person service loc project note visibility
```

| Key | Why it is recommended |
|---|---|
| `from` | Status start datetime |
| `state` | Presence state |
| `to` | Status end datetime for finished logs |
| `person` | Person or target whose state is recorded |
| `service` | Source or target service |
| `loc`, `project`, `note`, `visibility` | Context and visibility |

Example:

```txt
[/] S Working from:2026-06-06T14:00 state:busy person:self
```

## 10. Status-Specific Recommended Keys

These recommendations depend on the workflow status value. They are secondary to
type-specific recommendations.

### 10.1 Not Completed (`[ ]`)

Recommended keys:

```txt
do due priority project tag note
```

Use these to plan open work.

### 10.2 In Progress (`[/]`)

Recommended keys:

```txt
do due project context note updated
```

Use these to show what is currently being worked on and when it was last
updated.

For `S`, `[/]` is recommended when `to:` is absent.

### 10.3 Completed (`[x]`)

Recommended keys:

```txt
done project tag note
```

Use `done:` to record completion time.

For `S`, `[x]` is recommended when `to:` is present.

### 10.4 Canceled (`[-]`)

Recommended keys:

```txt
reason updated note
```

Use `reason:` to explain why the item was canceled.

### 10.5 Deferred Or Moved (`[>]`)

Recommended keys:

```txt
moved_to reason updated note
```

Use `moved_to:` for the new date or replacement item.

### 10.6 Pending Or Uncertain (`[?]`)

Recommended keys:

```txt
note updated
```

Use `note:` for what is uncertain or what is waiting for confirmation.

### 10.7 Note Status (`[N]`)

Recommended keys:

```txt
project context tag note url
```

`[N]` should normally be used with type `N`.

## 11. Status / Presence State Values

Recommended `state:` values for type `S`:

| State | Meaning |
|---|---|
| `available` | Available |
| `busy` | Busy |
| `away` | Away |
| `offline` | Offline |
| `dnd` | Do not disturb |
| `focus` | Focus |
| `sleeping` | Sleeping |
| `commuting` | Commuting |
| `working` | Working |
| `studying` | Studying |
| `meeting` | In a meeting |
| `custom` | Custom status |

If `person:` is omitted, tools may interpret it as `self`.

Tools may summarize the latest presence state by selecting the `S` item with the
newest `from:` datetime for each `person:`.

If `to:` is absent, range-based tools may treat the status as ongoing from
`from:` onward. If `to:` is present, range-based tools may treat `from/to` as the
status interval.

## 12. Note Rule

The note status `[N]` should normally be used only with note type `N`.

```txt
[N] N Research_Memo project:research
```

## 13. Formal Grammar

```ebnf
life_file     = { blank_line | comment_line | item_line } ;
item_line     = status, space, type, space, string, { space, detail } ;
status        = "[ ]" | "[/]" | "[x]" | "[-]" | "[>]" | "[?]" | "[N]" ;
type          = "T" | "E" | "D" | "R" | "H" | "N" | "S" ;
detail        = key, ":", string ;
key           = bare_key ;
string        = bare_string | quoted_string ;
space         = " " ;
```

## 14. Complete Example

```txt
[ ] T Write_Report do:2026-06-10 due:2026-06-12 project:university priority:A
[ ] E Seminar from:2026-06-08T13:00 to:2026-06-08T14:30 loc:university project:research
[/] S Working from:2026-06-06T14:00 state:busy person:self
[/] S "Research Focus" from:2026-06-06T16:00 state:focus person:self note:"Replies may be slow"
[x] S Sleeping from:2026-06-05T01:00 to:2026-06-05T08:30 state:sleeping person:self
[N] N "Use more figures in the next presentation" project:research
```
