# Git and GitHub Standard

Default branch: `main`.

Recommended branch names:

```text
feature/<issue>-short-name
fix/<issue>-short-name
task/<issue>-short-name
docs/<issue>-short-name
ai/codex/<issue>-short-name
ai/claude/<issue>-short-name
ai/kiro/<issue>-short-name
chore/standard-update-v<version>
```

## Pull Requests

Every pull request must include:

- related issue
- assurance level
- purpose
- change summary
- out-of-scope items
- verification results
- standard evaluation results when the standard changes
- security impact
- compatibility impact
- migration impact
- review ledger or review summary
- rollback or revert approach
- AI involvement
- required human decisions
- remaining risks

Use closing keywords such as `Closes #123` when the pull request completes an
issue.

## Protected Branch Rules

Protect `main` with:

- pull request required
- required checks
- code owner review where available
- stale approval dismissal
- approval of most recent reviewable push
- unresolved conversation blocking
- force push disabled
- delete branch disabled
- merge queue when the repository volume justifies it

Use `MERGE_GOVERNANCE.md` for stale review, merge authority, shared-file, and
rollback rules. AI tools must not have Ruleset bypass permission.
