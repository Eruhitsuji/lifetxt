# Quick capture and shorthand

Quick is one fast textual entry point accepting **shorthand or one complete
life.txt record**. CLI `add`/`quick`/`q`, local and Remote TUI `/add`, Web Quick
Add, `/capture`, Planner Quick Capture, and MCP `capture_item` use the same
surface-neutral resolver. Full records use the authoritative Format parser;
shorthand uses the existing four-token parser. Files store canonical fields.

Use shorthand for titles and common fields, or enter a complete
[Format line](./life_txt_format_spec.md) to retain explicit types, statuses,
bodies, quoted values, and repeated/custom keys through the same Quick entry.

## Quick start

Choose a writable file with `--append` or configure `write_file`:

```sh
lifetxt add "Buy milk" --append life.txt
lifetxt quick "Buy milk @home #errand" --append life.txt
lifetxt q "Submit report @work !high ^tomorrow" --append life.txt
```

`add` is the beginner-facing alias; all three CLI spellings use the same
handler. The title may also be read as one line from stdin with `quick -`.

## Supported capture tokens

A token must be a complete whitespace-delimited word: one sigil followed by a
non-empty value containing no whitespace.

| Input | Canonical field | Example | Repetition |
| --- | --- | --- | --- |
| `@NAME` | `project:NAME` | `@home` | every value is parsed; prefer one project |
| `#NAME` | `tag:NAME` | `#errand` | accumulates; CLI merges and de-duplicates tags |
| `!VALUE` | `priority:VALUE` | `!high` | every value is parsed; prefer one priority |
| `^DATE` | `due:DATE` | `^tomorrow` | every value is parsed; dates resolve before writing |

The shorthand parser does not restrict project, tag, or priority values to a
vocabulary; their value is the non-whitespace text after the sigil. Normal
Format validation still applies to the generated line. A token consisting only
of a sigil, such as `^`, remains title text.

## Input and persisted result

For an explicit date, the relationship is deterministic:

```text
Buy milk @home #errand !high ^2026-10-02
    -> title: Buy milk
       project: home; tag: errand; priority: high; due: 2026-10-02
    -> [ ] T "Buy milk" project:home tag:errand priority:high due:2026-10-02 id:task_...
```

The serializer decides quoting and field order, and ID generation depends on
configuration and surface. Do not copy the illustrative ID.

## Date convenience

`^DATE` accepts an ISO date or the shared bounded date tokens:

| Input | Resolution |
| --- | --- |
| `today`, `tomorrow`, `yesterday` | that calendar day |
| `monday` ... `sunday` | the next occurrence (today means seven days later) |
| `next_monday` ... `next_sunday` | that next occurrence plus seven days |
| `next_week` | the coming Monday |
| `+3d`, `-1w`, `+2m`, `+1y` | signed day/week/month/year offset |

Resolution uses the workspace-aware current date. Month/year shifts clamp to
a valid day. For example, `^tomorrow` is resolved first and persisted as
`due:YYYY-MM-DD`; `due:tomorrow` is not canonical persisted shorthand. CLI date
flags (`--due`, `--do`, `--until`) and TUI `/due` accept the same date tokens.
An unknown or impossible date after `^` is rejected without writing.

## CLI precedence, defaults, and duplicates

For scalar fields, precedence is:

```text
explicit CLI option > capture sigil > named capture preset > config/file default
```

