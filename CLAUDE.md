# CLAUDE.md

Claude Code must treat [`AGENTS.md`](AGENTS.md) as the canonical project instruction set and read it before planning, editing, testing, committing, or opening a pull request.

## Claude Code startup sequence

1. Read `AGENTS.md`.
2. Read `docs/development/repository-structure.md` and `docs/development/ai-development-workflow.md`.
3. Inspect `todo.md`, the relevant implementation modules, tests, schemas, configuration, examples, and English/Japanese documentation.
4. Confirm the current branch is an `agent/<short-description>` branch created from the latest `main`.
5. Produce a concrete plan before non-trivial work and keep it updated as discoveries change the scope.

## Working rules

- Prefer repository inspection over assumptions. Search for existing domain abstractions before adding new modules.
- Keep changes narrow and cohesive. Do not opportunistically reformat or rename unrelated files.
- Do not bypass semantic mutation, exact-revision, locking, journal, permission, privacy, or schema-version boundaries.
- Do not hand-edit generated files without identifying and running the authoritative generator.
- Keep English and Japanese documentation synchronized in meaning.
- Treat `todo.md` as a detailed active roadmap, not a changelog or short summary.
- Use focused tests during implementation and run `python -m unittest discover` before the PR when feasible.
- Open a draft PR and request maintainer merge. Never merge the PR yourself.

## Context management

When the repository is too large to hold in one context window:

- start from the public entry point and domain module;
- read adjacent tests before implementation;
- inspect registries and schemas that define the contract;
- record discovered invariants in the working plan;
- re-open source files immediately before editing rather than relying on stale excerpts;
- review the complete diff and `todo.md` before finalizing.

Directory-specific `AGENTS.md` files, when present, add or override instructions for their subtree. Follow the closest applicable file together with the root rules.
