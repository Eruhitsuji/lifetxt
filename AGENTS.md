# Project Agent Instructions

Read and follow:

1. `.ai/managed/core/INDEX.md`
2. `.ai/managed/core/PROCESS.md`
3. `.ai/managed/core/DEVELOPMENT_METHODS.md`
4. `.ai/managed/core/NEXT_ACTION.md`
5. `.ai/managed/core/AI_TOOL_COMPATIBILITY.md`
6. `.ai/managed/core/ASSURANCE_LEVELS.md`
7. `.ai/managed/core/TASK_DECOMPOSITION.md`
8. `.ai/managed/core/TRACEABILITY.md`
9. `.ai/managed/core/CAPABILITY_MANAGEMENT.md`
10. `.ai/managed/core/REVIEW.md`
11. `.ai/managed/core/MERGE_GOVERNANCE.md`
12. `.ai/managed/core/AI_HUMAN_INTERACTION.md`
13. relevant `.ai/managed/profiles/**/INDEX.md`
14. `.ai/project/PROJECT.yml`
15. `.ai/project/METHOD.yml`
16. `.ai/project/GUIDANCE.yml`
17. `.ai/project/CONTEXT_INDEX.yml`
18. `.ai/project/CAPABILITIES.yml`
19. `.ai/project/TRACEABILITY.yml`
20. `.ai/project/ASSURANCE.yml`
21. `.ai/project/ROLES.yml`
22. `.ai/project/RULES.md`
23. `.ai/project/COMMANDS.yml`
24. the assigned GitHub Issue and task contract

## Ownership

- `.ai/managed/**` is generated from the common standard.
- Do not edit `.ai/managed/**` during normal feature development.
- Project-specific rules belong under `.ai/project/**`.
- Standard updates require a dedicated standard-update task.

## Task Execution

Do not start implementation unless:

- a GitHub Issue exists
- acceptance criteria are defined
- the task is not blocked
- write scope is defined
- task size is XS/S or M with split justification
- assurance level and required human approvals are known
- traceability and capability impact are recorded
- a dedicated branch or worktree is used

Use repository commands from `.ai/project/COMMANDS.yml`.
Use `.ai/project/CONTEXT_INDEX.yml` to load only task-relevant standard sections.

For every implementation task, identify applicable process phase, review
viewpoints, test viewpoints, coding viewpoints, and security viewpoints before
changing files.

When the user asks what to do next, follow `.ai/managed/core/NEXT_ACTION.md`:
inspect project state, classify the current phase, and recommend the next one
to three actions.

When a decision requires human authority, use the Decision Request format from
`.ai/managed/core/AI_HUMAN_INTERACTION.md`.
