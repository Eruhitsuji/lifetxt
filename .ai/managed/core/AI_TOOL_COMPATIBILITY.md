# AI Tool Compatibility Standard

This standard reduces differences between Codex, Claude Code, Kiro, and future
AI tools by defining one tool-neutral behavior model and thin tool-specific
adapters.

## Authoritative Model

The source of truth is:

```text
.ai/managed/     common standard snapshot
.ai/project/     project-specific rules
GitHub Issue      task contract and acceptance criteria
Pull Request      review and integration unit
```

Tool-specific files are entry points only:

```text
AGENTS.md         Codex and compatible agents
CLAUDE.md         Claude Code
.kiro/steering/   Kiro
```

Adapters must point to the same authoritative documents. They must not create
separate rules that change the common behavior.

## Common Execution Contract

Every AI tool must follow this sequence:

1. Read the common standard, project rules, commands, and target task.
2. Use `.ai/project/CONTEXT_INDEX.yml` to load task-relevant rules by trigger.
3. Identify the current process phase, method, change type, and assurance level.
4. Confirm scope, write scope, dependencies, acceptance criteria, traceability,
   capability impact, and required human approvals.
5. Plan non-trivial work before editing.
6. Change only files allowed by the task contract.
7. Run applicable checks or clearly report why they could not run.
8. Inspect the diff before reporting completion.
9. Report changed files, verification results, and remaining risks.

## Adapter Responsibilities

Adapters may define:

- how the tool imports project files
- when the tool should use planning mode
- how the tool should request permissions
- how the tool should report verification results
- tool-specific safety limitations

Adapters must not define:

- conflicting task lifecycle states
- conflicting review requirements
- weaker security or secret-handling rules
- alternative sources of truth outside the repository and GitHub
- tool-specific exceptions that are not recorded under `.ai/project`

## Minimum Context Pack

When transferring work between AI tools or between a human and an AI, include:

- repository and branch
- target issue or pull request
- current process state
- selected development method
- standard version and commit SHA
- applicable context index entries and rule IDs
- write scope and forbidden scope
- acceptance criteria
- assurance level and human approvals still needed
- commands run and results
- open decisions, blockers, and risks

Use `templates/handoff.md` when the handoff is longer than a short comment.

## Normalized Role Names

Use these role names across all tools:

- Planner
- Architect
- Implementer
- Reviewer
- Tester
- Integrator
- Maintainer

If a tool has internal role names, map them to these names in the adapter or
task contract.

## Reporting Compatibility

AI reports must be readable without knowing which AI produced them. Avoid
tool-specific status words unless they are required by the tool UI.

Required report fields:

- objective
- current state or phase
- decision or action taken
- files changed or inspected
- verification
- risks and follow-up

## Runtime Evidence Compatibility

When a downstream project enables runtime evidence collection, supported AI
tools should be evaluated through the same provider-neutral evidence model:

- local provider history is collected into archive records
- provider-specific data is normalized into common event kinds
- deterministic checks use normalized events rather than tool-specific formats
- semantic checks identify ambiguity, conflicting guidance, or workflow friction
- findings use the common finding schema and sanitized reporting template

Use `.ai/project/AI_HISTORY.yml` for downstream collection policy and
`RUNTIME_EVIDENCE.md` for the common contract.

## Adding a New AI Tool

To support a new AI tool:

1. Add an adapter under `adapters/<tool>/`.
2. Reference `.ai/managed` and `.ai/project`.
3. Map the tool's capabilities to the common execution contract.
4. Add any tool-specific limitations.
5. Update validation if the adapter becomes required.
