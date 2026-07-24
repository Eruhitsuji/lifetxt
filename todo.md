# lifetxt TODO / Roadmap

Last updated: 2026-07-24 (updated x103)

This is the active roadmap after the 2026-07-24 semantic-write, attachment-transaction, compound-work-session, transaction-policy, clock-audit, diagnostics, and schema-contract batch, followed by the project-management, integration, and configuration roadmap review. The implementation batch moved quick capture, quick journal append, archive, undo/restore, tag merge, digest/template append, TUI item edits, and fzf/peco actions onto revision-aware semantic transforms; added journal-backed file attachment create/reference/delete/status operations and compound timer/task/presence work sessions across CLI, Web, and MCP; added configurable transaction retention and size policy, ownership and mode checks, read-only inspection of newer journal versions, evidence archives, backup integrity manifests, and deterministic fault-injection hooks; classified direct host-clock boundaries through a release-gated AST audit; added diagnostics F127-F134; expanded the published Draft 2020-12 schema bundle from 21 to 29 documents; and removed the legacy `compat_writes` module. The roadmap review adds versioned configuration and named-workspace foundations, stronger project and portfolio workflows, provider-neutral chat/email integration contracts, automatic source discovery through workspace manifests, and configuration documentation as an implementation acceptance criterion. Existing top-level `paths` / `write_file`, SMTP notification, digest delivery, and external-adapter groundwork are treated as foundations to extend rather than missing features to reimplement. Completed foundation items are removed. Remaining P0 work now focuses on the real observe-to-required deployment, external-editor and directory/open-reference attachment boundaries, real process and platform fault injection, policy operations and runbook hardening, remote clock-skew behavior, and real terminal/browser/SMTP verification. The previous detailed roadmap remains preserved in [`docs/roadmap-archive-2026-07-20.md`](docs/roadmap-archive-2026-07-20.md).

Priority guide:

- `P0`: Release-blocking data safety, correctness, migration, and real-environment verification.
- `P1`: Core format, configuration/workspace behavior, project management, remote access, integrations, messaging, timer/notification behavior, and daily workflow work.
- `P2`: Product customization, packaging, documentation, editor support, and maintainability.
- `Deferred`: Ideas that should wait for a proven use case or a stable foundation.

Design principles:

- Fail loudly when behavior is ambiguous or data may be lost.
- Keep life.txt authoritative and use standard, inspectable interchange formats.
- Route authoritative writes through validated, atomic, conflict-aware mutation contracts.
- Treat compensated multi-target commits as an explicit recovery contract, not as portable filesystem-level atomicity.
- Keep CLI, TUI, Web API, Web UI, MCP, editor support, schemas, configuration, and documentation semantically aligned.
- Make effective configuration deterministic, explainable, schema-valid, and safe to migrate before allowing it to control remote access, integrations, or automatic writes.
- Prefer lifetxt as an action and information hub over copying every external system's full data into life.txt.
- Treat remote access, integrations, and automation as proposal-producing clients unless a validated write contract permits direct mutation.
- Treat a successful release gate as evidence, not as permission to ignore known baseline debt.
- Preserve old public CLI behavior when introducing richer reports; use explicit modes or unambiguous new flags.

Feature-track order after the current P0 foundation:

1. Complete the real observe-to-required revision rollout and migrate external-editor and remaining open-reference write boundaries.
2. Validate attachment and compound work-session recovery under real process termination, power-loss, filesystem, and platform fault injection.
3. Complete transaction-policy operations, migration, bounded archival, and the operator recovery runbook.
4. Expand deterministic timezone fixtures across every public surface and define remote clock-skew handling.
5. Stabilize Format 1.0, canonical serialization, multi-file semantics, diagnostics, and contract schemas.
6. Add versioned configuration, effective-config explanation, named workspaces, and source manifests while preserving top-level `paths` / `write_file` compatibility.
7. Add project registry metadata, project/portfolio aggregations, milestones, risks, decisions, and shared Project Hub views.
8. Add single-user Remote Safe Mode and read-only remote CLI/TUI access using the same workspace contract.
9. Enable conflict-aware remote writes only for operations whose capability entries report complete revision and recovery enforcement.
10. Add Unified Inbox, daily command-center views, saved views, and life-area navigation.
11. Add managed groups, multi-recipient messaging, and per-recipient delivery state.
12. Add the provider-neutral integration contract, then implement Slack and email proposal/output adapters before Teams and Discord.
13. Add Web UI configuration and richer provider automation only after proposal, audit, permission, credential, and recovery boundaries are stable.

---

## P0: Release Safety and Correctness

