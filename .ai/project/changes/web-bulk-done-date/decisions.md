# Decisions

- Owner approved #1479 A-E; the current request authorizes implementation.
- Child #1480 records DoR, write scope, responsibilities and acceptance. S,
  complexity 5 after investigating source/revision behavior (1/1/0/2/1).
  UI and mutation/recovery form one coherent acceptance boundary. Standard:
  existing APIs and model, no authentication or security-contract changes.
- Reuse existing bulk selection/modal/mutation/timezone contracts; separately
  trace cap-web-bulk-done-date rather than attributing bulk support to #861.
- Implementer/Integrator Codex; accountable owner and merge authority Eruhitsuji.
  Feature branch from origin/main; final PR base main. No managed edits or deps.
- Phase: requirements/design/decomposition -> implementation -> developer
  verification -> independent review -> integration. Adaptive-default/W-model.
- Review: identity/data integrity, concurrency, partial success/uncertain outcomes,
  Undo, timezone, accessibility and compatibility. Coding: scoped module,
  canonical content equality, no unrelated refactor. Security: escape record
  titles, avoid raw server error disclosure, require explicit per-write CAS.
- Independent latest-head review, CI and human merge required. No release/deploy.
