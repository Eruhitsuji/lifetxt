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

Parsers should preserve unknown custom keys when possible.

## 6. Recommended Detail Keys

| Key | Meaning | Example |
|---|---|---|
| `id` | Item ID | `id:task_001` |
| `parent` | Parent item ID | `parent:task_001` |
| `created` | Creation date or datetime | `created:2026-06-06` |
| `updated` | Last updated date or datetime | `updated:2026-06-06T16:30` |
| `done` | Completion date or datetime | `done:2026-06-05` |
| `due` | Deadline date or datetime | `due:2026-06-12` |
| `do` | Planned execution date or datetime | `do:2026-06-10` |
| `from` | Start datetime | `from:2026-06-08T13:00` |
| `to` | End datetime | `to:2026-06-08T14:30` |
| `on` | All-day date | `on:2026-06-08` |
| `at` | Reminder or execution time | `at:18:00` |
| `repeat` | Recurrence rule | `repeat:daily` |
| `state` | Status or presence state | `state:busy` |
| `person` | Person or target whose status is recorded | `person:self` |
| `service` | Source or target service | `service:teams` |
| `project` | Project name | `project:research` |
| `context` | Context or situation | `context:home` |
| `loc` | Location | `loc:"Meeting Room A"` |
| `priority` | Priority | `priority:A` |
| `est` | Estimated duration | `est:90m` |
| `tag` | Tag | `tag:important` |
| `note` | Short note | `note:"Check later"` |
| `url` | Related URL | `url:https://example.com` |
| `reason` | Reason | `reason:"Schedule changed"` |
| `moved_to` | New date or item after deferral | `moved_to:2026-06-10` |
| `visibility` | Visibility scope | `visibility:team` |

## 7. Date And Time Values

| Form | Meaning | Example |
|---|---|---|
| `YYYY-MM-DD` | Date | `due:2026-06-12` |
| `YYYY-MM-DDTHH:MM` | Local datetime | `from:2026-06-08T13:00` |
| `HH:MM` | Time only | `at:18:00` |

Range-based tools may treat `from/to` and `on` as intervals. They may treat
`due`, `do`, `at`, and `moved_to` as point times or all-day spans.

## 8. Type-Specific Keys

| Type | Recommended keys |
|---|---|
| `T` | `do due project context priority est tag note url id parent created updated done` |
| `E` | `from to on loc project tag note url id created updated` |
| `D` | `due project priority tag note url id created updated done` |
| `R` | `at on project context priority tag note url id created updated done` |
| `H` | `repeat at on project context priority tag note id created updated done` |
| `N` | `project context tag note url id parent created updated` |
| `S` | `from state to person service loc project note visibility` |

## 9. Status / Presence Status (`S`)

### 9.1 Purpose

Use `S` to record the current state of a person or target, similar to presence
states in Teams, Discord, Slack, or similar tools.

### 9.2 Required Keys

`S` requires:

```txt
from state
```

`from:` is the status start datetime. `state:` is the status value.

```txt
[/] S Working from:2026-06-06T14:00 state:busy
```

### 9.3 Optional Keys

Recommended optional keys:

```txt
to person service loc project note visibility
```

If `person:` is omitted, tools may interpret it as `self`.

### 9.4 Active Status And Logs

If `to:` is absent, the status may be treated as currently active.

```txt
[/] S Working from:2026-06-06T14:00 state:busy person:self
```

If `to:` is present, the status may be treated as a past status log.

```txt
[x] S Working from:2026-06-06T14:00 to:2026-06-06T16:00 state:busy person:self
```

`[/]` is recommended for currently active status items. `[x]` is recommended
for completed status logs. These are recommendations; the parser still uses the
normal status syntax rules.

### 9.5 Recommended State Values

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

### 9.6 Summary Tool Behavior

Tools may summarize the latest presence state by selecting the `S` item with the
newest `from:` datetime for each `person:`.

If `to:` is absent, range-based tools may treat the status as ongoing from
`from:` onward. If `to:` is present, range-based tools may treat `from/to` as the
status interval.

### 9.7 Examples

```txt
[/] S Working from:2026-06-06T14:00 state:busy person:self
[/] S Away from:2026-06-06T15:30 state:away person:self
[/] S "Research Focus" from:2026-06-06T16:00 state:focus person:self note:"Replies may be slow"
[x] S Sleeping from:2026-06-05T01:00 to:2026-06-05T08:30 state:sleeping person:self
```

## 10. Note Rule

The note status `[N]` should normally be used only with note type `N`.

```txt
[N] N Research_Memo project:research
```

## 11. Formal Grammar

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

## 12. Complete Example

```txt
[ ] T Write_Report do:2026-06-10 due:2026-06-12 project:university priority:A
[ ] E Seminar from:2026-06-08T13:00 to:2026-06-08T14:30 loc:university project:research
[/] S Working from:2026-06-06T14:00 state:busy person:self
[/] S "Research Focus" from:2026-06-06T16:00 state:focus person:self note:"Replies may be slow"
[x] S Sleeping from:2026-06-05T01:00 to:2026-06-05T08:30 state:sleeping person:self
[N] N "Use more figures in the next presentation" project:research
```