- [ ] Execute and finish the strict Web revision migration in a real deployment. The metrics store can be exported, relocated with an exact revision, optionally moved with a journaled source deletion, and verified without leaking its local path. Next deploy `web.revision_mode: observe`, preserve the store across package upgrades and deployment moves, document the exact observation start, migrate every supported browser/API client to revision discovery and `If-Match`, require a complete zero-use window, switch supported deployments to `required`, and remove the temporary fallback and compatibility cookie only after the evidence is reviewed. Add an end-to-end upgrade matrix covering container replacement, read-only old paths, permission changes, restored backups, rollback to an older server, attachment clients, work-session clients, and recovery-required server startup.
- [ ] Finish authoritative write migration at process-boundary operations. Quick capture, journal append, archive, undo/restore, tag merge, digest/template append, normal TUI edits, and fzf/peco item actions now use semantic revision-aware transforms, and `compat_writes` is removed. Next define revision-safe behavior for external editor suspension/resume, editor-created replacements, commands that intentionally hand control to another process, plugin-provided mutations, directory attachment import, and attachment open-reference changes. Require an exact pre-edit revision, show a reviewable diff after return, reject changed files unless explicitly reconciled, and add one-winner/one-conflict tests for every remaining boundary.
- [ ] Finish public attachment and compound-work-session integration beyond regular files. File attachment create, reference, delete, and status operations and compound timer/task/presence start/stop now use journal-backed contracts across CLI, Web, and MCP. Next add directory and package attachments, safe open-reference metadata updates, externally modified attachment reconciliation, bounded large-file streaming, MIME and platform policy, recovery after a client restart, and capability rows that report exact touched targets, revision requirements, validation schemas, and recovery behavior. Keep remote attachment and compound-session writes disabled until those capability rows are complete and protocol-level partial-failure, restart, compensation, and diverged-recovery tests pass.
- [ ] Prove durable recovery under real failure modes. Deterministic fault-injection hooks now cover journal publication, target replace/delete, directory fsync, commit verification, and compensation boundaries. Next run those hooks in child processes with forced termination before and after every boundary; add abrupt interpreter termination, disk-full, quota, permission, ownership-change, corrupted or missing artifact, repeated recovery, Windows replace, antivirus/file-indexer, cloud-synchronized directory, removable-media, and network-filesystem tests. Publish the supported filesystem matrix and never mark a transaction recovered solely from journal state.
- [ ] Complete transaction-journal retention, privacy, and administrative operations. Configurable terminal retention, journal count and byte limits, ownership/mode checks, evidence archives, backup integrity manifests, and read-only inspection of newer journal versions are available. Next add a versioned policy configuration surface, journal migration for supported old versions, refusal rules for unsupported migration paths, bounded encrypted or access-controlled evidence archives, atomic policy updates, archive rotation, operator identity in administrative audit events, automatic preflight checks before Web/MCP startup, and a complete runbook for resume, compensate, abandon, restore, evidence preservation, and escalation.
- [ ] Complete deterministic timezone behavior across public surfaces. Direct host-clock calls are now classified by a release-gated AST audit, and unclassified additions fail policy validation. Next build one shared fixture table for CLI/file/config/host precedence, aware and naive values, time-only anchors, DST gaps and folds, non-hour offsets, midnight boundaries, historical timezone-rule changes, and remote clock skew; run it through CLI, TUI, Web, MCP, notifications, saved views, import/export, and work sessions; define skew tolerances and server-authoritative timestamp behavior; and retire baseline allowances when their compatibility or operational purpose disappears.
- [ ] Verify the dependency-free TUI in real WSL, Windows Terminal, macOS, and Linux terminals. Cover colors, glyph fallback, narrow layouts, editor suspension, auto-reload, revision refresh, timezone display, semantic mutation conflicts, multi-file transactions, attachment status, compound work sessions, stale-lock guidance, and recovery from an interrupted operation.
- [ ] Verify `fzf` and `peco` actions end to end on Windows PowerShell and Unix-like shells. The actions now route through semantic transforms, but real-shell verification must cover stale revisions, multi-selection, preview quoting, edit suspension, delete confirmation, non-ASCII paths, spaces, symlinks, mixed-source selections, all-or-none multi-file commits, and shell-specific exit-code propagation.
- [ ] Verify SMTP delivery with safe test accounts. Cover STARTTLS negotiation, authentication failure, app-password guidance, multiple recipients, retry/backoff, watcher state, quiet hours, redacted logging, and provider-specific message-size/rate-limit behavior without committing secrets.
- [ ] Add browser-engine smoke tests for the Web UI. Cover revision discovery, observe/required migration, persistent metrics export, ETag stripping/rewrite recovery, attachment and compound-work-session operations, mobile layout, keyboard navigation, command execution, undo, dialogs, charts, timeline edge cases, timezone display, stale revisions, accessibility focus, interrupted-transaction recovery, and browser restart. Keep FastAPI/TestClient tests as the lower-level API contract rather than describing them as browser coverage.

---

## P1: Format 1.0 and Data Semantics

