# Design Document

## Overview

**Purpose**: Let an operator confirm their workspace will load, parse, and
resolve a write target cleanly before pointing an AI client at it.

**Impact**: adds `ai doctor` alongside the existing `ai setup generic`
subcommand; no existing command changes.

### Goals
- Report one check per resolved input file (exists, parses).
- Report whether a write target resolves unambiguously.
- Recommend `read` as the default external-client profile.
- Support `--format text|json`; perform no write.

### Non-Goals
- Cloud Mailbox / bridge diagnostics.
- Duplicating `lifetxt doctor`'s general system checks (Python version,
  disk space, optional dependencies) -- those are not MCP-specific.

## Boundary Commitments

### This Spec Owns
- `lifetxt ai doctor` and its checks/flags.

### Out of Boundary
- `lifetxt doctor`, `lifetxt mcp`, `lifetxt ai setup generic` (reused,
  not modified).
- Cloud Mailbox bridge diagnostics (later phase).

### Allowed Dependencies
- `lifetxt.paths.resolve_write_target` (pure).
- The same input-parsing helper `lifetxt doctor`/`lifetxt check` use
  (`_parse_life_inputs`) and `lifetxt.cli._normalize_paths` /
  `config_paths` / `config_write_file` (all already used by `ai setup
  generic`, #505).

### Revalidation Triggers
- A change to `resolve_write_target`'s exception message (this command's
  check-2 failure text quotes it).
- A change to `_parse_life_inputs`'s return shape.

## Architecture

Single new CLI command handler in `lifetxt/cli.py`, sharing the same
path-resolution helpers `command_ai_setup_generic` (#505) already uses.
No new module, no diagram.

## File Structure Plan

### Modified Files
- `lifetxt/cli.py` -- add `doctor` as a sibling of `setup` under the `ai`
  subparser group; add `command_ai_doctor(args)`.
- `tests/test_lifetxt.py` -- add CLI tests.
- `docs/en/ai-integration.md`, `docs/ja/ai-integration.md`,
  `docs/en/cli.md`, `docs/ja/cli.md` -- document the command.

## Requirements Traceability

| Requirement | Summary | Components | Interfaces | Flows |
|-------------|---------|-------------|------------|-------|
| 1.1 | Per-file exists/parse check | `command_ai_doctor` | reuses `_parse_life_inputs` | CLI |
| 1.2 | Missing/unparseable file reported, not raised | `command_ai_doctor` | try/except around the parse check | CLI |
| 1.3 | No writes | `command_ai_doctor` | read-only helpers only | CLI |
| 2.1 | Write target resolves | `command_ai_doctor` | `resolve_write_target` | CLI |
| 2.2 | Ambiguous target reported, not raised | `command_ai_doctor` | catches `ValueError` from `resolve_write_target` | CLI |
| 3.1 | Profile recommendation | `command_ai_doctor` | static check entry | CLI |
| 3.2 | JSON output | `command_ai_doctor` | `--format json` | CLI |
| 3.3 | Text output (default) | `command_ai_doctor` | OK/WARN/FAIL symbols matching `lifetxt doctor` | CLI |

## Components and Interfaces

### `command_ai_doctor`

| Field | Detail |
|-------|--------|
| Intent | Report workspace/write-target health for a direct-MCP setup |
| Requirements | 1.1, 1.2, 1.3, 2.1, 2.2, 3.1, 3.2, 3.3 |

**Responsibilities & Constraints**
- Resolves input paths the same way `ai setup generic` does.
- For each existing input path, parses it and reports a per-file
  OK/FAIL check; a missing path is its own FAIL check naming the path.
- Attempts `resolve_write_target`; reports OK naming the resolved target,
  or FAIL with the caught `ValueError`'s own message when ambiguous.
- Always reports one informational recommendation check naming `read`.
- Never opens any file in write mode.

**Contracts**: Service [x] / API [ ] / Event [ ] / Batch [ ] / State [ ]

##### Service Interface
```python
def command_ai_doctor(args) -> int:
    """Report workspace/write-target health for a direct-MCP setup.
    Never writes a file."""
```
- Preconditions: `args.format` is `"text"` or `"json"`.
- Postconditions: stdout contains formatted text or one JSON array; no
  file is created, modified, or deleted; return code is always 0 (this
  is advisory, not a hard gate -- matching `lifetxt doctor`'s own
  convention of reporting FAIL without a nonzero exit for optional
  checks).

**Implementation Notes**
- Integration: reuses `_parse_life_inputs`/`resolve_write_target`/
  `_normalize_paths` directly; introduces no new parsing or resolution
  logic.
- Risks: none beyond what `ai setup generic` (#505) already accepted for
  the same helpers.

## Testing Strategy

- Unit tests: a clean fixture workspace reports all-OK checks; a missing
  input file is reported FAIL naming the file, not raised; a parse-error
  fixture is reported FAIL, not raised; an ambiguous multi-source
  workspace with no `--write-file` is reported FAIL with the same
  message `lifetxt mcp` would raise; `--format json` returns the expected
  shape; no file in the fixture directory is created/modified.
