# Quick capture and shorthand

Quick capture turns one short input into a normal `life.txt` task. The CLI
commands `add`, `quick`, and `q`, TUI `/add`, Web Quick add, and MCP/Web capture
operations share the same four-token parser. Shorthand is only an authoring
convenience: the file stores canonical fields such as `project:home`, never
`@home`.

Use Quick capture when a task title plus a few common fields is enough. Use a
complete [Format line](./life_txt_format_spec.md) or structured create/edit
operation for other record types, statuses, bodies, links, repeated/custom
keys, or fully explicit authoring.

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

## Full lines are surface-specific

The Web Quick-add controls, including `/capture`, route trimmed input beginning
with `[` to the raw-line endpoint. This permits a complete line such as
`[ ] N "Read later" tag:reading`. Other input uses the shorthand capture
endpoint.

CLI `add`/`quick`/`q`, TUI `/add`, MCP `capture_item`, and Web
`POST /api/items/capture` are task-capture interfaces; they do **not** detect a
complete line this way. Use their raw/structured authoring path instead. The
Web API exposes `POST /api/items/raw` separately.

## Availability

| Surface | Shorthand entry | Important differences |
| --- | --- | --- |
| CLI | `add`, `quick`, `q` | options, presets, defaults, stdin, `--no-shorthand` |
| TUI | `/add TITLE` | shorthand; no CLI options/presets; context prefill stays below explicit sigils |
| Web UI | Quick add and `/capture` | shorthand plus UI-only full-line routing |
| Web API | `POST /api/items/capture` | shorthand task capture; `type` may be supplied; raw line is a separate endpoint |
| MCP | `capture_item`, `parse_shorthand` | shorthand task capture or non-writing preview; structured `create_item` is separate |

All shorthand capture paths reject an empty result title and invalid `^DATE`.
Validation failures do not create the requested record. For the complete file
grammar and recommended field values, use the
[Format specification](./life_txt_format_spec.md); for CLI options use the
[CLI reference](./cli.md).
