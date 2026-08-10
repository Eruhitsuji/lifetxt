# Task Decomposition Standard

Tasks must be small enough to understand, implement, verify, review, merge, and
revert independently.

## Unit of Work

```text
1 Issue = 1 purpose = 1 executor = 1 branch/worktree = 1 pull request
```

GitHub Issues are the only source of truth for actionable tasks.

## Size Rules

| Size | Rule |
| --- | --- |
| XS | preferred; isolated and reviewable in one small PR |
| S | preferred; one coherent behavioral or documentation change |
| M | allowed only with explicit reason why it cannot be split |
| L | cannot be Ready; must be decomposed |
| XL | cannot be Ready; must be decomposed into epics/tasks |

Investigation and implementation are separate by default. A task may include
the tests directly required to verify its implementation.

## Complexity Score

Record a complexity score before marking a task Ready.

| Dimension | 0 | 1 | 2 |
| --- | --- | --- | --- |
| scope breadth | one file or doc | one module | multiple modules |
| dependency impact | none | internal dependency | external/shared dependency |
| uncertainty | clear | some unknowns | unclear or research needed |
| test effort | existing check | new targeted tests | integration or manual matrix |
| operational risk | none | minor deploy/runtime effect | release, data, or incident impact |

Score result:

- 0-3: XS/S candidate
- 4-6: S/M candidate; split if possible
- 7 or more: not Ready until decomposed or assurance escalated

## Pre-Implementation Checks

Before implementation, inspect:

- existing capabilities and reusable modules
- related Issues and PRs
- public APIs and contracts
- shared libraries and dependency packages
- tests and evidence already available

Record whether the change is:

- new implementation
- extension of existing capability
- reuse of existing capability

## Horizontal Review Scope Discipline

When acceptance criteria require a horizontal review (auditing adjacent code or
surfaces for the same defect class as the task's primary fix), the audit's
findings do not automatically enter the current task's scope. Fix a discovered
issue in the same task only when it shares the same root cause and is small and
evidenced; otherwise file it as a separate, evidence-backed follow-up issue.
See `REVIEW.md`'s "Horizontal Review Scope Discipline" for the review-side rule.

## Algorithm Changes

For algorithm changes, record:

- expected data scale
- time and space complexity
- simpler alternatives considered
- performance requirement
- measurement method
- benchmark or regression evidence when applicable
