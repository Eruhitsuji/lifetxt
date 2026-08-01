# Knowledge Maintenance Standard

Project knowledge must remain current enough for humans and AI tools to make
consistent decisions.

## Living Specification

The living specification includes:

- `.ai/project/PROJECT.yml`
- `.ai/project/CAPABILITIES.yml`
- `.ai/project/TRACEABILITY.yml`
- `.ai/project/ASSURANCE.yml`
- `.ai/project/ROLES.yml`
- `.ai/project/LIFECYCLE.yml`
- project architecture, structure, rules, commands, scopes, and exceptions

## Change Package Archival

After a change is merged:

1. Update the living specification.
2. Link PR, tests, review ledger, and release evidence.
3. Mark the change package completed.
4. Move or record the package under an archive location.

Do not leave current behavior described only in an archived or closed change
package.

## Upstreaming Project Rules

When the same project-specific rule appears in multiple projects, propose it as
a common standard or profile update.
