# life.txt Format Specification

## 1. Overview

`life.txt` is a plain-text format for managing tasks, events, deadlines, reminders, habits, status / presence records, and notes in a single human-readable file.

The format is designed to be:

- easy to write by hand
- easy to read in plain text
- easy to parse by programs
- suitable for conversion to JSONL, calendar formats, and task-management tools

Each item is normally written on one line.

---

## 2. Basic Line Format

Each line represents one item.

```txt
[status] type title detail...
```

The line consists of the following parts:

```txt
[status] type title key:value key:value ...
```

### Components

| Component | Description |
|---|---|
| `status` | The workflow state of the item |
| `type` | The kind of item |
| `title` | The main title or content of the item |
| `detail` | Optional metadata written as `key:value` |

---

## 3. Status Values

Only the following seven status values are allowed.

| Status | Meaning |
|---|---|
| `[ ]` | Not completed |
| `[/]` | In progress |
| `[x]` | Completed |
| `[-]` | Canceled |
| `[>]` | Deferred or moved |
| `[?]` | Pending or uncertain |
| `[N]` | Note |

Example:

```txt
[ ] T Write_Report due:2026-06-12
[/] T Organize_Experiment_Results project:research
[x] T Clean_Room done:2026-06-05
[-] E Call_Friend reason:canceled
[>] T Submit_Form moved_to:2026-06-10
[?] E Meeting from:2026-06-12T15:00 to:2026-06-12T16:00
[N] N Research_Memo project:research
```

---

## 4. Type Values

Only the following seven item types are allowed.

| Type | Name | Meaning |
|---|---|---|
| `T` | Task | A task or to-do item |
| `E` | Event | A calendar event |
| `D` | Deadline | A deadline |
| `R` | Reminder | A reminder |
| `H` | Habit | A habit or recurring item |
| `N` | Note | A note or memo |
| `S` | Status / Presence status | A current state or presence-state record |

Example:

```txt
[ ] T Write_Report due:2026-06-12
[ ] E Seminar from:2026-06-08T13:00 to:2026-06-08T14:30
[ ] D Scholarship_Form due:2026-06-20T17:00
[ ] R Turn_Off_Air_Conditioner at:2026-06-06T23:30
[ ] H English_Study repeat:daily at:18:00
[N] N Presentation_Memo project:research
[/] S Working from:2026-06-06T14:00 state:busy person:self
```

---

## 5. Title Rules

The title follows the same string rule as detail values.

If the title does not contain spaces, it may be written without double quotes.

```txt
[ ] T Write_Report due:2026-06-12
[ ] T Report_Writing due:2026-06-12
[ ] E Seminar from:2026-06-08T13:00 to:2026-06-08T14:30
```

If the title contains spaces, it must be enclosed in double quotes.

```txt
[ ] T "Write Report" due:2026-06-12
[ ] E "Research Meeting" from:2026-06-08T13:00 to:2026-06-08T14:30
[N] N "Use more figures in the next presentation" project:research
```

---

## 6. Detail Format

Details are optional metadata fields.

All details must use the following format:

```txt
key:value
```

Examples:

```txt
due:2026-06-12
priority:A
project:research
loc:lab
note:"Ask the professor later"
```

The following forms are not allowed:

```txt
+research
@home
priority A
priority : A
loc:Meeting Room A
```

If a value contains spaces, it must be enclosed in double quotes.

```txt
loc:"Meeting Room A"
note:"Ask the professor later"
```

---

## 7. Key Rules

A key must not contain spaces, colons, or double quotes.

Recommended key style:

```txt
lowercase_snake_case
```

Examples:

```txt
due:2026-06-12
created:2026-06-06
moved_to:2026-06-10
project:research
```

---

## 8. Value Rules

A value can be either a bare value or a quoted value.

### 8.1 Bare Value

A bare value must not contain spaces or double quotes.

```txt
project:research
priority:A
est:90m
repeat:daily
```

### 8.2 Quoted Value

A quoted value is enclosed in double quotes and may contain spaces.

```txt
loc:"Meeting Room A"
note:"Explain the overall idea before details"
reason:"Schedule changed"
```

---

## 9. Escaping Rules

Inside quoted strings, double quotes should be escaped with a backslash.

```txt
[N] N "Title is \"life.txt\"" project:format
```

A backslash itself should be escaped as `\\`.

```txt
[N] N Windows_Path path:"C:\\Users\\user\\Documents"
```

---

## 10. Multiple Values

Multiple values are represented by writing the same key multiple times.

```txt
[ ] T Create_Slides project:research tag:important tag:thesis tag:presentation
```

This can be converted to JSON as an array.

```json
{
  "status": "[ ]",
  "type": "T",
  "title": "Create_Slides",
  "details": {
    "project": ["research"],
    "tag": ["important", "thesis", "presentation"]
  }
}
```

For consistency, parsers are encouraged to store all detail values as arrays, even when a key appears only once.

---

## 11. Recommended Detail Keys

The following keys are recommended, but implementations may allow custom keys.

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

---

## 12. Date and Time Format

The recommended date and time format is based on ISO 8601.

### Date

