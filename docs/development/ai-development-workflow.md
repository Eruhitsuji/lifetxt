# AI-Driven Development Workflow

This workflow applies when Codex, Claude Code, or another coding agent implements changes in lifetxt. `AGENTS.md` is authoritative; this document expands the operational sequence.

## 1. Establish the task boundary

Before editing, identify:

- the user-visible behavior or maintainer outcome;
- the authoritative source of truth;
- affected public commands, APIs, schemas, configuration keys, and file formats;
- mutation, revision, permission, privacy, recovery, and compatibility implications;
- evidence required to make the final claims.

Do not turn an implementation request into a broad cleanup. Record adjacent work in `todo.md` instead.

## 2. Synchronize and branch

- Start from the latest remote `main`.
- Create `agent/<short-description>`.
- Confirm the branch contains no unrelated work.
- Never commit implementation directly to `main`.

## 3. Build a source map

Read the smallest complete set of relevant files:

1. public entry point or surface adapter;
2. shared operation/domain implementation;
3. tests for the behavior;
4. schemas and configuration registry;
5. English and Japanese documentation;
6. examples and generated outputs;
7. relevant roadmap entries in `todo.md`.

Search for registrations, aliases, monkey patches, dynamic dispatch, capability rows, and import compatibility before moving or renaming modules.

## 4. Write the implementation plan

For non-trivial work, the plan should list:

- files to add, update, move, or remove;
- contract and version changes;
- compatibility strategy;
- tests to add or update;
- documentation and example updates;
- generated artifacts and commands;
- `todo.md` changes;
- validation commands.

Update the plan when repository evidence contradicts the initial assumption.

## 5. Implement through shared contracts

Prefer this order:

1. domain model and validation;
2. surface-neutral operation;
3. exact-revision, locking, journal, or permission integration when writing;
4. schemas and capability metadata;
5. CLI/TUI/Web/MCP/Remote adapters;
6. documentation and examples.

A surface adapter should translate inputs and outputs. It should not contain a second implementation of domain rules.

## 6. Validate incrementally

Run the narrowest relevant test after each coherent change. Typical sequence:

```bash
python -m unittest tests.test_relevant_module
python -m unittest discover
```

When applicable, also validate:

- installed console entry point;
- generated schemas and examples;
- English/Japanese documentation parity;
- dependency-free behavior;
- read-only refusal;
- stale and missing revisions;
- conflict response shape;
- process interruption and recovery;
- older configuration/schema/client refusal or migration.

Do not label simulation as real-environment evidence. Browser, terminal, TLS, SMTP, power-loss, storage, and platform claims require the corresponding environment.

## 7. Update `todo.md`

Use the exact rules in `AGENTS.md`.

The roadmap update should explain the implemented foundation in enough detail that a future agent can distinguish it from remaining work. Remove completed checklist entries, rewrite partially completed entries, add newly discovered work, and reconsider priority.

Do not append a changelog section that leaves completed work duplicated as unchecked tasks.

## 8. Review the diff

Check for:

- unrelated formatting or file changes;
- public behavior changed without tests or migration notes;
- direct writes that bypass shared operations;
- missing revision, lock, permission, privacy, or recovery handling;
- schemas that describe representative data instead of real outputs;
- English/Japanese drift;
- generated files edited without the generator;
- secrets, local paths, personal data, tokens, or credentials;
- unsupported Python syntax;
- claims stronger than the produced evidence.

For structural changes, include an old-to-new path map and verify imports, packaging, documentation links, and console scripts.

## 9. Commit and open a draft PR

Use a terse commit message that describes the complete change. Open a draft PR with:

- purpose;
- implementation summary;
- affected files and contracts;
- user/developer impact;
- safety and compatibility notes;
- validation results;
- remaining work in `todo.md`.

Do not merge the PR. Ask the maintainer to review and merge it.

## Recommended agent handoff record

When one agent hands work to another, include:

```text
Goal:
Branch:
Current commit:
Implemented:
Files changed:
Contracts/versions affected:
Tests run and results:
Known failures or unavailable evidence:
Remaining steps:
todo.md changes still required:
```

The handoff must describe repository state, not an intended future state.

## Task completion definition

A change is complete only when:

- the requested behavior or artifact exists;
- relevant tests pass or failures are transparently documented;
- coupled schemas/configuration/docs/examples are updated;
- `todo.md` follows the update rules;
- the final diff is scoped and reviewed;
- a draft PR exists and the maintainer has been asked to merge it.
