# Design Document

## Overview
Add `lifetxt update-check` to `lifetxt/cli.py`: a new subparser plus
`command_update_check(args)`, backed by two small helpers --
`_parse_simple_version(text)` (dotted-numeric version parser, tolerant of a
leading `v` and a trailing pre-release/build suffix) and
`_github_latest_release_or_tag(repo, timeout)` (GitHub REST API query with
release-then-tag fallback). Uses the stdlib `urllib.request`/`urllib.error`
already imported at the top of `cli.py` (the same modules `fetch_url` uses
for iCalendar sources), keeping the project's dependency-light design intact
-- no new runtime dependency.

## Boundary Commitments
### This Spec Owns
- `lifetxt update-check` and its two supporting helpers.
### Out of Boundary
- `lifetxt update` (an actual self-update command). That is a separate,
  higher-assurance change (Security/High, its own cc-sdd spec and change
  package) that will reuse `_github_latest_release_or_tag` and
  `_parse_simple_version` from this change rather than duplicating them.
- Any existing command (`doctor`, `--version`, etc.) -- unchanged.
### Allowed Dependencies
- `urllib.request.Request`/`urlopen`, `urllib.error.HTTPError`/`URLError`
  (already imported in `cli.py`).
- `lifetxt.__version__` (already used by the `--version` flag added
  earlier in this batch).

## File Structure Plan
### Modified Files
- `lifetxt/cli.py` -- new subparser registration, `_UPDATE_CHECK_REPO`
  constant, `_parse_simple_version`, `_github_api_get`,
  `_github_latest_release_or_tag`, `command_update_check`.
- `tests/test_lifetxt.py` -- regression tests (network calls mocked).
- `docs/en/cli.md`, `docs/ja/cli.md` -- new command documentation; also
  corrects the `doctor` check table, which had drifted out of sync with the
  `doctor-unification` change earlier in this batch (found while editing
  the same section).

## Requirements Traceability
| Requirement | Design Element |
| --- | --- |
| 1.1, 1.2 | `_github_latest_release_or_tag`: GET `/releases/latest`, on 404 fall back to GET `/tags` |
| 1.3 | Both endpoints exhausted with nothing found -> returns `(None, None, None)`; `command_update_check` reports `status: "no_release_found"`, returns 0 |
| 1.4 | `latest > current` / `latest < current` / `latest == current` (tuple comparison) map to `update_available`/`ahead_of_latest`/`up_to_date` |
| 1.5 | `_parse_simple_version(latest_text)` returning `None` maps to `status: "unparseable"` |
| 1.6 | `--format` argparse choice; JSON branch serializes the `OrderedDict` result; text branch prints the human-readable message |
| 2.1 | `command_update_check` performs no file writes; only `write_text(None, ...)` (stdout) |
| 2.2 | At most one `/releases/latest` call, and one `/tags` call only when the first returned 404 |
| 2.3 | `--timeout` argparse option, threaded into both `urlopen` calls |
| 2.4 | A non-404 `HTTPError` or any `URLError` raises `ValueError`, which `main()`'s existing top-level handler turns into `ERROR: ...` plus exit 1 -- the same fail-loud convention every other CLI command already uses |

## Testing Strategy
- Unit tests mocking `lifetxt.cli.urlopen` (matching the existing pattern in
  `tests/test_remote_client_v20.py`) covering: no release/tag found, a
  release found and newer, falling back to a tag when no release exists and
  it being older, versions matching, a non-404 HTTP error, and a network
  error -- each asserting the exact `status` value and exit behavior.
- A version-parser unit test covering `v`-prefixed, suffixed, and
  unparseable inputs.
- An argparse wiring test confirming `update-check` resolves to
  `command_update_check`.
- Live verification (not part of the committed suite): a real, unmocked
  `lifetxt update-check` run against the actual `Eruhitsuji/lifetxt`
  repository, confirming it correctly reports `no_release_found` (this
  repository currently has no Releases or tags) in both text and JSON
  format.
- Full suite plus the surface-consistency drift gates
  (`tests.test_surface_runtime`) re-run to confirm the new subcommand does
  not disturb any existing capability/command-catalog consistency check.
