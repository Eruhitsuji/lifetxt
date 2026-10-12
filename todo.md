# lifetxt Roadmap and Deferred Ideas

Last organized: 2026-10-12 (#1269 audit; #1270 documentation cleanup).

This file records development themes and conditional ideas, not an executable
checklist or an implementation-status ledger.

- [GitHub Issues](https://github.com/Eruhitsuji/lifetxt/issues) are authoritative
  for actionable scope, acceptance criteria, priority, and task status.
- [Project Rules](.ai/project/RULES.md) are authoritative for principles and
  product boundaries.
- [Capabilities](.ai/project/CAPABILITIES.yml), [docs](docs/), and code describe
  available behavior. An issue being closed does not prove an entire old
  roadmap proposal was implemented.
- The [archive and scope index](docs/roadmap/README.md) preserve all 191 former
  checkbox items and link to the item-by-item [#1269 audit](https://github.com/Eruhitsuji/lifetxt/issues/1269).
  Moving an item there does not complete, cancel, or approve it.

## Priority Model

The post-Stable model from [#471](https://github.com/Eruhitsuji/lifetxt/issues/471)
remains the baseline:

- **P0:** Correctness, data-integrity, security, compatibility, or clean-install
  regressions. The [release compatibility contract](docs/en/release-compatibility-policy.md)
  remains binding.
- **P1:** The selected product themes below and their necessary maintenance,
  permission/privacy, workspace, and contract dependencies. A theme is not
  blanket authorization to implement every archived proposal.
- **P2:** Optional integrations, editor tooling, packaging, maintainability,
  customization, and missing real-environment evidence. Promote concrete
  defects to P0; missing evidence alone does not reopen the completed Stable
  1.0 gate.
- **Deferred:** Conditional ideas requiring a demonstrated use case or a
  separate design decision.

[STABLE_RELEASE.yml](.ai/project/STABLE_RELEASE.yml) retains the historical
release classification and evidence. The old P1/P2 lists are not a second
current backlog; select executable work through Issues.

## Selected Product Themes

These continue the themes selected in #471. Their existing engines and surface
work must be reused; the historical issue links are context, not new tasks.

- **Daily workspace:** Unified Inbox, Command Center, Saved Views, and Area
  navigation. Context: [#472](https://github.com/Eruhitsuji/lifetxt/issues/472),
  [#483](https://github.com/Eruhitsuji/lifetxt/issues/483),
  [#484](https://github.com/Eruhitsuji/lifetxt/issues/484),
  [#627](https://github.com/Eruhitsuji/lifetxt/issues/627), and
  [#1033](https://github.com/Eruhitsuji/lifetxt/issues/1033).
  Select remaining daily-workflow gaps rather than recreating the engines.
- **Project and Portfolio:** Reuse the shared project/report operations when
  exposing a missing surface. Context:
  [#499](https://github.com/Eruhitsuji/lifetxt/issues/499),
  [#605](https://github.com/Eruhitsuji/lifetxt/issues/605), and
  [Project documentation](docs/en/ticket-projects.md).
- **Ticket workflow usability:** List, detail, activity, and lightweight board
  usability over existing workflow, history, planning, and time-entry contracts.
  Context: [#126](https://github.com/Eruhitsuji/lifetxt/issues/126),
  [#150](https://github.com/Eruhitsuji/lifetxt/issues/150), and
  [ticket documentation](docs/en/tickets.md).
  Read views, bulk mutations, and planning changes need separate bounded scopes.

## Supporting Topics and Existing Tracking

Use these entry points to find prior work before proposing a new issue.
They neither reproduce existing acceptance criteria nor claim that a broad
archived item is fully delivered.

| Topic | Existing scope / reference |
| --- | --- |
| Format, diagnostics, schema, and surface consistency | [#319](https://github.com/Eruhitsuji/lifetxt/issues/319), [#320](https://github.com/Eruhitsuji/lifetxt/issues/320), [#49](https://github.com/Eruhitsuji/lifetxt/issues/49), [#676](https://github.com/Eruhitsuji/lifetxt/issues/676), [#1247](https://github.com/Eruhitsuji/lifetxt/issues/1247); [Format compatibility](docs/en/format-compatibility-matrix.md) |
| Configuration and workspace safety | [#156](https://github.com/Eruhitsuji/lifetxt/issues/156), [#238](https://github.com/Eruhitsuji/lifetxt/issues/238), [#945](https://github.com/Eruhitsuji/lifetxt/issues/945); [configuration guide](docs/en/config.md) |
| Remote access, authorization, and client usability | [#984](https://github.com/Eruhitsuji/lifetxt/issues/984), [#985](https://github.com/Eruhitsuji/lifetxt/issues/985), [#1062](https://github.com/Eruhitsuji/lifetxt/issues/1062), [#1066](https://github.com/Eruhitsuji/lifetxt/issues/1066), [#1114](https://github.com/Eruhitsuji/lifetxt/issues/1114); [Remote guide](docs/en/remote.md) |
| Messaging, notification, provider and development-tool adapters | [#498](https://github.com/Eruhitsuji/lifetxt/issues/498), [#616](https://github.com/Eruhitsuji/lifetxt/issues/616), [#617](https://github.com/Eruhitsuji/lifetxt/issues/617); adapter proposals remain in the [scope index](docs/roadmap/README.md), not an approved generic SDK or integration service |
| Timer, recurrence, import/export, and workflow polish | [#310](https://github.com/Eruhitsuji/lifetxt/issues/310), [#311](https://github.com/Eruhitsuji/lifetxt/issues/311), [#656](https://github.com/Eruhitsuji/lifetxt/issues/656), [#1217](https://github.com/Eruhitsuji/lifetxt/issues/1217), [#1227](https://github.com/Eruhitsuji/lifetxt/issues/1227); [CLI workflows](docs/en/new-cli-workflows.md) |
| Web customization, CLI structure, distribution, docs, and editor tooling | [#1031](https://github.com/Eruhitsuji/lifetxt/issues/1031), [#1067](https://github.com/Eruhitsuji/lifetxt/issues/1067), [#1132](https://github.com/Eruhitsuji/lifetxt/issues/1132), [#568](https://github.com/Eruhitsuji/lifetxt/issues/568), [#570](https://github.com/Eruhitsuji/lifetxt/issues/570); [static VS Code extension](editors/vscode/lifetxt/README.md) |

### Real-Environment Evidence

Track deployment observation and strict revision rollout in
[#288–#292](https://github.com/Eruhitsuji/lifetxt/issues/288), remote attachment
restart/replay/bounds in [#297–#299](https://github.com/Eruhitsuji/lifetxt/issues/297),
and browser revision/recovery/UI evidence in
[#317](https://github.com/Eruhitsuji/lifetxt/issues/317) /
[#318](https://github.com/Eruhitsuji/lifetxt/issues/318). Follow each linked issue's
scope instead of maintaining the same scenario checklist here.

The filesystem, TUI, selector, and SMTP evidence issues
[#304](https://github.com/Eruhitsuji/lifetxt/issues/304),
[#312](https://github.com/Eruhitsuji/lifetxt/issues/312),
[#313](https://github.com/Eruhitsuji/lifetxt/issues/313),
[#314](https://github.com/Eruhitsuji/lifetxt/issues/314),
[#315](https://github.com/Eruhitsuji/lifetxt/issues/315), and
[#316](https://github.com/Eruhitsuji/lifetxt/issues/316) were closed as
`not_planned` at the audit point. That is not verification evidence; replan only
when needed, preserving their procedures and the current support boundary.
[External verification](docs/en/external-environment-verification.md) describes
the distinction between automated host checks and manual evidence.

## Deferred Ideas

These are unscheduled prompts, not implementation tasks or approved changes.
The existing [online server-authoritative Remote flow](docs/en/remote-client-writes.md)
does not implement a writable local replica, offline merge, or general
bidirectional synchronization. The existing [VM](docs/en/vm.md) is opt-in,
local, and CLI-only; the historical counter-machine design is not the current
user contract. Keep those boundaries when evaluating the ideas below.

- Consider named or parallel timers only if one active timer remains restrictive in real use.
- Consider a local daemon only if notification watch, timer state, alarms, file reload, remote events, integration polling, ticket watcher delivery, development-tool polling, recovery, and automation genuinely require one process.
- Consider PWA offline capture only after shared CAS, offline proposals, and explicit conflict review exist.
- Consider general remote/local synchronization only after Format 1.0 and an ID-based retained-base merge model are stable.
- Consider automatic Git pull/push/merge only after semantic history, remote proposals, credential delegation, recovery, and conflict review are stable.
- Consider a plugin SDK only after schemas/mutation contracts are stable and an out-of-tree official adapter validates the design.
- Consider a rebuildable search index only after ticket/event/global-search benchmarks show a practical bottleneck; the index must remain disposable and reconstructable from authoritative files.
- Consider an additional human-edited configuration format only after the JSON schema, migration, comment-preservation requirements, canonicalization, and tooling costs are proven; do not support multiple partially equivalent formats prematurely.
- Consider advanced Agile forecasting, cross-project dependency scheduling, resource leveling, and editable Gantt planning only after core ticket history and date completeness are measurable; do not present generated forecasts as authoritative plans.
- Consider wiki, forum, repository browser, document hosting, help desk/SLA, and full Redmine replacement features only when a concrete lifetxt-native use case cannot be met by references, attachments, notes, messages, and external integrations.
- Consider counter-machine tracing, checkpoints, resumption, alternate instructions, macros, compilation, visualization, Web/TUI/MCP/remote execution, or automation integration only after the CLI-only three-instruction runtime is implemented, benchmarked, security-reviewed, and demonstrably useful.
- A future non-local computation surface must define hard CPU/time/memory/output limits, cancellation, concurrency isolation, authentication, rate limiting, audit, and denial-of-service controls; never reuse `--max-steps 0` outside explicit local CLI execution.