- [ ] Complete Format 1.0 enforcement beyond the mutation guard. Add parser-level version metadata, explicit `format migrate` and downgrade inspection, consistent unsupported-version errors in CLI/TUI/Web/MCP, newly-created-workspace policy, and a compatibility matrix covering format, canonical, schema, capability, revision, configuration, release-policy, and transaction-journal versions.
- [ ] Complete `LIFETXT_CANON_V1`. Define quoting, escaping, detail ordering, repeated-key ordering, continuation representation, comments, directive placement, blank-line behavior, Unicode edge cases, and idempotent serializer output. Add golden input/output/diagnostic fixtures and prohibit intentional output changes without a migration note and corpus-version decision.
- [ ] Enforce documented multi-file semantics. Make input/glob order deterministic and visible; enforce workspace-wide IDs during every write; define cross-file parent/link/archive/generated-file rules; preserve source metadata; require explicit write targets; and test partial-read, missing-file, permission, and path-alias cases.
- [ ] Expand the schema bundle beyond the current 33 documents where real contracts exist. Semantic write results, archive operations, attachment transactions, compound work sessions, transaction policy, backup integrity, fault-injection reports, clock-boundary audit, versioned configuration (`config-v1`), workspace source manifests (`workspace-source-manifest-v1`), project registry metadata (`project-registry-v1`), and project summaries (`project-summary-v1`) documents are now published and validated. Next add JSONL record schemas, endpoint-specific Web request/response schemas, MCP tool/resource result schemas, query language, normalized integration events, provider operation results, notification backend results, directory attachment packages, policy migration results, and import/export manifests. Generate schemas from authoritative registries where possible and validate real responses rather than hand-written examples alone.
- [ ] Extend stable diagnostics after F101-F134. Attachment path escape, symlink and executable policy violations, transaction retention and permission problems, unsupported newer journal versions, and incomplete backup integrity are now detected in addition to transaction interruption and divergence. Next add generated-file ownership violations, archive destination policy conflicts, directory-package attachment hazards, MIME-policy mismatches, mixed-source configuration conflicts, configuration/profile/include cycles, schema/capability mismatch, unsupported client and policy versions, failed policy migration, stale evidence archives, remote clock skew, and parser-native precise end spans. Keep diagnostics deterministic and schema-valid.
- [ ] Route legacy `check --format json` to the stable diagnostic shape. Preserve `source`, `line`, `column`, `span`, `code`, `severity`, `message`, and `hint`; compare CLI/Web/MCP output using the same fixture table; publish compatibility guarantees; and provide a transition period for scripts that consumed the old shape.
- [ ] Add conservative typo suggestions and `check --fix` only after canonical ordering/quoting is final. Every repair must be revision-checked, idempotent, reviewable as a diff, limited to unambiguous transformations, and disabled for unsupported format versions or interrupted transactions.
- [ ] Extend the golden-corpus policy when a second released format/corpus version exists. Keep version-1 cases immutable, run all prior corpora against new parsers/serializers/diagnostics, add downgrade expectations, and require explicit migration/release notes before accepting intentional changes.

---

## P1: Shared Surface Contracts

- [ ] Expand the registry-backed operation layer into real surface-neutral implementations for query, add, update, delete, done, repeat completion, agenda, next selection, timezone conversion, links, messaging, proposals, saved views, workspaces, projects, portfolios, integrations, remote access, timer actions, attachments, archive, and undo. Registry rows must identify required revisions, touched targets, validation schema, read-only availability, recovery behavior, and supported surfaces.
- [ ] Extend public-contract tests through CLI and TUI. Reuse the Web/MCP fixture semantics for create, stale/missing revisions, validation failure, lock timeout, read-only mode, unsupported format, missing capability, proposal staging, compound operations, multi-file partial failure, compensation, interrupted journals, and recovery failure.
- [ ] Complete the registry-derived command/capability drift gate. Generate CLI/TUI/Web/MCP availability from one registry; validate actual `/api/capabilities`, `get_capabilities`, and `lifetxt://capabilities`; include package/server version and installed/configured optional features; and require a documented exception for every surface mismatch.
- [ ] Continue reducing the direct-write baseline. Digest/template append operations and fzf item actions now use semantic CAS operations, and obsolete compatibility allowances are removed. Next move every remaining configuration output to the atomic config writer, classify editor handoff and attachment import boundaries explicitly, retain generated-schema output only as a generated artifact, and fail review when an allowance lacks a reason, owner, removal condition, and roadmap item.
- [ ] Move all extension dispatcher commands into the unified parser registry during the CLI module split. Generated help, shell completion, Web command palette, docs, and capability responses must consume the same option definitions without entrypoint special cases.
- [ ] Add structured proposal metadata and item-level diffs. Include source, provenance, assumptions, warnings, expected revisions for every target, side-effect plan, permission requirements, validation results, and compensation/recovery plan. Require an expected revision or explicit unsafe override before applying.
- [ ] Define a shared query language and saved-view schema. Reuse the same grammar and typed diagnostics in CLI, TUI, Web, MCP, remote clients, project/portfolio views, dashboards, sharing, and automation; define escaping, grouping, date/timezone behavior, unknown fields, ordering, limits, and version migration.
- [ ] Extend `doctor --workspace-safety` beyond automatic timer/journal discovery, transaction-state summary, attachment checks, transaction-policy checks, backup-integrity checks, terminal-journal cleanup, and redacted support-bundle export. Next discover directory/package attachment state, every resolved workspace source and write target, duplicate physical paths, configured schema and generated-file locations, remote profiles, integration credentials by reference only, policy migration requirements, and remote clock skew; add interactive confirmation for stale-lock and recovery cleanup while retaining explicit `--force` for non-interactive use; validate support bundles against named privacy profiles; and add a bounded, access-controlled archive option for complete recovery evidence.
- [ ] Decide which report commands need Web/MCP equivalents from demonstrated daily use. Avoid adding a surface only for symmetry; require a shared operation, schema, and permission model first.

