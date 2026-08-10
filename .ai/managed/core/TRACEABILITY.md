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

## Multi-PR Integration Branches

Some batches of related sub-tasks land as sub-PRs into a shared integration
branch before one final PR merges that branch into the default branch. This
breaks the single `pull request` field's implicit one-PR-per-task assumption,
since a sub-task's traceability record is often written before the final
integration PR exists.

- Each sub-task's traceability record keeps naming its own sub-PR. Do not
  rewrite a sub-PR entry to point at the integration PR instead — that
  misattributes the work to a PR that did not implement it.
- Add one further traceability entry for the integration-branch-to-default-branch
  PR itself, with that PR as its own `pull_request` step, linked to the epic or
  parent issue covering the batch.
- The integration PR's entry does not replace or supersede the sub-PR entries;
  it records the additional consolidation step.
