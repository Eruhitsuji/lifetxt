# Design: --no-open-world MCP restriction

## Problem

#543's Disclosure Policy investigation found that `--profile read`/`--profile
assist` currently conflate two independent properties: "may read local
workspace data" and "may open outbound network connections to configured
remote profiles." The `remote_*` tools (`remote_test_connection`,
`remote_list_resources`, `remote_get_resource`) are `OPEN_WORLD_TOOLS`
members *and* `READ_ONLY_TOOLS` members simultaneously, so they remain
callable under both constrained profiles today. Their data is already
correctly gated server-side by the remote server's own Remote Safe Mode
policy, but there is no way to run `lifetxt mcp --profile read` with a
guarantee that the connected client cannot reach the network at all.

## Approach

Add one new, independent, opt-in restriction layered on top of the existing
profile allowlist, rather than a new profile enum value or a reclassification
of existing tools.

### `McpContext`

```python
class McpContext:
    def __init__(self, ..., no_open_world=False, ...):
        ...
        self.no_open_world = bool(no_open_world)
```

No conflict validation with `profile`/`read_only` -- the two are fully
orthogonal by design (a `--no-open-world` client can be `read`, `assist`, or
`full`).

### Enforcement at `tools/call`

```python
def _require_tool_allowed_for_profile(name, context):
    if getattr(context, "no_open_world", False) and name in OPEN_WORLD_TOOLS:
        raise ValueError(
            "Tool '%s' is an open-world tool (makes an outbound network "
            "call) and is disabled by --no-open-world." % name
        )
    profile = getattr(context, "profile", None)
    allowed = _profile_allowed_tools(profile)
    if allowed is not None and name not in allowed:
        raise ValueError(...)
```

The `no_open_world` check runs first: since `remote_*` tools are already
`READ_ONLY_TOOLS` members, the profile-allowlist check alone would never deny
them under `read`/`assist` -- only this new check does, so it must run
unconditionally regardless of what the profile check would have decided, and
must produce its own accurate message.

### Enforcement at `tools/list`

```python
def filter_tool_schemas_for_profile(schemas, profile, no_open_world=False):
    allowed = _profile_allowed_tools(profile)
    result = schemas if allowed is None else [...]
    if no_open_world:
        result = [s for s in result if s.get("name") not in OPEN_WORLD_TOOLS]
    return result
```

`handle_request`'s `tools/list` branch passes `getattr(context,
"no_open_world", False)` as the new third argument. The default value
(`False`) is chosen so this is a strictly additive signature change -- no
other caller in the codebase calls `filter_tool_schemas_for_profile` (confirmed
by search; `mcp.py`'s `handle_request` is the sole caller), so no other
module needed updating, but the default still protects any future caller
that omits the new parameter.

### CLI wiring

```python
mcp.add_argument("--no-open-world", action="store_true", help=...)
```

`McpContext.from_args` reads `getattr(args, "no_open_world", False)` and
passes it through, following the exact pattern `--read-only`/`--profile`
already use.

## Why not remove `remote_*` from `READ_ONLY_TOOLS`/`OPEN_WORLD_TOOLS`

Both classifications remain correct and meaningful on their own terms:
`READ_ONLY_TOOLS` describes that these tools never mutate `life.txt` locally
(true, and worth preserving for clients that only care about local write
safety), and `OPEN_WORLD_TOOLS` describes that they make a real outbound call
(also true). Removing them from either set to simulate the new restriction
would corrupt an existing, independently useful classification for a
narrower purpose this new flag already serves cleanly.

## Documentation corrections found during this change

While updating `docs/en/ai-integration.md` section 6, two pre-existing
inaccuracies were found and corrected as part of the same edit (not a
separate task, since both sentences live in the exact paragraph being
updated):

1. "The server is local and stdio-only: no network listener, no telemetry,
   no outbound calls" -- contradicted by the `remote_*` tools, which have
   made real outbound HTTPS calls since #243 shipped. Corrected to name the
   exception and point to `--no-open-world`.
2. "Permission profiles control which tools are reachable. They do not yet
   control which workspace sources or records are visible to a client --
   that is a separate, not-yet-implemented workspace/disclosure layer." --
   contradicted by the AI-safe named-workspace pattern (#509), which *is*
   the disclosure layer and has been documented immediately below this
   paragraph (section 7) since #509 shipped. Corrected per #543's own
   finding (section B): workspace/source selection at connection time is,
   and should remain, the sole local MCP disclosure boundary.

## Testing strategy

Mirrors `McpPermissionProfileTests`' own structure (`tests/test_mcp_expansion.py`):
selection/defaulting, fail-closed enforcement at both `tools/list` and
`tools/call`, combined with each of `read`/`assist`/`full`, and confirmation
that a non-`OPEN_WORLD_TOOLS` `READ_ONLY_TOOLS` member (`remote_list_profiles`)
is unaffected. New class: `McpNoOpenWorldTests`.

## Security review focus

- Confirm `no_open_world` cannot be bypassed by any code path that calls a
  tool handler directly without going through `call_tool()`/
  `_require_tool_allowed_for_profile()`.
- Confirm the restriction is enforced identically at `tools/list` (schema
  advertisement) and `tools/call` (dispatch), matching #502's own precedent
  that a client must not be able to reach a tool it cannot see, or vice
  versa.
- Confirm no other `OPEN_WORLD_TOOLS` member could be added in the future
  without automatically inheriting this restriction (the check is by set
  membership, not by an enumerated tool-name list, so it fails closed for
  any future addition to `OPEN_WORLD_TOOLS`).
