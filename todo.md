# lifetxt TODO / Roadmap

Last updated: 2026-07-19 (updated x75)

This roadmap tracks remaining work after the current prototype updates and the next-feature planning pass. Completed items are removed. Existing `timer start` / `timer stop`, Web API / Web UI, and stdio MCP support are treated as baseline features; this file tracks stabilization, expansion, validation, documentation, and design work that still matters.

Priority guide:

- `P0`: Stabilize features that are already implemented and likely to break in real use.
- `P1`: Implement or refine core features that affect the format, CLI, API, MCP, or daily workflow.
- `P2`: Improve usability, documentation, packaging, long-term maintainability, and ecosystem fit.
- `Deferred`: Useful ideas that should not block the next practical release.

Design principles:

- Work backward from observed problems; do not add complex mechanisms only because they are imaginable.
- Fail loudly when behavior is ambiguous or data may be lost.
- Prefer existing infrastructure: git, detail fields, JSON Schema, shared mutation paths, and standard file formats.
- Keep CLI, Web API, Web UI, MCP, editor support, and documentation synchronized.

---

## P0: Stabilization and Data Safety

Items in this section are already implemented or foundational enough that they should be verified or hardened before the next release.

- [ ] Test on the Python versions CI actually runs. The CI failure that went unnoticed from 2026-07-12 to 2026-07-19 was Linux-only: `curses` imports successfully there even with no terminal attached, so `run_curses_or_plain` called `curses.wrapper()` and `cbreak()` failed, while on Windows the import failed first and silently took the plain path. Local development runs Python 3.6 on Windows; CI runs 3.10/3.11/3.12 on Ubuntu. Add a documented way to run the suite against a CI-like environment before pushing (Docker, WSL, or `py -3.12`).
- [ ] Make CI failures visible. Three consecutive weeks of red CI went unnoticed; consider a status badge in `readme.md` and/or failure notifications.
- [ ] Add a CI job that runs the suite without the optional web dependencies. Every web test guards with `skipTest`, but one had lost its guard and only failed for contributors without the extras installed; a no-extras job would catch the next one.
- [ ] Verify the new `tui` workspace in real terminals across WSL, Windows Terminal, and native macOS/Linux. The interactive path is covered by a stub-curses test but has never run against a real curses build; confirm the input bar cursor position, command palette rendering, `--glyphs auto` degradation on legacy code pages, color themes, narrow-terminal column dropping, and auto-reload with a human at a real TTY.
- [ ] Give the `tui` editing commands content-hash CAS. `_mutate_rows` in `lifetxt/tui_app.py` is now the single TUI write path for `/done`, `/status`, `/set`, `/due`, `/assign`, `/delete`, and `/timer`, and it validates the whole batch before writing, but it still reads through `fzf_helper` / `timer` helpers with no hash check, so an external edit between reload and write is silently overwritten. Fold it into the project-wide shared mutation layer rather than adding a second CAS implementation.
- [ ] Replace the TUI session undo stack with the shared mutation journal. It currently snapshots whole files per operation, which is correct but memory-hungry on large files and cannot be shared with CLI or Web undo.
- [ ] Add a screenshot or asciinema capture of the `tui` workspace for the docs. The written description in `docs/en/cli.md` and `docs/ja/cli.md` is now detailed but there is no visual reference.
- [ ] Verify `lifetxt fzf` and `inbox --fzf` with actual `fzf` and `peco` binaries on Windows PowerShell and Unix-like shells. Confirm preview rendering plus `show`, `done`, `delete`, and `edit` actions end-to-end.
- [ ] Verify `notify --email` against real SMTP providers in a safe test account. Confirm STARTTLS, authentication failure messages, multiple comma-separated recipients, `--watch` seen-state behavior after successful send, and app-password guidance.
- [ ] Verify weekly and monthly Web chart rendering in a real browser. Confirm Chart.js labels, bucket boundaries, empty data behavior, and meaningful Y-axis labels.
- [ ] Add browser-level smoke tests for the Web UI. Cover raw import live parse preview, detail modal message replies, occurrence badges, kiosk change highlighting, display-mode entry/exit, display light/dark palette snapshots, `+ New` tooltip viewport collision, browser Back/Forward cleanup for kiosk/display CSS state, Timeline empty states for today/24h/week, Timeline `ongoing` clipped records, search highlighting, command palette actions, undo toast restore, keyboard navigation, inline status cycling, export buttons, graph layout switching, modal focus trapping, and the current single-content router views.
- [ ] Fix timezone-offset data loss as a P0 data-safety issue. `timeutil.parse_datetime` must not convert an offset-aware value to the execution machine's local timezone and then drop `tzinfo`; preserve enough offset/aware information for `to-json` -> `from-json` round-trip and normalize only for comparisons.
- [ ] Add a round-trip golden corpus before expanding `fmt`, LSP, or `check --fix`. Start with the known `body:"inline" body:"second"` plus `|` continuation case that currently serializes into one fused value on reparse; decide whether repeated `body:` is invalid or has a lossless canonical representation.
- [ ] Add lock files and a shared mutation layer on top of the shared atomic write helper. Use one mutation path for CLI, Web API, MCP, background watchers, and future timer/alarm actions.
- [ ] Add content-hash compare-and-swap protection to all writes before or alongside lock files. Capture the file hash at read time and abort loudly if the content changed before write; apply the same principle to CLI, Web API, MCP, notification seen-state, timer state, and undo/archive operations.
- [ ] Add concurrent-write tests for quick add, item update, MCP write, notification acknowledgement, timer update, and archive operations. Fail loudly when the file changes between read and write.
- [ ] Review the new `source` field on agenda records for public Web deployments. `agenda_records` now sets `record["source"]` (webapp.py already read it, and without it every TUI agenda row was read-only), so `/api/agenda`, `agenda --format json`, and MCP agenda output now include the originating file path. Decide whether read-only or public servers should strip or relativize it.
- [ ] Audit the other row builders for the same missing-source class of bug. `_status_row` in `lifetxt/tui.py` takes `source` from the status record; confirm `latest_status_records` populates it, otherwise status rows are silently uneditable in the TUI the way agenda rows were.
- [ ] Harden public Web deployments beyond startup checks. Git/admin subprocess routes must not rely on `request.client.host` loopback checks behind reverse proxies; add trusted-proxy and disabled-by-default controls.
- [ ] Define the next release gate explicitly: timezone round-trip safety, shared mutation path with CAS, round-trip golden corpus, CI, packaging metadata cleanup, and published JSON Schema are blockers; timer expansion and decorative Web UI work are not.
- [ ] Verify the new repeat-completion flow end-to-end on real files: `complete` materialization across `repeat_base: due|done`, `done habit` logging, MCP `complete_item`, undo after completion, and interaction with archive. These shipped recently and are the most likely new-feature breakage.

