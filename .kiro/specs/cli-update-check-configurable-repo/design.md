# Design Document

## Overview
Add `_resolve_update_check_repo(args, config)` to `lifetxt/cli.py`:
resolves `args.repo` (from a new `--repo` flag), then
`config_section(config, "update").get("repository")`, then the existing
`_UPDATE_CHECK_REPO` constant as the last-resort default, validating the
result looks like `OWNER/NAME`. `command_update_check` calls this once and
uses the result everywhere it previously used `_UPDATE_CHECK_REPO` directly.
Registers `update.repository` in `config_registry.CONFIG_REGISTRY` and in
`schema_extensions_v5.py`'s `config-v1.schema.json` generator (mirrored into
`dist/schemas/config-v1.schema.json`, matching this project's established
generate-then-mirror process for that file).

## Boundary Commitments
### This Spec Owns
- `_resolve_update_check_repo`, `command_update_check`'s repo resolution,
  the `--repo` flag, and the `update.repository` registry/schema/doc
  entries.
### Out of Boundary
- `_github_latest_release_or_tag`, `_parse_simple_version`,
  `_github_api_get` -- unchanged, already repository-parameterized from the
  original `cli-update-check` change.
- `lifetxt update` (the separate self-update command, item D) -- will reuse
  `_resolve_update_check_repo` rather than duplicating the resolution logic,
  but that wiring is that spec's own task.
### Allowed Dependencies
- `config_section` (already imported in `cli.py`).

## File Structure Plan
### Modified Files
- `lifetxt/cli.py` -- `_resolve_update_check_repo`, `--repo` argument,
  `command_update_check` updated to use the resolved repo.
- `lifetxt/config_registry.py` -- `update.repository` entry.
- `lifetxt/schema_extensions_v5.py` -- `update` object added to the
  `config-v1.schema.json` generator and to `schema_samples_v5()`.
- `dist/schemas/config-v1.schema.json` -- mirrored addition.
- `docs/en/config.md`, `docs/ja/config.md` -- new "Update checks" section.
- `docs/en/cli.md`, `docs/ja/cli.md` -- `update-check` section updated to
  mention `--repo` and link to the config section.
- `tests/test_lifetxt.py`, `tests/test_config_validation.py` -- regression
  tests.

## Requirements Traceability
| Requirement | Design Element |
| --- | --- |
| 1.1, 1.4 | `update.repository` entry in `CONFIG_REGISTRY` |
| 1.2, 1.3 | `_resolve_update_check_repo`: `explicit or configured or _UPDATE_CHECK_REPO` |
| 2.1, 2.2 | `--repo` argparse option, read first in the resolver |
| 2.3 | `re.match(r"^[^/\s]+/[^/\s]+$", repo)` raises `ValueError` (fails loudly per this project's CLI error convention) on a malformed result |
| 3.1 | Existing `LifeTxtUpdateCheckCliTests` (8 tests from the original change) re-run unmodified |

## Testing Strategy
- Unit tests: `--repo` overrides the default; `update.repository` config is
  used when no flag is given; `--repo` takes precedence over configured
  `update.repository`; no flag/config falls back to the built-in default;
  an invalid repository format fails loudly.
- Config registry/schema tests mirroring the existing
  `config.write.require_revision` pattern:
  `test_registry_describes_update_repository`,
  `test_config_schema_declares_update_repository`.
- `tests.test_schema_extensions_v2`'s existing byte-identical bundle test
  confirms the generator and the mirrored `dist/schemas/config-v1.schema.json`
  file match exactly.
- Live verification (not part of the committed suite): `--repo
  torvalds/linux` against the real GitHub API; a real `.lifetxt.json` with
  `update.repository` set to the same repository, confirming the config
  path produces an identical result; `lifetxt config explain
  update.repository` against a real invocation.
- Full suite plus `tests.test_config_validation`, `tests.test_lifetxt`,
  `tests.test_schema_extensions_v2`, `tests.test_workspace_foundation`
  re-run to confirm no regression.
