# lifetxt TODO / Roadmap

Last updated: 2026-07-20 (updated x85)

This is the active roadmap after the 2026-07-20 shared mutation foundation batch. Completed items are removed. The previous detailed roadmap is preserved unchanged in [`docs/roadmap-archive-2026-07-20.md`](docs/roadmap-archive-2026-07-20.md) for traceability.

Priority guide:

- `P0`: Release-blocking data safety, correctness, and verification.
- `P1`: Core format, shared behavior, and daily workflow work.
- `P2`: Packaging, documentation, editor support, and maintainability.
- `Deferred`: Ideas that should wait for a proven use case or a stable foundation.

Design principles:

- Fail loudly when behavior is ambiguous or data may be lost.
- Keep life.txt authoritative and use standard, inspectable interchange formats.
- Route writes through one validated, atomic, conflict-aware mutation path.
- Keep CLI, TUI, Web API, Web UI, MCP, editor support, and documentation semantically aligned.

---

## P0: Release Safety and Correctness

- [ ] Route `presence.status_transition`, TUI `_mutate_rows`, Web writes, MCP writes, timer updates, and notification acknowledgement through the shared mutation layer.
- [ ] Add concurrent-write tests for quick capture, item update, MCP writes, notification acknowledgement, timer state, archive, and undo. Every stale write must fail with a clear conflict error.
- [ ] Fix timezone-offset data loss. Preserve aware datetime values for JSON/JSONL/CSV round trips and normalize only for comparisons.
- [ ] Define timezone rules for naive values, `#! timezone:`, `defaults.timezone`, CLI overrides, display, filtering, and completion-date boundaries.
- [ ] Add a parse-serialize-parse golden corpus before expanding formatting or LSP edits. Include repeated details, multiline bodies, continuations, offsets, Unicode, CRLF, empty files, and hierarchy.
- [ ] Resolve the repeated `body:` plus continuation ambiguity and document the lossless canonical representation or reject the form explicitly.
- [ ] Verify the dependency-free TUI in real WSL, Windows Terminal, macOS, and Linux terminals. Cover colors, glyph fallback, narrow layouts, editor suspension, and auto-reload.
- [ ] Verify `fzf` and `peco` actions end-to-end on Windows PowerShell and Unix-like shells.
- [ ] Verify SMTP delivery with safe test accounts, including STARTTLS, authentication errors, multiple recipients, watcher state, and provider app-password guidance.
- [ ] Add browser-level smoke tests for the Web UI, including mobile layout, keyboard navigation, command execution, undo, dialogs, charts, timeline edge cases, and accessibility focus behavior.
- [ ] Define and enforce the next release gate: timezone-safe round trips, shared mutation with CAS, golden corpus, green CI, clean packaging metadata, and published schemas.

---

## P1: Format 1.0 and Data Semantics

- [ ] Add a `format_version` directive and a migration/versioning policy. Define how unversioned and stale files are reported.
- [ ] Define `LIFETXT_CANON_V1`: UTF-8 without BOM, LF endings, NFC normalization, whitespace, quoting, detail ordering, repeated-key ordering, and continuation representation.
- [ ] Specify case-sensitivity rules for detail keys, tags, IDs, contexts, users, and projects.
- [ ] Specify multi-file semantics: ID uniqueness, glob ordering, cross-file links, archive references, source metadata, and write-target selection.
- [ ] Document metadata directive placement and precedence across CLI flags, config, file directives, and built-in defaults.
- [ ] Publish stable JSON Schemas for JSON, JSONL, Web API payloads, and MCP outputs under `dist/`, with HTTPS `$id` values and CI validation.
- [ ] Add diagnostics for Unicode normalization, BOM, CRLF, mixed indentation, invalid directives, duplicate IDs across files and archives, dangling links, dependency cycles, missing parents, and corrupt timer state.
- [ ] Add `check --format json` as a stable diagnostics API with source, line, span, code, severity, message, and fix hints.
- [ ] Add conservative typo suggestions and mechanical `check --fix` repairs only after the canonical form and golden corpus are stable.
- [ ] Define the concrete life.txt Format 1.0 compatibility boundary and migration checklist.

---

## P1: Shared Surface Contracts

- [ ] Define surface-neutral operations for query, add, update, delete, done, repeat completion, agenda, next-action selection, timer actions, links, attachments, and timezone conversion.
- [ ] Build contract tests that run the same fixtures through the shared Python layer and every applicable public surface.
- [ ] Generate a command/capability matrix and fail CI when required CLI, TUI, Web, or MCP behavior drifts without an explicit exception.
- [ ] Move the new extension dispatcher commands into the unified parser registry once the CLI module split begins, so generated help and every completion backend stay authoritative.
- [ ] Expose named review ranges (`last-week`, `last-month`, and `year`) through Web API and MCP, using `review.resolve_review_range` rather than duplicating date math.
- [ ] Decide which new report commands need Web API or MCP equivalents based on demonstrated daily use; avoid adding surfaces only for symmetry.
- [ ] Add structured proposal metadata and item-level diffs for MCP writes, then require an expected file hash or an explicit unsafe override.
- [ ] Add mutation-lock observability to `doctor`: list active and stale sidecar locks, show owner metadata, and clean up only locks proven stale.

