# lifetxt TODO / Roadmap

Last updated: 2026-07-20 (updated x86)

This is the active roadmap after reconciling main revision `586083b`, the archived x83 roadmap, and earlier use-case backlogs. Completed work is removed. Items that were compressed out of the active roadmap but remain unimplemented are restored below at an appropriate priority.

The basic timezone-offset JSON/JSONL/CSV round trip and the basic `check --format json` switch already exist. The remaining entries below cover semantics, stable schemas, diagnostics, conflict handling, and cross-surface guarantees that are not complete yet.

Priority guide:

- `P0`: Release-blocking data safety, correctness, security, and verification.
- `P1`: Core capabilities required for the next compatibility-focused release or the immediately following feature track.
- `P2`: Valuable product, workflow, documentation, packaging, editor, and maintainability work after the foundations are stable.
- `Deferred`: Ideas that must wait for a proven use case or a prerequisite design.

Ordering rule: items earlier within a section have higher priority unless an explicit dependency says otherwise.

Design principles:

- Fail loudly when behavior is ambiguous or data may be lost.
- Keep life.txt authoritative and use standard, inspectable interchange formats.
- Route every accepted write through one validated, atomic, conflict-aware mutation path.
- Keep CLI, TUI, Web API, Web UI, MCP, editor support, and documentation semantically aligned.
- Solve observed problems first; do not add synchronization, daemon, or plugin complexity before its prerequisites are proven.

---

## Current Execution Order

1. Complete shared mutation routing for every write path.
2. Expose a safe optimistic-concurrency contract through Web API, Web UI, and MCP.
3. Add lock observability and recovery through `doctor`.
4. Freeze parser and serializer behavior with a golden corpus and property-based tests.
5. Stabilize the diagnostics contract and diagnostic registry.
6. Define `format_version`, canonical form, Unicode rules, and multi-file semantics.
7. Publish schemas and complete release hardening.
8. Add local Git/VCS history workflows without remote synchronization.
9. Add single-user Remote Safe Mode.
10. Add multi-user sharing and remote synchronization only after the earlier contracts are stable.

---

## P0: Shared Mutation Routing and Conflict Safety

- [ ] Route every remaining life.txt write through `lifetxt.mutation`, including TUI `_mutate_rows`, Web append/update/delete/undo, MCP commit/undo, timer item updates, notification acknowledgement, archive, undo, quick capture, and compatibility-extension commands.
- [ ] Route timer and notification state files through the shared JSON mutation and sidecar-lock primitives. Use external expected-hash preconditions only where a caller actually reads and later submits a revision, but always serialize semantic state transitions under a lock.
- [ ] Add a repository guard that fails CI when a public write surface directly uses `atomic_write_text`, `atomic_write_json`, `open(..., "w")`, or another bypass for authoritative files without an explicit documented exception.
- [ ] Centralize `MutationConflict`, `LockTimeout`, validation failures, and environment failures into one surface-neutral error mapping for CLI exit codes, HTTP responses, MCP errors, and Web UI messages.
- [ ] Add per-source revision metadata to Web read responses. Multi-file views must distinguish an aggregate view revision from the exact source-file revision used for an item write.
- [ ] Implement Web API optimistic locking with `ETag` / `If-Match`. Return `412 Precondition Failed` for stale revisions and `428 Precondition Required` when a protected write omits the precondition.
- [ ] Update the Web UI in the same change as the Web precondition requirement so first-party clients never become unable to write after the API is hardened.
- [ ] Require `expected_hash` for MCP writes after the shared mutation migration. Keep any unsafe override explicit per operation, disabled by default, visible in the result, and impossible to enable silently through a broad server setting.
- [ ] Add concurrent-write tests for quick capture, item update, TUI batch edit, Web update/delete, MCP commit, notification acknowledgement, timer state, timer item updates, archive, undo, and multi-file writes. Every stale write must fail clearly and preserve the winning content.
- [ ] Verify that post-write hashes, permissions, BOM state, newline form, and directory durability remain correct through every migrated surface.

---

## P0: Lock Observability and Recovery

