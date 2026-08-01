# Capability Management Standard

Use a Capability Registry to prevent missing features, duplicate features, and
uncoordinated reimplementation.

## Capability Registry

Downstream projects maintain `.ai/project/CAPABILITIES.yml`.

Each capability records:

- stable capability ID
- name and summary
- status
- owner
- source requirements
- implementation locations
- public interfaces
- tests or evidence
- related issues and PRs
- replacement or deprecation information when applicable

## Duplicate and Reuse Check

Before implementing a feature, check:

- existing capability IDs
- related issues and pull requests
- existing API endpoints or commands
- common libraries and reusable modules
- dependency packages already in use

The task must record the decision:

- reuse existing capability
- extend existing capability
- create new capability
- replace or deprecate existing capability

Potential duplicates must be resolved before the task becomes Ready.

## Capability ID Rules

- IDs are stable and unique within the project.
- IDs should be human-readable, such as `cap-auth-login`.
- Do not reuse retired IDs for unrelated behavior.
- Validation should fail when duplicate active IDs are detected.
