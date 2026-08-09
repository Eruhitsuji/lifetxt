# Requirements Document

## Project Description (Input)
`docs/en/cli.md`'s TUI command tables are kept in sync with `lifetxt.tui_app.COMMANDS` by hand, with no automated check -- unlike the existing Web/TUI command-catalog consistency gate (`tests/test_surface_runtime.py`'s `test_live_web_command_catalog_matches_tui_registry_gate`). Add an equivalent automated drift test.

## Requirements

### Requirement 1: Documentation drift between the TUI command registry and docs/en/cli.md is caught automatically
**Objective:** As a maintainer adding or changing a TUI command, I want an automated test that fails when `docs/en/cli.md`'s command tables fall out of sync with `tui_app.COMMANDS`, so that drift is caught in CI instead of going unnoticed.

#### Acceptance Criteria
1. When a command exists in `tui_app.COMMANDS` but is not documented in `docs/en/cli.md`'s "#### Commands" section, the test shall fail naming the missing command.
2. When `docs/en/cli.md` documents a command no longer present in `tui_app.COMMANDS`, the test shall fail naming the stale entry.
3. When a documented command's usage string differs from `tui_app.COMMANDS`' registered usage, the test shall fail naming both values.
4. While the two are in sync, the test shall pass.
