# lifetxt TODO / Roadmap

Last updated: 2026-07-25 (updated x110)

This is the active roadmap after the 2026-07-24 process-boundary, directory/package attachment, transaction-administration, subprocess-recovery, clock-skew, and schema-contract batch; the 2026-07-25 configuration/workspace, Project/Portfolio, shared-query, messaging-group, person/group-overview, and development-ticket planning updates; and the current deterministic minimal-computation proposal. Completed sub-items are removed rather than repeated. Remaining P0 work is still real deployment and real-platform evidence, delegated mutation boundaries, remote attachment parity, protected recovery evidence, complete timezone fixtures, and real terminal/browser/SMTP verification. The development-ticket and counter-machine tracks describe planned work and do not claim those features are already implemented. The previous detailed roadmap remains preserved in [`docs/roadmap-archive-2026-07-20.md`](docs/roadmap-archive-2026-07-20.md).

Priority guide:

- `P0`: Release-blocking data safety, correctness, migration, and real-environment verification.
- `P1`: Core format, configuration/workspace behavior, project and development-ticket management, remote access, integrations, messaging, timer/notification behavior, and daily workflow work.
- `P2`: Product customization, deterministic optional tools, advanced planning views, packaging, documentation, editor support, and maintainability.
- `Deferred`: Ideas that should wait for a proven use case or a stable foundation.

Design principles:

- Fail loudly when behavior is ambiguous or data may be lost.
- Keep life.txt authoritative and use standard, inspectable interchange formats.
- Route authoritative writes through validated, atomic, conflict-aware mutation contracts.
- Treat compensated multi-target commits as an explicit recovery contract, not as portable filesystem-level atomicity.
- Keep CLI, TUI, Web API, Web UI, MCP, editor support, schemas, configuration, and documentation semantically aligned.
- Make effective configuration deterministic, explainable, schema-valid, and safe to migrate before allowing it to control remote access, integrations, or automatic writes.
- Prefer lifetxt as an action and information hub over copying every external system's full data into life.txt.
- Represent development tickets with normal Task records plus documented `record:ticket` metadata until evidence justifies a new item type; preserve generic project `record:issue` records for non-ticket project issues and risks.
- Keep the current ticket state readable on the ticket record while storing comments and audit-relevant changes as append-only `record:ticket_event` records committed through the same transaction as the state change.
- Treat Git, GitHub, GitLab, CI/CD, chat, and email as external authorities when appropriate; store stable references, normalized summaries, proposals, and audited actions instead of silently mirroring complete histories.
- Keep optional computation isolated from ordinary task semantics. Counter-machine records use normal Note items plus `machine:` details; they must not masquerade as Status (`S`) or Reminder (`R`) records.
- Keep the minimal computation runtime deterministic and side-effect free: no clock, randomness, network, subprocesses, parallelism, implicit file discovery, or authoritative file mutation.
- Treat an unlimited computation step count as an explicit local CLI opt-in, never as the default and never as a capability automatically exposed to Web, MCP, TUI, remote, or automation clients.
- Treat remote access, integrations, development-tool automation, and general automation as proposal-producing clients unless a validated write contract permits direct mutation.
- Treat a successful release gate as evidence, not as permission to ignore known baseline debt.
- Preserve old public CLI behavior when introducing richer reports; use explicit modes or unambiguous new flags.

Feature-track order after the current P0 foundation:

