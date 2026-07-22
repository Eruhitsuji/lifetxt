# lifetxt TODO / Roadmap

Last updated: 2026-07-20 (updated x90)

This is the active roadmap after the 2026-07-20 shared mutation foundation batch. Completed items are removed. The previous detailed roadmap is preserved unchanged in [`docs/roadmap-archive-2026-07-20.md`](docs/roadmap-archive-2026-07-20.md) for traceability.

Priority guide:

- `P0`: Release-blocking data safety, correctness, and verification.
- `P1`: Core format, shared behavior, remote access, messaging, and daily workflow work.
- `P2`: Product customization, packaging, documentation, editor support, and maintainability.
- `Deferred`: Ideas that should wait for a proven use case or a stable foundation.

Design principles:

- Fail loudly when behavior is ambiguous or data may be lost.
- Keep life.txt authoritative and use standard, inspectable interchange formats.
- Route writes through one validated, atomic, conflict-aware mutation path.
- Keep CLI, TUI, Web API, Web UI, MCP, editor support, and documentation semantically aligned.
- Prefer lifetxt as an action and information hub over copying every external system's full data into life.txt.
- Treat remote access, integrations, and automation as proposal-producing clients unless a validated write contract explicitly permits direct mutation.

Feature-track order after the P0 release gate:

1. Stabilize Format 1.0, shared schemas, and surface-neutral operation contracts.
2. Add single-user Remote Safe Mode and a read-only Remote Workspace Client.
3. Enable conflict-aware remote writes in CLI and TUI.
4. Add Unified Inbox, daily command-center views, saved views, and life-area navigation.
5. Add managed groups, multi-recipient messaging, and per-recipient delivery state.
6. Add Web UI configuration screens and custom dashboard composition.
7. Add external-service adapters and declarative automation only after proposals, auditability, and permission boundaries are stable.

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
- [ ] Add a completion regression test that sources the generated bash script and drives `_lifetxt_completion` directly. The current tests assert on the generated text, which cannot catch a script that is syntactically valid but behaves wrongly.
- [ ] Verify SMTP delivery with safe test accounts, including STARTTLS, authentication errors, multiple recipients, watcher state, and provider app-password guidance.
- [ ] Add browser-level smoke tests for the Web UI, including mobile layout, keyboard navigation, command execution, undo, dialogs, charts, timeline edge cases, and accessibility focus behavior.
- [ ] Warn when `serve PATH` reads one file but writes to a different one because config `write_file` overrides it. A POSIX `write_file` on Windows silently resolves drive-relative and creates a file the user never asked for, with the UI reporting success.
- [ ] Automate the Web UI translation-coverage sweep. The current check is a manual headless-browser walk over every view; CI should fail when newly added chrome has no dictionary entry, and the sweep must keep reporting the record-content bucket so an over-broad exclusion cannot hide a real gap.
- [ ] Define and enforce the next release gate: timezone-safe round trips, shared mutation with CAS, golden corpus, green CI, clean packaging metadata, and published schemas.

---

## P1: Format 1.0 and Data Semantics

- [ ] Add a `format_version` directive and a migration/versioning policy. Define how unversioned and stale files are reported.
- [ ] Define `LIFETXT_CANON_V1`: UTF-8 without BOM, LF endings, NFC normalization, whitespace, quoting, detail ordering, repeated-key ordering, and continuation representation.
- [ ] Specify case-sensitivity rules for detail keys, tags, IDs, contexts, users, teams, groups, areas, and projects.
- [ ] Specify multi-file semantics: ID uniqueness, glob ordering, cross-file links, archive references, source metadata, and write-target selection.
- [ ] Document metadata directive placement and precedence across CLI flags, config, file directives, and built-in defaults.
- [ ] Publish stable JSON Schemas for JSON, JSONL, Web API payloads, MCP outputs, remote capabilities, conflict responses, proposals, saved views, and message delivery state under `dist/`, with HTTPS `$id` values and CI validation.
- [ ] Add diagnostics for Unicode normalization, BOM, CRLF, mixed indentation, invalid directives, duplicate IDs across files and archives, dangling links, dependency cycles, missing parents, and corrupt timer state.
- [ ] Add `check --format json` as a stable diagnostics API with source, line, span, code, severity, message, and fix hints.
- [ ] Add conservative typo suggestions and mechanical `check --fix` repairs only after the canonical form and golden corpus are stable.
- [ ] Define the concrete life.txt Format 1.0 compatibility boundary and migration checklist.

---

## P1: Shared Surface Contracts

