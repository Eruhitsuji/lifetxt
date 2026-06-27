# lifetxt TODO / Roadmap

Last updated: 2026-06-27 (updated x15)

This roadmap tracks remaining work after the current prototype updates.
Completed prototype-only items are removed; items below are implementation,
validation, documentation, or design work that still matters.

Priority guide:

- `P0`: Stabilize features that are already implemented and likely to break in real use.
- `P1`: Implement or refine core features that affect the format, CLI, API, or daily workflow.
- `P2`: Improve usability, documentation, packaging, and long-term maintainability.
- `Deferred`: Useful ideas that should not block the next practical release.

---

## P0: Stabilization

Items in this section are already implemented but have not been verified in
real environments. Each item must be tested manually before the next release.

- [ ] Verify `tui` in real terminals across WSL, Windows Terminal, and native
  macOS/Linux: confirm Vim-like keymap, curses colors, auto-reload, and
  behavior when `textual` or `watchdog` is not installed (graceful fallback).

- [ ] Verify `lifetxt fzf` with actual `fzf` and `peco` on both Windows
  PowerShell and Unix-like shells: confirm preview command quoting, `done` and
  `delete` actions, and `edit` with `$EDITOR`.

- [ ] Verify `timer start/pause/resume/status/stop/cancel` with a real state
  file path on all supported platforms: confirm `elapsed:` is written correctly
  in compact form (`25m`, `1h30m`) and that pause/resume accumulates time
  correctly across multiple sessions.

---

## P1: Format Semantics

Design decisions that affect the file format, parser, and all downstream tools.
Resolve these before implementing features that depend on them.

- [ ] Decide hierarchy representation: choose whether `parent:` (explicit) or
  indentation (inferred) is the canonical form, and document the other as
  derived. Define `--canonical` output for `filter` and `from-json` so that
  round-tripped files have a predictable structure.

- [ ] Define dependency semantics for `depends_on:` and `blocks:`: specify
  whether `check` warns when a task is marked done while a `depends_on:`
  prerequisite is still open, whether `blocks:` is the inverse mirror of
  `depends_on:` or an independent assertion, and how `agenda` and `health`
  surface blocked items.

- [ ] Finalize timezone-aware datetime round-trip rules: specify how naive
  datetimes (no timezone suffix) are stored and interpreted, how
  `#! timezone:` and config `defaults.timezone` affect display and filtering,
  and how `to-json`, `to-csv`, and `from-json` preserve or normalize timezone
  information without silent data loss.

- [ ] Decide which item types should recommend `elapsed:`: currently only
  task-like records use it; determine whether `E` events, `S` status records,
  and `J` journal entries should also record elapsed time, and add
  type-specific guidance to the spec.

- [ ] Extend recurrence expansion beyond `agenda` and shared time filters:
  specify expansion behavior for `stats`, occurrence exports (JSON/JSONL/CSV/
  life.txt), and Web API/UI. Define how generated occurrences should be
  represented without confusing them with stored source items.

- [ ] Define encryption metadata conventions: specify whether encrypted field
  values are stored inline as a tagged string (e.g., `note:enc:AES256GCM:BASE64`)
  or in a separate sidecar file, and how the parser identifies encrypted values
  without decrypting so that `check`, `filter`, and `to-json` can handle them
  safely.

---

## P1: Configuration

Settings that affect how values are resolved across CLI, config file, and
file-level metadata. These must be consistent across all commands.

- [ ] Wire `#!` directive values into command behavior: apply `self` as the
  default `person:` for `S` items (when `--person self` or no `--person` is
  given), apply `timezone` to datetime display and filtering, and apply
  `project` as the default `project:` for items missing one. Currently
  `parse_directives` extracts them and `sources --format json` exposes them,
  but no command reads them yet.

- [ ] Define and enforce the setting resolution order for all configurable
  values, applied consistently by every command:
  1. Explicit CLI flag (highest priority)
  2. External config JSON `defaults` section
  3. `#!` file-level metadata directives
  4. Built-in defaults (`self="self"`, `timezone=UTC`)
  Document this order in the format spec, in `config init` output comments,
  and in a dedicated "Configuration" section of the CLI guide.

---

## P1: CLI — Core Improvements

Improvements to existing commands that affect daily workflow.

- [ ] Unify filter options: `filter`, `agenda`, `stats`, `to-json`,
  `to-jsonl`, `to-csv`, and `markdown` must share a single filter
  implementation and accept identical option names and semantics. Any filter
  added to one command must be available in all others without additional work.

- [ ] Improve `assist` for complex fields: add flag support for Markdown `body:`
  (multi-line input in interactive mode and `--body` flag for non-interactive),
  `RRULE:` values, `repeat:` with `interval:`/`until:`/`count:`, duration
  fields (`est:`, `elapsed:`), and link fields (`depends_on:`, `blocks:`,
  `related:`). Ensure Tab-completion covers these fields in interactive mode.

