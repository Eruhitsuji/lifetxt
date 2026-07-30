# AGENTS.md

This file is the canonical repository-level instruction set for AI coding agents, including Codex and Claude Code. Read it before planning or changing files. More specific `AGENTS.md` files may be added inside subdirectories when a subsystem needs stricter rules; the nearest file takes precedence for that subtree.

## Project intent

lifetxt is a dependency-light Python implementation of the life.txt format. The plain-text files remain authoritative. CLI, TUI, Web, MCP, schemas, configuration, documentation, and editor support must stay semantically aligned.

## Required workflow

1. Start from the latest `main` branch and create an `agent/<short-description>` branch. Never implement directly on `main`.
2. Inspect the relevant implementation, tests, schemas, configuration registry, English and Japanese documentation, and `todo.md` before changing behavior.
3. Write a concrete implementation plan for non-trivial changes. State affected contracts, compatibility risks, data-safety implications, and validation commands.
4. Make the smallest coherent change that preserves public behavior unless the task explicitly requires a versioned migration.
5. Add or update tests before considering the change complete.
6. Run the focused tests first, then the full dependency-free suite when feasible:
   - `python -m unittest <focused test module>`
   - `python -m unittest discover`
7. Update all affected documentation and generated/public contract files. English and Japanese documentation must remain equivalent in meaning.
8. Update `todo.md` in English according to the rules below.
9. Review the final diff for unrelated edits, direct-write regressions, missing schema/version changes, stale documentation, and accidental secrets.
10. Commit, push, and open a draft pull request. Ask the maintainer to merge it; do not merge it yourself.

## `todo.md` update rules

Every implementation PR must update `todo.md` without reducing it to a summary.

- Change the header to `Last updated: YYYY-MM-DD (updated xN)` using the current date and incrementing `N` by one.
- Remove roadmap items that are fully completed by the PR.
- Rewrite partially completed items so that implemented work is described accurately and only remaining work stays actionable.
- Add detailed follow-up work revealed by the implementation.
- Add concrete future-feature proposals when the change exposes useful adjacent opportunities.
- Re-evaluate priorities and move items between P0, P1, P2, and Deferred when evidence justifies it.
- Keep all roadmap prose in English.
- Do not claim real-environment, security, performance, compatibility, or recovery evidence that was not actually produced.

## Architecture and safety invariants

- Keep life.txt authoritative and human-inspectable.
- Route authoritative writes through validated, atomic, conflict-aware operations. Do not introduce ad-hoc file replacement.
- Multi-target changes must use explicit revision sets and journal/recovery semantics; do not describe compensated writes as portable filesystem atomicity.
- Preserve unknown custom keys and repeated values unless a versioned contract explicitly forbids them.
- Fail closed when permissions, privacy, revisions, schema versions, or recovery state are ambiguous.
- Treat external systems as authorities where appropriate. Store references, normalized summaries, proposals, and audited actions rather than silently mirroring full histories.
- Keep secrets out of life.txt, repository files, logs, fixtures, diagnostics, snapshots, and pull-request descriptions.
- Keep optional integrations and rich UI dependencies optional. The parser and core CLI must remain dependency-light.
- Avoid direct host-clock, randomness, network, subprocess, or environment-dependent behavior in deterministic components unless the contract explicitly permits and tests it.
- Do not enable a new remote mutation until authentication, permission, privacy, exact-revision, idempotency, clock/replay, event-history, recovery, and interruption behavior are defined and tested.

## Repository placement rules

Use the target structure documented in `docs/development/repository-structure.md`.

- Runtime package code belongs under `lifetxt/`, grouped by stable domain rather than by individual feature batch.
- Tests belong under `tests/` and should mirror the runtime domain they verify.
- User documentation belongs under `docs/en/` and `docs/ja/`.
- Maintainer and AI-agent documentation belongs under `docs/development/`.
- Runnable sample data belongs under `examples/`; test-only fixtures belong under `tests/fixtures/`.
- Generated artifacts must have a documented generator and verification command. Do not hand-edit generated outputs unless the generator contract explicitly requires it.
- Editor integrations belong under `editors/<editor>/`.
- GitHub templates and automation belong under `.github/`.
- Do not create catch-all modules such as `utils.py`, `helpers.py`, or `common.py` when a domain-specific module name is available.

## Change-coupling checklist

When one of these areas changes, inspect the coupled areas before finishing:

- Grammar/parser/canonicalization: diagnostics, schemas, examples, CLI conversion, Web/MCP output, English/Japanese format docs.
- CLI command or option: command registry, help/completion, capability discovery, docs, tests, Web command palette where supported.
- Configuration key: defaults, registry, validation, schema, migration, `config explain`, examples, English/Japanese docs.
- Public JSON shape: schema version, real-response validation, compatibility behavior, capability/version negotiation, docs.
- Mutation behavior: exact revisions, locks, dry-run, conflicts, audit/history, recovery, read-only behavior, remote denial.
- Ticket/project behavior: workflow, events/time entries, reports, privacy, query/saved views, CLI/TUI/Web/MCP/remote parity.
- Web/MCP/remote surface: authentication, authorization, CSRF/origin where relevant, redaction, bounds, pagination, capability discovery, older-client behavior.

## Coding and test conventions

- Support the Python baseline declared in `pyproject.toml`; do not use newer syntax without first changing and validating that baseline.
- Prefer explicit types and small domain-focused functions.
- Preserve deterministic ordering in outputs, diagnostics, schemas, and tests.
- Tests must cover success, validation failure, stale revision/conflict, read-only refusal, and interruption/recovery when applicable.
- Use temporary directories and synthetic credentials in tests. Never depend on a developer's home directory or real account.
- Keep error codes and externally consumed messages stable unless a migration is documented.
- Comments should explain invariants and non-obvious tradeoffs, not restate code.

## Pull request requirements

The draft PR description must include:

- what changed and why;
- files and contracts affected;
- user/developer impact;
- compatibility, safety, and migration notes;
- validation commands and results;
- remaining work recorded in `todo.md`.

Before requesting merge, confirm that the branch contains only intended changes and that every claim in the PR is supported by code, tests, or explicitly identified manual evidence.
