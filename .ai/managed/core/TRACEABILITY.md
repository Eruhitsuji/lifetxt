# Traceability Standard

Changes must be traceable from intent to release evidence.

## Required Chain

```text
Requirement
  -> Capability
  -> Epic
  -> Task
  -> Pull Request
  -> Test/Evidence
  -> Release
```

Every implementation task must identify the upstream requirement or capability
it supports. If none exists, create or propose the missing artifact before
implementation.

## Traceability Record

Traceability records should include:

- requirement ID
- capability ID
- epic or parent issue
- task issue
- pull request
- changed files or write scope
- tests and evidence
- release or deployment reference
- status: proposed, implemented, verified, released, deprecated, retired

## Consistency Rules

- A PR must link to an issue.
- A test or evidence item must link to the behavior it verifies.
- Release notes must identify the delivered capability or bug fix.
- Removed behavior must link to deprecation or retirement evidence.
- Traceability gaps require a follow-up issue or an approved exception.
