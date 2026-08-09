# Design Document

## Overview
Add a standard `--version`/`-V` flag to the top-level argparse parser (`lifetxt/cli.py:build_parser`), using argparse's built-in `action="version"` so the behavior (print and immediate exit) matches every other Python CLI tool's convention with zero custom logic.

### Goals
- `python -m lifetxt --version` / `-V` prints `lifetxt <version>` and exits 0.
### Non-Goals
- A separate `lifetxt version` subcommand with extended system info -- that richer view belongs to the doctor-unification task (separate spec), which already owns "system status at a glance."

## Boundary Commitments
### This Spec Owns
- The `--version`/`-V` flag registration only.
### Out of Boundary
- Doctor/system-status reporting (separate spec).
### Allowed Dependencies
- `lifetxt.__version__`.

## File Structure Plan
### Modified Files
- `lifetxt/cli.py` (`build_parser`): add `parser.add_argument("--version", "-V", action="version", version="lifetxt %(prog)s ...")` style registration.
- `tests/test_lifetxt.py` or a small dedicated test: assert `--version` exits 0 and prints the version string.

## Requirements Traceability
| Requirement | Design Element |
| --- | --- |
| 1.1, 1.2, 1.3 | `argparse.add_argument("--version", "-V", action="version", version=...)` on the top-level parser in `build_parser()` |

## Testing Strategy
- Unit: invoke the CLI with `--version` (via `entrypoint.main` with `sys.exit` captured, matching existing CLI test patterns) and assert exit code 0 and the version string in output.
- Live: run `python -m lifetxt --version` and `python -m lifetxt -V` as real subprocesses.