---

## P1: Configuration and Workspace Foundation

The existing top-level `paths` and `write_file` settings already provide basic default input and output selection. This track preserves that behavior as an implicit default workspace and extends it into a versioned, explainable, multi-workspace source manifest rather than introducing a second unrelated loading mechanism.

The foundation now exists across [`lifetxt/workspace.py`](lifetxt/workspace.py), [`lifetxt/config_layers.py`](lifetxt/config_layers.py), [`lifetxt/config_registry.py`](lifetxt/config_registry.py), [`lifetxt/config_validation.py`](lifetxt/config_validation.py), [`lifetxt/config_writer.py`](lifetxt/config_writer.py), and [`lifetxt/config_migration.py`](lifetxt/config_migration.py): a versioned source-manifest model (`path`, `role`, `required`, `writable`, `default_visible`, `format`, `priority`, `watch`, `privacy`, `generated_by`, `exclude`) with legacy `paths`/`write_file` treated as an implicit `workspaces.default`; a tested precedence model (built-in defaults → config file → profile → environment → CLI flags) with provenance; named workspaces and profiles with an explicit `default_workspace`; relative-path resolution against the configuration directory with deterministic glob order and WS001-WS013 diagnostics (missing required, duplicate physical file, symlink alias, generated/archive write target, excessive source count); the global `--workspace NAME` flag; `lifetxt workspace list|show|files|validate|doctor` with `files --resolved` reporting role/mode/origin/matched-glob/reason; `lifetxt config effective|sources|get|set|unset|explain|check|migrate`; `config_version` write-gating and a plaintext-secret credential policy; a schema-validated atomic config writer with bounded `.bak` rotation; non-destructive legacy→workspace migration; `config-v1.schema.json` and `workspace-source-manifest-v1.schema.json`; runnable `examples/config/*` (personal, work, project, generated-calendar, team, kiosk) validated against the schema and the credential policy; and English/Japanese `docs/*/config.md`. Remaining work extends and hardens that foundation.

- [ ] Complete `config_version` migration rules in the registry (multi-step upgrade/downgrade guidance and per-key `since`/`deprecated`/`replacement` coverage generation for docs). Write-gating for unsupported versions and read-only inspection already work.
- [ ] Extend the atomic config writer to be revision/CAS-aware: reject stale updates against a discovered pre-write revision and retain a recovery record beyond the bounded `.bak` rotation. Schema validation, credential-policy enforcement, atomic replace, and bounded backups already exist.
- [ ] Extend workspace resolution to detect true symlink loops (self-referential cycles) and excessive total source byte size, in addition to the existing alias, generated-target, and source-count checks.
- [ ] Thread `--workspace` into the TUI and add per-workspace timezone/notification context so remote and Web surfaces select the same resolved manifest, not just CLI read/write paths.
- [ ] Add schema-valid examples for remote and integration workspaces beyond the current personal/work/project/generated-calendar/team/kiosk set. Test Windows/POSIX paths, Unicode, broken JSON, unknown keys, cycles, missing files, glob order, and rollback after interrupted config updates.

---

## P1: Project and Portfolio Management

The read side now exists in [`lifetxt/projects.py`](lifetxt/projects.py): projects are built from `project:` details and `record:project|milestone|risk|issue|decision|meeting` records (documented custom keys, no new item type); a schema-backed registry (`projects` config + `project-registry-v1.schema.json`) supplies display name, aliases, default source/assignee/area, templates, and visibility while changing data stays in records; `project list|show|health|timeline|workload|risks` plus a single `project show` hub aggregation and a `portfolio` comparison are wired in the CLI; every derived number exposes its formula and missing-data limitations (progress = done/non-cancelled tasks, transparent green/yellow/red health, blocked via `depends_on:`, overdue via reference date); `project new` and `project add milestone|risk|decision|meeting` append records to the resolved workspace write target with `--dry-run`; a `project-summary-v1.schema.json` is published; and English/Japanese `docs/*/projects.md` plus `examples/config/projects.lifetxt.json` document it. Remaining work adds writes-that-move, cross-surface exposure, and privacy.