1. Complete the real observe-to-required revision rollout and migrate plugin-provided or intentionally delegated mutation boundaries.
2. Validate attachment and compound work-session recovery under real power-loss, filesystem, Windows, security-software, cloud-sync, removable-media, and network-filesystem failures.
3. Complete encrypted/access-controlled evidence storage, policy migration for future released versions, and the operator escalation/restoration runbook.
4. Expand deterministic timezone fixtures across every public surface and enforce the implemented server-authoritative clock-skew policy on future remote writes.
5. Stabilize Format 1.0, canonical serialization, multi-file semantics, diagnostics, and contract schemas.
6. Finish versioned-configuration migration, CAS-aware configuration writes, named-workspace hardening, TUI workspace selection, and source-manifest edge cases while preserving top-level `paths` / `write_file` compatibility.
7. Finish project archive, validation, cross-surface Project Hub exposure, permissions, and privacy on top of the implemented Project/Portfolio read foundation.
8. Add Development Ticket Management Core: ticket metadata, tracker/status mapping, typed fields, query/list/show/new/edit/assign/relation operations, validation, and project aggregation.
9. Add Ticket Workflow, History, Planning, and Time Tracking: role-aware transitions, append-only events/comments, watchers, versions, sprints, backlog, time entries, and compound mutation/recovery behavior.
10. Add single-user Remote Safe Mode and read-only remote CLI/TUI access using the same workspace, project, and ticket contracts.
11. Enable conflict-aware remote writes only for operations whose capability entries report complete revision, permission, event-history, and recovery enforcement.
12. Add Unified Inbox, daily command-center views, saved views, and life-area navigation, including ticket attention and review queues.
13. Add managed groups, multi-recipient messaging, ticket watchers, and per-recipient delivery state.
14. Add the provider-neutral integration contract, then implement Slack and email proposal/output adapters before Teams and Discord.
15. Add development-toolchain ticket integration for Git references, GitHub/GitLab issues and pull requests, CI/CD events, release notes, and explicitly approved closure proposals.
16. Add TUI/Web ticket detail, activity, saved-query, backlog, sprint, roadmap, and Kanban views after shared ticket operations and workflow contracts are stable.
17. Add the CLI-only deterministic minimal computation runtime after Format 1.0, canonical detail handling, stable diagnostics, and the unified parser/command registry are ready.
18. Add Web UI configuration, advanced Agile/Gantt views, and richer provider automation only after proposal, audit, permission, credential, performance, and recovery boundaries are stable.

---

## P0: Release Safety and Correctness

- [ ] Execute and finish the strict Web revision migration in a real deployment. Preserve the metrics store across upgrades and deployment moves, document the observation period, migrate every supported browser/API client to revision discovery and `If-Match`, require a complete zero-use window, switch supported deployments to `required`, and remove temporary fallback behavior only after evidence review. Cover container replacement, read-only old paths, permission changes, restored backups, older-server rollback, attachment clients, work-session clients, future ticket clients, and recovery-required startup.
- [ ] Finish the remaining delegated-process mutation boundaries. Require the existing proposal/diff/revision/apply contract for plugin-provided mutations, commands that intentionally hand control to another process, editor extensions that replace or rename files, future integration adapters, and future development-tool ticket adapters. Add one-winner/one-conflict and process-restart fixtures before advertising any boundary as writable.
- [ ] Finish directory/package attachment parity and remote recovery contracts. Expose directory/package/reconcile/open operations through Web and MCP only after capability rows identify exact targets, item/attachment/metadata revisions, schemas, MIME/platform restrictions, restart behavior, and recovery actions. Add duplicate transaction-ID, partial-failure, restart, compensation, divergence, and large-streaming protocol tests; keep remote writes and ticket attachment automation disabled until those contracts pass.
- [ ] Prove durable recovery under real power, storage, and platform failures. Expand subprocess drills to every fsync/replace/delete/verification/compensation boundary, repeated recovery, corrupted/missing artifacts, disk-full, quota, permission and ownership changes, signals, Windows replace, antivirus/indexer interference, cloud-synchronized directories, removable media, and network filesystems. Include future ticket-plus-event, ticket-plus-time-entry, bulk-ticket, and sprint-planning compound operations.
- [ ] Complete protected evidence storage and future policy/journal migration operations. Add encrypted or OS-access-controlled evidence profiles, key rotation and recovery, migration functions for every future released policy/journal version, explicit refusal matrices, archive encryption/rotation, authorization-backed operator identity, restore-from-backup commands, and a complete escalation/runbook drill.
- [ ] Complete deterministic timezone fixtures and enforce clock-skew policy on writable remote protocols. Run one shared fixture table through CLI, TUI, Web, MCP, notifications, saved views, import/export, projects, tickets, ticket events, time entries, sprint/version boundaries, integrations, and work sessions; require acceptable skew before future remote writes.
- [ ] Verify the dependency-free TUI in real WSL, Windows Terminal, macOS, and Linux terminals. Cover colors, glyph fallback, narrow layouts, editor suspension, auto-reload, revision refresh, timezone display, semantic conflicts, multi-file transactions, attachments, compound work sessions, stale-lock guidance, and interrupted-operation recovery. Add ticket view verification when implemented.
- [ ] Verify `fzf` and `peco` actions end to end on Windows PowerShell and Unix-like shells, including stale revisions, multi-selection, preview quoting, edit suspension, delete confirmation, Unicode paths, spaces, symlinks, mixed-source selections, all-or-none multi-file commits, and shell exit propagation.
- [ ] Verify SMTP delivery with safe test accounts. Cover STARTTLS, authentication failure, app-password guidance, multiple recipients, retry/backoff, watcher state, quiet hours, redacted logging, provider limits, and future ticket-watcher notifications.
- [ ] Add browser-engine smoke tests for the Web UI. Cover revision migration, persistent metrics, ETag alteration, attachment/work-session operations, mobile layout, keyboard navigation, command execution, undo, dialogs, charts, timeline edges, timezone display, stale revisions, accessibility focus, interrupted recovery, and browser restart. Add ticket list/detail/activity/bulk/board coverage when those surfaces exist.

