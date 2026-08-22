# Research & Design Decisions

## Summary
- **Feature**: `mcp-permission-profiles`
- **Discovery Scope**: Extension (existing `lifetxt/mcp.py` stdio MCP server)
- **Key Findings**:
  - `lifetxt/mcp.py` already maintains `READ_ONLY_TOOLS` and `DESTRUCTIVE_TOOLS`
    frozensets, but only for MCP annotation purposes (`readOnlyHint`,
    `destructiveHint`); nothing enforces them today.
  - The only real write guard today is `McpContext.read_only`, checked by a
    shared helper (`_require_writable`) that every mutating tool handler
    calls except one: `stage_proposal`.
  - `stage_proposal` was already implemented to write only to the
    non-authoritative Unified Inbox proposal store, never to `life.txt`,
    and deliberately does not call `_require_writable` — it is already
    exactly the "safe write" this feature's `assist` profile needs, with
    no code change required to the tool itself.
  - `tools/list` currently calls `tool_schemas()` with no context, so the
    advertised tool set cannot vary by connection today; this is the one
    call site that must gain profile awareness.
  - Three other modules define their own unrelated local functions named
    `tool_schemas` (`remote_contracts_v6.py`, `surface_runtime.py`,
    `ticket_project_surfaces.py`); none of them call
    `lifetxt.mcp.tool_schemas`, so changing its signature only affects
    `lifetxt/mcp.py` itself.

## Research Log

### Existing write-enforcement mechanism
- **Context**: Requirement 7 requires that existing per-tool write guards
  stay in place, unmodified, as defense in depth.
- **Sources Consulted**: `lifetxt/mcp.py` (`McpContext.__init__`,
  `_require_writable`, every `_tool_*` handler).
- **Findings**: every write-tool handler in `TOOL_HANDLERS` except
  `stage_proposal` calls `_require_writable(context)` first, which raises
  when `context.read_only` is `True`. This is a single, already-shared
  choke point, not scattered ad hoc checks.
- **Implications**: keeping `context.read_only` as-is and deriving it from
  the new `profile` (`True` whenever `profile == "read"`) gets requirement
  7 for free, with zero change to any handler body.

### `stage_proposal` as the `assist` allowlist candidate
- **Context**: the repository owner confirmed `assist` should allow exactly
  one write tool, `stage_proposal`, and nothing else.
- **Sources Consulted**: `lifetxt/mcp.py::_tool_stage_proposal`,
  `lifetxt/inbox.py::stage_create`, `cap-unified-inbox-proposals` in
  `.ai/project/CAPABILITIES.yml`.
- **Findings**: `stage_proposal` already writes only to the proposal store
  and never calls `_require_writable`; a person must separately accept a
  proposal (a different, already-`DESTRUCTIVE_TOOLS`-free path not exposed
  to MCP at all today) before it becomes a `life.txt` record.
- **Implications**: no change to `stage_proposal` or the proposal contract
  is needed. `assist`'s allowlist is purely an addition to the new
  profile-dispatch filter, not a change to what the tool does.

### `tools/list` context plumbing
- **Context**: requirement 2.1/3.1 require the advertised tool list itself
  to change per profile, not only call-time rejection.
- **Sources Consulted**: `lifetxt/mcp.py::handle_request`,
  `lifetxt/mcp.py::tool_schemas`.
- **Findings**: `handle_request` already holds `context` in scope at the
  `tools/list` branch; only the call `tool_schemas()` itself needs an
  optional profile argument.
