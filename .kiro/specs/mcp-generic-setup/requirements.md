# Requirements Document

## Project Description (Input)

`lifetxt ai setup generic`: a read-only, side-effect-light CLI command for
the lifetxt repository. GitHub Issue #505, parent epic #500, extends #502's
`--profile` flag. Standard assurance (read-only, additive CLI command, no
change to `lifetxt mcp` itself).

Who has the problem: an operator who wants to connect an external AI client
to their `lifetxt mcp` server. Today they must read
`docs/en/ai-integration.md` and hand-write a client configuration; there is
no command that prints the exact, copy-pasteable command/config for their
own workspace.

Current situation: `lifetxt mcp` (with #502's `--profile` flag) is the
integration surface, but nothing generates a ready-to-paste configuration
from it.

What should change: add `lifetxt ai setup generic`, which prints (a) the
exact `python -m lifetxt mcp ...` command for the current workspace's
resolved paths/write-file, and (b) a generic MCP client configuration JSON
snippet (the same `mcpServers` shape already documented in
`docs/en/ai-integration.md`). The emitted profile defaults to `read` unless
the operator explicitly asks for `assist` or `full`. The command performs no
write of any kind and never edits any third-party client configuration
file automatically.

## Boundary Context

- **In scope**: `lifetxt ai setup generic`; resolving the current
  workspace's paths/write-file the same way `lifetxt mcp` would; printing a
  command line and a generic client configuration snippet; `--profile` and
  `--format text|json`.
- **Out of scope**: provider-specific adapters (`lifetxt ai setup
  chatgpt|claude|gemini`, etc.); `lifetxt ai status`/`doctor`/`clients`; any
  change to `lifetxt mcp` itself or to permission-profile enforcement
  (already implemented by #502).
- **Adjacent expectations**: this feature relies on `lifetxt mcp --profile`
  (#502) already existing and behaving as documented; it does not
  reimplement or alter that enforcement.

## Requirements

### Requirement 1: Print a ready-to-run command and generic client configuration

**Objective:** As an operator setting up MCP access, I want a command that prints the exact command and a generic client configuration for my workspace, so that I can connect an AI client without hand-writing either.

#### Acceptance Criteria

1. When the operator runs `lifetxt ai setup generic`, the CLI shall print a `python -m lifetxt mcp ...` command line reflecting the current workspace's resolved input paths and write target.
2. When the operator runs `lifetxt ai setup generic`, the CLI shall print a generic MCP client configuration snippet naming the same command and arguments as the printed command line.
3. The CLI shall not write, modify, or delete any file when running `lifetxt ai setup generic`.

### Requirement 2: Default to a constrained profile

**Objective:** As an operator, I want the emitted example to default to a safe profile, so that copying it without changing anything does not grant an AI client full write access by accident.

#### Acceptance Criteria

1. When the operator runs `lifetxt ai setup generic` without `--profile`, the CLI shall emit a command and configuration using the `read` profile.
2. When the operator runs `lifetxt ai setup generic --profile assist` or `--profile full`, the CLI shall emit a command and configuration using the requested profile instead.
3. If the operator supplies a `--profile` value other than `read`, `assist`, or `full`, then the CLI shall reject the invocation with a clear error.

### Requirement 3: Machine-readable output

**Objective:** As an operator or script author, I want a JSON output mode, so that the setup information can be consumed programmatically.

#### Acceptance Criteria

1. When the operator runs `lifetxt ai setup generic --format json`, the CLI shall print the command (as an argument list) and the client configuration as a JSON object instead of formatted text.
2. When `--format` is omitted, the CLI shall print human-readable text.