- [ ] Add `lifetxt doctor --locks` to list active, stale, malformed, and ambiguous sidecar locks with target, operation, PID, host, creation time, and age.
- [ ] Add `lifetxt doctor --locks --clean-stale`; never delete an active or ambiguous lock, and reuse the exact stale-owner checks from `mutation.py` rather than duplicating them.
- [ ] Add tests for live local owners, dead local owners, remote-host metadata, malformed metadata, lock replacement during inspection, and cleanup races.
- [ ] Document lock files, conflict recovery, cloud-sync and network-filesystem limitations, safe manual cleanup, and what to collect in a bug report.

---

## P0: Parser, Serializer, Time, and Recurrence Safety

- [ ] Add a parse-serialize-parse golden corpus before expanding formatting, migrations, or LSP edits.
- [ ] Cover repeated details, multiple `body:` values, continuation lines, empty continuation lines, nested hierarchy, quoted escapes, bare-string edge cases, timezone offsets (`+09:00`, `Z`, fractional seconds), Unicode and combining characters, BOM, LF/CRLF/CR, attachments, empty files, comments, directives, and invalid inputs.
- [ ] Separate golden assertions into semantic round-trip equality, canonical fixpoint stability, exact-preservation cases, and expected-rejection cases.
- [ ] Resolve the repeated `body:` plus continuation ambiguity and either define one lossless representation or reject the ambiguous form explicitly.
- [ ] Add Hypothesis/property-based item generation in an optional CI job while retaining the dependency-free required job.
- [ ] Define timezone rules for naive values, `#! timezone:`, `defaults.timezone`, CLI overrides, display, filtering, comparisons, recurrence, and completion-date boundaries.
- [ ] Add deterministic-clock coverage for timezone boundaries and for `next`, `standup`, `invoice`, review selectors, workload, journal defaults, and timer behavior.
- [ ] Verify repeat completion end-to-end across `repeat_base: due|done`, habit completion, MCP completion, undo, and archive.
- [ ] Add missing recurrence rules: `BYDAY` materialization, `count:` semantics, generated-occurrence identity, and explicit same-day duplicate-completion rejection with an intentional force path.

---

## P0: Existing Surface Verification and Public-Deployment Safety

- [ ] Verify the dependency-free TUI in real WSL, Windows Terminal, macOS, and Linux terminals. Cover colors, glyph fallback, CJK and grapheme width, narrow layouts, editor suspension, and auto-reload.
- [ ] Verify `fzf` and `peco` preview and action flows end-to-end on Windows PowerShell and Unix-like shells.
- [ ] Verify SMTP delivery with safe test accounts, including STARTTLS, authentication errors, multiple recipients, watcher state, and provider app-password guidance.
- [ ] Add browser-level smoke tests for mobile layout, command execution, status cycling, item creation/editing, undo, dialogs, charts, review, timeline edge cases, graph controls, focus handling, keyboard navigation, and accessibility state.
- [ ] Review source-path exposure in agenda, status, Web API, MCP, read-only servers, and public views. Strip, relativize, or authorize source metadata instead of leaking server filesystem paths.
- [ ] Harden Git/admin Web routes for reverse-proxy deployments. Do not trust `request.client.host` loopback checks without an explicit trusted-proxy model, and keep administrative subprocess routes disabled by default.
- [ ] Keep default Web binding on localhost and add secure secret loading such as `--token-env` or environment-backed config so credentials do not appear in shell history or life.txt.
- [ ] Define and enforce the next release gate: shared mutation routing, external CAS, lock diagnostics, timezone-safe semantics, golden corpus, green CI, clean packaging metadata, published schemas, and public-deployment safety review.

---

## P1: Diagnostics Contract and Format 1.0

