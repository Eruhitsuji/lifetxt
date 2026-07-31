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