- [ ] Add recurrence occurrence output to `agenda`: include source item ID,
  occurrence datetime, and the recurrence rule that generated the occurrence
  in `--format json` and `--format jsonl` output. Define how filtered
  occurrence sets are exported to JSON, JSONL, CSV, and life.txt.

- [ ] Add terminal width adaptation: commands that render tables (`agenda`,
  `status`, `stats`, `tui`) must detect terminal width and switch to a compact
  single-line-per-item format when the terminal is too narrow for a full table.
  Support `--width N` to override auto-detection.

- [ ] Keep CLI help synchronized with docs: after every change to `tui`,
  `fzf`, `timer`, `stats`, `git-hook`, and `completion`, update
  `docs/en/cli.md`, `docs/ja/cli.md`, and shell completion scripts in the
  same commit.

---

## P1: CLI — New Commands (Onboarding & Safety)

New commands that reduce the initial setup cost and protect against data loss.
Implement before other new commands because they lower the barrier for all
subsequent use.

- [ ] Add `init` command for interactive first-time setup: prompt for user
  name, timezone, and default project, then write `life.txt` with matching
  `#!` directives and `.lifetxt.json` with matching `defaults`. Append a
  starter task (`[ ] T First_Task due:TODAY`) so the file is non-empty and
  immediately parseable by every other command. Prompt before overwriting
  existing files. Intended to replace the manual setup steps currently
  described in the README.

- [ ] Add `doctor` command for environment diagnostics: check Python version,
  presence and readability of `life.txt` and `.lifetxt.json`, availability of
  optional dependencies (`fzf`, `peco`, `textual`, `watchdog`, `matplotlib`,
  `cryptography`), and common data issues (missing IDs, W213 duplicates,
  unresolved references). Print a `✓`/`!`/`✗` summary with a concrete
  next-step command for each issue. Exit non-zero when any check fails so
  `doctor` can be used in CI onboarding scripts.

- [ ] Add `undo` command to reverse the most recent write on a given file:
  before every successful write operation (`assist`, `done`, `archive`,
  `quick`, `assign`, `encrypt`, `decrypt`), save a timestamped backup to
  `.cache/lifetxt/undo/` (configurable via `undo.dir`). `lifetxt undo FILE`
  restores the previous version; `--list` shows the undo stack with
  timestamps and operation names. Limit stack depth via `undo.keep`
  (default: 20). Document that `undo` is not a substitute for Git but provides
  safety for users who do not use version control.

- [ ] Add automatic backup configuration: when `backup.auto` is `true` in
  config, save a timestamped copy of any modified file to `backup.dir`
  (default: `.cache/lifetxt/backup/`) before each write. Retain the most
  recent `backup.keep` copies (default: 20) per file and delete older ones.
  Complements `undo` (operation-level) with file-level timestamped recovery
  that survives process crashes and does not require an explicit undo step.

---

## P1: CLI — New Commands (Daily Operations)

New commands for the most frequent daily actions. Each delegates to an
existing command internally to reuse validation and atomic write behavior.

- [ ] Add `assign` command for changing `assignee:` on an existing item:
  `lifetxt assign FILE ID --to PERSON`. Optionally create a type `M`
  notification to the new assignee when `--notify` is passed. Delegate to
  `assist --update` internally.

---

## P1: CLI — New Commands (Review & Health)

New commands that close the feedback loop: surfacing what is happening,
what is overdue, and what the week looked like.

- [ ] Add `review` command for human-readable period summaries: produce a
  structured report covering completed tasks, remaining open tasks, habit
  completion rates, mood trend, elapsed time by project, and journal body
  excerpts. Options: `--week` (current ISO week), `--month YYYY-MM`,
  `--from`/`--to`, `--project`. Formats: `text` (terminal-readable, pipeable
  to a pager) and `json` (structured for LLM input). The JSON schema must be
  stable so AI-assisted review workflows can rely on it.

- [ ] Add `health` command for operational sanity checks beyond syntax
  validation:
  - W301: task open for more than `--since` days (default: 30) without update
  - W302: habit with no completion record within `--since` days
  - W303: deadline due within `--lookahead` days (default: 7) still open
  - W304: `assignee:` or `owner:` with no recent `S` presence record
  Support `--ignore CODE`, `--format text|json`, and `--since`/`--lookahead`
  thresholds. Keep `health` separate from `check` so CI can gate on format
  errors without failing on operational warnings.

