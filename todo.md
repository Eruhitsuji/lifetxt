# lifetxt TODO / Roadmap

Last updated: 2026-06-28 (updated x33)

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

- [ ] Extend `#!` directive wiring to `timezone`: apply `timezone` directive
  to datetime display (agenda, summary, stats) and filtering. Currently `self`
  and `project` are wired for `quick` and `assist`; `timezone` remains unread.

- [ ] Document the four-level setting resolution order in the format spec and
  in a dedicated "Configuration" section of the CLI guide: (1) CLI flag,
  (2) config JSON defaults, (3) `#!` file-level directives, (4) built-in
  defaults. Update `config init` output to include comments describing each level.

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

- [ ] Add onboarding mention for `init` and `doctor` to README and verify
  `--yes` behavior is documented in CLI guide.

---

## P1: CLI — New Commands (Daily Operations)

New commands for the most frequent daily actions. Each delegates to an
existing command internally to reuse validation and atomic write behavior.

---

## P1: CLI — New Commands (Review & Health)

New commands that close the feedback loop: surfacing what is happening,
what is overdue, and what the week looked like.

- [ ] Add `--process` mode to `inbox` command: interactive one-by-one triage
  prompting for `project:`, `due:`, and `assignee:` using `assist` completion
  helpers. Add `--fzf` to open inbox results in `fzf` for quick editing.

---

## P1: CLI — Archive

Commands and behaviors for moving old items out of active files.

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

### API Stability & Security

- [ ] Add API tests for mixed writable and generated/read-only file sets.

- [ ] Expand `docs/en/web.md` and `docs/ja/web.md` with current endpoint
  request/response examples for every route.

### Statistics & Charts (Web UI)

- [ ] Verify weekly/monthly chart rendering in the browser: the `/api/chart/habits`
  now returns raw counts per bucket; confirm Chart.js renders bars correctly
  and the Y-axis label is meaningful (e.g., "completions / week").

### Item Input Form (Web UI)

- [ ] Improve `importRawLine()` parser: handle all field types (multi-value,
  quoted values, `body:` continuation) so complex raw lines populate the
  form faithfully (current regex-based split is best-effort for simple lines).

### Record Display (Web UI)

- [ ] Enhance item detail dependency view: expand the current row-based dep
  view into a mini force-directed graph (D3.js, CDN) inside the drawer showing
  multi-hop dependency chains, not just direct links.

### ID Links & Cross-References (Web UI)

- [ ] Test ref-link badge scroll-to-deps on touch devices: the scroll
  uses `scrollIntoView({behavior:'smooth'})` which may not work reliably
  on iOS Safari — verify or replace with explicit `scrollTop` logic.

### Dependency & Reference Graph (Web UI & CLI)

- [ ] Add a dependency/reference graph panel to the browser GUI: render the
  `/api/graph` JSON using D3-force (loaded from CDN). Node color encodes type;
  node border encodes status. Clicking a node opens the item in the side drawer.

- [ ] Add `links` tests for Mermaid/DOT: cross-file node references, special
  characters in IDs/titles (quotes, spaces), and `--id` + `--direction` scoping
  with mermaid/dot output (verify only reachable subgraph is rendered).

### Recurrence & Notifications (Web UI)

- [ ] Represent recurrence occurrences in the Web API/UI: distinguish source
  items (stored in the file) from generated occurrences (computed at request
  time) in `/api/agenda` and the GUI calendar view. Never write generated
  occurrences back to the file.

- [ ] Improve message thread UI: use `parent:` and `/api/messages/thread/{id}`
  to render conversation threads in the browser GUI. Ensure `ack:` and
  `snooze_until:` state is reflected in the UI without a page reload.

- [ ] Improve notification retry: when Notification.permission is "denied",
  prompt the user to re-enable notifications in browser settings rather than
  silently failing on the retry attempt.

- [ ] Improve "clear preset" × button visibility: currently the button is always
  visible in the toolbar; hide it when no preset is stored in localStorage by
  wiring `updatePresetClearBtn()` to `applyViewPreset` and page load.

### Git Integration (Web API)

### Quick-filter & Navigation (Web UI)

- [ ] Add `GET /api/git/log` pagination: the current `?n=` cap is 50;
  add a "Show more" link in the git modal to load older commits.

### Context Menu & Dark Mode (Web UI) — New

- [ ] Wire dark mode toggle to system color-scheme change events:
  add a `matchMedia('prefers-color-scheme: dark').addEventListener('change',...)`
  listener so the UI auto-switches when the OS theme changes at runtime.