- [ ] Define surface-neutral operations for query, add, update, delete, done, repeat completion, agenda, next-action selection, timer actions, links, attachments, timezone conversion, messaging, proposals, saved views, and remote workspace access.
- [ ] Build contract tests that run the same fixtures through the shared Python layer and every applicable public surface.
- [ ] Generate a command/capability matrix and fail CI when required CLI, TUI, Web, or MCP behavior drifts without an explicit exception.
- [ ] Move the new extension dispatcher commands into the unified parser registry once the CLI module split begins, so generated help and every completion backend stay authoritative.
- [ ] Expose named review ranges (`last-week`, `last-month`, and `year`) through Web API and MCP, using `review.resolve_review_range` rather than duplicating date math.
- [ ] Decide which new report commands need Web API or MCP equivalents based on demonstrated daily use; avoid adding surfaces only for symmetry.
- [ ] Add structured proposal metadata and item-level diffs for MCP and external writes, then require an expected file hash or an explicit unsafe override.
- [ ] Add mutation-lock observability to `doctor`: list active and stale sidecar locks, show owner metadata, and clean up only locks proven stale.
- [ ] Define a shared query language and saved-view schema before adding more one-off filtering options. Reuse the same grammar in CLI, TUI, Web UI, MCP, remote clients, dashboards, sharing, and automation.

---

## P1: Remote Safe Mode and Remote Workspace Access

This track starts only after shared mutation routing, external revision preconditions, stable schemas, and the public-deployment security review are complete. The first release is single-user and does not attempt offline synchronization or automatic merging.

- [ ] Add single-user Remote Safe Mode with password login and/or trusted reverse-proxy authentication while retaining token authentication for API clients.
- [ ] Use secure server-side sessions, protected cookies, CSRF protection for browser writes, login throttling, session expiration and revocation, security headers, and environment-backed secret loading.
- [ ] Add a versioned capability endpoint that reports server version, format/schema versions, supported operations, authentication mode, read-only state, writable targets, revision-precondition support, and optional features.
- [ ] Define a shared `WorkspaceBackend` interface with `LocalFileBackend` and `RemoteApiBackend` implementations so CLI and TUI commands do not reimplement local-versus-remote behavior.
- [ ] Add remote profile management, for example `lifetxt remote add|list|show|test|remove NAME`, storing URLs and non-secret preferences in config while referencing credentials through environment variables or operating-system credential facilities.
- [ ] Add read-only remote operation for `list`, `show`, `filter`, `agenda`, `next`, `review`, `messages`, `status`, `links`, `graph`, and completion before enabling writes.
- [ ] Add `lifetxt tui --remote NAME` with read-only browsing first. Reuse the normal TUI rendering and command catalog rather than building a separate remote TUI.
- [ ] Add conflict-aware remote create, update, delete, done, timer, message, and acknowledgement operations only after the Web API exposes source-file revisions and requires `ETag` / `If-Match` or an equivalent expected revision.
- [ ] Make remote conflicts show the expected revision, current revision, current server item, and the user's attempted change. Never overwrite automatically or describe a comparison as true three-way merge without a retained base representation.
- [ ] Start remote refresh with explicit reload and bounded polling. Add SSE or WebSocket updates only after polling behavior and reconnect semantics are proven insufficient.
- [ ] Keep remote/local transfer explicit through commands such as export, copy, or proposal import. Do not implement background bidirectional file synchronization in this track.
- [ ] Add connection diagnostics for TLS, authentication, server compatibility, clock skew, schema mismatch, unavailable capabilities, read-only mode, and proxy configuration.
- [ ] Test remote CLI/TUI behavior against read-only servers, stale revisions, expired sessions, network interruption, retries, multi-file workspaces, and servers with older capability versions.

---

## P1: Messaging, Groups, and Delivery State

The format already preserves repeated `recipient:` values and recognizes `team:` and `group:`. This track implements consistent recipient management, expansion, delivery, and acknowledgement semantics rather than adding duplicate syntax.