- [ ] Create a central diagnostic registry containing stable code, title, default severity, description, causes, triggering example, resolution hints, and documentation anchor.
- [ ] Stabilize `check --format json` as a public diagnostics API with source, line, column/span, code, severity, message, related locations, and machine-readable fix hints.
- [ ] Add `lifetxt check --why CODE`, generated documentation, Web help, MCP explanations, and future LSP hover data from the same diagnostic registry.
- [ ] Add a `format_version` directive and migration/versioning policy. Treat unversioned files compatibly with a warning, reject unsupported future versions, and diagnose duplicate or misplaced directives.
- [ ] Define `LIFETXT_CANON_V1`: UTF-8 without BOM, LF endings, NFC, whitespace, quoting, detail ordering, repeated-key ordering, continuation representation, directive placement, and stable serialization.
- [ ] Diagnose non-NFC text without silently rewriting it during parse. Add an explicit canonical-format or fix operation only after canonical rules are finalized.
- [ ] For attachment paths, try the literal path first, diagnose normalization-equivalent alternatives, and never choose among ambiguous filesystem matches automatically.
- [ ] Specify case-sensitivity rules for detail keys, tags, IDs, contexts, users, teams, and projects across parsing, filtering, completion, Web, MCP, and editors.
- [ ] Specify multi-file semantics: ID uniqueness, glob and directory ordering, source identity, cross-file links, archive references, generated files, write-target selection, and multi-file revision behavior.
- [ ] Document metadata directive placement and precedence across CLI flags, project config, global config, file directives, and built-in defaults.
- [ ] Publish stable JSON Schemas for JSON, JSONL, Web API payloads, MCP tool inputs/outputs, diagnostics, proposals, and conflict responses under `dist/` with HTTPS `$id` values and CI validation.
- [ ] Add diagnostics for Unicode normalization, BOM, CRLF, mixed indentation, invalid directives, duplicate IDs across active files and archives, dangling links, dependency cycles, missing parents, corrupt timer state, config schema errors, and likely secret values.
- [ ] Add conservative typo suggestions and mechanical `check --fix` repairs only after the canonical form and golden corpus are stable.
- [ ] Add `lifetxt fmt --check|--diff|--canonical` after canonical behavior is specified; formatting must never change meaning silently.
- [ ] Define and document stable exit codes for usage errors, validation errors, write conflicts, lock failures, environment failures, and internal errors.
- [ ] Define the concrete life.txt Format 1.0 compatibility boundary, migration checklist, compatibility fixtures, and release policy.

---

## P1: Recovery, Proposals, and Shared Surface Contracts

- [ ] Design an append-only mutation journal under `.cache/lifetxt/` with operation, before/after hashes, surface, actor/client metadata, timestamp, target, item-level changes, and recovery references.
- [ ] Use the mutation journal as the shared foundation for CLI/Web/MCP auditability, multi-level undo, conflict debugging, and future synchronization; do not make the journal authoritative over life.txt.
- [ ] Preserve original source and line context when restoring deleted items, and replace Web UI single-action undo with a bounded history backed by the shared journal.
- [ ] Add structured proposal metadata and item-level `{op, id, before, after}` diffs for MCP and future external writes.
- [ ] Add an explicit proposal approval flow shared by MCP and CLI. Bind approval to proposal hash and expected file hash, expire stale proposals, apply accepted batches atomically, and record interpretation assumptions and warnings.
- [ ] Improve conflict responses with expected and actual hashes, current target/item data, and a client-displayable comparison. Do not claim a true three-way view unless the base representation is supplied or retained.
- [ ] Define surface-neutral operations for query, add, update, delete, done, repeat completion, agenda, next-action selection, timer actions, links, attachments, timezone conversion, proposals, and recovery.
- [ ] Build contract tests that run the same fixtures through the shared Python layer and every applicable CLI, TUI, Web, and MCP surface.
- [ ] Generate a command/capability matrix and fail CI when required behavior drifts without an explicit documented exception.
- [ ] Move compatibility-extension commands into the unified parser registry once the CLI split begins so help, completion, docs, and every surface derive from one command catalog.
- [ ] Expose named review ranges through Web API and MCP using `review.resolve_review_range`; avoid duplicating date math in clients.
- [ ] Add a small shared query language and named saved views before adding more one-off filter flags. Reuse it across CLI, TUI, Web, MCP, dashboards, sharing, and automation.
- [ ] Promote `context:` to a fully shared filter and completion dimension, including inbox processing and Web/MCP query paths.
- [ ] Decide which report commands need Web API or MCP equivalents based on demonstrated use, while preserving a stable script-friendly shape.

---

## P1: Local Git/VCS History

This track starts after canonical serialization, multi-file identity, and mutation journaling are stable. It intentionally excludes automatic remote synchronization.

