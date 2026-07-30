# Repository Structure for AI-Driven Development

This document defines the target repository structure for lifetxt. It is intentionally a staged migration plan rather than an instruction to move every existing file at once. Structural changes must preserve imports, public commands, schemas, documentation links, package contents, and supported Python versions.

## Goals

The structure is designed to make work by maintainers, Codex, and Claude Code safer and easier to review.

- Make ownership and coupling visible from paths.
- Keep domain logic independent from CLI, TUI, Web, MCP, and Remote adapters.
- Separate authoritative source, generated artifacts, test fixtures, examples, and maintainer documentation.
- Reduce context required to understand a change.
- Allow subtree-specific `AGENTS.md` files as domains become large.
- Support incremental migration without a flag day.

## Current high-level structure

The repository currently has these major roots:

```text
.vscode/
docs/
editors/vscode/lifetxt/
examples/
lifetxt/
tests/
.gitignore
Dockerfile
LICENSE
life_txt_format_spec.md
pyproject.toml
railway.toml
readme.md
render.yaml
requirements-web.txt
todo.md
```

This remains valid during migration. Existing public paths must not be moved only for cosmetic consistency.

## Target structure

```text
lifetxt/
├── AGENTS.md
├── CLAUDE.md
├── readme.md
├── todo.md
├── pyproject.toml
├── requirements-web.txt
├── docs/
│   ├── en/                         # English user and operator documentation
│   ├── ja/                         # Japanese user and operator documentation
│   ├── development/                # Maintainer and AI-agent documentation
│   │   ├── repository-structure.md
│   │   ├── ai-development-workflow.md
│   │   ├── architecture.md         # Future subsystem and dependency map
│   │   ├── testing.md              # Future test tiers and evidence rules
│   │   └── decisions/              # Future architecture decision records
│   └── generated/                  # Only when generated docs are unavoidable
├── lifetxt/
│   ├── __init__.py
│   ├── entrypoint.py               # Stable console entry point
│   ├── core/                       # Grammar-independent shared primitives
│   │   ├── errors.py
│   │   ├── revisions.py
│   │   ├── locking.py
│   │   └── clock.py
│   ├── format/                     # Parser, model, diagnostics, canonical form
│   │   ├── model.py
│   │   ├── parser.py
│   │   ├── diagnostics.py
│   │   ├── canonical.py
│   │   └── migration.py
│   ├── workspace/                  # Config layering, manifests, source resolution
│   │   ├── model.py
│   │   ├── resolver.py
│   │   ├── config.py
│   │   └── migration.py
│   ├── operations/                 # Surface-neutral read/write use cases
│   │   ├── registry.py
│   │   ├── items.py
│   │   ├── agenda.py
│   │   ├── messages.py
│   │   └── proposals.py
│   ├── projects/                   # Projects, portfolio, command-center aggregation
│   ├── tickets/                    # Tickets, workflow, history, planning, reports
│   ├── attachments/                # Attachment model and transaction operations
│   ├── integrations/               # Provider-neutral contracts and adapters
│   ├── remote/                     # Remote protocol, auth, policy, clients
│   ├── recovery/                   # Journals, policies, evidence, restore workflows
│   ├── schemas/                    # Schema registry/generator source
│   ├── cli/                        # Thin command adapters and parser registration
│   ├── tui/                        # TUI state/layout/render/adapters
│   ├── web/                        # FastAPI and browser assets/adapters
│   ├── mcp/                        # MCP protocol adapters
│   └── compatibility/              # Explicit temporary compatibility shims only
├── tests/
│   ├── unit/                       # Pure module and domain tests
│   ├── contract/                   # Cross-surface and schema contract tests
│   ├── integration/                # Multi-module and process tests
│   ├── evidence/                   # Clearly named real/adverse environment harnesses
│   ├── fixtures/                   # Test-only input and expected-output data
│   └── helpers/                    # Test infrastructure, never runtime code
├── schemas/
│   ├── source/                     # Optional declarative schema sources
│   ├── generated/                  # Checked-in public schemas
│   └── examples/                   # Valid and invalid schema instances
├── examples/
│   ├── life/                       # Runnable life.txt datasets
│   ├── config/                     # Runnable configuration examples
│   ├── integrations/               # Secret-free provider examples
│   └── development/                # Ticket/project/dev-tool workflows
├── editors/
│   └── vscode/lifetxt/
├── scripts/
│   ├── generate/                   # Deterministic generators
│   ├── check/                      # Repository validation commands
│   └── release/                    # Future release automation
└── .github/
    ├── workflows/
    ├── ISSUE_TEMPLATE/
    └── pull_request_template.md
```

The tree above is a destination model. A directory should be introduced only when it has a clear responsibility and at least one coherent module or contract to own.

## Dependency direction

The intended dependency direction is:

```text
core -> format -> workspace -> domain modules -> operations -> surface adapters
```

More specifically:

