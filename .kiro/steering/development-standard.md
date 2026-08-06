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

Spec-driven work in this project writes into the standard's change packages, not
into a `.kiro/specs/` tree. Per #101: a specification directory only Kiro reads
would be an alternative source of truth outside the repository and GitHub, which
`.ai/managed/core/AI_TOOL_COMPATIBILITY.md` forbids adapters from creating.

One directory per change:

```text
.ai/project/changes/<change-id>/
  change.yml  requirements.yml  design.md  decisions.md  traceability.yml  verification.yml
```

Copy `.ai/project/changes/_template/` to start. Where a spec artifact has an
obvious counterpart, use it: requirements go in `requirements.yml`, design in
`design.md`, decisions and their rejected alternatives in `decisions.md`.

Not every change needs a package. `.ai/project/changes/README.md` sets the
threshold: non-trivial changes, High or Regulated assurance work, public API
changes, data changes, migrations, operations changes, or any change where
requirements, design, tasks, tests, and release evidence may drift. Below that
threshold, the issue and pull request carry the reasoning.

### Tasks are GitHub Issues

Do not write a `tasks.md` checklist. `.ai/managed/core/TASK_MANAGEMENT.md` makes
GitHub Issues the source of truth for actionable work, and
`.ai/managed/core/INDEX.md` lists "no implementation without a reviewable task
source" in the non-overridable baseline. A second task list in the repository
would compete with that.

Decomposition output becomes issues, each meeting
`.ai/managed/core/DEFINITION_OF_READY.md`.

### A specification does not authorise implementation

Approved requirements and a reviewed design are inputs to task decomposition. The
gate for starting work is an issue that meets Definition of Ready and is not
`status:inbox` or `status:blocked`. Writing the spec does not open that gate.
