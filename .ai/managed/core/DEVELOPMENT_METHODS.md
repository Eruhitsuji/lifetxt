# Development Methods Standard

Projects may use different development methods, but they must keep the common
quality baseline: traceable tasks, explicit scope, independent review, verified
changes, and recorded decisions.

Development method is only one axis. Each task must also declare its change
type and assurance level. Use `ASSURANCE_LEVELS.md` so low-risk work stays
lightweight and high-risk work receives enough review and evidence.

## Default Method

If a project has not selected a method, use the adaptive default:

```text
small iterations + Kanban flow + W-model quality gates
```

This means work moves continuously through Issues and PRs, while each phase has
a matching review or verification viewpoint.

## Method Selection

The selected method belongs in `.ai/project/METHOD.yml`.

Choose one primary method for project planning and optionally one quality gate
model for verification.

Example:

```yaml
schema_version: 1

primary_method: kanban
quality_gate_model: w-model
planning_cadence: weekly
release_cadence: on-demand
```

Large epics may override the project method in the issue or feature spec when
the override is explicit and reviewable.

## Supported Methods

| Method | Use When | Minimum Controls |
| --- | --- | --- |
| Kanban | Work arrives continuously or priorities change often | WIP limits, explicit status, Definition of Ready/Done |
| Scrum | Work can be planned in fixed iterations | sprint goal, selected backlog, review, retrospective |
| Scrumban | Iterations are useful but incoming work is continuous | WIP limits plus lightweight iteration planning |
| Waterfall | Scope is stable and sequential approval is required | signed requirements, design gate, test plan, release gate |
| V-model | Verification must map directly to each specification level | requirements tests, design reviews, integration tests |
| W-model | AI/human review should happen throughout development | review and test viewpoint for each phase |
| XP | Rapid change with strong engineering discipline | TDD where practical, refactoring discipline, continuous integration |
| Lean | Reducing waste and lead time is the main goal | value hypothesis, small batches, measurable outcomes |
| Dual-track agile | Discovery and delivery proceed in parallel | discovery issues, delivery issues, decision checkpoints |
| Shape Up | Work is shaped before a fixed delivery cycle | pitch, appetite, circuit breaker, betting decision |
| Spiral | Technical or product risk dominates | risk list, prototype or investigation per cycle |
| Prototype or PoC | Feasibility is unknown | timebox, learning goals, throwaway or hardening decision |
| Trunk-based development | Team integrates very frequently | small PRs, CI, feature flags, revert plan |
| Release train | Releases happen on a fixed schedule | release branch policy, stabilization window, release checklist |
| Maintenance flow | Main work is bugs, dependencies, and operations | triage queue, severity rules, regression tests |
| Regulated or audit-heavy flow | Evidence and approvals must be retained | approval records, traceability, test evidence, change log |

The list is intentionally extensible. Add project-specific methods under
`.ai/project/RULES.md` or propose reusable additions to this standard.

## Method-Independent Baseline

No method may bypass these requirements:

- actionable work is tracked in GitHub Issues
- implementation scope and acceptance criteria are explicit
- parallel work has write scope and dependency controls
- security-sensitive changes receive explicit review
- behavior changes have relevant tests or a recorded exception
- pull requests include verification results
- final approval is not performed solely by the implementing AI
- release decisions are owned by a human maintainer

## Method Selection Questions

When a user does not know which method to choose, ask or infer:

- Is the goal discovery, delivery, maintenance, or release?
- Is scope stable or still changing?
- Is risk mainly product, technical, security, schedule, or compliance?
- How many humans and AI tools will work in parallel?
- Is a fixed iteration or continuous flow more natural?
- What evidence is required before merge or release?

If the answers are unknown, recommend the adaptive default.

## Issue-Level Method Rules

Each significant issue should state:

- lifecycle phase
- selected method or inherited project method
- required review viewpoints
- required test viewpoints
- expected evidence

Use `templates/process-selection.md` for method decisions and
`templates/implementation-plan.md` for issue-level execution plans.
