# Prepare for a future integration branch

The current integration, release source and documented deployment branch are
`main`. A permanent `next` branch is deferred. Review the current contract and
the remaining migration work with:

```bash
python scripts/check_branch_readiness.py
python scripts/check_branch_readiness.py --candidate next --json
```

The read-only tool checks `.ai/project/BRANCH_STRATEGY.json` against explicit
repository evidence: project/default branch, merge policy, final PR rule, CI
main push trigger, tagged release trigger and the main server-update runbook.
It reports `change_required` and `manual_required` items with source paths.
Exit 0 means the **current main-only contract is consistent**, not that next
is ready. `migration_ready` remains false and candidate state remains deferred.
Malformed or missing metadata, inconsistent sources and invalid candidate names
exit 1. The candidate-name check accepts a conservative subset of Git names.

The JSON metadata makes branch roles explicit for future tools and design
reviews. Changing it does not change GitHub's default branch, workflow triggers,
AI PR destinations, release provenance or a server checkout. The script checks
known source patterns rather than parsing all GitHub Actions semantics. If a
source is restructured, review and update its check instead of accepting a
missing pattern as success.

Before adoption, use the report in a dedicated design Issue to decide:

- feature PR and next-to-main promotion contracts, traceability and review;
- next push checks, aggregate gates and main's complete compatibility checks;
- branch protection, required check names and human promotion authority;
- approved main release/tag provenance;
- separate test server checkout, data, service, backup and fixed-SHA evidence;
- acceptance criteria and rollback ownership.

GitHub settings, actual server state and data isolation are not queried or
inferred. This tool creates no branches, changes no workflows or server settings,
and performs no deployment. Adoption requires a separate human decision.