- [ ] Add a group directory with config-defined groups for local use and server-managed groups for authenticated remote workspaces. Define nested-group policy, cycle detection, duplicate removal, disabled members, and deterministic expansion order.
- [ ] Add shared CLI, TUI, Web UI, API, and MCP message composition that accepts repeated direct recipients plus teams or groups and previews the final expanded recipient set before sending.
- [ ] Add commands such as `lifetxt message send`, `message recipients`, `group list`, `group show`, and `group validate`, generated from the same command and capability registry as other surfaces.
- [ ] Preserve both the original group reference and the resolved recipient set needed for auditability, while keeping the human-authored Message item readable.
- [ ] Define per-recipient states such as pending, delivered, failed, read, acknowledged, and skipped. Decide whether delivery records live in a generated life.txt file or non-authoritative operational storage, and publish the chosen schema.
- [ ] Add acknowledgement policies for `any`, `all`, and an explicit count, with clear behavior when group membership changes after a message is created.
- [ ] Add recipient-specific acknowledgement and snooze operations; a single person's acknowledgement must not silently complete a multi-recipient message unless its policy permits that result.
- [ ] Add recipient expansion, delivery state, acknowledgement progress, and resend controls to the Web Messages view and record detail modal.
- [ ] Add permission checks for group visibility, group messaging, recipient discovery, delivery-state visibility, and administrative group changes in Remote Safe Mode and future multi-user mode.
- [ ] Route terminal, desktop, email, Web UI, and future Teams/Slack/Discord delivery through a backend contract that records per-recipient outcomes without storing provider credentials in life.txt.
- [ ] Add tests for repeated recipients, direct-plus-group duplicates, nested groups, cycles, empty groups, partial delivery failure, acknowledgement-policy completion, and membership changes.

---

## P1: Life Hub and Information Unification

The goal is to make lifetxt the place where users decide what to do next and reach related information, not to replace every source system or copy all external content into life.txt.

- [ ] Add a Unified Inbox that receives quick capture, Web Share Target input, MCP suggestions, remote-client changes, and future external-service imports as reviewable proposals with source, provenance, assumptions, warnings, and item-level diffs.
- [ ] Add explicit accept, edit, reject, defer, and batch-apply actions for inbox proposals. Accepted batches must pass validation, expected-revision checks, and the shared mutation path atomically.
- [ ] Add a shared daily command-center aggregation used by `lifetxt today`, `lifetxt brief morning|evening`, TUI, Web Dashboard, and remote clients. Include agenda, overdue and due-today work, active timers, unacknowledged messages, habits, waiting items, and recent captures.
- [ ] Define `area:` as an optional higher-level life/work classification above `project:`. Preserve custom-key compatibility first, then add shared filtering, completion, saved views, validation guidance, and documentation before treating it as a core key.
- [ ] Add built-in area presets only as examples (`work`, `research`, `health`, `home`, `finance`, `family`, `learning`); never require a fixed taxonomy.
- [ ] Add person and group overview commands/views that collect assigned work, meetings, messages, status, shared projects, waiting items, links, and group membership without duplicating source records.
- [ ] Add decision and meeting-record workflows using existing Note/Journal records and stable links before considering new item types. Provide templates for agenda, decisions, action items, unresolved questions, and follow-up dates.
- [ ] Add backlinks and related-item navigation across `parent:`, `ref:`, `depends_on:`, `blocks:`, `related:`, messages, decisions, meetings, people, groups, and external URLs.
- [ ] Expand global search across title, details, body, message threads, attachment names, people, groups, projects, areas, decisions, and URLs. Keep direct scanning as the baseline until large-file benchmarks justify an index.
- [ ] Add declarative automation rules only after proposals, audit logging, permission checks, and conflict-aware writes are stable. Rules must use allow-listed triggers/actions and must not execute arbitrary code.
- [ ] Add external adapters for email, calendar, GitHub, Slack, Teams, Discord, browser capture, and mobile sharing incrementally. Default imported changes to proposals and store only references or summaries when the external system remains authoritative.
- [ ] Add privacy controls and redaction for personal, health, finance, family, and work data when producing shared views, remote API responses, AI context, exports, and notification payloads.

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
- [ ] Expose RRULE expansion beyond the CLI: an agenda/Web/MCP preview of the next N occurrences of a rule, reusing `recurrence.expand` rather than re-deriving dates per surface.
- [ ] Decide whether to extend the RRULE subset with `BYSETPOS`, `BYWEEKNO`, and `BYYEARDAY`, based on real use. These are currently rejected with a visible warning, which is the correct default.
- [ ] Add a drift guard so the validator's RRULE messages cannot outlive the engine again. `_SUPPORTED_RRULE_KEYS` is now derived, but the per-part wording (which FREQ values honor a BYDAY position, for instance) is still written by hand in two places.
- [ ] Support `RDATE`, the counterpart to the `EXDATE` handling `--expand-rrule` already has. Feeds use it to add a one-off occurrence outside the rule, which expansion currently drops.
- [ ] Let `--expand-rrule` re-expand on a rolling window. A file expanded once goes stale as its horizon passes, and `--merge-existing` only refreshes dates still inside the new window.
- [ ] Decide how archive and undo should handle attachments whose paths later move.

---

## P2: Web UI Customization

Theme tokens and Dashboard card order/limits already exist. The remaining work is to make supported customization discoverable, editable, validated, portable, and consistent with saved views rather than allowing arbitrary code.