---

## P1: Format and Data Semantics

Design decisions that affect the file format, parser, serialization, and every downstream tool. Resolve these before adding features that depend on them.

- [ ] Finalize timezone-aware datetime round-trip rules. Specify how naive datetimes are stored and interpreted, how `#! timezone:` and config `defaults.timezone` affect display and filtering, and how JSON/JSONL/CSV import and export preserve timezone information without silent data loss.
- [ ] Wire `#! timezone:` into datetime display and filtering for agenda, summary, stats, review, Web API, and MCP. Add tests that cover timezone-suffixed values, naive values, file directives, config defaults, and CLI overrides.
- [ ] Decide which item types should recommend `elapsed:`. Determine whether events, status records, journal entries, reminders, and future timer session records should record elapsed time, and add type-specific guidance to the format spec.
- [ ] Finalize occurrence materialization rules for life.txt output files. Specify how generated recurrence occurrences may be written to `.life.txt` or `.generated/*.life.txt` without confusing them with stored source items.
- [ ] Support `BYDAY` RRULE values in `complete` / `complete_item` next-occurrence materialization. Currently `next_repeat_occurrence()` fails loudly and asks for a manual due-date edit; decide the intended next-match rule (e.g. next matching weekday) before implementing.
- [ ] Fail loudly on same-day double completion. `complete` and `done habit` should reject a second completion for the same instance or date with a clear error, and allow an explicit `--force` overwrite; a silent no-op hides typos in the target ID or date.
- [ ] Specify the completion date boundary rule. A completion recorded after midnight defaults to the local calendar date, and an explicit date argument always wins; never guess timezones to reassign the day.
- [ ] Add a `format_version` file directive and a versioning policy for the format spec. `migrate` already exists but has no version anchor to migrate from or to; define how unversioned files are treated and when `check` warns about stale versions.
- [ ] Decide how `count:` interacts with `complete` materialization. `next_repeat_occurrence()` currently ignores `count:` (it only stops at `until:`) because nothing tracks how many instances have already been completed; either derive a count from archived/completed sibling instances or document that `count:` only bounds agenda's virtual expansion, not real completions.
- [ ] Specify multi-file semantics. Define ID uniqueness scope, cross-file link resolution, glob ordering, archive interactions, source-file metadata, and write-file selection when multiple files are loaded.
- [ ] Specify Unicode, encoding, and newline rules. Normalize comparison-sensitive fields to NFC, require UTF-8 without BOM and LF line endings for canonical output, and add `check` diagnostics for non-canonical encodings and newline forms.
- [ ] Define `LIFETXT_CANON_V1` as a named canonical form. Specify detail key ordering, whitespace, quoting rules, repeated-key ordering, continuation-line representation, LF endings, UTF-8, and NFC so `fmt --canonical`, golden corpus comparisons, JSON/CSV export, and future merge tooling have a stable byte-level target.
- [ ] Specify case-sensitivity rules for detail keys, tags, IDs, contexts, users, and projects. Make parser, filters, docs, completion, and editor support agree.
- [ ] Document `#!` metadata directive placement rules. Directives must appear contiguously before the first item, and the spec should include the resolution order across CLI flags, config, file directives, and built-in defaults.
- [ ] Add JSON Schema definitions for JSON, JSONL, Web API payloads, and MCP tool outputs. Publish schemas under a stable `dist/` path, give them HTTPS `$id` values, and validate golden corpus exports in CI.

---

## P1: Timer System Expansion

Existing timer support should grow from basic start/stop tracking into a coherent local productivity subsystem shared by CLI, Web UI, Web API, and MCP.

