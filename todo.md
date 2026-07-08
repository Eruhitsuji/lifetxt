# lifetxt TODO / Roadmap

Last updated: 2026-07-08 (updated x61)

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

- [ ] Verify `tui` in real terminals across WSL, Windows Terminal, and native macOS/Linux. Confirm Vim-like keymaps, curses colors, narrow-terminal behavior, and auto-reload with a human at a real TTY.
- [ ] Verify `lifetxt fzf` and `inbox --fzf` with actual `fzf` and `peco` binaries on Windows PowerShell and Unix-like shells. Confirm preview rendering plus `show`, `done`, `delete`, and `edit` actions end-to-end.
- [ ] Verify `notify --email` against real SMTP providers in a safe test account. Confirm STARTTLS, authentication failure messages, multiple comma-separated recipients, `--watch` seen-state behavior after successful send, and app-password guidance.
- [ ] Verify weekly and monthly Web chart rendering in a real browser. Confirm Chart.js labels, bucket boundaries, empty data behavior, and meaningful Y-axis labels.
- [ ] Add browser-level smoke tests for the Web UI. Cover raw import live parse preview, detail modal message replies, occurrence badges, kiosk change highlighting, display-mode entry/exit, browser Back/Forward cleanup for kiosk/display CSS state, Timeline empty states for today/24h/week, search highlighting, command palette actions, undo toast restore, keyboard navigation, inline status cycling, export buttons, graph layout switching, modal focus trapping, and the current single-content router views.
- [ ] Audit untyped boolean query parameters across all FastAPI routes. Apply string-aware parsing or typed `bool` parameters to `/api/items`, `/api/messages`, `/api/agenda`, chart routes, and any remaining endpoints; add one regression test per route.
- [ ] Unify all mutating operations behind one atomic write path. Use write-temp plus rename, a lock file for concurrent writers, and a shared mutation layer for CLI, Web API, MCP, background watchers, and future timer/alarm actions.
- [ ] Add concurrent-write tests for quick add, item update, MCP write, notification acknowledgement, timer update, and archive operations. Fail loudly when the file changes between read and write.
- [ ] Add a release smoke-test runner that executes key CLI and Web API flows without running the full unit suite. Include timer state-file behavior, cross-platform paths, Web API write mode, read-only mode, and MCP startup.

---

## P1: Format and Data Semantics

Design decisions that affect the file format, parser, serialization, and every downstream tool. Resolve these before adding features that depend on them.

- [ ] Finalize timezone-aware datetime round-trip rules. Specify how naive datetimes are stored and interpreted, how `#! timezone:` and config `defaults.timezone` affect display and filtering, and how JSON/JSONL/CSV import and export preserve timezone information without silent data loss.
- [ ] Wire `#! timezone:` into datetime display and filtering for agenda, summary, stats, review, Web API, and MCP. Add tests that cover timezone-suffixed values, naive values, file directives, config defaults, and CLI overrides.
- [ ] Decide which item types should recommend `elapsed:`. Determine whether events, status records, journal entries, reminders, and future timer session records should record elapsed time, and add type-specific guidance to the format spec.
- [ ] Finalize occurrence materialization rules for life.txt output files. Specify how generated recurrence occurrences may be written to `.life.txt` or `.generated/*.life.txt` without confusing them with stored source items.
- [ ] Support `BYDAY` RRULE values in `complete` / `complete_item` next-occurrence materialization. Currently `next_repeat_occurrence()` fails loudly and asks for a manual due-date edit; decide the intended next-match rule (e.g. next matching weekday) before implementing.
- [ ] Decide how `count:` interacts with `complete` materialization. `next_repeat_occurrence()` currently ignores `count:` (it only stops at `until:`) because nothing tracks how many instances have already been completed; either derive a count from archived/completed sibling instances or document that `count:` only bounds agenda's virtual expansion, not real completions.
- [ ] Specify multi-file semantics. Define ID uniqueness scope, cross-file link resolution, glob ordering, archive interactions, source-file metadata, and write-file selection when multiple files are loaded.
- [ ] Specify Unicode, encoding, and newline rules. Normalize comparison-sensitive fields to NFC, require UTF-8 without BOM and LF line endings for canonical output, and add `check` diagnostics for non-canonical encodings and newline forms.
- [ ] Specify case-sensitivity rules for detail keys, tags, IDs, contexts, users, and projects. Make parser, filters, docs, completion, and editor support agree.
- [ ] Document `#!` metadata directive placement rules. Directives must appear contiguously before the first item, and the spec should include the resolution order across CLI flags, config, file directives, and built-in defaults.
- [ ] Add JSON Schema definitions for JSON, JSONL, Web API payloads, and MCP tool outputs. Publish schemas under a stable `dist/` path, give them HTTPS `$id` values, and validate golden corpus exports in CI.