- [ ] Add a Web settings UI for supported `web.*` values with schema validation, defaults, reset, preview, and clear indication of settings that require a server restart.
- [ ] Make navigation configurable: visible views, view order, default view, role/device presets, mobile bottom-navigation entries, and administrative-only surfaces.
- [ ] Add a custom dashboard schema based on allow-listed cards and the shared saved-view/query model. Support card title, query, grouping, date range, limit, width, and display mode without embedding arbitrary HTML or JavaScript.
- [ ] Add drag-and-drop card ordering and add/remove controls while preserving a text-based exportable configuration as the authoritative representation.
- [ ] Add configurable Items table columns, column order, compact/comfortable density, default sorting, default grouping, and type-specific detail fields.
- [ ] Add configurable quick-add defaults, date formats, week start, type/status/priority icons, semantic colors, and view-specific empty-state guidance.
- [ ] Add desktop and mobile previews plus configuration export/import with versioned schemas and migration diagnostics.
- [ ] Add named UI presets for personal, work, team board, kiosk, and mobile capture as examples composed from normal settings, not hard-coded special modes.
- [ ] Keep arbitrary CSS administrator-only and disabled by default if introduced. Keep arbitrary JavaScript and third-party in-page plugins deferred until the plugin/security model is stable.
- [ ] Add browser tests for invalid settings, missing tokens, inaccessible contrast, responsive layouts, preset migration, import/export, and recovery from a broken configuration.

---

## P2: CLI, Packaging, and Distribution

- [ ] Route the `extra_cli` commands (`next`, `show`, `edit`, `path`, `count`, `invoice`, `standup`, `to-ics`, `from-todo`) through `build_parser`. Completion now special-cases them via `entrypoint._EXTRA_COMMANDS`, but `--help`, generated docs, and per-command option completion still cannot see their flags.
- [ ] Cache `completion values` results keyed by file path and mtime. A lookup reparses the whole file on every keypress-triggered completion (~250 ms for 200 records), which is noticeable on large files. `GET /api/complete` has the same problem: it re-reads every path per keystroke.
- [ ] Complete command arguments in the Web UI command palette, which still only matches command names. The inline widget covers the text fields but not `Ctrl+K`.
- [ ] Offer completion candidates in the CLI's own interactive prompt (`assist --interactive`), the last input surface with no completion at all.
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
- [ ] Extract the Web UI Japanese dictionary from `webapp.py` into a data file that CLI, TUI, and MCP can share, so one translation exists per string instead of one per surface.
- [ ] Decide the policy for languages beyond Japanese: how `web.language` falls back, whether partial dictionaries are allowed, and what an untranslated string should do.
- [ ] Add worked examples and captures for TUI, Web views, timer, statistics, review, graph, attachments, invoice, standup, import/export, remote workspace use, group messaging, saved views, and recovery.
- [ ] Document file splitting, generated files, archive files, cache files, multiple writers, backups, undo, Git-based recovery, remote workspaces, authentication, and proposal review.
- [ ] Document sidecar lock files, CAS conflict recovery, cloud-sync and network-filesystem limitations, and safe manual cleanup.
- [ ] Package the VS Code grammar/snippets as an installable extension and generate key lists from model definitions.
- [ ] Add editor support for directives, encrypted values, folding, file icons, and syntax-highlight snapshots.
- [ ] Add a lossless parser/CST with source spans before implementing LSP edits.
- [ ] Implement LSP diagnostics first, then symbols, completion, hover, go-to-definition, safe code actions, and finally workspace rename after multi-file CAS is proven.

---

## Deferred Ideas

- [ ] Consider named or parallel timers only if the single active timer remains restrictive in real use.
- [ ] Consider a local daemon only if notification watch, timer state, alarm delivery, file reload, remote event streaming, and automation genuinely need one process.
- [ ] Consider PWA offline capture only after shared CAS, an offline proposal queue, and explicit conflict review exist.
- [ ] Consider general remote/local synchronization after Format 1.0 and an ID-based three-way merge model are stable.
- [ ] Consider automatic Git pull/push/merge only after local semantic history, remote proposals, credential delegation, and conflict review are stable.
- [ ] Consider a plugin SDK only after shared schemas and mutation contracts are stable and an out-of-tree official adapter validates the design.
- [ ] Consider a rebuildable search index only after large-file benchmarks demonstrate a practical bottleneck.
- [ ] Do not add arbitrary Web UI JavaScript, plugins that directly rewrite life.txt, or unrestricted automation code before a sandbox and permission model exists.
- [ ] Do not attempt to replace email, calendar, chat, or file storage wholesale; integrate them through references, summaries, proposals, and explicit user-approved actions.