- [ ] Decide the timer scope boundary before adding more stateful features. Treat `start` / `stop` / `pause` / `resume` / `elapsed:` updates as the core plain-text workflow, and explicitly justify or defer alarm, Pomodoro, parallel timers, and crash-recovery complexity.
- [ ] Design a timer state model that supports stopwatch sessions, alarms, Pomodoro-style intervals, pause/resume, cancellation, completion, and optional association with a life.txt item ID.
- [ ] Add the remaining timer CLI commands: `timer alarm`, `timer pomodoro`, and `timer log`. `timer status`, `timer pause`, `timer resume`, `timer cancel`, and `timer summary` are implemented; keep `timer start` / `timer stop` as the simplest path.
- [ ] Support arbitrary Pomodoro profiles. Allow configurable focus length, short break length, long break length, cycle count, auto-start policy, notification behavior, and optional project/item defaults.
- [ ] Add alarm support. Allow one-shot alarms by absolute time or relative duration, store enough state to survive process restarts, and fail loudly when the requested time is ambiguous.
- [ ] Add stopwatch mode for ad-hoc measurement without requiring a task ID. Let users optionally attach the resulting elapsed time to an item later.
- [ ] Decide whether named or multiple parallel timers belong in P1 or should remain deferred. If implemented, define conflict rules for writing `elapsed:` to the same item from multiple active timers.
- [ ] Define how timer sessions are persisted. Decide between a state file, life.txt session records, or both. Include crash recovery, stale timer detection, and portability across machines.
- [ ] Add notification hooks for timer events. Support terminal output first, then optional desktop notification, Web UI toast, email, and future webhook channels through the shared notification backend.
- [ ] Add timer summary and statistics. Show active timer, current interval, total elapsed today, elapsed by project, and completed Pomodoro cycles through CLI, Web UI, Web API, and MCP.
- [ ] Add timer tests. Cover duration normalization, pause/resume math, crossing midnight, timezone display, crash recovery, concurrent writes, state-file corruption, and cross-platform file locking.
- [ ] Add timer documentation. Include start/pause/stop, stopwatch, alarm, Pomodoro profiles, item-linked elapsed updates, crash recovery, and examples for both CLI and Web UI.

---

## P1: Timer Web UI / Web API / MCP

The timer feature should be controllable from every user-facing surface while sharing one backend state model.

- [ ] Re-scope Timer Web/API/MCP expansion before implementing new surfaces. Keep existing start/stop/elapsed workflows stable first, and move alarm/Pomodoro/global panel work to Deferred unless there is a concrete daily-use requirement that justifies persistent-process complexity.
- [ ] Add Web API endpoints for timer operations: status, start, stop, pause, resume, cancel, create alarm, create Pomodoro session, list recent sessions, and attach elapsed time to an item.
- [ ] Add an inline timer control to the Web UI detail modal for task-like items. Provide start, pause, resume, stop, and cancel actions that update `elapsed:` through the existing item update path.
- [ ] Add a global timer panel to the Web UI. Show active stopwatch, active Pomodoro phase, next alarm, elapsed today, and quick controls without opening a record.
- [ ] Add Web UI alarm and Pomodoro setup flows. Use explicit fields instead of natural-language guessing, and preview the resulting schedule before starting.
- [ ] Add MCP timer tools. Include `timer_status`, `timer_start`, `timer_stop`, `timer_pause`, `timer_resume`, `timer_cancel`, `timer_alarm`, `timer_pomodoro`, and `timer_log`, all backed by the same mutation path as CLI and Web API.
- [ ] Make MCP timer writes safe by default. For actions that modify life.txt content, support proposal mode that returns a diff unless the client explicitly asks for a committed write.
- [ ] Add read-only mode behavior for timer surfaces. Decide whether read-only Web/MCP servers may show timer state, and ensure they cannot mutate life.txt or timer state unless explicitly configured.
- [ ] Document the timer API and MCP tools with request/response examples, error cases, and client configuration snippets.

---

## P1: CLI Core Improvements

Improvements to existing commands that affect daily workflow.

- [ ] Add `--last-week`, `--last-month`, and `--year` convenience selectors to `review`. Implement shared range selectors in `review.resolve_review_range` so CLI, Web API, and MCP accept the same range names.
- [ ] Extend `inbox --fzf` from selection-only output to optional follow-up actions after selector verification is complete. Support `show`, `assign`, `done`, and `edit` without bypassing validation or atomic writes.
- [ ] Add clipboard capture and an `--edit` ($EDITOR) flow to `quick`, or a dedicated `lifetxt capture` wrapper. `quick -` already reads a single title line from stdin through the existing safe write path; clipboard support and multi-line `$EDITOR` composition are still missing.
- [ ] Keep date-token parsing intentionally small and explicit. Support a documented closed set such as `today`, `tomorrow`, weekdays, and relative offsets; reject unrecognized natural-language dates instead of guessing.
- [ ] Promote `context:` to a first-class filter. Accept `--context` in `filter`, `agenda`, `next`, Web API, MCP, and shell completion. Prompt for context during inbox processing.
- [ ] Add `lifetxt next`. Show actionable open tasks that are not blocked and not someday/maybe, sorted by priority, due date, and age. Reuse existing filter logic where possible.
- [ ] Add `lifetxt habit today`. Materialize today's habit checkboxes from repeat-enabled habit definitions, idempotent per habit and date, with `--dry-run` support.
- [ ] Add `lifetxt invoice`. Aggregate `elapsed:` per project for a billing period, support rates and rounding, and output Markdown and CSV.
- [ ] Add `lifetxt standup`. Summarize done yesterday, planned today, and blocked work for a user, with text, Markdown, and Slack-ready output.
- [ ] Add `lifetxt fmt`. Normalize indentation, spacing, newline style, ordering where safe, and canonical detail formatting. Provide `--check` and `--diff` modes for CI and pre-commit use.
- [ ] Add `check --fix` for mechanical fixes that cannot change meaning. Start with key spelling normalization, whitespace, line endings, and canonical date forms.
- [ ] Add `depends_on` cycle detection to `check`, `health`, Web API, and MCP. Report the shortest cycle path and avoid undefined agenda ordering.
- [ ] Add a small shared query language before adding more per-surface filter flags. Support a closed grammar such as `tag:urgent AND NOT tag:archived AND due<2026-07-01`, fail loudly on unknown syntax, and reuse it for CLI `--query`, Web API, MCP, and named saved views.
- [ ] Use East Asian Width-aware column widths in CLI table output. `_format_table` in `lifetxt/cli.py` measures cell width with `len()`, so tables with Japanese titles misalign; reuse the `unicodedata.east_asian_width` logic already used by the TUI.
- [ ] Specify common CLI output behavior: `--json`, `--quiet`, `--verbose`, `--color=auto|always|never`, `NO_COLOR`, pager behavior, stdin `-`, and documented exit codes.