---

## P1: Timer and Notification Foundation

- [ ] Decide the timer scope boundary before adding persistent alarm or Pomodoro complexity.
- [ ] Define one timer state model for start, stop, pause, resume, cancel, crash recovery, stale-state detection, and optional item association.
- [ ] Decide whether `timer alarm`, `timer pomodoro`, and `timer log` belong in core or should remain delegated to operating-system tools.
- [ ] Add timer state validation, cross-platform locking, midnight/timezone tests, and corruption recovery.
- [ ] Add notification backend abstraction for terminal, Linux, macOS, Windows, email, and Web UI delivery.
- [ ] Add quiet hours, persisted acknowledgement, recurring reminder acknowledgement, and shared snooze presets.

---

## P1: Workflow Follow-ups

- [ ] Add deterministic-clock tests for `next`, `standup`, `invoice`, review selectors, workload, and journal defaults.
- [ ] Add `next --explain` to show why each task was selected and why excluded tasks were blocked, deferred, or classified as someday.
- [ ] Add invoice policy documentation and fixtures for rounding, rates, currencies, missing project names, and malformed elapsed values.
- [ ] Add standup team mode only after per-user output is stable; preserve a script-friendly JSON shape.
- [ ] Add ICS round-trip fixtures for all-day events, offset-aware events, attendees, recurrence, escaped text, and UID collisions.
- [ ] Define overwrite and conflict behavior before adding bidirectional calendar synchronization or `sync-ics --merge-existing` expansion.
- [ ] Add todo.txt and GitHub Markdown idempotency fixtures so repeated imports do not create duplicate records.
- [ ] Verify attachment opening on Windows, macOS, and Linux, including spaces, symlinks, executable rejection, and paths outside the source directory.
- [ ] Add a safe cache for large `dir:` hashes keyed by path metadata and content-verification state.
- [ ] Decide how archive and undo should handle attachments whose paths later move.

---

## P2: CLI, Packaging, and Distribution

- [ ] Split `lifetxt/cli.py` into command-focused modules with a thin registry-based dispatcher.
- [ ] Split `lifetxt/tui_app.py` into state, command, layout, and rendering modules.
- [ ] Raise the supported Python baseline to `>=3.10` after clean-environment verification and remove obsolete compatibility code deliberately.
- [ ] Expand CI to Ubuntu, Windows, and macOS, add coverage, and retain the dependency-free job as a required check.
- [ ] Expand `scripts/run_ci_like.py` with named profiles (`cli`, `web`, `mcp`, and `release`) and an optional `doctor --ci` front end.
- [ ] Verify editable install, optional extras, console scripts, PowerShell usage, build artifacts, and clean-wheel installation.
- [ ] Add release documentation and automation: changelog, semantic versioning, build, tag, PyPI publication, and post-release smoke checks.
- [ ] Add `CONTRIBUTING.md`, issue templates, pre-commit configuration, `SECURITY.md`, supported-version policy, and private vulnerability reporting.
- [ ] Consider a zipapp or other single-file distribution only after wheel installation and the Python baseline are stable.

---

## P2: Documentation, Editor, and LSP

- [ ] Define which document is authoritative for grammar, CLI behavior, Web/API behavior, and examples.
- [ ] Add English/Japanese parity checks for headings, code blocks, command names, and stable examples.
- [ ] Add worked examples and captures for TUI, Web views, timer, statistics, review, graph, attachments, invoice, standup, import/export, and recovery.
- [ ] Document file splitting, generated files, archive files, cache files, multiple writers, backups, undo, and Git-based recovery.
- [ ] Document sidecar lock files, CAS conflict recovery, cloud-sync and network-filesystem limitations, and safe manual cleanup.
- [ ] Package the VS Code grammar/snippets as an installable extension and generate key lists from model definitions.
- [ ] Add editor support for directives, encrypted values, folding, file icons, and syntax-highlight snapshots.
- [ ] Add a lossless parser/CST with source spans before implementing LSP edits.
- [ ] Implement LSP diagnostics first, then symbols, completion, hover, go-to-definition, safe code actions, and finally workspace rename after multi-file CAS is proven.

---

## Deferred Ideas

- [ ] Consider named or parallel timers only if the single active timer remains restrictive in real use.
- [ ] Consider a local daemon only if notification watch, timer state, alarm delivery, and file reload genuinely need one process.
- [ ] Consider PWA offline capture only after shared CAS, an offline proposal queue, and explicit conflict review exist.
- [ ] Consider general synchronization after Format 1.0 and an ID-based three-way merge model are stable.
- [ ] Consider a plugin SDK only after shared schemas and mutation contracts are stable and an out-of-tree official adapter validates the design.
- [ ] Consider a rebuildable search index only after large-file benchmarks demonstrate a practical bottleneck.