```txt
YYYY-MM-DD
```

Example:

```txt
due:2026-06-12
```

### Local Date and Time

```txt
YYYY-MM-DDTHH:MM
```

Example:

```txt
from:2026-06-08T13:00
```

### Time Only

```txt
HH:MM
```

Example:

```txt
at:18:00
```

### 12.1 Range-Based Tool Behavior

Tools may provide range-based views such as an agenda or near-current-time
pickup. Such tools should treat `from/to` and `on` as intervals. They may treat
`due`, `do`, `at`, and `moved_to` as point times or all-day spans. If `at:` is a
time-only value such as `18:00`, tools may combine it with `on:` when present or
with each date in the requested range.

---

## 13. Recurrence Values

Simple recurrence values may be written as follows:

```txt
repeat:daily
repeat:weekly
repeat:monthly
repeat:yearly
```

Examples:

```txt
[ ] H English_Study repeat:daily at:18:00
[ ] H Weekly_Review repeat:weekly at:20:00
```

For more advanced recurrence rules, implementations may support iCalendar-style RRULE values.

```txt
[ ] H Exercise repeat:"RRULE:FREQ=WEEKLY;BYDAY=MO,WE,FR" at:07:00
```

---

## 14. Recommended Type-Specific Keys

### 14.1 Task (`T`)

Recommended keys:

```txt
do due project context priority est tag note url id parent created updated done
```

Example:

```txt
[ ] T Write_Report do:2026-06-10 due:2026-06-12 project:university priority:A est:120m tag:report
```

### 14.2 Event (`E`)

Recommended keys:

```txt
from to on loc project tag note url id created updated
```

Example:

```txt
[ ] E Research_Meeting from:2026-06-08T13:00 to:2026-06-08T14:30 loc:"Meeting Room A" project:research
```

### 14.3 Deadline (`D`)

Recommended keys:

```txt
due project priority tag note url id created updated done
```

Example:

```txt
[ ] D Scholarship_Form due:2026-06-20T17:00 project:university priority:A
```

### 14.4 Reminder (`R`)

Recommended keys:

```txt
at on project context priority tag note url id created updated done
```

Example:

```txt
[ ] R Turn_Off_Air_Conditioner at:2026-06-06T23:30 project:life
```

### 14.5 Habit (`H`)

Recommended keys:

```txt
repeat at on project context priority tag note id created updated done
```

Example:

```txt
[ ] H English_Study repeat:daily at:18:00 project:english tag:TOEIC tag:vocabulary
```

### 14.6 Note (`N`)

Recommended keys:

```txt
project context tag note url id parent created updated
```

Example:

```txt
[N] N Presentation_Memo project:research note:"Use figures before detailed explanation"
```

### 14.7 Status / Presence Status (`S`)

`S` represents a current state or presence status, similar to status values in
chat tools such as Teams, Discord, Slack, or similar systems.

#### 14.7.1 Purpose

Use `S` to record the current state of a person or target. It can represent
availability, focus, away status, sleep, meetings, commuting, or another
chat-style presence state.

#### 14.7.2 Required Keys

Required keys:

```txt
from state
```

`from:` is the status start datetime. `state:` is the status value.

Example:

```txt
[/] S Working from:2026-06-06T14:00 state:busy
```

#### 14.7.3 Recommended Optional Keys

Recommended optional keys:

```txt
to person service loc project note visibility
```

Meanings:

| Key | Meaning | Example |
|---|---|---|
| `from` | Start datetime of the status | `from:2026-06-06T14:00` |
| `state` | Status or presence state | `state:busy` |
| `to` | End datetime of the status | `to:2026-06-06T16:00` |
| `person` | Person or target of the status. If omitted, implementations may interpret it as `self` | `person:self` |
| `service` | Source or target service | `service:teams` |
| `loc` | Location | `loc:home` |
| `project` | Related project | `project:research` |
| `note` | Additional note | `note:"Reply may be slow"` |
| `visibility` | Visibility scope | `visibility:team` |

If `person:` is omitted, implementations may interpret it as `self`.

#### 14.7.4 Active Status and Status Logs

If `to:` is absent, the status may be treated as currently active.

```txt
[/] S Working from:2026-06-06T14:00 state:busy person:self
```

If `to:` is present, the status may be treated as a past status log.

```txt
[x] S Working from:2026-06-06T14:00 to:2026-06-06T16:00 state:busy person:self
```

For consistency, `[/]` is recommended for currently active status items, and `[x]` is recommended for completed status logs. This is a type-specific recommendation; the parser still uses the normal status syntax rules.

#### 14.7.5 Recommended State Values

Recommended `state:` values:

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

Other state values may be preserved by parsers, but tools should warn when the
value is outside the recommended set.

#### 14.7.6 Summary Tool Behavior

Tools may summarize the latest presence state by selecting the `S` item with the
newest `from:` datetime for each `person:`. If `person:` is omitted, summary
tools may treat it as `self`.

If `to:` is absent, range-based tools may treat the status as ongoing from
`from:` onward. If `to:` is present, range-based tools may treat `from/to` as the
status interval.

#### 14.7.7 Examples