---

## P1: TUI Workspace Follow-ups

The workspace now covers navigation, filtering (`project`/`context`/`tag`/fuzzy),
row editing (`/status`, `/set`, `/due`, `/assign`, `/delete`), `/timer`,
`/export`, `/stats`, `/next`, `/goto`, searchable help, a two-pane wide layout,
and session persistence. These items extend it further.

- [ ] Add a `/filter` command backed by the shared query language once that grammar exists, so the TUI, CLI `--query`, Web API, and MCP resolve the same expressions instead of the TUI keeping its own fuzzy-only filter plus one flag per field. Every new `/context`-style command is a reason to build the grammar sooner.
- [ ] Add an in-place field editor. `/set KEY VALUE` covers scripted edits, but editing an existing value means retyping it; a small inline editor prefilled with the current value would cover the common case without leaving the session.
- [ ] Add multi-line body editing to the workspace. `/set body ...` cannot express continuation lines, so bodies still require `/edit` and `$EDITOR`.
- [ ] Add mouse support for row selection and tab switching behind a config flag. Terminal mouse reporting conflicts with terminal-native text selection, so it must be opt-in.
- [ ] Add `/timer pause` and `/timer resume`. The CLI already has them and the shared state file supports them; only the TUI commands are missing.
- [ ] Let `/export` reuse the CLI exporters. `render_export` in `lifetxt/tui_app.py` writes rows independently so the output matches the screen exactly, but Markdown and CSV shapes now exist in two places and can drift from `markdown.py` and `csvio.py`.
- [ ] Add an `editor` entry to `config init` output and to the config schema work. `resolve_editor` now reads a top-level `editor` key, but `lifetxt config init` does not emit it, so the Windows fallback is discoverable only from the docs and the error message.
- [ ] Verify `/edit` with a real terminal editor at a real TTY. The curses suspend/restore path (`def_prog_mode` / `endwin` / `reset_prog_mode` / `redrawwin`) is unit-tested only through a stub hook and has never run against a real curses build.
- [ ] Add a confirmation affordance better than `/delete yes`. Re-typing the command is safe but clumsy for bulk deletes; consider an inline confirm prompt in the input bar.
- [ ] Show which rows a bulk command will touch before it runs. `/done` with 30 marked rows currently gives no preview.
- [ ] Add a `/view` for archived records once multi-file semantics are specified.
- [ ] Reconsider the per-section row limit for sorted views. The limit now always applies and reports truncation, but for `/next` and `/sort due` a global "top N" may be more useful than a per-section cap.

---

## P1: Web API / Browser UI

### API Stability and Security

- [ ] Expand Web API documentation with full request and response examples for less-common routes, especially Git integration, timer endpoints, review, graph, blockers, parse, generated/read-only mode, and mutation error cases.
- [ ] Keep Web API default binding safe. Bind to localhost by default, document the security model, and require explicit configuration for non-localhost access.
- [ ] Add `--token-env` and config/env-based bearer-token loading. Public deployment recipes should never require putting tokens directly in command lines, config examples, or life.txt content.
- [ ] Publish and test OpenAPI output. Ensure it reflects read-only mode, write-file behavior, timer endpoints, review endpoints, and MCP-adjacent schemas.
- [ ] Add write-conflict detection before update and delete operations when multiple writers share a file. Return a clear conflict response instead of overwriting silently.
- [ ] Implement ETag / `If-Match` optimistic locking for item updates and deletes. Use a hash of the source text or source snapshot as the ETag, return `412 Precondition Failed` on mismatch, and reuse the same hash model for MCP write proposals and CLI CAS checks.

### Record Display and Undo

- [ ] Preserve original line position when Web UI Undo restores a deleted item. Avoid re-appending restored raw lines at the end of the writable file when the original context is available.
- [ ] Add a multi-level undo history to the Web UI. The undo toast currently covers only the most recent write; keep a small session-scoped stack so several consecutive mistakes can be reverted in order.
- [ ] Design an append-only mutation journal at `.cache/lifetxt/journal.jsonl`. Record `{op, before, after, surface, ts, file_hash}` for CLI, Web API, MCP, and background writes so multi-level undo, audit trails, sync debugging, and MCP source metadata share one durable primitive.
- [ ] Add source-file and line-position metadata to detail views when multiple files are loaded. Make write targets explicit when editing cross-file results.
- [ ] Improve long-body and Markdown previews in the detail modal. Keep CLI HTML rendering and Web UI rendering consistent through shared code.

### Graph and Dependencies

- [ ] Add Mermaid and DOT tests for cross-file node references, special characters in IDs and titles, and scoped `--id` plus `--direction` rendering.
- [ ] Document the dependency graph end-to-end across `links`, `/api/graph`, MCP tools, and the browser panel.

### Dashboard, Focus, Review, Team, Timeline, and Status