- [ ] Add keyboard shortcut for dark mode toggle (e.g., `d` key) and add
  entry to help modal table.

- [ ] Context menu: add "Copy line number" and "Open raw file" entries;
  "Open raw file" could use `file://` URI on desktop or show a path toast.

### Stats & Charts (Web UI) — New

- [ ] Wire `/api/stats/summary` endpoint to the Stats panel: show by_type
  and by_status breakdowns alongside the existing project mini-table.

- [ ] Chart Y-axis label: when group=weekly/monthly, annotate the Y-axis
  as "completions / week" or "completions / month" rather than raw count.

- [ ] Add export button to charts: "Download CSV" that serializes the
  current chart labels+datasets as a CSV file (client-side Blob download).

### Drawer Improvements (Web UI) — New

- [ ] Drawer: add "Share" button that copies a `?line=N` deep-link URL to
  clipboard so the user can share a direct link to a specific item.

- [ ] Drawer: show full item type name (e.g., "Task" not "T") next to the
  type badge, with a tooltip explaining what each type does.

### Agenda & Notifications (Web UI) — New

- [ ] Agenda: add "view all" link below the truncated agenda list that
  sets `agenda_limit` to 0 (unlimited) and reloads.

- [ ] Notification: show delivery time relative to "now" (e.g., "5 min ago")
  in the notification row pill instead of the raw timestamp.

### MCP Support

- [ ] Add MCP (Model Context Protocol) server support via `serve --mcp`:
  expose life.txt operations as MCP tools so MCP-compatible AI clients
  (Claude Desktop, Cursor, etc.) can read and write items using natural
  language. Minimum tool set: `list_items` (with filter parameters matching
  `filter`), `get_item` (by ID), `create_item` (delegates to `assist`),
  `update_item` (delegates to `assist --update`), `mark_done` (delegates to
  `done`), `get_agenda` (delegates to `agenda`), `get_graph` (delegates to
  `/api/graph`). Implement as an optional dependency separate from the
  existing FastAPI server.

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

- [ ] Add usage example for `.pre-commit-hooks.yaml` to docs: show the
  `.pre-commit-config.yaml` snippet that references the `lifetxt-check` hook,
  and document which file patterns are matched by default.

- [ ] Document that secret URLs and tokens (iCalendar feed URLs, API tokens)
  must not be stored in life.txt content. Reference the `--url-env` and
  `--key-env` patterns as the correct approach.

---

## P1: Validation

Diagnostics added to `check` and `health` that catch common mistakes.

---

## P2: CLI — Power User Commands

Additional commands for users who want deeper inspection, style enforcement,
long-term file management, and sharing. Implement after P1 commands are stable.

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

- [ ] Add dependency-focused views and filters: show only blocked or unblocked
  items in `agenda`, expose blocker chains in `links` or a dedicated
  `deps` view, and add Web UI affordances for quickly seeing why an item is
  blocked. Keep this as a usability layer on top of the implemented
  `depends_on:` / `blocks:` semantics.

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

- [ ] Expand `docs/en/web.md` and `docs/ja/web.md` with: current endpoint
  request/response examples for every route, the statistics dashboard and
  chart panel usage, the item creation and edit form, the dependency graph
  panel (how to open it, how to navigate, how to use `?root=ID`), the Git
  integration endpoints and security model, and the `quick-add` shortcut.

- [ ] Document the dependency graph feature end-to-end: explain the
  `links --format mermaid` and `links --format dot` CLI outputs, the
  `/api/graph` endpoint, the browser GUI graph panel, and when to use each.
  Include a worked example showing how to trace a blocked task back to its
  root blocker using both the CLI and the GUI.

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

- [ ] Add canonical hierarchy edge-case tests: `from-jsonl --canonical`,
  `from-csv --canonical`, custom `ids.key`, a parent without an ID, and items
  that already have explicit `parent:` details.

- [ ] Add recurrence tests: occurrence expansion for all five simple repeat
  values, `interval:` / `until:` / `count:` edge cases, occurrence export
  shapes, and long-range expansion performance (10 years of daily recurrence
  must complete under 500 ms).

- [ ] Add duration normalization tests (W222): `1h00m` simplification, elapsed
  accumulation across multiple items in the same project.

- [ ] Add `#!` directive wiring tests for `timezone`: verify datetime display
  is affected once timezone wiring is implemented.

- [ ] Add `quick` tests: `write_file` config fallback (no `--append`).

- [ ] Add Markdown rendering regression tests: CLI HTML output snapshot and
  Web UI Markdown preview snapshot, run in CI to prevent the table-rendering
  bug from reappearing.