- **Implications**: `tool_schemas(profile=None)` keeps every existing
  no-argument caller (notably the CLI/Web/MCP capability-drift gate in
  `tests/test_surface_runtime.py`, which needs the *full* registry
  regardless of any one server's active profile) byte-identical, while
  `handle_request` passes `context.profile` at the one call site that
  actually serves a live connection.

## Architecture Pattern Evaluation

| Option | Description | Strengths | Risks / Limitations | Notes |
|--------|-------------|-----------|---------------------|-------|
| Extend `McpContext` with a `profile` attribute, derive `read_only` from it | Single source of truth for both old and new enforcement | Minimal diff, no new class, every existing call site keeps working | `read_only` becomes a derived property rather than a fully independent flag | Selected |
| New parallel `ProfileContext` wrapper around `McpContext` | Keeps `McpContext` untouched | — | Two objects to keep in sync at every call site; existing tests would need a second context type | Rejected — adds an abstraction layer with no second implementation in sight (simplification lens) |
| Denylist unclassified tools only under `assist`, allowlist under `read` | Slightly less code | — | Contradicts requirement 6 (fail closed for *any* unclassified tool, not just under `read`) | Rejected |

## Design Decisions

### Decision: One dispatch-level filter reused by both `tools/list` and `tools/call`
- **Context**: requirement 6 requires identical fail-closed behavior at
  both the advertisement and execution points, so a client cannot bypass
  the profile by calling a tool it was never shown.
- **Alternatives Considered**:
  1. Filter only at `tools/list`, trusting well-behaved clients not to call
     an unlisted tool.
  2. Filter only at `tools/call`, leaving `tools/list` showing everything.
  3. One shared allowlist function (`_profile_allowed_tools`) consulted by
     both paths.
- **Selected Approach**: Option 3. `tool_schemas(profile)` and
  `call_tool(name, arguments, context)` both consult
  `_profile_allowed_tools(context.profile)`.
- **Rationale**: options 1 and 2 each leave one path unenforced, which
  directly contradicts requirement 6's "even if the client calls it
  directly without listing first" wording.
- **Trade-offs**: none of note; the shared function is a single small
  addition.
- **Follow-up**: none.

### Decision: `--read-only` normalizes into `profile` inside `McpContext.__init__`, not in the CLI layer
- **Context**: requirement 5 requires `--read-only` and `--profile read` to
  produce identical enforcement, from both the CLI and from direct
  programmatic construction (existing tests construct `McpContext`
  directly with `read_only=True` and no `profile`).
- **Alternatives Considered**:
  1. Have the CLI translate `--read-only` into `profile="read"` before
     constructing `McpContext`, leaving `McpContext` itself unaware of the
     alias.
  2. Normalize inside `McpContext.__init__` so any caller (CLI or direct
     construction) gets the same result.
- **Selected Approach**: Option 2.
- **Rationale**: option 1 would leave existing direct-construction test
  code and any future non-CLI caller unprotected by the new dispatch-level
  enforcement, silently reintroducing the "read_only bool with no
  tools/list/tools/call enforcement" gap this feature exists to close.
- **Trade-offs**: `McpContext.__init__` gains one small normalization
  branch; considered acceptable given the safety benefit.
- **Follow-up**: none.

### The real dispatch path is a multi-layer monkeypatch chain
- **Context**: light discovery (before implementation) only looked at
  `lifetxt/mcp.py` in isolation; it missed that `lifetxt/__init__.py`
  unconditionally wraps `mcp.call_tool`, `mcp.tool_schemas`, and
  `mcp.handle_request` at import time from four other modules
  (`surface_runtime.py`, `surface_runtime_compat.py`,
  `remote_contracts_v6.py`, `ticket_project_surfaces.py`), each adding its
  own tools and re-wrapping whatever was previously bound.
- **Sources Consulted**: `lifetxt/__init__.py` install order;
  `surface_runtime.py::_patch_mcp`,
  `surface_runtime_compat.py::_scope_mcp_contract_to_jsonrpc`,
  `remote_contracts_v6.py::_patch_mcp`,
  `ticket_project_surfaces.py`; live tracing of the actual bound functions
  (`inspect.getsource`, closure-cell inspection) plus end-to-end
  `handle_request` calls with expected revisions supplied.
- **Findings**: giving `tool_schemas()` a `profile` parameter breaks
  immediately, because every wrapper layer re-defines it with zero
  parameters and calls the previous layer with zero arguments --
  `handle_request` calling the live (fully wrapped) name with one
  positional argument raises `TypeError` before reaching any of my code.
  `call_tool`'s signature is unchanged by every layer, so my dispatch-level
  check does get reached, but only after several layers of pass-through
  (and, for revision-tracked tools such as `create_item`, only once a
  correct `expected_file_hash` clears an earlier precondition check in
  `surface_runtime.py`'s own wrapper -- confirmed by live testing with and
  without a correct precondition, not assumed).
- **Implications**: keep `tool_schemas()` itself completely unchanged
  (zero-arg, byte-identical to before this feature). Add a separate
  `filter_tool_schemas_for_profile(schemas, profile)` function and call it
  in `handle_request`'s own `tools/list` branch on the *result* of calling
  `tool_schemas()` (whatever that name currently resolves to, including
  every monkeypatch-added tool), rather than pushing a profile parameter
  down into `tool_schemas()`'s own signature. `READ_ONLY_TOOLS` is read at
  call time from the same module global every extension module extends in
  place, so filtering still covers tools added by any of the four wrapper
  modules with no change to any of them.

## Risks & Mitigations
- A future tool added to `TOOL_HANDLERS` without an explicit classification
  becomes unreachable under `read`/`assist` — intended (requirement 6), but
  worth a code comment next to `TOOL_HANDLERS` so it is not mistaken for a
  bug during a later change.
- Documentation drift between `docs/en/ai-integration.md` and
  `docs/ja/ai-integration.md` — mitigated by writing both in the same task,
  matching this repository's established parity practice.

## References
- GitHub Issue #502 (this feature's task contract)
- GitHub Issue #500 (parent epic, Section 1 "MCP permission profiles" and
  Section 17 Phase 1)
- `.ai/project/CAPABILITIES.yml` — `cap-unified-inbox-proposals`