- [ ] Deduplicate Review Markdown rendering between CLI, Web UI, digest, and MCP. Use one server-side renderer so exports stay byte-consistent.
- [ ] Complete the `?workspace=` / `?panel=` deprecation. The Web UI now emits a one-time console warning; after one release, remove the alias mapping in `currentView()` and the docs row.
- [ ] Fully expand `repeat`-enabled occurrences across the visible Calendar month. `/api/agenda` currently returns a capped set for daily/weekly repeats, so long-running habits show only a few cells; decide the expansion cap and share it with Timeline.
- [ ] Add a day-detail popover to the Calendar view. Clicking a day (or its `+N more`) should optionally open an in-place list with quick-add for that date instead of jumping to Agenda.

### Accessibility and Internationalization

- [ ] Audit redesigned UI color contrast for WCAG AA in both themes. Include badges, muted text, kiosk header, presence dots, Calendar entry chips, and timer state indicators.
- [ ] Extend the Web UI label dictionary. `web.language` / `?lang=` cover core chrome strings; add the remaining Calendar, accessibility-toggle, and empty-state labels, and document the supported languages.
- [ ] Add browser-level tooltip placement tests for the Web UI. Cover topbar buttons, workspace tabs, Timeline and Calendar controls, editor field help, small viewports, keyboard focus, and clipped-window edge cases.

---

## P1: Notifications and Background Watch

Hygiene for `notify`, `notify --watch`, and future timer/alarm delivery. Independent of other features but easy to trip over in daily use.

- [ ] Add quiet-hours configuration. Suppress non-urgent notification delivery inside a configured local-time window and deliver a catch-up summary when the window ends.
- [ ] Add configurable snooze duration presets shared by CLI, Web UI, Web API, and MCP snooze actions.
- [ ] Persist acknowledgement and seen state across watcher restarts. A restarted `notify --watch` must not re-deliver already-acknowledged messages.
- [ ] Abstract the notification delivery backend. Support terminal output, `notify-send`, macOS `osascript`, and Windows toast behind one interface, with email and Web UI toast as existing channels; fail loudly when the selected backend is unavailable.
- [ ] Add acknowledgeable recurring reminders. A repeat-enabled reminder record should re-notify on schedule until acknowledged, with the acknowledgement recorded through the same persisted seen-state as messages.
- [ ] Add optional HTML multipart rendering to email notifications and digests. Keep plain text as the default and canonical form.

---

## P1: MCP Expansion and AI Integration

The existing stdio MCP server should become a safer, more complete interface for AI clients without losing the local-first file model.

- [ ] Align MCP tool input and output with JSON Schema definitions. Validate tool responses against the same schemas used for JSON export and Web API payloads.
- [ ] Add or refine MCP tools for search, review, next actions, standup summary, workload summary, habit streaks, dependency graph, blockers, and timer control.
- [ ] Make proposal mode the default for destructive or ambiguous MCP writes. Return a structured diff that can be applied by a human-approved `lifetxt apply` or equivalent command.
- [ ] Align MCP proposal diffs with a reusable JSON Patch-style structure. Keep it compatible with future `lifetxt diff`, JSON Schema `$id` publication, and cross-project AI context tooling instead of inventing a chat-only diff shape.
- [ ] Require MCP-created records to include source metadata such as `source:mcp`, unless the user explicitly disables it.
- [ ] Generate IDs on the lifetxt side, not in the AI client. Avoid trusting AI-generated IDs for write operations.
- [ ] Re-check file mtime and content hash before every MCP write. Return a conflict error if the file changed after the MCP client read it.
- [ ] Ensure MCP, CLI, and Web API use one internal mutation path. Do not duplicate validation, ID generation, link checks, timer updates, or atomic-write behavior across surfaces.
- [ ] Add MCP read-only mode tests. Confirm read tools still work and write tools return clear errors.
- [ ] Add MCP edge-case tests for `get_review`, timer tools, search, cross-file items, empty files, invalid ranges, read-only mode, and conflict handling.
- [ ] Publish ready-to-copy MCP client configuration snippets for Claude Desktop, Cursor, VS Code, and local-only multi-file use. Include read-only and write-enabled examples.
- [ ] Add `docs/en/ai-integration.md` and `docs/ja/ai-integration.md`. Cover MCP setup, local LLM privacy patterns, CLI pipe patterns, JSON review prompts, and GitHub Actions summaries.

---

## P1: Multiple Files, Sync, and External Tools

- [ ] Document the recommended directory layout: `life.txt` for hand-written data, `.generated/` for sync output, `archive/` for archived items, and `.cache/lifetxt/` for undo, backup, timer, and notification state.
- [ ] Define integration boundaries for calendar sources beyond ICS and for presence/message tools such as Teams, Discord, and Slack. Specify which fields are imported, exported, or read-only.
- [ ] Define conflict policy for `sync-ics --merge-existing`. Decide whether local edits inside generated records are overwritten, preserved by selected keys, or reported as conflicts before replacement.
- [ ] Add `to-ics` export. Preserve event times, all-day events, attendees where safe, recurrence where supported, and source UID metadata.
- [ ] Add a todo.txt import preset. Markdown checkbox import already exists as `from-markdown`; map todo.txt priority, contexts, projects, and completion dates, generate stable IDs where possible, and avoid duplicates on re-run.
- [ ] Add `from-markdown --preset github`. Map GitHub-flavored issue and task-list conventions (checkbox state, `#123` references, assignee mentions) onto the standard import path.
- [ ] Add usage examples for `.pre-commit-hooks.yaml` and `.pre-commit-config.yaml`. Document matched file patterns and recommended hooks.
- [ ] Document that secret URLs and tokens must not be stored in life.txt content. Use environment-variable patterns such as `--url-env` and `--key-env` instead.
- [ ] Add named filters or saved views in config. Let CLI, Web UI, Web API, and MCP resolve the same named filter definitions.
- [ ] Decide whether `--config paths` should auto-load default file sets when no file arguments are given.