- [ ] Add `inbox` command to surface unclassified items: list open tasks that
  have no `project:`, no `due:`, and no `assignee:`. Options: `--process`
  for interactive one-by-one triage (prompts for project, due, assignee using
  `assist` completion helpers), `--fzf` to open matches in `fzf` for quick
  editing. Intended as the GTD inbox-processing step for items captured via
  `quick` or `assist` without full detail.

- [ ] Add `cleanup` command as a guided file-maintenance navigator: run
  `check`, `health`, `ids`, and `links` internally, then print a prioritized
  action list (e.g., "3 items have no ID — run `ids --assign --dry-run`",
  "5 completed items older than 90 days — consider `archive --before 90d`").
  Never modifies the file; only reports and suggests next commands. Support
  `--format text|json` and `--ignore CODE`.

---

## P1: CLI — Archive

Commands and behaviors for moving old items out of active files.

- [ ] Add `archive` command: move or copy completed/canceled/old items from
  a source file to a separate archive file. Core options: `--before DATE`
  (archive items whose latest date key is before DATE), `--max-items N`
  (archive at most N items), `--status done,canceled` (filter by status),
  `--dry-run` (print what would change without writing), `--move` (default)
  vs `--copy`, `--yes` (skip confirmation prompt).

- [ ] Implement structure-preserving mode for `archive` (default): copy
  comment lines and blank lines verbatim to both the source remainder file
  and the archive file. Item lines are distributed by the archive criteria.
  Comments are never removed from either file, so section headings remain
  intact; a section may become empty (heading with no items below it) in
  either file. Document this behavior with a before/after example.

- [ ] Implement orphan-child handling via `--orphan-children MODE`
  (default: `block`):
  - `block`: refuse to archive a parent when any direct or transitive child
    is open; report all blocking child IDs and line numbers.
  - `adopt`: archive parent and all children together; mark open children
    `[-]` with `reason:adopted-by-archive` before writing.
  - `promote`: archive the parent only; remove `parent:` from children left
    behind and insert a comment above each noting the archived parent ID.
  Document all three modes with before/after examples.

- [ ] Extend `archive --dry-run` with cross-file reference checking: when
  other loaded files reference the ID of an item being archived (via
  `depends_on:`, `blocks:`, `parent:`, `ref:`, or `related:`), report each
  referencing item (file path, line, key, referencing ID) as a warning.
  Default: warn only. Add `--block-on-external-refs` to treat these as errors.

---

## P1: CLI — Encryption

Field-level encryption for sensitive content (journal bodies, messages).

- [ ] Add `encrypt` and `decrypt` commands: `encrypt` rewrites selected field
  values as tagged ciphertext in-place using a passphrase or key file;
  `decrypt` restores them. Options: `--field FIELD` (e.g., `body`, `note`),
  `--type TYPE` (e.g., `J`, `M`), `--dry-run`, `--key-env ENVVAR`. Core
  implementation uses only Python standard-library primitives (`hashlib`,
  `hmac`, `secrets`, `base64`); document an optional stronger path using the
  `cryptography` package. Ciphertext tag format: `enc:ALG:BASE64` (e.g.,
  `enc:AES256GCM:...`) so the parser can detect encrypted values without
  decrypting and skip them in `check`, `filter`, and `to-json`.

---

## P1: CLI — Visualization

CLI-native charts without external dependencies.

- [ ] Add `plot` command: render task completion trends, habit streaks, mood
  timelines, elapsed time by project, and deadline density as Unicode bar
  charts and sparklines. No dependencies beyond the Python standard library
  for the default text output. Accept the same `--type`, `--project`,
  `--from`, `--to`, `--group daily|weekly|monthly` filters as `stats`. Add
  optional `--format svg|png` via `matplotlib` (opt-in dependency); the
  dependency-free text output remains the default and is always available.

---

## P1: Web API / Browser UI

- [ ] Standardize API error responses: every error must return a stable JSON
  body `{"error": CODE, "message": "...", "detail": {...}}` so clients can
  parse errors programmatically without inspecting human-readable text.

- [ ] Add local authentication: implement a simple bearer-token option
  (`api.token` in config, presented as `Authorization: Bearer TOKEN`) before
  exposing the server to any non-loopback address. Document that the server
  must not be exposed to the network without a token.

- [ ] Improve message thread UI: use `parent:` and `/api/messages/thread/{id}`
  to render conversation threads in the browser GUI. Ensure `ack:` and
  `snooze_until:` state is reflected in the UI without a page reload.

- [ ] Improve Web notification UX: show permission state (granted/denied/
  default), acknowledgement button, snooze control, retry on delivery failure,
  and visible delivery state (pending/delivered/snoozed/acknowledged) in the
  browser GUI.

- [ ] Allow display-mode presets from config `views` to be selected by URL
  parameter (`?view=NAME`) without duplicating the preset definition in the
  URL. Currently presets are defined in config but must be re-specified as
  URL parameters.