---

## P1: Format 1.0 and Data Semantics

- [ ] Complete Format 1.0 enforcement beyond the mutation guard. Add parser-level version metadata, explicit migration and downgrade inspection, consistent unsupported-version errors, newly-created-workspace policy, and a compatibility matrix covering format, canonical, schema, capability, revision, configuration, transaction, ticket, and future counter-machine result versions.
- [ ] Complete `LIFETXT_CANON_V1`. Define quoting, escaping, detail ordering, repeated-key ordering, continuation representation, comments, directive placement, blank-line behavior, Unicode edge cases, and idempotent serializer output. Machine scalar details must preserve source information so duplicate `id`, `machine`, `value`, `op`, `target`, `next`, `zero`, or `nonzero` values can be rejected rather than silently collapsed.
- [ ] Enforce documented multi-file semantics. Make input/glob order deterministic and visible; enforce workspace-wide IDs during every write; define cross-file parent/link/archive/generated-file rules; preserve source metadata; and require explicit write targets. Counter-machine `run` remains single-explicit-file in its first release and must not inherit workspace paths or load referenced files implicitly.
- [ ] Expand the schema bundle where real contracts exist. Add remaining JSONL, endpoint-specific Web, MCP, query, ticket, integration, development-tool, notification, attachment-package, migration, and import/export schemas. For the computation track, publish at least `counter-machine-result-v1.schema.json` and a stable diagnostic/result envelope; validate actual CLI JSON responses rather than only hand-written examples.
- [ ] Extend stable diagnostics after F101-F134 for generated-file ownership, archive policy, package/MIME hazards, mixed configuration, schema/capability mismatch, policy migration, clock skew, ticket workflow/history/planning errors, and parser-native spans. Counter-machine runtime diagnostics use a documented `C001`-`C012` namespace without replacing format diagnostics; define source line/column, machine item ID, detail key, severity, message, and hint where available.
- [ ] Route legacy `check --format json` to the stable diagnostic shape and publish compatibility guarantees. Decide whether machine validation is opt-in through `run` only or also available through a non-executing `check --machine` mode; do not make ordinary files fail merely because unknown custom `machine:` values exist outside an explicitly requested machine validation context.
- [ ] Add conservative `check --fix` only after canonical behavior is final. Ticket workflow/history and counter-machine repairs remain report-only; missing labels, ambiguous duplicate scalar details, negative counters, and unknown instructions must never be auto-created or guessed.
- [ ] Extend the golden-corpus policy when another released format/corpus version exists. Add machine records as custom-key preservation cases without making the counter-machine model part of the core grammar.

---

## P1: Shared Surface Contracts

