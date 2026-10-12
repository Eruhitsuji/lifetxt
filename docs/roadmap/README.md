# Roadmap Archive and Retained Scope

The active [roadmap](../../todo.md) contains themes, existing tracking entry
points, and Deferred Ideas. Actionable tasks live in
[GitHub Issues](https://github.com/Eruhitsuji/lifetxt/issues), per
[#51](https://github.com/Eruhitsuji/lifetxt/issues/51) and
[#471](https://github.com/Eruhitsuji/lifetxt/issues/471).

## 2026-10-12 Snapshot

[archive-2026-10-12.md](archive-2026-10-12.md) is a **historical, byte-for-byte
copy**, not current product documentation or an executable backlog.

- Source main commit: `6707e2740c9f09d0449660d661fbde239c19cbc9`.
- Source Git blob: `11d4246285deea806e191a8b17e7d1274c2bd0e5`.
- Original: [todo.md at the source commit](https://github.com/Eruhitsuji/lifetxt/blob/6707e2740c9f09d0449660d661fbde239c19cbc9/todo.md).
- 191 checkbox items, including the two original checked items.
- Audit and item-by-item recommendations:
  [#1269](https://github.com/Eruhitsuji/lifetxt/issues/1269).
- Documentation cleanup:
  [#1270](https://github.com/Eruhitsuji/lifetxt/issues/1270).

The original date, priority labels, status claims, command syntax, and relative
links are intentionally unchanged in the snapshot. Relative links there refer
to the **original repository-root location**; use the fixed-commit original
above to navigate them. In particular, the old counter-machine design and
`run` proposals must not replace the current [VM contract](../en/vm.md).

## Scope Index

`item_id` is the 1-based checkbox order in the snapshot. Line ranges refer to
that snapshot and the fixed-commit original; each includes any continuation
lines through the last checkbox in the section. Every original item remains
available for future refinement.

The destination column identifies a theme or existing tracking context, not a
claim that the referenced issue implements the entire archived section.
Uncovered requirements remain in the snapshot and the #1269 audit. Read the
linked issue's scope and closure reason before reusing or proposing work.

| Historical section | item_id range | Original lines | Current destination / existing tracking context |
| --- | --- | --- | --- |
| P1: Remote Safe Mode follow-up | 001–007 | 95–101 | Remote support; [#1062](https://github.com/Eruhitsuji/lifetxt/issues/1062)/[#1066](https://github.com/Eruhitsuji/lifetxt/issues/1066)/[#1114](https://github.com/Eruhitsuji/lifetxt/issues/1114); production-session choices remain unselected |
| P1: Format 1.0 and Data Semantics | 008–015 | 105–112 | Format/diagnostics/schema; [#319](https://github.com/Eruhitsuji/lifetxt/issues/319)/[#320](https://github.com/Eruhitsuji/lifetxt/issues/320)/[#1247](https://github.com/Eruhitsuji/lifetxt/issues/1247); future compatibility domains remain conditional |
| P1: Shared Surface Contracts | 016–024 | 118–126 | Shared contracts; [#676](https://github.com/Eruhitsuji/lifetxt/issues/676)/[#1132](https://github.com/Eruhitsuji/lifetxt/issues/1132); surface gaps require operation-specific scope |
| P1: Configuration and Workspace Foundation | 025–027 | 132–134 | Configuration/workspaces; [#156](https://github.com/Eruhitsuji/lifetxt/issues/156)/[#238](https://github.com/Eruhitsuji/lifetxt/issues/238)/[#945](https://github.com/Eruhitsuji/lifetxt/issues/945); unverified parity remains in [#1269](https://github.com/Eruhitsuji/lifetxt/issues/1269) |
| P1: Project and Portfolio Management | 028–032 | 140–144 | Project/Portfolio theme; [#499](https://github.com/Eruhitsuji/lifetxt/issues/499)/[#605](https://github.com/Eruhitsuji/lifetxt/issues/605); record registry/semantic gaps remain in [#1269](https://github.com/Eruhitsuji/lifetxt/issues/1269) |
| P1: Development Ticket Management Core | 033–043 | 150–160 | Ticket usability theme; [#150](https://github.com/Eruhitsuji/lifetxt/issues/150)/[#605](https://github.com/Eruhitsuji/lifetxt/issues/605); bulk/report metadata proposals remain retained |
| P1: Ticket Workflow, History, Planning, and Time Tracking | 044–050 | 166–172 | Ticket usability theme; workflow/history/planning/time-entry residual scope remains in [#1269](https://github.com/Eruhitsuji/lifetxt/issues/1269) |
| P1: Remote Safe Mode and Remote Workspace Access | 051–062 | 178–189 | Remote support; [#984](https://github.com/Eruhitsuji/lifetxt/issues/984)/[#985](https://github.com/Eruhitsuji/lifetxt/issues/985)/[#1062](https://github.com/Eruhitsuji/lifetxt/issues/1062)/[#1114](https://github.com/Eruhitsuji/lifetxt/issues/1114); deployment/audit/transport residual scope remains retained |
| P1: Messaging, Groups, Watchers, and Delivery State | 063–069 | 195–201 | Messaging/notification support; [#498](https://github.com/Eruhitsuji/lifetxt/issues/498)/[#616](https://github.com/Eruhitsuji/lifetxt/issues/616)/[#617](https://github.com/Eruhitsuji/lifetxt/issues/617); server groups/delivery UI residual scope remains retained |
| P1: Integration Adapter Foundation | 070–076 | 207–213 | Provider adapter proposals; requirements/identity/side effects require a separate decision |
| P1: Development Toolchain Ticket Integration | 077–084 | 219–226 | Development-tool adapter proposals; Git historical reads do not implement provider mutations |
| P1: Life Hub and Information Unification | 085–094 | 232–241 | Daily workspace theme; [#472](https://github.com/Eruhitsuji/lifetxt/issues/472)/[#483](https://github.com/Eruhitsuji/lifetxt/issues/483)/[#484](https://github.com/Eruhitsuji/lifetxt/issues/484)/[#627](https://github.com/Eruhitsuji/lifetxt/issues/627)/[#1033](https://github.com/Eruhitsuji/lifetxt/issues/1033); automation/integration proposals remain conditional |
| P1: Timer and Notification Foundation | 095–100 | 247–252 | Timer/notification support; single-timer/OS delegation decisions and residual state contracts remain retained |
| P1: Workflow Follow-ups | 101–115 | 258–272 | Workflow support; [#656](https://github.com/Eruhitsuji/lifetxt/issues/656)/[#1217](https://github.com/Eruhitsuji/lifetxt/issues/1217)/[#1227](https://github.com/Eruhitsuji/lifetxt/issues/1227); invoice/ICS/RDATE/re-expansion/cache residual scope remains retained |
| P2: Ticket UI and Agile Planning | 116–124 | 278–286 | Ticket usability theme; dedicated board/Gantt/bulk/Agile views remain separately scoped proposals |
| P2: Deterministic Minimal Computation Runtime | 125–125 | 292–295 | Historical VM design; current CLI-only VM is documented in docs/en/vm.md ([#560](https://github.com/Eruhitsuji/lifetxt/issues/560)) |
| P2: Web UI Customization | 126–134 | 301–309 | Web/docs/editor support; [#1031](https://github.com/Eruhitsuji/lifetxt/issues/1031)/[#1067](https://github.com/Eruhitsuji/lifetxt/issues/1067); generic settings/presets/card ordering remain separate proposals |
| P2: CLI, Packaging, and Distribution | 135–149 | 315–329 | CLI/distribution support; [#1132](https://github.com/Eruhitsuji/lifetxt/issues/1132)/[#568](https://github.com/Eruhitsuji/lifetxt/issues/568)/[#570](https://github.com/Eruhitsuji/lifetxt/issues/570); conditional cache/Python/CI/doctor proposals remain retained |
| P2: Configuration, Ticketing, Integration, and Runtime Documentation | 150–156 | 335–341 | Documentation support; [#156](https://github.com/Eruhitsuji/lifetxt/issues/156)/[#265](https://github.com/Eruhitsuji/lifetxt/issues/265); future integration/runtime examples are not available-feature claims |
| P2: Documentation, Editor, and LSP | 157–168 | 347–358 | Documentation/editor support; static VS Code extension exists; dynamic LSP/CST proposals remain retained |
| P2: Reliability and Real-Environment Verification (Post-Stable, Non-Blocking) | 169–179 | 374–384 | Existing deployment/attachment/browser tracking: [#288](https://github.com/Eruhitsuji/lifetxt/issues/288)–292/[#297](https://github.com/Eruhitsuji/lifetxt/issues/297)–299/[#317](https://github.com/Eruhitsuji/lifetxt/issues/317)–318; not_planned evidence is not completed |
| Deferred Ideas | 180–191 | 390–401 | 12 conditional Deferred Ideas retained in active todo.md; no adoption or cancellation implied |

## Pending Evidence and Decisions

The audit left these **38 items unclear**, rather than concluding they were
implemented or absent:

`005, 015, 024, 031, 038, 041, 046, 063, 066, 070, 071, 073, 075, 076, 078, 079, 080, 081, 092, 095, 098, 103, 104, 106, 109, 111, 114, 116, 119, 121, 129, 132, 135, 137, 139, 143, 145, 160`

Removing their duplicate active checkbox does not resolve them. Before promoting
one into executable work, read its full original scope and audit row, identify
the actual missing slice, search existing Issues, and use or extend existing
tracking where applicable. Design prompts remain unapproved until a decision is
recorded in the authoritative Rules/Docs or a dedicated issue.

The 12 Deferred Ideas (180–191) remain in active todo.md as plain conditional
bullets. Other unselected proposals are retained by the scope index above; this
cleanup does not adopt, reject, or reprioritize them.

The open revision-rollout (#288–292), attachment (#297–299), and browser
(#317–318) tracking is preserved. At the audit point, #304/#312/#313/#314/#315/#316
were closed as `not_planned`, which must not be presented as real-environment
verification. Use [the verification procedure](../en/external-environment-verification.md)
when choosing to replan those scenarios.

## Earlier History

[The 2026-07-20 roadmap archive](../roadmap-archive-2026-07-20.md) remains an
earlier historical snapshot. Current behavior belongs in user Docs and
Capabilities; neither archive is a competing product specification.

## Documentation Traceability

- Requirement: `req-roadmap-issue-deduplication`.
- Existing capability context: `cap-life-philosophy-documentation`; no runtime capability changes.
- Investigation: #1269; implementation task: #1270.
- Pull request: pending creation.
- Evidence: source blob/byte equality, 191-item continuous index, 12 unchanged
  Deferred idea texts, 38 retained unclear IDs, live relative-link checks, and
  `git diff --check`.
- Rollback: revert the documentation PR; no user-data migration.
