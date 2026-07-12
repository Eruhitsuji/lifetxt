# life.txt Format Specification

## 1. Overview

`life.txt` is a plain-text format for tasks, events, deadlines, reminders,
habits, status / presence records, messages, notes, and journal / diary
entries.

```txt
[status] type title key:value key:value ...
```

Blank lines are ignored. Lines beginning with `#` are comments. Most items fit
on one line; optional continuation lines beginning with `|` attach multiline
body text to the previous item.

### 1.1 CLI-Compatible Profile

The reference CLI (`python -m lifetxt`) implements a strict, round-trippable
profile of this specification.

| Area | CLI-compatible rule |
|---|---|
| Encoding | Input is read as UTF-8, accepting an optional UTF-8 BOM. Output is UTF-8. |
| Line endings | `LF`, `CRLF`, and `CR` are accepted when reading. Serializers write `LF`. |
| Item line | `indent [status] type title details...` |
| Separators | A single space is canonical between status, type, title, and details. Multiple spaces are parsed with warnings. Tabs are errors. |
| Comments | A comment starts with `#` in column 1. Indented comments are ignored with a warning. |
| Details in files | Detail syntax is always `key:value`. `key=value` is not file syntax. |
| Details in CLI helpers | `assist -d`, `assist --add-detail`, and interactive detail prompts accept `key=value` as input convenience, then write canonical `key:value`. |
| Custom keys | Unknown keys are valid syntax and are preserved. Validators may warn when a key is not known or not recommended for the item type. |
| Repeated keys | Repeat the same key to represent multiple values. JSON/JSONL stores every detail as an array. CSV stores repeated values as a JSON array cell. |
| Hierarchy | Leading spaces are preserved as `indent` in JSON. When possible, the parser infers `parent:` for indented items. |
| Multiline body | Continuation lines beginning with `|` become one `body:` value with embedded newlines. |

For command behavior, filters, and conversion formats, see
[`docs/en/cli.md`](./docs/en/cli.md).

## 2. Status Values

| Status | Meaning |
|---|---|
| `[ ]` | Not completed |
| `[/]` | In progress |
| `[x]` | Completed |
| `[-]` | Canceled |
| `[>]` | Deferred or moved |
| `[?]` | Pending or uncertain |
| `[N]` | Note or journal record |

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
| `M` | Message | A person-to-person message or notification request |
| `J` | Journal / Diary | A diary, journal, or daily log entry |

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

### 4.1 Line Continuation

