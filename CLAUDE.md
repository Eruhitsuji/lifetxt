# Claude Code Project Instructions

@AGENTS.md
@.ai/managed/core/INDEX.md
@.ai/managed/core/PROCESS.md
@.ai/managed/core/DEVELOPMENT_METHODS.md
@.ai/managed/core/NEXT_ACTION.md
@.ai/managed/core/AI_TOOL_COMPATIBILITY.md
@.ai/managed/core/ASSURANCE_LEVELS.md
@.ai/managed/core/TASK_DECOMPOSITION.md
@.ai/managed/core/TRACEABILITY.md
@.ai/managed/core/CAPABILITY_MANAGEMENT.md
@.ai/managed/core/REVIEW.md
@.ai/managed/core/MERGE_GOVERNANCE.md
@.ai/managed/core/AI_HUMAN_INTERACTION.md
@.ai/project/PROJECT.yml
@.ai/project/METHOD.yml
@.ai/project/GUIDANCE.yml
@.ai/project/CONTEXT_INDEX.yml
@.ai/project/CAPABILITIES.yml
@.ai/project/TRACEABILITY.yml
@.ai/project/ASSURANCE.yml
@.ai/project/ROLES.yml
@.ai/project/RULES.md
@.ai/project/COMMANDS.yml

## Claude Code Specific Rules

- Use Plan Mode before modifying multiple modules or public interfaces.
- Ask before destructive operations, dependency-wide migrations, or standard
  updates.
- Prefer repository commands over manually assembled commands.
- Use `.ai/project/CONTEXT_INDEX.yml` for progressive context loading before
  pulling in large standard sections.
- Escalate human-only decisions using `.ai/managed/core/AI_HUMAN_INTERACTION.md`.
- Do not commit or push unless explicitly instructed.
