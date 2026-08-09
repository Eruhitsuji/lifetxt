# Design Document

## Overview
`command_update`'s "nothing to update" check is generalized from exact
commit equality to ancestry: after the existing `current == target` fast
path (cheap, no subprocess), an unequal pair is additionally checked with
`git merge-base --is-ancestor <target> <current>` (exit 0 means `target`
is already reachable from `current`). Either condition sets the same
`already_merged` flag, which reports `up_to_date` exactly as before.

## Boundary Commitments
### This Spec Owns
- The `already_merged` computation in `command_update`, replacing the bare
  `if current == target:` check.
### Out of Boundary
- Every other safety rail and code path in `command_update` -- unchanged.
- `_git_commit_summary`, `_run_git_for_update`, `_reject_option_like_git_arg`
  -- unchanged, reused as-is.
### Allowed Dependencies
- `_run_git_for_update` (already exists).

## File Structure Plan
### Modified Files
- `lifetxt/cli.py` -- `command_update`'s up-to-date check.
- `tests/test_lifetxt.py` -- updated mocked dispatchers (a new
  `merge-base --is-ancestor` call needed a response in every test that
  reaches it) plus one new dedicated regression test.

## Requirements Traceability
| Requirement | Design Element |
| --- | --- |
| 1.1 | `already_merged = current == target` (unchanged fast path) |
| 1.2 | `if not already_merged: ancestor_check = _run_git_for_update(["merge-base", "--is-ancestor", target, current], ...); already_merged = ancestor_check.returncode == 0` |
| 1.3 | A proper descendant target makes `--is-ancestor` exit non-zero, leaving `already_merged` false and the existing dry-run/`--yes` flow unchanged |
| 1.4 | `merge-base --is-ancestor` only reads the object graph; it is not one of the two mutating operations (`fetch`, `merge --ff-only`) `command_update`'s docstring commits to as the only ones it ever runs -- it does not change that contract, since it mutates nothing |

## Testing Strategy
- Found via live `/verify` testing against this actual development
  checkout: `lifetxt update --ref main` (current branch built on top of and
  therefore ahead of `main`) incorrectly reported an available update.
  Reproduced deliberately and confirmed fixed against a disposable clone
  with a local tag pointing at an ancestor commit, fetched via a local-path
  remote (`--remote .`) to avoid relying on GitHub's raw-SHA fetch support:
  before the fix, reported `update_available_dry_run`; after, reports
  `up_to_date`. The normal forward-update case was re-verified against the
  same clone (fetching the newer `main` from a real `origin`) to confirm it
  still reports `update_available_dry_run` correctly.
- Unit tests: the shared mocked git dispatcher in
  `LifeTxtUpdateCommandCliTests._run` (and one test with its own inline
  dispatcher) updated to answer `merge-base --is-ancestor` calls; a new
  dedicated test confirms an ancestor target reports `up_to_date` without
  ever calling `merge`.
- Full suite re-run to confirm no regression elsewhere.
