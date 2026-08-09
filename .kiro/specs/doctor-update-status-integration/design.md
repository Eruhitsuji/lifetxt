# Design Document

## Overview
Add `--check-update`/`--repo`/`--update-timeout` to the `doctor` subparser.
`command_doctor`, when `--check-update` is set, calls
`_resolve_update_check_repo(args, config)` and
`_github_latest_release_or_tag(repo, timeout=...)` (both already exist,
shared unmodified with `update-check`) inside a `try`/`except ValueError`
block, adding one `update` check row via the existing `add_check` closure.
Any failure -- network, API, or version-parsing -- is caught and reported
as `WARN`, never raised, so `command_doctor` cannot fail because of this
check.

## Boundary Commitments
### This Spec Owns
- The `--check-update`/`--repo`/`--update-timeout` doctor arguments and the
  new `update` check row in `command_doctor`.
### Out of Boundary
- `update-check` and `update`'s own commands -- unchanged, reused as-is.
- `doctor`'s other checks (python/system/life.txt/config/disk/tools/
  dependencies/check/ids) -- unchanged.
### Allowed Dependencies
- `_resolve_update_check_repo`, `_github_latest_release_or_tag`,
  `_parse_simple_version` (all pre-existing, from the `cli-update-check`
  change).

## File Structure Plan
### Modified Files
- `lifetxt/cli.py` -- new `doctor` arguments, `update` check row.
- `tests/test_lifetxt.py` -- regression tests.
- `docs/en/cli.md`, `docs/ja/cli.md` -- documentation, including the
  `doctor` check table.

## Requirements Traceability
| Requirement | Design Element |
| --- | --- |
| 1.1 | `if getattr(args, "check_update", False):` guards the entire block; the flag defaults to `False` (`action="store_true"`) |
| 1.2, 1.3, 1.4 | Mirrors `command_update_check`'s own status branching (`update_available` -> WARN, `up_to_date`/`ahead_of_latest` -> OK, `no_release_found` -> OK), collapsed into one `add_check` call per outcome |
| 1.5 | `_resolve_update_check_repo(args, config)` reused unmodified; `args.repo` is the same attribute name `update-check`/`update` already use |
| 1.6 | `--update-timeout` (default 5, distinct from `update-check`'s own `--timeout` default of 10, since a health-check command should stay fast) threaded into `_github_latest_release_or_tag`'s `timeout` parameter |
| 2.1, 2.2 | `try: ... except ValueError as exc: add_check("WARN", "update", ...)`; `add_check` only sets `any_fail` on `"FAIL"`, never `"WARN"`, so this check can never change the exit code |

## Testing Strategy
- Unit tests (network mocked via `lifetxt.cli.urlopen`, in-process calls to
  `command_doctor` since `run_cli` spawns a real subprocess and cannot be
  mocked): flag omitted omits the row entirely, up-to-date reports OK,
  update-available reports WARN with exit code still 0, a network failure
  reports WARN (not FAIL) with exit code still 0, no-release-found reports
  OK.
- Live verification (not part of the committed suite): real `doctor
  --check-update` against this project's own repository (no releases yet)
  correctly reports OK/"No published releases..."; `doctor --check-update
  --repo torvalds/linux` against a real repository with releases correctly
  reports WARN naming the real latest tag.
- Full suite plus `tests.test_surface_runtime` re-run to confirm the new
  arguments and check row do not disturb any capability/command-catalog
  consistency gate.