- [ ] Add a `project archive` workflow that moves a project's records to a configured archive source through the workspace transaction/recovery contract, never creating a write target outside the resolved source manifest. Read aggregation, `project new`, and `project add` already exist.
- [ ] Expose the existing `project`/`portfolio` operations through TUI, Web, MCP, saved views, and remote read-only clients where capabilities permit, reusing the shared `lifetxt/projects.py` aggregation rather than reimplementing it per surface.
- [ ] Add validation for milestone/risk/issue/decision/meeting records (severity enum, resolution state, decision/follow-up dates, affected milestone links) and surface violations as stable diagnostics. Templates and record builders already exist.
- [ ] Add project permissions and privacy behavior for remote workspaces, team views, integrations, exports, AI context, and notifications. Tests must cover duplicate project definitions, missing registries, cross-file tasks, archived/renamed projects, stale revisions, partial transactions, and mixed private/shared records. Alias resolution and registry-only projects are already covered.

---

## P1: Remote Safe Mode and Remote Workspace Access

This track starts only after revision migration, authoritative write routing, stable schemas, versioned configuration/workspaces, and the public-deployment security review are complete. The first release is single-user and does not attempt offline synchronization or automatic merging.

- [ ] Add single-user Remote Safe Mode with password login and/or trusted reverse-proxy authentication while retaining scoped token authentication for API clients.
- [ ] Use secure server-side sessions, protected cookies, CSRF protection for browser writes, login throttling, session expiration/revocation, security headers, environment-backed secrets, and auditable authentication events.
- [ ] Derive capability optional-feature availability from installed dependencies and configuration. Include package/server/policy/schema/transaction/configuration versions and publish older-client compatibility rules.
- [ ] Define a shared `WorkspaceBackend` interface with `LocalFileBackend` and `RemoteApiBackend` so CLI/TUI commands do not reimplement local-versus-remote behavior.
- [ ] Add `lifetxt remote add|list|show|test|remove NAME`. Store non-secret profile values under the published remote-profile schema and reference credentials through environment variables or OS credential facilities.
- [ ] Add read-only remote operations for list, show, filter, agenda, next, review, messages, status, links, graph, diagnostics, completion, projects, portfolios, workspace source inspection, and doctor compatibility inspection.
- [ ] Add `lifetxt tui --remote NAME` with read-only browsing first. Reuse normal TUI rendering, commands, timezone context, diagnostics, and capability negotiation.
- [ ] Add conflict-aware remote create/update/delete/done/message/status/acknowledgement only after observe mode is retired. Defer timer, attachment, archive, project creation/archive, workspace configuration, and undo remote writes until capability entries report complete multi-target and recovery enforcement.
- [ ] Validate remote conflicts against `conflict-v1.schema.json` and show expected revision, current revision, current item, and attempted change. Never overwrite automatically or call a comparison a three-way merge without a retained base.
- [ ] Start refresh with explicit reload and bounded polling. Add SSE/WebSocket only after reconnect, ordering, backpressure, and missed-event behavior are specified and polling is demonstrably inadequate.
- [ ] Keep remote/local transfer explicit through export, copy, or proposal import. Do not add background bidirectional synchronization in this track.
- [ ] Add diagnostics for TLS, authentication, clock skew, schema/capability/configuration mismatch, read-only mode, proxy configuration, ETag removal/rewrite, transaction-version mismatch, and server recovery state.
- [ ] Test remote CLI/TUI against stale revisions, expired sessions, interruption, retries, multi-file workspaces, older servers, required mode, proxies that alter ETags, and servers recovering an interrupted transaction.

---

## P1: Messaging, Groups, and Delivery State

- [ ] Add a group directory with config-defined local groups and server-managed remote groups. Define nested groups, cycle detection, duplicate removal, disabled members, deterministic expansion, visibility, and version migration using `group-v1.schema.json`.
- [ ] Add shared message composition for CLI/TUI/Web/API/MCP with repeated direct recipients plus teams/groups and an explicit preview of the resolved set.
- [ ] Add `message send`, `message recipients`, `group list`, `group show`, and `group validate` from the shared command/capability registry.
- [ ] Preserve both original group references and the resolved recipient set required for audit while keeping the authored Message item readable.
- [ ] Implement per-recipient pending/delivered/failed/read/acknowledged/skipped state using `delivery-state-v1.schema.json`. Decide authoritative versus operational storage and apply revision/multi-target rules accordingly.
- [ ] Add acknowledgement policies for `any`, `all`, and explicit counts, including group membership changes after message creation.
- [ ] Add recipient-specific acknowledgement and snooze. One recipient must not complete a multi-recipient message unless policy permits it.
- [ ] Add delivery progress, resend controls, and partial-failure presentation to the Web Messages view and detail modal.
- [ ] Add permission checks for group visibility, recipient discovery, messaging, delivery-state visibility, and administrative changes.
- [ ] Route terminal, desktop, email, Web, and future provider delivery through one backend contract that records outcomes without storing credentials in life.txt.
- [ ] Add tests for repeated recipients, direct-plus-group duplicates, nesting, cycles, empty groups, disabled members, partial delivery, acknowledgement completion, resend, and membership changes.

---

## P1: Integration Adapter Foundation

