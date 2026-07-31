# Assurance Levels Standard

Development method, change type, and assurance level are separate decisions.
The method controls workflow cadence. The change type describes what is being
changed. The assurance level controls the amount of evidence and review needed.

## Change Type

Use one primary change type:

- Feature
- Bug
- Investigation
- Refactoring
- Security
- Performance
- Migration
- Operations
- Incident
- Deprecation
- Standard Update

## Assurance Levels

| Level | Use When | Required Artifacts | Review | Human Approval | Test or Verification | Evidence | Merge Conditions |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Quick | low-risk documentation, small internal change, investigation note | issue or PR summary | one review when code changes | not required unless protected area | targeted check or documented reason | command/result or reviewed note | CI required if configured; no blocking findings |
| Standard | normal feature, bug, test, or maintenance work | task contract, PR template, verification | independent review | required for protected branch approval | project commands plus targeted tests | PR evidence and review result | Definition of Done and CI pass |
| High | public API, data model, security-sensitive, migration, shared contract, high-risk performance work | change package, traceability, test plan, review ledger | implementation and integration review; security/performance as applicable | required from accountable owner or domain owner | unit/integration/compatibility/migration checks | change package, CI, review ledger | merge authority approval and rollback plan |
| Regulated | audit-heavy, compliance, destructive, incident, release, retirement, or high blast-radius change | change package, approval record, release/operations evidence | multi-stage review, audit review, final authority review | required from approved human team | documented verification matrix and retained evidence | traceability, approvals, test evidence, release/ops record | explicit merge/release authority approval; no stale review |

## Escalation Rules

Raise assurance level when any condition applies:

- security impact
- data migration, deletion, retention, or privacy impact
- public API or compatibility impact
- operational, deployment, rollback, or incident impact
- overlapping write scope or shared files
- unclear requirement or unresolved design decision
- algorithmic complexity or performance risk
- external service, cost, or dependency addition
- regulatory, audit, or contractual requirement

The AI may recommend an assurance level, but final acceptance of High or
Regulated risk is owned by a human authority.

## Method Interaction

All development methods can use any assurance level. Do not force regulated
process on every change, and do not use a lightweight method to avoid required
evidence.
