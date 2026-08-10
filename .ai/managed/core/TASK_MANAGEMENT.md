# Task Management Standard

GitHub Issues are the source of truth for actionable work. This does not
change based on the status backend below.

## Status Backend

The mechanism that owns issue lifecycle status is a separate, explicitly
configured choice from the task source of truth. Record it in
`.ai/project/PROJECT.yml`'s `governance.status_backend`:

| Backend | Semantics |
| --- | --- |
| `github-projects` (default) | GitHub Projects owns planning, prioritization, status, ownership, and cross-project visibility. This is the backward-compatible default for any project that does not set `status_backend`. |
| `github-labels` | `status:*` labels on the issue represent the 8 canonical status values below. Other planning fields (priority, ownership) may still live in the issue body or other labels. |
| `external-tracker` | Status lives outside GitHub. The issue body or a comment must reference the external ticket ID; GitHub Issues remain the task source of truth, but are not the live status view. |

Exactly one status backend is authoritative per project. Do not treat GitHub
Projects and labels as simultaneous, competing sources of truth for the same
project — if both appear to be in use, treat that as a project or execution
finding requiring the project owner to pick one (see `RUNTIME_EVIDENCE.md`'s
finding classes).

Existing downstream projects that do not set `governance.status_backend`
behave exactly as before this field existed: `github-projects`.

## Status Values

```text
Inbox
Ready
Planned
In Progress
In Review
Blocked
Done
Cancelled
```

## Standard Fields

- Priority: P0, P1, P2, P3
- Size: XS, S, M, L, XL
- Executor Type: Human, AI, Human + AI
- AI Tool: None, Codex, Claude Code, Kiro, Multiple
- Role: Planner, Architect, Implementer, Reviewer, Tester, Integrator
- Write Scope
- Forbidden Scope
- Base Commit
- Parent Issue
- Blocked By
- Parallel Group
- Conflict Risk
- Review Agent
- Integration Owner
- Development Method
- Current Phase
- Change Type
- Assurance Level
- Complexity Score
- Capability ID
- Requirement ID
- Traceability Record
- Reuse Decision
- Shared Files
- Integration Order

## Issue Requirements

Implementation issues must include:

- purpose
- background
- scope
- out of scope
- acceptance criteria
- technical constraints
- verification method
- ownership
- write scope
- dependencies
- task size and complexity score
- assurance level
- traceability to requirement or capability
- reuse or duplicate-feature check result
- shared files and integration owner when applicable

Do not start implementation while an issue is `Inbox` or `Blocked`.

## Task Size Rules

Tasks should be XS or S. M tasks require a written reason that the work cannot
be split further. L and XL tasks must not become `Ready`; decompose them into
smaller issues first.

Use `TASK_DECOMPOSITION.md` before marking work Ready.

## Traceability and Capability Checks

Before implementation, the task must record the chain it contributes to:

```text
Requirement -> Capability -> Epic -> Task -> PR -> Test/Evidence -> Release
```

Check `.ai/project/CAPABILITIES.yml`, related Issues, open PRs, existing APIs,
shared libraries, and dependencies before creating a new implementation. Record
whether the task reuses, extends, creates, replaces, or deprecates a capability.

Use `CAPABILITY_MANAGEMENT.md` and `TRACEABILITY.md`.

## Investigation and Implementation

Investigation and implementation are separate by default. Use an Investigation
issue when requirements, feasibility, algorithm choice, dependency impact, or
performance risk is unclear. Implementation tasks may include the tests directly
required to verify the change.

## Guidance Issues

Users may create guidance issues when they do not know what to do next.

Guidance issues are not implementation tasks. They should produce one of these
outputs:

- refined implementation issue
- investigation issue
- process decision issue
- foundation issue
- review or test plan
- recommendation to close as no action

Use `templates/github/ISSUE_TEMPLATE/guidance.yml` when the user needs help
choosing the next action.

## Process Decision Issues

Use process decision issues when a project, epic, or major task needs to select
or change its development method.

The decision must record:

- selected method
- quality gate model
- planning cadence
- release cadence
- reason for selection
- revisit condition

Use `templates/process-selection.md` for the decision body.

## Standard Adoption Issues

Existing project adoption must be tracked as a dedicated issue, not mixed into a
feature issue.

Adoption issues must include:

- target repository and default branch
- selected standard version and commit SHA
- adoption level: Passive, Guided, or Enforced
- selected profiles and enabled AI tools
- existing CI, issue templates, PR templates, CODEOWNERS, and AI instruction
  files
- files that must be preserved
- manual merge work for existing templates or instructions
- validation commands that can run now
- TODO items that require foundation follow-up issues

Adoption issue status should progress through:

```text
Inbox
  -> Ready
  -> In Progress
  -> In Review
  -> Done
```

Do not mark adoption `Done` until the adoption pull request is merged and
remaining foundation gaps are captured as separate issues.
