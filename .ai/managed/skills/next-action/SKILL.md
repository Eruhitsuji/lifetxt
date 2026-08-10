---
name: next-action
description: Answer "what should I do next?" by inspecting project state, classifying the current phase, and recommending one to three safe next actions.
---

# Next Action Skill

Packages `standards/core/NEXT_ACTION.md`'s required behavior directly so it is
followed the same way every time, instead of being re-derived from prose.

## When to use this skill

The user is unsure what to do, asks for guidance, or gives an ambiguous task.

## Procedure

1. Inspect, in order, whatever is available:
   - current repository branch and working tree state
   - `.ai/standard.lock.yml`
   - `.ai/project/PROJECT.yml`, `METHOD.yml`, `GUIDANCE.yml`, `COMMANDS.yml`,
     `CONTEXT_INDEX.yml`, `CAPABILITIES.yml`, `TRACEABILITY.yml`,
     `ASSURANCE.yml`, `ROLES.yml`, `MERGE_POLICY.yml`
   - the active GitHub Issue, pull request, or Project item, when available
   - local TODO markers and foundation issue templates when no issue exists
   - recent CI or validation status when available
   If a source cannot be accessed, say so and continue with the best available
   local evidence — do not stop.
2. Classify the project into exactly one state from `NEXT_ACTION.md`'s table:
   No repository, New project initialization, Existing project adoption,
   Foundation setup, Backlog grooming, Active implementation, Review,
   Integration, Release preparation, Standard update, or Blocked.
3. Apply the decision rules: prefer finishing an open adoption, initialization,
   review, or release gate over starting new feature work; prefer making an
   issue Ready over implementing an unclear request; prefer a small
   investigation issue when the correct path is unknown; prefer project
   commands from `COMMANDS.yml` over guessed commands; prefer the project's
   selected method in `METHOD.yml`, or the adaptive default if absent.
4. Respond using this exact structure, with only the next one to three
   actions (defer more detailed plans to a plan template or GitHub Issue):

   ```text
   Current state:
   Evidence:
   Recommended next action:
   Why:
   Options:
   Risks or blockers:
   Suggested issue or PR update:
   ```

5. If the user appears non-technical or says they don't know what to do,
   avoid tool-specific jargon in the first answer and give one recommended
   action plus at most two alternatives.
6. If the recommendation identifies missing project facts, propose a
   foundation issue rather than guessing and encoding the guess as fact.