- [ ] Represent recurrence occurrences in the Web API/UI: distinguish source
  items (stored in the file) from generated occurrences (computed at request
  time) in `/api/agenda` and the GUI calendar view. Never write generated
  occurrences back to the file.

- [ ] Add chart API endpoints: `/api/chart/tasks`, `/api/chart/habits`,
  `/api/chart/mood`, `/api/chart/elapsed`. Each returns a stable JSON data
  structure suitable for a browser charting library (e.g., Chart.js). Add
  corresponding chart panels to the browser GUI.

- [ ] Add MCP (Model Context Protocol) server support via `serve --mcp`:
  expose life.txt operations as MCP tools so MCP-compatible AI clients
  (Claude Desktop, Cursor, etc.) can read and write items using natural
  language. Minimum tool set: `list_items` (with filter parameters matching
  `filter`), `get_item` (by ID), `create_item` (delegates to `assist`),
  `update_item` (delegates to `assist --update`), `mark_done` (delegates to
  `done`), `get_agenda` (delegates to `agenda`). Implement as an optional
  dependency separate from the existing FastAPI server.

- [ ] Add API tests for mixed writable and generated/read-only file sets.

- [ ] Expand `docs/en/web.md` and `docs/ja/web.md` with current endpoint
  request/response examples for every route.

---

## P1: Multiple Files / Sync / External Tools

- [ ] Document the recommended directory layout for a typical user:
  `life.txt` (hand-written), `.generated/` (ICS sync output), `archive/`
  (archived items), `.cache/lifetxt/` (undo stack, backup, notification
  state). Explain which directories belong in `.gitignore`.

- [ ] Make generated/read-only file handling consistent: commands that write
  (`assist`, `done`, `archive`, `assign`) must refuse to modify a file listed
  in config `generated_paths` or marked read-only by the OS, and must report
  a clear error rather than silently failing or corrupting the file.

- [ ] Improve `sync-ics` idempotency: use the iCalendar `UID` field as the
  stable item ID so re-running `sync-ics` updates existing events rather than
  duplicating them. Detect and soft-delete items whose UID no longer appears
  in the feed. Store source metadata (`source:ics`, `uid:`) on generated items.

- [ ] Extend `import-ics` with source-specific presets: add `--preset todoist`
  for Todoist CSV exports, `--preset github` for GitHub Issues JSON exports,
  and `--preset markdown` for Markdown task-list files (`- [ ] title`). Each
  preset maps source fields to life.txt keys consistently and documents
  unmapped fields. Keep `from-csv` and `from-json` as the generic low-level
  path; presets are convenience wrappers.

- [ ] Define integration boundaries for calendar sources beyond ICS and for
  presence/message tools (Teams, Discord, Slack): specify which fields are
  imported, which are exported, and which are read-only in life.txt because
  they are managed by the external tool.

- [ ] Add pre-commit framework examples: provide `.pre-commit-hooks.yaml` so
  `lifetxt check` can be used as a pre-commit hook without the built-in
  `git-hook install` command.

- [ ] Document that secret URLs and tokens (iCalendar feed URLs, API tokens)
  must not be stored in life.txt content. Reference the `--url-env` and
  `--key-env` patterns as the correct approach.

---

## P1: Validation

Diagnostics added to `check` and `health` that catch common mistakes.

- [ ] Add W219: warn when a completed or canceled parent (`[x]` or `[-]`)
  has one or more open children (`[ ]`, `[/]`, `[>]`, `[?]`). Report each
  open child's ID, line number, and status. Apply to both explicit `parent:`
  references and inferred indentation-based relationships. Suppress with
  `--ignore W219` for intentional cases (open subtasks that continue
  independently after the parent closes).

- [ ] Add W219 resolution guidance to `check` output: when W219 fires,
  print the three resolution options — (1) close children manually, (2) run
  `archive --orphan-children adopt`, (3) run `archive --orphan-children
  promote` — so the user knows how to fix the issue without reading docs.

---

## P2: CLI — Power User Commands

Additional commands for users who want deeper inspection, style enforcement,
long-term file management, and sharing. Implement after P1 commands are stable.

- [ ] Add `search` command as a life.txt-aware alternative to `grep`: support
  substring and regex matching (`--regex`) scoped to specific fields (`--in
  title`, `--in body`, `--in KEY`; multiple `--in` values are OR-ed). Highlight
  matched text in `text` output. Accept glob input for cross-file search.
  Output formats: `text` (highlighted), `life` (original lines), `json`,
  `jsonl`.

