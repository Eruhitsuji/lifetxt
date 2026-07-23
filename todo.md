# lifetxt TODO / Roadmap

Last updated: 2026-07-23 (updated x96)

This is the active roadmap after the 2026-07-23 strict release-policy batch. The batch added a required GitHub Actions release gate, versioned release and golden-corpus policies, Draft 2020-12 schema validation, generated-versus-published schema drift checks, a published release-manifest schema, validation of generated manifests, deterministic evidence fingerprints, Japanese Web translation coverage with reviewed debt tracking, a reviewed direct-write baseline, named local CI profiles, clean sdist/wheel installation tests, Twine metadata validation, legacy Web revision-fallback telemetry, and English/Japanese operating documentation. Completed items are removed; partially completed work is rewritten to describe only the remaining migration, debt reduction, multi-target safety, multi-platform verification, and release automation. The previous detailed roadmap is preserved unchanged in [`docs/roadmap-archive-2026-07-20.md`](docs/roadmap-archive-2026-07-20.md) for traceability.

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
- Treat a successful release gate as evidence, not as permission to ignore known baseline debt; review the manifest and shrink resolved allowances in the same change.

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

- [ ] Complete the strict revision rollout after the public Web/MCP transaction foundation. The server now exposes in-memory fallback counts, endpoint counts, last-used UTC time, deprecation headers, and a removal condition through `/api/revision-metrics`; next persist or export that telemetry across restarts, define the observation window, remove the fallback after supported clients report zero use, and require revision discovery plus `If-Match` unconditionally. Migrate remaining CLI/TUI quick capture, archive, and undo paths, and add true multi-target transactions for timer state plus life.txt and attachment/file side effects. Retain one-winner/one-conflict tests at the actual CLI, TUI, Web, and MCP protocol boundaries, including compound operations and rollback failures.
- [ ] Apply the documented timezone precedence (CLI override, `#! timezone:`, `defaults.timezone`, host) to actual display, filtering, recurrence, timer, notification, and completion-date boundaries. Define naive-value interpretation, time-only offset behavior, DST gap/fold handling, and non-hour offsets rather than limiting the policy to inspection and validation.
- [ ] Verify the dependency-free TUI in real WSL, Windows Terminal, macOS, and Linux terminals. Cover colors, glyph fallback, narrow layouts, editor suspension, auto-reload, revision refresh, and mutation-conflict presentation.
- [ ] Verify `fzf` and `peco` actions end-to-end on Windows PowerShell and Unix-like shells, including stale revisions, multi-selection, preview quoting, edit suspension, delete confirmation, and non-ASCII paths.
- [ ] Verify SMTP delivery with safe test accounts, including STARTTLS, authentication errors, multiple recipients, watcher state, and provider app-password guidance.
- [ ] Add browser-engine smoke tests for the Web UI, including the revision-discovery cookie and fetch bridge, revision-migration metrics, mobile layout, keyboard navigation, command execution, undo, dialogs, charts, timeline edge cases, stale-revision recovery, and accessibility focus behavior. Keep the current FastAPI/TestClient contract tests as the lower-level API gate rather than describing them as browser coverage.

---

## P1: Format 1.0 and Data Semantics

- [ ] Complete Format 1.0 enforcement beyond the implemented mutation guard. The shared mutation path now refuses a declared unsupported version while preserving read-only inspection and unversioned compatibility; next add parser-level version metadata, explicit migration commands, downgrade behavior, and uniform CLI/TUI error presentation before requiring `#! format_version: 1` for newly created workspaces.
- [ ] Complete `LIFETXT_CANON_V1` beyond the implemented UTF-8/BOM, LF, NFC, trailing-whitespace, lowercase-key, and final-newline rules. Define quoting, escaping, detail ordering, repeated-key ordering, continuation representation, comments, directive placement, and idempotent serializer output with golden fixtures.
- [ ] Enforce and test the documented multi-file semantics: workspace-wide ID uniqueness, deterministic glob/input order, cross-file links, archive references, source metadata, generated-file behavior, and explicit write-target selection.
- [ ] Expand the published schema bundle beyond item, diagnostic, capability, conflict, and release-manifest documents. Add JSON/JSONL exports, Web API payloads, MCP outputs, proposals, saved views, remote profiles, group definitions, and message delivery state under `dist/schemas/`; add `$ref` resolution tests and validate real Web/MCP responses rather than only representative documents.
- [ ] Extend stable diagnostics beyond BOM, line endings, NFC, trailing whitespace, key case, final newline, duplicate directives, and format version. Add mixed indentation, malformed directives, duplicate IDs across active files and archives, dangling links, dependency cycles, missing parents, corrupt timer state, invalid timezone directives, unsafe write-target diagnostics, and persisted legacy revision-fallback usage diagnostics.
- [ ] Route the legacy `check --format json` interface to the new stable diagnostic shape. Preserve `source`, `line`, `column`, `span`, `code`, `severity`, `message`, and `hint`, publish compatibility guarantees, and add fixtures that compare CLI, Web, and MCP diagnostics.
- [ ] Add conservative typo suggestions and mechanical `check --fix` repairs only after the remaining canonical ordering and quoting rules are stable. Every fix must be revision-checked, idempotent, reviewable as a diff, and limited to unambiguous transformations.
- [ ] Define the concrete life.txt Format 1.0 compatibility boundary and migration checklist, including downgrade behavior, unsupported-directive handling, schema version compatibility, remote capability negotiation, revision-contract compatibility, release-policy compatibility, and required release notes for intentional canonical-output changes.
- [ ] Extend the implemented golden-corpus policy when a second format/corpus version exists. Keep the current version-1 minimum cases and required names immutable, run every previously released corpus against new parsers and serializers, publish migration notes for intentional changes, and add downgrade expectations before introducing version 2.