- [ ] Add a `lifetxt vcs` command group with `init`, `status`, `diff`, `history`, and `restore`.
- [ ] Make `vcs status` and `vcs diff` understand item IDs and details so formatting-only or moved-record changes are distinguishable from semantic changes.
- [ ] Add item-scoped history and restore, for example `vcs history --id ITEM` and `vcs restore --id ITEM --revision REV`, with dry-run and conflict checks.
- [ ] Reuse the semantic diff representation for MCP proposals, conflict review, mutation-journal inspection, and Git history.
- [ ] Add optional debounced or daily auto-commit after manual commit behavior is proven. Keep it off by default and avoid one commit per UI click.
- [ ] Delegate credentials to normal Git/SSH/Git Credential Manager facilities; never store repository credentials in life.txt or lifetxt config.
- [ ] Document Git hooks, recovery, `.gitignore` guidance for generated/cache files, and the difference between built-in undo, snapshots, the mutation journal, and Git history.

---

## P1: Remote Safe Mode

This track starts only after P0 conflict safety and the public-deployment review are complete. Version 1 is single-user and does not attempt collaborative editing.

- [ ] Add a single-user Remote Safe Mode with password login and/or trusted reverse-proxy authentication while retaining the existing token mode for API clients.
- [ ] Use secure server-side sessions with protected cookies and CSRF protection for browser writes; do not expose long-lived bearer tokens to browser JavaScript.
- [ ] Keep account, session, share, audit, and rate-limit state outside life.txt, with life.txt remaining authoritative for user records.
- [ ] Add explicit access policies for private, authenticated, and read-only operation. Public write access must never be an implicit bind-address side effect.
- [ ] Add login throttling, session expiration and revocation, security headers, secure secret loading, and deployment diagnostics in `doctor`.
- [ ] Add an audit log for actor, surface, operation, target, before/after hash, result, and conflict without recording secrets unnecessarily.
- [ ] Add deployment guides for direct localhost use and reverse-proxy HTTPS deployments, including trusted proxy settings and disabled administrative routes.
- [ ] Define field/source redaction for public or shared output before adding public dashboards or links.
- [ ] Keep remote attachment upload/storage outside the first version; first define object hashing, authorization, size limits, and retention.

---

## P1: Workflow, Timer, Notification, and Attachment Follow-ups

- [ ] Add `next --explain` to show why each task was selected and why excluded tasks were blocked, deferred, or classified as someday.
- [ ] Add `lifetxt habit today` to materialize today's repeat-enabled habits idempotently with stable IDs and `--dry-run`.
- [ ] Add clipboard capture and a general multi-line editor flow to quick capture. Consider a `capture` alias only if it provides a clearer zero-friction workflow without duplicating semantics.
- [ ] Extend `inbox --fzf` with safe `show`, `assign`, `done`, and `edit` actions after real selector verification.
- [ ] Define one timer state model for start, stop, pause, resume, cancel, crash recovery, stale-state detection, session history, and optional item association.
- [ ] Add timer state validation, cross-platform locking, simultaneous CLI/Web action tests, midnight/timezone tests, and corruption recovery.
- [ ] Decide whether alarm, Pomodoro, stopwatch-only sessions, and timer logs belong in core or remain delegated to operating-system tools.
- [ ] Add a notification backend abstraction for terminal, Linux, macOS, Windows, email, and Web UI delivery.
- [ ] Add quiet hours, persisted acknowledgement/seen state, recurring reminder acknowledgement, shared snooze presets, and optional HTML multipart email while retaining canonical plain text.
- [ ] Add attachment add/verify/status actions to TUI and Web UI, not only opening and MCP attachment.
- [ ] Show attachment status in Web detail views without exposing unsafe server-local file links to remote users.
- [ ] Verify attachment opening on Windows, macOS, and Linux, including spaces, Unicode normalization, symlinks, executable rejection, case-sensitive filesystems, and paths outside the source directory.
- [ ] Add a safe cache for large `dir:` hashes keyed by normalized path metadata and verified content state.
- [ ] Decide how archive, undo, item moves, and remote use handle attachment paths that later move.
- [ ] Add invoice policy documentation and fixtures for rounding, rates, currencies, missing project names, and malformed elapsed values.
- [ ] Add standup team mode only after per-user output is stable; preserve a script-friendly JSON shape.
- [ ] Add ICS round-trip fixtures for all-day events, offset-aware events, attendees, recurrence, escaped text, and UID collisions.
- [ ] Define overwrite and conflict behavior before extending bidirectional calendar synchronization.
- [ ] Add todo.txt and GitHub Markdown idempotency fixtures so repeated imports do not create duplicate records.
- [ ] Add `.pre-commit-config.yaml` examples and document which life.txt filename patterns are checked.

---

