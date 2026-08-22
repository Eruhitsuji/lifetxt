# Design

## Summary

Add `lifetxt mcp --profile read|assist|full`, enforced identically at
`tools/list` (advertised tool filtering) and `tools/call` (dispatch-time
rejection), reusing the existing `READ_ONLY_TOOLS` classification in
`lifetxt/mcp.py` rather than a new parallel list.

- `read`: only `READ_ONLY_TOOLS` are visible/callable.
- `assist`: `READ_ONLY_TOOLS` plus exactly one additional tool,
  `stage_proposal` (Unified Inbox proposal staging — writes only to the
  non-authoritative proposal store, never to `life.txt`, and already skips
  every other write guard for that reason).
- `full`: today's current behavior, unmodified.
- `--read-only` becomes equivalent to `--profile read` by normalizing both
  into one state on `McpContext` (`self.profile`, with
  `self.read_only = bool(read_only) or profile == "read"`), so every
  existing `_require_writable`-based handler guard keeps working as
  defense in depth with zero change to any handler body.
- A tool with no explicit classification is denied under `read`/`assist`
  (fail closed); tool annotations (`readOnlyHint`, etc.) are never
  consulted for this decision.

Full technical detail (traceability, component-by-component contracts,
testing strategy) is in `.kiro/specs/mcp-permission-profiles/design.md`.
This document is the reviewer-facing summary; it wins if the two drift.

## Interfaces and Contracts

- ADDED: `lifetxt mcp --profile {read,assist,full}` CLI flag.
- ADDED: `lifetxt/mcp.py::_profile_allowed_tools(profile)` — returns the
  allowed tool-name set for a profile, or `None` for `full` (no
  restriction).
- ADDED: `lifetxt/mcp.py::ASSIST_EXTRA_TOOLS` — the one-tool frozenset
  `{"stage_proposal"}`.
- MODIFIED: `lifetxt/mcp.py::McpContext.__init__`/`from_args` — gains a
  `profile` parameter, normalizes `--read-only`/`profile=None` into one of
  `"read"`/`"assist"`/`"full"`, derives `self.read_only`.
- MODIFIED: `lifetxt/mcp.py::tool_schemas()` — gains an optional `profile`
  parameter (default `None`, preserving today's unfiltered result for
  every existing no-argument caller); filters by profile when given.
- MODIFIED: `lifetxt/mcp.py::call_tool()` — rejects a disallowed tool
  before dispatching to its handler.
- REMOVED: none.

## Alternatives

- Filter only at `tools/list` or only at `tools/call`, trusting the other
  path — rejected, since it leaves a bypass a client could use by calling
  an unlisted tool directly. See requirements
  `req-mcp-permission-profiles-fail-closed`.
- A new `ProfileContext` wrapper class kept separate from `McpContext` —
  rejected as unnecessary indirection with only one implementation in
  sight; extending `McpContext` in place keeps every existing call site
  (including direct test construction) working unchanged. See
  `.kiro/specs/mcp-permission-profiles/research.md` for the full
  build-vs-adopt comparison.
- Have the CLI translate `--read-only` into `profile="read"` before
  constructing `McpContext`, leaving `McpContext` itself unaware of the
  alias — rejected, since it would leave existing direct-construction
  callers (including test code) without the new dispatch-level
  enforcement.

## Risks

- A future MCP tool added to `TOOL_HANDLERS` without an explicit
  classification decision becomes unreachable under `read`/`assist` until
  classified. This is the intended fail-closed behavior, not a defect, but
  it means a future tool-adding change should consciously decide its
  profile classification; mitigated with a code comment next to
  `TOOL_HANDLERS`.
- This is an authorization-boundary change on the project's MCP surface;
  mitigated by keeping the diff minimal (one module plus one CLI
  subparser), full test coverage of every allow/deny combination, and the
  required independent security review before merge.

## Operations Impact

None. No new runtime dependency, no new persisted state, no deployment or
service change. The active profile is a per-process, per-connection
runtime setting derived from CLI arguments.

## Compatibility Impact

- `full` (no flags, or `--profile full`) is byte-identical to today's
  unmodified default — confirmed by re-running the existing MCP test
  suite unchanged.
- `--read-only` continues to work exactly as today for every existing
  caller; it is now equivalent to `--profile read` rather than a second,
  independent mechanism.
- No existing tool's behavior changes; only which tools a given
  connection can see or call changes, and only when a constrained profile
  is explicitly requested.