- [ ] Expand the registry-backed operation layer into surface-neutral implementations for existing query, item, messaging, proposal, workspace, project, ticket, integration, remote, timer, attachment, archive, and undo operations. Registry rows must identify revisions, targets, schemas, permissions, generated events, external effects, recovery, and supported surfaces.
- [ ] Keep the minimal computation operation outside authoritative mutation registries in its first release. Register it as a pure CLI read/execute/render operation with one explicit input file and optional independent output file; report `writes_authoritative_data: false`, `network: false`, and `external_process: false`.
- [ ] Extend public-contract tests through CLI/TUI and reuse shared fixture semantics for revisions, validation, read-only mode, proposals, compound failures, compensation, interrupted journals, and ticket operations. Add a separate pure-runtime matrix for deterministic machine execution without implying Web/MCP parity.
- [ ] Complete registry-derived command/capability drift checks. The `run` command may appear in generated CLI help and documentation, but Web, MCP, TUI, remote, and automation capabilities must report it unavailable until separate resource and denial-of-service policies are designed.
- [ ] Continue reducing direct-write baselines. Future machine execution must never add a direct-write allowance: stdout is default, `-o` writes only a distinct result file atomically, and the input file is never modified.
- [ ] Move all dispatcher commands into the unified parser registry during CLI module splitting. Define `run FILE --entry ID [--max-steps N] [--format life|json] [-o FILE]` in the same source used by help, completion, docs, and exit-code contracts.
- [ ] Preserve structured proposal metadata and shared query language work for normal lifetxt operations. Do not expose counter-machine state as actionable tasks, proposals, saved-view mutations, or automation triggers in the initial runtime.
- [ ] Extend `doctor --workspace-safety` for current workspace, transaction, attachment, remote, ticket, integration, and privacy checks. Counter-machine execution needs no workspace discovery; optionally report only whether the pure runtime is installed and its default step limit, without scanning files.
- [ ] Decide which report commands need Web/MCP equivalents from demonstrated use. The minimal computation runtime explicitly fails this symmetry test for its initial release and remains CLI-only.

---

## P1: Configuration and Workspace Foundation

The implemented configuration/workspace foundation remains the authority for normal lifetxt file discovery. The minimal runtime intentionally does not use automatic workspace sources in its first release.

- [ ] Complete configuration migration metadata, CAS-aware configuration writes, symlink-loop/size safeguards, TUI workspace selection, per-workspace timezone/notification context, and remote/integration/software-project examples.
- [ ] Add an optional `runtime.counter_machine.default_max_steps` setting only if repeated use demonstrates value; the CLI default remains explicit and documented even without configuration. Configuration must never permit network, subprocess, implicit include, or authoritative-input mutation.
- [ ] If a runtime setting is added, publish type/default/range/provenance through the configuration registry and `config explain`; reject negative limits and distinguish `0` as an explicit unlimited value.
- [ ] Do not let `paths`, `write_file`, profiles, generated sources, or workspace globs alter `lifetxt run FILE`. The positional file is the complete program source, and `-o` is the only output destination.

---

## P1: Project and Portfolio Management

- [ ] Add project archive through the workspace transaction/recovery contract and define how tickets, events, time entries, versions, sprints, attachments, and external references move or remain linked.
- [ ] Expose Project/Portfolio operations through TUI, Web, saved views, remote read-only clients, and remaining shared surfaces without reimplementing aggregation.
- [ ] Complete validation for milestone/risk/issue/decision/meeting records and preserve the explicit boundary between generic `record:issue` and development `record:ticket`.
- [ ] Add project permissions/privacy for remote workspaces, teams, integrations, exports, AI context, notifications, tickets, events, and time entries.
- [ ] Keep counter-machine Note records excluded from project progress, workload, health, command-center attention, invoice, and ticket metrics unless a user explicitly queries their custom details.

---

## P1: Development Ticket Management Core

- [ ] Publish `ticket-v1.schema.json`, canonical ticket field semantics, item-status mapping, a versioned `ticketing` configuration section, typed custom fields, and deterministic diagnostics.
- [ ] Add shared `ticket new|list|show|edit|assign|close|reopen`, `ticket link|unlink`, ticket-aware query/sorting/grouping/saved views, previewed all-or-none bulk operations, and transparent Project/Portfolio ticket metrics.
- [ ] Add local fixtures and English/Japanese documentation for bug, feature, task, support, security, hierarchy, duplicate/dependency, privacy/custom fields, cross-file/archive, malformed tickets, and explicit Task/issue-to-ticket migration.
- [ ] Ensure generic Note records used for counter machines cannot be interpreted as tickets merely because they contain fields such as `id`, `target`, or `next`.

---

## P1: Ticket Workflow, History, Planning, and Time Tracking

- [ ] Publish workflow, append-only event, version, sprint, and time-entry schemas.
- [ ] Add role-aware `ticket transition`, comments, watcher changes, assignment/field changes, history integrity, notification policy, versions, sprint/backlog planning, time logging/timesheets, timer integration, deterministic planning metrics, and complete recovery tests.
- [ ] Keep machine execution entirely separate from ticket workflow guards, audit events, timers, time entries, and ticket automation.

---

## P1: Remote Safe Mode and Remote Workspace Access

