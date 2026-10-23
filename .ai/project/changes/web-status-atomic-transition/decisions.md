# Decisions

- 2026-10-23: Owner approved High assurance, Ready and the proposed design in
  the task conversation; the sanitized approval and task contract are recorded
  on #1378 before implementation. Bug / S / complexity 6, adaptive-default,
  continuous Kanban and W-model. One branch `fix/1378-atomic-status` from
  origin/main, one PR into main.
- Extend `cap-web-beginner-first-ux` Status authoring with
  `req-web-status-atomic-transition`; no duplicate capability/model/API.
- Preserve the current revision middleware, including legacy fallback. Do not
  add headers or require new revisions beyond the existing policy.
- Reuse the authoritative transform writer with creation enabled. Keep all
  runtime edits inside the Status handler, with focused API regression tests.
- The required High change package is supporting evidence, not an expansion
  into UI/shared-runtime work. Shared-file integration belongs to Eruhitsuji.
- Independent implementation and integration reviews belong to Eruhitsuji and
  remain pending until performed on the final head. Implementer self-review is
  recorded separately and is not independent approval.