---

## P1: Timer System Expansion

Existing timer support should grow from basic start/stop tracking into a coherent local productivity subsystem shared by CLI, Web UI, Web API, and MCP.

- [ ] Design a timer state model that supports stopwatch sessions, alarms, Pomodoro-style intervals, pause/resume, cancellation, completion, and optional association with a life.txt item ID.
- [ ] Add CLI commands for the expanded timer model: `timer status`, `timer pause`, `timer resume`, `timer cancel`, `timer alarm`, `timer pomodoro`, and `timer log`. Preserve the current `timer start` / `timer stop` behavior as the simplest path.
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

- [ ] Add `--last-week` and `--last-month` convenience flags to `review`. Implement shared range selectors in `review.resolve_review_range` so CLI, Web API, and MCP accept the same range names.
- [ ] Extend `inbox --fzf` from selection-only output to optional follow-up actions after selector verification is complete. Support `show`, `assign`, `done`, and `edit` without bypassing validation or atomic writes.
- [ ] Add clipboard capture and an `--edit` ($EDITOR) flow to `quick`, or a dedicated `lifetxt capture` wrapper. `quick -` already reads a single title line from stdin through the existing safe write path; clipboard support and multi-line `$EDITOR` composition are still missing.
- [ ] Keep date-token parsing intentionally small and explicit. Support a documented closed set such as `today`, `tomorrow`, weekdays, and relative offsets; reject unrecognized natural-language dates instead of guessing.
- [ ] Promote `context:` to a first-class filter. Accept `--context` in `filter`, `agenda`, `next`, Web API, MCP, and shell completion. Prompt for context during inbox processing.
- [ ] Add `lifetxt next`. Show actionable open tasks that are not blocked and not someday/maybe, sorted by priority, due date, and age. Reuse existing filter logic where possible.
- [ ] Add `lifetxt habit today`. Materialize today's habit checkboxes from repeat-enabled habit definitions, idempotent per habit and date, with `--dry-run` support.
- [ ] Add `lifetxt invoice`. Aggregate `elapsed:` per project for a billing period, support rates and rounding, and output Markdown and CSV.
- [ ] Add `lifetxt standup`. Summarize done yesterday, planned today, and blocked work for a user, with text, Markdown, and Slack-ready output.
- [ ] Add `lifetxt demo`. Start the Web UI against generated temporary sample data for selected personas and clearly mark that no real user files are being changed.
- [ ] Add `lifetxt fmt`. Normalize indentation, spacing, newline style, ordering where safe, and canonical detail formatting. Provide `--check` and `--diff` modes for CI and pre-commit use.
- [ ] Add `check --fix` for mechanical fixes that cannot change meaning. Start with key spelling normalization, whitespace, line endings, and canonical date forms.
- [ ] Add `depends_on` cycle detection to `check`, `health`, Web API, and MCP. Report the shortest cycle path and avoid undefined agenda ordering.
- [ ] Add `config show`. Display the effective merged config from defaults, global config, repo-local config, environment variables, file directives, and CLI overrides.
- [ ] Specify common CLI output behavior: `--json`, `--quiet`, `--verbose`, `--color=auto|always|never`, `NO_COLOR`, pager behavior, stdin `-`, and documented exit codes.

---

## P1: Web API / Browser UI

### API Stability and Security

- [ ] Expand Web API documentation with full request and response examples for less-common routes, especially Git integration, timer endpoints, review, graph, blockers, parse, generated/read-only mode, and mutation error cases.
- [ ] Keep Web API default binding safe. Bind to localhost by default, document the security model, and require explicit configuration for non-localhost access.
- [ ] Publish and test OpenAPI output. Ensure it reflects read-only mode, write-file behavior, timer endpoints, review endpoints, and MCP-adjacent schemas.
- [ ] Add write-conflict detection before update and delete operations when multiple writers share a file. Return a clear conflict response instead of overwriting silently.
- [ ] Add a Web API `POST /api/items/{id}/complete` route mirroring the CLI `complete` command and MCP `complete_item` tool (see `lifetxt/cli.py` `command_complete`, `lifetxt/agenda.py` `next_repeat_occurrence`, `lifetxt/mcp.py` `_tool_complete_item`), then add a Complete action to the Web UI detail modal for repeat-enabled items so all three surfaces stay in sync.