---

## P1: Shared Surface Contracts

- [ ] Expand the registry-backed operation layer into real surface-neutral implementations for query, add, update, delete, done, repeat completion, agenda, next-action selection, timer actions, links, attachments, timezone conversion, messaging, proposals, saved views, and remote workspace access. The current registry and matrix describe Web/MCP capabilities and revision coverage, but timer and attachment entries intentionally report that full multi-target revision enforcement is unavailable.
- [ ] Extend the current public-contract tests beyond Web/MCP create, stale revision, missing revision, proposal staging, named review ranges, compound repeat completion, fallback telemetry, and release-policy contracts. Run the same fixtures through CLI and TUI and add validation failure, lock timeout, read-only mode, unsupported format, missing capability, multi-file partial failure, and rollback failure cases.
- [ ] Make the registry-derived command/capability matrix a complete CI drift gate. The release gate now validates the capability schema and representative capability document; next generate CLI, TUI, Web, and MCP availability from the same registry, validate actual `/api/capabilities`, `get_capabilities`, and `lifetxt://capabilities` responses, and require an explicit documented exception when a surface cannot support an operation.
- [ ] Retire the `compat_writes` bridge when the TUI/fzf and CLI module splits reach their write commands. Import `lifetxt.mutation` directly, give each operation a stable name, and run semantic transforms against the in-lock current text instead of submitting a precomputed whole-file replacement.
- [ ] Reduce the versioned direct-write baseline instead of allowing it to become permanent. Move CLI configuration output to an atomic config writer, convert digest/template append operations to semantic CAS operations, remove the fzf allowance when `compat_writes` is retired, retain generated-schema output as an explicitly classified artifact, and fail review when a baseline entry has no reason or corresponding roadmap debt.
- [ ] Move all extension dispatcher commands, including `safety`, `format`, and `capabilities`, into the unified parser registry once the CLI module split begins, so generated help and every completion backend stay authoritative.
- [ ] Decide which new report commands need Web API or MCP equivalents based on demonstrated daily use; avoid adding surfaces only for symmetry.
- [ ] Add structured proposal metadata and item-level diffs for MCP and external writes, then require an expected file hash or an explicit unsafe override. Replace the current in-memory text-only proposal preview with a side-effect-free operation plan before supporting multi-target proposals.
- [ ] Integrate the implemented lock inspection into `doctor`: list active and stale sidecar locks, show owner metadata and PID liveness, scan configured workspace targets, and clean up only locks proven stale after an explicit confirmation or non-interactive force flag.
- [ ] Define a shared query language and saved-view schema before adding more one-off filtering options. Reuse the same grammar in CLI, TUI, Web UI, MCP, remote clients, dashboards, sharing, and automation.

---

## P1: Remote Safe Mode and Remote Workspace Access

This track starts only after shared mutation routing, external revision preconditions, stable schemas, and the public-deployment security review are complete. The first release is single-user and does not attempt offline synchronization or automatic merging.