- [ ] Add secure single-user Remote Safe Mode, session/CSRF/throttling protections, capability/version negotiation, `WorkspaceBackend`, remote profiles, read-only remote operations, and read-only TUI browsing.
- [ ] Add conflict-aware remote writes only after required revision, permission, event-generation, and recovery contracts are complete.
- [ ] Add diagnostics and tests for TLS, authentication/authorization, clock skew, schema/configuration/workflow mismatch, proxy ETag changes, older clients/servers, interruption, and recovery.
- [ ] Do not expose `lifetxt run` remotely in the initial implementation. A future remote computation service would require CPU/time/memory quotas, cancellation, concurrency isolation, authentication, audit, and denial-of-service analysis and is therefore Deferred.

---

## P1: Messaging, Groups, Watchers, and Delivery State

- [ ] Extend implemented local groups, recipient resolution, message composition, and derived delivery state to server-managed groups, TUI/Web/API composition, per-recipient writes/snooze, Web delivery progress, permissions, provider backends, and complete tests.
- [ ] Keep machine execution from sending messages or notifications. Step-limit warnings and runtime diagnostics go only to the invoking CLI's stdout/stderr or selected result file.

---

## P1: Integration Adapter Foundation

- [ ] Publish normalized integration events and provider capabilities; define `IntegrationAdapter`; add idempotency, cursors, retry/rate limits, dead-letter inspection, secret-safe credentials, mapping rules, Slack/email first, then Discord/Teams, reference-first attachments, administration commands, and provider mocks.
- [ ] Do not permit integration payloads to invoke the counter-machine runtime. Imported files containing `machine:` details remain inert data unless a local user explicitly runs the CLI command.

---

## P1: Development Toolchain Ticket Integration

- [ ] Define stable Git/repository/branch/commit/issue/PR/review/build/deployment/release references; add proposal-first Git scanning, GitHub/GitLab adapters, normalized CI/CD events, explainable transition guards, release outputs, capability reporting, and failure/recovery tests.
- [ ] Keep machine examples and generated outputs out of automatic ticket closure, CI action execution, and integration hooks unless a future explicit safe use case is separately designed.

---

## P1: Life Hub and Information Unification

- [ ] Add Unified Inbox proposal review/batch apply, extend command center to TUI/Web and ticket/build/release attention, finish `area:` filtering/inheritance, extend person/group overview, backlinks, search, privacy, and normalized provider/development-tool consumption.
- [ ] Add declarative automation only after proposal, audit, permission, conflict, recovery, ticket-history, integration-idempotency, and credential boundaries are stable.
- [ ] Exclude `machine:counter` and `machine:instruction` Notes from default captures, attention queues, agenda, person/group work, and search facets unless explicitly requested by query.

---

## P1: Timer and Notification Foundation

- [ ] Complete timer scope/state/capability decisions, alarm/Pomodoro evaluation, notification backend abstraction, quiet hours, acknowledgement, snooze, retry, restart-safe state, ticket watcher selection, and provider limits.
- [ ] Do not use timers as machine step limits and do not let machine execution write `elapsed:` or timer state. Runtime step accounting is an in-memory deterministic counter only.

---

## P1: Workflow Follow-ups

- [ ] Complete shared deterministic-clock coverage for current commands and ticket/integration behavior.
- [ ] Add `next --explain`, invoice policy, standup team mode, ICS fixtures/conflict behavior, todo.txt/GitHub Markdown idempotency, attachment opening/hash cache, recurrence preview and remaining RRULE decisions, rolling-window expansion, and archive/undo attachment-path rules.
- [ ] Counter-machine tests must prove independence from clock/timezone context by running with different host timezones and injected clocks and producing byte-identical JSON/life output.

---

## P2: Ticket UI and Agile Planning

- [ ] Add TUI/Web Ticket List, Ticket Detail, activity timeline, workflow-safe Kanban, backlog/sprint/version/release views, optional calendar/Gantt, data-coverage-aware metrics, Web presets, and browser/TUI accessibility/performance/recovery tests.
- [ ] Every UI mutation must call shared ticket operations; no ticket UI should gain access to the computation runtime in this track.

---

## P2: Deterministic Minimal Computation Runtime

