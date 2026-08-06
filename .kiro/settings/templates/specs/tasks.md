# Implementation Plan

> **This file is working material, not the task source of truth.**
>
> In this repository, actionable work lives in GitHub Issues.
> `.ai/managed/core/TASK_MANAGEMENT.md` makes Issues the source of truth, and
> `.ai/managed/core/INDEX.md` lists "no implementation without a reviewable task source"
> in the non-overridable baseline. A checklist here would compete with both.
>
> Use this breakdown to decide what the issues should be, then file them. Each must meet
> `.ai/managed/core/DEFINITION_OF_READY.md` before implementation starts, and an issue that is
> `status:inbox` or `status:blocked` may not be started. Writing this file does not open that gate.
>
> Recording the resulting issue numbers beside each task here is encouraged; inventing progress
> here without them is not.
>
> See #101 for the decision behind this.

## Task Format Template

Use whichever pattern fits the work breakdown:

### Major task only
- [ ] {{NUMBER}}. {{TASK_DESCRIPTION}}{{PARALLEL_MARK}}
  - {{DETAIL_ITEM_1}} *(Include details only when needed. If the task stands alone, omit bullet items.)*
  - _Requirements: {{REQUIREMENT_IDS}}_

### Major + Sub-task structure
- [ ] {{MAJOR_NUMBER}}. {{MAJOR_TASK_SUMMARY}}
- [ ] {{MAJOR_NUMBER}}.{{SUB_NUMBER}} {{SUB_TASK_DESCRIPTION}}{{SUB_PARALLEL_MARK}}
  - {{DETAIL_ITEM_1}}
  - {{DETAIL_ITEM_2}}
  - {{OBSERVABLE_COMPLETION_ITEM}} *(At least one detail item should state the observable completion condition for this task.)*
  - _Requirements: {{REQUIREMENT_IDS}}_ *(IDs only; do not add descriptions or parentheses.)*
  - _Boundary: {{COMPONENT_NAMES}}_ *(Only for (P) tasks. Omit when scope is obvious.)*
  - _Depends: {{TASK_IDS}}_ *(Only for non-obvious cross-boundary dependencies. Most tasks omit this.)*

> **Parallel marker**: Append ` (P)` only to tasks that can be executed in parallel. Omit the marker when running in `--sequential` mode.
>
> **Optional test coverage**: When a sub-task is deferrable test work tied to acceptance criteria, mark the checkbox as `- [ ]*` and explain the referenced requirements in the detail bullets.
