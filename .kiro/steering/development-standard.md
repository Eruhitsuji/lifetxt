# Development Standard

Follow:

- `.ai/managed/core/INDEX.md`
- `.ai/managed/core/PROCESS.md`
- `.ai/managed/core/DEVELOPMENT_METHODS.md`
- `.ai/managed/core/NEXT_ACTION.md`
- `.ai/managed/core/AI_TOOL_COMPATIBILITY.md`
- `.ai/managed/core/ASSURANCE_LEVELS.md`
- `.ai/managed/core/TASK_DECOMPOSITION.md`
- `.ai/managed/core/TRACEABILITY.md`
- `.ai/managed/core/CAPABILITY_MANAGEMENT.md`
- `.ai/managed/core/REVIEW.md`
- `.ai/managed/core/MERGE_GOVERNANCE.md`
- `.ai/managed/core/AI_HUMAN_INTERACTION.md`
- `.ai/managed/core/TASK_MANAGEMENT.md`
- `.ai/managed/core/MULTI_AGENT_DEVELOPMENT.md`
- `.ai/project/METHOD.yml`
- `.ai/project/GUIDANCE.yml`
- `.ai/project/CONTEXT_INDEX.yml`
- `.ai/project/CAPABILITIES.yml`
- `.ai/project/TRACEABILITY.yml`
- `.ai/project/ASSURANCE.yml`
- `.ai/project/ROLES.yml`
- `.ai/project/RULES.md`

Do not edit `.ai/managed/**` during normal development.

When the user asks what to do next, inspect project state and recommend the
next one to three actions using `.ai/managed/core/NEXT_ACTION.md`.

Use `.ai/project/CONTEXT_INDEX.yml` for progressive context loading. Do not
load or restate the whole standard when a narrower rule set is enough.

## Specifications

The rule lives in `.ai/project/RULES.md` under **Specifications**. Read it there;
it is not restated here, so the two cannot drift apart. In short:

- cc-sdd writes to `.kiro/specs/<feature>/`. That is working material.
- `.ai/project/changes/<change-id>/` is the source of truth for non-trivial and
  High or Regulated work, distilled from it. The change package wins.
- `.ai/project/changes/README.md` sets the threshold for needing a package at all.
- A spec's task breakdown decides what issues to file; it is not itself a task
  list. `tasks.md` is working material.
- A specification does not authorise implementation. The gate is an issue meeting
  `.ai/managed/core/DEFINITION_OF_READY.md`, not `status:inbox` or
  `status:blocked`.

Copy `.ai/project/changes/_template/` to start a change package.