This optional track adds a universal but deliberately tiny computation model without changing life.txt grammar or ordinary item behavior. It is lower priority than core personal-information, project, ticket, remote, integration, and safety work. The first implementation is local, dependency-free, CLI-only, read-only with respect to the input, deterministic, and limited to `inc`, `decjz`, and `halt`.

### Record model

- [ ] Represent every counter and instruction as a normal Note item using `[N] N`, not Status (`S`) or Reminder (`R`), so presence, reminder, agenda, notification, and command-center behavior is not triggered accidentally.
- [ ] Define counters as `[N] N TITLE id:ID machine:counter value:INTEGER`. Require exactly one `id`, `machine`, and `value`; require ASCII decimal digits only; reject signs, decimal/exponent/hex/underscore forms; require a non-negative value; and use arbitrary-precision integers with no language-level upper bound.
- [ ] Define instructions as `[N] N TITLE id:ID machine:instruction op:OPERATION ...`. Treat instruction IDs as labels and require exactly one scalar value for every operation field.
- [ ] Define `inc` as `op:inc target:COUNTER_ID next:NEXT_ID`; atomically increment the target and move the program counter to `next` within one in-memory step.
- [ ] Define `decjz` as `op:decjz target:COUNTER_ID zero:ZERO_ID nonzero:NONZERO_ID`; when the counter is zero, preserve its value and jump to `zero`; otherwise decrement once and jump to `nonzero` within one in-memory step.
- [ ] Define `halt` as `op:halt` with no target/jump details. Count execution of `halt` as one step, set `last_instruction` to the halt ID, set `next_instruction` to `null`, and return `halted: true`.
- [ ] Use one input-wide ID namespace for counters, instructions, and other items visible to machine references. Reject duplicate IDs rather than allowing a counter and instruction to share the same label. Do not infer missing IDs, labels, counters, or jumps.
- [ ] Preserve input definition order for counter output in both life and JSON formats. Use maps for lookup internally without changing deterministic serialization order.

### Validation and diagnostics

- [ ] Implement `lifetxt/counter_machine_validator.py` to collect candidate records and validate the complete program before any instruction executes.
- [ ] Define `C001` missing entry instruction, `C002` invalid counter value, `C003` unknown operation, `C004` missing required detail, `C005` missing target counter, `C006` missing target instruction, `C007` maximum step count exceeded, `C008` duplicate ID, `C009` repeated scalar detail, `C010` output resolves to the input file, `C011` invalid `machine:` record composition, and `C012` negative step limit.
- [ ] Return all deterministic pre-execution validation diagnostics that can be reported safely, ordered by source line, diagnostic code, and item ID. Do not execute partially valid programs and do not auto-correct references.
- [ ] Reject operation-inapplicable scalar details in strict machine validation (for example `target` on `halt` or `zero` on `inc`) so typographical mistakes do not become silently ignored data.
- [ ] Keep ordinary parsing permissive: unknown custom keys remain valid life.txt syntax, and machine-specific errors appear only when the machine validator/run command is explicitly invoked.

### Runtime semantics

- [ ] Implement `lifetxt/counter_machine.py` with immutable program definitions, mutable in-memory counter state, current instruction ID, step count, and a structured result object. Keep parsing/validation separate from execution.
- [ ] Define step-limit behavior precisely: before each instruction, if `max_steps > 0` and `steps >= max_steps`, do not execute the next instruction; return `C007`, `halted: false`, the current counter state, the last executed instruction or `null`, and the pending `next_instruction`. After a permitted instruction executes, increment `steps` exactly once.
- [ ] Set the CLI default to `--max-steps 100000`. Interpret `--max-steps 0` as an explicit unlimited local execution mode, emit one fixed stderr warning, and document that a non-halting program may never return. Reject negative values as `C012`.
- [ ] Guarantee determinism for the same input bytes, entry ID, limit, and output format. Prohibit time access, randomness, network access, subprocesses, environment-dependent branching, implicit file reads, writes during execution, and parallel instruction execution.
- [ ] Treat state mutation and program-counter movement as indivisible within the single-threaded interpreter loop. Runtime exceptions must not expose a half-applied step in the returned structured state.
- [ ] Keep resource claims accurate: arbitrary-precision integers and unlimited steps are language-model properties, but actual executions remain bounded by available memory, process lifetime, and an optional step safety limit.

### CLI and output