- [ ] Add large-file performance tests: parsing, filtering, and duplicate-ID
  detection on a 50,000-line file must each complete under 5 seconds.

- [ ] Add FastAPI test-client coverage for all `/api/*` routes when optional
  web dependencies are installed, including `/api/check-line` and `/api/graph`.

- [ ] Add `/api/check-line` tests: valid line returns `ok:true`; invalid line
  returns `ok:false` with error diagnostics; empty line returns `ok:true`.

- [ ] Add release process: changelog (`CHANGELOG.md`), semantic versioning
  policy (`MAJOR.MINOR.PATCH`), and a `make release` or CI workflow that
  tags, builds, and publishes to PyPI.

- [ ] Verify packaging on a clean environment: `pip install -e .`, optional
  extras (`[web]`, `[crypto]`, `[plot]`), console script entry points, and
  Windows PowerShell usage.

- [ ] Add `archive` tests: structure-preserving mode (comments in both files,
  empty sections retained), all three `--orphan-children` modes, `--dry-run`
  for each mode, `--block-on-external-refs`, and cross-file reference warning.

- [ ] Add `#!` directive wiring tests for `timezone`: verify datetime display
  is affected once timezone wiring is implemented.

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

- [ ] Add `check --ignore` tests: `--code` filter interaction (include-only
  overrides ignore for same code when both flags specified).

- [ ] Add `undo` edge-case tests: concurrent write isolation (two simultaneous
  quick-adds to the same file).

- [ ] Add `done` tests: ambiguous title match (interactive confirmation prompt).

- [ ] Add `summary` tests: counts match file contents for every type/status
  combination, missing-ID count is accurate, JSON schema is stable.

- [ ] Add `review` edge-case tests: mood trend most-common-first summary aggregation.

- [ ] Add dependency edge-case tests: cross-file blockers, and source metadata
  in blocked agenda records.

- [ ] Add `inbox --process` tests: prompts for project/due/assignee in sequence,
  each field correctly applied via `assist --update`.

- [ ] Add `assign` edge-case tests: ambiguous `--text` match (interactive
  confirm prompt), validation error when resulting line is invalid.

- [ ] Add `diff` tests: added, completed, canceled, status-changed,
  detail-changed items; filter scope; JSON output schema.

- [ ] Add `search` tests: cross-file glob, highlighted matches in text output.

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

- [ ] Add chart API tests: `/api/chart/tasks`, `/api/chart/habits`,
  `/api/chart/mood`, `/api/chart/elapsed` each return a stable JSON structure
  with `labels` and `datasets` arrays; `from`/`to`/`project`/`group` query
  parameters filter results correctly; empty data range returns empty datasets
  without error.

- [ ] Add graph API tests: `GET /api/graph` returns all nodes and edges for a
  known fixture; `?root=ID` returns only the reachable subgraph; `?depth=N`
  limits traversal; a fixture with a cycle does not cause infinite recursion.

- [ ] Add `links` tests for Mermaid/DOT: cross-file node references, titles
  with embedded quote characters.

- [ ] Add git API endpoint tests (with a real git repo fixture): `POST
  /api/git/pull` returns exit code and stderr; `POST /api/git/commit` with a
  message creates a commit; endpoints return 403 when `git.enable_api` is
  false; endpoints return 403 when accessed from a non-loopback address.

- [ ] Add `who` tests: same person has records in multiple files (latest wins).

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
- [ ] Consider a full Git server (e.g., Soft-serve or a Gitea-compatible
  endpoint) embedded in `serve` for teams who cannot use GitHub/GitLab. Only
  worth implementing if the lightweight `/api/git/*` subprocess endpoints
  prove insufficient for multi-user workflows; defer until there is concrete
  demand.
- [ ] Consider graph layout presets in the browser GUI graph panel: `LR`
  (left-to-right hierarchy), `TB` (top-to-bottom), and `force` (physics-based
  for non-hierarchical graphs). Let the user switch layouts without reloading.
- [ ] Consider exporting the dependency graph as an SVG or PNG from the
  browser GUI (using the Cytoscape.js export API) so users can share the graph
  without running the server.

### Security
- [ ] Consider asymmetric encryption (public/private key) for `encrypt` to
  support multi-user scenarios where different people encrypt but only the
  key holder can decrypt.

### Ecosystem
- [ ] Consider import/export adapters beyond ICS: org-mode, Todoist CSV, and
  mailbox/message logs, after the preset mechanism in `import-ics` is stable.
- [ ] Consider a static HTML export mode (`serve --export DIR`) that writes
  a read-only snapshot of the GUI without requiring the server to keep running.