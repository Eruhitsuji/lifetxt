# Requirements Document

## Project Description (Input)

`lifetxt ai doctor`: a read-only CLI command for the lifetxt repository.
GitHub Issue #507, parent epic #500, third implementation child alongside
#502 (permission profiles) and #505 (generic setup command).

Who has the problem: an operator about to connect an AI client to
`lifetxt mcp` who wants to know, before doing so, whether the workspace
will actually load, parse, and resolve a write target cleanly.

Current situation: `lifetxt doctor` checks general system health (Python
version, disk space, optional dependencies) but nothing MCP-specific;
`lifetxt ai setup generic` (#505) prints a ready-to-use command but does
not validate that the workspace will actually work.

What should change: add `lifetxt ai doctor`, reporting whether the
resolved workspace input files exist and parse without error, whether a
write target resolves unambiguously (or the exact error `lifetxt mcp`
itself would raise), and a recommendation naming `read` as the default
profile for external/untrusted clients. Read-only; no write of any kind.

## Boundary Context

- **In scope**: `lifetxt ai doctor` and its `--write-file`/`--format`
  flags; input-file existence/parse checks; write-target resolution
  checks; a static profile-recommendation line.
- **Out of scope**: Cloud Mailbox / bridge diagnostics (pending/rejected
  request counts, mailbox transport health, credential environment
  presence); any change to `lifetxt doctor`, `lifetxt mcp`, or `lifetxt ai
  setup generic`.
- **Adjacent expectations**: relies on `lifetxt mcp --profile` (#502) and
  the path-resolution helpers `lifetxt ai setup generic` (#505) already
  uses; does not redefine either.

## Requirements

### Requirement 1: Workspace health checks

**Objective:** As an operator, I want to know before connecting a client whether my workspace will load cleanly, so that I do not discover a parse error or missing file only after a client is already connected.

#### Acceptance Criteria

1. When the operator runs `lifetxt ai doctor`, the CLI shall report one check per resolved input file confirming it exists and parses without error.
2. If a resolved input file is missing or fails to parse, then the CLI shall report that file's check as failed, naming the file, rather than raising an unhandled exception.
3. The CLI shall not write, modify, or delete any file when running `lifetxt ai doctor`.

### Requirement 2: Write-target resolution check

**Objective:** As an operator, I want to know whether a write target resolves unambiguously, so that I do not discover a `lifetxt mcp` startup failure only when a client already expects it to be running.

#### Acceptance Criteria

1. When a write target resolves unambiguously for the given inputs, the CLI shall report that check as passed and name the resolved target.
2. If the write target is ambiguous (multiple input sources, no explicit `--write-file`), then the CLI shall report that check as failed with the same guidance `lifetxt mcp` itself would give, rather than crashing.

### Requirement 3: Profile guidance and output format

**Objective:** As an operator, I want a reminder of the recommended default profile and a machine-readable output option, so that I do not need to re-read #502's documentation and can script this check when useful.

#### Acceptance Criteria

1. The CLI shall report a recommendation naming `read` as the default profile for external or untrusted AI clients.
2. When the operator runs `lifetxt ai doctor --format json`, the CLI shall print the checks as a JSON array instead of formatted text.
3. When `--format` is omitted, the CLI shall print human-readable text using the same OK/WARN/FAIL symbol convention `lifetxt doctor` already uses.