- [ ] Add `lifetxt run FILE --entry ID --max-steps N --format life|json -o FILE` through the unified CLI parser registry. Limit the initial command to exactly these options plus normal global help/version behavior; do not add expressions, variables, functions, stdin programs, includes, tracing, or mutation flags.
- [ ] Read exactly one explicit UTF-8 life.txt file through the normal parser. Do not load config `paths`, workspace manifests, neighboring files, links, attachments, or generated sources.
- [ ] Default output to stdout. For `-o`, resolve input and output paths (including symlinks/aliases) and return `C010` if they identify the same file. Write a distinct output file atomically; do not create transaction journals for the read-only input.
- [ ] Define JSON output as a stable object containing `halted`, nullable `code`, `steps`, `entry`, nullable `last_instruction`, nullable `next_instruction`, and ordered `counters`. On `C007`, include the complete intermediate state and return process exit code `1`.
- [ ] Define life output as canonical `[N] N ... machine:counter value:...` counter records in input order. For complete structured error/interruption metadata, require JSON; stderr may contain a fixed human-readable diagnostic. Decide whether optional comment metadata is useful only after real usage.
- [ ] Use process exit code `0` only for normal `halt`, `1` for machine validation/runtime failure including `C007`, and `2` for CLI argument parsing failure. Keep process exit codes separate from `C001`-`C012`.
- [ ] Document that the first release never changes the source program and cannot resume from an output state automatically. Resumption, checkpoints, traces, and in-place counter updates remain out of scope.

### Tests, schemas, and documentation

- [ ] Add the two-counter transfer example and assert `a=0`, `b=3`, `halted=true`, and `steps=8` when `halt` counts as an instruction. Include zero-input behavior and entry-at-halt behavior.
- [ ] Test large arbitrary-precision counters, self-loops, non-halting programs under a finite limit, explicit unlimited-mode parsing without running an endless CI case, step-limit off-by-one boundaries, missing/duplicate references, repeated scalar details, unknown operations, invalid decimal syntax, and output/input path aliases.
- [ ] Test deterministic byte output across repeated runs, supported Python versions, LF/CRLF input, input item order, unrelated ordinary Notes, different host clocks/timezones/locales, and hash-randomization seeds.
- [ ] Publish a JSON result schema and representative success, validation-error, and `C007` instances. Add release-manifest validation and generated CLI/docs drift checks.
- [ ] Add English/Japanese `counter-machine.md` documentation covering the three operations, exact record forms, validation codes, step counting, output, safety model, Turing-completeness assumptions, limitations, and complete examples.
- [ ] Add dependency-free unit tests for `counter_machine.py`, `counter_machine_validator.py`, and the CLI command. Keep Web, TUI, MCP, remote, integration, and automation execution tests absent because those surfaces are intentionally unsupported.

### Explicit non-goals

- [ ] Do not add arithmetic expressions, comparison operators beyond zero-test, strings, general `if`, loops as syntax, functions, subroutines, stacks, arrays, standard input/output instructions, file access, external commands, GUI/TUI execution, MCP execution, remote execution, or in-place source updates.
- [ ] Do not add debugger, trace, optimizer, compiler, macro, include, or alternate machine instructions until the three-operation model is implemented, documented, and proven useful.
- [ ] Do not market Turing completeness as operational safety or practical performance. State that universality assumes at least two unbounded non-negative counters and unbounded execution steps, while real runs remain finite-resource processes.

---

## P2: Web UI Customization

- [ ] Add schema-validated Web settings backed by the shared configuration registry, configurable navigation, allow-listed saved-view/dashboard cards, drag/drop card layout, Items/Ticket columns, quick-add defaults, responsive previews, versioned import/export, presets, CSS restrictions, and browser tests.
- [ ] Keep arbitrary JavaScript and third-party in-page plugins disabled/deferred.
- [ ] Do not add a browser counter-machine runner as part of customization.

---

## P2: CLI, Packaging, and Distribution

- [ ] Finish the unified parser registry, completion caching, Web command-palette arguments, interactive completion, `cli.py` and `tui_app.py` splits, supported-Python decisions, multi-platform required CI, `doctor --ci`, release automation, contribution/security templates, and wheel-first distribution.
- [ ] Place counter-machine command handling in dedicated modules backed by shared model/validator/runtime code; do not grow `cli.py` with an interpreter loop.
- [ ] Keep the runtime dependency-free and include it in clean-wheel and no-Web smoke tests.
- [ ] Add release smoke cases for `run --help`, the two-counter sample, JSON schema validation, finite-limit failure, and installed-console behavior outside the repository.
- [ ] Consider zipapp/single-file distribution only after normal wheel behavior is stable.