- [ ] Publish a normalized integration-event schema and a provider capability model for inbound messages/events, outbound messages/actions, thread/reply references, attachments, acknowledgement, health, and cursor state. Preserve provider IDs and provenance without treating provider-specific payloads as life.txt syntax.
- [ ] Define one `IntegrationAdapter` contract for receive, normalize, preview, stage proposal, send, acknowledge, health, and capabilities. Inbound changes must default to reviewable Unified Inbox proposals unless an allow-listed operation has explicit direct-write permission and recovery semantics.
- [ ] Add idempotency keys, provider cursors, duplicate suppression, bounded retry/backoff, rate-limit handling, partial-failure reporting, dead-letter inspection, restart-safe state, and redacted audit events. Provider outages must not block unrelated local lifetxt operations.
- [ ] Keep credentials outside life.txt and plaintext configuration. Store only environment-variable or OS credential references, define token scopes and rotation checks, and ensure logs, effective config, diagnostics, exports, and support bundles never expose secrets.
- [ ] Add schema-validated mapping rules for provider account/workspace/channel/user/group/thread to lifetxt workspace, project, area, recipient, tags, and proposal policy. Detect ambiguous identity mappings and require preview before broad rule activation.
- [ ] Implement Slack and email first because existing digest/SMTP foundations can validate the outbound contract. For Slack, cover channel input, message output, thread replies, user/group mapping, and digest delivery. For email, cover SMTP output, IMAP or provider-API input, thread/message IDs, sender/subject rules, reply behavior, and safe attachment references.
- [ ] Implement Discord and Teams only after the common contract and Slack/email operational evidence are stable. Cover webhook/bot or API capability differences, channel/team mapping, replies, rate limits, permission scopes, and provider-specific unsupported operations without faking symmetry.
- [ ] Keep external attachments reference-first. Copy or transform content only through the attachment transaction, MIME, size, privacy, permission, and recovery policies; never silently mirror an entire mailbox or chat history.
- [ ] Add `integration list|show|test|pull|preview|send|health` and expose configured/installed capability state through doctor, Web administration, and MCP without returning credentials. Add fixtures and provider sandboxes/mocks for duplicate delivery, cursor reset, rate limits, revoked credentials, partial send, malformed payloads, restart, and proposal approval conflicts.

---

## P1: Life Hub and Information Unification

- [ ] Add a Unified Inbox for quick capture, Web Share Target, MCP suggestions, remote changes, and normalized external integration events as reviewable proposals with source, provenance, assumptions, warnings, schemas, and item-level diffs.
- [ ] Add accept, edit, reject, defer, and atomic batch-apply actions. Accepted batches must pass permission, validation, expected-revision, multi-target, and recovery checks.
- [ ] Add one daily command-center aggregation used by `today`, morning/evening briefs, TUI, Web Dashboard, and remote clients. Include agenda, overdue/due-today, timers, unacknowledged messages, habits, waiting work, project milestones/risks, recent captures, and safety warnings.
- [ ] Define optional `area:` above `project:` with custom-key compatibility, filtering, completion, saved views, validation, and documentation before treating it as core.
- [ ] Provide area presets only as examples (`work`, `research`, `health`, `home`, `finance`, `family`, `learning`), never as a mandatory taxonomy.
- [ ] Add person/group overview views collecting assigned work, meetings, messages, presence, projects, waiting items, links, and memberships without duplicating records.
- [ ] Add decision and meeting workflows using Note/Journal records and stable links before considering new item types. Provide templates for agenda, decisions, actions, unresolved questions, owners, and follow-up dates.
- [ ] Add backlinks and related navigation across parent/ref/depends_on/blocks/related, messages, decisions, meetings, people, groups, attachments, projects, milestones, risks, and external URLs.
- [ ] Expand global search across title, details, body, threads, attachment names, people, groups, projects, areas, decisions, URLs, and proposal metadata. Keep direct scanning until benchmarks justify an index.
- [ ] Add declarative automation only after proposals, audit logs, permissions, conflict-aware writes, transaction recovery, integration idempotency, and credential boundaries are stable. Use allow-listed triggers/actions and never execute arbitrary code.
- [ ] Consume provider integrations through the normalized adapter contract. Store references/summaries when email, calendar, GitHub, Slack, Teams, Discord, browser capture, or mobile sharing remains authoritative, and make every external side effect previewable and auditable.
- [ ] Add privacy controls and redaction for personal, health, finance, family, and work data in shared views, remote responses, AI context, exports, support bundles, telemetry, integrations, and notifications.

---

## P1: Timer and Notification Foundation

