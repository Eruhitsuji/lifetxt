# Getting Started: The Beginner / Minimal Profile

`life.txt` has a lot of surface area: 9 item types, 7 statuses, dozens of
detail keys, hierarchy, links, recurrence, messages, and more. You do not
need any of that to start.

This page teaches the **Beginner / Minimal Profile** -- a small, named
subset of the existing [format specification](./life_txt_format_spec.md).
It is not a second format:

> Every Beginner Profile record is already valid Full Format syntax. Nothing
> you write here needs to be migrated, converted, or rewritten when you learn
> more of the format later.

```text
life.txt Format 1.0
├── Beginner / Minimal Profile   <- this page, level 1
├── Daily Use                    <- this page, level 2
└── Full Format                  <- life_txt_format_spec.md, level 3
```

Want to see it work before reading further? `lifetxt tour` shows a tiny
Beginner Profile sample and one real derived view over it -- no config, no
`life.txt`, and no setup required:

```sh
lifetxt tour
```

## Level 1 -- Minimum (5 minutes)

Learn four things and you can write a useful `life.txt`:

| Concept | Vocabulary |
| --- | --- |
| Statuses | `[ ]` open, `[x]` completed, `[N]` note |
| Types | `T` task, `E` event, `N` note |
| Time keys | `due`, `on`, `from`, `to` |
| Long text | one or more `\|` lines after the item |

A line has the shape:

```txt
[status] type "title" key:value
```

Always quote the title while you are learning. It is ordinary Format 1.0
syntax (bare titles without spaces are also valid; see
[section 4](./life_txt_format_spec.md#4-title-and-value-rules) of the format
specification), but quoting removes one thing to think about while you are
starting out.

### Tasks (`T`)

```txt
[ ] T "Buy milk"
[ ] T "Write report" due:2026-09-10
[x] T "Buy milk" done:2026-09-01
```

`due:` is the deadline. `[x]` marks a task done; add `done:` with the
completion date.

### Events (`E`)

```txt
[ ] E "Lab meeting" on:2026-09-10
[ ] E "Lab meeting" from:2026-09-10T13:00 to:2026-09-10T14:00
```

Use `on:` for an all-day date, or `from:`/`to:` for a specific time range.

### Notes (`N`)

```txt
[N] N "Research idea"
```

`[N]` is the note status, used for `N` (and later `J`) records that are not
"open" or "done" -- they simply exist. Add longer text with `|` continuation
lines:

```txt
[N] N "Research idea"
| Use previous and next frames as temporal context.
| Compare the result with the current frame-only model.
```

### A complete 5-minute file

```txt
# Tasks
[ ] T "Buy milk"
[ ] T "Write report" due:2026-09-10

# Events
[ ] E "Lab meeting" from:2026-09-10T13:00 to:2026-09-10T14:00

# Notes
[N] N "Research idea"
| Temporal context may reduce false positives.
```

This is [`examples/getting_started_life.txt`](../../examples/getting_started_life.txt).
Save your own version as `life.txt` and check it:

```sh
python -m lifetxt check life.txt
```

That is the entire Level 1 vocabulary. `check` uses the same parser as every
other command, so anything you can write with only this vocabulary already
works with `filter`, `agenda`, `tui`, `serve`, and every other surface.

Once you have written a few lines, `lifetxt today` is the daily entry point:

```sh
python -m lifetxt today life.txt
```

It is not a second data model or a new vocabulary -- it summarizes and
prioritizes what you already wrote (what's due, what's actionable, what's
blocked, today's events) into one view. The intended path stays small: write
in life.txt, run `today` to see what needs attention, and reach for a
specialized command (`agenda`, `next`, `project`, ...) only when you need to
go deeper. See [life-hub.md](life-hub.md) for the full picture.

## Level 2 -- Daily Use

Once the basics feel natural, these existing features cover most everyday
needs without touching IDs, links, or recurrence internals:

| Concept | Vocabulary |
| --- | --- |
| More types | `D` deadline, `R` reminder, `H` habit, `J` journal / diary |
| More statuses | `[/]` in progress |
| More keys | `do`, `at`, `repeat`, `project`, `tag`, `priority` |

```txt
[/] T "Write paper" due:2026-09-30 project:research
[ ] R "Take medicine" at:21:00
[ ] H "English study" repeat:daily at:18:00
[N] J "Today" on:2026-09-10
| Worked on the experiment.
```

`project:` and `tag:` group related items for `filter`, `stats`, and the Web
UI. `priority:` (`low`/`normal`/`high`, or a number) affects sort order in
`next`. `repeat:` (`daily`, `weekly`, `monthly`, `yearly`,
`weekdays`) expands recurring items automatically. See
[section 9](./life_txt_format_spec.md#9-type-specific-recommended-keys) of
the format specification for the recommended keys per type, and
[`cli.md`](./cli.md) for command-level filtering and shorthand capture
(`lifetxt add "Buy milk @home #errand !high ^tomorrow"` -- `add` is the
beginner-facing spelling of `quick`/`q`).

## Level 3 -- Full Format

Everything else in `life.txt` is still there when you need it, and none of
it is required to have used Level 1 or Level 2 correctly:

- remaining types (`S` status/presence, `M` message) and statuses (`[-]`
  canceled, `[>]` deferred, `[?]` pending)
- IDs and links: `id`, `parent`, `ref`, `depends_on`, `blocks`, `related`,
  `duplicate_of`, `replaced_by`
- people/ownership keys (`assignee`, `owner`, `attendee`, `person`, ...)
- recurrence limits (`interval`, `until`, `count`) and `repeat:RRULE:...`
- hierarchy via indentation
- repeated and custom keys
- workflow and system metadata, development tickets, Personal Context /
  AI-oriented conventions

Start from [`life_txt_format_spec.md`](./life_txt_format_spec.md) when you
want any of these. Nothing you wrote at Level 1 or Level 2 needs to change
first -- it is already valid input to the full grammar.

## Where to go next

- `lifetxt tour` -- a 30-second, zero-config demonstration; a good place to
  start before writing anything.
- `lifetxt init` -- create your own starter `life.txt` and config.
- `lifetxt add "Buy milk ^tomorrow"` -- capture your first real record.
- `lifetxt web` -- open the browser UI against it.
- [`life_txt_format_spec.md`](./life_txt_format_spec.md) -- the complete
  grammar.
- [`cli.md`](./cli.md) -- every command, filter, and output format.
- [`use-cases.md`](./use-cases.md) -- practical setups (task tracking,
  calendar, journaling, team status, AI integration).
- [`philosophy.md`](./philosophy.md) -- why lifetxt is built this way.

## Beginner mode in the Web UI

The [Web UI](./web.md#beginner-authoring-mode)'s record editor can hide
advanced Type/Status options, showing only this Beginner Profile's
`T`/`E`/`N` types and `[ ]`/`[x]`/`[N]` statuses until you choose to reveal
the rest -- the same vocabulary described above, applied to an authoring
surface instead of only this document.

## Read this in another language

lifetxt's human-readable CLI text (headings, guidance, `help`) can be shown
in Japanese instead of English -- command names, options, and Format 1.0
syntax always stay the same canonical English tokens:

```sh
lifetxt --lang ja tour
lifetxt --lang ja init
lifetxt --lang ja help beginner
LIFETXT_LANG=ja lifetxt today
```

See [`cli.md`](./cli.md)'s Localization section for the full precedence
rules, and read this same guide in Japanese at
[`docs/ja/getting-started.md`](../ja/getting-started.md).
