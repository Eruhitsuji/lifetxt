# life.txt CLI Guide

This document describes the command-line interface provided by:

```sh
python -m lifetxt
```

The CLI is dependency-free and reads UTF-8 `life.txt`, JSON, JSONL, or CSV files.
Most file-reading commands accept one or more paths. Use `-` or omit paths to
read from standard input.

## 1. Command Overview

```sh
python -m lifetxt tour
python -m lifetxt check [path ...]
python -m lifetxt integrity [path ...]
python -m lifetxt ids [path ...]
python -m lifetxt links [path ...]
python -m lifetxt sources [path ...]
python -m lifetxt to-json [path ...]
python -m lifetxt to-jsonl [path ...]
python -m lifetxt to-csv [path ...]
python -m lifetxt demo [options]
python -m lifetxt markdown [path ...]
python -m lifetxt import-ics [path ...]
python -m lifetxt import [path ...]
python -m lifetxt sync-ics --url-env ENVVAR
python -m lifetxt filter [path ...]
python -m lifetxt from-json [path ...]
python -m lifetxt from-jsonl [path ...]
python -m lifetxt from-csv [path ...]
python -m lifetxt status [path ...]
python -m lifetxt notify [path ...]
python -m lifetxt agenda [path ...]
python -m lifetxt assist [options]
python -m lifetxt tui [path ...]
python -m lifetxt fzf [path ...]
python -m lifetxt timer start path --id ID
python -m lifetxt timer pause
python -m lifetxt timer resume
python -m lifetxt timer stop
python -m lifetxt timer summary [path ...]
python -m lifetxt stats [path ...]
python -m lifetxt git-hook install
python -m lifetxt completion bash
python -m lifetxt serve [path ...]
python -m lifetxt web [path ...]
python -m lifetxt config init
python -m lifetxt config show
python -m lifetxt init
python -m lifetxt doctor
python -m lifetxt quick "Title"
python -m lifetxt add "Title"
python -m lifetxt done [path ...]
python -m lifetxt complete [path ...]
python -m lifetxt assign [path ...]
python -m lifetxt batch [path ...]
python -m lifetxt archive [path ...]
python -m lifetxt undo [path ...]
python -m lifetxt summary [path ...]
python -m lifetxt inbox [path ...]
python -m lifetxt cleanup [path ...]
python -m lifetxt health [path ...]
python -m lifetxt review [path ...]
python -m lifetxt who [path ...]
python -m lifetxt search PATTERN [path ...]
python -m lifetxt find TERM [path ...]
python -m lifetxt snapshot [path ...]
python -m lifetxt lint [path ...]
python -m lifetxt diff FILE_A FILE_B
python -m lifetxt plot [path ...]
python -m lifetxt export-heatmap [path ...]
python -m lifetxt migrate [path ...]
python -m lifetxt from-markdown [path ...]
python -m lifetxt deps [path ...]
python -m lifetxt tag list [path ...]
python -m lifetxt watch [path ...] -- COMMAND
python -m lifetxt encrypt [path ...]
python -m lifetxt decrypt [path ...]
python -m lifetxt share [path ...]
python -m lifetxt digest [path ...]
python -m lifetxt template list
python -m lifetxt workspace list
python -m lifetxt project list
python -m lifetxt portfolio [path ...]
python -m lifetxt today [path ...]
python -m lifetxt area list [path ...]
python -m lifetxt backlinks ID [path ...]
python -m lifetxt temporal ID [path ...]
python -m lifetxt freebusy [path ...] --from START --to END
python -m lifetxt query "QUERY" [path ...] [--explain]
python -m lifetxt view list
python -m lifetxt group list [path ...]
python -m lifetxt message recipients [path ...]
python -m lifetxt person list [path ...]
python -m lifetxt proposal list
python -m lifetxt ticket list [path ...]
python -m lifetxt version list [path ...]
python -m lifetxt sprint list [path ...]
python -m lifetxt rrule daily
python -m lifetxt update-check
python -m lifetxt update
python -m lifetxt server-init --server-config server-init.json
python -m lifetxt server-update --server-config server-update.json
python -m lifetxt remote profile-list
python -m lifetxt vm run program.life.txt --entry s1
```