Thus `lifetxt add "Buy milk @home" --project errands` writes
`project:errands`. A preset supplies `type`, `status`, `project`, `tags`, and
`priority` only where explicit input has not supplied them. Tags from
`--tag`, shorthand, and a preset merge in the CLI and exact duplicates are
removed. See [named capture presets](./config.md#named-capture-presets).

The shared parser preserves repeated values. Surfaces that pass parser output
directly (TUI, Web capture endpoint, MCP) can therefore preserve repeated
projects, priorities, dates, or duplicate tags; do not rely on CLI tag
de-duplication as a cross-surface rule. Prefer one scalar token and unique tags.

`--no-shorthand` is CLI-only and keeps every sigil token in the title. The CLI
still applies explicit options and configured defaults.

## Whitespace, quoting, and literal sigils

- The CLI shell quoting in `"Buy milk @home"` groups the entire title argument;
  the capture parser itself has no quoted-token grammar.
- Runs of spaces are normalized when shorthand is parsed. A sigil value cannot
  contain whitespace; `@"deep work"` is not a multi-word project convention.
- Sigils inside a word are literal: `a@b.com` remains title text.
- Prefix a whole token with one backslash to keep the sigil literally:
  `Write about \@home` becomes the title `Write about @home`.
- There is no separate escape syntax for spaces inside a shorthand value.
- Quote characters received by the parser are ordinary title/value characters;
  unmatched quotes are not a shorthand syntax error. Let your shell enforce
  its own quoting rules.

A title made entirely from recognized sigils is rejected. Plain text without
recognized tokens is unchanged apart from normal title serialization.

## Complete records through the same Quick entry

```sh
lifetxt quick '[N] N "Idea" body:"Try shared Quick input"' --append life.txt
lifetxt add '[N] J "Journal" on:2026-10-01 body:"Today’s notes"' --append life.txt
```

Paste the same full line into Web Quick Add, `/capture`, Planner, or TUI
`/add [N] N "Idea" body:"text"`; MCP uses `capture_item` with `text` containing
the line. Web clients always use `POST /api/items/capture` with `{"text":"..."}`.
The response includes `mode: shorthand` or `mode: full_line`.
`POST /api/quick/resolve` previews the same contract without writing or assigning IDs.
Explicit `POST /api/items/raw` and structured create/import remain available.

A trimmed leading `[` reserves complete-record intent. Invalid statuses/types,
unclosed quotes and invalid syntax fail without creating a shorthand task.
For example `[ ] T "unterminated` is rejected. Quick accepts one line, not batch
or multiline import. Format warnings remain warnings; custom keys remain valid.
Sigils inside a full record's title/body are literal and never expanded.

Full records are authoritative: CLI type/status/detail flags, presets and
configured authoring defaults apply to shorthand only, not to full records.
Use the full record itself to set its fields. `--no-shorthand` disables sigil
expansion for title input; it does not bypass malformed full-record validation,
even when combined with `--no-check`. Related/context captures fill only absent
fields. Existing revision, authentication, read-only and write-target guards apply.
Explicit IDs are preserved and duplicate workspace IDs are rejected. CLI follows
`ids.auto`; TUI/Web/MCP continue guaranteeing addressable IDs, using configured
ID keys/prefixes. MCP may add configured source metadata and supports dry-run proposals.

## Availability

| Surface | Common Quick entry | Adapter behavior |
| --- | --- | --- |
| CLI | `add`, `quick`, `q`, stdin | existing shorthand flags/presets/defaults |
| Local TUI | `/add`, `/a`, `/related` | shared resolver; related context fills absent fields |
| Remote TUI | `/add`, `/a`, `/related` | sends text to authoritative server with revision |
| Web UI | Quick Add, `/capture`, Planner, command `/add`, Focus Quick Add | common capture API; Focus supplies today's due date only if absent |
| Web API | `POST /api/items/capture` | shorthand or full record; optional shorthand `type` |
| MCP | `capture_item` | shorthand or full record; existing proposals and source metadata |

`parse_shorthand` / `POST /api/shorthand/parse` remain explicit shorthand-only
preview contracts. Structured/guided editors and presence/message commands keep
their specialized contracts.

All shorthand capture paths reject an empty result title and invalid `^DATE`.
Validation failures do not create the requested record. For the complete file
grammar and recommended field values, use the
[Format specification](./life_txt_format_spec.md); for CLI options use the
[CLI reference](./cli.md).