---

## P1: Validation and Health Diagnostics

Diagnostics added to `check`, `health`, `doctor`, Web API, and MCP should catch common mistakes before data is lost.

- [ ] Add diagnostics for Unicode normalization, BOM usage, CRLF when canonical LF is required, mixed tabs/spaces in indentation, and invalid directive placement.
- [ ] Add diagnostics for duplicate IDs across configured files and archives. Provide an `ids --include-archive` or equivalent workflow.
- [ ] Add diagnostics for dangling links, cross-file references to archived records, dependency cycles, missing parents, and invalid hierarchy indentation.
- [ ] Add diagnostics for invalid timer state, stale active timers, corrupted timer state files, and elapsed values that cannot be normalized.
- [ ] Add diagnostics for config schema errors. Broken config should fail loudly with a clear path and key name.
- [ ] Add typo suggestions for unknown detail keys. For values such as `assginee:`, warn with the nearest known key candidates instead of silently accepting likely mistakes; keep auto-fix separate and conservative.
- [ ] Add `check --format json` as the stable diagnostics API before implementing LSP diagnostics. Include file, line, column/span where available, code, severity, message, and fix hints so editor integrations can be a thin wrapper over `check`.
- [ ] Add a diagnostic code catalog generated from parser and validator definitions. Include code, name, description, triggering example, and resolution hint.
- [ ] Add opt-in secret linting. Warn on likely tokens, access keys, `token=` query strings, long base64-like values, and private calendar URLs; document environment-variable patterns as the preferred fix.
- [ ] Document stable exit codes for validation errors, usage errors, write conflicts, environment failures, and internal errors.

---

## P1: LSP and Parser Foundation

Editor support should move beyond syntax highlighting while keeping the parser and spec authoritative.

- [ ] Add a lossless parser or CST mode that preserves source spans, comments, continuation lines, directive lines, and exact ranges. Treat this as the foundation for LSP, precise diagnostics, code actions, and formatting.
- [ ] Add `lifetxt lsp` as a Python-packaged language server. The VS Code extension should spawn it rather than reimplementing logic.
- [ ] Start LSP support with diagnostics using `check` logic and debounce. Keep errors consistent with CLI diagnostics.
- [ ] Add document symbols for sections, item trees, and major directives.
- [ ] Add completion for detail keys, statuses, type aliases, IDs, cross-file references, contexts, users, projects, and date snippets.
- [ ] Add hover information for due dates, repeat next occurrence, elapsed/estimated progress, linked items, dependency blockers, and timer state.
- [ ] Add code actions for status toggling, mechanical `check --fix` repairs, adding missing IDs, and safe detail-key normalization.
- [ ] Add go-to-definition and references for IDs and dependency links. Leave rename as a later feature because it requires workspace-wide edits.
- [ ] Keep full-file reparsing until performance problems are observed on realistic files.

---

## P2: CLI Power User Commands

- [ ] Extend `template` beyond config-defined templates. Consider supporting a `templates.life.txt` file with a reserved template marker for teams that prefer version-controlled templates.
- [ ] Add `lifetxt show <id>` to display one item with resolved links, source file, hierarchy context, and dependent records.
- [ ] Add `lifetxt edit <id>` to open the target item in `$EDITOR` at the correct line.
- [ ] Add `lifetxt path` to display resolved default file paths and config paths for debugging.
- [ ] Extend `lifetxt demo` with named profiles such as `minimal`, `team`, `calendar`, `status`, `messages`, `journal`, and `stress`. Add an optional `--serve` mode that launches the Web UI against a temporary generated file and clearly marks that no real user data is being changed.
- [ ] Add count and aggregation commands such as `count --by status|tag|person|project|context`.
- [ ] Extend `batch` beyond `done` and `assign`. Add safe bulk operations such as tag rename, status set, and due-date shift, all through the shared mutation path with `--dry-run` support.
- [ ] Add `who --workload` for a per-person workload summary. Show open, due-soon, and overdue counts per assignee in CLI and Web API output.
- [ ] Add `review --someday` to list `[?]` someday/maybe items untouched for longer than a threshold, so periodic reviews surface stale ideas.
- [ ] Add `quick --journal` journal prompts. Open `$EDITOR` prefilled with a dated journal skeleton and append the result as a `J` record through the safe write path.
- [ ] Add sort-key options for `filter` and `agenda`, such as `--sort due,priority`.
- [ ] Consider git auto-commit for mutations through config. Use git as a durable recovery mechanism while keeping built-in undo and backups documented.
- [ ] Add `lifetxt diff` for ID-level semantic diffs before building a custom git merge driver. Compare records by ID, show changed details and body values, and handle moved records separately from content changes.
- [ ] Consider a custom git merge driver that resolves item-level changes by ID for shared repositories.

---

## P2: Editor Support

