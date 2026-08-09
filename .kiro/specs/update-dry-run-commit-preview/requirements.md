# Requirements Document

## Project Description (Input)
`lifetxt update`'s dry-run output (the default, no `--yes`) reports only the
current and target commit hashes, not what is actually in between. An
operator deciding whether to run `--yes` has no way to see what they would
be pulling in without leaving lifetxt and running `git log` themselves.
Direct follow-up to the just-shipped `lifetxt-self-update` capability,
requested to strengthen its own safety story: seeing the commit list before
committing to `--yes` is exactly the kind of information a cautious operator
needs.

## Requirements

### Requirement 1: The dry-run preview lists pending commits
**Objective:** As an operator running `lifetxt update` without `--yes`, I
want to see what commits I would be pulling in, so that I can decide
whether to proceed with `--yes` without leaving the tool.

#### Acceptance Criteria
1. WHEN `update` reports `update_available_dry_run`, THE SYSTEM SHALL list
   the commits between the current and target commit, newest first, one
   line each (hash and subject), in text output.
2. WHEN the commit range has more commits than the display limit, THE
   SYSTEM SHALL show a count of the remaining commits rather than silently
   truncating.
3. THE SYSTEM SHALL also include the commit list and the true total count
   as `commits` and `commit_count` fields in `--format json` output.
4. THE SYSTEM SHALL apply the same commit-list reporting to a successful
   `--yes` update's confirmation message, so the "what changed" summary is
   available after applying an update too, not only before.

### Requirement 2: The commit-list lookup never blocks the update itself
**Objective:** As an operator, I want a failure to look up the commit list
to never prevent `update` from reporting or applying the actual
fast-forward, so that a cosmetic preview failure cannot block the real
operation.

#### Acceptance Criteria
1. WHEN the `git log`/`git rev-list` lookup fails for any reason, THE
   SYSTEM SHALL report an empty commit list and continue reporting the
   pending fast-forward normally, rather than raising an error.
2. THE SYSTEM SHALL NOT make any additional git call that could mutate the
   working tree or branch pointer as part of this preview.