## P2: Multi-User Sharing and Remote Attachments

- [ ] Add workspace-level Owner, Editor, Contributor, and Viewer roles only after single-user Remote Safe Mode is stable.
- [ ] Resolve `self` to a stable authenticated user identity before writing collaborative records; stored meaning must not change depending on who reads the file.
- [ ] Add expiring, revocable, optionally password-protected read-only share links scoped to a saved view or explicit filters.
- [ ] Add export and attachment permissions to share policies, and redact source paths and selected details consistently.
- [ ] Reuse the proposal approval flow for Contributor changes instead of granting direct unrestricted writes.
- [ ] Define a content-addressed remote attachment store or external object-store adapter with authorization, quotas, hash verification, and cleanup.

---

## P2: Web UI and Mobile Follow-ups Restored from Earlier Roadmaps

- [ ] Add a persistent Web command input, inline command results, argument completion, and `/undo` instead of requiring every command flow to start through a modal.
- [ ] Reconcile `/next` and other command semantics with the shared operation layer and add DOM-level command-handler tests.
- [ ] Make Review items clickable, add project/custom-date filters, export the shared Markdown representation, and calculate real current/longest habit streaks.
- [ ] Make Dashboard cards and limits configurable through named views rather than hard-coded layout-only settings.
- [ ] Add a Calendar day-detail popover and share recurrence-expansion limits with Timeline.
- [ ] Complete Web label localization, WCAG AA contrast, visible focus, tab semantics, live regions, skip links, reduced-motion behavior, and a supported high-contrast theme.
- [ ] Verify mobile behavior on real iOS Safari and Android Chrome, including safe areas, dynamic viewport height, toolbar scrolling, dialogs, and touch undo.
- [ ] Add visible affordances for horizontally scrolling mobile toolbars and revisit floating actions while a modal or bottom sheet is open.
- [ ] Keep an installable online-only PWA shell as a later P2 option; offline writes and Web Share Target capture remain Deferred until the proposal queue is safe.

---

## P2: TUI and CLI Usability Restored from Earlier Roadmaps

- [ ] Add an in-place field editor and multiline body editing to the TUI without forcing users to retype existing values.
- [ ] Add optional mouse support, `/timer pause|resume`, shared exporter reuse, an inline delete confirmation, and a preview of bulk-command targets.
- [ ] Add an archived-record view after multi-file/archive semantics are specified.
- [ ] Reconsider sorted-view limits so `/next` and due sorting can use a useful global top-N mode.
- [ ] Add a general shared output policy for JSON, quiet/verbose modes, color, `NO_COLOR`, pager behavior, stdin, and exit codes.
- [ ] Add East Asian Width and grapheme-aware table handling to every CLI renderer that still uses raw `len()`.
- [ ] Add safe batch operations such as tag rename, status set, and due-date shift through the shared mutation path with dry-run and per-file failure summaries.
- [ ] Add `templates.life.txt` support only if teams demonstrate a need for version-controlled templates beyond config-defined templates.

---

## P2: Editor, LSP, Documentation, and Examples

- [ ] Define which document is authoritative for grammar, CLI behavior, Web/API behavior, examples, and generated references.
- [ ] Add English/Japanese parity checks for headings, code blocks, command names, stable examples, and terminology.
- [ ] Add a bilingual glossary for stable format, diagnostics, CLI, and API terms.
- [ ] Package the VS Code grammar/snippets as an installable extension and generate key lists from model definitions.
- [ ] Add editor support for directives, encrypted values, folding, file icons, and syntax-highlight snapshots.
- [ ] Add a lossless parser/CST with source spans, comments, continuations, and exact ranges before implementing LSP edits.
- [ ] Implement LSP diagnostics first, then symbols, completion, hover, go-to-definition, safe code actions, references, and finally workspace rename after multi-file CAS is proven.
- [ ] Add worked examples and captures for TUI, Web views, timer, statistics, review, graph, attachments, invoice, standup, import/export, locks, conflicts, proposals, recovery, and Git/VCS.
- [ ] Document file splitting, generated files, archive files, cache files, multiple writers, backups, undo, mutation journal, Git recovery, and which paths belong in `.gitignore`.
- [ ] Add full AI integration guides with MCP client examples, CLI pipelines, privacy-sensitive local-model examples, proposal review, and automated summaries.
- [ ] Add a positioning/comparison guide and explicit non-goals for todo.txt, Taskwarrior, Org mode, Logseq, and GUI task managers.
- [ ] Add version-controlled starter kits for GTD, students/researchers, software development, journals/habits, freelance billing, team status, family boards, and AI-agent inboxes.