- [ ] Add `lint` command for style and convention checks separate from
  `check`: detect key-name typos (e.g., `proj:` vs `project:`), non-standard
  tag casing, priority values outside a configured set, and custom rules
  loaded from a JSON ruleset file (`--ruleset FILE`). Support `--rule RULE`
  to enable specific built-in rules and `--fix` to auto-correct safe issues
  in-place. Exit behavior: exit 0 when only style issues are found so `lint`
  does not block CI that already uses `check`.

- [ ] Add `diff` command for semantic diffing between two life.txt inputs
  (files, glob sets, or snapshots): report added, completed, canceled,
  status-changed, and detail-changed items grouped by change type. Support
  `--format text|json|jsonl` and `--type`, `--project`, `--status` filters.
  Primary use cases: weekly progress review, pre/post archive comparison,
  team file change summaries.

- [ ] Add `snapshot` command for point-in-time file copies:
  `lifetxt snapshot life.txt -o snapshots/2026-06-27.life.txt`.
  The output is a plain life.txt file with no special markers. Combine with
  `diff` for progress comparisons. Document a recommended snapshot naming
  convention (`YYYY-MM-DD` prefix) and directory layout.

- [ ] Add `migrate` command for in-place format upgrades: apply a named
  migration (e.g., `--migration normalize-elapsed`, `--migration rename-key
  old=new`) to all items in a file. Options: `--dry-run` to preview changes,
  `--backup` to write a `.bak` before modifying. Implement migrations as
  versioned, composable transformations so multiple can be chained. Document
  each migration name, the change it applies, and the spec version it targets.

- [ ] Add `template` command for reusable item sets: store named templates in
  config JSON or in a `templates.life.txt` file using a reserved `TEMPLATE`
  type marker. `lifetxt template list` shows available templates; `lifetxt
  template apply NAME --append FILE` expands the template, resolving date
  placeholders (`{today}`, `{next_monday}`, `{next_week}`) at apply time, and
  appends the result. Differs from `H` habits: template content varies each
  time and is not scheduled automatically.

- [ ] Add `share` command to generate self-contained read-only output:
  combine `filter`, `plot`, and `review` output into a single HTML or Markdown
  file for sharing without running the server. `--format html` must produce a
  single file with no external dependencies (inline CSS and JS). `--format
  markdown` produces a document suitable for pasting into a wiki or note tool.
  Accept standard filter options and `--week`/`--month` shortcuts.

- [ ] Add `digest` command for scheduled report delivery: read `review --format
  json` output and POST it to a configured destination. Channels: `--format
  slack-webhook` (Slack incoming webhook URL via `--url-env`), `--format
  email` (SMTP with credentials from environment variables), `--format file`
  (append Markdown to a local log). Transport dependencies are optional; the
  command exits with a clear error if the required dependency or environment
  variable is missing before making any network request.

- [ ] Add `who` command as a multi-file presence summary: read `S` items from
  all loaded files, group by `person:`, and display the latest active state in
  a compact one-line-per-person table. Equivalent to `status --active` across
  a glob but optimized for team-at-a-glance use. Support `--format text|json`
  and accept glob patterns directly.

---

## P2: Editor Support

- [ ] Package VS Code grammar and snippets as a proper extension installable
  from the Marketplace or via `code --install-extension`, not by copying files
  manually.

- [ ] Keep editor file-association documentation current for `life.txt`,
  `*.life.txt`, and `*_life.txt` in `docs/en/editor.md` and
  `docs/ja/editor.md`.

- [ ] Generate Tab-completion candidates and snippet key lists directly from
  `lifetxt/model.py` (`RECOMMENDED_KEYS_BY_TYPE`, status aliases, type
  aliases) to prevent drift between the editor extension, CLI completion
  scripts, and the spec.