- [ ] Package VS Code grammar and snippets as a proper extension installable from the Marketplace or with `code --install-extension`.
- [ ] Keep editor file-association documentation current for `life.txt`, `*.life.txt`, and `*_life.txt`.
- [ ] Generate VS Code snippet key lists from `lifetxt/model.py` to prevent drift between the editor extension, CLI completion, and the spec.
- [ ] Add highlight snapshot tests for title, status, type, detail key, quoted value, body continuation, line continuation, directive lines, and encrypted values.
- [ ] Add editor support for metadata directive lines. Highlight them distinctly from ordinary comments and add snippets for common directive combinations.
- [ ] Add editor support for encrypted field values. Display `enc:` values distinctly and show a tooltip that the value is encrypted.
- [ ] Add snippets for task timer fields, events with attendees, status records, messages with notification, journal entries with mood, linked subtasks, and template records.
- [ ] Add folding ranges for sections and subtrees.
- [ ] Register file icons and language IDs for `.life.txt` patterns.

---

## P2: Documentation and Examples

- [ ] Resolve documentation synchronization policy. Decide which of `readme.md`, `docs/en/readme.md`, `docs/ja/readme.md`, and the format spec is authoritative for each topic.
- [ ] Add worked examples for timer, expanded timer modes, stats, TUI, fzf, git hooks, completion, archive, MCP, Web API, and Web UI workflows.
- [ ] Add recommended workflow docs for daily capture, inbox processing, team status sharing, notifications, calendar sync, weekly review, periodic archiving, and timer-based focus sessions.
- [ ] Add migration notes for every breaking or user-visible format change. Include command examples once migration support exists.
- [ ] Add screenshots or terminal captures for Web agenda, timer panel, TUI dashboard, stats weekly output, plot output, doctor output, Review view, Team view, Timeline view, and graph view.
- [ ] Document file-splitting strategies. Explain one-file-per-author, generated files, archive files, cache files, and what the tool enforces versus what is only a recommendation.
- [ ] Document archive command and workflow, including orphan-children handling, external reference safety, structure-preserving behavior, and dry-run usage.
- [ ] Document a "family board" kiosk recipe in `docs/en/web.md` and `docs/ja/web.md`. Cover a shared display setup: kiosk URL parameters, auto-refresh, presence, and a small config example.
- [ ] Document undo and backup behavior. Explain differences, recommended config for users without Git, and recovery steps after accidental writes.
- [ ] Expand CLI docs for all implemented commands that currently only have overview entries.
- [ ] Expand Web docs with statistics dashboard workflows, chart usage, item creation/editing, Git integration security, quick-add, command palette, undo toast, keyboard navigation, export, graph layout, detail modal actions, and timer UI.
- [ ] Add an English/Japanese documentation parity CI check. Compare headings, code blocks, command names, and key examples.
- [ ] Add a bilingual glossary for stable terms used in the spec, diagnostics, CLI output, and docs.

---

## P2: Tests, CI, and Release

- [ ] Expand CI after the minimal P0 workflow lands. Add the full Python 3.10/3.11/3.12 and Ubuntu/Windows/macOS matrix, coverage reporting, and optional dependency jobs without blocking the first safety-focused CI pass.
- [ ] Expand `scripts/smoke_test.py` into named smoke profiles. Add `--profile cli`, `--profile web`, `--profile mcp`, and `--profile release` so CI, local debugging, and release checks can run the right subset quickly.
- [ ] Add snapshot tests for important human-readable CLI output.
- [ ] Add sync tests comparing model constants with English and Japanese format specs, CLI completion, editor snippets, and docs examples.
- [ ] Add a guard against time-dependent test fixtures. TUI fixtures using a `due:` date near today drifted into the 12h agenda window as the clock advanced, so the same record appeared in both the tasks and agenda sections and assertions passed or failed depending on the hour. Fixtures are now pinned far in the future; consider injecting a fixed clock instead so the hazard cannot come back.
- [ ] Add cross-platform tests for paths with spaces, glob expansion, Windows line endings, CJK terminal width, shell completion, and Windows console behavior.
- [ ] Add glob input tests for `*.life.txt`, `*_life.txt`, directories, and `projects/**/*.life.txt` across all file-reading commands.
- [ ] Add parser edge-case tests for nested quotes, invalid continuations, mixed indentation, duplicate IDs, Unicode normalization, CRLF, emoji, multi-value fields, and empty files.
- [ ] Add parse-serialize-parse round-trip tests. Treat this as a prerequisite for `fmt`, LSP, code actions, and stable docs examples.
- [ ] Add Hypothesis/property-based round-trip tests. Generate random valid items, serialize them, parse them again, and assert semantic equivalence so repeated-key, quote, continuation, timezone, and body edge cases are discovered mechanically.
- [ ] Add parser fuzz tests and a backward-compatibility golden corpus.
- [ ] Add recurrence tests for simple repeat values, interval, until, count, long-range performance, occurrence export shapes, and repeat completion semantics.
- [ ] Add real-export fixture tests for Todoist CSV, GitHub issues, Markdown checkboxes, todo.txt, and future calendar export/import flows.
- [ ] Add large-file performance tests. Parsing, filtering, duplicate-ID detection, and core review aggregation on a 50,000-line file should meet documented thresholds.
- [ ] Add optional web dependency CI and FastAPI TestClient coverage for all `/api/*` routes, including timer endpoints and read-only behavior.
- [ ] Add Playwright or equivalent browser tests for core Web UI flows, including the View Guide actions, workspace tab keyboard navigation, guided empty states, and Team `View items` click-through.
- [ ] Add MCP integration tests that start the stdio server and exercise read, write-proposal, write-commit, read-only, timer, and conflict paths.
- [ ] Add release process documentation and automation: `CHANGELOG.md`, semantic versioning policy, build, tag, PyPI publishing, and post-release smoke checks.
- [ ] Verify packaging in a clean environment. Cover editable install, optional extras, console script entry points, Windows PowerShell usage, and zipapp or other single-file distribution if supported.
- [ ] Add CONTRIBUTING, issue templates, and pre-commit configuration.