### Record Display and Undo

- [ ] Preserve original line position when Web UI Undo restores a deleted item. Avoid re-appending restored raw lines at the end of the writable file when the original context is available.
- [ ] Add source-file and line-position metadata to detail views when multiple files are loaded. Make write targets explicit when editing cross-file results.
- [ ] Improve long-body and Markdown previews in the detail modal. Keep CLI HTML rendering and Web UI rendering consistent through shared code.

### Graph and Dependencies

- [ ] Add a force-directed layout preset to the browser graph panel. Keep existing ring and layered layouts, and persist the selected layout per user or URL when appropriate.
- [ ] Add Mermaid and DOT tests for cross-file node references, special characters in IDs and titles, and scoped `--id` plus `--direction` rendering.
- [ ] Document the dependency graph end-to-end across `links`, `/api/graph`, MCP tools, and the browser panel.

### Dashboard, Focus, Review, Team, Timeline, and Status

- [ ] Deduplicate Review Markdown rendering between CLI, Web UI, digest, and MCP. Use one server-side renderer so exports stay byte-consistent.
- [ ] Compute real habit streaks in `lifetxt/review.py` from per-day completion data. Show current and longest streaks in CLI, Web UI, API, and MCP review output.
- [ ] Deprecate the legacy `?workspace=` URL alias after one release. Emit a console warning first, then remove the mapping and docs row.
- [ ] Make presence state colors configurable through `web.presence.states`, merged over default regex rules.
- [ ] Order and pin Team board cards by configured user order or `web.team.pin`, then sort remaining users alphabetically.
- [ ] Add a per-person click-through from Team board cards to a filtered Items view.
- [ ] Add a guided empty state when zero items load. Offer first task creation, import documentation, demo mode, and docs links.
- [ ] Add days-remaining countdowns to agenda output and Web Dashboard cards for upcoming due items.

### Accessibility and Internationalization

- [ ] Perform a Web UI accessibility pass. Add tablist semantics, arrow-key view navigation, `aria-live` regions for toasts and notifications, a skip-to-content link, and visible focus coverage.
- [ ] Audit redesigned UI color contrast for WCAG AA in both themes. Include badges, muted text, kiosk header, presence dots, and timer state indicators.
- [ ] Honor `prefers-reduced-motion`. Disable kiosk auto-scroll, skeleton shimmer, timer animations, and modal transitions when appropriate; add a config override.
- [ ] Add a high-contrast theme using the existing theme-token approach.
- [ ] Add a Web UI label dictionary with `web.language` and `?lang=` for static chrome strings. Keep user item content untranslated.
- [ ] Expand contextual hover/focus help across advanced Web UI controls. Prioritize filters, export, agenda blocked mode, graph layout, notification permission, raw import, and destructive actions; keep the help short enough for pointer and keyboard users.

---

## P1: MCP Expansion and AI Integration

The existing stdio MCP server should become a safer, more complete interface for AI clients without losing the local-first file model.

- [ ] Align MCP tool input and output with JSON Schema definitions. Validate tool responses against the same schemas used for JSON export and Web API payloads.
- [ ] Add or refine MCP tools for search, review, next actions, standup summary, workload summary, habit streaks, dependency graph, blockers, and timer control.
- [ ] Make proposal mode the default for destructive or ambiguous MCP writes. Return a structured diff that can be applied by a human-approved `lifetxt apply` or equivalent command.
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
- [ ] Add import presets for todo.txt and Markdown checkboxes. Generate stable IDs where possible and avoid duplicates on re-run.
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
- [ ] Add a diagnostic code catalog generated from parser and validator definitions. Include code, name, description, triggering example, and resolution hint.
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
- [ ] Add count and aggregation commands such as `count --by status|tag|person|project|context`.
- [ ] Add sort-key options for `filter` and `agenda`, such as `--sort due,priority`.
- [ ] Consider git auto-commit for mutations through config. Use git as a durable recovery mechanism while keeping built-in undo and backups documented.
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
- [ ] Document undo and backup behavior. Explain differences, recommended config for users without Git, and recovery steps after accidental writes.
- [ ] Expand CLI docs for all implemented commands that currently only have overview entries.
- [ ] Expand Web docs with statistics dashboard workflows, chart usage, item creation/editing, Git integration security, quick-add, command palette, undo toast, keyboard navigation, export, graph layout, detail modal actions, and timer UI.
- [ ] Add an English/Japanese documentation parity CI check. Compare headings, code blocks, command names, and key examples.
- [ ] Add a bilingual glossary for stable terms used in the spec, diagnostics, CLI output, and docs.

