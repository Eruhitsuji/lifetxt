# Design Document

## Overview

**Purpose**: Give an operator a copy-pasteable command and MCP client
configuration for their own workspace, without hand-writing either.

**Users**: operators setting up an external AI client for the first time.

**Impact**: adds a new `ai` CLI command group with one subcommand,
`setup generic`. No existing command changes.

### Goals
- Print a `python -m lifetxt mcp ...` command matching the current
  workspace's resolved paths/write target.
- Print a generic MCP client configuration snippet using the same
  command/arguments.
- Default the emitted profile to `read`.
- Support `--format text|json`.
- Perform no write of any kind.

### Non-Goals
- Provider-specific adapters (`ai setup chatgpt|claude|gemini`).
- `ai status`/`ai doctor`/`ai clients`/`ai bridge`.
- Any change to `lifetxt mcp` itself.

## Boundary Commitments

### This Spec Owns
- `lifetxt ai setup generic` and its `--profile`/`--write-file`/`--format`
  flags.
- The printed command line and client configuration snippet's shape.

### Out of Boundary
- `lifetxt mcp`'s own behavior (#502; reused, not modified).
- Any other `lifetxt ai *` subcommand -- this spec adds only the `ai`
  parser group's structure needed for `setup generic`, not the sibling
  commands #500 lists for later phases.

### Allowed Dependencies
- `lifetxt.paths.resolve_write_target` (pure; raises on genuine ambiguity
  rather than guessing).
- `lifetxt.webapp.normalize_server_paths` (pure; glob expansion only).
- `lifetxt.config.config_paths` / `config_write_file`.
- `lifetxt.mcp.MCP_PROFILES` (the three valid profile values from #502).

### Revalidation Triggers
- A change to `lifetxt mcp`'s own argument names/defaults (this command's
  printed output must keep matching what `lifetxt mcp` actually accepts).
- Adding a sibling `lifetxt ai *` command (should reuse this command's
  `ai` parser group, not create a second one).

## Architecture

Single new CLI command handler in `lifetxt/cli.py`, reusing existing
read-only path-resolution helpers. No new module, no diagram (one
component, no external integration).

## File Structure Plan

### Modified Files
- `lifetxt/cli.py` -- add the `ai` subparser group with a `setup`
  sub-subparser and a `generic` sub-sub-subparser; add
  `command_ai_setup_generic(args)`.
- `tests/test_lifetxt.py` -- add CLI tests for the new command.
- `docs/en/ai-integration.md`, `docs/ja/ai-integration.md` -- document the
  command.
- `docs/en/cli.md`, `docs/ja/cli.md` -- add a command reference entry.

No new files.

## Requirements Traceability

| Requirement | Summary | Components | Interfaces | Flows |
|-------------|---------|-------------|------------|-------|
| 1.1 | Print command line | `command_ai_setup_generic` | resolves paths/write target the same way `lifetxt mcp` would | CLI |
| 1.2 | Print client config | `command_ai_setup_generic` | builds `mcpServers` JSON from the same resolved values | CLI |
| 1.3 | No writes | `command_ai_setup_generic` | uses only pure resolution helpers, never opens a file for writing | CLI |
| 2.1 | Default profile `read` | `command_ai_setup_generic` | `--profile` default `"read"` | CLI |
| 2.2 | Explicit profile override | `command_ai_setup_generic` | `--profile` choices | CLI |
| 2.3 | Invalid profile rejected | CLI `ai setup generic` subparser | `argparse choices=` | CLI |
| 3.1 | JSON output | `command_ai_setup_generic` | `--format json` | CLI |
| 3.2 | Text output (default) | `command_ai_setup_generic` | default format | CLI |

## Components and Interfaces

### `command_ai_setup_generic`

| Field | Detail |
|-------|--------|
| Intent | Resolve the current workspace's MCP command/config and print it |
| Requirements | 1.1, 1.2, 1.3, 2.1, 2.2, 2.3, 3.1, 3.2 |

**Responsibilities & Constraints**
- Resolves input paths and write target exactly as `lifetxt mcp` would
  (same helpers, same precedence: explicit CLI paths/`--write-file`, else
  config, else `life.txt`), so the printed command is guaranteed to match
  what `lifetxt mcp` would actually do with the same arguments.
- Never opens any file in write mode.
- Builds one `mcpServers` JSON object naming `python`, `-m`, `lifetxt`,
  `mcp`, `--profile`, the resolved profile, `--write-file` (when the
  resolved write target differs from the first input), and the resolved
  input paths.

**Contracts**: Service [x] / API [ ] / Event [ ] / Batch [ ] / State [ ]

##### Service Interface
```python
def command_ai_setup_generic(args) -> int:
    """Print a python -m lifetxt mcp command and a generic MCP client
    configuration for the resolved workspace. Never writes a file."""
```
- Preconditions: `args.profile` is `None` or one of `MCP_PROFILES`
  (enforced by argparse `choices=`); `args.format` is `"text"` or
  `"json"`.
- Postconditions: stdout contains either formatted text or one JSON
  object; no file on disk is created, modified, or deleted.

**Implementation Notes**
- Integration: reuses `resolve_write_target`/`normalize_server_paths`
  directly rather than constructing an `McpContext` -- constructing one
  under a non-`read` profile could trigger `assert_unique_workspace_ids`
  and a transaction startup preflight (which can create a journal
  directory when `transactions.preflight_on_startup` is configured),
  which would violate this command's own "no write of any kind"
  requirement.
- Risks: if `resolve_write_target` raises (multiple input sources, no
  explicit write target), this command surfaces that error directly
  rather than guessing -- the same requirement `lifetxt mcp` itself would
  need satisfied to actually start.

## Testing Strategy

- Unit tests: default profile is `read`; `--profile assist`/`full`
  override the emitted profile; an invalid `--profile` value is rejected;
  `--format json` returns a JSON object with the expected command/config
  shape; the printed command's paths/write-file match a fixture
  workspace's config; no file is created/modified by the command
  (assert the temp directory's file set is unchanged before/after).
- Documentation: `scripts/validate_release_docs.py` passes after updating
  `docs/en/ai-integration.md` / `docs/ja/ai-integration.md` and
  `docs/en/cli.md` / `docs/ja/cli.md`.