- [ ] Decide and document the single-timer scope boundary before adding alarms, Pomodoro, or parallel timers.
- [ ] Define one timer state model for start, stop, pause, resume, cancel, crash recovery, stale detection, associated items, timezone behavior, and schema versioning.
- [ ] Complete timer capability enforcement after the implemented journal-backed start, stop, pause, resume, and cancel paths. Migrate compound work-session operations, define stale-state and restart semantics for every action, validate actual CLI/Web/MCP responses against `timer-operation-v1.schema.json`, and set capability enforcement true only when every advertised timer route exposes revisions and recovery behavior.
- [ ] Decide whether alarm, Pomodoro, and timer logging belong in core or remain delegated to OS tools based on real usage and notification-backend maturity.
- [ ] Add a notification backend abstraction for terminal, Linux, macOS, Windows, email, Web, Slack, Teams, and Discord delivery with typed results, provider capability checks, and redacted diagnostics.
- [ ] Add quiet hours, persisted acknowledgement, recurring-reminder acknowledgement, shared snooze presets, timezone-aware scheduling, retry policy, restart-safe watcher state, and provider-specific rate-limit handling.

---

## P1: Workflow Follow-ups

- [ ] Expand deterministic-clock coverage beyond the implemented clock context and timer/time-only cases. Add one shared table for `next`, standup, invoice, review selectors, workload, journal defaults, notification watchers, completion dates, recurrence, ICS conversion, Web dashboard ranges, MCP resources, TUI commands, project/portfolio reports, and integration timestamps across midnight, DST, non-hour offsets, and remote clock skew.
- [ ] Add `next --explain` showing selection reasons and exclusions caused by blockers, deferred state, someday classification, user/project/context filters, or missing capabilities.
- [ ] Add invoice policy documentation and fixtures for rounding, rates, currencies, missing projects, malformed elapsed values, and timezone/date-boundary behavior.
- [ ] Add standup team mode only after per-user output is stable; retain a script-friendly schema.
- [ ] Add ICS round-trip fixtures for all-day events, offsets, attendees, recurrence, escaped text, UID collisions, timezone identifiers, DST boundaries, and cancellation.
- [ ] Define overwrite/conflict behavior before bidirectional calendar synchronization or broader `sync-ics --merge-existing` behavior.
- [ ] Add todo.txt and GitHub Markdown idempotency fixtures so repeated imports do not duplicate records.
- [ ] Verify attachment opening on Windows/macOS/Linux, including spaces, symlinks, executables, outside-root paths, deleted files, and transaction recovery.
- [ ] Add a safe large-`dir:` hash cache keyed by path metadata and content-verification state.
- [ ] Expose recurrence preview through agenda/Web/MCP by reusing `recurrence.expand` rather than re-deriving dates per surface.
- [ ] Decide on `BYSETPOS`, `BYWEEKNO`, and `BYYEARDAY` only from real use; visible rejection remains the default.
- [ ] Add an RRULE message drift guard so validator and engine semantics stay synchronized.
- [ ] Add `RDATE` support alongside `EXDATE`.
- [ ] Add rolling-window re-expansion so previously expanded files do not silently become stale.
- [ ] Define how archive/undo and transaction recovery handle attachments whose paths move after the original operation.

---

## P2: Web UI Customization

- [ ] Add a schema-validated Web settings UI backed by the shared configuration registry for supported `web.*` values with defaults, provenance, reset, preview, validation diagnostics, and restart-required indicators.
- [ ] Make navigation configurable: visible views, order, default view, role/device presets, mobile navigation, and administrative-only surfaces.
- [ ] Add allow-listed custom dashboard cards using the shared saved-view/query model with title, query, grouping, range, limit, width, and display mode.
- [ ] Add drag/drop card ordering and add/remove controls while keeping text configuration authoritative and exportable.
- [ ] Add configurable Items columns, order, density, sorting, grouping, and type-specific fields.
- [ ] Add configurable quick-add defaults, date formats, week start, icons, semantic colors, and view-specific empty states.
- [ ] Add desktop/mobile previews and versioned configuration import/export with migration diagnostics.
- [ ] Add personal, work, project, portfolio, team-board, kiosk, and mobile-capture presets composed from normal settings.
- [ ] Keep arbitrary CSS administrator-only and disabled by default; keep arbitrary JavaScript and third-party in-page plugins deferred.
- [ ] Add browser tests for invalid settings, missing tokens, contrast, responsive layouts, preset migration, import/export, provenance display, interrupted config updates, and broken-config recovery.

---

## P2: CLI, Packaging, and Distribution

- [ ] Route extension commands through the unified parser registry so help, docs, and option completion are authoritative.
- [ ] Cache completion values by path and metadata after benchmarks define invalidation behavior; apply the same cache to Web completion.
- [ ] Complete command arguments in the Web command palette.
- [ ] Add completion to `assist --interactive`.
- [ ] Split `cli.py` into command-focused modules with a thin registry dispatcher.
- [ ] Split `tui_app.py` into state, command, layout, rendering, and mutation/recovery presentation modules.
- [ ] Raise the supported Python baseline only after clean environment, wheel, dependency, and downstream compatibility verification.
- [ ] Expand required CI to Ubuntu, Windows, and macOS with coverage and the dependency-free job.
- [ ] Add `doctor --ci` only after legacy doctor and workspace-safety report schemas have a stable unified registry entry.
- [ ] Add release automation for changelog, semantic versioning, signed/attested artifacts, tag, PyPI publication, and post-release smoke checks.
- [ ] Add `CONTRIBUTING.md`, issue templates, pre-commit, `SECURITY.md`, supported-version policy, and private vulnerability reporting.
- [ ] Consider zipapp or another single-file distribution only after wheel and supported-Python behavior are stable.

