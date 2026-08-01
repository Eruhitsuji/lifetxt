# Process Standard

This standard defines the method-independent lifecycle that every project must
be able to map to its selected development method.

If a project has not selected a method, use the default from
`DEVELOPMENT_METHODS.md`: small iterations, Kanban flow, and W-model quality
gates.

## Lifecycle

```text
Discovery
  -> Product Requirements
  -> System / Software Requirements
  -> Architecture and Design
  -> Task Decomposition
  -> Implementation
  -> Developer Verification
  -> Independent Review
  -> Integration Verification
  -> Release Approval
  -> Deployment
  -> Operations and Monitoring
  -> Incident and Maintenance
  -> Evaluation and Improvement
  -> Deprecation
  -> Retirement
```

The process may be executed in short iterations, but the required outputs and
gates must not be skipped for implementation work.

## Phase Standards

| Phase | Required Work | Output | Gate |
| --- | --- | --- | --- |
| Discovery | Clarify problem, users, constraints, and expected value | Issue, brief, or product note | Problem and owner are clear |
| Product Requirements | Define user needs, scope, out of scope, acceptance criteria, risks | Ready issue or feature spec | Definition of Ready satisfied |
| System / Software Requirements | Define system constraints, interfaces, data, operations, and compatibility rules | requirements record or contract note | requirements are testable and traceable |
| Architecture and Design | Decide architecture, interfaces, data, migration, security approach | Design note, ADR, or change package | Impact and contracts are reviewable |
| Task Decomposition | Split work by dependency and write scope | Sub-issues and task contracts | Parallel work is safe and tasks are XS/S or justified M |
| Implementation | Change code/docs only within scope | Branch/worktree and commits | Acceptance criteria addressed |
| Developer Verification | Run local checks and targeted tests | Commands and results | No false pass claims |
| Independent Review | Review behavior, design, tests, security, compatibility | PR review, review report, or review ledger | Separate party reviewed the latest commit |
| Integration Verification | Run CI and integration checks against merge target | CI results and conflict notes | Required checks pass and merge risks are understood |
| Release Approval | Confirm readiness, changelog, migration notes | Release PR/tag or deployment record | Release Authority approves |
| Deployment | Deploy or install the change | Deployment record | Smoke check and rollback path are ready |
| Operations and Monitoring | Confirm telemetry, runbooks, alerts, SLOs, backup/restore | Operational evidence | Operations Owner accepts readiness |
| Incident and Maintenance | Triage, mitigate, repair, and verify operational work | Incident or maintenance issue | Incident Commander or owner accepts status |
| Evaluation and Improvement | Capture process, product, or standard improvements | Follow-up issues or standard-change issue | Improvements are tracked |
| Deprecation | Plan removal or replacement | Deprecation plan | Compatibility and migration are approved |
| Retirement | Remove capability or retire system | Retirement record | Users, data, and operations are safe |

## Method Mapping

Projects may use agile, Kanban, Scrum, Waterfall, V-model, W-model, XP, Lean,
Shape Up, Spiral, prototype, maintenance, release-train, or regulated workflows.

Each selected method must still map work to the lifecycle above. The method may
change cadence, artifacts, and approval depth, but it must not remove
traceability, review, verification, or ownership.

See `DEVELOPMENT_METHODS.md`.

See `SPECIFICATION_LIFECYCLE.md` for the complete owner, evidence, gate, and
next-condition matrix.

## Assurance Mapping

Every change must state its change type and assurance level. The selected
development method controls cadence, but the assurance level controls evidence,
review depth, and human approvals. Use `ASSURANCE_LEVELS.md`.

## W-Model Mapping

| Development Side | Verification Side |
| --- | --- |
| Requirements | Acceptance tests and user-visible behavior checks |
| Architecture/design | Architecture review and integration tests |
| Interface/contracts | Contract tests and compatibility checks |
| Implementation | Unit tests and static checks |
| Integration | End-to-end, migration, and release checks |

## Iteration Rules

- Keep iterations small enough that issues can be reviewed independently.
- Do not begin implementation before the issue meets Definition of Ready.
- Do not merge before Definition of Done is satisfied.
- Record newly discovered work as follow-up issues.
- Update common standards when repeated project-specific rules become reusable.

## AI Use by Phase

| Phase | AI Can Do | Human Must Own |
| --- | --- | --- |
| Discovery | Summarize context, draft questions, compare options | Problem framing and priority |
| Requirements | Draft acceptance criteria and split scope | Final requirements decision |
| Design | Propose architecture and risks | Architecture approval |
| Implementation | Implement scoped changes and tests | Scope control and final responsibility |
| Review | First-pass review and test gap detection | Final approval |
| Release | Draft notes and checklists | Release decision |

## Next Action Support

When the user asks what to do next, follow `NEXT_ACTION.md`. The AI should
classify the current state, cite the evidence it inspected, and recommend the
next one to three actions instead of asking the user to understand the whole
process first.
