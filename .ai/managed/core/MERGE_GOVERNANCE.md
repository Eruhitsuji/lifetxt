# Merge Governance Standard

Merge governance protects the default branch from unreviewed, untraceable, or
unsafe changes.

## Required Rules

- direct push to `main` is prohibited
- force push is prohibited
- pull request is required
- related Issue is required
- required CI must pass
- unresolved review comments block merge
- Definition of Done must be satisfied
- review after the latest push is required
- stale approvals are invalid
- Implementer and Merge Authority are separated
- the actor who made the latest push cannot be the only final approver
- AI must not have Ruleset bypass permission
- shared-file conflicts are resolved by Integrator or Owner
- Merge Queue is used when available and appropriate
- conflicts are not resolved mechanically without semantic review
- rollback or revert plan is confirmed before merge

## Review Freshness

A review is stale when:

```text
reviewed_commit != current_head_commit
```

Stale reviews must be repeated or explicitly reconfirmed by an authorized
reviewer.

## Shared Files

Tasks that touch shared files must name:

- shared files
- owner or integrator
- integration order
- conflict risk
- rollback strategy

## Integration Branches

Related sub-tasks may land as sub-PRs into a shared integration branch before
one final PR merges that branch into the default branch (see `TRACEABILITY.md`'s
"Multi-PR Integration Branches" for the traceability recording rule).

- Required checks apply at both levels: each sub-PR must pass required checks
  before merging into the integration branch, and the integration branch must
  pass required checks again before merging into the default branch.
- Review freshness applies at both levels; a sub-PR review does not substitute
  for review of the final integration PR's head commit.
- The rollback or revert plan must address both the integration-branch merge
  and the final default-branch merge, since reverting the final merge does not
  automatically undo what the integration branch accumulated.

## Merge Evidence

PRs must record:

- linked issue
- assurance level
- review ledger result
- required checks
- unresolved risks
- migration and compatibility impact
- rollback or revert approach