- [ ] Add single-user Remote Safe Mode with password login and/or trusted reverse-proxy authentication while retaining token authentication for API clients.
- [ ] Use secure server-side sessions, protected cookies, CSRF protection for browser writes, login throttling, session expiration and revocation, security headers, and environment-backed secret loading.
- [ ] Complete capability-response validation beyond the implemented schema/sample gate. Add the package/server version, derive optional-feature availability from installed dependencies and configuration rather than constants, validate actual Web/MCP responses against `capability-v1.schema.json`, and publish compatibility rules for older clients. Keep `/api/capabilities`, `get_capabilities`, and `lifetxt://capabilities` semantically identical.
- [ ] Define a shared `WorkspaceBackend` interface with `LocalFileBackend` and `RemoteApiBackend` implementations so CLI and TUI commands do not reimplement local-versus-remote behavior.
- [ ] Add remote profile management, for example `lifetxt remote add|list|show|test|remove NAME`, storing URLs and non-secret preferences in config while referencing credentials through environment variables or operating-system credential facilities.
- [ ] Add read-only remote operation for `list`, `show`, `filter`, `agenda`, `next`, `review`, `messages`, `status`, `links`, `graph`, and completion before enabling writes.
- [ ] Add `lifetxt tui --remote NAME` with read-only browsing first. Reuse the normal TUI rendering and command catalog rather than building a separate remote TUI.
- [ ] Add conflict-aware remote create, update, delete, done, message, status, and acknowledgement against the implemented Web ETag contract. Defer timer and attachment remote writes until the capability matrix reports multi-target revision enforcement. Remove the Web compatibility fallback before describing remote writes as safe-by-default.
- [ ] Make remote conflicts validate against `conflict-v1.schema.json` and show the expected revision, current revision, current server item, and the user's attempted change. Never overwrite automatically or describe a comparison as true three-way merge without a retained base representation.
- [ ] Start remote refresh with explicit reload and bounded polling. Add SSE or WebSocket updates only after polling behavior and reconnect semantics are proven insufficient.
- [ ] Keep remote/local transfer explicit through commands such as export, copy, or proposal import. Do not implement background bidirectional file synchronization in this track.
- [ ] Add connection diagnostics for TLS, authentication, server compatibility, clock skew, schema mismatch, unavailable capabilities, read-only mode, proxy configuration, legacy revision fallback, and ETag stripping by reverse proxies.
- [ ] Test remote CLI/TUI behavior against read-only servers, stale revisions, expired sessions, network interruption, retries, multi-file workspaces, servers with older capability versions, and proxies that rewrite or remove ETags.

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
- [ ] Design and connect a multi-target revision contract for timer JSON state plus the associated life.txt item. Add state-schema validation, cross-platform locking, midnight/timezone tests, corruption recovery, stale-state diagnostics, safe reset/backup behavior, and compensation rules when one target cannot commit. Keep the capability matrix's timer `revision_required` value false until this contract is complete.
- [ ] Add notification backend abstraction for terminal, Linux, macOS, Windows, email, and Web UI delivery.
- [ ] Add quiet hours, persisted acknowledgement, recurring reminder acknowledgement, and shared snooze presets.

---

## P1: Workflow Follow-ups

- [ ] Add deterministic-clock tests for `next`, `standup`, `invoice`, review selectors, workload, and journal defaults. Include the shared named ranges (`last-week`, `last-month`, and `year`) in the same fixture table used by CLI, Web, and MCP.
- [ ] Add `next --explain` to show why each task was selected and why excluded tasks were blocked, deferred, or classified as someday.
- [ ] Add invoice policy documentation and fixtures for rounding, rates, currencies, missing project names, and malformed elapsed values.
- [ ] Add standup team mode only after per-user output is stable; preserve a script-friendly JSON shape.
- [ ] Add ICS round-trip fixtures for all-day events, offset-aware events, attendees, recurrence, escaped text, and UID collisions.
- [ ] Add timezone fixtures for monthly and yearly recurrence, time-only offsets, DST gaps and folds, non-hour offsets, mixed aware/naive boundaries, and each configured precedence source. Verify CLI, Web, MCP, timer, notification, and completion-date behavior against the same fixture table.
- [ ] Define overwrite and conflict behavior before adding bidirectional calendar synchronization or `sync-ics --merge-existing` expansion.
- [ ] Add todo.txt and GitHub Markdown idempotency fixtures so repeated imports do not create duplicate records.
- [ ] Verify attachment opening on Windows, macOS, and Linux, including spaces, symlinks, executable rejection, and paths outside the source directory.
- [ ] Add a safe cache for large `dir:` hashes keyed by path metadata and content-verification state.
- [ ] Expose RRULE expansion beyond the CLI: an agenda/Web/MCP preview of the next N occurrences of a rule, reusing `recurrence.expand` rather than re-deriving dates per surface.
- [ ] Decide whether to extend the RRULE subset with `BYSETPOS`, `BYWEEKNO`, and `BYYEARDAY`, based on real use. These are currently rejected with a visible warning, which is the correct default.
- [ ] Add a drift guard so the validator's RRULE messages cannot outlive the engine again. `_SUPPORTED_RRULE_KEYS` is now derived, but the per-part wording (which FREQ values honor a BYDAY position, for instance) is still written by hand in two places.
- [ ] Support `RDATE`, the counterpart to the `EXDATE` handling `--expand-rrule` already has. Feeds use it to add a one-off occurrence outside the rule, which expansion currently drops.
- [ ] Let `--expand-rrule` re-expand on a rolling window. A file expanded once goes stale as its horizon passes, and `--merge-existing` only refreshes dates still inside the new window.
- [ ] Decide how archive and undo should handle attachments whose paths later move and how a multi-target transaction records or compensates that move.

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