---

## P2: Configuration, Ticketing, Integration, and Runtime Documentation

- [ ] Complete task-oriented config guides and generated English/Japanese references with every configuration, ticketing, workflow, integration, and optional runtime setting.
- [ ] Add dedicated workspace, integration, migration, ticket, ticket-workflow, ticket-planning, development-integration, and counter-machine guides.
- [ ] Generate reference tables and `config explain` data from authoritative registries; fail CI on missing schema/docs/migration/security coverage or invalid examples.
- [ ] Add runnable example datasets for personal/work/project/team, remote/integrations, ticket workflows, versions/sprints/events/time, Git/CI proposals, and a minimal counter-machine program. Keep machine examples isolated from normal persona data unless the use case explicitly demonstrates custom-record coexistence.

---

## P2: Documentation, Editor, and LSP

- [ ] Define authoritative documents for grammar, CLI, Web/API, schemas, configuration, ticketing/workflows, integrations, recovery, optional runtime behavior, and examples.
- [ ] Add English/Japanese parity checks and worked examples/captures for existing surfaces and planned ticket/runtime behavior.
- [ ] Document file splitting, generated/archive/cache files, source manifests, ticket/event/time-entry files, multiple writers, backups, undo, Git recovery, remote workspaces, proposals, compatibility, journals, and recovery.
- [ ] Expand lock/CAS documentation, package VS Code grammar/snippets, add directive/encrypted-value/folding/file-icon support, implement a lossless CST before LSP edits, then diagnostics/symbols/completion/hover/definitions/safe actions/rename.
- [ ] Add `machine:counter` and `machine:instruction` snippets only after the runtime syntax is final. Editor support may validate/read/navigate labels but must not execute programs.
- [ ] Replace compatibility monkey-patches with direct modules during planned splits while preserving behavior and tests.

---

## Deferred Ideas

- [ ] Consider named or parallel timers only if one active timer remains restrictive in real use.
- [ ] Consider a local daemon only if notification watch, timers, file reload, remote events, integration polling, ticket watcher delivery, development-tool polling, recovery, and automation genuinely require one process.
- [ ] Consider PWA offline capture only after shared CAS, offline proposals, and explicit conflict review exist.
- [ ] Consider general remote/local synchronization only after Format 1.0 and an ID-based retained-base merge model are stable.
- [ ] Consider automatic Git pull/push/merge only after semantic history, remote proposals, credential delegation, recovery, and conflict review are stable.
- [ ] Consider a plugin SDK only after schemas/mutation contracts are stable and an out-of-tree official adapter validates the design.
- [ ] Consider a rebuildable search index only after ticket/event/global-search benchmarks show a practical bottleneck; keep it disposable.
- [ ] Consider another human-edited configuration format only after JSON schema, migration, comment preservation, canonicalization, and tooling costs are proven.
- [ ] Consider advanced Agile forecasting, cross-project dependency scheduling, resource leveling, and editable Gantt only after ticket history/date completeness is measurable.
- [ ] Consider wiki, forum, repository browser, document hosting, help desk/SLA, and full Redmine replacement features only for concrete lifetxt-native use cases.
- [ ] Consider counter-machine tracing, checkpoints, resumption, alternate instructions, macros, compilation, visualization, Web/TUI/MCP/remote execution, or automation integration only after the CLI-only three-instruction runtime is implemented, benchmarked, security-reviewed, and demonstrably useful.
- [ ] A future non-local computation surface must define hard CPU/time/memory/output limits, cancellation, concurrency isolation, authentication, rate limiting, audit, and denial-of-service controls; never reuse `--max-steps 0` outside explicit local CLI execution.
- [ ] Do not automatically close tickets from commit/merge/CI/deployment events before proposal, permission, idempotency, stale-evidence, and compound-history contracts are proven.
- [ ] Do not add arbitrary Web JavaScript, direct life.txt rewrite plugins, unrestricted integration/development-tool hooks, or unrestricted automation before sandbox and permission models exist.
- [ ] Do not attempt to replace email, calendar, chat, Git hosting, CI/CD, issue trackers, or file storage wholesale; integrate through references, summaries, proposals, and explicit approved actions.