| Command | Purpose |
|---|---|
| `check` | Validate life.txt syntax and semantic warnings |
| `integrity` | Run a read-only aggregate data-integrity report |
| `ids` | Audit present, missing, and duplicate item IDs |
| `links` | Inspect ID-based references between items |
| `sources` | Report which input file owns each parsed item |
| `to-json` | Convert life.txt to a JSON array |
| `to-jsonl` | Convert life.txt to JSONL |
| `to-csv` | Convert life.txt to CSV |
| `demo` | Generate valid demo life.txt records for demos, tests, and screenshots |
| `markdown` | Render safe Markdown fields as HTML, text, JSON, or JSONL |
| `import-ics` | Convert iCalendar `.ics` events to life.txt event items |
| `sync-ics` | Fetch iCalendar URLs and regenerate life.txt event items |
| `filter` | Filter items and output life.txt, JSON, or JSONL |
| `from-json` | Convert JSON to life.txt |
| `from-jsonl` | Convert JSONL to life.txt |
| `from-csv` | Convert CSV to life.txt |
| `status` | Show the latest `S` status / presence record for each person |
| `state` (`s`) | Record a presence status, closing the previously open one |
| `files` | Inspect, verify, and hash `file:` and `dir:` attachments |
| `start` | Start work: task in progress, timer running, presence recorded |
| `stop` | Stop work: timer stopped with `elapsed:`, presence closed |
| `notify` | Show or watch due type `M` message notifications |
| `agenda` | Show items related to a datetime range |
| `assist` | Create or update life.txt items from prompts or flags |
| `tui` | Open an interactive terminal workspace for tasks, agenda, and status |
| `fzf` | Select filtered items with `fzf` or `peco` and run an action |
| `timer` | Track elapsed time for one task-like item |
| `stats` | Summarize task, habit, mood, and project activity |
| `git-hook` | Install or inspect Git hooks that validate life.txt files |
| `completion` | Generate shell completion scripts |
| `serve` | Run the optional FastAPI REST API and browser GUI |
| `mcp` | Run the stdio MCP server for AI clients |
| `config` | Create or inspect an external JSON config file |
| `init` | Interactive first-time setup: create life.txt and .lifetxt.json |
| `doctor` | Check Python version, files, dependencies, and data issues |
| `quick` (`q`) | Quickly capture a new item and append it to a file; `-` reads the title from stdin |
| `done` (`d`) | Mark a task done and append `done:`; `--now` records the time. On habit (`H`) items, append `done:DATE` to the completion log instead |
| `complete` | Complete a repeat-enabled task instance and materialize the next occurrence; behaves like `done` otherwise |
| `assign` | Change the `assignee:` on an existing item |
| `batch` | Apply a simple item command across multiple life.txt files |
| `archive` | Move or copy completed/canceled items to a separate archive file |
| `undo` | Restore a file to its state before the most recent write operation |
| `summary` | Show a fast overview of a life.txt file |
| `inbox` | List open tasks with no project, due date, or assignee |
| `cleanup` | Guided file-maintenance navigator: report issues and suggest next commands |
| `health` | Operational sanity checks: stale tasks, missed habits, upcoming deadlines |
| `review` | Human-readable period summary: completed tasks, habits, mood, elapsed time |
| `who` | Team presence summary: latest active `S` item per person |
| `search` | Search items by substring, regex, or `--fuzzy` typo-tolerant match in title or field values |
| `find` | Search across items, projects, people, groups, areas, and proposals; supports `--fuzzy` |
| `snapshot` | Copy a life.txt file to a timestamped snapshot for backups |
| `lint` | Check life.txt for style issues: key-name typos, tag casing, duplicate keys |
| `diff` | Semantic diff between two life.txt files |
| `plot` | Render task/habit/mood/elapsed statistics as bar charts (text/SVG/PNG) |
| `export-heatmap` | Export task or habit activity as a dependency-free SVG heatmap |
| `migrate` | Apply in-place format migrations to a life.txt file |
| `from-markdown` | Convert a Markdown task list (`- [ ] title`) to life.txt items |
| `deps` | Show dependency chains (`depends_on:`/`blocks:`) as an indented tree |
| `tag` | Tag management: list, rename, merge |
| `watch` | Watch life.txt files for changes and re-run a command on each change |
| `encrypt` | Encrypt selected field values in-place using a passphrase |
| `decrypt` | Decrypt `enc:`-tagged field values in-place using a passphrase |
| `share` | Export a self-contained HTML or Markdown report (filter + review + chart) |
| `digest` | Send a `review` summary to Slack, email, or a local file |
| `template` | List and apply reusable named item templates |
| `workspace` | Inspect and validate named workspaces and their source manifests (see [config.md](config.md#named-workspaces)) |
| `project` | List, inspect, and manage projects built from `project:` records (see [projects.md](projects.md)) |
| `portfolio` | Compare projects by state, progress, risk, and workload (see [projects.md](projects.md)) |
| `today` | Daily command center hub: current status, today's events, overdue/due, next actions, blocked, habits, and inbox, optionally scoped with `--saved-view`/`--area` (see [life-hub.md](life-hub.md)) |
| `area` | Group tasks and projects by `area:` (see [life-hub.md](life-hub.md)) |
| `backlinks` | Show items that reference a given ID (incoming links) (see [life-hub.md](life-hub.md)) |
| `temporal` | Show one item's derived temporal context: overdue/due/staleness and nearby dated items (see [life-hub.md](life-hub.md)) |
| `freebusy` | Show busy/free time intervals and overlap conflicts for `E`/`R` items within a datetime range (see [life-hub.md](life-hub.md)) |
| `query` | Filter items with the shared query language (see [query.md](query.md)) |
| `view` | List, inspect, and run saved views (named queries) (see [query.md](query.md)) |
| `group` | Inspect and validate messaging groups (see [messaging.md](messaging.md)) |
| `message` | Compose messages and inspect recipients and delivery state (see [messaging.md](messaging.md)) |
| `person` | Overview of a person's work, messages, meetings, and memberships (see [people.md](people.md)) |
| `proposal` | Unified Inbox: review, edit, accept, or reject staged proposals (see [inbox.md](inbox.md)) |
| `ticket` | Development tickets (`record:ticket`): new, list, show, edit, transitions, links (see [§19](#19-development-tickets-ticket)) |
| `version` | Manage ticket release versions (see [tickets.md](tickets.md)) |
| `sprint` | Manage ticket sprints (see [tickets.md](tickets.md)) |
| `rrule` | Expand a recurrence rule into concrete occurrences (see [13.10](#1310-rrule-expanding-a-recurrence)) |
| `update-check` | Check GitHub for a newer lifetxt release or tag, read-only (see [16](#16-tour-init-and-doctor)) |
| `update` | Fast-forward the running lifetxt git install to a newer release, tag, or ref (see [16](#16-tour-init-and-doctor)) |
| `server-init` | Plan-first Ubuntu Server production bootstrap (see [22](#22-server-init)) |
| `server-update` | Guarded production update for a systemd-managed install (see [23](#23-server-update)) |
| `remote` | Use authenticated Remote Safe Mode from the CLI: profiles, reads, and ticket writes (see [§20](#20-remote-safe-mode-client-remote)) |
| `vm` | Opt-in, isolated Turing-complete VM: execute valid life.txt records as a 2-counter machine (see [vm.md](vm.md)) |

lifetxt also has a small set of workflow and format-1.0 commands not detailed
in this file; see [§21](#21-commands-documented-elsewhere) for pointers.

### 1.1 Command Categories and Guided Paths

The table above is the complete flat reference. For a role-based index --
and for beginners who don't yet know which command name to look for -- run:

```sh
python -m lifetxt help
```

`help` (with no arguments) shows a "Start here" quick loop, the guided-path
audiences below, and this same category grouping. `python -m lifetxt --help`
also prints the category grouping ahead of the full flag reference. See
[§16](#16-tour-init-and-doctor) for `help`'s full command reference,
including its `--json` machine-readable form for scripts and AI clients.

| Category | Commands |
|---|---|
| Getting Started / Daily | `tour`, `help`, `init`, `quick` (`add`), `today`, `next`, `agenda`, `show`, `edit`, `done`, `complete`, `progress`, `clone`, `reopen`, `due`, `review`, `assist`, `state`, `start`, `stop`, `assign`, `timer`, `notify` |
| Query / Explore | `filter`, `search`, `find`, `query`, `view`, `summary`, `inbox`, `health`, `temporal`, `freebusy`, `count`, `status`, `recent` |
| Projects / People / Collaboration | `project`, `portfolio`, `area`, `person`, `group`, `who`, `message`, `proposal`, `ticket`, `version`, `sprint` |
| Structure / Data Integrity | `check`, `integrity`, `ids`, `links`, `backlinks`, `sources`, `tag`, `lint`, `deps`, `diff`, `snapshot`, `undo`, `cleanup`, `files` |
| Import / Export / Reports | `import`, `import-ics`, `sync-ics`, `to-json`, `to-jsonl`, `to-csv`, `from-json`, `from-jsonl`, `from-csv`, `from-markdown`, `from-todo`, `to-ics`, `markdown`, `stats`, `plot`, `export-heatmap`, `standup`, `invoice`, `share`, `digest`, `report` |
| Interfaces / Integration | `tui`, `fzf`, `web`, `serve`, `mcp`, `ai`, `completion`, `git-hook`, `watch`, `remote` |
| Workspace / Configuration / Safety | `config`, `workspace`, `path`, `doctor`, `format`, `safety`, `capabilities`, `attachment`, `update`, `update-check`, `server-init`, `server-update`, `server-report` |
| Personal Context | `context`, `memory`, `decisions` |
| Advanced / Experimental | `archive`, `batch`, `encrypt`, `decrypt`, `migrate`, `template`, `demo`, `vm`, `rrule` |

Guided paths (`python -m lifetxt help AUDIENCE`):

| Audience | Flow |
|---|---|
| Beginner | `tour` -> `init` -> `add` -> `today` -> `done` |
| Daily user | `add` -> `today` -> `next` -> `show`/`edit` -> `review` |
| Power user | `query` -> `view` -> `project` -> `workspace` -> `links` |
| AI user | `mcp` -> `ai` -> `context` |
| Administration / development | `integrity` -> `safety` -> `format` -> `capabilities` |

Looking up one command (`python -m lifetxt help NAME`, alias names such as
`add` resolve to their canonical command) prints its category, aliases,
read-only/destructive classification, a copyable example, and related
commands -- add `--json` (or `--format json`) for the machine-readable form.
This category/audience/command metadata lives in one place,
`lifetxt/cli_taxonomy.py`, so `--help`, `help`, and this table cannot drift
from each other without failing `tests/test_cli_taxonomy.py`.

### 1.2 Localization

lifetxt's human-readable CLI text (headings, guidance, `help`) can be shown in
English or Japanese. Command names, options, Format 1.0 syntax, and every
machine-readable output (`--json`/`--format json`/JSONL/CSV, the Web API, MCP,
and schemas) never change with locale -- only presentation text does.

```sh
lifetxt --lang ja help beginner
LIFETXT_LANG=ja lifetxt today
lifetxt --lang en today
```

Locale is resolved in this order: an explicit `--lang` value, then the
`LIFETXT_LANG` environment variable, then the OS/process locale, then English.
A Japanese OS locale in any of its common forms (`ja`, `ja_JP`, `ja-JP`,
`ja_JP.UTF-8`) normalizes to `ja`; an unsupported locale falls back to English
rather than failing. A missing Japanese translation for a given string also
falls back to English rather than crashing or printing nothing.

```sh
lifetxt --lang ja help
lifetxt --lang fr help    # unsupported locale: falls back to English
```

Beginner/daily flows (`tour`, `init`, `add`/`quick`, `today`, `done`/`complete`)
and a representative slice of `check`/`lint`/`doctor`'s own fixed labels and
next-step guidance are covered. Individual parser/validator diagnostic
messages are not yet translated -- their raw text, code, severity, and
location fields stay in English and are unaffected by `--lang` either way.

### 1.3 Fuzzy Search

`search` and `find` match exact substrings by default. Add `--fuzzy` to also
match a field within a small typo/edit distance of the pattern -- useful when
you mistype or slightly misremember a word. Fuzzy matching is opt-in and
compares Unicode-normalized text (so full-width and half-width Japanese
variants, and Latin case differences, do not matter); an exact substring
match always ranks ahead of an approximate-only one. `--fuzzy` cannot be
combined with `search --regex`, since a compiled regex has no similarity
score to compare.

```sh
python -m lifetxt search "stast" --fuzzy life.txt   # matches a title containing "stats"
python -m lifetxt find "stast" life.txt --fuzzy      # same tolerance across items, projects, people, groups, areas, proposals
```

### 1.4 Guarded `lint --fix`

`lint` is read-only by default. `--fix` auto-corrects only the findings it
can resolve with a single, deterministic, meaning-preserving replacement --
a known key-name typo (`L001`) or non-standard key casing (`L002`). Every
other finding (a duplicate key, or a custom `--ruleset` match) is left
untouched: `--fix` never guesses at an ambiguous replacement.

```sh
python -m lifetxt lint life.txt --fix              # apply safe fixes
python -m lifetxt lint life.txt --fix --dry-run    # preview without writing
```

Before writing anything, `--fix` builds the complete fix plan for a file and
re-parses the resulting text with the canonical parser. If even one planned
fix would introduce a parse error, that file's fixes are skipped entirely
(reported by name) rather than partially applied -- a fix is only ever
written as one complete, already-revalidated file.

## 2. Common Conventions

### 2.0 Global Options

Three options are recognized before the subcommand name, for every command:

| Option | Meaning |
|---|---|
| `--version`, `-V` | Print `lifetxt VERSION` and exit 0. Ignores every other argument |
| `--config FILE` | External JSON config file (see below) |
| `--workspace NAME` | Named workspace to resolve inputs and the write target from (see [config.md](config.md#named-workspaces)) |

```sh
python -m lifetxt --version
python -m lifetxt --workspace work agenda
python -m lifetxt --config .lifetxt.json --workspace work check
```

`--workspace` selects one of the `workspaces` entries in the loaded config,
resolving its declared sources into the input-path/write-target set used by
that command -- it replaces `paths`/`write_file`-only configuration for
projects that define more than one named workspace. `lifetxt workspace list`,
`show`, `files`, `validate`, and `doctor` inspect workspaces directly.

#### External Config

Any command may receive `--config FILE` before or after the subcommand. If it is
omitted, the CLI checks `LIFETXT_CONFIG`, `.lifetxt.json`, and
`lifetxt.config.json` in that order.

```sh
python -m lifetxt config init -o .lifetxt.json
python -m lifetxt --config .lifetxt.json check
python -m lifetxt agenda --config .lifetxt.json --around now --window 1d
```

`paths` supplies default input files for life.txt-reading commands, `write_file`
supplies the default writable file for `serve`, `web` supplies server defaults,
`message` supplies assist defaults for type `M`, and `sync_ics` supplies default
calendar sync sources and output.

### 2.1 Input Paths

For commands that read files, `path ...` is optional and may contain multiple
files. Multiple inputs are read in order. Paths may be glob patterns such as
`*.life.txt` or `projects/**/*.life.txt`. When a directory is passed, the CLI
reads life.txt-like `.txt` files in that directory.

Multi-file input expansion is deterministic: explicit paths retain caller
order; glob matches are sorted by path; directory matches use the fixed pattern
priority `life.txt`, `*.life.txt`, `*_life.txt`, `*.txt`, with names sorted
within each pattern; duplicate paths are removed by absolute-path identity.

```sh
python -m lifetxt check life.txt
python -m lifetxt check work.life.txt home.life.txt
python -m lifetxt check "projects/**/*.life.txt"
python -m lifetxt check examples
python -m lifetxt check -
type life.txt | python -m lifetxt check
```

If paths are omitted or the path is `-`, the command reads from stdin.
When input comes from files, diagnostics include the source path before the line
and column number. Stdin-only diagnostics omit the source path.

All files loaded by one command form one logical input set for ID checks and
references. `parent:`, `ref:`, `depends_on:`, `blocks:`, `related:`,
`duplicate_of:`, and `replaced_by:` can point to IDs in any loaded file.
Commands such as `check`, `links`, `ids`,
`to-json`, and `to-jsonl` use this same input set, so pass every related file
or configure shared paths when you want cross-file references to resolve.
Reference cycle detection (`parent:`, `depends_on:`/`blocks:`,
`duplicate_of:`, `replaced_by:`) also spans every loaded file, not just the
file the cycle happens to start in.

A missing or permission-denied file among multiple input sources fails the
entire operation before any output is produced. The error names the failing
path (via the underlying OS error) and the command exits non-zero; the
remaining, readable sources are never partially read or reported on. This is
enforced once, uniformly, for every command by `lifetxt`'s top-level entry
point rather than per command. A symlinked input file is read like any other
file rather than silently skipped; because path deduplication compares
absolute paths rather than resolving symlinks, a symlink and the real file it
points at are treated as two distinct sources if both are passed, which
correctly produces a duplicate-ID warning rather than silently merging them.

### 2.2 Output Paths

Commands with `-o` / `--output` write to a file. Without `--output`, output is
written to stdout.

For `assist` create mode, `--output FILE` appends the generated line to `FILE`.
It does not overwrite the file. In `assist --update` mode, `--output FILE`
writes the updated whole file to `FILE`.
Whole-file writes use a temporary file and atomic replace. For bulk ID backfill,
use `ids --assign --backup` to keep a `FILE.bak` copy before writing.

### 2.3 Output Formats

Several commands support machine-readable output.

| Format | Meaning |
|---|---|
| `text` | Human-readable table or diagnostics |
| `life` | life.txt lines |
| `json` | JSON array |
| `jsonl` | One JSON object per line |

### 2.4 Nested Items

Indented item lines are parsed as nested records. If an indented item does not
already have `parent:`, the parser infers `parent:` from the nearest
less-indented ancestor that has the selected ID key, normally `id:`.

```txt
[ ] T Research_Project id:proj_research
  [ ] T Literature_Review id:task_lit
    [N] N Reading_Memo
```

Machine-readable JSON includes an `indent` field for indented items. The
canonical hierarchy form is explicit `parent:`. Life output preserves original
lines by default; `--canonical` writes unindented lines and keeps or adds
explicit `parent:` details when the parent can be inferred.

### 2.5 Exit Codes

| Code | Meaning |
|---|---|
| `0` | Success |
| `1` | Validation error or command error |
| `2` | CLI usage error, such as missing subcommand |

### 2.5.1 CLI Error Recovery

Every CLI-level error (as opposed to a `check` diagnostic about life.txt
content itself; see [§3](#3-check)) still prints its original one-line
`ERROR: ...` message to stderr, unchanged, with the same exit code as
before -- scripts and redirected output see byte-identical behavior. When
stderr is a real interactive terminal, five common, easily-recovered error
families additionally get actionable follow-up guidance appended after
that line:

| Family | Extra guidance |
|---|---|
| Unknown command (a typo such as `todya`) | `Did you mean?` naming the closest real command name(s) from the same runtime-derived registry `lifetxt help` uses (never a fabricated command), plus `lifetxt help beginner` |
| Missing value for a global option (`--config`, `--workspace`, `--lang`) | The exact `Usage: --OPTION VALUE_KIND` form |
| Unknown workspace name | `Did you mean?` against the real configured workspace names, plus the full `Available:` list |
| Missing or malformed configuration file (invalid JSON, not a JSON object) | `lifetxt doctor` as the next step |
| Missing or unreadable input path | The unreadable path restated plainly, plus `lifetxt path` to see what lifetxt would actually use |

A suggestion is only ever a real, currently valid name (a command,
workspace, or alias) -- an error with no close match shows no `Did you
mean?` line rather than guessing. This never changes an exit code, and it
never adds anything to `--format json`/`--format jsonl` output or any other
structured output.

### 2.6 Format Compatibility

The CLI follows the file grammar in
[`life_txt_format_spec.md`](./life_txt_format_spec.md). The important
compatibility rules are:

- `key:value` is the only detail syntax in a life.txt file.
- `key=value` is accepted only by helper inputs such as `assist -d`,
  `assist --add-detail`, and the interactive detail prompt.
- A trailing `\` joins the following physical line before parsing; all reading
  commands use this same logical-line parser.
- JSON and JSONL details are always arrays, even when the item has only one
  value for a key.
- CSV conversion requires `status`, `type`, and `title` columns. Other non-empty
  columns become details; JSON array cells become repeated detail values.
- `filter`, `agenda`, `stats`, `to-json`, `to-jsonl`, `to-csv`, and
  `markdown` share the same item filter implementation for status, type,
  project, tag, user, team, detail, text, and time filters.
- `check`, `ids`, `links`, and all converters use the same parser, so syntax
  accepted by one reading command is accepted by the others.
- Multiple input files are parsed as one logical set for duplicate-ID and
  reference checks.

CLI command coverage:

| Command | Reads life.txt | Writes life.txt | Validates syntax | Supports item filters |
|---|---:|---:|---:|---:|
| `check` | yes | no | yes | no |
| `ids` | yes | optional with `--assign` | yes | no |
| `links` | yes | no | yes | relation filters only |
| `to-json`, `to-jsonl`, `to-csv`, `markdown` | yes | no | yes | yes |
| `from-json`, `from-jsonl`, `from-csv` | no | yes | serializer rules |
| `demo` | no | optional | generated item validation | type selection only |
| `filter` | yes | yes | yes | yes |
| `status` | yes | no | yes | `--person`, `--active` |
| `notify` | yes | no | yes | notification-specific |
| `agenda` | yes | optional with `--format life -o` | yes | yes |
| `assist` | optional for update | yes | yes unless `--no-check` | no |
| `import-ics`, `sync-ics` | `.ics` | yes | generated item validation |
| `tui` | yes | no | yes | dashboard-specific |
| `fzf` | yes | `done` and `delete` actions | yes | yes |
| `timer` | yes | `start` and `stop` update one item | yes | summary filters |
| `stats` | yes | no | yes | yes |
| `git-hook` | no | Git hooks only | no | no |
| `completion` | no | optional script output | no | no |
| `serve` | yes | yes through API/UI | yes | URL/API filters |

## 2.7 Shorthand Notation

Frequently used operations have shorter forms. They are shared by the CLI, TUI,
and Web UI, so a token means the same thing everywhere.

### Capture sigils

`quick`, the TUI `/add`, and the Web quick-add box expand four sigils out of the
title:

| Sigil | Expands to | Example |
| --- | --- | --- |
| `@NAME` | `project:NAME` | `@home` |
| `#NAME` | `tag:NAME` | `#errand` |
| `!VALUE` | `priority:VALUE` | `!high` |
| `^DATE` | `due:DATE` | `^tomorrow` |

```sh
lifetxt q "Buy milk @home #errand !high ^tomorrow"
# [ ] T "Buy milk" project:home tag:errand priority:high due:2026-07-20 id:task_...
```

Only whole whitespace-delimited words count, so `Mail a@b.com about it` keeps
the address and `Compute 10 ^ 2` keeps the caret. Prefix a token with a
backslash (`\@literal`) to keep it verbatim, or pass `--no-shorthand` to
disable expansion for one capture. Repeated `#tags` accumulate; for
single-valued keys an explicit flag such as `--project` wins over the sigil.

A title made only of sigils is rejected rather than creating an untitled record,
and an unrecognized `^date` fails loudly instead of writing an unparseable
value.

### Named capture presets

`--preset NAME` applies a configured `capture.presets.<name>` object's
`type`/`status`/`project`/`tags`/`priority` defaults before shorthand and
explicit flags run, so both still win over the preset for the same field:

```sh
lifetxt quick --preset work-task "Prepare proposal"
lifetxt quick --preset work-task "Fix bug !high"    # explicit !high overrides preset priority
lifetxt add --preset idea "Try local-first sync"    # add/q share the same --preset
```

See [config.md](config.md#named-capture-presets) for the configuration
contract, precedence rules, and tag-merge behavior.

### Relative date tokens

Anywhere a date is accepted — `--due`, `--do`, `--until`, `^` sigils, and the
TUI `/due` — these tokens resolve to an ISO date:

| Token | Meaning |
| --- | --- |
| `today` / `tomorrow` / `yesterday` | the obvious calendar day |
| `monday` .. `sunday` | the next occurrence of that weekday |
| `next_monday` .. `next_sunday` | that weekday next week |
| `next_week` | the coming Monday |
| `+3d` `-1w` `+2m` `+1y` | signed offsets in days, weeks, months, years |

Month offsets clamp to a valid day, so 31 January `+1m` is 28 February. The set
is closed: anything else is passed through unchanged where that is safe, and
rejected where a real date is required.

### Command aliases

| Alias | Command |
| --- | --- |
| `add` | `quick` |
| `q` | `quick` |
| `d` | `done` |
| `s` | `state` |
| `a` | `agenda` |
| `f` | `filter` |

`add` is the beginner-facing spelling: `lifetxt add "Buy milk ^tomorrow"` is
exactly `lifetxt quick "Buy milk ^tomorrow"` -- same parser, same handler, same
write path. `quick`/`q` remain fully supported for existing workflows and
scripts.

The TUI has its own one-letter aliases in the command palette: `/d` `/s` `/a`
`/f` `/t` `/e` `/u` `/n` `/q`. An exact alias always wins over fuzzy ranking, so
`/d` is `/done` and never `/detail` or `/delete`.

---

## 2.8 Presence Status

`status` reads the current presence; `state` (alias `s`) writes it.

```sh
lifetxt s busy                          # open a status, closing the previous one
lifetxt state focus --title "Deep Work" # with an explicit title
lifetxt state busy --note "in the lab" --project research
lifetxt state --end                     # close the current status
lifetxt status                          # read the current status
```

A transition is one edit: the person's open `S` record gets `to:` plus `[x]`,
and a new `[/]` record is appended with `from:`. Doing this by hand is what
leaves two records that both look current.

Switching to the state that is already open writes nothing and says so, because
repeating `lifetxt s busy` would otherwise split one long busy block into a stub
plus a new record and lose the real start time. Pass `--force` when you really
want a new record. Use `--at YYYY-MM-DDTHH:MM` to backdate a transition, and
`--person` for someone else. If two records are already open for the same
person, a transition closes both rather than adding a third.

---

## 2.9 Completion Time

`done` appends `done:` when it closes a task. The precision is configurable:

```sh
lifetxt done life.txt t1              # done:2026-07-19
lifetxt done life.txt t1 --now        # done:2026-07-19T14:32
lifetxt done life.txt t1 --date-only  # force a date even when config says datetime
```

```json
{ "done": { "precision": "datetime" } }
```

`precision` accepts `date` (the default) or `datetime`; anything else fails
loudly. Flags override config. Habit (`H`) completion logs stay date-only in
every configuration, because the log is one entry per calendar day and a time
would break same-day duplicate detection.

The format spec already allows `done:` to be a date or a datetime, so turning
this on does not change the file format.

---

## 2.10 Start And Stop

`start` and `stop` combine the three edits that bracket a work session.

```sh
lifetxt start life.txt t1     # task -> [/], timer starts, presence -> busy
lifetxt stop                  # timer stops and writes elapsed:, presence closes
lifetxt stop --done           # also close the task and write done:
```

`start` accepts `--state` to use something other than `busy`, and
`--no-timer` / `--no-presence` to skip either half. `stop` reads the running
timer for the file and item, so it needs no arguments. Both support `--dry-run`.

Only one timer runs at a time, shared with `lifetxt timer`, so `start` refuses
to begin a second one and names the task already running.

---

## 2.11 External Files And Directories

`file:` and `dir:` associate an item with something on disk. Paths are stored
with forward slashes and resolve relative to the **life.txt file**, not the
shell's working directory, so the same file gives the same answer from anywhere.

```sh
lifetxt files life.txt                 # list every attachment and its status
lifetxt files life.txt --update        # write or refresh #sha256= hashes
lifetxt files life.txt --check         # exit 1 if anything is missing or changed
lifetxt files life.txt --problems      # only show what needs attention
lifetxt files life.txt --format json   # machine-readable
```

| Status | Meaning |
| --- | --- |
| `ok` | Exists and the recorded hash matches |
| `unhashed` | Exists; no hash recorded yet |
| `changed` | Exists but the content differs from the recorded hash |
| `missing` | Nothing at that path |
| `wrong_type` | `file:` points at a directory, or `dir:` at a file |
| `error` | The value could not be parsed or read |

`--update` normalizes the stored path at the same time, so a Windows-style
`.\docs\spec.md` becomes `./docs/spec.md`. Missing targets keep their bare
path rather than gaining a misleading hash.

`check` includes attachment diagnostics. Existence and portability are checked
by default because they are cheap; hash verification reads every referenced
file and walks directory trees, so it is opt-in:

```sh
lifetxt check life.txt                  # W401 missing, W403 wrong type, W404 non-portable
lifetxt check life.txt --verify-files   # adds W402 content changed
lifetxt check life.txt --no-files       # skip attachment checks entirely
lifetxt check life.txt --category files # only attachment diagnostics
```

Directory hashes exclude version-control and build directories. Configure with:

```json
{
  "attachments": {
    "ignore": [".git", "node_modules", "__pycache__"],
    "max_files": 2000,
    "max_bytes": 209715200
  }
}
```

The guards fail loudly rather than hanging when `dir:` points somewhere huge.

---

## 3. `check`

Validate life.txt syntax and semantic rules.

```sh
python -m lifetxt check [path ...] [--format text|json|sarif] [--warnings-as-errors]
python -m lifetxt check life.txt --severity warning --category reference
python -m lifetxt check life.txt --code E010,W213 --format json
python -m lifetxt check life.txt --format sarif > lifetxt.sarif
```

Options:

| Option | Meaning |
|---|---|
| `path ...` | Input file(s), or `-` for stdin |
| `--format text` | Print human-readable diagnostics |
| `--format json` | Print diagnostics as JSON |
| `--format sarif` | Print diagnostics as a SARIF 2.1.0 document (see below) |
| `--warnings-as-errors` | Exit non-zero when warnings are present |
| `--severity error|warning` | Show only matching severities; repeatable or comma-separated |
| `--code CODE` | Show only matching diagnostic codes such as `E010` or `W213`; repeatable or comma-separated |
| `--category CATEGORY` | Show only matching diagnostic categories; repeatable or comma-separated |

Diagnostic filters affect both output and exit code. For example,
`--category reference` exits according to matching reference diagnostics only,
not unrelated syntax or style diagnostics.

Categories:

| Category | Typical diagnostics |
|---|---|
| `syntax` | Parser errors such as malformed status, type, title, or detail syntax |
| `schema` | Invalid core status/type values |
| `style` | Key style and custom-key recommendations |
| `time` | Date/time value format and range warnings |
| `status` | Presence/status item rules |
| `message` | Message item sender/recipient/notification rules |
| `id` | Duplicate IDs and unsafe ID-like values |
| `reference` | Missing, self, cyclic, or ambiguous references |
| `recurrence` | `repeat:`, `RRULE:`, `interval:`, and `count:` recommendations |
| `duration` | Duration fields such as `est:` and `elapsed:` |
| `workflow` | Status/detail workflow and dependency-state recommendations |
| `files` | Attachment target, type, content-hash, and portability diagnostics |
| `semantic` | Fallback category for semantic diagnostics not covered above |

JSON diagnostics:

`check --format json` returns an array of diagnostic objects. The stable fields
are `severity`, `code`, `category`, `message`, `source`, `line`, `column`, and
`hint`. `category` is part of the published contract and matches the categories
accepted by `--category`. `hint` is always present as a string; diagnostics with
no safe generic guidance use `""`. Parser and validator diagnostics with clear
remediation publish non-empty hints. This release leaves no parser or validator
diagnostic code intentionally empty; other diagnostic producers may still emit
`""` when there is no safe guidance to provide.

`source`, `line`, and `column` are omitted when that location component is not
known. Consumers must ignore unknown fields so future releases can add fields
without breaking scripts. The current transition is additive: scripts written
against the previous CLI JSON output should keep reading their existing fields
and relax exact-key validation to tolerate `hint` and future unknown fields.
Existing stable fields are not removed or renamed without first documenting a
transition period; the old spelling remains available during that period and is
removed only in a later release. `span` is intentionally deferred until
parser-native end spans are implemented; do not infer a stable `span` from
`line` and `column`.

The same diagnostic object shape is used by the raw-line validation surfaces
`POST /api/check-line` and MCP `check_line`.

Text diagnostics:

`check`'s default text output renders each diagnostic as a small block: a
header line (`path:line:column  SEVERITY CODE  message`), a source-line
snippet with a `^` caret (or a `^~~~` range when the diagnostic's own end
position is known and on the same line), and the diagnostic's `hint` text
when one is present. A source snippet is shown only when the diagnostic's
file can still be read at its original path and line number; an unreadable
or already-modified source falls back to the header line alone rather than
failing. A trailing `N problems: X error(s), Y warning(s)` line summarizes
the full filtered set. This is a presentation-only enhancement over the
stable JSON fields above; `--format json` is completely unaffected.

For a small, explicitly supported set of diagnostics -- an invalid status or
type token, a detail key that is close to a known or type-recommended key, and
an invalid `state:` value -- the text output may add a `Did you mean?` line
(or a bulleted list when more than one candidate is equally plausible) right
after the diagnostic's own hint. This is a suggestion only: it never changes
what the parser or validator accepts, never mutates the file, and never
changes a diagnostic's severity, code, or the command's exit code. Candidates
come only from lifetxt's existing canonical vocabulary (the status/type token
lists and their known aliases, the known/recommended detail-key sets, and the
known `state:` values); a key that has no close match to that vocabulary is
left alone as ordinary custom data, never guessed at. `--format json` never
carries a suggestion field.

The text output also marks one narrow, evidenced root-cause/secondary
relationship: repeated `E009`/`E010` ("this does not look like a detail")
failures on the *exact same* source line, which the parser can only ever
produce from one call to its per-line detail-parsing loop (for example, an
unquoted multi-word title spills its remaining words into that loop as
several separately-reported failures). The first such diagnostic on the
line gets a `Related: N other diagnostic(s) on this line may be
consequences of this one` note; each later one gets `Related: possibly
caused by CODE at column N above; fix that first`. This is deliberately
narrow: two diagnostics that merely sit on the same or nearby lines, share
a similar code, or have similar wording are never linked this way -- only
this one specific, structurally-guaranteed pair of codes is. `--code`/
`--severity`/`--category`/`--ignore` filtering is applied first, and the
relationship is recomputed over whatever remains: filtering away every
partner leaves a lone diagnostic with no relation note, and filtering away
only the first diagnostic still lets the remaining ones on that line form
their own group. `--format json` never carries this relationship either.

SARIF output:

`--format sarif` emits a [SARIF 2.1.0](https://docs.oasis-open.org/sarif/sarif/v2.1.0/sarif-v2.1.0.html)
document over the exact same filtered diagnostics `text`/`json` render --
`--code`/`--severity`/`--category`/`--ignore`/`--warnings-as-errors` all
apply identically, and the resulting result count and order always match
`--format json`'s diagnostic array. This is a pure, read-only export: it
never re-runs or changes validation, and it has no network, upload, or
credential handling of its own -- pipe the output to a file and hand that
file to whatever consumes SARIF (for example GitHub Code Scanning's
`upload-sarif` Action, or an IDE extension):

```sh
python -m lifetxt check life.txt --format sarif > lifetxt.sarif
```

Mapping: `code` becomes `ruleId` (one deduplicated rule entry per distinct
code, never repeated per occurrence); `severity` becomes `level`
(`error`/`warning`, matching lifetxt's only two severities); `source`
becomes `artifactLocation.uri` (an absolute path becomes a `file://` URI on
either Windows or POSIX; a relative path -- the common case -- is used
as-is, which SARIF's relative-URI-reference form permits directly);
`line`/`column` become `region.startLine`/`startColumn` with no offset
conversion, since SARIF's column semantics already match lifetxt's own
1-based convention; `end_line`/`end_column` become `region.endLine`/
`endColumn` only when a diagnostic already carries a precise end position
-- an unknown end is never invented. `hint`, when non-empty, is carried as
`result.properties.hint`. `text`/`json` output is completely unchanged by
this addition.

Examples:

```sh
python -m lifetxt check life.txt
python -m lifetxt check life.txt --warnings-as-errors
python -m lifetxt check life.txt --format json
python -m lifetxt check life.txt --format sarif > lifetxt.sarif
python -m lifetxt check life.txt --category id,reference
```

### 3.1 `ids`

Audit item IDs without changing files.

```sh
python -m lifetxt ids [path ...] [--only all|present|missing|duplicates]
```

Options:

| Option | Meaning |
|---|---|
| `path ...` | Input file(s), or `-` for stdin |
| `--key KEY` | Detail key to audit; defaults to config `ids.key`, `api.id_key`, or `id` |
| `--only all` | Show summary, duplicate IDs, and missing IDs |
| `--only present` | Show all present ID values |
| `--only missing` | Show items without the selected ID key |
| `--only duplicates` | Show duplicate ID values only |
| `--format text|json|jsonl` | Output format |
| `--pretty` | Pretty-print JSON output |
| `--assign` | Assign IDs to items missing the selected ID key |
| `--dry-run` | Show planned assignments without writing files |
| `--backup` | Write `FILE.bak` before modifying a file with `--assign` |
| `--prefix PREFIX` | ID prefix for `--assign`; defaults to the configured type prefix |

Examples:

```sh
python -m lifetxt ids life.txt
python -m lifetxt ids life.txt archive.life.txt --only duplicates
python -m lifetxt ids life.txt --only missing --format json --pretty
python -m lifetxt ids life.txt --assign --dry-run
python -m lifetxt ids life.txt --assign --backup
python -m lifetxt ids "projects/**/*.life.txt" --assign --prefix item --dry-run
```

### 3.2 `links`

Inspect relationships that point to item IDs. The command understands
`parent:`, `ref:`, `depends_on:`, `blocks:`, `related:`, `duplicate_of:`,
and `replaced_by:`.

```sh
python -m lifetxt links [path ...]
python -m lifetxt links life.txt --id task_report --direction incoming
python -m lifetxt links life.txt --id task_report --direction outgoing --format json --pretty
python -m lifetxt links life.txt --relation depends_on --relation blocks
python -m lifetxt links life.txt --chain task_report
python -m lifetxt links life.txt --chain task_report --format json --pretty
python -m lifetxt links life.txt --topo
python -m lifetxt links life.txt --critical-path
python -m lifetxt links life.txt --critical-path --chain task_report
python -m lifetxt links life.txt --path task_a task_b
```

Options:

| Option | Meaning |
|---|---|
| `--id ID` | Show only links connected to this ID |
| `--chain ID` | Show the dependency blocker chain for this item ID; also usable as `--critical-path`'s root |
| `--direction incoming|outgoing|both` | Direction when `--id` is used |
| `--relation RELATION` | Limit to a relation key such as `depends_on`; repeatable or comma-separated |
| `--topo` | Print a topological order over the `depends_on`/`blocks` graph (or the `--relation` subset). Refuses loudly on a cycle |
| `--critical-path` | Print the longest `depends_on`/`blocks` chain (or the `--relation` subset), optionally rooted at `--chain ID` |
| `--path FROM TO` | Print the shortest chain of relations connecting two item IDs, over the full relation graph (or the `--relation` subset), traversed in both directions |
| `--key KEY` | ID detail key; defaults to config `ids.key`, `api.id_key`, or `id` |
| `--format text|json|jsonl|mermaid|dot` | Output format. `--chain`, `--topo`, `--critical-path`, and `--path` support `text`, `json`, and `jsonl` only |
| `--pretty` | Pretty-print JSON |

`--topo`, `--critical-path`, and `--path` are mutually exclusive with each
other and with `--id`/`--chain`, except that `--critical-path` accepts
`--chain ID` as its optional root. `--critical-path`'s JSON/jsonl output
includes an `estimate_sum` field, populated only when every item on the
winning chain carries a plain numeric `estimate:` detail (not `elapsed:`'s
`Xh`/`Ym` duration syntax); it is `null` otherwise. `--path`'s output is a
list of hops, each carrying the connecting `relation` and `direction`
(`incoming`/`outgoing`) except the first hop, which has neither.

`check` reports missing references (`W215`), self references (`W216`),
`parent:` cycles (`W217`), ambiguous references (`W218`), completed items
whose `depends_on:` prerequisite is still open (`W224`), combined
`depends_on:`/`blocks:` cycles (`W227`), `duplicate_of:` cycles (`W228`),
and `replaced_by:` cycles (`W229`).
For duration fields such as `est:` and `elapsed:`, `check` reports
non-canonical but parseable values as `W222` and unrecognized values such as
`elapsed:1d` as `W226`.

Dependency behavior:

- `depends_on:ID` blocks the current item while `ID` is open.
- `blocks:ID` independently marks `ID` as blocked while the current item is open.
- `health` reports blocked open items as `W305`.
- `links --chain ID` and `deps --root ID` print the same blocker chain in a
  terminal-friendly tree. The chain includes both direct `depends_on:` blockers
  and inverse `blocks:` blockers.

### 3.3 `sources`

Report source ownership for parsed items. This is useful when commands read
multiple hand-written files, generated calendar files, and archives together.

```sh
python -m lifetxt sources [path ...]
python -m lifetxt sources "projects/**/*.life.txt" --format json --pretty
python -m lifetxt sources life.txt archive.life.txt --missing-id
```

Options:

| Option | Meaning |
|---|---|
| `path ...` | Input life.txt file(s), directory, glob, or `-` for stdin |
| `--key KEY` | Detail key shown as the item ID; defaults to config `ids.key`, `api.id_key`, or `id` |
| `--missing-id` | Show only items missing the selected ID key |
| `--format text|json|jsonl` | Output format |
| `--pretty` | Pretty-print JSON output |

The report includes source path, line range, selected ID, parent ID, type,
status, title, indentation level, and detail count. It also runs duplicate-ID
and reference checks across the same logical input set and prints warnings to
stderr.

### 3.4 `integrity`

Run a read-only aggregate integrity report over the selected input set. The
first slice reuses existing parser, validator, duplicate-ID/reference,
attachment, workspace, and ticket checks where their context is available.
It does not repair, rewrite, migrate, archive, recover, or delete data.

```sh
python -m lifetxt integrity [path ...]
python -m lifetxt integrity life.txt --json
python -m lifetxt integrity life.txt --profile strict --json
python -m lifetxt integrity life.txt --verify-files
python -m lifetxt integrity life.txt --ai-context --json
python -m lifetxt integrity life.txt --graph --json
python -m lifetxt integrity plan life.txt
python -m lifetxt integrity apply life.txt --expected-revision HASH --confirm --json
```

Options:

| Option | Meaning |
|---|---|
| `path ...` | Input life.txt file(s), directory, glob, or configured paths |
| `--json` | Emit the `integrity-v1` JSON report |
| `--profile default\|strict` | Keep default effective severities or escalate warnings to errors in the report only |
| `--verify-files` | Verify `file:` / `dir:` hashes in addition to cheap attachment checks |
| `--ai-context` | Add opt-in AI-safe workspace and Personal AI Memory convention diagnostics |
| `--graph` | Add opt-in relation-graph health diagnostics: orphan items, most-referenced hubs, connected components, and the longest `depends_on`/`blocks` chain |

JSON diagnostics include `severity`, `effective_severity`, `code`,
`category`, `message`, `hint`, `source_file`, `line`, `column`, `item_id`,
`check_state`, and `details`. Missing files and unavailable optional contexts
are reported as blocked or skipped checks instead of being silently omitted.
Strict profile mapping never changes `lifetxt check`; it only changes
`effective_severity` in integrity output.

`--ai-context` adds read-only `category: ai_context` diagnostics. These checks
report whether a named workspace resembles the #500 AI-safe pattern (broad read
context with a dedicated writable inbox/proposal target) and whether Personal AI
Memory candidates follow the #503 convention (`N` records with `person:` and
`tag:preference`, `tag:goal`, or `tag:decision`). The flag does not change MCP,
proposal, query, or write behavior.

`--graph` adds read-only `category: graph` diagnostics, reusing `lifetxt links`'s
own engines (`link_records`, `critical_path`) rather than a second graph
implementation: `G002` lists items with a unique `id:` that carry no relation of
any kind (bounded to 20 ids, `details.truncated` set when more exist); `G003`
lists the top 10 most-referenced item ids by relation count; `G004` reports the
connected-component count and the largest component's size over the full
relation graph; `G005` reports the longest `depends_on`/`blocks` chain length
and path, or reports `blocked` with a `warning` severity when the graph contains
a cycle (see `check`'s `W227`). The flag does not repair, rewrite, or otherwise
change any file.

`python -m lifetxt integrity plan ...` emits an `integrity-plan-v1` JSON plan.
The plan is deterministic and non-mutating: automatic entries describe safe
candidates such as missing ID assignment, while ambiguous, missing-source, sync,
reference, and recovery findings remain manual or blocked review items. Every
file-backed action includes the current expected source revision when it can be
read.

`python -m lifetxt integrity apply ...` is intentionally narrow. It only applies
the automatic missing-ID assignment repair, requires one explicit file path,
requires `--expected-revision`, and refuses to write unless `--confirm` is
present. Revision mismatch, parse errors, and unsupported repair classes fail
closed before writing. The command reports an `integrity-apply-v1` result with
before/after revisions and assignment records.

## 4. Conversion And Rendering

### 4.1 `to-json`

Convert life.txt to a JSON array.

```sh
python -m lifetxt to-json [path ...] [-o output.json] [--pretty] [filter options]
```

Options:

| Option | Meaning |
|---|---|
| `path ...` | Input life.txt file(s), or `-` for stdin |
| `-o`, `--output` | Output file; defaults to stdout |
| `--pretty` | Pretty-print JSON |
| `--occurrences` | Export computed agenda occurrence records instead of stored items |
| `filter options` | Same item filters as `filter` |

For file-backed input, each item object includes `_source_file` and
`_source_line`. Multi-line records also include `_source_end_line`. These
fields are metadata for tools and are ignored by `from-json`.

With `--occurrences`, `to-json` exports computed agenda records instead of
stored source items. This mode requires both `--after` and `--before`, expands
supported `repeat:` / `RRULE:` records inside that bounded range, and keeps the
same filters as `agenda`. Generated rows include `generated: true`,
`source_id`, `occurrence_start`, `occurrence_end`, `occurrence_index`, and
`repeat_rule` when available.

### 4.2 `to-jsonl`

Convert life.txt to JSONL.

```sh
python -m lifetxt to-jsonl [path ...] [-o output.jsonl] [--occurrences] [filter options]
```

JSONL rows use the same shape as `to-json`, including `_source_file` and line
metadata when the input came from a file. With `--occurrences`, each JSONL row
is one computed agenda occurrence record and requires `--after` plus
`--before`.

### 4.3 `from-json`

Convert a JSON item, JSON item array, or `{ "items": [...] }` object to
life.txt.

```sh
python -m lifetxt from-json [path ...] [-o life.txt]
```

Options:

| Option | Meaning |
|---|---|
| `path ...` | Input JSON file(s), or `-` for stdin |
| `-o`, `--output` | Output life.txt file; defaults to stdout |
| `--canonical` | Convert indented JSON records to explicit `parent:` links and write unindented life.txt |

### 4.4 `from-jsonl`

Convert JSONL to life.txt.

```sh
python -m lifetxt from-jsonl [path ...] [-o life.txt]
```

`from-jsonl` accepts the same `-o` and `--canonical` options as `from-json`.

### 4.5 `to-csv`

Convert life.txt to CSV. The CSV contains `status`, `type`, and `title`
columns plus one column for each detail key found in the selected items.
Repeated detail values are stored as a JSON array inside the cell. Multiline
`body:` values are stored as normal quoted CSV cells.

```sh
python -m lifetxt to-csv [path ...] [-o output.csv] [--occurrences] [filter options]
python -m lifetxt to-csv life.txt --type journal --project research -o journal.csv
```

With `--occurrences`, `to-csv` writes computed agenda occurrence rows with a
stable schema: `when`, `key`, `line`, `source_id`, `occurrence_start`,
`occurrence_end`, `occurrence_index`, `repeat_rule`, `status`, `type`, `title`,
`blocked`, `blocked_by`, `details`, and `text`. This mode also requires both
`--after` and `--before`.

### 4.6 `from-csv`

Convert CSV back to life.txt. CSV input requires `status`, `type`, and `title`
columns. All other non-empty columns become detail keys. Cells containing a JSON
array become repeated detail values.

```sh
python -m lifetxt from-csv [path ...] [-o life.txt]
```

`from-csv` also accepts `--canonical` for consistency with `from-json`.

### 4.7 `demo`

Generate a valid demo life.txt file. This is intended for Web UI demos,
screenshots, CLI examples, smoke tests, and empty local setups. `--count`
counts item records, not physical lines, so journal records with continuation
body lines may produce more output lines than the requested item count.

```sh
python -m lifetxt demo
python -m lifetxt demo --count 50 --date 2026-07-12 -o demo.life.txt
python -m lifetxt demo --count 20 --date 2026-07-12T09:30 --types T,E,S,M,J
python -m lifetxt demo --count 10 --date 2026-07-13 -o demo.life.txt --append
```

Options:

| Option | Meaning |
|---|---|
| `-n`, `--count N` | Number of item records to generate. Defaults to 30 |
| `--date VALUE` | Base date or datetime. Defaults to the current datetime |
| `--types VALUES` | Limit generated item types. Accepts comma-separated values and may be repeated |
| `--seed N` | Deterministic variation seed. Defaults to 1 |
| `--project NAME` | Default `project:` value. Defaults to `demo` |
| `--person NAME` | Person names used by status, message, assignee, attendee, and owner fields. Repeatable |
| `--start-index N` | First demo ID number. Defaults to 1, or the next existing demo ID when appending |
| `-o`, `--output FILE` | Write generated life.txt to a file instead of stdout |
| `--append` | Append to `--output`; requires `--output` |
| `--no-check` | Skip validation of generated records |

By default, generated items are checked before they are printed or written. When
appending to an existing demo file, the command scans existing `demo_*_NNN` IDs
and continues from the next number unless `--start-index` is given.

### 4.8 `markdown`

Render the safe life.txt Markdown subset from selected fields. This command
does not modify the file; it reads raw title/body/note text and emits rendered
HTML, plain text, JSON, or JSONL.

```sh
python -m lifetxt markdown [path ...] [--field body] [--format html|text|json|jsonl]
python -m lifetxt markdown life.txt --field all --format json --pretty
python -m lifetxt markdown examples/markdown_life.txt --type journal -o body.html
```

Options:

| Option | Meaning |
|---|---|
| `path ...` | Input life.txt file(s), directory, glob, or `-` for stdin |
| `--field title|body|note|all` | Field to render; repeatable or comma-separated. Defaults to `body` |
| `--format html|text|json|jsonl` | Output format. Defaults to `html` |
| `-o`, `--output` | Output file; defaults to stdout |
| `--pretty` | Pretty-print JSON output |
| `filter options` | Same item filters as `filter` |

JSON and JSONL records include `source`, `line`, `type`, `status`, `title`,
`field`, `index`, `raw`, `html`, and `text`. Raw HTML in Markdown source is
escaped. Unsafe links such as `javascript:` are not rendered as links.

### 4.9 Export Filter Options

`to-json`, `to-jsonl`, `to-csv`, and `markdown` can filter items before writing
output.

| Option | Meaning |
|---|---|
| `--open` | Keep unfinished workflow items only: `[ ]`, `[/]`, `[>]`, `[?]` |
| `--status VALUE` | Filter by status or alias; repeatable or comma-separated |
| `--type VALUE` | Filter by type or alias; repeatable or comma-separated |
| `--project VALUE` | Filter by `project:`; repeatable or comma-separated |
| `--tag VALUE` | Filter by `tag:`; repeatable or comma-separated |
| `--tag-all VALUE` | Require every listed `tag:` value |
| `--exclude-tag VALUE` | Exclude items containing any listed `tag:` value |
| `--user VALUE` | Filter across `user`, `person`, `owner`, `assignee`, `attendee`, `sender`, and `recipient` |
| `--team VALUE` | Filter by `team:` / `group:` or config-defined team membership |
| `--person VALUE` | Filter by `person:`; missing `person:` on `S` items means `self` |
| `--owner VALUE` | Filter by `owner:`; repeatable or comma-separated |
| `--assignee VALUE` | Filter by `assignee:`; repeatable or comma-separated |
| `--attendee VALUE` | Filter by `attendee:`; repeatable or comma-separated |
| `--sender VALUE` | Filter by `sender:`; repeatable or comma-separated |
| `--recipient VALUE` | Filter by `recipient:`; repeatable or comma-separated |
| `--detail FILTER` | Filter by detail key or `key=value`; repeatable and ANDed |
| `--text TEXT` | Case-insensitive substring search over title, line, and details |
| `--after VALUE` | Keep items related to this time or later |
| `--before VALUE` | Keep items related to this time or earlier |
| `--occurrences` | For `to-json`, `to-jsonl`, and `to-csv`: export bounded agenda occurrences instead of stored items |

`--after` and `--before` accept `now`, `YYYY-MM-DD`, or ISO-like datetimes such
as `YYYY-MM-DDTHH:MM`, `YYYY-MM-DDTHH:MM:SS`,
`YYYY-MM-DDTHH:MM:SS.5`, `YYYY-MM-DDTHH:MM+09:00`, or
`YYYY-MM-DDTHH:MM:SS.25+09:00`. They use the same time matching rules as
`agenda`. Time-only `at:HH:MM` values without an `on:` date are not matched by
one-sided `--after` or `--before` filters, because they have no date anchor.

`--user`, `--team`, and `--tag` use aliases from config `users`, `teams`, and
`tags.aliases` / `tags.groups` when available.

Examples:

```sh
python -m lifetxt to-json life.txt --open --type task --pretty
python -m lifetxt to-jsonl work.life.txt home.life.txt --project research
python -m lifetxt to-json life.txt --assignee alice --pretty
python -m lifetxt to-json life.txt --recipient alice --type message --pretty
python -m lifetxt to-json life.txt --after now --type event -o future_events.json
python -m lifetxt to-json "projects/**/*.life.txt" --team research --tag-all urgent,review
python -m lifetxt to-json life.txt --occurrences --after 2026-06-01 --before 2026-06-30 --pretty
python -m lifetxt to-csv life.txt --occurrences --after 2026-06-01 --before 2026-06-30 -o occurrences.csv
```

## 5. iCalendar Import And Sync

### 5.0 `import`: the unified entry point

`lifetxt import` is a routing-only dispatcher over `import-ics` below -- there
is no second ICS/Markdown/Todoist/GitHub conversion implementation, only a
smaller, more discoverable command name that infers `--preset` from the input
file extension when it can be determined safely:

```sh
python -m lifetxt import calendar.ics                       # infers --preset ics
python -m lifetxt import tasks.md                            # infers --preset markdown
python -m lifetxt import todoist_export.csv --preset todoist # explicit preset required
python -m lifetxt import github_issues.json --preset github  # explicit preset required
```

| Input | Preset |
|---|---|
| `*.ics` | `ics` (inferred) |
| `*.md`, `*.markdown` | `markdown` (inferred) |
| anything else, including `*.csv` and `*.json` | requires an explicit `--preset ics\|markdown\|todoist\|github` |
| reading from stdin (no path given) | always requires an explicit `--preset` |

`import` accepts every `import-ics` option below (`-o`/`--output`, `--append`,
`--project`, `--tag`, `--expand-rrule`, `--expand-until`, `--expand-count`,
`--preset`) -- the two subcommands share one argument definition -- and
delegates the actual conversion, validation, write-target resolution, and
write safety unchanged. Use `import-ics` directly for scripts that already
name a preset explicitly; `import` exists to make first migration easier to
discover, not to replace it.

### 5.1 `import-ics`

Convert iCalendar `.ics` files, such as Google Calendar exports, to life.txt
event items.

```sh
python -m lifetxt import-ics [path ...] [-o life.txt] [--append] [--project PROJECT] [--tag TAG] [--preset ics|markdown|todoist|github]
```

Options:

| Option | Meaning |
|---|---|
| `path ...` | Input `.ics` file(s), or `-` for stdin |
| `-o`, `--output` | Output file; defaults to stdout |
| `--append` | Append to `--output` instead of overwriting it |
| `--project PROJECT` | Add `project:PROJECT` to every imported event |
| `--tag TAG` | Add `tag:TAG` to every imported event; repeatable |
| `--expand-rrule` | Write one record per occurrence instead of a single record carrying `repeat:RRULE:` |
| `--expand-until DATE` | Expand occurrences up to this date; defaults to one year out |
| `--expand-count N` | Maximum occurrences per recurring event; capped at 500 |
| `--preset PRESET` | Input preset. `ics` is the default. `markdown`, `todoist`, and `github` import Markdown task lists, Todoist CSV exports, and GitHub Issues JSON exports as task items |

Mapping:

| iCalendar field | life.txt output |
|---|---|
| `VEVENT` | `E` item |
| `SUMMARY` | title |
| `UID` | `id:`, `source:ics`, and `uid:` |
| `DTSTART` / `DTEND` | `from:` / `to:` for timed events |
| `DTSTART;VALUE=DATE` | `on:` for all-day events |
| `LOCATION` | `loc:` |
| `DESCRIPTION` | `note:` |
| `URL` | `url:` |
| `ORGANIZER` | `owner:` |
| `ATTENDEE` | repeated `attendee:` |
| `CATEGORIES` | repeated `tag:` |
| `RRULE` | `repeat:RRULE:...` |
| `STATUS:CANCELLED` | `[-]` with `reason:canceled` |
| `STATUS:TENTATIVE` | `[?]` |

Notes:

- Only `VEVENT` components are imported.
- ICS-derived events include `source:ics` and `uid:UID` so later syncs can
  distinguish external calendar records from hand-written records.
- Google Calendar all-day `DTEND` values are exclusive. Multi-day all-day
  events become repeated `on:` values.
- `TZID` local wall times are kept as written. UTC `Z` datetimes are converted
  to the machine's local timezone before writing `YYYY-MM-DDTHH:MM`.
- `RRULE` values are preserved as `repeat:RRULE:...`; supported RRULE subsets
  are expanded later by `agenda` and time filters, not during import.

#### Expanding recurring events at import time

By default a recurring event stays one record with `repeat:RRULE:...`. That is
compact and keeps the rule authoritative, and `agenda`, `rrule`, and the
calendar view all evaluate it on demand.

`--expand-rrule` writes one record per occurrence instead:

```sh
python -m lifetxt import-ics google_calendar.ics --expand-rrule --expand-until 2026-12-31
```

```txt
[ ] E "Team standup" id:standup@example.com_20260706 source:ics uid:standup@example.com from:2026-07-06T09:00 repeat_base:2026-07-06
[ ] E "Team standup" id:standup@example.com_20260708 source:ics uid:standup@example.com from:2026-07-08T09:00 repeat_base:2026-07-06
```

Use it when occurrences need to be handled individually — completing,
annotating, or rescheduling one date without touching the series — or when
something downstream reads the file but cannot evaluate an RRULE.

Each occurrence gets:

- a unique `id:` of `UID_YYYYMMDD`, since occurrences share one UID
- the original `uid:`, so instances stay traceable to the calendar event
- `repeat_base:` naming the series anchor
- no `repeat:`, because the instance is a concrete date, not a series

Bounds, so one open-ended rule cannot fill the file:

| Situation | Result |
|---|---|
| Rule has `COUNT` or `UNTIL` | Honored as written |
| Neither, and no `--expand-until` | One year from the series start |
| Any case | Hard ceiling of 500 occurrences per event |

`EXDATE` is honored, so an occurrence the feed has cancelled is not written
back out as a real event. `RDATE` (a one-off occurrence added outside the
rule) is not yet expanded.

An event whose rule cannot be expanded — an unsupported `FREQ`, a missing
start — is written in the compact form rather than dropped. Losing a calendar
entry would be worse than leaving it unexpanded.

Re-running `sync-ics --expand-rrule --merge-existing` is idempotent: the dated
ids match, so occurrences are updated rather than duplicated.

Examples:

```sh
python -m lifetxt import-ics google_calendar.ics
python -m lifetxt import-ics google_calendar.ics -o imported_events.life.txt
python -m lifetxt import-ics google_calendar.ics -o life.txt --append --tag google
python -m lifetxt import-ics work.ics personal.ics --project calendar
python -m lifetxt import-ics tasks.md --preset markdown --project inbox
python -m lifetxt import-ics todoist.csv --preset todoist --tag todoist
python -m lifetxt import-ics github_issues.json --preset github --project repo
```

Example output:

```txt
[ ] E "Research Meeting" id:event-1@example.com source:ics uid:event-1@example.com from:2026-06-08T13:00 to:2026-06-08T14:30 loc:"Meeting Room A" owner:"Prof. Smith" attendee:Alice tag:google
```

Preset mapping:

| Preset | Input | Output |
|---|---|---|
| `markdown` | Markdown task list lines such as `- [ ] title` | `T` items with `source:markdown` |
| `todoist` | Todoist CSV columns such as `Content`, `Project`, `Date`, `Labels`, `Priority`, `Completed` | `T` items with `source:todoist`; source IDs become `uid:` and `id:todoist-...` |
| `github` | GitHub Issues JSON array or an object containing `items`, `issues`, or `data` | `T` items with `source:github`; issue numbers become `id:github-N` and `ref:github-N`; pull requests are skipped |

### 5.2 `sync-ics`

Fetch one or more iCalendar URLs and regenerate a generated life.txt file.
This is the recommended mode for periodic sync because the output file is
overwritten, so events are not duplicated on each run.

```sh
python -m lifetxt sync-ics --url-env LIFETXT_GOOGLE_CAL_ICS -o .generated/google_calendar.life.txt --cache-dir .cache/lifetxt --tag google
```

Options:

| Option | Meaning |
|---|---|
| `--url URL` | iCalendar URL to fetch; repeatable |
| `--url-env ENVVAR` | Environment variable containing an iCalendar URL; repeatable |
| `-o`, `--output` | Generated life.txt output; defaults to stdout |
| `--cache-dir DIR` | Save raw downloaded `.ics` snapshots in this directory |
| `--dry-run` | Fetch and print generated life.txt without writing output or cache files |
| `--merge-existing` | Merge generated events into an existing output by `id:` instead of replacing the whole file |
| `--soft-delete-missing` | With `--merge-existing`, mark existing `source:ics` events missing from the feed as `[-]` with `reason:missing_from_feed` |
| `--project PROJECT` | Add `project:PROJECT` to every synced event |
| `--tag TAG` | Add `tag:TAG` to every synced event; repeatable |
| `--expand-rrule`, `--expand-until DATE`, `--expand-count N` | Write one record per occurrence; see [5.1](#51-import-ics). Idempotent with `--merge-existing` |
| `--timeout SECONDS` | Fetch timeout; defaults to 30 |
| `--user-agent VALUE` | HTTP User-Agent header |

Use `--url-env` for secret iCalendar URLs so the URL is not stored in shell
history, scripts, or documentation.

PowerShell example:

```powershell
$env:LIFETXT_GOOGLE_CAL_ICS = "https://calendar.google.com/calendar/ical/..."
New-Item -ItemType Directory -Force .generated, .cache/lifetxt
python -m lifetxt sync-ics --url-env LIFETXT_GOOGLE_CAL_ICS -o .generated/google_calendar.life.txt --cache-dir .cache/lifetxt --tag google
python -m lifetxt sync-ics --url-env LIFETXT_GOOGLE_CAL_ICS -o .generated/google_calendar.life.txt --merge-existing --soft-delete-missing
python -m lifetxt check life.txt .generated/google_calendar.life.txt
python -m lifetxt agenda life.txt .generated/google_calendar.life.txt --around now --window 1d
```

For periodic sync, put the same commands in a `.ps1` file and run it with
Windows Task Scheduler. Keep manually edited items in your main `life.txt` and
ICS-derived items in `.generated/*.life.txt`; pass both files to commands such
as `agenda`, `filter`, `to-json`, and `check`.
When using `--merge-existing`, comments and unmatched hand-written lines in the
generated output are preserved. Matching records are replaced by UID-backed
generated events, and missing `source:ics` events can be soft-deleted.

## 6. `filter`

Filter parsed life.txt items and output the result as life.txt, JSON, or JSONL.
This is useful when you want to materialize a subset as another `life.txt`
file.

```sh
python -m lifetxt filter [path ...] [filter options] [--format life|json|jsonl] [-o output]
```

Options:

| Option | Meaning |
|---|---|
| `path ...` | Input life.txt file(s), or `-` for stdin |
| `--format life` | Output matching life.txt lines; this is the default |
| `--format json` | Output a JSON array |
| `--format jsonl` | Output JSONL |
| `--format table` | Output a bordered STATUS/TYPE/TITLE/PROJECT table (or a compact one-line-per-item form below `--width` 80) |
| `--width N` | Table column width in characters for `--format table`. `0` (default) detects the terminal width |
| `--limit N` | Return at most N items (`0` = no limit) |
| `-o`, `--output` | Output file; defaults to stdout |
| `--pretty` | Pretty-print JSON output |
| `--canonical` | Regenerate normalized, unindented life.txt lines with explicit `parent:` links where inferable |

Filter options are the same as the export filter options in section 4.8.
With `--format life`, original matching item lines are preserved by default.
Use `--canonical` when you want normalized quoting, spacing, and hierarchy
represented as explicit `parent:` links rather than indentation. Use
`--format table` for a quick human-readable scan in a terminal — like
`agenda`'s and `stats`'s tables, it switches to a compact single-line form
automatically in narrow terminals (or below `--width 80`).

Examples:

```sh
python -m lifetxt filter life.txt --open --type task -o open_tasks.life.txt
python -m lifetxt filter life.txt --open --type task --canonical -o canonical_tasks.life.txt
python -m lifetxt filter life.txt --assignee alice -o alice_items.life.txt
python -m lifetxt filter life.txt --recipient alice --type message -o alice_messages.life.txt
python -m lifetxt filter life.txt --after now --type event -o future_schedule.life.txt
python -m lifetxt filter life.txt --type status --person self -o my_status.life.txt
python -m lifetxt filter work.life.txt home.life.txt --project research --format json --pretty
python -m lifetxt filter "projects/**/*.life.txt" --team research --tag-all urgent,review --exclude-tag archived
```

## 7. `status`

Show the latest `S` status / presence record for each person.

```sh
python -m lifetxt status [path ...] [--format text|json|jsonl] [--person PERSON] [--active] [--pretty]
```

Selection rules:

- Only type `S` items are considered.
- Records are grouped by `person:`.
- Missing `person:` is treated as `self`.
- The latest record is the item with the newest `from:` datetime.
- With `--active`, finished logs with `to:` are ignored.

Options:

| Option | Meaning |
|---|---|
| `path ...` | Input life.txt file(s), or `-` for stdin |
| `--format text` | Print a table |
| `--format json` | Print a JSON array |
| `--format jsonl` | Print JSONL |
| `--person PERSON` | Show only one person |
| `--active` | Only consider active status items without `to:` |
| `--pretty` | Pretty-print JSON output |

Examples:

```sh
python -m lifetxt status life.txt
python -m lifetxt status life.txt --active
python -m lifetxt status life.txt --person self
python -m lifetxt status life.txt --format json --pretty
```

## 8. `notify`

Show due type `M` message notifications once, or keep a resident watcher
running with `--watch`.

```sh
python -m lifetxt notify [path ...] [--recipient PERSON] [--watch]
python -m lifetxt notify life.txt --recipient self --email --email-to me@example.com --dry-run
python -m lifetxt notify life.txt --watch --once --state-file .generated/notifications.json
python -m lifetxt notify life.txt --watch --email --email-to me@example.com --interval 60
```

Selection rules:

- Only type `M` items are considered.
- Only open workflow statuses are considered: `[ ]`, `[/]`, `[>]`, and `[?]`.
- `recipient:` must match the selected recipient.
- `notify_at:` is a one-time notification.
- `notify_from:` / `notify_to:` is an active notification period.
- Items with `ack:` are treated as acknowledged and are not notified.
- Items with future `snooze_until:` are temporarily suppressed.

Options:

| Option | Meaning |
|---|---|
| `path ...` | Input life.txt file(s), or `-` for stdin |
| `--recipient PERSON` | Recipient; defaults to `notifications.recipient` or `user.name` from config |
| `--lookahead VALUE` | Future notification window, such as `0m`, `5m`, or `1h` |
| `--grace VALUE` | Past grace window for missed notifications |
| `--watch` | Stay running and poll repeatedly |
| `--once` | With `--watch`, poll once, update seen-state, and exit; useful for smoke tests or schedulers |
| `--interval SECONDS` | Poll interval for `--watch` |
| `--desktop` | Also show a simple desktop notification when supported |
| `--email` | Also send due notifications as one plain-text email batch |
| `--email-to ADDRESS[,ADDRESS...]` | Email recipient list; defaults to `notifications.email.to` |
| `--email-subject TEXT` | Base email subject; defaults to `notifications.email.subject` |
| `--smtp-host-env ENVVAR` | Env var with SMTP host; default is `notifications.email.smtp_host_env` or `LIFETXT_SMTP_HOST` |
| `--smtp-user-env ENVVAR` | Env var with SMTP username; default is `notifications.email.smtp_user_env` or `LIFETXT_SMTP_USER` |
| `--smtp-pass-env ENVVAR` | Env var with SMTP password; default is `notifications.email.smtp_pass_env` or `LIFETXT_SMTP_PASS` |
| `--smtp-port PORT` | Explicit SMTP port (e.g. `587` for STARTTLS); default is `notifications.email.smtp_port`, or the existing default port when neither is set |
| `--dry-run` | With `--email`, print the email body without connecting to SMTP |
| `--state-file PATH` | Persist seen notification IDs for `--watch` |
| `--no-state` | Disable persistent seen-state for `--watch` |
| `--format text|json|jsonl` | Output format in one-shot mode |

Examples:

```sh
python -m lifetxt notify life.txt --recipient self
python -m lifetxt notify life.txt --recipient self --format json --pretty
python -m lifetxt notify life.txt --watch --interval 30
python -m lifetxt notify life.txt --watch --once --state-file .generated/notifications.json
python -m lifetxt notify life.txt --email --email-to me@example.com --dry-run
```

Email notification delivery uses SMTP credentials from environment variables,
not from life.txt content. Configure the env var names under
`notifications.email.*` when the defaults are not suitable.

## 9. `agenda`

Show items related to a datetime range.

```sh
python -m lifetxt agenda [path ...] [range options] [filter options] [output options]
```

Range matching rules:

- `from/to` is treated as an interval.
- `notify_from/notify_to` is treated as a message notification interval.
- `on` is treated as an all-day interval.
- `due`, `do`, `at`, `moved_to`, and `notify_at` are treated as point times or all-day spans.
- Type `S` records without `to:` are treated as ongoing from `from:`.
- `at:HH:MM` is combined with `on:` when present, otherwise with each date in the requested range.
- Simple `repeat:` values are expanded for `daily`, `weekly`, `monthly`, `yearly`, and `weekdays`.
- `interval:`, `until:`, and `count:` constrain simple recurrence expansion.
- `repeat:RRULE:...` expands a dependency-free subset:
  `FREQ=DAILY|WEEKLY|MONTHLY|YEARLY`, `INTERVAL`, `COUNT`, `UNTIL`, and
  daily/weekly `BYDAY`.
- Floating repeated `at:` values without `on:` are expanded only inside bounded agenda ranges.

### 9.1 Range Options

| Option | Meaning |
|---|---|
| `--from VALUE` | Range start: `now`, date, or ISO-like datetime |
| `--to VALUE` | Range end: `now`, date, or ISO-like datetime |
| `--after VALUE` | Alias for `--from` in `agenda`; useful when sharing filter presets |
| `--before VALUE` | Alias for `--to` in `agenda`; useful when sharing filter presets |
| `--around VALUE` | Range center; defaults to `now` |
| `--window VALUE` | Half-width for `--around`; defaults to `1h` |

Use either `--from/--to`, `--after/--before`, or `--around`. Do not mix
`--from` with `--after` or `--to` with `--before` in the same command. If no
range is specified, the command uses `--around now --window 1h`.

Duration values for `--window`:

| Form | Meaning |
|---|---|
| `15s` | 15 seconds |
| `30m` | 30 minutes |
| `2h` | 2 hours |
| `1d` | 1 day |
| `1w` | 1 week |
| `1mo` | 1 month, approximated as 30 days |
| `1y` | 1 year, approximated as 365 days |
| `30` | 30 minutes |

Examples:

```sh
python -m lifetxt agenda life.txt --from 2026-06-06 --to 2026-06-06
python -m lifetxt agenda life.txt --after 2026-06-06 --before 2026-06-06
python -m lifetxt agenda life.txt --from 2026-06-06T13:00 --to 2026-06-06T18:00
python -m lifetxt agenda life.txt --from 2026-06-06T13:00:30.25+09:00 --to 2026-06-06T18:00:00.5+09:00
python -m lifetxt agenda life.txt --around now --window 2h
python -m lifetxt agenda life.txt --around now --window 1w
python -m lifetxt agenda life.txt --from 2026-06-01 --to 2026-06-30 --type habit
```

### 9.2 Filter Options

| Option | Meaning |
|---|---|
| `--open` | Show unfinished workflow items only: `[ ]`, `[/]`, `[>]`, `[?]` |
| `--status VALUE` | Filter by status or alias; repeatable or comma-separated |
| `--type VALUE` | Filter by type or alias; repeatable or comma-separated |
| `--project VALUE` | Filter by `project:`; repeatable or comma-separated |
| `--tag VALUE` | Filter by `tag:`; repeatable or comma-separated |
| `--tag-all VALUE` | Require every listed `tag:` value |
| `--exclude-tag VALUE` | Exclude items containing any listed `tag:` value |
| `--user VALUE` | Filter across user-related details |
| `--team VALUE` | Filter by `team:` / `group:` or config-defined team membership |
| `--person VALUE` | Filter by `person:`; repeatable or comma-separated |
| `--owner VALUE` | Filter by `owner:`; repeatable or comma-separated |
| `--assignee VALUE` | Filter by `assignee:`; repeatable or comma-separated |
| `--attendee VALUE` | Filter by `attendee:`; repeatable or comma-separated |
| `--sender VALUE` | Filter by `sender:`; repeatable or comma-separated |
| `--recipient VALUE` | Filter by `recipient:`; repeatable or comma-separated |
| `--detail FILTER` | Filter by detail key or `key=value`; repeatable and ANDed |
| `--text TEXT` | Case-insensitive substring search over title, line, and details |
| `--blocked [only|hide|all]` | Filter dependency-blocked records. Plain `--blocked` is the same as `--blocked only` |
| `--unblocked` | Backward-compatible alias for `--blocked hide` |

Examples:

```sh
python -m lifetxt agenda life.txt --from 2026-06-06 --to 2026-06-06 --open
python -m lifetxt agenda life.txt --from 2026-06-06 --to 2026-06-06 --status todo --type task
python -m lifetxt agenda life.txt --from 2026-06-06 --to 2026-06-06 --project research --tag urgent
python -m lifetxt agenda life.txt --from 2026-06-06 --to 2026-06-06 --team research --tag-all urgent,review
python -m lifetxt agenda life.txt --from 2026-06-06 --to 2026-06-06 --assignee alice
python -m lifetxt agenda life.txt --from 2026-06-06 --to 2026-06-06 --recipient alice
python -m lifetxt agenda life.txt --from 2026-06-06 --to 2026-06-06 --detail priority=A --text report
python -m lifetxt agenda life.txt --from 2026-06-06 --to 2026-06-06 --person alice
python -m lifetxt agenda life.txt --from 2026-06-06 --to 2026-06-06 --blocked
python -m lifetxt agenda life.txt --from 2026-06-06 --to 2026-06-06 --blocked hide
```

`--detail key` checks that the key exists. `--detail key=value` checks for an
exact detail value. Multiple `--detail` filters are ANDed.

### 9.3 Output Options

| Option | Meaning |
|---|---|
| `--format text` | Print a table |
| `--format life` | Print matching original life.txt item lines |
| `--format json` | Print a JSON array |
| `--format jsonl` | Print JSONL |
| `-o`, `--output` | Output file; defaults to stdout |
| `--pretty` | Pretty-print JSON output |
| `--width N` | Render text output for a specific terminal width |

Agenda JSON / JSONL records include `blocked: true` and a `blocked_by` array
when an open item is blocked by an open `depends_on:` or `blocks:` relation.
Repeated occurrences also include `source_id`, `occurrence_start`,
`occurrence_end`, `occurrence_index`, and `repeat_rule` when available. Text
output shows dependency state with a compact `blocked` column. `--format life`
still prints the original stored item lines.

Examples:

```sh
python -m lifetxt agenda life.txt --from 2026-06-06 --to 2026-06-06 --format life
python -m lifetxt agenda life.txt --from 2026-06-06 --to 2026-06-06 --format json --pretty
python -m lifetxt agenda life.txt --around now --window 1w --format life -o agenda.life.txt
python -m lifetxt agenda life.txt --around now --window 1d --width 70
```

## 10. `assist`

Create or update life.txt items from flags or prompts.

```sh
python -m lifetxt assist [options]
```

### 10.1 Create Non-Interactively

```sh
python -m lifetxt assist --type task --title "Write Report" --due 2026-06-12 --project university
python -m lifetxt assist --type status --title "Working" --from 2026-06-06T14:00 --state busy --person self
python -m lifetxt assist --type message --title "Review Slides" --sender self --recipient alice --notify-at 2026-06-06T09:00
python -m lifetxt assist --type diary --title "Research day" --on 2026-06-23 --mood good --body "Read papers."
python -m lifetxt assist --type journal --title "Research day" --on 2026-06-23 --body-file notes.md
python -m lifetxt assist --type habit --title "Review" --rrule "FREQ=WEEKLY;BYDAY=MO;COUNT=4"
```

Core options:

| Option | Meaning |
|---|---|
| `-s`, `--status` | Status or alias, such as `[ ]`, `done`, or `note` |
| `-t`, `--type` | Type or alias, such as `T`, `task`, `status`, or `diary` |
| `--title` | Item title |
| `-d`, `--detail` | Detail as `key=value` or `key:value`; repeatable |
| `-o`, `--output` | Append generated line to a file |
| `--append` | Append generated line to a file |
| `--no-check` | Skip validation of the generated line |
| `--body-file FILE` | Read a multiline `body:` value from a UTF-8 file |
| `--body-stdin` | Read a multiline `body:` value from standard input |
| `--rrule VALUE` | Set `repeat:RRULE:...`; the `RRULE:` prefix is optional |

Known detail keys also have direct flags. Each can be repeated:

```txt
--id --parent --ref --depends_on --blocks --related --created --updated --done --due --do --from --to
--state --user --person --owner --assignee --attendee --sender --recipient --team --group --service --channel
--visibility --notify_at --notify_from --notify_to --ack --snooze_until --on --at --repeat --interval --until --count
--project --context --loc --priority --progress --est --elapsed --tag --note --body --mood --weather --url
--reason --moved_to
```

For detail keys that contain underscores, hyphenated aliases are also accepted:
for example `--notify-at`, `--notify-from`, and `--snooze-until`.

### 10.2 Interactive Create

```sh
python -m lifetxt assist --interactive
python -m lifetxt assist --interactive --append life.txt
```

Interactive help:

| Input | Meaning |
|---|---|
| `?` | Contextual help for the current prompt |
| `?type` | Type help |
| `?status` | Status help |
| `?detail` | Suggested detail keys |
| `?all` | All known detail keys |
| `?due` | Help for a detail key |
| `body<<` | Enter a multiline `body:` value; finish with a single `.` line |

When the terminal supports it, Tab completes type, status, and detail-key
candidates. Up/Down recall previous inputs. Use `--no-completion` to disable
line editing helpers.

### 10.3 Update Existing Items

Update an item by line number or by `id:` value.

```sh
python -m lifetxt assist --update life.txt --line 3 --title "New Title"
python -m lifetxt assist --update life.txt --match-id task_001 --status done --done 2026-06-06
python -m lifetxt assist --update life.txt --match-id task_001 --add-detail tag=important
python -m lifetxt assist --update life.txt --match-id task_001 --remove-detail tag
python -m lifetxt assist --update life.txt --match-id task_001 --output updated_life.txt
```

Update options:

| Option | Meaning |
|---|---|
| `--update FILE` | Read and update an existing life.txt file |
| `--line N` | Select the item on line `N` |
| `--match-id ID` | Select the item whose `id:` is exactly `ID`, or, when nothing matches exactly, whose `id:` is uniquely prefixed by `ID` |
| `--add-detail key=value` | Append a detail value |
| `--remove-detail key` | Remove all values for a detail key |
| `--output FILE` | Write the updated whole file to another file |

Without `--output`, update mode writes back to the input file.

#### Short ID prefix selection

`--match-id` (and the plain `ID` positional argument accepted by `start`,
`done`, and `complete`) does not require the full `id:` value. A shorter
prefix works as long as it is unique across the effective item set:

```sh
python -m lifetxt done life.txt task_01J   # matches id:task_01JZY5M93PK17C7BA4M8
```

Resolution order is always exact match first, then unique prefix:

1. An `id:` value equal to what you typed always wins outright, even when
   a shorter `id:` elsewhere would also prefix-match it.
2. Otherwise, exactly one item's `id:` must start with what you typed.

A prefix matching more than one item is refused rather than guessed:

```text
ERROR: Ambiguous ID prefix `task_a`.

Matches:
  task_a12345
  task_a16789

Use a longer prefix.
```

This is one shared resolver (`lifetxt.ids.resolve_item_by_id`) reused by
every ID-selecting command, so `--match-id`/`ID` behaves identically
everywhere; stored `id:` values and every machine-readable output are
unaffected -- only the *selector* you type accepts a prefix.

## 11. `serve`

Run the optional FastAPI REST API and browser GUI.

Install web dependencies first:

```sh
pip install -r requirements-web.txt
```

Start the server:

```sh
python -m lifetxt serve life.txt --host 127.0.0.1 --port 8000
LIFETXT_API_TOKEN=change-me python -m lifetxt serve life.txt --host 0.0.0.0 --token-env LIFETXT_API_TOKEN
```

Open `http://127.0.0.1:8000/` in a browser.

### 11.0 `web`: the one-command browser entry point

`lifetxt web` starts the exact same server `serve` does and then opens your
default browser to it -- there is no second Web implementation, only a thinner
launcher over the same runtime:

```sh
python -m lifetxt web life.txt
python -m lifetxt web life.txt --no-open   # start the server without opening a browser
```

`web` accepts the same `path ...`, `--write-file`, `--host`, `--port`,
`--read-only`, `--token-env`, and `--insecure-public` options `serve` does
(the two subcommands share one argument definition), binds loopback by
default, and shares every safety behavior described below. It waits for the
server's own `/api/health` route to answer before opening the browser, so the
tab never loads before the app is ready. Use `serve` directly for
server/deployment-oriented invocations, including `--mcp`, which `web` does
not expose.

Options:

| Option | Meaning |
|---|---|
| `path ...` | life.txt file(s) to read; defaults to `life.txt` |
| `--write-file FILE` | File used for create, update, and delete operations |
| `--host HOST` | Bind host; defaults to `127.0.0.1` |
| `--port PORT` | Bind port; defaults to `8000` |
| `--read-only` | Disable write endpoints except `/api/check-line`; useful for public or wall-display deployments |
| `--token-env ENVVAR` | Read the API bearer token from an environment variable and require `Authorization: Bearer TOKEN` on API routes |
| `--insecure-public` | Explicitly allow a non-loopback writable server without a bearer token; intended only for trusted local networks |
| `--mcp` | Run the stdio MCP server instead of the FastAPI HTTP server |

When `--host` binds a non-loopback address such as `0.0.0.0`, writable mode
now requires either `--token-env ENVVAR`, `--read-only`, or the explicit
`--insecure-public` opt-in. Keep secrets in environment variables rather than
committing them to `.lifetxt.json`.

The REST API includes `/api/items`, `/api/messages`, `/api/agenda`, `/api/status`, and
`/api/health`. See [web.md](./web.md) for the full API and GUI guide.

The browser GUI includes a header Workspace, centered record modals,
URL/config-driven view presets, Review filters with Markdown copy, configurable
Dashboard cards and theme tokens, `Ctrl+K` fuzzy command palette, recently
opened records, undo history, browser notifications, graph review, display
mode, and kiosk mode. When reading multiple files, combine `path ...` with
`--write-file FILE` so generated or read-only files can be shown while edits go
only to the hand-maintained file.

### 11.1 `mcp`

Run a JSON-RPC stdio MCP server for MCP-compatible AI clients. It has no extra
dependency beyond the core package.

```sh
python -m lifetxt mcp life.txt
python -m lifetxt mcp life.txt .generated/google_calendar.life.txt --write-file life.txt
python -m lifetxt serve life.txt --mcp
python -m lifetxt mcp "projects/**/*.life.txt" --write-file life.txt --read-only
python -m lifetxt mcp life.txt --profile assist
```

`--profile {read,assist,full}` controls which tools the connected client can
see and call, enforced both when tools are listed and when one is called:

| Profile | Allows |
|---|---|
| `read` | Every read-only tool. Equivalent to `--read-only`. |
| `assist` | Every read-only tool, plus `stage_proposal` (stages a Unified Inbox proposal; never writes life.txt directly). |
| `full` | Everything (today's default when `--profile`/`--read-only` are both omitted). |

A tool with no explicit read/write classification is unreachable under `read`
and `assist`, not reachable by default. `--read-only` is equivalent to
`--profile read`; combining `--read-only` with a different `--profile` is
rejected. See `docs/en/ai-integration.md` section 6 for the full model.

`--no-open-world` denies every tool that makes an outbound network call
(`remote_test_connection`, `remote_list_resources`, `remote_get_resource`)
regardless of `--profile`. It is independent of and combinable with any
profile -- use it when a connected client must be sandboxed to the local
workspace with no network reach at all:

```sh
python -m lifetxt mcp life.txt --profile read --no-open-world
```

`--profile` and `resources/list`/`resources/read` gate which *tools*/resources
are reachable, not what data a reachable one returns: every read-only tool and
resource returns the full raw content of every loaded source regardless of
profile. Use a named workspace to limit what data is visible to a client, not
`--profile`; see `docs/en/ai-integration.md` sections 6-7.

The MCP server exposes these tools:

| Tool | Purpose |
|---|---|
| `list_items` | List items with filters matching `/api/items` |
| `get_item` | Read one item by ID |
| `check_line` / `parse_item` | Validate or preview raw life.txt text |
| `create_item` / `update_item` / `mark_done` / `delete_item` | Write item changes to the configured writable file |
| `complete_item` | Complete a repeat-enabled task instance and materialize the next occurrence; behaves like `mark_done` otherwise |
| `get_agenda` | Return agenda records for a range |
| `get_review` | Return the weekly/monthly review report (same shape as `review --format json` and `GET /api/review`) |
| `get_graph` / `get_blockers` / `list_links` | Inspect ID references and dependency blockers |
| `list_status` | Return latest `S` presence records |
| `list_notifications` | Return due message notifications |
| `list_messages` / `create_message` / `reply_message` / `ack_message` / `snooze_message` | Work with type `M` messages |

It also exposes `lifetxt://source/N` resources so clients can read the loaded
source files without writing -- these are unaffected by `--profile`; see
above. Use `--profile read` (or the equivalent `--read-only`) to disable all
MCP write tools, or `--profile assist` to allow only proposal staging. When
multiple files are loaded, read tools scan all files and write tools modify
only `--write-file`.

### 11.2 `ai setup generic`

Print the exact `lifetxt mcp` command and a generic MCP client
configuration for the current workspace. Writes nothing.

```sh
python -m lifetxt ai setup generic life.txt
python -m lifetxt ai setup generic life.txt --profile assist
python -m lifetxt ai setup generic life.txt --format json
```

`--profile` defaults to `read`; `--write-file` overrides the printed write
target. `--format json` returns `{"command": [...], "mcp_client_config":
{...}}` instead of formatted text.

### 11.3 `ai setup claude` / `ai setup gemini`

Provider-specific variants of `ai setup generic`, printing the same
`mcpServers` configuration plus each provider's own config file location and
CLI-driven setup command. Both write nothing; they only print/copy. Neither
changes MCP domain authorization -- they differ only in command/config syntax.

```sh
python -m lifetxt ai setup claude life.txt
python -m lifetxt ai setup gemini life.txt --profile assist
```

`ai setup claude` prints the `claude_desktop_config.json` path for each OS
(macOS, Windows, Linux), the `.mcp.json` project-scope path, and the
equivalent `claude mcp add --transport stdio ...` command.

`ai setup gemini` prints the Gemini CLI `settings.json` path for both user and
project scope, and the equivalent `gemini mcp add ...` command.

Both accept the same `--write-file`, `--profile` (default `read`), and
`--format text|json` flags as `ai setup generic`.

### 11.4 `ai doctor`

Check whether the workspace will load and resolve a write target cleanly
for a direct MCP connection. Writes nothing.

```sh
python -m lifetxt ai doctor life.txt
python -m lifetxt ai doctor life.txt --write-file life.txt --format json
```

Reports one check per input file (found/parsed), a `write-target` check
(resolved, or the same `--write-file`-required error `lifetxt mcp` would
raise), and a `profile` recommendation naming `read` as the default for
external/untrusted clients. `--format json` returns the checks as a JSON
array.

## 12. `config`

Create or inspect an external JSON config file.

```sh
python -m lifetxt config init -o .lifetxt.json
python -m lifetxt --config .lifetxt.json config show
```

Example config:

```json
{
  "paths": ["life.txt", ".generated/google_calendar.life.txt"],
  "write_file": "life.txt",
  "done": { "precision": "date" },
  "attachments": { "ignore": [".git", "node_modules"], "max_files": 2000 },
  "user": {
    "name": "self",
    "display_name": "Self",
    "aliases": ["me"],
    "teams": []
  },
  "users": {
    "alice": {
      "display_name": "Alice",
      "aliases": ["ali"],
      "teams": ["research"]
    }
  },
  "teams": {
    "research": {
      "display_name": "Research Team",
      "members": ["self", "alice"],
      "aliases": ["lab"]
    }
  },
  "tags": {
    "aliases": {
      "review": ["code-review"]
    },
    "groups": {
      "work": ["research", "writing"]
    }
  },
  "defaults": {
    "person": "self",
    "timezone": "Asia/Tokyo"
  },
  "message": {
    "default_sender": "",
    "default_channel": "lifetxt"
  },
  "timer": {
    "state_file": "~/.lifetxt_timer.json"
  },
  "tui": {
    "theme": "auto",
    "keymap": "prompt",
    "glyphs": "auto",
    "limit": 10,
    "agenda_window": "12h",
    "session": true,
    "session_file": ".cache/lifetxt/tui_session.json"
  },
  "notifications": {
    "enabled": true,
    "recipient": "",
    "lookahead": "0m",
    "grace": "2m",
    "poll_seconds": 30,
    "state_file": ".cache/lifetxt/notifications.json",
    "snooze_default": "10m",
    "desktop": false,
    "web": true,
    "email": {
      "enabled": false,
      "to": "",
      "subject": "lifetxt notifications",
      "smtp_host_env": "LIFETXT_SMTP_HOST",
      "smtp_user_env": "LIFETXT_SMTP_USER",
      "smtp_pass_env": "LIFETXT_SMTP_PASS"
    }
  },
  "api": {
    "id_key": "id",
    "allow_id_writes": true
  },
  "ids": {
    "auto": true,
    "key": "id",
    "prefixes": {
      "T": "task",
      "E": "event",
      "D": "deadline",
      "R": "reminder",
      "H": "habit",
      "N": "note",
      "S": "status",
      "M": "msg",
      "J": "journal"
    }
  },
  "web": {
    "host": "127.0.0.1",
    "port": 8000,
    "display_refresh": 60,
    "notification_poll_seconds": 30,
    "notification_lookahead": "0m",
    "default_limit": "",
    "default_sort": "line",
    "default_order": "asc",
    "due_soon_days": 3,
    "theme": {
      "accent": "#0e7a65",
      "accent_hover": "#0a6252",
      "accent_soft": "#e0f0ea",
      "accent_ink": "#ffffff"
    },
    "dashboard": {
      "cards": ["today", "needs_attention", "completions", "projects"],
      "limits": {
        "today": 7,
        "needs_attention": 7,
        "projects": 7
      }
    }
  },
  "views": {
    "today": {
      "around": "now",
      "window": "1d",
      "sort": "time",
      "order": "asc"
    },
    "my_messages": {
      "view": "messages",
      "recipient": "self",
      "open_only": "true",
      "sort": "time",
      "order": "asc"
    },
    "team_status": {
      "view": "status",
      "type": "S",
      "active": "true",
      "refresh": "30"
    }
  },
  "sync_ics": {
    "output": ".generated/google_calendar.life.txt",
    "cache_dir": ".cache/lifetxt",
    "generated_paths": [".generated/google_calendar.life.txt"],
    "sources": [
      {
        "name": "google",
        "url_env": "LIFETXT_GOOGLE_CAL_ICS",
        "tags": ["google"]
      }
    ]
  }
}
```

When `ids.auto` is `true`, newly created items from `assist`, `/api/items`,
`/api/messages`, and message replies receive an `id:` if one was not provided.
Existing IDs are collected from every configured input file in `paths`, plus the
configured `write_file` and the command output file when applicable, so generated
IDs avoid collisions across multiple loaded `life.txt` files.
`check` reports duplicate IDs as warning `W213`, including duplicates across
multiple input files.
Set `ids.key` / `api.id_key` to use a custom ID detail key; id-based Web API
operations and `ids --assign --key KEY` use the selected key. Config `users`,
`teams`, and `tags` supply aliases and team membership for `--user`, `--team`,
and tag filters.

Files listed in top-level `generated_paths` or `sync_ics.generated_paths` are
treated as generated/read-only by ordinary mutation commands such as `assist`,
`done`, `archive`, `assign`, `tag`, `batch`, `migrate`, `encrypt`, and
`decrypt`. `sync-ics` is the exception because generated files are its intended
output target; it still refuses OS read-only output files.

### 12.1 Configuration Resolution Order

The same setting (for example, which person's name is used as `self`, or
which project a `quick` item is assigned to) can be supplied at four
different levels. When more than one level supplies a value, lifetxt applies
them in this order, highest priority first:

1. **CLI flag** — a flag passed directly to the command you run, e.g.
   `lifetxt quick "Buy milk" --project errands` or `lifetxt agenda --person alice`.
2. **Config JSON defaults** — values under `defaults` (and related sections
   like `user`, `message`) in the loaded `.lifetxt.json`, e.g.
   `"defaults": {"person": "self", "timezone": "Asia/Tokyo"}`.
3. **`#!` file-level directives** — directive lines at the top of a life.txt
   file, e.g. `#! self: alice`, `#! project: research`, `#! timezone: UTC`.
   These apply only to the file they appear in.
4. **Built-in defaults** — hard-coded fallbacks used when nothing else
   supplies a value, e.g. person `"self"` or timezone `"UTC"`.

Example: if a life.txt file starts with `#! project: research` but you run
`lifetxt quick "Draft outline" --project writing`, the item is filed under
`writing` (CLI flag wins). If you omit `--project` but the config file sets
`"defaults": {"project": "misc"}` and the file has no `#! project:` directive,
the item is filed under `misc`. If none of the three higher levels supply a
project, the item has no project.

`lifetxt config init` prints this resolution order as a reminder after
writing the config file. `lifetxt init` writes both a starter life.txt (with
`#! self:` / `#! timezone:` / `#! project:` directives) and a matching
`.lifetxt.json` (with `defaults.person` / `defaults.timezone`) so new users
see all three configurable levels side by side.

## 13. CUI Extensions

### 13.1 `tui`

`tui` opens an interactive terminal workspace for open tasks, near-current
agenda items, and active `S` status records.

```sh
python -m lifetxt tui [path ...]
python -m lifetxt tui life.txt --theme dark --limit 15
python -m lifetxt tui life.txt --keymap vim --agenda-window 1d
python -m lifetxt tui life.txt --glyphs ascii
python -m lifetxt tui life.txt --plain > snapshot.txt
```

On a real terminal, `tui` runs an interactive workspace: a persistent input bar
at the bottom, a slash-command palette with fuzzy completion, live filtering as
you type, one scrollable result list with section headers, and an inspector
panel for the selected row. When stdout is not a TTY (piping or redirecting), or
with `--plain`, the command prints a single plain-text dashboard snapshot
instead, so `python -m lifetxt tui > snapshot.txt` still works.

#### Remote mode (`--remote-url`)

`tui` can operate against a remote `lifetxt serve` workspace over HTTP(S)
instead of local files, so a client machine can inspect and operate an
authoritative workspace hosted elsewhere with the same interaction model
used for local files.

```sh
python -m lifetxt tui --remote-url https://lifetxt.example.internal
python -m lifetxt tui --remote-url http://127.0.0.1:8765
python -m lifetxt tui --remote-url http://lifetxt.wg-internal:8080 \
    --remote-user alice --allow-insecure-remote-http
```

- `--remote-url` selects remote mode; local `tui` is completely unchanged
  when it is omitted.
- `--remote-user` sets an HTTP Basic Auth username (for example, one an
  Apache reverse proxy enforces). The password is never a literal CLI
  argument: it is read from the `LIFETXT_REMOTE_TUI_PASSWORD` environment
  variable, or the variable named by `--remote-password-env`.
- Plain HTTP to a non-loopback host is refused unless
  `--allow-insecure-remote-http` is given explicitly. This is intended only
  for a connection already secured by another layer, such as a WireGuard
  tunnel -- HTTPS remains the safer general default, and this flag does not
  make plain HTTP to a public host safe.
- Requires the interactive curses workspace: `--plain` and piped/redirected
  output are not supported for remote mode.

**Reference deployment.** The motivating topology is a personal server
reachable only over a private network:

```text
Remote client
  lifetxt tui --remote-url http://lifetxt.wg-internal:8080 --remote-user alice \
      --allow-insecure-remote-http
      |
      | HTTP over WireGuard (already encrypted at the tunnel layer)
      v
Apache :8080  (HTTP Basic Auth)
      |
      | reverse proxy
      v
127.0.0.1:8765  lifetxt serve
      |
      v
server-side authoritative life.txt/workspace
```

Basic Auth over plain HTTP is only appropriate here because WireGuard
already encrypts the link; the password is otherwise sent in a trivially
reversible encoding. Never place this topology's Apache endpoint directly
on the public Internet.

**Operations and revision safety.** Remote mode reads and writes through
the server's ordinary REST API (`GET /api/items`,
`PUT`/`DELETE .../api/items/id/{id}`, `POST /api/items`), using the
server's existing whole-file `If-Match`/`X-Lifetxt-Revision` precondition
contract -- the same one every `lifetxt serve` deployment already has, not
a second protocol invented for the TUI. A write is rejected with a
conflict, never silently applied or auto-retried, if the file changed
since this session last read it; the conflict message and a reload are
your recovery path. There is no local write target in remote mode:
commands with no remote equivalent yet (currently `/state` and `/now`,
which manage presence status) report a clear error instead of writing to a
local file.

**Automatic refresh.** Once connected, the TUI polls the server every 1.5
seconds using a single cheap `GET /api/revision` call -- far lighter than
re-fetching every item -- and only reloads the full item list when that
revision actually changed. The active view, selection, and search/filter
state are preserved across a background reload when the selected item
still exists. `/reload` remains available as a manual fallback at any
time. This is deliberately simple bounded polling, not a push protocol
(SSE/WebSocket); a future optimization may add one if measurements justify
it.

**Connection status.** The header shows `remote:<host> as <user>
(connected)` or `(disconnected)` -- never a password -- and a toast
announces a lost or restored connection. A transient network failure
leaves the last-known view on screen rather than clearing it; only the
status word changes. A startup connection failure exits with a clear
error rather than falling back to any local file.

**Multi-client use.** Two or more `tui --remote-url` sessions (or a mix of
TUI, Web UI, and CLI clients) against the same server are safe: each
authoritative write carries the writer's own last-known revision, so a
second client's stale edit is rejected as a conflict rather than silently
overwriting the first client's change, and a committed change becomes
visible to every other client within one polling interval.

**Offline read cache (`--remote-cache`).** By default, remote mode has no
offline cache: a connection failure never falls back to local data. Passing
`--remote-cache` opts in to a bounded, read-only last-known snapshot: after
every successful read, the fetched items and revision are persisted under
`~/.cache/lifetxt/remote-tui/` (or `$LIFETXT_REMOTE_TUI_CACHE_DIR`), keyed by
the server URL and username so different servers or users never mix. If the
connection is later unreachable, the TUI shows this cached view instead of
only an error, with the header reporting `cached, stale` and the age of the
snapshot. The cache:

- is never treated as authoritative and is bounded to 2000 items;
- never stores credentials, tokens, or Authorization headers -- only the
  server-visible item content already returned by `GET /api/items`;
- is written with owner-only file permissions where the OS supports it;
- refuses every mutation (create/edit/delete) while it is the active view,
  since a cached snapshot cannot honor the server's revision-precondition
  contract -- reconnecting and reloading first is required before writing
  again.

`--remote-clear-cache` deletes the cache for the given `--remote-url` (and
`--remote-user`, if set) and exits without starting the TUI:

```sh
python -m lifetxt tui --remote-url https://lifetxt.example.internal --remote-cache
python -m lifetxt tui --remote-url https://lifetxt.example.internal --remote-clear-cache
```

**Current limitations.** No offline mutation queue -- writes always require
a live connection, even with `--remote-cache` enabled. Marked-row bulk edits
spanning many items in one semantic commit remain local-only; remote edits
are applied one item at a time. Presence status (`/state`, `/now`) has no
remote equivalent yet. See `lifetxt remote` (the existing dependency-free
Remote Safe Mode CLI/REPL, [§20](#20-remote-safe-mode-client-remote))
for a different, ticket-focused remote client this feature does not
replace.

#### The input bar

The input bar is always focused in the default `prompt` keymap. Typing plain
text filters every listed row as you type, using a fuzzy matcher that scores
substring hits above scattered subsequence hits and highlights the matched
characters. Fields are weighted, so a title hit ranks above an id hit, which
ranks above a hit buried in a detail value. Press `Enter` to commit the filter and clear the bar, or `Esc` to
clear the bar and then the active filters.

Typing `/` opens the command palette. It ranks commands with the same fuzzy
matcher, shows each command's usage and summary, and completes the highlighted
entry with `Tab`. `Enter` runs the typed command; if the name is not exact, the
highlighted suggestion runs instead, so `/do` + `Enter` runs `/done`. An unknown
command fails loudly and suggests the closest name.

Once the command name is followed by a space, the palette switches to listing
that command's **argument values** and `Tab` completes those instead:

```txt
/state <TAB>     available busy focus meeting away commuting …
/timer <TAB>     start stop status cancel
/due tomo<TAB>   tomorrow
/project re<TAB> (the projects in your file starting with "re")
/goto <TAB>      (the record ids in your file)
```

Fixed-choice commands (`/view`, `/sort`, `/status`, `/mark`, `/timer`,
`/export`, `/theme`) offer their own words. The rest read the file you have
open, so `/project`, `/context`, `/tag`, `/goto`, `/assign`, `/now`, and
`/state` offer the projects, contexts, tags, ids, and people it already
contains — including presence states of your own beyond the documented set.
`/due` offers the date words the shorthand accepts. Commands taking free text,
such as `/search` and `/add`, offer nothing.

Up/Down move through the candidates and `Tab` accepts the highlighted one.
These are the same candidates the shell completion scripts, the Web UI, and
the MCP `complete` tool return.

#### Commands

**Views and filters**

| Command | Purpose |
| --- | --- |
| `/help [QUERY]` | Toggle the reference, or search it (`/help timer`) |
| `/view all\|tasks\|agenda\|status\|next\|today` | Switch which sections are listed |
| `/next` | Open, unblocked, non-someday actions ordered by priority |
| `/today` | Show the Daily Command Center: now, attention, inbox, upcoming |
| `/search TEXT` | Fuzzy filter every listed row |
| `/project NAME` | Filter by `project:` (empty value clears it) |
| `/context NAME` | Filter by `context:` (empty value clears it) |
| `/tag NAME` | Filter by `tag:`, with or without a leading `#` |
| `/saved [NAME]` | List saved views, or apply one as the active filter |
| `/area [NAME]` | List areas with progress, or filter rows to one area |
| `/sort natural\|due\|priority\|title\|status` | Change row ordering |
| `/clear` | Clear every filter and mark |
| `/goto ID` | Move the selection to a record id |
| `/mark toggle\|all\|none` | Mark rows for bulk actions |

**Editing** — every command below applies to the marked rows, or to the selected
row when nothing is marked.

| Command | Purpose |
| --- | --- |
| `/done [now]` | Mark task-like rows done and record `done:`; `now` adds the time |
| `/state STATE [TITLE] \| end` | Record presence, closing the previous status; `/state end` closes it |
| `/now [PERSON]` | Show the current open presence status |
| `/status open\|active\|done\|dropped` | Set a status, using the same aliases as the CLI |
| `/set KEY VALUE` | Set a detail; an empty value removes the key |
| `/due DATE` | Set `due:` using `today`, `tomorrow`, a weekday, `+3d`, or `-1w` |
| `/assign USER` | Set `assignee:` |
| `/add TITLE` | Append a new open task; capture sigils (`@ # ! ^`) are expanded |
| `/delete yes` | Delete rows; refuses without the explicit `yes` |
| `/edit` | Open the selected row in `$EDITOR` |
| `/timer start\|stop\|status\|cancel` | Track elapsed time and write `elapsed:` on stop |
| `/undo` | Undo the last write made in this session |

**Output and appearance**

| Command | Purpose |
| --- | --- |
| `/export md\|csv\|json [PATH]` | Write the currently visible rows to a file |
| `/stats` | Toggle a breakdown of visible rows by status, type, and project |
| `/detail` | Toggle the inspector panel |
| `/reload` | Re-read every file now |
| `/theme auto\|dark\|light\|mono` | Change the color theme, applied immediately |
| `/limit N` | Rows kept per section |
| `/window 12h` | Agenda window around now |
| `/quit` | Leave the TUI |

#### Choosing an editor

`/edit` (and `fzf --action edit`) resolves the editor from `EDITOR`, then
`VISUAL`, then an `editor` key in the config file. The config key exists for
Windows, where neither variable is normally set:

```powershell
$env:EDITOR = "code"                                               # this session
[Environment]::SetEnvironmentVariable("EDITOR", "code", "User")    # permanent
```

```sh
export EDITOR=vim        # add to your shell profile to persist
```

```json
{ "editor": "code" }
```

The config file is `.lifetxt.json` or `lifetxt.config.json` **in the current
directory**, or the path in `$LIFETXT_CONFIG`. There is no global config
location, so the `editor` key only applies when you run `lifetxt` from that
directory; use `EDITOR` if you want it to apply everywhere.

The setting may include flags, such as `code -n`. The executable is resolved
through `PATH`, which is required on Windows where `code` is a `.CMD` that
cannot be launched from a bare name. Editors that open a window are passed a
wait flag so that `/edit` returns only after you close the file.

Line numbers are passed as `+42` to `vim`, `nvim`, `vi`, `nano`, `emacs`,
`micro`, and `gedit`, and as a `path:42` suffix to `helix`, VS Code and its
forks, and Sublime Text. Any other editor simply receives the file path. When no editor is configured, the error names the exact
command to run for your platform.

Terminal editors are supported: the TUI releases the terminal before launching
the editor and restores the screen when it exits.

Command aliases: `/d` done, `/s` state, `/a` add, `/f` search, `/t` timer,
`/e` edit, `/u` undo, `/n` next, `/q` quit. An exact alias beats fuzzy ranking.

#### Editing safety

Every editing command runs through one internal mutation path. It validates all
target rows *before* writing anything, so a bulk edit that includes a row
without an `id:` fails loudly and changes nothing rather than applying to half
the selection. The affected files are snapshotted as a single undo entry, so one
`/undo` reverts a whole bulk operation, including `/delete`.

Rows without an `id:` cannot be edited from the TUI. Run `lifetxt ids --assign`
first.

#### Timer

`/timer start` starts a stopwatch on the selected row and flips a `[ ]` task to
`[/]`. `/timer status` reports the running timer, `/timer stop` adds the elapsed
minutes to any existing `elapsed:` value and clears the timer, and
`/timer cancel` discards the session without writing `elapsed:`. The state file
is shared with `lifetxt timer`, so only one timer runs at a time across both.

#### Export

`/export` writes the rows exactly as filtered and sorted on screen, so
`/project work` then `/sort due` then `/export md report.md` produces a report of
that view. Markdown emits a checkbox list grouped by section, CSV emits one
header row plus one row per record, and JSON emits the full row objects
including details.

#### Row limits

`tui.limit` (or `/limit N`) caps how many rows each section shows. Truncation is
never silent: the section header shows `TASKS 10/30`, and a trailing
`... 20 more hidden by limit:10` row appears at the end of the section.

#### Session state

View, sort, project/context/tag filters, inspector visibility, and command
history are saved to `.cache/lifetxt/tui_session.json` on exit and restored on
the next run. Values that are no longer valid are ignored rather than failing.
Set `tui.session_file` to move the file, or `tui.session` to `off` to disable it.

#### Keys

In the default `prompt` keymap: Up/Down move the selection (or the palette
entry when it is open), PageUp/PageDown move by half a page, Home/End jump to
the first or last row, `Ctrl-T` marks or unmarks the selected row, `Ctrl-P` /
`Ctrl-N` recall previous input, `Ctrl-A` / `Ctrl-E` jump to the start or end of
the input, `Ctrl-U` / `Ctrl-K` delete before or after the cursor, and `Ctrl-C`
quits cleanly without a traceback.

`--keymap vim` starts in a navigation mode instead, where `j` / `k` move,
`g` / `G` jump to the first or last row, `Space` marks, `Enter` toggles the
inspector, `Tab` cycles views, `d` / `e` / `u` / `r` run done / edit / undo /
reload, `/` starts a filter, `:` starts a command, `?` toggles help, and `q`
quits. `/` and `:` are one-shot: after `Enter` or `Esc` the input bar hands
control back to navigation mode, so `j` and `k` move again immediately.

While help is open, `j` / `k` and PageUp/PageDown scroll the reference, which is
longer than one screen.

##### Custom key bindings

The `vim`/`arrows` navigation actions above (`move_up`, `move_down`, `first`,
`last`, `open`, `toggle_mark`, `done`, `search`, `command`, `reload`, `help`,
`quit`) can each be remapped to different keys through `tui.bindings`, layered
on top of the selected keymap:

```json
{
  "tui": {
    "keymap": "vim",
    "bindings": {
      "move_up": ["k"],
      "move_down": ["j"],
      "open": ["enter", "l"],
      "done": ["x"],
      "search": ["/"],
      "help": ["?"],
      "quit": ["q"]
    }
  }
}
```

A value may be a single key name or an array of aliases; unmentioned actions
keep the built-in preset's key. `?` (toggle help, when the reference is
closed) shows the *effective* bindings, so a customization is never
documented incorrectly. `Ctrl-C`, page moves, `e`/`u` (edit/undo), `Tab`
(cycle views), and `Esc`/cancel are never part of this registry and always
work, so a custom map can never make the TUI impossible to exit. A key
already mapped to two different actions, an unknown action id, or an
unsupported key name is rejected before the TUI starts, naming the problem.
See [config.md](config.md#configurable-tui-key-bindings) for the full
contract, including the `prompt` keymap's own default keys, which have no
`tui.bindings` overlay since `prompt` never leaves the input bar.

#### Appearance

On terminals at least 118 columns wide the inspector moves beside the list as a
right-hand pane instead of sitting below it, and stacks one field per line so
narrow panes do not clip values.

`--theme auto|dark|light|mono` controls colors, and `--glyphs
auto|unicode|ascii` chooses the box-drawing set. `auto` probes the output
encoding and falls back to ASCII when the terminal cannot represent the rounded
borders, so Windows code pages degrade cleanly instead of raising. Column
widths are East Asian Width-aware, so Japanese titles stay aligned, and the meta
columns (project, due, priority, and -- on the widest terminals -- `progress:`)
drop out one at a time as the terminal narrows rather than wrapping. A record
with no `progress:` detail shows nothing in that column. Selecting a row and
opening the detail inspector (`s`) shows the same `progress:` value alongside
the full life.txt line; editing it, like editing any other detail, goes
through `e` (open in `$EDITOR`), the same guarded, revision-checked write path
every other TUI edit uses.

Defaults can be set in config under `tui.theme`, `tui.keymap`, `tui.glyphs`,
`tui.limit`, `tui.agenda_window`, and `tui.bindings` (see above).

Filtering and sorting run against a cached parse, so typing in the input bar
does not re-read the files. A re-parse happens only when a file changes on disk,
after a write, or on `/reload`.

The workspace auto-reloads when input files change. If `watchdog` is installed,
file events are used; otherwise the fallback checks file mtimes periodically. A
file that fails to parse shows an error panel with the diagnostic instead of
exiting, so you can fix the file and watch it recover.

### 13.2 `fzf`

`fzf` applies the normal item filters, sends matching items to `fzf` or `peco`,
and then runs an action.

```sh
python -m lifetxt fzf life.txt --open --type task --action done
python -m lifetxt fzf life.txt --project research --action show
python -m lifetxt fzf "projects/**/*.life.txt" --tool peco --action edit
```

Options:

| Option | Meaning |
|---|---|
| `--action done|edit|delete|show` | Action for selected items; prompts when omitted |
| `--tool fzf|peco` | Selection tool; auto-detects `fzf` then `peco` by default |
| `--preview` / `--no-preview` | Enable or disable `fzf` preview |
| `--print-query` | With `fzf`, print the query line instead of selected items |

`done` and `delete` require an item ID. Use `ids --assign` first if needed.
`delete` prints the selected source file, line, and title, then requires typing
`DELETE`. `edit` opens the selected source file with `$EDITOR`. The fzf preview
shows the source location, multiline `body:`, and the generated life.txt line.

### 13.3 `timer`

`timer` keeps one running timer in a JSON state file and writes accumulated time
back to the item as `elapsed:`.

```sh
python -m lifetxt timer start life.txt --id task_report
python -m lifetxt timer status life.txt
python -m lifetxt timer pause
python -m lifetxt timer resume
python -m lifetxt timer stop
python -m lifetxt timer summary life.txt --project research
```

Subcommands:

| Subcommand | Meaning |
|---|---|
| `start path --id ID` | Start timing the item with `id:ID`; `[ ]` becomes `[/]` |
| `pause` | Pause the single running timer without changing the item |
| `resume` | Resume a paused timer |
| `stop [path] [--id ID]` | Stop the running timer and update `elapsed:` |
| `status [path ...]` | Show the current timer and elapsed time |
| `summary path ...` | Sum `elapsed:` values by item and project |
| `cancel` | Remove the running state without changing any item |

Only one global timer can run at a time. `pause` stores the current accumulated
minutes in the state file, and `stop` writes the accumulated total back to the
item even if the timer is currently paused. Elapsed values use compact forms
such as `25m`, `1h`, or `1h30m`. The state file defaults to
`~/.lifetxt_timer.json` and can be changed with `timer.state_file` in config.

### 13.4 `stats`

`stats` summarizes task completion, overdue tasks, habit streaks, mood entries,
and project completion rates.

```sh
python -m lifetxt stats life.txt
python -m lifetxt stats life.txt --from 2026-06-01 --to 2026-06-30
python -m lifetxt stats life.txt --project research --format json
python -m lifetxt stats life.txt --tag focus --assignee alice --format json
python -m lifetxt stats "projects/**/*.life.txt" --group weekly
python -m lifetxt stats life.txt --width 60
```

Options:

| Option | Meaning |
|---|---|
| `--from DATE` | Start date; defaults to 29 days before `--to` |
| `--to DATE` | End date; defaults to today |
| `filter options` | Same item filters as `filter`, including status, type, project, tag, user, team, people, detail, text, and time filters |
| `--group daily|weekly|monthly` | Bucket mood trend output |
| `--format text|json` | Output format |
| `--width N` | Use compact text output for narrow terminal widths |

For `weekly` and `monthly`, task buckets are shown with done / total / overdue
counts, and habit sparklines are bucketed by completion count.

### 13.5 Reports, Charts, Batch, And Encryption

`review` can emit JSON, JSONL, Markdown, or a self-contained HTML report:

```sh
python -m lifetxt review life.txt --week --format html > weekly_review.html
```

`plot` still renders terminal bar charts by default. It can also write SVG
without extra dependencies, or PNG when `matplotlib` is installed:

```sh
python -m lifetxt plot life.txt --chart deadlines --from 2026-06-01 --to 2026-06-30
python -m lifetxt plot life.txt --chart tasks --format svg -o tasks.svg
python -m lifetxt plot life.txt --chart habits --format png -o habits.png
```

`export-heatmap` writes a dependency-free SVG calendar heatmap of task and habit
activity:

```sh
python -m lifetxt export-heatmap life.txt --from 2026-01-01 --to 2026-12-31 -o activity.svg
python -m lifetxt export-heatmap "projects/**/*.life.txt" --type habit --project research -o habits.svg
```

`batch` applies an existing item action across multiple files. It reuses the
regular implementations so validation, atomic writes, and generated/read-only
file refusal stay consistent:

```sh
python -m lifetxt batch done "projects/**/*.life.txt" --id task_report
python -m lifetxt batch assign life.txt team_life.txt --text Review --to alice --dry-run
python -m lifetxt batch tag-rename "projects/**/*.life.txt" --old inbox --new triage --dry-run
python -m lifetxt batch tag-merge team.life.txt archive.life.txt --old urgent_old --new urgent
python -m lifetxt batch migrate "projects/**/*.life.txt" --migration normalize-status --migration strip-empty-details --backup
```

Supported actions are `done`, `assign`, `tag-rename`, `tag-merge`, and
`migrate`. `done` and `assign` require at least one `--id` or `--text`
selector. `tag-rename` and `tag-merge` require `--old` and `--new`.
`migrate` requires one or more `--migration NAME[=ARG]` flags. The summary
reports how many per-file operations were applied and how many failed.

`watch` reruns a lifetxt subcommand whenever the input files change:

```sh
python -m lifetxt watch life.txt --run agenda --timestamp
python -m lifetxt watch life.txt .generated/google_calendar.life.txt --run "agenda --around now --window 2h" --notify
```

`--timestamp` prints a dated run header. Non-zero command exits are highlighted
on terminals that support ANSI colors. `--notify` sends a desktop notification
when the child command exit status changes; if desktop notification support is
not available, it falls back to a terminal bell.

`encrypt` and `decrypt` can read the passphrase from either an environment
variable or a UTF-8 text file:

```sh
python -m lifetxt encrypt life.txt --field body --type journal --key-file .secrets/lifetxt.key
python -m lifetxt encrypt life.txt --field body --type journal --algorithm aesgcm --key-file .secrets/lifetxt.key
python -m lifetxt decrypt life.txt --field body --key-file .secrets/lifetxt.key
```

`inbox --fzf` sends unclassified inbox items to `fzf` or `peco` and prints the
selected row. It returns an error if neither selector is installed.

### 13.6 `git-hook`

`git-hook` installs local Git hooks for the current repository. The generated
`pre-commit` hook runs `lifetxt check` for the configured files. The generated
`commit-msg` hook appends a short list of completed tasks when available.

```sh
python -m lifetxt git-hook status
python -m lifetxt git-hook install --files life.txt examples/*.txt
python -m lifetxt git-hook uninstall
```

The installer refuses to overwrite non-lifetxt hooks unless `--force` is passed.
Use `--no-commit-msg` when only validation is desired.

### 13.7 `completion`

`completion` emits shell completion scripts.

```sh
python -m lifetxt completion bash
python -m lifetxt completion zsh -o ~/.zfunc/_lifetxt
python -m lifetxt completion fish -o ~/.config/fish/completions/lifetxt.fish
python -m lifetxt completion powershell -o $HOME\Documents\PowerShell\lifetxt-completion.ps1
python -m lifetxt completion install --shell bash
```

`completion install` prints commands only. It does not modify shell startup
files automatically.

Everything the scripts offer is derived from the CLI's own argument parser, so
a new command or flag appears in completion as soon as it exists.

**Options are scoped to the command being typed.** `lifetxt check --<TAB>`
offers only the ten flags `check` accepts, not every flag in the program:

```txt
lifetxt check --<TAB>
  --help --verify-files --no-files --format --warnings-as-errors
  --ignore --severity --code --category --config
```

**Values are completed too.** Fixed sets such as `--type`, `--format`,
`--theme`, and `--state` come from the format definitions. Subcommands are
completed as well, so `lifetxt timer <TAB>` offers `start stop status cancel`.

Presence states are completed both as a flag value and as the positional that
`state`, `s`, and `start` take, which is the form most people type:

```txt
lifetxt state <TAB>
  available busy focus meeting away commuting working offline sleeping
```

#### Candidates from your own file

`state:` is free-form, and projects, tags, IDs, and people are entirely yours,
so the built-in lists cannot know them. The scripts call a helper command to
read the current file:

```bash
python -m lifetxt completion values --kind state
python -m lifetxt completion values --kind project life.txt
```

| `--kind` | Candidates |
|---|---|
| `state` | The documented states, followed by any others in your file |
| `project`, `tag`, `id` | Values present in the file |
| `person` | `person:`, `owner:`, `assignee:`, `attendee:`, `sender:`, `recipient:`, `user:` |
| `type`, `status` | The format's own sets; no file needed |

Paths default to the config `paths`. Because a shell runs this while you are
typing, it never fails loudly: an unreadable or missing file yields the
built-in candidates rather than an error that would corrupt your prompt.

So a file using `state:hyperfocus` completes it alongside the documented set:

```txt
lifetxt state <TAB>
  available busy focus meeting away commuting working offline sleeping hyperfocus
```

PowerShell note: `lifetxt check --<TAB>` does not fire, because PowerShell
treats a bare `--` as the end-of-parameters marker and never calls the
completer. Type at least one more character (`lifetxt check --v<TAB>`).

### 13.8 `deps`

`deps` prints unresolved or declared dependency chains as an indented terminal
tree. It uses the same blocker semantics as `agenda` and `health`: a
`depends_on:` target blocks the current item, and an item with `blocks:ID`
blocks the target `ID`.

```sh
python -m lifetxt deps life.txt
python -m lifetxt deps life.txt --blocked
python -m lifetxt deps life.txt --root task_report
python -m lifetxt deps life.txt --root task_report --format json --pretty
python -m lifetxt deps life.txt --root task_report --format mermaid --depth 2
python -m lifetxt deps life.txt --blocked --format dot
```

Options:

| Option | Meaning |
|---|---|
| `--blocked` | Show only open items with open blockers |
| `--root ID` | Trace the blocker chain for one item ID |
| `--format text|json|mermaid|dot` | Output format |
| `--depth N` | Maximum dependency depth to render; `0` shows root nodes only |
| `--pretty` | Pretty-print JSON |

### 13.9 `complete` and habit `done` logging

Task-like items marked `[x]` with `done` lose their `repeat:` cadence: nothing
records the next due instance, and the file itself is the only completion
history. `complete` and the habit-aware branch of `done` resolve this without
inventing a new syntax; both build on the existing `repeat:`, `due:`/`do:`,
`until:`, and `done:` detail keys.

**`complete`** targets repeat-enabled tasks (any type, typically `T`). It
marks the current instance `[x]` with `done:DATE` and appends a fresh `[ ]`
instance immediately after it with the next due date, Taskwarrior-style:

```sh
python -m lifetxt complete life.txt task_water_plants
python -m lifetxt complete life.txt --text "Water plants" --date 2026-07-08
python -m lifetxt complete life.txt task_water_plants --dry-run
```

The next due date advances by exactly one `repeat:` interval from an anchor
date, controlled by `repeat_base:due|done` (a detail key on the item, or
`defaults.repeat_base` in config; `due` is the default):

- `repeat_base:due` advances from the item's current `due:`/`do:` value. The
  item must already carry a `due:` or `do:`; missing dates fail loudly instead
  of guessing a start date.
- `repeat_base:done` advances from the completion date instead (today, or
  `--date`), useful for tasks where "clean the gutters every 3 months after I
  actually did it" matters more than a fixed schedule.

If the series has a `until:` bound and the next occurrence would fall after
it, `complete` marks the current instance done and prints that the series has
ended without materializing a new instance. `BYDAY` RRULE values (e.g.
`RRULE:FREQ=WEEKLY;BYDAY=MO,WE,FR`) are not yet supported for materialization
and fail loudly; edit the due date by hand for those. Items without a
`repeat:` value behave exactly like `done`. The new instance always gets a
freshly generated ID — the completed instance keeps its original ID — so
`ids` never reports a collision. File growth from repeated completions is
expected; run `archive` periodically to move closed instances out of the
working file.

**Habit `done` logging** (`H` type items) takes a different approach, because
a habit definition is meant to stay a single always-open line while its
history accumulates. `lifetxt done PATH ID [--date DATE] [--force]` on an `H`
item does not touch `status:`; it appends `done:DATE` to the item's existing
`done:` values (a duplicate-key list, same as any other repeated detail key)
and prints the resulting streak:

```sh
python -m lifetxt done life.txt habit_exercise
python -m lifetxt done life.txt habit_exercise --date 2026-06-01
```

Logging the same date twice fails loudly (`--force` overrides it
deliberately) so a stray second run cannot silently inflate a streak. Streaks
are computed from the accumulated `done:` dates with `stats.streak_days`, the
same function the Web UI heatmap and `stats --habits` already use, so all
surfaces agree. Non-habit `done` is unchanged: `done PATH ID [--date DATE]`
still marks the item `[x]` and sets `done:DATE` (defaulting to today).

### 13.10 `rrule`: expanding a recurrence

`repeat:` accepts both plain cadences (`daily`, `weekly`) and iCalendar rules
(`RRULE:FREQ=MONTHLY;BYDAY=1MO`). The rule text alone rarely makes the actual
dates obvious, so `rrule` expands one into the concrete occurrences that
`agenda` and `complete` will use.

Expand a rule directly:

```bash
python -m lifetxt rrule "RRULE:FREQ=MONTHLY;BYDAY=1MO" --from 2026-07-01 --count 3
```

```txt
Every month on 1st Monday
  1  2026-07-06  Mon
  2  2026-08-03  Mon
  3  2026-09-07  Mon
```

Or expand the rule already stored on an item:

```bash
python -m lifetxt rrule --path life.txt --id standup --count 4
```

Options:

| Option | Meaning |
|---|---|
| `--path PATH`, `--id ID` | Read `repeat:` from an existing item instead of passing a rule |
| `--from DATE` | Series start; defaults to today, or the item's `due:`/`do:`/`from:` |
| `--after DATE`, `--before DATE` | Restrict output to a window |
| `--count N` | Maximum occurrences to print (default 10) |
| `--format text\|json\|life` | Human-readable table, machine-readable JSON, or ready-to-paste life.txt lines |
| `--type KIND`, `--title TEXT` | Type and title used by `--format life` |

`--format life` emits records you can append directly, which is useful for
materializing a fixed number of instances instead of relying on `complete`:

```bash
python -m lifetxt rrule weekly --from 2026-07-06 --count 2 --format life \
  --type T --title Standup
```

```txt
[ ] T Standup due:2026-07-06
[ ] T Standup due:2026-07-13
```

The supported subset is `FREQ`, `INTERVAL`, `COUNT`, `UNTIL`, `BYDAY`
(including positional forms such as `1MO` and `-1FR`), `BYMONTHDAY`
(including negative offsets such as `-1` for the last day), `BYMONTH`, and
`WKST`. Parts outside that subset are reported on stderr rather than silently
ignored:

```txt
Ignoring unsupported RRULE part(s): BYSETPOS
```

A date-only `UNTIL` covers the whole day, so `UNTIL=20260703` includes an
occurrence on 2026-07-03 rather than cutting off at midnight.

#### `WKST`: which day starts a week

`WKST` names the first day of the week and defaults to Monday. It changes the
result whenever `INTERVAL` skips weeks, because it decides which week a date
belongs to. These two rules differ only in `WKST` (the example is from RFC
5545 §3.8.5.3):

```bash
python -m lifetxt rrule "RRULE:FREQ=WEEKLY;INTERVAL=2;COUNT=4;BYDAY=TU,SU;WKST=MO" \
  --from 1997-08-05
python -m lifetxt rrule "RRULE:FREQ=WEEKLY;INTERVAL=2;COUNT=4;BYDAY=TU,SU;WKST=SU" \
  --from 1997-08-05
```

```txt
WKST=MO  →  Aug 5, 10, 19, 24
WKST=SU  →  Aug 5, 17, 19, 31
```

With `WKST=MO` the Sunday closes its week, so Aug 10 still belongs to the
first selected week. With `WKST=SU` a Sunday opens a new week, so Aug 10 falls
in the skipped week and Aug 17 is the next match. The week start also fixes
the order within a week, which is why the Sunday precedes the Tuesday above.

`--format json` reports it as `week_start`, and `describe` mentions it only
when the interval makes it matter:

```txt
Every 2 weeks on Sunday, Tuesday (weeks start Sunday)
```

A position in `BYDAY` (`2MO`) applies only to `FREQ=MONTHLY` and
`FREQ=YEARLY`. Weekly and daily expansion ignores the number, so `check`
warns rather than letting `FREQ=WEEKLY;BYDAY=2MO` quietly mean every Monday.

### 13.11 `progress`

`lifetxt progress PATH [ID] --delta DELTA` increments or decrements an
item's existing `progress:` value by a signed delta, without rewriting it
by hand. `lifetxt progress PATH [ID] --set VALUE` (#665) instead replaces
`progress:` directly with `VALUE`, in whichever representation you give it.
`--delta` and `--set` are mutually exclusive. Both reuse the shared
`progress:` parser and validator (`0<=current<=total` for a fraction,
`0-100` for a percentage) and the same guarded mutation path as
`done`/`complete`, so revision/backup handling is identical.

```sh
python -m lifetxt progress life.txt experiment_1 --delta +1
python -m lifetxt progress life.txt experiment_1 --delta=-1
python -m lifetxt progress life.txt task_1 --delta +10%
python -m lifetxt progress life.txt task_1 --delta=-15% --dry-run
python -m lifetxt progress life.txt task_1 --set 75%
python -m lifetxt progress life.txt experiment_1 --set 3/10
```

Given `progress:3/10`, `--delta +1` produces `progress:4/10` (the
denominator is kept); given `progress:40%`, `--delta +10%` produces
`progress:50%`. **Representation kind is never converted**: a `%`-suffixed
delta against a fraction, or a plain-number delta against a percentage,
fails loudly instead of guessing which one you meant. A negative delta
must use `--delta=-N` (with `=`) — `--delta -N` is parsed by argparse as an
unrecognized flag, not a value.

A result outside the valid range (`progress:14/10`, `progress:105%`, a
negative fraction numerator) is rejected before anything is written.
`--delta` against an item with **no** existing `progress:` detail is
rejected rather than silently treated as `0%` — set an initial value first
with `--set` (for example `lifetxt progress PATH ID --set 0%`); `--set`
itself works whether or not the item already has a `progress:` value,
since it never needs an existing one to add to or subtract from. `ID`
accepts a unique ID prefix (see [Short ID prefix selection](#short-id-prefix-selection));
`--line`/`--text` select an item the same way as `done`. `--dry-run` shows
the resulting value without writing.

### 13.12 `clone`

`lifetxt clone PATH [ID]` creates a new item derived from an existing one,
without copying its identity or history. It reuses the item's existing
parsed representation and the same append/mutation contract `quick` uses,
so revision/backup handling and ID generation are identical — this is not
a raw text copy.

```sh
lifetxt clone life.txt experiment_01
lifetxt clone life.txt experiment_01 --dry-run
```

Given:

```text
[/] T "Experiment condition A" id:experiment_01 project:research
    priority:A progress:8/10
```

`clone` appends:

```text
[ ] T "Experiment condition A" project:research priority:A
```

**Copy policy** (defined once, in one place, rather than per-field):
ordinary metadata (`project`, `tag`, `priority`, `context`, dates, and
every other detail not listed below) is copied as-is. The following are
never copied onto the clone:

- the source's own ID (whatever key `id_key` resolves to) — a duplicate ID
  would corrupt the workspace, so it is never carried over
- `source`, `uid`, `created`, `updated` — identity/system provenance of the
  *original* record, not the new one
- `done` — completion history
- `progress` — reset entirely rather than carried over or implicitly
  assumed to be `0%`, matching the same missing-progress principle
  `progress` (13.11) uses

**Status** defaults to open (`[ ]`) for ordinary kinds, reusing the exact
same kind-aware default `assist`'s interactive prompt uses: `N`/`J` (notes,
journal entries) get `[N]`, and `S` (presence status) gets `[/]` or `[x]`
depending on whether the resulting details still carry a `to:` value. The
original item is never modified. If `ids.auto` is enabled, the new item
receives a freshly generated, guaranteed-unique ID the same way `quick`
does; if disabled, the new item simply has no ID at all — either way, `ids`
never reports a collision. `ID` accepts a unique ID prefix (see
[Short ID prefix selection](#short-id-prefix-selection)); `--line`/`--text`
select the source item the same way as `done`. `--dry-run` shows the
generated item without writing it.

### 13.13 `reopen`

`lifetxt reopen PATH [ID]` undoes a completion: it removes `done:` and
restores the item to its existing kind-aware open/default status, the exact
same status `clone` gives a fresh copy (`[ ]` for ordinary kinds; `[N]` for
`N`/`J`; `[/]` or `[x]` for `S` depending on whether `to:` remains). It
reuses the same target resolver and guarded mutation path as
`done`/`complete`/`clone` rather than a second item-editing path.

```sh
python -m lifetxt reopen life.txt task_1
python -m lifetxt reopen life.txt task_1 --dry-run
```

Given `[x] T Task id:task_1 done:2026-09-01 project:home`, `reopen`
produces `[ ] T Task id:task_1 project:home` — `done:` is removed and every
other detail is preserved unchanged.

An already-open item is a deterministic no-op (exit `0`, nothing written,
"Already open" printed) rather than an error. Habit (`H`) records log
completions as multiple `done:` dates rather than a single completed state,
so `reopen` refuses habits outright and names the alternative
(`assist --update` to remove one specific `done:` date). `ID` accepts a
unique ID prefix (see [Short ID prefix selection](#short-id-prefix-selection));
`--line`/`--text` select an item the same way as `done`. `--dry-run` shows
the resulting status and which detail would be removed without writing.

### 13.14 `due`

`lifetxt due PATH ID DATE` sets or replaces one item's `due:` value;
`lifetxt due PATH ID --clear` removes it. `ID` is required and positional
(unlike `done`/`progress`/`clone`, `due` does not accept `--line`/`--text`,
since a second optional positional for the date would make which token
means what ambiguous). It reuses the same guarded mutation path as
`done`/`progress`/`clone`, so revision/backup handling is identical, and
only ever touches `due:` — every other detail, and item status, are
preserved unchanged.

```sh
python -m lifetxt due life.txt task_1 2026-09-07
python -m lifetxt due life.txt task_1 tomorrow
python -m lifetxt due life.txt task_1 --clear
python -m lifetxt due life.txt task_1 2026-09-07 --dry-run
```

`DATE` also accepts the bounded relative shorthand described in
[§13.15](#1315-relative-date-shorthand) (`today`, `tomorrow`, `+3d`, ...);
it is resolved to an absolute date before anything is written, so
`due:` in the file is always canonical. An invalid or unrecognized date
is rejected before anything is written. `--clear` on an item with no
`due:` is a deterministic no-op (exit `0`, nothing written). `ID` accepts
a unique ID prefix (see [Short ID prefix selection](#short-id-prefix-selection)).
`--dry-run` shows what would change without writing.

### 13.15 Relative date shorthand

A handful of commands that take a human-facing date accept a small,
deterministic set of relative tokens instead of typing `YYYY-MM-DD`
yourself: `today`, `tomorrow`, `yesterday`, a weekday name (the next
occurrence), `next_WEEKDAY`, `next_week`, and a signed offset such as
`+3d`, `-1w`, `+2m`, `+1y`. This is **not** a natural-language date
parser — `next monday`, `in two weeks`, and similar free-text phrases are
deliberately unsupported and fail with an actionable message rather than
being guessed at.

```sh
python -m lifetxt due life.txt task_1 tomorrow
python -m lifetxt quick "Submit report" --due tomorrow
python -m lifetxt quick "Renew lease" --due +30d
```

**Resolution happens only at this CLI input boundary**, through the one
shared resolver (`lifetxt.shorthand.resolve_date_token`) every accepting
command reuses, using the same workspace-aware current date
`today`/`agenda`/`done` already resolve their own dates against. The value
actually written to
`life.txt` is always the resolved canonical absolute date —
`due:2026-09-09`, never `due:tomorrow` — so Format 1.0 itself gains no new
syntax and every other reader of the file (the parser, `check`, the Web
API, MCP) sees only ordinary absolute dates. `quick`/`add`'s
`--due`/`--do`/`--until` flags already resolved this same shorthand
before `due` (13.14) existed; both now share the identical resolver
rather than each parsing dates independently. An explicit `YYYY-MM-DD`
value is returned unchanged.

## 14. Aliases

Status aliases include:

| Alias | Status |
|---|---|
| `todo`, `open`, `queued`, `scheduled` | `[ ]` |
| `progress`, `doing`, `in_progress`, `active`, `sending` | `[/]` |
| `done`, `complete`, `completed`, `sent`, `delivered` | `[x]` |
| `cancel`, `canceled`, `cancelled` | `[-]` |
| `defer`, `deferred`, `moved` | `[>]` |
| `pending`, `unknown` | `[?]` |
| `note`, `n` | `[N]` |

Type aliases include:

| Alias | Type |
|---|---|
| `task`, `todo` | `T` |
| `event`, `calendar` | `E` |
| `deadline`, `due` | `D` |
| `reminder`, `remind` | `R` |
| `habit`, `recurring` | `H` |
| `note`, `memo` | `N` |
| `status`, `presence`, `presence_status`, `state` | `S` |
| `message`, `msg`, `mail`, `notification` | `M` |
| `journal`, `diary`, `log`, `entry` | `J` |

## 15. Practical Workflows

Validate and convert:

```sh
python -m lifetxt check life.txt
python -m lifetxt to-json life.txt --pretty -o life.json
python -m lifetxt to-jsonl life.txt --open --type task -o open_tasks.jsonl
python -m lifetxt to-csv life.txt --type journal -o journal.csv
```

Create filtered life.txt files:

```sh
python -m lifetxt filter life.txt --open --type task -o open_tasks.life.txt
python -m lifetxt filter life.txt --after now --type event -o future_schedule.life.txt
python -m lifetxt filter life.txt --type status --person self -o my_status.life.txt
python -m lifetxt filter life.txt --type message --recipient alice -o alice_messages.life.txt
```

Import calendar events:

```sh
python -m lifetxt import-ics google_calendar.ics -o life.txt --append --tag google
```

Sync calendar events from a secret iCalendar URL:

```sh
python -m lifetxt sync-ics --url-env LIFETXT_GOOGLE_CAL_ICS -o .generated/google_calendar.life.txt --cache-dir .cache/lifetxt --tag google
```

Show near-current items:

```sh
python -m lifetxt agenda life.txt --around now --window 2h --open
```

Show today's unfinished tasks:

```sh
python -m lifetxt agenda life.txt --from 2026-06-06 --to 2026-06-06 --open --type task
```

Show current team presence:

```sh
python -m lifetxt status life.txt --active
```

Run the browser GUI:

```sh
pip install -r requirements-web.txt
python -m lifetxt serve life.txt
```

## 16. `tour`, `init`, and `doctor`

These are the recommended entry points for new users: `tour` needs nothing
at all, `init` creates your own workspace, and `doctor` checks it.

### 16.0 `tour`

A zero-config, dependency-free first-run demonstration. It builds a tiny,
built-in Beginner Profile sample -- covering `T`, `E`, and `N` -- entirely in
memory, runs it through the same `command_center`/"today" engine `lifetxt
today` uses, and prints both. No `life.txt`, config, network access, or
existing workspace is required, and nothing is written to disk:

```sh
python -m lifetxt tour
python -m lifetxt tour --format json
```

| Option | Meaning |
|---|---|
| `--format {text,json}` | Output format; defaults to `text` |
| `-o`, `--output FILE` | Write to a file instead of stdout |

The sample's dates are anchored to today's date, so the derived section shows
a task genuinely due today; run it again tomorrow and the same sample shows a
different day. The final section names concrete next steps: `init`, `add`,
and `today`.

```sh
python -m lifetxt init
python -m lifetxt init --yes
python -m lifetxt doctor
```

`init` creates a starter `life.txt` and a matching `.lifetxt.json`:

| Option | Meaning |
|---|---|
| `--file PATH` | life.txt file to create. Defaults to `life.txt` |
| `--config-output PATH` | Config file to create. Defaults to `.lifetxt.json` |
| `--force` | Overwrite existing files without prompting |
| `--name NAME` | Your name, written as `#! self:` and `defaults.person` |
| `--timezone TZ` | Your timezone, written as `#! timezone:` and `defaults.timezone` |
| `--project NAME` | Default project, written as `#! project:` and `defaults.project` |
| `--preset {minimal,personal,student,work,research}` | Starter section skeleton. Defaults to `minimal` (today's plain single-task starter, unchanged) |
| `--yes` | Run fully non-interactively using defaults (`self`, `UTC`, no project, `minimal` preset) — skips every prompt, including the overwrite confirmation when combined with `--force`. Use this in scripts and CI. |

Without `--yes`, `init` prompts for your name, timezone, default project, and
starter preset, and asks before overwriting an existing `life.txt` or config
file (unless `--force` is also given). With `--yes`, none of these prompts
are shown; any value not supplied via `--name`/`--timezone`/`--project`/
`--preset` falls back to its built-in default.

`--preset` only adds a small skeleton of `# Section` comment headings around
the same starter task -- no new Format syntax, no fabricated sample data, and
no separate parser or writer per preset:

```sh
python -m lifetxt init --preset student
python -m lifetxt init --preset research --yes
```

| Preset | Sections |
|---|---|
| `minimal` (default) | none -- just the starter task, matching `init`'s original output |
| `personal` | Tasks, Notes |
| `student` | Tasks, Classes / Events, Deadlines, Notes |
| `work` | Tasks, Meetings, Projects, Notes |
| `research` | Tasks, Meetings, Experiments, Research Notes |

`doctor` reports pass/warn/fail checks and never modifies files:

| Check | What it verifies |
|---|---|
| `python` | Python 3.10+ (fails below 3.10) |
| `system` | lifetxt version, full Python version, and OS/platform (informational) |
| `update` | Only with `--check-update`: whether a newer GitHub release/tag exists (warns if so, or if the check itself fails) |
| `life.txt` | The configured or default life.txt file exists and is readable |
| `config` | `.lifetxt.json` (or `--config` path) exists (warns if missing) |
| `disk` | Free space on the volume holding the life.txt file (warns below 100 MiB) |
| `fzf`, `peco` | Optional selector tools found in `PATH` (warns if missing) |
| `fastapi`, `uvicorn`, `httpx2`, `textual`, `watchdog`, `jsonschema`, `matplotlib`, `cryptography` | Optional Python packages installed (warns if missing); the same set `doctor --workspace-safety` checks |
| `check` | Parses the life.txt file(s) and reports error/warning counts |
| `ids` | Reports items missing an `id:` detail |

`doctor` exits non-zero only when a `FAIL`-level check fails (Python version
too old, or the file is missing/unreadable); missing optional dependencies
are `WARN` and do not affect the exit code. Use `--format json` for
machine-readable output.

Pass `--check-update` to add an `update` row reusing `update-check`'s own
logic (see below) -- off by default, so plain `doctor` never requires
network access:

```sh
python -m lifetxt doctor --check-update
python -m lifetxt doctor --check-update --repo your-github-username/your-fork
```

A newer release/tag being available reports `WARN`, matching the missing-
optional-dependency checks -- it never fails `doctor`'s exit code. A network
or API failure while checking also reports `WARN` (`Could not check for
updates: ...`) rather than failing `doctor` outright; `--update-timeout
SECONDS` (default `5`) bounds how long that check can take.

`update-check` compares the running version against the latest published
GitHub Release for a repository, falling back to the latest tag when no
Release has been published. The default repository is this project's own
(`Eruhitsuji/lifetxt`); a fork should set `update.repository` (see
[config.md](config.md#update-checks)) or pass `--repo` so checks compare
against the fork's own releases instead of upstream:

```sh
python -m lifetxt update-check
python -m lifetxt update-check --format json
python -m lifetxt update-check --repo your-github-username/your-fork
```

It makes a read-only request to the public GitHub API and never installs or
modifies anything. Reported `status` values: `up_to_date`, `update_available`,
`ahead_of_latest` (running newer than the latest published version),
`no_release_found` (the repository has no Releases or tags yet), and
`unparseable` (a release/tag name that could not be read as a version). Use
`--timeout SECONDS` to change the network timeout (default `10`).

`update` fast-forwards the running install's own git checkout -- lifetxt has
no PyPI distribution, so updating means git, and it **only ever works when
lifetxt was installed editable from a git clone** (`python -m pip install -e
.`; see [readme.md's Development environment section](../../readme.md#development-environment)).
A plain, non-editable `pip install .` (the default getting-started install;
see [readme.md](../../readme.md)) has no git checkout backing it, so `update`
cannot apply there -- reinstall from a newer checkout or artifact instead. It
is dry-run by default:

```sh
python -m lifetxt update
python -m lifetxt update --yes
python -m lifetxt update --ref main --yes
python -m lifetxt update --repo your-github-username/your-fork --yes
```

Without `--yes`, `update` fetches (read-only against your git remote) and
reports what *would* change -- current commit, target commit, the ref it
resolved to, and (in text output) up to 20 pending commits one-line-each,
newest first, with a count of any remaining ones -- without touching your
working tree. `--yes` is required to actually apply it. `--format json`
includes the same preview as a `commits` array and a `commit_count`
integer. Looking up the commit list never blocks the update itself: if it
fails for any reason, `update` still reports the pending fast-forward with
an empty commit list rather than erroring out. Safety rails, all fail
loudly rather than guessing:

- Refuses when the running install is not inside a git working tree.
- Refuses when the working tree has any uncommitted change, tracked or
  untracked (`git status --porcelain` must be empty) -- commit, stash, or
  discard first.
- Refuses when `HEAD` is detached -- check out a branch first.
- Only ever runs `git fetch` and `git merge --ff-only`. Never resets,
  rebases, force-pushes, or rewrites history; a non-fast-forward situation
  is refused, not forced.
- Never runs `pip install` or any other build step afterward. If the update
  changed dependencies, re-run `pip install -e .` (or your usual extras)
  yourself -- `update` tells you to when it applies a change.

Without `--ref`, `update` resolves the target the same way `update-check`
does (latest published Release, or tag; `--repo`/`update.repository`
override which repository that lookup queries). The actual `git fetch`
always goes through your existing local git remote (`origin` by default,
or `--remote NAME`) -- `--repo` only chooses which ref *name* to ask for,
never which URL is fetched from.

### 16.1 `help`

Progressive-disclosure, goal-based, and machine-readable help, distinct from
`tour` (an experiential walkthrough of a sample workspace) and from
`--help` (the exhaustive flag reference). `help` answers "what should I run"
rather than "what flags does X take":

```sh
python -m lifetxt help
python -m lifetxt help beginner
python -m lifetxt help daily
python -m lifetxt help power
python -m lifetxt help ai
python -m lifetxt help admin
python -m lifetxt help add
python -m lifetxt help add --json
```

| Form | Shows |
|---|---|
| `help` (no argument) | The "Start here" quick loop, every guided-path audience, and the category index from [§1.1](#11-command-categories-and-guided-paths) |
| `help beginner\|daily\|power\|ai\|admin` | That audience's short, ordered command flow with one copyable example per step |
| `help NAME` | One command's category, aliases, a copyable example, related commands, and whether it is read-only or destructive; `NAME` may be an alias (`add`, `q`, `d`, `s`, `a`, `f`) |
| `help diagnostic` | A compact, one-line-per-code overview of every diagnostic code this catalog documents |
| `help diagnostic CODE` | One diagnostic code's category, severity, meaning, remediation, and a valid/invalid example, e.g. `help diagnostic E003` |
| `--json` (or `--format json`) | The same information as structured JSON instead of text -- `lifetxt-help-catalog-v1` for the bare form, `lifetxt-help-audience-v1` for an audience, `lifetxt-help-command-v1` (with `arguments`/`options`/`examples` added) for one command, `lifetxt-diagnostic-catalog-v1` for `diagnostic` with no code, `lifetxt-diagnostic-explain-v1` for `diagnostic CODE` |
| `-o`, `--output FILE` | Write to a file instead of stdout |

`help` never reads life.txt, configuration, or any workspace: its output is
static per lifetxt version, so it is safe to call from a script or an AI
client with no data access. `read_only`/`destructive` in its JSON output are
a best-effort classification for guidance, not an enforced permission
boundary -- MCP's `--profile read|assist|full` (see
[ai-integration.md](ai-integration.md)) is the actual enforcement mechanism
for untrusted AI clients. An unrecognized command name or audience fails
loudly (exit 1) naming the known audiences rather than guessing.

`help diagnostic CODE` documents a bounded, explicitly curated subset of
stable diagnostic codes -- the ones a Beginner Profile user is most likely to
hit (`E001`-`E005`, `E010`, `W101`-`W103`, `W106`, `W207`, `W213`, `W225`) --
not every code in the system. `code`, `category`, and `severity` are the same
locale-independent machine identity `check --format json` already publishes
(see [§3](#3-check)); only the human-facing `summary` text is localized
today. `remediation` reuses the same text as the diagnostic's own `hint`
field where one already exists, so it stays English-only for the same
diagnostics that field is English-only for. An unknown code fails loudly
(exit 1) naming the documented codes rather than guessing the closest match.

## 17. `encrypt` and `decrypt`

Current behavior: `encrypt` defaults to `--algorithm xsk`, which stores values
as `enc:XSK:BASE64` and requires no extra package. If `cryptography` is
installed, `encrypt --algorithm aesgcm` stores values as `enc:GCM:BASE64`
using AES-GCM. `decrypt` defaults to `--algorithm auto` and dispatches from the
stored `enc:` tag, so one file can contain both algorithms during migration.

```sh
LIFETXT_KEY="correct horse battery staple" python -m lifetxt encrypt life.txt --field body --type J --algorithm aesgcm
LIFETXT_KEY="correct horse battery staple" python -m lifetxt decrypt life.txt --field body --algorithm auto
```

Field-level encryption for sensitive values such as journal bodies and message
text. XSK needs no extra dependency; AES-GCM needs the optional
`cryptography` package.

```sh
LIFETXT_KEY="correct horse battery staple" python -m lifetxt encrypt life.txt --field body --type J
LIFETXT_KEY="correct horse battery staple" python -m lifetxt decrypt life.txt --field body
```

**Algorithm.** Values are tagged `enc:XSK:BASE64` in place, e.g.
`body:"enc:XSK:AbCd..."`. XSK ("XOR stream cipher, keyed") derives a 32-byte
key from the passphrase with PBKDF2-HMAC-SHA256 (100,000 iterations) and a
random 16-byte salt per value, expands it into a keystream with repeated
SHA-256 (`SHA256(key ‖ counter)`), and XORs it against the UTF-8 plaintext.
An HMAC-SHA256 over `salt ‖ ciphertext`, keyed with the same derived key, is
prepended for integrity — `decrypt` refuses to decode a value whose MAC does
not match ("wrong passphrase or tampered data"), so passphrase typos fail
loudly instead of producing garbled text. This is a from-scratch construction
built only from `hashlib`/`hmac`/`secrets`; it is adequate for keeping
casual/local-file secrets out of plain sight (e.g. a private journal in a
repo you otherwise trust), but it has not been audited and is not a
substitute for a reviewed cryptographic library.

AES-GCM uses `cryptography.hazmat.primitives.ciphers.aead.AESGCM`, a random
16-byte salt, a random 12-byte nonce, and PBKDF2-HMAC-SHA256 with 200,000
iterations. It is the recommended choice for new encrypted content when adding
the optional dependency is acceptable.

**Passphrase strength.** Since the key is derived entirely from the
passphrase, passphrase strength is the only thing protecting the data.
Use a long, unique passphrase (a multi-word passphrase, or output from a
password manager) — not a word from a dictionary. Never commit the
passphrase itself to the repository.

**Key management.**

| Method | Flag | Notes |
|---|---|---|
| Environment variable | `--key-env NAME` (default `LIFETXT_KEY`) | Convenient for local shells and CI secrets; avoid printing the shell history |
| Key file | `--key-file PATH` | Overrides `--key-env`. Store the file outside the repo, or add it to `.gitignore` |

**Rotation workflow.** To rotate a passphrase: `decrypt` every affected file
with the old passphrase, then `encrypt` again with the new passphrase before
discarding the old one. There is no in-place re-key operation, so both
passphrases must be available during the rotation window.

**Checking a partially encrypted file.** `check` and `filter` treat
`enc:XSK:...` and `enc:GCM:...` values as opaque strings — they do not attempt to decrypt them,
so syntax validation and filtering by other fields work normally on a file
that mixes encrypted and plaintext values. Filtering *by* an encrypted
field's plaintext content is not possible without decrypting first.

**Upgrade path.** Existing `enc:XSK:` values remain readable. To move a file
to AES-GCM, decrypt it with the current passphrase and then encrypt the target
fields again with `--algorithm aesgcm`. `doctor` reports whether
`cryptography` is installed.

## 18. `share`, `digest`, and `template`

### `share`

Export a self-contained HTML or Markdown report — filtered items, a bar
chart, and a table — without running the server.

```sh
python -m lifetxt share life.txt --open --type task -o open_tasks.html
python -m lifetxt share life.txt --week --format markdown -o weekly.md
python -m lifetxt share life.txt --project research --title "Research report"
```

`share` accepts the same filter options as `filter`/`agenda` (see section 2),
plus:

| Option | Meaning |
|---|---|
| `--week` | Label the report with the current ISO week (Monday to today) |
| `--month YYYY-MM` | Label the report with a specific calendar month |
| `--format html\|markdown` | Output format. Defaults to `html` |
| `-o, --output PATH` | Output file. Defaults to `share.html` or `share.md` |
| `--title TEXT` | Report title. Defaults to "lifetxt share report" |

`--week`/`--month` only set the label shown at the top of the report; combine
them with `--after`/`--before` if you also want to restrict which items are
included by date. The HTML output has no external dependencies (inline CSS,
inline SVG chart) and can be opened directly in a browser or attached to an
email.

### `digest`

Deliver a `review`-style period summary to Slack, email, or a local file.

```sh
python -m lifetxt digest life.txt --week --format slack-webhook --url-env SLACK_WEBHOOK_URL
python -m lifetxt digest life.txt --month 2026-06 --format email --to team@example.com
python -m lifetxt digest life.txt --week --format file --path digest-log.md
```

| Option | Meaning |
|---|---|
| `--week` / `--month YYYY-MM` | Same period selection as `review` |
| `--project NAME` | Restrict to a specific project |
| `--format slack-webhook\|email\|file` | Delivery channel (required) |
| `--url-env ENVVAR` | Env var with the Slack incoming webhook URL (`slack-webhook`) |
| `--to ADDRESS` | Recipient email address (`email`) |
| `--smtp-host-env`, `--smtp-user-env`, `--smtp-pass-env` | Env vars with SMTP host/username/password (`email`); default to `LIFETXT_SMTP_HOST`/`_USER`/`_PASS` |
| `--smtp-port PORT` | Explicit SMTP port (`email`), e.g. `587` for STARTTLS; omitting it preserves the existing default port |
| `--path PATH` | Local file to append Markdown to (`file`) |
| `--report NAME` | Use a configured `lifetxt report` profile as the message source instead of the built-in review summary (`--week`/`--month`/`--project` are ignored) |
| `--date YYYY-MM-DD` | With `--report`: generate the period containing this date instead of today |
| `--previous` | With `--report`: generate the immediately completed previous period |
| `--dry-run` | Build the message and print it without making a network request or writing |

Each channel validates its required environment variables (or `--to`/`--path`)
**before** making any network request or writing any file, so a missing
secret fails fast with a clear error rather than partway through delivery. An
explicit `--smtp-port` is likewise validated (an integer from 1 to 65535)
before any connection is attempted, regardless of `--dry-run`.
See [reports.md](reports.md) for `lifetxt report
list|preview|run|send|validate|inspect` and the full Report v2 `sections`/
`format`/`audience`/`compare`/`scope`/`email` contract.

### `template`

List and apply reusable named item templates stored in config `templates`.

```sh
python -m lifetxt template list
python -m lifetxt template apply weekly_review --append life.txt
python -m lifetxt template apply weekly_review --append life.txt --dry-run
```

Define templates in `.lifetxt.json`:

```json
{
  "templates": {
    "weekly_review": {
      "lines": [
        "[ ] T Weekly_Review due:{next_monday} project:reflection",
        "[ ] T Plan_Next_Week due:{next_monday} project:reflection"
      ]
    }
  }
}
```

Date placeholders are resolved when the template is applied (not when it is
defined): `{today}`, `{next_monday}` (the next strictly-future Monday), and
`{next_week}` (today + 7 days). Unlike `H` habits, a template's content is
not re-scheduled automatically — running `apply` again appends another copy
of the same lines with freshly resolved dates.

## 19. Development Tickets (`ticket`)

`ticket` manages development tickets stored as normal Task records with
`record:ticket` metadata (no new item type). It has one of the larger
subcommand surfaces in the CLI; full behavior, field/workflow configuration,
custom fields, versions, sprints, and planning views are documented in
[tickets.md](tickets.md), [ticket-projects.md](ticket-projects.md), and
[query.md](query.md#saved-views) (saved views also cover ticket queries).

```sh
python -m lifetxt ticket new WEB-1 "Fix login redirect" --project web --tracker bug
python -m lifetxt ticket list --project web --status open
python -m lifetxt ticket show WEB-1
python -m lifetxt ticket transition WEB-1 review --comment "Ready for review"
python -m lifetxt ticket comment WEB-1 "Root cause confirmed"
python -m lifetxt ticket log-time WEB-1 90m --activity development
```

| Subcommand group | Purpose |
|---|---|
| `new`, `list`, `show`, `edit`, `assign`, `close`, `reopen` | Create and maintain ticket records |
| `link`, `unlink` | Add or remove relations (`depends_on:`, `blocks:`, `related:`, `duplicate_of:`, `replaced_by:`, ...) |
| `validate`, `validate-history`, `validate-planning` | Consistency checks for tickets, append-only history, and planning data |
| `transition`, `comment`, `reassign`, `change`, `watch`, `unwatch`, `log-time` | Audit-safe mutations that append a `record:ticket_event`/`record:time_entry` alongside the state change |
| `activity`, `time` | Show ticket events, time entries, and authoritative append-only time |
| `revision`, `file-revision` | Print exact source-file/writable-file revisions for conflict-aware writes |
| `fields`, `workflow` | Inspect the effective custom-field registry and workflow configuration |
| `summary`, `board`, `attention` | Shared ticket/project reports (also reachable via `project tickets`) |
| `plan`, `backlog`, `roadmap` | Version/sprint membership and planning views |

Ticket release versions and sprints are managed with the sibling `version`
and `sprint` commands (`version new|list|show|close|release|lock|reopen`,
`sprint new|list|show|start|close|reopen`); see
[tickets.md](tickets.md#versions-sprints-backlog-and-roadmap).

## 20. Remote Safe Mode Client (`remote`)

`remote` is a dependency-free CLI client for a server running `lifetxt serve`
with Remote Safe Mode enabled (`remote.enabled: true` in that server's
config). It talks to the server's HTTP API using a stored profile (URL, TLS
preference, protocol version, and the *name* of an environment variable that
holds the Bearer token — never the token value itself). Full protocol,
permission-model, and conflict-handling detail lives in
[remote.md](remote.md) and [remote-client-writes.md](remote-client-writes.md);
this section is a command-surface summary.

```sh
python -m lifetxt remote profile-set home https://life.example.test --token-env LIFETXT_REMOTE_TOKEN
python -m lifetxt remote profile-list
python -m lifetxt remote test home
python -m lifetxt remote resources home
python -m lifetxt remote get home tickets --param project=web --param status=review
python -m lifetxt remote ticket-show home WEB-42
python -m lifetxt remote permissions home
python -m lifetxt remote diagnose home
python -m lifetxt remote snapshot home
python -m lifetxt remote export home snapshot.json
```

| Subcommand | Purpose |
|---|---|
| `profile-set`, `profile-list`, `profile-show`, `profile-delete` (alias `profile-remove`) | Manage locally stored connection profiles |
| `test` | Verify connectivity and report the negotiated protocol version and principal |
| `resources` | List the read resources the server publishes for the negotiated protocol |
| `get RESOURCE --param k=v` | Fetch one resource (`tickets`, `items`, `next`, `agenda`, `search`, `status`, `links`, `projects`, `ticket-detail`, `ticket-report`, ...), filtered by `--param` |
| `ticket-show` | Show one visible ticket from the permission-filtered snapshot |
| `permissions` | Show the authenticated principal's effective role, scopes, and denial reasons |
| `diagnose` | Report server-side Remote Safe Mode health checks (enablement, HTTPS policy, principal registry, session store, ...) |
| `snapshot` | Fetch the full permission-filtered data snapshot |
| `export PATH` | Write a `remote-snapshot-v1`-shaped snapshot to a local file |
| `ticket-create`, `ticket-edit`, `ticket-transition`, `ticket-comment`, `ticket-log-time` | Ticket mutations, gated by `remote.ticket_writes_enabled` and an exact `If-Match` revision (`--dry-run` available on each) |
| `tui PROFILE [--interactive]` | A minimal text-mode client: read-only browsing by default, or an interactive session that can propose and confirm writes |

All subcommands accept `--profiles-file PATH` to use a profiles store other
than the default. Mutation subcommands additionally accept
`--transaction-id ID` and `--dry-run`; see
[remote-client-writes.md](remote-client-writes.md#revision-conflicts) for how
revision conflicts are reported.

## 21. Commands Documented Elsewhere

A few command families are intentionally documented in their own file rather
than duplicated here, because they are large enough (or specific enough) to
warrant a dedicated guide:

| Commands | Guide |
|---|---|
| `next`, `show`, `edit`, `path`, `count`, `invoice`, `standup`, `to-ics`, `from-todo` | [new-cli-workflows.md](new-cli-workflows.md) |
| `safety locks\|serve-target\|timezone\|revisions\|transactions\|write-routes\|release-gate`, `attachment put\|reference\|delete\|status`, `format info\|check\|canon\|schemas`, `capabilities` | [release-safety-foundations.md](release-safety-foundations.md) |
| `workspace` (in depth), named-workspace configuration | [config.md](config.md#named-workspaces) |
| `project`, `portfolio`, `project archive`, `project tickets` | [projects.md](projects.md), [ticket-projects.md](ticket-projects.md) |
| `query`, `view` (saved queries) | [query.md](query.md) |
| `person`, `message`, `group` | [people.md](people.md), [messaging.md](messaging.md) |
| `proposal` (Unified Inbox) | [inbox.md](inbox.md) |
| `today`, `area`, `backlinks`, `temporal`, `freebusy` | [life-hub.md](life-hub.md) |
| `ticket`, `version`, `sprint` | [§19](#19-development-tickets-ticket), [tickets.md](tickets.md) |
| `remote` | [§20](#20-remote-safe-mode-client-remote), [remote.md](remote.md), [remote-client-writes.md](remote-client-writes.md) |
| `vm` (opt-in Turing-complete VM) | [vm.md](vm.md) |
| `report list\|preview\|run\|send\|validate\|inspect` (named periodic reports) | [reports.md](reports.md) |
| `server-report plan\|install\|remove` (scheduled report jobs) | [§24](#24-server-report), [reports.md](reports.md) |
| `context`, `memory`, `decisions` (Personal Context) | [personal-context-toolkit.md](personal-context-toolkit.md) |

`python -m lifetxt --help` lists every command; each subcommand's own
`--help` is always authoritative for its exact flags.

## 22. `server-init`

Plan-first bootstrap for a reference Ubuntu Server production deployment. See
[docs/deployment/ubuntu-server.md](../deployment/ubuntu-server.md) for the
manual runbook this command automates into a reviewable plan.

```sh
python -m lifetxt server-init --server-config server-init.json
python -m lifetxt server-init --server-config server-init.json --yes
```

| Option | Meaning |
|---|---|
| `--server-config PATH` | Required. Bootstrap config JSON file -- distinct from the global `--config` application config.json. |
| `--yes` | Apply the plan. Without this, `server-init` only reports what would be created, left unchanged, or validated. |
| `--format text\|json` | Output format. |

Dry-run is the default. The command resolves the deployment into explicit
directory, file, command, and health-check steps. A real run creates only
missing matching artifacts, treats byte-identical existing artifacts as no-op,
and refuses differing existing files rather than overwriting production data,
systemd units, sudoers files, or reverse-proxy configuration.

The bootstrap config must name the source and data roots explicitly:

```json
{
  "install_root": "/opt/lifetxt/src",
  "data_root": "/srv/lifetxt",
  "python": "/opt/lifetxt/venv/bin/python",
  "installer": "uv",
  "uv_executable": "/home/lifetxt/.local/bin/uv",
  "extras": ["web", "tui"],
  "service_user": "lifetxt",
  "service_group": "lifetxt",
  "systemd": {
    "enabled": true,
    "unit_dir": "/etc/systemd/system",
    "daemon_reload": false,
    "enable": false,
    "start": false
  },
  "service_control": {
    "enabled": true,
    "wrapper_path": "/usr/local/sbin/lifetxt-systemctl",
    "sudoers_path": "/etc/sudoers.d/lifetxt-server-update"
  },
  "reverse_proxy": {
    "backend": "nginx",
    "nginx_config_path": "/etc/nginx/sites-available/lifetxt.conf"
  }
}
```

Important boundaries:

- `web.bind` must remain `127.0.0.1`; generated systemd and nginx artifacts keep
  `lifetxt serve` behind loopback.
- `service_user` and `service_group` are required when systemd artifacts are
  generated; the command does not assume a username.
- `service_control.enabled` generates a narrow wrapper/sudoers artifact for
  `is-active`, `stop`, and `start` on the configured lifetxt units only.
- Installer, validation, and service commands are structured argv arrays. The
  command does not add a shell-string escape hatch.
- Calendar URLs, Basic Auth credentials, real hostnames, VPN details, and other
  secrets must stay outside repository-tracked files. Generated nginx output
  keeps placeholder host/certificate values.

The generated `server-update.json` matches the selected installer (`pip`,
`uv`, or `conda-pip`), source/data layout, service wrapper, integrity checks,
backup directory, update lock, and health URL so future
[`server-update`](#23-server-update) runs start from the same deployment
contract.

## 23. `server-update`

Guarded production update for a systemd-managed install, wrapping
`update`'s git fast-forward logic (see [§16](#16-tour-init-and-doctor)) with
backup, service stop/start, dependency reinstall, and verification. See
[docs/deployment/ubuntu-server.md](../deployment/ubuntu-server.md) for the
full operator-facing runbook this command is designed for.

```sh
python -m lifetxt server-update --server-config /etc/lifetxt/server-update.json
python -m lifetxt server-update --server-config /etc/lifetxt/server-update.json --yes
```

| Option | Meaning |
|---|---|
| `--server-config PATH` | Required. Deployment config JSON file -- distinct from the global `--config` application config.json. |
| `--yes` | Actually apply the update. Without this, `server-update` only fetches and reports what would happen. |
| `--approve SHA` | Apply an update the review gate flagged as high-impact (see below), bound to the exact resolved target commit. Implies `--yes`. |
| `--format text\|json` | Output format. |

`--server-config` points at a JSON file naming the target Python
environment and the deployment's paths/services, not any life.txt content:

| Key | Meaning |
|---|---|
| `python` | Required. Path to the target environment's `python` executable (reinstall, sanity check, and integrity checks all run through it). |
| `remote`, `branch`, `ref`, `repo` | Same meaning as `update`'s `--remote`/`--ref`/`--repo`; `branch` additionally refuses the run if the current branch does not match. |
| `life_txt_path` | Primary life.txt path passed to the `check`/`ids`/`ticket validate-history` integrity checks. |
| `backup_paths` | Files backed up (and hashed before/after the code update) -- typically the primary, config, and archive files. |
| `backup_dir` | Directory timestamped backups are written under. Omitting it disables this command's own backup step; hash verification still runs. |
| `lock_path` | Single-update lock file. Omitting it disables locking. |
| `services` | systemd unit names to stop before updating and restart afterward. Only units already `active` are touched -- a unit you left stopped stays stopped. |
| `service_manager` | `"systemctl"` (default) or `"none"` (no service management; useful for a non-systemd or manually-managed install). |
| `service_command` | Structured argv prefix used for service actions. Defaults to `["systemctl"]`; a least-privilege wrapper can be named here instead of running the whole updater as root. |
| `service_preflight_commands` | Optional structured argv commands run before lock/backup/service/code mutation. Use this to fail early when sudo/Polkit authorization is missing. |
| `application_config` | Optional application `.lifetxt.json` passed as global `--config` to integrity checks. |
| `workspace` | Optional named workspace used by `workspace_validate`. |
| `integrity_checks` | Subset of `["check", "workspace_validate", "ids", "ticket_validate_history"]`, or objects with `name`, optional `path`, `application_config`, `workspace`, and `id`. |
| `health_url` | `/api/health` URL checked after services restart. Omit to skip. |
| `installer` | `"pip"` (default), `"uv"`, or `"conda-pip"`. |
| `pip_install_args` | Arguments appended to `<python> -m pip install`. Defaults to `["-e", "."]`. |
| `uv_executable`, `uv_install_args` | `uv` backend settings. The command is `<uv_executable> pip install --python <python> <uv_install_args...>`, so the venv does not need pip installed. |
| `conda_executable`, `conda_env_name`, `conda_env_prefix`, `conda_install_args` | conda backend settings. The command is `<conda_executable> run --name NAME python -m pip install ...` or `--prefix PREFIX`; set exactly one of name/prefix. |
| `validation_commands` | Optional structured argv commands run after reinstall/sanity/import/integrity validation and before services restart. Disabled by default. Each entry may be an argv array or an object with `name`, `argv`, optional `cwd`, and optional `timeout`. |
| `health_timeout`, `git_timeout`, `service_timeout` | Per-category subprocess/network timeouts in seconds. |
| `health_ready_timeout` | Total readiness deadline, in seconds, for post-restart health retries. Defaults to `10`. |
| `health_retry_interval` | Delay, in seconds, between failed health attempts during the readiness window. Defaults to `0.5`. |

Example with a pip-less `uv`-managed venv, separate primary/archive
life.txt targets, and an explicit application config/workspace:

```json
{
  "install_root": "/opt/lifetxt/src",
  "python": "/opt/lifetxt/venv/bin/python",
  "installer": "uv",
  "uv_executable": "uv",
  "uv_install_args": ["-e", "/opt/lifetxt/src[web,tui,dev]"],
  "application_config": "/srv/lifetxt/.lifetxt.json",
  "workspace": "production",
  "life_txt_path": "/srv/lifetxt/life.txt",
  "backup_paths": [
    "/srv/lifetxt/life.txt",
    "/srv/lifetxt/archive/life.txt",
    "/srv/lifetxt/.lifetxt.json"
  ],
  "backup_dir": "/srv/lifetxt/backups/server-update",
  "lock_path": "/srv/lifetxt/.locks/server-update.lock",
  "services": ["lifetxt.service", "lifetxt-sync-ics.timer"],
  "service_command": ["sudo", "-n", "/usr/local/sbin/lifetxt-systemctl"],
  "service_preflight_commands": [
    ["sudo", "-n", "-l", "/usr/local/sbin/lifetxt-systemctl"]
  ],
  "integrity_checks": [
    {"name": "workspace_validate"},
    {"name": "check", "path": "/srv/lifetxt/life.txt"},
    {"name": "ids", "path": "/srv/lifetxt/life.txt"},
    {
      "id": "archive_history",
      "name": "ticket_validate_history",
      "path": "/srv/lifetxt/archive/life.txt"
    }
  ],
  "validation_commands": [
    {
      "name": "unit_suite",
      "argv": ["/opt/lifetxt/venv/bin/python", "-m", "unittest", "discover"],
      "cwd": "/opt/lifetxt/src",
      "timeout": 900
    }
  ],
  "health_url": "http://127.0.0.1:8765/api/health",
  "health_ready_timeout": 10,
  "health_retry_interval": 0.5
}
```

Example for a conda-managed environment:

```json
{
  "install_root": "/opt/lifetxt/src",
  "installer": "conda-pip",
  "conda_executable": "conda",
  "conda_env_prefix": "/opt/conda/envs/lifetxt-prod",
  "conda_install_args": ["-e", "/opt/lifetxt/src[web,tui,dev]"],
  "integrity_checks": [
    {"name": "check", "path": "/srv/lifetxt/life.txt"}
  ]
}
```

`conda-pip` deliberately uses `conda run ... python -m pip install` so setup,
the sanity import, and built-in integrity checks all run in the selected conda
environment. The target environment must contain `pip`; follow conda's normal
practice of installing conda packages first and using pip as the last
environment-building step.

Without `--yes`, `server-update` fetches and reports the pending update
(same preview shape as `update`) without touching anything. With `--yes`:

1. Acquires the configured lock (refuses if another `server-update` is
   already running).
2. Runs configured `service_preflight_commands`, if any.
3. Backs up `backup_paths` into a fresh timestamped directory under
   `backup_dir` and hashes them.
4. Stops whichever configured `services` are currently active.
5. Fast-forwards to the exact commit already resolved during the dry-run
   preview -- no second, unreviewed fetch.
6. Reinstalls the package with the selected installer (`pip`, `uv`, or
   `conda-pip`) and runs a sanity `import lifetxt` check.
7. Re-hashes `backup_paths` and refuses to continue if anything changed
   during the code update.
8. Runs the configured `integrity_checks`.
9. Runs optional `validation_commands`.
10. Restarts the services it stopped and checks `health_url`.

The health check is readiness-aware. After services restart successfully,
`server-update` sends one health request immediately. If the endpoint is
not listening yet, returns a transient connection error, times out, or
returns an unhealthy HTTP response, `server-update` waits
`health_retry_interval` seconds and tries again until
`health_ready_timeout` expires. The first healthy response ends the wait
and the update reports `updated`. If the deadline expires, the update still
reports `validated_health_check_failed`. The `health_check` report includes
attempt count, elapsed seconds, timing settings, and the final status or
error. Dry-run output includes the health URL and readiness timing that
would apply during the mutating run.

Failure behavior:

- A failure before the code update (steps 1-4) restores whatever service
  state existed before the attempt and releases the lock.
- A failure after the code update but before validation completes (steps
  5-9) leaves services **stopped** rather than restarting unvalidated code.
  The report names the exact backup directory and pre-update commit for
  manual recovery.
- A validated, applied update whose service restart or health check itself
  fails is reported as a distinct status (`validated_restart_incomplete` /
  `validated_health_check_failed`) rather than silently claiming full
  success -- both still exit non-zero.

### 23.1 High-impact review gate

Before touching backup, services, or code, `server-update` classifies how
risky the pending update looks. If nothing about it looks high-impact,
`--yes` proceeds straight into the flow above with no operator
interaction. If it does, `--yes` alone stops before any mutation and
prints a paste-friendly review block instead:

```text
===== LIFETXT_UPDATE_REVIEW_BEGIN =====
status=REVIEW_REQUIRED
current=<sha>
target=<sha>
commit_count=<n>
changed_file_count=<n>
changed_line_count=<n>
binary_file_count=<n>
--- reasons ---
...
--- commits ---
...
--- changed files ---
...
--- diff stat ---
...
--- execution plan ---
installer=<pip-or-uv-or-conda-pip>
install_command=<structured argv rendered for review>
service_command=<structured argv rendered for review>
approved_command=lifetxt server-update --server-config <path> --approve <exact-target-sha>
===== LIFETXT_UPDATE_REVIEW_END =====
```

Copy the `approved_command` line verbatim (or otherwise pass `--approve
<sha>`, which implies `--yes`) to apply that exact, already-reviewed
commit. `--approve` is checked against the freshly-resolved target every
time: if the upstream target moved since the block was generated,
`server-update` refuses with a clear error rather than silently
re-reviewing against the new commit -- get a fresh review instead.

A review is required when the update between the current and target
commit:

- touches parser/model/serializer/validator code, config or workspace
  resolution, atomic-write/mutation/transaction/archive-safety code,
  schema or migration files (including the generated `dist/schemas/`
  bundle), Remote Safe Mode (`remote_*` modules), calendar/ICS sync
  (`ics.py`), or the `contrib/systemd/`/`contrib/nginx/` deployment files
  themselves;
- deletes any tracked file; or
- has a commit message containing "breaking", "security", or "migration"
  (case-insensitive).

`changed_file_count`/`changed_line_count`/`binary_file_count` are always
reported (even outside a triggered review, in the dry-run preview) as an
additional signal -- a large diff is not by itself a trigger, and a bulk
regeneration of `dist/schemas/` does not inflate `changed_line_count` (it
is still flagged via the schema/migration category above). These trigger
categories are fixed; they are not configurable through `--server-config`,
so no flag other than exact-SHA `--approve` can bypass one.

## 24. `server-report`

Install or remove one systemd oneshot+timer pair for a report profile on an
already-running deployment, without re-running `server-init`. See
[docs/deployment/ubuntu-server.md §10](../deployment/ubuntu-server.md#10-scheduled-reports)
for the full runbook, and [reports.md](reports.md) for `server-init`'s own
opt-in `reporting` section (the equivalent bootstrap-time path for a new or
fully regenerated deployment).

```sh
python -m lifetxt server-report plan weekly --app-config /srv/lifetxt/.lifetxt.json --service-user lifetxt --service-group lifetxt
python -m lifetxt server-report install weekly --app-config /srv/lifetxt/.lifetxt.json --service-user lifetxt --service-group lifetxt --yes --enable --start
python -m lifetxt server-report remove weekly --app-config /srv/lifetxt/.lifetxt.json --yes
```

| Option | Meaning |
|---|---|
| `--app-config PATH` | Required. The application `.lifetxt.json` containing the report profile -- deliberately not `--config`, which the global `--config` flag would silently strip before this command ever saw it. |
| `--service-user`, `--service-group` | Required for `plan`/`install`. The systemd unit's `User=`/`Group=`. |
| `--data-root PATH` | Deployment data root. Defaults to the directory containing `--app-config`. |
| `--unit-dir PATH` | Directory to read/write unit files. Defaults to `<data-root>/systemd`. |
| `--python PATH` | Target Python interpreter. Defaults to a bare `lifetxt` on `PATH`. |
| `--at HH:MM` | 24-hour time the job's timer fires at, relative to the profile's own period boundary. Default `00:10`. |
| `--send-email` | For `plan`/`install`: also run `report send <profile> --previous` as a second `ExecStart=` line after `report run` succeeds. Requires `--environment-file` and a profile with a valid `email` section. |
| `--environment-file PATH` | Absolute path to a systemd `EnvironmentFile=` holding SMTP credential environment variables. Only the path is ever written into generated unit text or plan output -- never its contents. Required with `--send-email`; rejected without it. |
| `--service-command ARGV...` | Command prefix used to enable/disable/start the timer. Default `systemctl`. |
| `--yes` | Actually write (`install`) or delete (`remove`) the unit files. Without this, both subcommands only report what would happen. |
| `--enable` | With `install --yes`: also run `systemctl enable` on the timer. |
| `--start` | With `install --yes`: also run `systemctl enable --now` (implies `--enable`). |
| `--format text\|json` | Output format. |

`NAME` must already exist in `--app-config`'s `reports` section and pass the
real Report v2 profile validator; `server-report` never creates or edits a
report profile. `install` refuses to write over a conflicting existing unit
file (matching `server-init`'s own conflict policy). `remove` best-effort
disables/stops the timer via `systemctl` (tolerating `systemctl` being
unavailable or the unit never having been enabled), then deletes only unit
files that still contain the generator's own marker comment, refusing to
delete an unrelated same-named file.

`--send-email`'s second `ExecStart=` line only ever runs after the first
(`report run`) succeeds, since systemd runs a oneshot unit's `ExecStart=`
lines in order and fails the whole service if one fails -- a failed or
partial report is never emailed. See
[docs/deployment/ubuntu-server.md's Scheduled email delivery
section](../deployment/ubuntu-server.md#scheduled-email-delivery) for the
full walkthrough, including creating the `EnvironmentFile=` and testing
delivery by hand first.