---

## P2: Tests, CI, and Release

- [ ] Add a CI pipeline for unit tests, compile checks, and example file validation on every push. Run on Python 3.10, 3.11, and 3.12 across Ubuntu, Windows, and macOS.
- [ ] Add snapshot tests for important human-readable CLI output.
- [ ] Add sync tests comparing model constants with English and Japanese format specs, CLI completion, editor snippets, and docs examples.
- [ ] Add cross-platform tests for paths with spaces, glob expansion, Windows line endings, CJK terminal width, shell completion, and Windows console behavior.
- [ ] Add glob input tests for `*.life.txt`, `*_life.txt`, directories, and `projects/**/*.life.txt` across all file-reading commands.
- [ ] Add parser edge-case tests for nested quotes, invalid continuations, mixed indentation, duplicate IDs, Unicode normalization, CRLF, emoji, multi-value fields, and empty files.
- [ ] Add parse-serialize-parse round-trip tests. Treat this as a prerequisite for `fmt`, LSP, code actions, and stable docs examples.
- [ ] Add parser fuzz tests and a backward-compatibility golden corpus.
- [ ] Add recurrence tests for simple repeat values, interval, until, count, long-range performance, occurrence export shapes, and repeat completion semantics.
- [ ] Add real-export fixture tests for Todoist CSV, GitHub issues, Markdown checkboxes, todo.txt, and future calendar export/import flows.
- [ ] Add large-file performance tests. Parsing, filtering, duplicate-ID detection, and core review aggregation on a 50,000-line file should meet documented thresholds.
- [ ] Add optional web dependency CI and FastAPI TestClient coverage for all `/api/*` routes, including timer endpoints and read-only behavior.
- [ ] Add Playwright or equivalent browser tests for core Web UI flows.
- [ ] Add MCP integration tests that start the stdio server and exercise read, write-proposal, write-commit, read-only, timer, and conflict paths.
- [ ] Add release process documentation and automation: `CHANGELOG.md`, semantic versioning policy, build, tag, PyPI publishing, and post-release smoke checks.
- [ ] Verify packaging in a clean environment. Cover editable install, optional extras, console script entry points, Windows PowerShell usage, and zipapp or other single-file distribution if supported.
- [ ] Add CONTRIBUTING, issue templates, and pre-commit configuration.

---

## P2: Distribution, Environment, and Localization

- [ ] Follow XDG Base Directory conventions for global config where appropriate while preserving project-local configuration.
- [ ] Define precedence for project-local config and global config.
- [ ] Add config schema validation.
- [ ] Add week-start configuration for agenda, review, and Web calendar-style views.
- [ ] Add CLI message localization for English and Japanese. Keep stored data in ISO-oriented canonical forms; localize display only.
- [ ] Add locale-aware date display options without changing the saved datetime format.
- [ ] Verify Windows behavior for paths, PowerShell quoting, console encoding, notifications, file locks, and browser launch behavior.
- [ ] Generate man pages from CLI help.
- [ ] Bundle shell completion for bash, zsh, and fish, with an optional install helper.
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
- [ ] Consider a small local daemon that unifies notification watch, timer status, alarm delivery, and file-reload events.
- [ ] Consider opt-in quick type inference from title text after explicit capture commands are stable.
- [ ] Consider template variables beyond date placeholders and a prompt mode for template expansion.
- [ ] Consider additional digest channels such as Teams webhook, Discord webhook, and desktop notification.
- [ ] Consider a community lint ruleset repository.

### Web, API, and MCP

- [ ] Consider MCP HTTP/SSE transport with token authentication for clients that cannot launch stdio commands directly.
- [ ] Consider server-side graph rendering so share and digest outputs can attach the same graph image without a browser.
- [ ] Consider a full embedded Git server only if lightweight Git subprocess endpoints prove insufficient.
- [ ] Consider static HTML export mode for the Web UI as a read-only snapshot.
- [ ] Consider interactive plot mode in TUI after plot output is stable.
- [ ] Consider integrating team presence into the TUI sidebar.

### Ecosystem and Security

- [ ] Consider asymmetric encryption for multi-user scenarios where different users encrypt but only selected key holders can decrypt.
- [ ] Consider richer import/export adapters after ICS, Markdown, Todoist, GitHub issues, and todo.txt coverage is stable: org-mode, mailbox logs, CalDAV, and richer bidirectional calendar/status integrations.
- [ ] Consider a plugin mechanism only after repeated integration requests cannot be handled through CLI, Web API, MCP, or import/export adapters.