A physical line ending with a trailing backslash (`\`) is joined with the next
physical line before parsing. This is intended for long item lines.

```txt
[ ] T Write_Report \
  due:2026-06-12 project:research
```

The joined logical line is parsed as:

```txt
[ ] T Write_Report due:2026-06-12 project:research
```

Whitespace after the trailing backslash is ignored. Leading spaces on the
continued line are stripped. A bare trailing backslash at the end of the file is
an error. A backslash-continued item line must not continue into a `|` body
continuation line; use normal `|` body lines after a complete item line instead.

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

## 5.1 Nested / Hierarchical Records

Item lines may be indented with spaces to express a visual hierarchy. Two
spaces per level are recommended.

```txt
[ ] T Research_Project id:proj_research due:2026-07-31
  [ ] T Literature_Review id:task_lit
    [N] N Reading_Memo
    | Summarize the related work section.
  [ ] E Lab_Meeting from:2026-07-06T13:00 to:2026-07-06T14:00
```

When an indented item does not already contain `parent:`, parsers may infer
`parent:` from the nearest less-indented ancestor's selected ID key, normally
`id:`. In the example above, `Literature_Review` and `Lab_Meeting` inherit
`parent:proj_research`, and `Reading_Memo` inherits `parent:task_lit`.

The canonical machine representation of hierarchy is explicit `parent:`.
Indentation is a convenient authoring and display form derived from the same
relationship. CLI commands that provide `--canonical` write unindented item
lines and keep or add explicit `parent:` details when they can infer the parent
from indentation and the parent item has an ID.

If the ancestor has no ID, the item remains valid but tools should warn because
the hierarchy cannot be represented as an ID link. You can always write
`parent:` explicitly, and explicit `parent:` takes precedence over indentation.
Indented body continuation lines are allowed; they attach to the previous item
exactly like unindented `|` continuation lines.

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
| `project` | Project or larger work area | `project:research` |
| `tag` | Free tag; repeat for multiple tags | `tag:important` |
| `note` | Short human note | `note:"Check later"` |
| `body` | Long text body; may use continuation lines | `body:short_text` |
| `url` | Related URL | `url:https://example.com` |

`id:` values should be unique across the loaded life.txt files. Validators
report duplicate IDs as warning `W213`; id-based API and update operations may
reject ambiguous IDs. ID values should be compact ASCII tokens without spaces or
quotes. External IDs such as iCalendar UIDs may contain symbols like `@`.

### 7.2 Link Keys

| Key | Meaning | Example |
|---|---|---|
| `parent` | Parent item, hierarchy, or message thread parent | `parent:task_001` |
| `ref` | Generic reference to another item | `ref:task_001` |
| `depends_on` | Item that must be completed or resolved first | `depends_on:task_001` |
| `blocks` | Item that is blocked by this item | `blocks:task_002` |
| `related` | Looser related item | `related:note_001` |

Reference values point to the selected ID key, normally `id:`. Tools should
warn when a reference has no target, points to the same item, or creates a
cycle through `parent:`.

Dependency semantics:

- `depends_on:ID` means the current item cannot proceed until item `ID` is
  completed, canceled, or otherwise no longer open.
- `blocks:ID` means the current item is an independent blocker for item `ID`.
  It is an inverse assertion, not a required mirror of `depends_on:`.
- Open dependency statuses are `[ ]`, `[/]`, `[>]`, and `[?]`.
- `check` emits `W224` when an item marked `[x]` still has a `depends_on:`
  prerequisite that is open.
- `agenda` includes `blocked: true` and `blocked_by` in JSON / JSONL output
  when an open item is blocked by an open prerequisite. Text output shows a
  compact `blocked` column.
- `health` emits `W305` for open items blocked by open prerequisites.

When a command loads multiple life.txt files in one invocation, references are
resolved against the whole loaded input set. For example, `parent:task_001` in
`team.life.txt` may point to `id:task_001` in `life.txt` if both files are
passed to the same command or loaded through config paths. Converters that
emit JSON or JSONL include source metadata for file-backed input records:
`_source_file`, `_source_line`, and, for multi-line records,
`_source_end_line`. These `_source_*` fields are command output metadata, not
life.txt detail keys, and `from-json` / `from-jsonl` ignore them when writing
life.txt back.

### 7.3 People Keys

| Key | Meaning | Example |
|---|---|---|
| `user` | General user reference when no narrower role fits | `user:alice` |
| `owner` | Person accountable for the item | `owner:alice` |
| `assignee` | Person assigned to do the work | `assignee:alice` |
| `attendee` | Event participant; repeat for multiple attendees | `attendee:alice` |
| `person` | Status / presence target; mainly for type `S` | `person:self` |
| `sender` | Message sender; mainly for type `M` | `sender:self` |
| `recipient` | Message recipient; repeat for multiple recipients | `recipient:alice` |
| `team` | Team related to the item | `team:research` |
| `group` | User group related to the item | `group:lab` |

Use `person` for the target whose presence state is recorded. For non-status
items, prefer the more specific `owner`, `assignee`, or `attendee`.
Use `sender` and `recipient` for message delivery records. Use `user` only when
the relationship is intentionally generic. Use `team` / `group` for collective
ownership, filtering, or routing.

### 7.4 Time Keys

| Key | Meaning | Example |
|---|---|---|
| `from` | Start datetime for an interval | `from:2026-06-08T13:00` |
| `to` | End datetime for an interval | `to:2026-06-08T14:30` |
| `on` | All-day date | `on:2026-06-08` |
| `at` | Reminder or execution time | `at:18:00` |
| `due` | Deadline date or datetime | `due:2026-06-12` |
| `do` | Planned execution date or datetime | `do:2026-06-10` |
| `done` | Completion date or datetime | `done:2026-06-05` |
| `notify_at` | Message notification date or datetime | `notify_at:2026-06-06T09:00` |
| `notify_from` | Notification period start | `notify_from:2026-06-06T09:00` |
| `notify_to` | Notification period end | `notify_to:2026-06-06T17:00` |
| `ack` | Notification acknowledgement date or datetime | `ack:2026-06-06T09:05` |
| `snooze_until` | Suppress notification until this date or datetime | `snooze_until:2026-06-06T09:30` |

### 7.5 Effort Keys

| Key | Meaning | Example |
|---|---|---|
| `est` | Estimated effort or duration | `est:2h` |
| `elapsed` | Accumulated actual elapsed time | `elapsed:1h30m` |

`elapsed:` is used by the `timer` CLI command. Compact values such as `25m`,
`1h`, `1h30m`, and bare minutes such as `90` are supported. `check` reports
parseable but non-canonical duration values as `W222`; unrecognized values such
as `elapsed:1d` or `elapsed:90x` are reported as `W226` instead of being treated
as zero minutes.

### 7.6 Recurrence Keys

| Key | Meaning | Example |
|---|---|---|
| `repeat` | Recurrence rule | `repeat:daily` |
| `repeat_base` | Anchor for the next occurrence on `complete`: `due` or `done` | `repeat_base:done` |
| `interval` | Repeat every N units | `interval:2` |
| `until` | Last recurrence date or datetime | `until:2026-12-31` |
| `count` | Maximum number of occurrences | `count:10` |

Supported simple `repeat:` values are `daily`, `weekly`, `monthly`, `yearly`,
and `weekdays`. `RRULE:...` values may be stored for interoperability. Built-in
agenda and time-filter expansion supports a dependency-free RRULE subset:
`FREQ=DAILY|WEEKLY|MONTHLY|YEARLY`, `INTERVAL`, `COUNT`, `UNTIL`, and
daily/weekly `BYDAY`.

`repeat_base` only affects the `complete` CLI command and the `complete_item`
MCP tool, which materialize the next occurrence of a repeat-enabled task
instance (see CLI docs section 13.9). It has no effect on agenda's virtual
expansion. `repeat_base:due` (the default, also settable via
`defaults.repeat_base` in config) advances from the item's current `due:`/
`do:` value and requires one to be present. `repeat_base:done` advances from
the completion date instead. `BYDAY` RRULE values are not yet supported by
`complete`'s materialization.

### 7.7 Message Keys

| Key | Meaning | Example |
|---|---|---|
| `sender` | Message sender | `sender:self` |
| `recipient` | Message recipient; repeat for multiple recipients | `recipient:alice` |
| `body` | Message body, especially when longer than the title | `body:"Please review the slides"` |
| `notify_at` | One notification time | `notify_at:2026-06-06T09:00` |
| `notify_from`, `notify_to` | Notification period | `notify_from:2026-06-06T09:00 notify_to:2026-06-06T17:00` |
| `ack` | Acknowledged notification | `ack:2026-06-06T09:05` |
| `snooze_until` | Notification snooze end | `snooze_until:2026-06-06T09:30` |
| `channel` | Delivery channel or route | `channel:teams` |

### 7.8 Journal Keys

| Key | Meaning | Example |
|---|---|---|
| `on` | Journal date | `on:2026-06-23` |
| `at` | Journal time | `at:22:30` |
| `from`, `to` | Time span covered by the entry | `from:2026-06-23T09:00 to:2026-06-23T18:00` |
| `mood` | Mood label | `mood:good` |
| `weather` | Weather label | `weather:sunny` |
| `loc` | Location | `loc:home` |
| `body` | Long journal text | continuation lines beginning with `|` |

### 7.9 Workflow Keys

| Key | Meaning | Example |
|---|---|---|
| `reason` | Reason for cancellation, deferral, or uncertainty | `reason:"Schedule changed"` |
| `moved_to` | New date or replacement item after deferral | `moved_to:2026-06-10` |

### 7.10 System Keys

| Key | Meaning | Example |
|---|---|---|
| `created` | Creation date or datetime | `created:2026-06-06` |
| `updated` | Last updated date or datetime | `updated:2026-06-06T16:30` |

## 8. Date And Time Values

| Form | Meaning | Example |
|---|---|---|
| `YYYY-MM-DD` | Date | `due:2026-06-12` |
| `YYYY-MM-DDTHH:MM` | Local datetime | `from:2026-06-08T13:00` |
| `YYYY-MM-DDTHH:MM:SS` | Local datetime with seconds | `from:2026-06-08T13:00:30` |
| `YYYY-MM-DDTHH:MM:SS.sss` | Local datetime with fractional seconds | `from:2026-06-08T13:00:30.5` |
| `YYYY-MM-DDTHH:MM+09:00` | Datetime with timezone offset | `from:2026-06-08T13:00+09:00` |
| `YYYY-MM-DDTHH:MM:SS.sss+09:00` | Datetime with seconds, fractional seconds, and timezone | `from:2026-06-08T13:00:30.25+09:00` |
| `YYYY-MM-DDTHH:MMZ` | UTC datetime | `from:2026-06-08T04:00Z` |
| `HH:MM` | Time only | `at:18:00` |
| `HH:MM:SS` | Time only with seconds | `at:18:00:30` |
| `HH:MM:SS.sss` | Time only with fractional seconds | `at:18:00:30.5` |
| `HH:MM+09:00` | Time only with timezone offset | `at:18:00+09:00` |

Range-based tools may treat `from/to`, `notify_from/notify_to`, and `on` as
intervals. They may treat `due`, `do`, `at`, `moved_to`, and `notify_at` as
point times or all-day spans.

When a timezone is present, tools may normalize the value to the machine's local
timezone before comparing or displaying it. Fractional seconds support up to six
digits.

## 8.1 Recurrence Semantics

Simple recurrence is expressed with `repeat:` and optional `interval:`,
`until:`, and `count:`. iCalendar-compatible recurrence can also be stored as
`repeat:RRULE:...`.

```txt
[ ] H Stretch repeat:daily at:18:00
[ ] H Review repeat:weekly interval:2 on:2026-06-01 until:2026-12-31
[ ] H Workday_Checkin repeat:weekdays at:09:00 count:10
[ ] E Training repeat:RRULE:FREQ=WEEKLY;BYDAY=MO,WE;COUNT=6 from:2026-06-01T09:00 to:2026-06-01T10:00
```

Agenda and time filters expand simple recurrences and the supported RRULE
subset from the first available anchor, in this order:

| Anchor | Meaning |
|---|---|
| `from` / `to` | Repeating timed interval |
| `at` with `on` | Repeating time on the anchored date pattern |
| `at` without `on` | Floating time expanded only inside a bounded requested range |
| `on` | Repeating all-day date |
| `due`, `do`, `moved_to`, `notify_at` | Repeating point date/datetime or all-day span |

`interval:2` means every two units of the selected repeat value. `count:` limits
the number of generated occurrences from the anchor. `until:` is an inclusive
end date/datetime. One-sided filters intentionally ignore floating `at:` values
without `on:` because they have no stable date anchor.

Requested date/time ranges are half-open: `[start, end)`. When a CLI or API
range uses a date-only end such as `--to 2026-06-12`, tools interpret the end as
`2026-06-13T00:00` and exclude records exactly at that next-day boundary. This
keeps fractional-second values on the selected day, such as
`2026-06-12T23:59:59.5`, inside the requested range.

For `repeat:RRULE:...`, the built-in subset reads `FREQ`, `INTERVAL`, `COUNT`,
and `UNTIL`; `BYDAY` is supported for `FREQ=DAILY` and `FREQ=WEEKLY`. `UNTIL`
may use life.txt datetime syntax or iCalendar basic forms such as `20260630`
and `20260630T090000`. More complex RRULE features are preserved as text but
are not expanded by the dependency-free core. `check` emits recurrence warning
`W223` when it detects unsupported RRULE features.

## 9. Type-Specific Recommended Keys

### 9.1 Task (`T`)

Use `T` for work that can be completed.

Recommended keys:

```txt
do due priority assignee owner team est elapsed project tag note body id parent ref depends_on blocks related
```

| Key | Why it is recommended |
|---|---|
| `do` | When the task should be worked on |
| `due` | When the task must be finished |
| `priority` | Relative importance |
| `assignee` | Person assigned to do the task |
| `owner` | Person accountable for the task |
| `team` | Team related to the task |
| `est` | Estimated effort |
| `elapsed` | Actual elapsed time, usually maintained by `timer` |
| `project`, `tag`, `note`, `body`, `id`, `parent` | Organization and context |

Example:

```txt
[ ] T Write_Report do:2026-06-10 due:2026-06-12 project:university priority:A assignee:alice
```

### 9.2 Event (`E`)

Use `E` for calendar-like events.

Recommended keys:

```txt
from to on loc attendee owner team project tag note body ref related
```

| Key | Why it is recommended |
|---|---|
| `from`, `to` | Timed event interval |
| `on` | All-day event date |
| `loc` | Event location |
| `attendee` | Event participant; repeat for multiple attendees |
| `owner` | Person accountable for the event record |
| `project`, `tag`, `note`, `body` | Organization and context |

Example:

```txt
[ ] E Seminar from:2026-06-08T13:00 to:2026-06-08T14:30 loc:university attendee:alice
```

### 9.3 Deadline (`D`)

Use `D` for important deadlines that are not themselves events.

Recommended keys:

```txt
due priority owner assignee team project tag note body depends_on ref related
```

| Key | Why it is recommended |
|---|---|
| `due` | Required deadline |
| `priority` | Relative importance |
| `owner` | Person accountable for the deadline |
| `assignee` | Person assigned to complete related work |
| `project`, `tag`, `note`, `body` | Organization and context |

Example:

```txt
[ ] D Scholarship_Form due:2026-06-20T17:00 project:university priority:A owner:alice
```

### 9.4 Reminder (`R`)

Use `R` for a reminder at a date, time, or datetime.

Recommended keys:

```txt
at on owner team project context note body ref related
```

| Key | Why it is recommended |
|---|---|
| `at` | Reminder time or datetime |
| `on` | Reminder date when `at:` is time-only |
| `owner` | Person accountable for the reminder |
| `project`, `context`, `note`, `body` | Organization and context |

Example:

```txt
[ ] R Take_Medicine at:2026-06-06T21:00 project:health
```

### 9.5 Habit (`H`)

Use `H` for recurring actions.

Recommended keys:

```txt
repeat interval until count at on owner team project tag note body ref related
```

| Key | Why it is recommended |
|---|---|
| `repeat` | Recurrence rule |
| `interval`, `until`, `count` | Recurrence limits |
| `at`, `on` | Time or date anchor |
| `owner` | Person accountable for the habit |
| `project`, `tag`, `note`, `body` | Organization and context |

Example:

```txt
[ ] H English_Study repeat:daily at:18:00 project:english
[ ] H Weekly_Review repeat:weekly interval:2 on:2026-06-01 until:2026-12-31 project:life
```

### 9.6 Note (`N`)

Use `N` for notes and memos.

Recommended keys:

```txt
project context tag note body url id parent ref related
```

| Key | Why it is recommended |
|---|---|
| `project`, `context`, `tag` | Organization and retrieval |
| `note` | Extra note text when the title is short |
| `body` | Longer note text, especially with continuation lines |
| `url` | Related reference |
| `id`, `parent` | Linking notes to other items |

Example:

```txt
[N] N Research_Memo project:research note:"Use figures before detailed explanation"
```

### 9.7 Journal / Diary (`J`)

Use `J` for diary entries, daily logs, and longer personal or work journals.
Because `D` is already Deadline, diary uses the type letter `J` for Journal.
`[N]` is the recommended status.

Recommended keys:

```txt
on at from to mood weather loc person project tag note body url id parent ref related created updated
```

| Key | Why it is recommended |
|---|---|
| `on`, `at`, `from`, `to` | Date/time covered by the entry |
| `mood`, `weather`, `loc` | Diary context |
| `person` | Person the entry is about, usually `self` |
| `project`, `tag`, `note`, `body`, `url` | Retrieval and long-form content |
| `id`, `parent`, `created`, `updated` | Linking and metadata |

Examples:

```txt
[N] J "Research day" on:2026-06-23 mood:good tag:lab
| Read papers in the morning.
| Wrote parser tests in the afternoon.
```

### 9.8 Status / Presence Status (`S`)

Use `S` for chat-style current state or presence status.

Required keys:

```txt
from state
```

Recommended keys:

```txt
from state to person team group service loc project note body ref related visibility
```

| Key | Why it is recommended |
|---|---|
| `from` | Status start datetime |
| `state` | Presence state |
| `to` | Status end datetime for finished logs |
| `person` | Person or target whose state is recorded |
| `team`, `group` | Team or group context for the status |
| `service` | Source or target service |
| `loc`, `project`, `note`, `body`, `visibility` | Context and visibility |

Example:

```txt
[/] S Working from:2026-06-06T14:00 state:busy person:self
```

### 9.9 Message (`M`)

Use `M` for a person-to-person message, a queued notification, or a delivery
request. `M` records are not an external messaging API by themselves; they are
a structured life.txt record that tools can show, filter, or send later.

Required keys:

```txt
sender recipient
```

Recommended keys:

```txt
sender recipient team group notify_at notify_from notify_to ack snooze_until channel service priority project tag note body url id parent ref related created updated
```

| Key | Why it is recommended |
|---|---|
| `sender` | Person or agent sending the message |
| `recipient` | Person receiving the message; repeat for multiple recipients |
| `team`, `group` | Team or group routing/context |
| `notify_at` | Single notification or delivery time |
| `notify_from`, `notify_to` | Notification window or delivery period |
| `ack` | Acknowledged notification; tools should not notify again |
| `snooze_until` | Suppress notification until this date or datetime |
| `channel` | Delivery route such as `teams`, `discord`, `slack`, or `email` |
| `service` | Source or target service |
| `priority`, `project`, `tag`, `note`, `body`, `url`, `id`, `parent`, `created`, `updated` | Routing, context, and traceability |

Examples:

```txt
[ ] M "Review slides" sender:self recipient:alice notify_at:2026-06-06T09:00 channel:teams
[ ] M "Detailed request" sender:self recipient:alice body:"Please review sections 2 and 3" notify_at:2026-06-06T09:00
[/] M "Daily reminder" sender:lifetxt recipient:self notify_from:2026-06-06T09:00 notify_to:2026-06-06T17:00 channel:desktop
[x] M "Sent review request" sender:self recipient:alice done:2026-06-06T09:05
```

## 10. Status-Specific Recommended Keys

These recommendations depend on the workflow status value. They are secondary to
type-specific recommendations.

### 10.1 Not Completed (`[ ]`)

Recommended keys:

```txt
do due priority project tag note ref related
```

Use these to plan open work.

### 10.2 In Progress (`[/]`)

Recommended keys:

```txt
do due project context note ref related updated
```

Use these to show what is currently being worked on and when it was last
updated.

For `S`, `[/]` is recommended when `to:` is absent.
For `M`, `[/]` can mean the notification is active or delivery is in progress.

### 10.3 Completed (`[x]`)

Recommended keys:

```txt
done project tag note
```

Use `done:` to record completion time.

For `S`, `[x]` is recommended when `to:` is present.
For `M`, `[x]` can mean the message was sent, delivered, or otherwise completed.

### 10.4 Canceled (`[-]`)

Recommended keys:

```txt
reason updated note
```

Use `reason:` to explain why the item was canceled.
For `M`, `[-]` can mean the message or notification was canceled.

### 10.5 Deferred Or Moved (`[>]`)

Recommended keys:

```txt
moved_to reason updated note
```

Use `moved_to:` for the new date or replacement item.
For `M`, `[>]` can mean delivery was postponed.

### 10.6 Pending Or Uncertain (`[?]`)

Recommended keys:

```txt
note updated
```

Use `note:` for what is uncertain or what is waiting for confirmation.
For `M`, `[?]` can mean delivery state or recipient response is unknown.

### 10.7 Note Status (`[N]`)

Recommended keys:

```txt
project context tag note body url ref related
```

`[N]` should normally be used with type `N` or `J`.

## 11. Multiline Body Text

A line beginning with `|` continues the previous item as a `body:` detail. A
single space after `|` is treated as a separator and is not part of the text.
Use a bare `|` for an empty body line.

`body:` is not limited to `J`. Use `note:` for a short aside and `body:` for
long-form content on any type, especially detailed tasks, event descriptions,
messages, notes, and journals.

```txt
[ ] T Write_Report due:2026-06-12 project:university
| Include the method section and references.

[N] J "Research day" on:2026-06-23 mood:good
| First paragraph.
|
| Second paragraph.
```

This is equivalent to a `body:` value containing embedded newlines. Serializers
should emit multiline `body` values with continuation lines. Continuation lines
must follow an item; an orphan continuation line is a syntax error.

## 12. Status / Presence State Values

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

## 13. Note And Journal Rule

The note status `[N]` should normally be used only with note type `N` or journal
type `J`.

```txt
[N] N Research_Memo project:research
[N] J "Research day" on:2026-06-23
```

## 14. Formal Grammar

```ebnf
life_file         = { blank_line | comment_line | item_line | continuation_line } ;
blank_line        = { " " | "\t" } ;
comment_line      = "#", text ;
item_line         = indent, status, space, type, space, string, { space, detail } ;
continuation_line = indent, "|", [ space ], body_text ;

indent            = { " " } ;
space             = " " ;
status            = "[ ]" | "[/]" | "[x]" | "[-]" | "[>]" | "[?]" | "[N]" ;
type              = "T" | "E" | "D" | "R" | "H" | "N" | "S" | "M" | "J" ;
detail            = key, ":", string ;

key               = bare_key ;
bare_key          = key_char, { key_char } ;
key_char          = ? any character except space, colon, or double quote ? ;

string            = bare_string | quoted_string ;
bare_string       = bare_char, { bare_char } ;
bare_char         = ? any character except space or double quote ? ;
quoted_string     = '"', { quoted_char | escape }, '"' ;
quoted_char       = ? any character except double quote or backslash ? ;
escape            = "\\\"" | "\\\\" ;

body_text         = text ;
text              = ? any characters until end of line ? ;
```

Notes:

- The CLI validator recommends lowercase snake_case keys matching
  `[a-z][a-z0-9_]*`, but the parser preserves other syntactically valid keys.
- A quoted string must be followed by a space or end of line.
- A bare string cannot contain spaces or double quotes. The serializer quotes
  values that contain tabs, backslashes, empty strings, or other non-canonical
  bare-string characters.
- Continuation lines must follow an item. They are serialized as `body:` when
  JSON/JSONL/CSV data is converted back to life.txt.
- `key=value` appears only in CLI helper input; it is intentionally excluded
  from the file grammar.

## 15. Complete Example

```txt
[ ] T Write_Report do:2026-06-10 due:2026-06-12 project:university priority:A assignee:alice
[ ] E Seminar from:2026-06-08T13:00 to:2026-06-08T14:30 loc:university project:research attendee:alice
[/] S Working from:2026-06-06T14:00 state:busy person:self
[/] S "Research Focus" from:2026-06-06T16:00 state:focus person:self note:"Replies may be slow"
[x] S Sleeping from:2026-06-05T01:00 to:2026-06-05T08:30 state:sleeping person:self
[ ] M "Review slides" sender:self recipient:alice notify_at:2026-06-06T09:00 channel:teams
[N] N "Use more figures in the next presentation" project:research
```