Examples:

```txt
[/] S Working from:2026-06-06T14:00 state:busy person:self
[/] S Away from:2026-06-06T15:30 state:away person:self
[/] S "Research Focus" from:2026-06-06T16:00 state:focus person:self note:"Replies may be slow"
[x] S Sleeping from:2026-06-05T01:00 to:2026-06-05T08:30 state:sleeping person:self
```

---

## 15. Recommended Status-Type Rule for Notes

The note status `[N]` should be used only with the note type `N`.

Recommended valid form:

```txt
[N] N Research_Memo project:research
```

The following forms should be treated as errors or warnings.

```txt
[ ] N Research_Memo
[N] T Buy_Milk
```

---

## 16. Comments and Blank Lines

Blank lines may be ignored.

Lines beginning with `#` may be treated as comments.

```txt
# This is a comment.

[ ] T Write_Report due:2026-06-12
```

Comments are not life.txt items.

---

## 17. Formal Grammar

A simplified grammar is shown below.

```ebnf
life_file     = { blank_line | comment_line | item_line } ;

item_line     = status, space, type, space, string, { space, detail } ;

status        = "[ ]" | "[/]" | "[x]" | "[-]" | "[>]" | "[?]" | "[N]" ;

type          = "T" | "E" | "D" | "R" | "H" | "N" | "S" ;

detail        = key, ":", string ;

key           = bare_key ;

string        = bare_string | quoted_string ;

bare_key      = { character_except_space_colon_or_double_quote } ;

bare_string   = { character_except_space_or_double_quote } ;

quoted_string = '"', { escaped_character | character_except_double_quote_or_backslash }, '"' ;

space         = " " ;

blank_line    = { space } ;

comment_line  = "#", { any_character } ;
```

---

## 18. JSONL Conversion Example

### life.txt

```txt
[ ] T Write_Report do:2026-06-10 due:2026-06-12 project:university priority:A tag:report tag:important
[ ] E Research_Meeting from:2026-06-08T13:00 to:2026-06-08T14:30 loc:"Meeting Room A" project:research
[/] S Working from:2026-06-06T14:00 state:busy person:self
[N] N Presentation_Memo project:research note:"Use figures before detailed explanation"
```

### JSONL

```jsonl
{"status":"[ ]","type":"T","title":"Write_Report","details":{"do":["2026-06-10"],"due":["2026-06-12"],"project":["university"],"priority":["A"],"tag":["report","important"]}}
{"status":"[ ]","type":"E","title":"Research_Meeting","details":{"from":["2026-06-08T13:00"],"to":["2026-06-08T14:30"],"loc":["Meeting Room A"],"project":["research"]}}
{"status":"[/]","type":"S","title":"Working","details":{"from":["2026-06-06T14:00"],"state":["busy"],"person":["self"]}}
{"status":"[N]","type":"N","title":"Presentation_Memo","details":{"project":["research"],"note":["Use figures before detailed explanation"]}}
```

---

## 19. Complete Example

```txt
# life.txt

[ ] T Write_Report do:2026-06-10 due:2026-06-12 project:university priority:A est:120m tag:report tag:important
[/] T Organize_Experiment_Results do:2026-06-06 project:research priority:A
[x] T Clean_Room done:2026-06-05 project:life
[-] E Call_Friend from:2026-06-07T20:00 to:2026-06-07T21:00 reason:"Schedule changed"
[?] E Meeting from:2026-06-12T15:00 to:2026-06-12T16:00 project:university
[ ] D Scholarship_Form due:2026-06-20T17:00 project:university priority:A
[ ] R Turn_Off_Air_Conditioner at:2026-06-06T23:30 project:life
[ ] H English_Study repeat:daily at:18:00 project:english tag:TOEIC tag:vocabulary
[/] S Working from:2026-06-06T14:00 state:busy person:self
[x] S Sleeping from:2026-06-05T01:00 to:2026-06-05T08:30 state:sleeping person:self
[N] N Presentation_Memo project:research note:"Use figures before detailed explanation"
```

Status / presence records can be mixed with other item types.

```txt
[ ] T Write_Report do:2026-06-10 due:2026-06-12 project:university priority:A
[ ] E Seminar from:2026-06-08T13:00 to:2026-06-08T14:30 loc:university project:research
[/] S Working from:2026-06-06T14:00 state:busy person:self
[/] S "Research Focus" from:2026-06-06T16:00 state:focus person:self note:"Replies may be slow"
[x] S Sleeping from:2026-06-05T01:00 to:2026-06-05T08:30 state:sleeping person:self
[N] N "Use more figures in the next presentation" project:research
```

---

## 20. Design Summary

The core design of `life.txt` is:

```txt
[status] type title key:value key:value ...
```

Important rules:

1. One item should normally be written on one line.
2. Only the defined status values are allowed.
3. Only the defined type values are allowed.
4. Titles and values may be bare strings if they contain no spaces.
5. Titles and values must be quoted if they contain spaces.
6. All details must use the `key:value` format.
7. Multiple values are represented by repeating the same key.
8. Parsers should preserve unknown custom keys when possible.
