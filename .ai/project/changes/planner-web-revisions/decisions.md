# Decisions

- 2026-10-09 JST: The user requested #1162 implementation through PR creation.
  Scope is the issue's existing client revision contract, without new server API,
  data-model, configuration or authorization decisions.
- Bug / High, complexity 7 (1+1+1+2+2), M: one coherent fix and the regression
  matrix for all current mutation callers. Splitting would leave the same defect
  present on other supported Planner actions.
- Reuse cap-web-mobile-planner and server revision/CAS; implement locally in the
  Planner API helper to bind actions to their read snapshots and leave main Web
  behavior unchanged. No new dependencies.
- Correct preliminary audit: expected_source_revision is currently a compatibility
  request member, not enforced by capture_item. The generic header is authoritative.
- Human implementation/integration reviews and final High risk/merge acceptance
  remain pending; AI self-review does not replace independent approval.
- Production verification/reset is not performed. Preserve the failed observation,
  verify deployed mutations, then follow #290 for an authorized fresh 14-day
  observation before reassessing #289/#290/#291.