---

## P2: Tests, Packaging, Release, and Architecture

- [ ] Split `lifetxt/cli.py` into command-focused modules with a thin registry-based dispatcher.
- [ ] Split `lifetxt/tui_app.py` into state, command, layout, rendering, and terminal-adapter modules.
- [ ] Extract browser HTML/CSS/JavaScript from `webapp.py` into lintable package assets without requiring a mandatory frontend build.
- [ ] Raise the supported Python baseline to `>=3.10` after clean-environment verification and remove obsolete compatibility code deliberately.
- [ ] Expand CI to Ubuntu, Windows, and macOS, add coverage, and retain the dependency-free job as a required check.
- [ ] Expand `scripts/run_ci_like.py` and smoke tests with named `cli`, `web`, `mcp`, and `release` profiles plus an optional `doctor --ci` front end.
- [ ] Add parser fuzzing, compatibility fixtures, output snapshots, large-file benchmarks, recurrence performance tests, glob/path tests, real exporter fixtures, and end-to-end MCP/browser tests.
- [ ] Restore targeted archived tests that remain unimplemented: archive modes, encrypt/decrypt failures, plot outputs, init/doctor behavior, check filtering, undo concurrency, ambiguous matches, multi-file summaries, batch partial failures, inbox processing, migrations, and digest webhook payloads.
- [ ] Verify editable install, optional extras, console scripts, PowerShell usage, build artifacts, clean-wheel installation, and package data.
- [ ] Add release documentation and automation: changelog, semantic versioning, build, pre-release, tag, PyPI publication, and post-release smoke checks.
- [ ] Add `CONTRIBUTING.md`, issue templates, pre-commit configuration, `SECURITY.md`, supported-version policy, and private vulnerability reporting.
- [ ] Add repository discovery metadata, badges, screenshots, supported-platform information, and Format 1.0 compatibility links.
- [ ] Consider a zipapp or other single-file distribution only after wheel installation and the Python baseline are stable.

---

## P2: Additional Use-Case Features Restored from Earlier Roadmaps

- [ ] Add `import-ics --preset university` only after recurring-event materialization rules are stable.
- [ ] Add due-date countdown display options for agenda and dashboards without changing stored data.
- [ ] Add a built-in "mine" saved view once shared query and identity rules are stable.
- [ ] Add persona-based `demo` profiles and a clearly isolated temporary Web demo mode.
- [ ] Add scheduled auto-archive only after manual archive, recovery, and conflict behavior are well tested.
- [ ] Add `lifetxt todo-scan` for stable-ID TODO/FIXME import only after importer idempotency and source-move behavior are defined.
- [ ] Add a documented family-board kiosk recipe after Remote Safe Mode and recurring acknowledgement behavior are safe.
- [ ] Add localizable date display and week-start settings without changing canonical saved datetime values.
- [ ] Consider man-page generation after the command registry becomes authoritative.

---

## Deferred Ideas

- [ ] Defer automatic Git pull/push, general synchronization, and ID-based automatic three-way merge until Format 1.0, semantic diff, mutation journal, proposal approval, and conflict UX are stable.
- [ ] Defer a custom Git merge driver until the same ID-based merge model is proven through explicit dry-run plans.
- [ ] Defer offline PWA writes, Web Share Target writes, and background replay until an offline proposal queue carries source revisions and explicit conflict review.
- [ ] Defer a local daemon until notification watch, timer delivery, reload events, or remote operation demonstrably require one process.
- [ ] Defer named or parallel timers, full alarm management, and Pomodoro orchestration until the single-timer state model proves insufficient.
- [ ] Defer a general plugin SDK until schemas, mutation contracts, proposal boundaries, and one out-of-tree official adapter validate the design.
- [ ] Defer a rebuildable search index until large-file benchmarks demonstrate a practical bottleneck.
- [ ] Defer richer bidirectional adapters such as CalDAV, mailbox logs, Teams, Discord, and Slack until field ownership and conflict policies are explicit.
- [ ] Defer asymmetric multi-user encryption until identity, authorization, key rotation, and recovery requirements are defined.
