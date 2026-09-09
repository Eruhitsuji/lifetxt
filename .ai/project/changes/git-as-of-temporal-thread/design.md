# Design: Git-backed as-of selection

The selector resolves an explicit ref or HEAD, enumerates reachable commits
within a hard limit, and chooses the candidate with the greatest committer
timestamp not later than the offset-aware cutoff. Full SHA descending is the
fixed tie-break. Author timestamps and domain dates do not participate.

The selected SHA is passed to the exact-revision snapshot path. Shallow or
unverifiable history and missing paths become limitations and make evidence
incomplete. No matching commit is an error without fallback.

All operations are read-only, time-bounded, and size-bounded. Rollback is a PR
revert and no user data migration is required.
