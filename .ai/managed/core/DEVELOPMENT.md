# Development Standard

## Principles

- Prefer small, reviewable changes.
- Preserve compatibility unless an approved issue authorizes a breaking change.
- Follow existing project architecture before adding new abstractions.
- Add abstractions only when they remove real duplication or clarify ownership.
- Treat documentation and tests as part of the deliverable.

## Change Control

Every non-trivial change must be linked to:

- a GitHub Issue
- acceptance criteria
- verification commands
- a pull request

Out-of-scope work discovered during implementation must be recorded as a new
issue rather than silently added to the current pull request.

## Standard Work Items

Every implementation issue should identify:

- lifecycle phase
- owner
- executor
- reviewer
- write scope
- forbidden scope
- acceptance criteria
- verification commands
- expected documentation impact
- security and compatibility impact

## Phase Gate Rule

Work may be lightweight, but each phase must have an explicit gate:

- requirements gate: the issue satisfies Definition of Ready
- design gate: affected contracts and risks are reviewable
- implementation gate: the change is scoped and traceable
- verification gate: commands and results are recorded
- review gate: a separate party reviewed the final diff
- release gate: Definition of Done is satisfied

## Error Handling

- Prefer explicit failure modes over silent fallback.
- Preserve useful diagnostic context without logging secrets.
- Include recovery guidance when an operator or user can act.

## Dependencies

Add dependencies only when:

- the problem is not better solved by existing project code
- the dependency is maintained and has acceptable license/security posture
- the change includes lockfile updates and verification
- the pull request explains the reason and alternatives considered