- [ ] Add highlight snapshot tests for every grammar token: title, status,
  type, detail key, quoted value, body continuation (`|`), line continuation
  (`\`), `#!` directive, and `enc:` encrypted value prefix. Run these in CI
  to catch grammar regressions.

- [ ] Add editor support for `#!` metadata directive lines: highlight
  distinctly from ordinary `#` comment lines. Add snippets for common
  directive combinations (`self` + `timezone` + `project`).

- [ ] Add editor support for encrypted field values (`enc:` prefix): display
  with a distinct color and a tooltip indicating the value is encrypted.

- [ ] Add snippets for: task with timer fields (`est:`, `elapsed:`), event
  with attendees, status record (self), message with notification, journal
  entry with mood, linked subtask with `parent:` and `depends_on:`, and
  template record.

---

## P2: TUI Usability

- [ ] Add configurable TUI themes and keymaps via config after collecting
  real-terminal feedback: support at minimum a light/dark theme toggle and
  a non-Vim keymap preset for users who prefer arrow-key navigation.

- [ ] Add row selection to TUI: pressing Enter on a task row should offer
  actions (show full detail, open in `$EDITOR`, mark done via `done`, quick
  filter by project). This makes `tui` usable as a lightweight interactive
  manager without switching to `fzf`.

---

## P2: Documentation / Examples

- [ ] Resolve documentation synchronization policy: decide which of `readme.md`,
  `docs/en/readme.md`, `docs/ja/readme.md`, and `life_txt_format_spec.md` is
  the authoritative source for each topic, and document the policy so
  contributors know where to make changes.

- [ ] Add worked examples for: `timer` (start, pause, stop, summary),
  `stats` (weekly grouping), `tui` (keymap cheatsheet), `fzf` (preview and
  actions), `git-hook` (install and commit-msg), `completion` (bash/zsh/fish
  install).

- [ ] Add recommended workflow docs with step-by-step instructions for:
  daily use (`quick` → `inbox` → `done` → `summary`), team status sharing,
  message notifications, calendar sync (`sync-ics` + `agenda`), weekly review
  (`review` → LLM → `template apply`), and periodic archiving.

- [ ] Add migration notes for every breaking format change: `S`, `M`, `J`
  type additions, multiline body (`|`), hierarchy and `parent:`, CSV column
  schema, `elapsed:` normalization, Markdown subset, and RRULE storage.
  Include the `migrate` command invocation for each change once implemented.

- [ ] Add screenshots or terminal captures for: Web UI agenda view, `tui`
  dashboard, `stats` weekly output, `plot` terminal chart, and `doctor`
  diagnostic output. Include in both English and Japanese docs.

- [ ] Generate a diagnostic code catalog from parser and validator definitions:
  each code (E0xx, W2xx, W3xx, W4xx) must have a name, description, example
  triggering input, and resolution hint. Use this catalog as the source for
  CLI `--help`, shell completion, and the docs diagnostic reference.

- [ ] Document recommended file-splitting strategies (not enforced
  constraints): one file per editor/author, auto-generated files in
  `.generated/`, archives in `archive/`, and periodic archiving schedule.
  Clarify that the tool enforces nothing; these are operational recommendations.

- [ ] Document `#!` metadata directive syntax: supported keys, placement
  rules, and the full four-level resolution order with side-by-side examples
  comparing directive-based, config-based, and CLI-flag-based configuration
  for the same setting.

- [ ] Document `archive` command and workflow: all `--orphan-children` modes
  with before/after examples, `--block-on-external-refs` for cross-file
  safety, structure-preserving comment behavior, and when to use `--dry-run`.

- [ ] Document W219 resolution: explain the three resolution paths (close
  children manually, `archive --orphan-children adopt`, `archive
  --orphan-children promote`) and when `--ignore W219` is appropriate.

- [ ] Document `encrypt`/`decrypt`: supported algorithms, key management
  recommendations (passphrase vs key file vs environment variable), which
  field types are good candidates, and how to run `check` safely on a
  partially encrypted file.

- [ ] Document `plot`: chart types, filter options, terminal rendering
  behavior, enabling SVG/PNG output, and piping text output to a pager.

- [ ] Document `undo` and `backup.auto`: differences between the two safety
  mechanisms, recommended config for users without Git, and step-by-step
  recovery from an accidental write.

- [ ] Document `init` and `doctor`: position as the recommended onboarding
  entry points in the main README and installation guide, with an annotated
  example of a first session from `init` through `quick` and `summary`.

- [ ] Add `docs/en/ai-integration.md` and `docs/ja/ai-integration.md`:
  MCP server setup and tool reference, CLI pipe patterns (`to-json | llm
  "..."`), example prompts for `review --format json` → LLM weekly review,
  local LLM (Ollama) setup for privacy-sensitive files, and a GitHub Actions
  workflow for automated AI summaries on push. Include annotated examples
  showing what life.txt data looks like from the AI's perspective.

- [ ] Add all new command docs and workflow examples to `docs/en/cli.md` and
  `docs/ja/cli.md`: `init`, `doctor`, `quick`, `done`, `undo`, `assign`,
  `summary`, `review`, `health`, `inbox`, `cleanup`, `archive`, `encrypt`,
  `decrypt`, `plot`, `search`, `lint`, `diff`, `snapshot`, `migrate`,
  `template`, `share`, `digest`, `who`.

- [ ] Consider generating CLI reference pages from `argparse` definitions to
  eliminate drift between `--help` output and the Markdown docs.

---

## P2: Tests / CI / Release

- [ ] Add CI pipeline: unit tests, compile checks, and example file
  validation on every push. Run on Python 3.10, 3.11, and 3.12 on Ubuntu,
  Windows, and macOS.

- [ ] Add a lightweight smoke-test runner for release checks: execute key CLI
  smoke tests (including timer state-file and cross-platform path tests)
  without running the full unittest suite.

- [ ] Add snapshot tests for all important human-readable CLI output so
  unintended formatting changes are caught automatically.

- [ ] Add sync tests comparing `RECOMMENDED_KEYS_BY_TYPE` in
  `lifetxt/model.py` with the type-specific recommended key lists in the
  English and Japanese format specs.

- [ ] Add cross-platform tests: paths with spaces, glob expansion, Windows
  line endings (`\r\n`), and shell completion output on bash, zsh, and fish.

- [ ] Add glob input tests for `*.life.txt`, `*_life.txt`, and
  `projects/**/*.life.txt` across all file-reading commands.

- [ ] Add parser edge-case tests: Unicode escaping, nested quotes, invalid
  `|` continuation variants, indentation with mixed spaces and tabs, and
  same-file duplicate-ID edge cases.

- [ ] Add recurrence tests: occurrence expansion for all five simple repeat
  values, `interval:` / `until:` / `count:` edge cases, occurrence export
  shapes, and long-range expansion performance (10 years of daily recurrence
  must complete under 500 ms).

- [ ] Add duration normalization tests (W222): bare integers, `1h00m`,
  `1.5h`, and unrecognized formats.

- [ ] Add `#!` directive wiring tests: verify that `self`, `timezone`, and
  `project` directive values influence `S`-item person defaulting, datetime
  display, and item project defaulting once wiring is implemented.

- [ ] Add `quick` tests: `write_file` config fallback (no `--append`),
  `--type E` generates event, validation error on malformed title.

- [ ] Add `done` tests: `--text` with zero matches exits non-zero; `--line`
  with non-item line exits non-zero; no positional/line/text arg exits with
  error message.

- [ ] Add `summary` tests: multi-file input returns array JSON; `--pretty`
  indents output; stdin input works.

- [ ] Add Markdown rendering regression tests: CLI HTML output snapshot and
  Web UI Markdown preview snapshot, run in CI to prevent the table-rendering
  bug from reappearing.

- [ ] Add large-file performance tests: parsing, filtering, and duplicate-ID
  detection on a 50,000-line file must each complete under 5 seconds.

- [ ] Add FastAPI test-client coverage for all `/api/*` routes when optional
  web dependencies are installed.

- [ ] Add release process: changelog (`CHANGELOG.md`), semantic versioning
  policy (`MAJOR.MINOR.PATCH`), and a `make release` or CI workflow that
  tags, builds, and publishes to PyPI.

- [ ] Verify packaging on a clean environment: `pip install -e .`, optional
  extras (`[web]`, `[crypto]`, `[plot]`), console script entry points, and
  Windows PowerShell usage.

- [ ] Add `archive` tests: structure-preserving mode (comments in both files,
  empty sections retained), all three `--orphan-children` modes, `--dry-run`
  for each mode, `--block-on-external-refs`, and cross-file reference warning.

- [ ] Add W219 tests: explicit `parent:` with completed parent and open child,
  inferred indentation-based parent, `--ignore W219` suppression, no false
  positive when all children are also completed.

- [ ] Add `#!` directive parser tests: valid block at file start, block
  terminated by a non-`#!` line, unknown key handling, directives appearing
  after item lines (ignored or warned), and four-level resolution order.

- [ ] Add `encrypt`/`decrypt` round-trip tests: encrypt then decrypt restores
  original value exactly, for all supported algorithms. Test `--dry-run`,
  `--field`, `--type`, `--key-env`. Verify `check` emits no false positives
  for encrypted values.

- [ ] Add `plot` output tests: text chart rendering for task, habit, mood,
  and elapsed with each `--group` value. Snapshot tests for bar chart and
  sparkline terminal output.

- [ ] Add `init` tests: generated files contain valid directives and a starter
  item; `.lifetxt.json` matches prompted values; prompts before overwriting.

- [ ] Add `doctor` tests: pass on a clean environment, correct
  pass/warn/fail per check, optional dependencies reported as warn, exit
  non-zero on any failure.

- [ ] Add `quick` tests: positional title parsing, relative date resolution,
  default type `T`, generated line passes `check`, appended to correct file.

- [ ] Add `undo` tests: undo after each write command, `--list` output,
  stack-depth eviction, error on empty stack.

- [ ] Add `done` tests: by ID, by line number, by unique title match, by
  ambiguous title match (confirmation prompt), auto-appended `done:` date.

- [ ] Add `summary` tests: counts match file contents for every type/status
  combination, missing-ID count is accurate, JSON schema is stable.

- [ ] Add `review` tests: all output sections present for `--week`, `--month`,
  `--from/--to`; JSON schema stability; empty period (no items).

- [ ] Add `health` tests: W301–W304 each fire under the correct condition,
  `--ignore CODE` suppresses correctly, no false positives on recently active
  items.

- [ ] Add `inbox` tests: items without all three qualifier fields are included;
  items with any qualifier are excluded; `--process` prompts in sequence.

- [ ] Add `assign` tests: `assignee:` updated by ID, `--notify` generates
  valid `M` item, `assist --update` validation applied.

- [ ] Add `cleanup` tests: suggestions match actual findings from `check`,
  `health`, `ids`, `links`; `--ignore CODE` suppresses; file is never modified.

- [ ] Add `diff` tests: added, completed, canceled, status-changed,
  detail-changed items; filter scope; JSON output schema.

- [ ] Add `search` tests: substring, regex, field-scoped, multi-field,
  no-match, cross-file glob.

- [ ] Add `migrate` tests: `--dry-run`, `--backup`, chained migrations,
  idempotency.

- [ ] Add `share` tests: HTML is a single self-contained file; Markdown
  renders correctly; filters narrow output.

- [ ] Add `digest` tests: Slack payload shape, `--format file` append,
  missing env var exits before network request.

- [ ] Add `undo` / `backup.auto` tests: backup created before each write,
  `backup.keep` eviction, directory auto-created.

- [ ] Add MCP server smoke tests: each tool returns the expected response
  shape; write tools modify only the writable file.

- [ ] Add `who` tests: latest active `S` per person across multiple files,
  finished records excluded, JSON schema stable.

---

## Deferred Ideas

Ideas that are useful but should not block any near-term release. Revisit
after the corresponding P1 or P2 feature is stable.

### Format & Parser
- [ ] Consider `#! import: PATH [as ALIAS]` directive (phase 2 of file-level
  metadata): auto-load declared files for cross-file ID resolution without
  listing them on the CLI. Unresolved design questions: relative-path base,
  maximum import depth, circular-import detection, read-only semantics for
  imported IDs. Evaluate whether `--config paths` already covers all practical
  cases before implementing.
- [ ] Consider namespace-qualified ID syntax (`alias:id`) only if flat
  cross-file resolution proves insufficient after `#! import` or `--config
  paths` is in place. The `:` separator conflicts with `key:value` parsing
  and requires a parser change; defer until a concrete unsolvable case arises.
- [ ] Consider JSON Schema definitions for JSON/JSONL output and API payloads
  to enable external tool validation without parsing life.txt directly.

### CLI Extensions
- [ ] Consider named or multiple parallel timers if the single global timer
  becomes too restrictive for users who switch between tasks frequently.
- [ ] Consider a small local daemon that unifies notification watch, timer
  status, and file-reload events into a single background process.
- [ ] Consider `quick` type inference from title keywords ("meeting at 14:00"
  → `E`, "remind me to …" → `R`) as an opt-in mode after the basic command
  is stable.
- [ ] Consider `template` variables beyond date placeholders (`{user}`,
  `{project}`) and a simple prompt mode that asks for variable values before
  expanding.
- [ ] Consider `review --format markdown` for output suitable for pasting into
  a note tool or Markdown wiki, after the text and JSON formats are stable.
- [ ] Consider `digest` additional channels (Teams webhook, Discord webhook,
  desktop notification) after the core Slack/email delivery is stable.
- [ ] Consider `archive` rotation policy (e.g., yearly auto-archive via config
  `archive.auto`) after the basic `archive` command is stable.
- [ ] Consider `--config paths` auto-load mode: when no file arguments are
  given, fall back to the paths configured in `.lifetxt.json`, reducing
  repetition in daily use.
- [ ] Consider `lint` community ruleset repository so teams can share and
  contribute standard style conventions.

### Web & API
- [ ] Consider `plot` output as a self-contained HTML file with embedded
  Chart.js for sharing without running the server.
- [ ] Consider interactive `plot` mode in `tui` as a live-updating chart
  panel, after the basic `plot` command is stable.
- [ ] Consider `who` integration into the `tui` sidebar panel showing team
  presence alongside tasks and agenda.
- [ ] Consider `share` export as an email-ready HTML attachment via `digest`.
- [ ] Consider write-conflict detection using source-ownership metadata before
  `update` and `delete` operations when multiple writers share a file.

### Security
- [ ] Consider asymmetric encryption (public/private key) for `encrypt` to
  support multi-user scenarios where different people encrypt but only the
  key holder can decrypt.

### Ecosystem
- [ ] Consider import/export adapters beyond ICS: org-mode, Todoist CSV, and
  mailbox/message logs, after the preset mechanism in `import-ics` is stable.
- [ ] Consider a static HTML export mode (`serve --export DIR`) that writes
  a read-only snapshot of the GUI without requiring the server to keep running.