---

## P2: Configuration and Integration Documentation

Configuration documentation is part of the acceptance criteria for every new setting. A setting is not complete when only the implementation or template changes; its schema metadata, CLI explanation, examples, migration behavior, and Japanese/English documentation must change together.

- [ ] Add `docs/en/config.md` and `docs/ja/config.md` as task-oriented guides covering discovery order, minimum configuration, precedence, profiles, workspaces, source manifests, write targets, environment references, validation, effective values, and common personal/work/team examples.
- [ ] Add complete `config-reference.md` documents in English and Japanese. For every key, publish type, default, required status, allowed values, environment override, restart requirement, secret status, version introduced/deprecated, example, and related command.
- [ ] Add dedicated English/Japanese `workspaces.md`, `integrations.md`, and `config-migration.md` guides covering path resolution, roles, glob expansion, read-only/generated/archive sources, provider credentials, proposal mode, mapping, retry/privacy/audit, compatibility, backup, rollback, and troubleshooting.
- [ ] Generate the mechanical reference tables and `config explain` registry data from the authoritative configuration schema/registry. CI must fail when a schema key lacks reference coverage, a deprecated key lacks migration guidance, a secret key lacks a security warning, or checked-in examples are not schema-valid.
- [ ] Add runnable example configurations for one file, multiple project files, generated calendars, personal/work profiles, remote access, Slack/email integrations, Teams/Discord placeholders, notifications, Web customization, and project/portfolio views. Test examples on Windows-style and POSIX paths without committing credentials.

---

## P2: Documentation, Editor, and LSP

- [ ] Define authoritative documents for grammar, CLI behavior, Web/API behavior, schemas, configuration, integrations, recovery, and examples.
- [ ] Add English/Japanese parity checks for headings, code blocks, command names, stable examples, configuration/workspace/integration docs, revision/timezone/workspace-safety docs, and recovery docs.
- [ ] Extract the Web Japanese dictionary into shared data usable by CLI/TUI/MCP.
- [ ] Define policy for languages beyond Japanese, fallback, partial dictionaries, and untranslated text.
- [ ] Add worked examples and captures for TUI, Web, timer, statistics, review, graph, attachments, reports, project/portfolio management, integration proposals/output, import/export, diagnostics, Format migration, configuration migration, revision negotiation, timezone behavior, multi-target recovery, remote workspaces, messaging, and saved views.
- [ ] Document file splitting, generated/archive/cache files, configured source manifests, multiple writers, backups, undo, Git recovery, remote workspaces, authentication, proposals, release policy, schema/configuration compatibility, telemetry retention, transaction journals, and recovery.
- [ ] Expand lock/CAS documentation for cloud sync and network filesystems, stale evidence, manual cleanup, expected-revision examples, conflicts, proxies, embedded versus public APIs, configuration writes, and multi-target limitations.
- [ ] Package VS Code grammar/snippets as an installable extension and generate keys from model definitions.
- [ ] Add directive/encrypted-value/folding/file-icon support and syntax-highlight snapshots.
- [ ] Add a lossless parser/CST with spans before LSP edits.
- [ ] Implement LSP diagnostics, then symbols, completion, hover, definitions, safe code actions, and workspace rename only after multi-file CAS/recovery is proven.
- [ ] Replace compatibility monkey-patches with direct modules during planned splits, preserving public behavior and tests at each removal.

---

## Deferred Ideas

- [ ] Consider named or parallel timers only if one active timer remains restrictive in real use.
- [ ] Consider a local daemon only if notification watch, timer state, alarms, file reload, remote events, integration polling, recovery, and automation genuinely require one process.
- [ ] Consider PWA offline capture only after shared CAS, offline proposals, and explicit conflict review exist.
- [ ] Consider general remote/local synchronization only after Format 1.0 and an ID-based retained-base merge model are stable.
- [ ] Consider automatic Git pull/push/merge only after semantic history, remote proposals, credential delegation, recovery, and conflict review are stable.
- [ ] Consider a plugin SDK only after schemas/mutation contracts are stable and an out-of-tree official adapter validates the design.
- [ ] Consider a rebuildable search index only after large-file benchmarks show a practical bottleneck.
- [ ] Consider an additional human-edited configuration format only after the JSON schema, migration, comment-preservation requirements, canonicalization, and tooling costs are proven; do not support multiple partially equivalent formats prematurely.
- [ ] Do not add arbitrary Web JavaScript, direct life.txt rewrite plugins, unrestricted integration hooks, or unrestricted automation before sandbox and permission models exist.
- [ ] Do not attempt to replace email, calendar, chat, or file storage wholesale; integrate through references, summaries, proposals, and explicit approved actions.
