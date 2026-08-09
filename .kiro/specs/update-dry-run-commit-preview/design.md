# Design Document

## Overview
Add `_git_commit_summary(repo_root, current, target, timeout, limit=20)` to
`lifetxt/cli.py`: runs `git log --oneline --max-count=<limit> <current>..<target>`
plus `git rev-list --count <current>..<target>` (both read-only), returning
`(commits, total_count)`. On any git failure, returns `([], 0)` rather than
raising. `command_update` calls this once (after fetch, before the dry-run/
`--yes` branch) and includes the result in both the JSON `result` dict and
the text message for both the dry-run and the post-update confirmation.

## Boundary Commitments
### This Spec Owns
- `_git_commit_summary` and its two call sites in `command_update`'s
  dry-run and `--yes` success paths.
### Out of Boundary
- Every existing safety rail in `command_update` (dirty-tree/detached-HEAD/
  non-git refusals, fetch, `merge --ff-only`) -- unchanged.
- `update-check` -- unchanged.
### Allowed Dependencies
- `_run_git_for_update` (already exists; reused unmodified).

## File Structure Plan
### Modified Files
- `lifetxt/cli.py` -- `_git_commit_summary`, wiring into `command_update`.
- `tests/test_lifetxt.py` -- regression tests.
- `docs/en/cli.md`, `docs/ja/cli.md` -- documentation.

## Requirements Traceability
| Requirement | Design Element |
| --- | --- |
| 1.1, 1.2 | `_git_commit_summary` capped at `_UPDATE_LOG_PREVIEW_LIMIT` (20); `commit_count > len(commits)` appends an "... and N more" line |
| 1.3 | `result["commits"]`/`result["commit_count"]` set before either `emit()` call in the post-fetch branch |
| 1.4 | Both the dry-run and `--yes` success message-building blocks call the same `_commit_lines()` closure |
| 2.1 | `_git_commit_summary` checks `.returncode` itself and returns `([], 0)` on failure instead of raising |
| 2.2 | Only `log` and `rev-list` are added -- both read-only, neither touches refs or the working tree |

## Testing Strategy
- Unit tests (`subprocess.run` mocked): commit list populated correctly in
  JSON output, long list truncated with the correct remaining count in text
  output, a `git log`/`rev-list` failure does not block the dry-run report
  (empty list, `update_available_dry_run` still reported), already-up-to-date
  path never touches `commits` and skips the lookup entirely.
- Live verification (not part of the committed suite): against a real
  disposable clone of this repository checked out at its very first commit,
  dry-run against `--ref main` correctly listed the 20 most recent of an
  896-commit range with an accurate "... and 876 more" line; `--format json`
  correctly reported the same 20 commits plus the true `commit_count`.
