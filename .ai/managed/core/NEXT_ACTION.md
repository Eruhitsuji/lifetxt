# Next Action Standard

AI tools must be able to answer "what should I do next?" by inspecting the
project state, classifying the current phase, and proposing a small set of
safe next actions.

This standard applies when the user is unsure, asks for guidance, or provides
an ambiguous task.

## Required Behavior

When asked for the next action, the AI must not jump directly into
implementation. It must first inspect available project state and produce a
short recommendation.

Minimum inspection sources:

- current repository branch and working tree state
- `.ai/standard.lock.yml`
- `.ai/project/PROJECT.yml`
- `.ai/project/METHOD.yml`
- `.ai/project/GUIDANCE.yml`
- `.ai/project/COMMANDS.yml`
- `.ai/project/CONTEXT_INDEX.yml`
- `.ai/project/CAPABILITIES.yml`
- `.ai/project/TRACEABILITY.yml`
- `.ai/project/ASSURANCE.yml`
- `.ai/project/ROLES.yml`
- `.ai/project/MERGE_POLICY.yml`
- active GitHub Issue, pull request, or Project item when available
- local TODO markers and foundation issue templates when no issue exists
- recent CI or validation status when available

If a source cannot be accessed, the AI must say so and continue with the best
available local evidence.

## State Classification

Classify the project into one primary state:

| State | Meaning | Usual Next Action |
| --- | --- | --- |
| No repository | No project repository exists yet | Create project request or repository |
| New project initialization | Repository exists but standard is not active | Complete initialization PR and foundation issues |
| Existing project adoption | Existing repository is adding the standard | Finish adoption issue, adoption PR, and activation gate |
| Foundation setup | Standard exists but commands, owners, CI, or process are TODO | Resolve foundation issue with the highest risk |
| Backlog grooming | Work exists but is not Ready | refine issues and acceptance criteria |
| Active implementation | A Ready issue is assigned and branch/worktree exists | implement within write scope |
| Review | PR exists and implementation is complete | run review checklist and address findings |
| Integration | PR is approved or queued | confirm CI, conflicts, and merge readiness |
| Release preparation | Release candidate is being assembled | run release checklist and migration review |
| Standard update | `.ai/managed` or standard files are changing | use standard update flow |
| Blocked | Required decision, dependency, or access is missing | identify blocker owner and unblock action |

## Recommendation Format

The response must be concise and actionable:

```text
Current state:
Evidence:
Recommended next action:
Why:
Options:
Risks or blockers:
Suggested issue or PR update:
```

If the user appears non-technical or explicitly says they do not know what to
do, avoid tool-specific jargon in the first answer. Provide one recommended
action and at most two alternatives.

## Decision Rules

- Prefer finishing an open adoption, initialization, review, or release gate
  before starting new feature work.
- Prefer making an issue Ready over implementing an unclear request.
- Prefer creating a small investigation issue when the correct path is unknown.
- Prefer project-specific commands from `.ai/project/COMMANDS.yml` over guessed
  commands.
- Prefer existing process method in `.ai/project/METHOD.yml`; if absent, use
  the adaptive default in `DEVELOPMENT_METHODS.md`.
- Prefer context loading rules from `.ai/project/CONTEXT_INDEX.yml` so the AI
  loads only the needed standard sections.
- Escalate to a human decision when `AI_HUMAN_INTERACTION.md` or
  `AI_PERMISSIONS.md` marks the action as approval-required.
- Do not mark work Done before the Definition of Done is satisfied.

## Output Limits

For normal guidance, include only the next one to three actions. More detailed
plans should be written to a plan template or GitHub Issue.

## Required Follow-Up

When the recommendation identifies missing project facts, create or propose a
foundation issue rather than encoding guesses into common standards.
