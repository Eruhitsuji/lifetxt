# Standard Distribution Standard

The common standard is distributed to downstream projects as a committed,
version-locked snapshot.

## Downstream Directories

```text
.ai/
+-- standard.lock.yml
+-- managed/
+-- project/
```

## Adoption Modes

The same downstream layout is used for new and existing projects.

New projects install the standard during repository initialization. Existing
projects install it through a dedicated adoption pull request.

| Mode | Managed Snapshot | Project Rules | Existing Files |
| --- | --- | --- | --- |
| New project | created during bootstrap | generated from templates | minimal or absent |
| Existing project | added or refreshed in adoption PR | created with TODOs where needed | preserved by default |

Existing project adoption must not rewrite or delete established CI, templates,
AI instructions, branch rules, or ownership files unless the adoption pull
request explicitly documents the change and rollback path.

## Required Project Layer Files

Every active downstream project should eventually have:

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
- `.ai/project/PERMISSIONS.yml`
- `.ai/project/LIFECYCLE.yml`
- `.ai/project/changes/`

Existing projects may start with TODO values, but TODOs must be tracked as
foundation issues before the project is considered fully active.

## Ownership

| Path | Owner | Normal feature edits |
| --- | --- | --- |
| `.ai/managed/**` | common standard | prohibited |
| `.ai/project/**` | downstream project | allowed |
| `.ai/standard.lock.yml` | standard update process | prohibited outside update tasks |
| `AGENTS.md` | generated adapter plus project entry | integrator only |
| `CLAUDE.md` | generated adapter plus project entry | integrator only |
| `.kiro/steering/**` | generated adapter plus project entry | integrator only |

## Lock File

Every downstream project must record:

- standard repository
- version
- commit SHA
- installed profiles
- adapter versions
- install/update timestamp

Do not use floating branches such as `main` for required standards.

## Existing Project Adoption

When installing the standard into an existing project:

- create an adoption issue first
- audit existing workflows, templates, commands, owners, and AI instruction files
- create a dedicated adoption branch
- install `.ai/managed/**` and `.ai/standard.lock.yml`
- create missing `.ai/project/**` files without inventing unknown commands
- initialize context loading, capability registry, traceability, assurance,
  role, permission, merge policy, and lifecycle files with TODOs where facts
  are unknown
- preserve existing `AGENTS.md`, `CLAUDE.md`, `.kiro/`, and `.github/` files by
  default
- record preserved files and manual merge work in the adoption pull request
- defer branch-rule enforcement until required checks are stable

The project may start at a passive or guided adoption level and move to enforced
operation later.