- `core` must not import CLI, TUI, Web, MCP, Remote, or provider adapters.
- `format` may depend on `core`, but not on user-interface surfaces.
- `workspace` may depend on `core` and `format`.
- domain packages such as `tickets`, `projects`, and `attachments` may depend on `core`, `format`, and `workspace`.
- `operations` coordinates domain behavior and is the preferred entry point for mutations.
- CLI, TUI, Web, MCP, and Remote modules translate transport/UI input to shared operations; they must not reimplement domain rules.
- integrations may observe external systems and produce normalized events or proposals. Direct authoritative writes require an admitted shared operation and complete safety contract.

Circular dependencies are a design defect. Resolve them by extracting a smaller domain contract, not by adding late imports without documentation.

## Module naming

Choose names that expose responsibility.

Good:

- `ticket_revision_writes.py`
- `workspace_resolver.py`
- `remote_authorization.py`
- `schema_registry.py`

Avoid:

- `utils.py`
- `helpers.py`
- `common.py`
- `misc.py`
- `manager.py` without a precise domain

When a flat domain accumulates several tightly related files, first create a package with a stable public facade. Preserve old import paths through a documented compatibility module only when downstream compatibility requires it.

## Public and private modules

Each domain package should expose a small stable facade through `__init__.py` or a clearly named service module. Internal modules should not become public merely because another surface imports them.

Before moving a module:

1. search all imports, tests, documentation links, monkey patches, and dynamic registrations;
2. identify public names and supported invocation paths;
3. add the destination module and compatibility import where required;
4. migrate callers in one coherent batch;
5. run focused and full tests;
6. remove the compatibility path only after the roadmap condition is met.

## Tests

Tests should mirror runtime domains and communicate evidence level.

- `unit`: deterministic behavior with no external process or network.
- `contract`: schemas, real serialized outputs, CLI/Web/MCP/Remote equivalence, compatibility refusal.
- `integration`: filesystem, subprocess, multiple modules, recovery simulation.
- `evidence`: explicitly manual or environment-dependent verification. Passing a simulated test must not be described as real power-loss, browser, TLS, SMTP, or platform evidence.

Existing tests may remain flat while touched domains migrate. Do not move tests separately from the code and imports they validate.

## Schemas and generated files

Every generated artifact must document:

- the authoritative source;
- the generator command;
- deterministic ordering rules;
- the verification command;
- compatibility/versioning behavior.

Generated files should contain a notice when practical. CI should fail when regeneration changes tracked outputs.

Do not create both `lifetxt/schemas/` and top-level `schemas/source/` unless responsibilities are explicit. A reasonable split is Python generator/registry code under `lifetxt/schemas/` and public generated JSON files under top-level `schemas/generated/`.

## Documentation

- `docs/en/` and `docs/ja/` are user/operator documentation and must remain equivalent in meaning.
- `docs/development/` is the canonical location for architecture, development workflow, testing policy, and AI-agent guidance.
- Architecture decisions that affect compatibility, authority, data safety, permissions, or dependency direction should be recorded in `docs/development/decisions/` once the ADR convention is introduced.
- The root README should stay task-oriented and link to detailed documents rather than duplicating all maintainer rules.

## Migration phases

### Phase 0: Rules and visibility

- Add `AGENTS.md`, `CLAUDE.md`, development documentation, and a PR template.
- Document current-to-target mapping and coupling rules.
- Add no import-path changes.

### Phase 1: Guardrails

- Add repository checks for documentation parity, generated artifacts, forbidden direct writes, module size, and import direction.
- Establish test tiers without moving all tests.
- Add subtree `AGENTS.md` only for large/high-risk domains.

### Phase 2: Surface extraction

- Split monolithic CLI and TUI modules into thin adapters backed by existing shared operations.
- Preserve command names and public behavior.
- Add contract tests before moving logic.

### Phase 3: Domain packages

- Group ticket, project, remote, recovery, attachment, and integration modules into domain packages.
- Add stable facades and temporary compatibility imports.
- Migrate one domain per PR.

### Phase 4: Format and workspace foundations

- Move parser/canonical/diagnostic and workspace/configuration modules only after Format 1.0 and migration boundaries are stable.
- Treat these moves as compatibility work, not feature work.

### Phase 5: Cleanup

- Remove expired compatibility modules and monkey patches.
- Enforce import boundaries in CI.
- Update packaging metadata and contributor documentation.

## Rules for structural pull requests

A structural PR must:

- avoid mixing unrelated feature behavior with file moves;
- preserve public imports or document a migration;
- show old-to-new path mapping;
- update tests and documentation links;
- verify package installation and console entry points;
- retain blame/history where possible through pure moves before edits;
- update `todo.md` with completed migration scope and remaining phases;
- state what was not migrated.

Large all-at-once reorganizations are not acceptable while major public contracts are still evolving. Prefer domain-sized, reviewable migrations with explicit compatibility boundaries.
