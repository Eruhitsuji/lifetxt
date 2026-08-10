# Review Standard

Reviews protect behavior, maintainability, security, and integration safety.

Every implementation pull request must receive a review from a separate party.
AI review is useful as first-pass review, but final approval for protected
branches should be owned by a human or responsible team.

## Review Types

| Type | Purpose |
| --- | --- |
| Requirements review | Confirm the issue is clear, scoped, and testable |
| Design review | Confirm architecture, contracts, dependencies, and risks |
| Code review | Confirm implementation correctness and maintainability |
| Test review | Confirm sufficient and meaningful verification |
| Security review | Confirm security-sensitive behavior is safe |
| Integration review | Confirm merge order, shared files, and compatibility |
| Release review | Confirm readiness, migration notes, and residual risks |
| Operations review | Confirm monitoring, logging, rollback, runbooks, and incident readiness |
| Audit review | Confirm traceability, approvals, retained evidence, and exception records |

## Review Stages

Use review repeatedly across the lifecycle:

- pre-implementation review: requirements, design, decomposition, scope, and
  assurance level
- implementation review: code, tests, security, compatibility, and evidence
- integration and merge review: latest commit, CI, shared files, conflicts,
  rollback, and merge authority
- release and operations review: release readiness, deployment, monitoring,
  incident response, deprecation, or retirement when applicable

## Pull Request Review Viewpoints

Reviewers must check:

- the change matches the issue and acceptance criteria
- no unrelated work is included
- write scope and forbidden scope are respected
- behavior is correct for normal, edge, and error cases
- public interfaces and data contracts remain compatible or are documented
- tests cover meaningful behavior rather than implementation details
- security-sensitive changes received appropriate scrutiny
- failure modes, logging, and observability are adequate
- documentation and migration notes are updated when needed
- commands and results are actually recorded
- review freshness is still valid for the current head commit

## Horizontal Review Scope Discipline

Acceptance criteria sometimes ask for a horizontal review: auditing adjacent
code or surfaces for the same defect class as the task's primary fix, then
fixing or recording what is found. This creates a real scope-boundary decision
for whatever the audit turns up:

- Fix a discovered issue in the same pull request only when it shares the same
  root cause as the primary fix and the fix is small and evidenced.
- Otherwise, file it as a new, evidence-backed follow-up issue. Do not expand
  the current pull request's scope to cover a materially separate concern or a
  fix that needs its own product or design decision, and do not silently drop
  an evidenced finding just because it falls outside the primary fix.

A reviewer checking "no unrelated work is included" should treat an
unscoped, unexplained expansion driven by a horizontal review the same as any
other scope creep — and should treat a horizontal-review acceptance criterion
with no resulting fix or follow-up issue as a sign the audit was not done.

## Review Ledger

Medium-risk or higher work should record a review ledger entry:

```yaml
reviewer: ""
review_type: code
target_commit: ""
result: pending
finding_count: 0
completed_at: ""
```

The review is stale when:

```text
reviewed_commit != current_head_commit
```

Stale review must be repeated or explicitly reconfirmed by an authorized
reviewer before merge.

## Review Severity

Use this severity model:

- P0: must fix before merge; security, data loss, severe regression, or broken release
- P1: must fix before merge; correctness, compatibility, or missing required test
- P2: should fix; maintainability, clarity, or moderate risk
- P3: optional; style, naming, small cleanup, or follow-up suggestion

## AI Review Rules

- An AI must not be the final approver of its own implementation.
- AI review should cite concrete files, behavior, and risk.
- AI review should prioritize bugs and missing tests over style.
- If the AI cannot verify a claim, it must state that clearly.
- Human reviewers own final judgment for protected branches.

## Review Completion Criteria

A review is complete when:

- blocking findings are resolved or explicitly accepted by the owner
- required checks have passed or unrun checks are documented
- new risks are captured in the PR or follow-up issues
- the reviewer has inspected the final diff after the latest push
