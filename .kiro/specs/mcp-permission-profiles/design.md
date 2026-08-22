# Design Document

## Overview

**Purpose**: This feature delivers a safe-by-default connection mode to
operators who expose their `lifetxt mcp` stdio server to an external AI
client (ChatGPT, Claude, Gemini, a local LLM, an IDE agent), letting them
choose how much of the tool surface that client can reach without writing a
per-client integration.

**Users**: operators running `lifetxt mcp` for an external or
lower-trust AI client will use `--profile read` or `--profile assist`;
existing operators who already trust their client fully keep `full`
(today's unchanged default).

**Impact**: `lifetxt/mcp.py` gains one dispatch-level enforcement layer
consulted by both `tools/list` and `tools/call`, reusing the classification
data it already has. No tool's behavior changes; only which tools a given
connection can see or call changes.

### Goals
- Add `--profile read|assist|full` to `lifetxt mcp`.
- Enforce the profile identically at `tools/list` and `tools/call`.
- Make `--read-only` behave exactly like `--profile read`.
- Fail closed: a tool with no explicit classification is unreachable under
  `read`/`assist`.
- Zero behavior change under `full` (today's default).

### Non-Goals
- Workspace/disclosure policy (which data is visible) — later child issue.
- Any change to `lifetxt serve`'s Web API, Remote Safe Mode, Cloud Mailbox,
  or provider-specific setup adapters.
- Widening the `assist` allowlist beyond `stage_proposal`.
- Changing what any individual tool does.

## Boundary Commitments

### This Spec Owns
- The `lifetxt mcp --profile` CLI flag and its interaction with
  `--read-only`.
- The profile-to-allowed-tools mapping (`read`, `assist`, `full`) and its
  enforcement at both `tools/list` and `tools/call`.
- The exact `assist` allowlist: every tool in `READ_ONLY_TOOLS` plus
  `stage_proposal`, and nothing else.
- English and Japanese documentation of the three profiles.

### Out of Boundary
- Which workspace sources, records, or fields are visible to a client
  (disclosure/visibility policy) — a separate, later child issue of #500.
- `lifetxt serve`'s own, separately implemented `--read-only` Web API
  behavior — untouched.
- Remote Safe Mode, Cloud Mailbox, and any provider-specific adapter —
  later phases of #500.
- Changing `stage_proposal`'s behavior, the Unified Inbox proposal
  contract, or any other tool's implementation.
- Reporting the active profile through `get_file_state` or a future AI
  doctor command — candidate for a later child issue (see Open
  Questions / Risks), not required by this spec's acceptance criteria.

### Allowed Dependencies
- Existing `READ_ONLY_TOOLS` / `DESTRUCTIVE_TOOLS` classification constants
  and the `TOOL_HANDLERS` registry in `lifetxt/mcp.py`.
- The existing `stage_proposal` tool and the Unified Inbox proposal
  contract (`cap-unified-inbox-proposals`), used unmodified.
- The existing `McpContext` / `_require_writable` mechanism.
- `argparse` for CLI flag parsing and choice validation.

### Revalidation Triggers
- Adding a new tool to `TOOL_HANDLERS` without deciding its
  `READ_ONLY_TOOLS`/`ASSIST_EXTRA_TOOLS` classification (it becomes
  unreachable under `read`/`assist` by design — a reviewer should notice
  and confirm this was a deliberate choice, not an oversight).
- Any change to what `stage_proposal` writes or to its non-authoritative
  nature (would change whether `assist` is still safe to allow by default).
- Any change to `_require_writable`'s set of callers.

## Architecture

### Existing Architecture Analysis
- `lifetxt/mcp.py` is a single-module stdio JSON-RPC server. `handle_request`
  dispatches `tools/list` to `tool_schemas()` and `tools/call` to
  `call_tool(name, arguments, context)`.
- `McpContext` is constructed once per process (`from_args`, called by
  `cmd_mcp`) and threaded through every handler call.
- `_require_writable(context)` is already the single choke point every
  mutating tool handler calls except `stage_proposal`.

This is a single-component, in-process filtering change with no new
service, external call, or data store; no architecture diagram is included
per this project's design guidance (diagrams are reserved for multi-
component or multi-service flows).

### Architecture Integration
- Selected pattern: extend the existing `McpContext`/dispatch functions in
  place; add one small allowlist-computation function reused by both
  `tools/list` and `tools/call`.
- Domain boundary: entirely inside `lifetxt/mcp.py`'s existing dispatch
  layer; no other module changes except the CLI argument definition.
- Existing patterns preserved: `_require_writable`, the `READ_ONLY_TOOLS`/
  `DESTRUCTIVE_TOOLS` classification style, `McpContext.from_args`.
- New components: one allowlist function and one enforcement check
  (see Components and Interfaces) — no new class, no new module.
- Steering compliance: reuses existing classification and the Unified
  Inbox proposal contract rather than building a parallel permission model
  (`CAPABILITY_MANAGEMENT.md` reuse-before-new-implementation).

### Technology Stack

| Layer | Choice / Version | Role in Feature | Notes |
|-------|------------------|------------------|-------|
| CLI | Python `argparse` (already in use) | Validates `--profile {read,assist,full}` and its interaction with `--read-only` | No new dependency |
| MCP dispatch | Python (`lifetxt/mcp.py`, already in use) | Computes and enforces the per-profile tool allowlist | No new dependency |

## File Structure Plan

### Modified Files
- `lifetxt/mcp.py` — add `ASSIST_EXTRA_TOOLS` (a one-tool frozenset),
  `_profile_allowed_tools(profile)`, and
  `_require_tool_allowed_for_profile(name, context)`; extend
  `McpContext.__init__`/`from_args` with a `profile` parameter and
  normalization; change `tool_schemas()` to accept an optional `profile`
  argument and filter by it; update the `tools/list` branch of
  `handle_request` to pass `context.profile`; update `call_tool` to call
  the new enforcement check before dispatching to `TOOL_HANDLERS`.
- `lifetxt/cli.py` — add `--profile` (`choices=["read", "assist", "full"]`,
  default `None`) to the `mcp` subparser; update the `--read-only` help
  text to state the alias relationship.
- `tests/test_mcp_expansion.py` — add profile enforcement test coverage
  (see Testing Strategy).
- `docs/en/ai-integration.md`, `docs/ja/ai-integration.md` — document the
  three profiles, the `assist` allowlist, and the `--read-only` relationship.
- `docs/en/cli.md`, `docs/ja/cli.md` — update the `mcp` command reference.

No new files are introduced.

## Requirements Traceability

| Requirement | Summary | Components | Interfaces | Flows |
|-------------|---------|-------------|------------|-------|
| 1.1 | `--profile` value activates that profile | CLI mcp subparser, `McpContext` | `from_args`, `__init__` | CLI startup |
| 1.2 | Invalid `--profile` value rejected | CLI mcp subparser | `argparse` `choices=` | CLI startup |
| 1.3 | No flags -> `full` | `McpContext` | `__init__` normalization | CLI startup |
| 2.1 | `read` lists only non-mutating tools | MCP Profile Enforcement | `tool_schemas(profile)` | `tools/list` |
| 2.2 | `read` rejects a call to a non-listed tool | MCP Profile Enforcement | `call_tool` -> `_require_tool_allowed_for_profile` | `tools/call` |
| 2.3 | `read` rejects an unclassified tool the same way | MCP Profile Enforcement | `_profile_allowed_tools("read")` | `tools/call` |
| 3.1 | `assist` lists read tools + `stage_proposal` | MCP Profile Enforcement | `tool_schemas(profile)`, `ASSIST_EXTRA_TOOLS` | `tools/list` |
| 3.2 | `assist` allows read tools and `stage_proposal` | MCP Profile Enforcement | `call_tool` | `tools/call` |
| 3.3 | `assist` rejects any other tool | MCP Profile Enforcement | `_require_tool_allowed_for_profile` | `tools/call` |
| 3.4 | `assist` rejects an unclassified tool the same way | MCP Profile Enforcement | `_profile_allowed_tools("assist")` | `tools/call` |
| 4.1 | `full` lists/allows every tool, unrestricted | MCP Profile Enforcement | `_profile_allowed_tools("full") is None` | `tools/list`, `tools/call` |
| 4.2 | `full` identical to today's no-flag behavior | `McpContext`, MCP Profile Enforcement | `__init__` default, `tool_schemas(None)` | CLI startup, `tools/list` |
| 5.1 | `--read-only` == `--profile read` | `McpContext` | `__init__` normalization | CLI startup |
| 5.2 | Conflicting `--read-only` + other `--profile` rejected | CLI mcp subparser, `McpContext` | `from_args` | CLI startup |
| 5.3 | Help text documents the alias | CLI mcp subparser | argparse `help=` | CLI startup |
| 6.1 | Unclassified tool denied under `read`/`assist` | MCP Profile Enforcement | `_profile_allowed_tools` | `tools/list`, `tools/call` |
| 6.2 | Annotations not used for authorization | MCP Profile Enforcement | `_profile_allowed_tools` (reads only classification constants) | `tools/call` |
| 7.1 | Existing per-tool guards stay active | `McpContext`, `_require_writable` | `read_only` derived property | `tools/call` |
| 8.1 | Profiles documented bilingually | Documentation | `docs/en\|ja/ai-integration.md`, `docs/en\|ja/cli.md` | n/a |

## Components and Interfaces

| Component | Domain/Layer | Intent | Req Coverage | Key Dependencies (P0/P1) | Contracts |
|-----------|---------------|--------|---------------|---------------------------|-----------|
| MCP Profile Enforcement | `lifetxt/mcp.py` dispatch | Compute and enforce the per-profile tool allowlist at `tools/list` and `tools/call` | 2.*, 3.*, 4.*, 6.* | `TOOL_HANDLERS`, `READ_ONLY_TOOLS` (P0) | Service |
| `McpContext` profile/read_only | `lifetxt/mcp.py` context | Normalize `--profile`/`--read-only` into one authorization state | 1.*, 4.2, 5.*, 7.1 | argparse (P1) | Service |
| CLI `mcp` subparser | `lifetxt/cli.py` | Parse and validate `--profile`/`--read-only` before construction | 1.2, 5.2, 5.3 | argparse (P0) | Service |

### MCP Profile Enforcement

| Field | Detail |
|-------|--------|
| Intent | Restrict which MCP tools are advertised and callable based on the active permission profile |
| Requirements | 2.1, 2.2, 2.3, 3.1, 3.2, 3.3, 3.4, 4.1, 4.2, 6.1, 6.2 |

**Responsibilities & Constraints**
- Computes the allowed tool-name set for a profile; `None` means "no
  restriction" (`full`).
- Applied identically at `tools/list` (filtering the schema list) and
  `tools/call` (rejecting disallowed calls), so a client cannot bypass the
  restriction by calling a tool it was never shown.
- Does not alter any tool's behavior, only its reachability.
- Treats a tool with no explicit classification as "not allowed" under
  `read`/`assist` (fail closed), never as "allowed by default."
- Never reads a tool's MCP annotations (`readOnlyHint`, etc.) to decide
  reachability.

**Dependencies**
- Inbound: CLI `mcp` subparser, via `McpContext.from_args` (P0)
- Outbound: `TOOL_HANDLERS` registry, `READ_ONLY_TOOLS` classification (P0)
- Outbound: the existing `stage_proposal` tool, referenced by name only,
  via `ASSIST_EXTRA_TOOLS` (P1)

**Contracts**: Service [x] / API [ ] / Event [ ] / Batch [ ] / State [ ]

##### Service Interface
```python
def _profile_allowed_tools(profile: str | None) -> "frozenset[str] | None":
    """Tool names allowed under profile. None means no restriction (full)."""

def _require_tool_allowed_for_profile(name: str, context: "McpContext") -> None:
    """Raise ValueError if name is not allowed under context.profile."""

def tool_schemas(profile: "str | None" = None) -> list:
    """Annotated tool schemas, filtered to profile's allowlist when profile
    is 'read' or 'assist'. profile=None (default) returns every registered
    tool, unchanged from today, for callers that need the full registry
    (e.g. the CLI/Web/MCP capability drift gate)."""
```
- Preconditions: `profile` is one of `None`, `"read"`, `"assist"`, `"full"`
  (already validated by `McpContext.__init__`).
- Postconditions: `call_tool` never dispatches to a handler for a
  disallowed tool; `tools/list` never advertises a disallowed tool.
- Invariants: `_profile_allowed_tools("full") is None` always;
  `_profile_allowed_tools("read")` is always a subset of
  `_profile_allowed_tools("assist")`.

**Implementation Notes**
- Integration: `call_tool` calls `_require_tool_allowed_for_profile` right
  after its existing "unknown tool" check and before dispatching to
  `TOOL_HANDLERS[name]`.
- Validation: argparse `choices=["read", "assist", "full"]` on `--profile`
  satisfies requirement 1.2 without additional code.
- Risks: a future tool added to `TOOL_HANDLERS` without a classification
  decision becomes unreachable under `read`/`assist` until classified —
  intended (requirement 6), documented with a code comment next to
  `TOOL_HANDLERS` so a future author does not mistake it for a bug.

### `McpContext` Profile / Read-Only Normalization

| Field | Detail |
|-------|--------|
| Intent | Normalize `--profile` and `--read-only` into one authorization state (`self.profile`, `self.read_only`) |
| Requirements | 1.1, 1.3, 4.2, 5.1, 7.1 |

**Responsibilities & Constraints**
- `profile=None` (not given) normalizes to `"read"` if `read_only` is
  truthy, else `"full"` — preserves today's default and the existing
  `--read-only` behavior with no caller changes required.
- Validates `profile` is one of `"read"`, `"assist"`, `"full"`.
- Derives `self.read_only = bool(read_only) or profile == "read"`, so
  every existing `_require_writable` call site keeps working unchanged
  whenever the active profile is `read` (defense in depth, requirement 7).

**Dependencies**
- Inbound: `McpContext.from_args` (CLI), direct construction (tests / any
  future non-CLI caller)
- Outbound: none new

**Contracts**: Service [x] / API [ ] / Event [ ] / Batch [ ] / State [ ]

##### Service Interface
```python
class McpContext:
    def __init__(self, ..., read_only: bool = False,
                 profile: "str | None" = None, ...) -> None:
        """profile=None normalizes to 'read' (if read_only) or 'full'."""
```
- Preconditions: `profile`, if given, is one of `"read"`, `"assist"`,
  `"full"`.
- Postconditions: `self.profile` is always one of the three valid values;
  `self.read_only` is `True` whenever `self.profile == "read"`.
- Invariants: constructing with `read_only=True` and no `profile` is
  observably identical, from this point forward, to constructing with
  `profile="read"`.

**Implementation Notes**
- Integration: `McpContext.from_args` rejects (raises `ValueError`) a
  request that supplies both `read_only=True` and a `profile` other than
  `"read"`, before constructing the context — satisfies requirement 5.2.
- Risks: none beyond what is already covered by existing tests exercising
  `read_only=True` construction directly, which continue to pass unchanged.

### CLI `mcp` Subparser

| Field | Detail |
|-------|--------|
| Intent | Parse and validate `--profile`/`--read-only` before `McpContext` is constructed |
| Requirements | 1.2, 5.2, 5.3 |

**Responsibilities & Constraints**
- Adds `--profile` with `choices=["read", "assist", "full"]`, default
  `None`.
- Updates `--read-only`'s help text to state it is equivalent to
  `--profile read`.

**Contracts**: Service [x] / API [ ] / Event [ ] / Batch [ ] / State [ ]

**Implementation Notes**
- Integration: no new subparser; this is an addition to the existing `mcp`
  subparser in `lifetxt/cli.py`.
- Validation: argparse itself rejects an invalid `--profile` value with a
  standard "invalid choice" error and nonzero exit, before `command_mcp`
  ever runs.

## Data Models

None. The active profile is a per-process, per-connection runtime setting
derived from CLI arguments; nothing is persisted.

## Error Handling

### Error Strategy
- **Invalid `--profile` value**: argparse rejects it at parse time with a
  standard "invalid choice" error; the process exits nonzero before the
  server starts.
- **Conflicting `--read-only` + `--profile` other than `read`**:
  `McpContext.from_args` raises `ValueError` naming the conflict, surfaced
  by `cmd_mcp`'s existing top-level error handling before the stdio loop
  starts.
- **Disallowed `tools/call` under a constrained profile**: `call_tool`
  raises `ValueError` naming the tool and the active profile; this is
  caught by `handle_request`'s existing exception handling and returned as
  a JSON-RPC error response — the same mechanism every other tool error
  already uses, unchanged.

### Monitoring
No new logging/monitoring is introduced; JSON-RPC error responses already
propagate to the calling client, which is the intended observability
surface for a tool rejection.

## Testing Strategy

- **Unit Tests** (`tests/test_mcp_expansion.py`, new
  `McpPermissionProfileTests` class):
  - `--profile read`/`assist`/`full` each produce the correct
    `McpContext.profile`/`.read_only`.
  - `tool_schemas("read")` returns exactly `READ_ONLY_TOOLS`;
    `tool_schemas("assist")` returns `READ_ONLY_TOOLS | {"stage_proposal"}`;
    `tool_schemas(None)` and `tool_schemas("full")` return everything,
    identical to today's `tool_schemas()`.
  - `call_tool` under `read`: a read tool succeeds; `stage_proposal`,
    `create_item`, and a synthetic never-classified tool name are all
    denied.
  - `call_tool` under `assist`: a read tool succeeds; `stage_proposal`
    succeeds and actually stages a proposal; `create_item`, a
    `DESTRUCTIVE_TOOLS` member, and a synthetic never-classified tool name
    are all denied.
  - `--read-only` and `--profile read` produce identical `McpContext`
    state (equivalence test).
  - `--read-only` combined with `--profile assist`/`full` is rejected with
    a clear error; `--read-only` combined with `--profile read` (the
    non-conflicting redundant case) is accepted.
- **Integration Tests**:
  - A fake stdio session issuing `tools/list` then `tools/call` under each
    profile, confirming the listed set matches what is actually callable.
  - Full existing `tests/test_mcp_expansion.py` and
    `tests/test_surface_runtime.py` suites re-run unmodified to confirm no
    regression to the capability-drift gate.
- **Live verification** (per this repository's established practice for
  security-sensitive changes): a real `lifetxt mcp --profile read` /
  `--profile assist` / `--profile full` stdio session driven with real
  JSON-RPC lines, confirming `tools/list` and `tools/call` agree in each
  mode against a real workspace fixture.

## Security Considerations

- Enforcement is allowlist-based (fail closed), not a denylist: a tool
  added later is unreachable under `read`/`assist` until a person
  deliberately classifies it. This directly satisfies requirement 6 and
  #500's fail-closed principle.
- Tool annotations (`readOnlyHint`, etc.) remain descriptive only;
  `_profile_allowed_tools` never reads them — satisfies requirement 6.2 and
  #500's explicit "do not treat MCP annotations as authorization controls"
  principle.
- Defense in depth is preserved: `_require_writable` still blocks every
  handler that calls it whenever `self.read_only` is `True`, independent
  of the new dispatch-level check — satisfies requirement 7.
- `assist`'s only allowed write, `stage_proposal`, writes solely to the
  non-authoritative Unified Inbox proposal store; it cannot mutate
  `life.txt` directly (already true today, unmodified by this feature),
  which is why `assist` is safe to allow without becoming a second, broader
  authorization tier.
- This design will additionally go through this repository's standard
  `/security-review` pass before merge, per the change's High assurance
  level.

## Open Questions / Risks

- Whether `get_file_state` (or a future `lifetxt ai doctor`-style command)
  should also report the active profile for client/operator self-
  inspection is deferred to a later child issue; it is not required by
  this spec's acceptance criteria and is not implemented here.