---

## P2: Maintainability and Architecture

- [ ] Split browser static assets out of `lifetxt/webapp.py` before adding more complex Web UI features. Keep a build-free path if possible by serving package-data HTML/CSS/JS through StaticFiles or equivalent, but make JavaScript lintable and editor-friendly.
- [ ] Split `lifetxt/cli.py` into command-focused modules with a thin dispatcher. Keep the public CLI stable, move shared formatting/filter/mutation helpers into internal modules, and reduce the risk of unrelated command regressions.
- [ ] Add lightweight lint or syntax checks for extracted browser JavaScript once assets are split. This should run in CI without requiring a full frontend build chain.
- [ ] Decide the future of the optional Textual TUI path. The dependency-free workspace in `lifetxt/tui_app.py` is now the primary interface and is strictly richer than the Static-only Textual wrapper, which is only reached when curses is missing; either delete the Textual path or rebuild it on the shared `WorkspaceState` and frame model.
- [ ] Split `lifetxt/tui_app.py` into a `tui/` package. It now holds the state model, ~29 command handlers, key handling, frame building, session persistence, and the color palette in one module; commands and layout should become separate units so each is testable and reviewable in isolation.

---

## P2: Distribution, Environment, and Localization

- [ ] Raise the supported Python baseline to match reality. Move package metadata and docs toward Python `>=3.10`, verify dependencies such as FastAPI against that floor, and remove Python 2-era style where it obscures modern typing or warnings.
- [ ] Fix Python 3.12 import-time warnings. Audit parser and docs strings for invalid escape sequences and other warnings that pollute stderr during normal CLI or test runs.
- [ ] Follow XDG Base Directory conventions for global config where appropriate while preserving project-local configuration.
- [ ] Define precedence for project-local config and global config.
- [ ] Add config schema validation.
- [ ] Add week-start configuration for agenda, review, and Web calendar-style views.
- [ ] Add CLI message localization for English and Japanese. Keep stored data in ISO-oriented canonical forms; localize display only.
- [ ] Add locale-aware date display options without changing the saved datetime format.
- [ ] Verify Windows behavior for paths, PowerShell quoting, console encoding, notifications, file locks, and browser launch behavior.
- [ ] Generate man pages from CLI help.
- [ ] Add PowerShell to the bundled shell completions. bash, zsh, and fish completion plus the `completion install` helper already exist; Windows users currently get nothing.
- [ ] Consider zipapp or another single-file distribution path for users without a prepared Python environment.
- [ ] Consider a Homebrew formula after demand is observed.

---

## Deferred Ideas

Useful ideas that should not block near-term releases. Revisit after the corresponding P1 or P2 foundation is stable.

### Format and Parser

- [ ] Consider `#! import: PATH [as ALIAS]` for declared cross-file loading only if configured paths do not solve practical use cases.
- [ ] Consider namespace-qualified ID syntax only if flat cross-file ID resolution proves insufficient.
- [ ] Consider richer schema packages for external tools after JSON Schema output is stable.

### CLI and Background Services

- [ ] Consider named or multiple parallel timers if the single active timer remains too restrictive after the expanded timer model ships.
- [ ] Consider full alarm and Pomodoro management only after the plain-text timer workflow proves insufficient. Prefer OS notification tools or dedicated timer apps unless lifetxt-specific item linkage clearly adds value.
- [ ] Consider a small local daemon that unifies notification watch, timer status, alarm delivery, and file-reload events.
- [ ] Consider opt-in quick type inference from title text after explicit capture commands are stable.
- [ ] Consider `lifetxt todo-scan` to import `TODO`/`FIXME` source-code comments as tasks with file/line references.
- [ ] Consider a scheduled auto-archive rotation policy in config (for example, yearly) after manual `archive` usage patterns are observed.
- [ ] Consider template variables beyond date placeholders and a prompt mode for template expansion.
- [ ] Consider additional digest channels such as Teams webhook, Discord webhook, and desktop notification.
- [ ] Consider a community lint ruleset repository.

### Web, API, and MCP

- [ ] Consider MCP HTTP/SSE transport with token authentication for clients that cannot launch stdio commands directly.
- [ ] Consider making experimental or low-use Web UI surfaces read-only until their write paths have shared mutation, undo, conflict detection, accessibility, and browser tests.
- [ ] Consider server-side graph rendering so share and digest outputs can attach the same graph image without a browser.
- [ ] Consider a full embedded Git server only if lightweight Git subprocess endpoints prove insufficient.
- [ ] Consider static HTML export mode for the Web UI as a read-only snapshot.
- [ ] Consider PWA support for the Web UI: offline caching, home-screen install, and a mobile quick-capture screen, plus Web Share Target registration so text shared from other apps lands in the inbox. This is the most direct answer to mobile input friction, but it needs the Web calendar/quick-add surfaces and write-conflict detection to stabilize first.
- [ ] Consider interactive plot mode in TUI after plot output is stable.
- [ ] Consider integrating team presence into the TUI sidebar.

### Ecosystem and Security

- [ ] Consider asymmetric encryption for multi-user scenarios where different users encrypt but only selected key holders can decrypt.
- [ ] Consider richer import/export adapters after ICS, Markdown, Todoist, GitHub issues, and todo.txt coverage is stable: org-mode, mailbox logs, CalDAV, and richer bidirectional calendar/status integrations.
- [ ] Consider a plugin mechanism only after repeated integration requests cannot be handled through CLI, Web API, MCP, or import/export adapters.
