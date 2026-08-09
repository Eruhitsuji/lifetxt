# Requirements Document

## Project Description (Input)
Found during live `/verify` testing of the `cli-web-multiday-enhancements`
batch: `lifetxt update --ref main` against a real checkout that was already
*ahead* of `main` (built on top of it, containing all of `main`'s history)
incorrectly reported `"Update available on ... : <current> -> <target>
... Re-run with --yes to fast-forward"`, even though the resolved target
was actually an ancestor of the current commit -- there was nothing to
update. `command_update`'s only "nothing to do" check was exact commit
equality (`current == target`), which misses the case where the fetched
ref resolves to an older commit already contained in the current branch's
history (a stale `--ref`, an older release/tag, or -- as found here -- a
base branch that the current branch has since diverged ahead of).

## Requirements

### Requirement 1: A target already reachable from HEAD is reported as up to date
**Objective:** As an operator running `lifetxt update`, I want an accurate
report when the resolved target is already contained in my current
history, so that I am never told to `--yes` a fast-forward that isn't one.

#### Acceptance Criteria
1. WHEN the fetched target commit is identical to the current commit, THE
   SYSTEM SHALL report `up_to_date` (unchanged from prior behavior).
2. WHEN the fetched target commit differs from the current commit but is
   an ancestor of it (already merged into the current branch's history),
   THE SYSTEM SHALL also report `up_to_date`, not
   `update_available_dry_run`.
3. WHEN the fetched target commit is a proper descendant of the current
   commit (a real, outstanding fast-forward), THE SYSTEM SHALL continue to
   report `update_available_dry_run` (or `updated` with `--yes`),
   unchanged from prior behavior.
4. THE SYSTEM SHALL determine ancestry using `git merge-base
   --is-ancestor`, a read-only git query, adding no new mutation risk.

## Out of Scope
- Reporting a *different* status for "target is behind" versus "target
  equals current" -- both are equally "nothing to update," and the
  distinction is not useful to the operator.