- [ ] Route the `extra_cli` commands (`next`, `show`, `edit`, `path`, `count`, `invoice`, `standup`, `to-ics`, `from-todo`, `from-markdown`, `safety`, `format`, and `capabilities`) through `build_parser`. Completion currently special-cases them via `entrypoint._EXTRA_COMMANDS`, but `--help`, generated docs, and per-command option completion still cannot see their flags authoritatively.
- [ ] Cache `completion values` results keyed by file path and mtime. A lookup reparses the whole file on every keypress-triggered completion (~250 ms for 200 records), which is noticeable on large files. `GET /api/complete` has the same problem: it re-reads every path per keystroke.
- [ ] Complete command arguments in the Web UI command palette, which still only matches command names. The inline widget covers the text fields but not `Ctrl+K`.
- [ ] Offer completion candidates in the CLI's own interactive prompt (`assist --interactive`), the last input surface with no completion at all.
- [ ] Split `lifetxt/cli.py` into command-focused modules with a thin registry-based dispatcher.
- [ ] Split `lifetxt/tui_app.py` into state, command, layout, and rendering modules.
- [ ] Raise the supported Python baseline to `>=3.10` after clean-environment verification and remove obsolete compatibility code deliberately. The release checker now has a dependency-free Python 3.10 TOML fallback, so remove it only together with the declared baseline change.
- [ ] Expand CI to Ubuntu, Windows, and macOS, add coverage, and retain both the dependency-free job and required release-policy job as required checks.
- [ ] Add an optional `doctor --ci` front end for the implemented `core`, `cli`, `web`, `mcp`, and `release` profiles. Add the registry/capability drift suite to the appropriate profiles and provide a concise local failure summary that points to persisted evidence.
- [ ] Extend the implemented Ubuntu clean-wheel gate to Windows PowerShell and macOS, install and smoke-test optional extras from the built wheel, verify launcher quoting and non-ASCII paths, and test wheel contents against an explicit package manifest.
- [ ] Add release documentation and automation beyond the implemented build/validation gate: changelog generation, semantic versioning policy, tag creation, PyPI publication, post-release smoke checks, artifact checksums, provenance attestations, and signing policy.
- [ ] Add `CONTRIBUTING.md`, issue templates, pre-commit configuration, `SECURITY.md`, supported-version policy, and private vulnerability reporting.
- [ ] Consider a zipapp or other single-file distribution only after wheel installation and the Python baseline are stable.

---

## P2: Documentation, Editor, and LSP

- [ ] Define which document is authoritative for grammar, CLI behavior, Web/API behavior, examples, release policy, and compatibility baselines.
- [ ] Add English/Japanese parity checks for headings, code blocks, command names, and stable examples, including release-policy, baseline, and public-surface revision documents.
- [ ] Shrink `web-ja-translation-baseline-v1.json` to zero by translating its known chrome entries. Make CI fail when a resolved entry remains in the baseline, so translation work cannot leave stale suppressions behind.
- [ ] Extract the Web UI Japanese dictionary from `webapp.py` into a data file that CLI, TUI, and MCP can share, so one translation exists per string instead of one per surface.
- [ ] Decide the policy for languages beyond Japanese: how `web.language` falls back, whether partial dictionaries are allowed, and what an untranslated string should do.
- [ ] Add worked examples and captures for TUI, Web views, timer, statistics, review, graph, attachments, invoice, standup, import/export, safety diagnostics, Format 1.0 migration, Web/MCP revision negotiation, release evidence review, remote workspace use, group messaging, saved views, and recovery.
- [ ] Document file splitting, generated files, archive files, cache files, multiple writers, backups, undo, Git-based recovery, remote workspaces, authentication, proposal review, schema compatibility, legacy revision fallback, multi-target transaction recovery, baseline review, and release-manifest interpretation.
- [ ] Expand the sidecar lock and CAS documentation with cloud-sync and network-filesystem limitations, stale-lock evidence requirements, safe manual cleanup, expected-revision examples for every public surface, conflict troubleshooting, ETag proxy behavior, and the distinction between embedded helper APIs and public protocol boundaries.
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
