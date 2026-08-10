# Core Standard Index

Core standards are mandatory for every downstream project unless a rule is
explicitly marked overridable and the project records an approved exception.

## Documents

- `DEVELOPMENT.md`: implementation quality and change control
- `PROCESS.md`: lifecycle, phase gates, and method-independent process mapping
- `DEVELOPMENT_METHODS.md`: supported development methods and selection rules
- `SPECIFICATION_LIFECYCLE.md`: full product, software, release, operations,
  incident, deprecation, and retirement lifecycle
- `ARTIFACT_CONSISTENCY.md`: consistency gates across requirements, design,
  tasks, implementation, tests, operations, and release artifacts
- `ASSURANCE_LEVELS.md`: change type and risk-based evidence levels
- `NEXT_ACTION.md`: AI guidance flow for "what should I do next?"
- `AI_TOOL_COMPATIBILITY.md`: common behavior model across AI tools
- `AI_HUMAN_INTERACTION.md`: human-facing presentation, decision requests, and
  approval triggers
- `AI_PERMISSIONS.md`: least-privilege AI operation and approval boundaries
- `REVIEW.md`: review types, required viewpoints, and approval rules
- `CODING.md`: coding conventions and maintainability
- `TESTING.md`: verification strategy and reporting
- `SECURITY.md`: secrets, input handling, and security review
- `GIT_GITHUB.md`: branch, pull request, and GitHub rules
- `MERGE_GOVERNANCE.md`: merge authority, stale review, shared-file, and
  rollback requirements
- `TASK_MANAGEMENT.md`: Issues and Projects as the task source of truth
- `TASK_DECOMPOSITION.md`: task size, complexity, dependency, and scope rules
- `TRACEABILITY.md`: Requirement -> Capability -> Task -> PR -> evidence chain
- `CAPABILITY_MANAGEMENT.md`: capability registry, reuse, duplicate, and
  deprecation rules
- `MULTI_AGENT_DEVELOPMENT.md`: multi-human and multi-AI parallel execution
- `OPERATIONS.md`: monitoring, logging, incident, rollback, and retirement
  viewpoints
- `AUTOMATION_AND_HOOKS.md`: automation boundaries and mechanical safeguards
- `KNOWLEDGE_MAINTENANCE.md`: keeping reusable knowledge current and promotable
- `STANDARD_DISTRIBUTION.md`: `.ai/managed` and `.ai/project` model
- `SKILLS.md`: tool-neutral packaged procedure contract and storage model
- `STANDARD_EVALUATION.md`: model-neutral evaluation scenarios for the standard
- `RUNTIME_EVIDENCE.md`: local-first AI history archives, normalized events,
  runtime findings, privacy, and reporting controls
- `DEFINITION_OF_READY.md`: start conditions for AI-ready tasks
- `DEFINITION_OF_DONE.md`: completion conditions

## Non-Overridable Baseline

Downstream projects must not weaken these requirements:

- no secrets in repositories, prompts, logs, issues, or pull requests
- no direct push to protected default branches
- no implementation without a reviewable task source
- no final approval by the same AI that implemented the change
- no write-scope violations during parallel development
- no claim that checks passed unless they were executed
- no merge when the latest review is stale
- no AI bypass of protected branch rules or human-only approvals
- no raw AI history, transcripts, local paths, secrets, or private URLs in
  public issues or pull requests without explicit privacy approval
- no data deletion, migration, release, rollback, or retirement without the
  required human authority

## Standard Development Model

Downstream projects may choose a method that fits their context. If no method
has been selected, use the adaptive default: small iterations, Kanban flow, and
W-model quality gates.

```text
Discovery
  -> Product Requirements
  -> System / Software Requirements
  -> Architecture and Design
  -> Task Decomposition
  -> Implementation
  -> Developer Verification
  -> Independent Review
  -> Integration Verification
  -> Release Approval
  -> Deployment
  -> Operations and Monitoring
  -> Incident and Maintenance
  -> Evaluation and Improvement
  -> Deprecation
  -> Retirement
```

Each phase must define its expected input, output, review viewpoint, and test
viewpoint. The phase can be lightweight, but it must be explicit.

Each change must also choose three independent axes:

- development method: workflow cadence and planning style
- change type: Feature, Bug, Investigation, Refactoring, Security,
  Performance, Migration, Operations, Incident, Deprecation, or Standard Update
- assurance level: Quick, Standard, High, or Regulated

## AI Guidance

When a user asks "what should I do next?", AI tools must follow
`NEXT_ACTION.md`. They should inspect the project state, identify the current
phase, and recommend the safest next action. This is required so beginners can
use the project without already knowing GitHub Issues, PRs, or development
methods.

AI tools should use downstream `.ai/project/CONTEXT_INDEX.yml` to load only the
standards needed for the current task. `AGENTS.md`, `CLAUDE.md`, and
`.kiro/steering/**` are entry points, not full copies of the standard.

## Tool Compatibility

Codex, Claude Code, Kiro, and future AI tools must use the same task contract,
role names, quality viewpoints, and reporting shape. Tool-specific adapter
files are only entry points; they must not define conflicting standards.

## Runtime Evidence

When a downstream project enables runtime evidence collection, AI development
history must remain local-first by default. Findings must distinguish project
execution problems from upstream standard gaps, use sanitized reports, and
avoid raw transcript disclosure unless a human explicitly approves it.

## Project Adoption

The standard supports two downstream adoption paths:

- new project initialization from a template repository
- existing project adoption through a dedicated adoption issue and pull request

Both paths must install the same `.ai/managed` snapshot model. Existing project
adoption must preserve current files by default and defer enforcement until the
project can pass the required checks.
