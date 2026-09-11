# Design: remote-historical-evidence-read (#728)

## Shape

A new module, `lifetxt/remote_historical.py`, exposes exactly one function,
`read_historical_resource(paths, config, principal, params)`, called by a
new FastAPI route `GET /api/remote/v1/historical` in `lifetxt/remote_web.py`
(protocol-version-2-gated, matching `/api/remote/v1/resources/*`).

## Reuse, not reimplementation

- Git input: `lifetxt.historical_temporal.read_historical_snapshot`
  (unmodified). This module never calls `git` itself.
- Authorization primitives: `lifetxt.remote_access.require_scope`,
  `can_access`, `redact_remote_value`, `append_audit` (all unmodified).
- Access-tuple derivation: `lifetxt.remote_backend._access_for_item`
  (reused cross-module, matching this project's established precedent of
  importing a sibling module's private helper rather than duplicating it,
  e.g. `mcp.py` importing `webapp._subgraph`).
- Source revision reporting: `lifetxt.remote_backend.source_revision`.

## Two independent opt-ins

1. `remote.historical_reads_enabled` (config, default `false`).
2. An explicit `historical` scope on the principal. `require_scope` already
   treats scopes as an explicit allow-list per principal (a role's implicit
   scopes plus any additional configured scopes); `historical` is never
   added implicitly by any built-in role, so an operator must opt every
   principal in individually. This mirrors `cap-mcp-permission-profiles`'s
   `read`/`assist`/`full` precedent of never inferring a broader grant from
   a narrower one.

Both checks happen before any Git subprocess call.

## Conjunctive authorization

For each historical item:

1. Compute its historical access tuple via `_access_for_item(item,
   historical_id_index)` (the historical snapshot's own id index, so a
   historical `ticket_event`/`time_entry`/etc. Note still inherits its
   historical parent's tuple, matching current-state behavior).
2. `can_access(principal, **historical_access)` must be `True`, or the
   record is denied.
3. If a record with the same ID exists in the *current* live workspace
   (read once per request via the existing `webapp.read_life_inputs`, best
   effort -- a failure to read current state never blocks or widens a
   historical result, it simply means no current-side check applies for
   that ID), its own access tuple must also grant access.

Because both checks are simple booleans, "the more restrictive of the two
wins" (#727 Section 7) reduces to a plain AND -- no separate conflict-
resolution mechanism is needed.

## Bounds

- `read_historical_snapshot` already enforces `MAX_HISTORICAL_FILE_BYTES`,
  `MAX_HISTORICAL_TOTAL_BYTES`, `MAX_HISTORY_COMMITS`, and
  `GIT_TIMEOUT_SECONDS` per Git subprocess call.
- This module adds one further, server-level bound: `limit` (default 200,
  maximum 1000), applied after the conjunctive access filter, matching the
  existing `tickets` resource's own bounded-pagination precedent (though
  cursor-based pagination itself is explicitly out of scope here, per
  #727 Section 2's "no history-browsing endpoint" decision -- `limit` only
  truncates one already-selected commit's item set).

## Fail-closed, never falls back

`read_historical_snapshot` raises `ValueError` for every failure mode this
issue names (no Git repository, unresolvable revision, no tracked path at
the selected commit, malformed `--as-of`). That `ValueError` is caught once
and turned into `RemoteAccessError("REMOTE_HISTORICAL_UNAVAILABLE", ..., 422)`
-- the request fails; nothing is served from the current working tree.

## Audit contract

`_audit()` builds one `OrderedDict` event (`event`, `principal_id`,
`principal_role`, `selector`, `classification`, plus `denial_reason` or the
served-path counters) and passes it to the existing `append_audit(config,
event)`, which already applies `redact_remote_value` before writing and is
a no-op unless `remote.audit_log` is configured. No raw item content, no
local paths, and no secret-shaped values are ever placed in the event by
construction (only counts, IDs of principals, and Git-internal metadata
such as the resolved commit SHA are included).

## Why a dedicated route instead of the generic `_BUILDERS` dispatch

`remote_backend.read_resource()`'s generic dispatch (`_BUILDERS`) is
item-driven: it always reads the *current* workspace via
`webapp.read_life_inputs`, then hands the result to a resource-specific
builder. Historical reads need a structurally different input path (Git
subprocess calls resolving a revision/as-of cutoff first), a different
bounds policy, and a second, conjunctive access check against the current
workspace. Forcing this into the same dispatch would either weaken the
existing resources' contract or require `_BUILDERS` entries to accept a
Git selector they have no reason to understand. A dedicated route keeps the
generic resource dispatch untouched while still reusing every actual policy
primitive it relies on.
