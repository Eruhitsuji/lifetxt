# Research & Design Decisions

## Summary
- **Feature**: `remote-pagination`
- **Discovery Scope**: Extension (light discovery)
- **Key Findings**:
  - `ticket_list()` (`lifetxt/tickets.py:232-241`) already sorts its output deterministically by `id` before `_resource_tickets()` applies any further filtering — the one prerequisite cursor pagination needs already exists for tickets specifically.
  - `_limit()` (`remote_backend.py:169-171`) hardcodes `default=None` for its `_int(...)` call, which is exactly why omitting `limit` returns everything today. Reusing `_limit()` as-is for tickets is not possible without changing its default for every other resource that calls it (`items`, `links`, `agenda`) — those must keep today's unbounded-when-omitted behavior per the issue's explicit out-of-scope. `_resource_tickets()` must call `_int()` directly with its own default instead of going through `_limit()`.
  - `read_resource()` (`remote_backend.py:362-382`) computes `source_revision(paths)` *after* calling the resource builder; both are cheap/independent, so computing it once up front and reusing it for both the `since_revision` check and the response's `revision` field is a pure reordering, not a behavior change for existing callers.
  - Both routes that can reach the `tickets` builder (`remote_web.py`'s dedicated `/api/remote/v1/tickets` and the generic `/api/remote/v1/resources/tickets`) call `read_resource()`. Putting the `since_revision` check inside `read_resource()`, gated on `name == "tickets"`, is the only way to cover both routes without duplicating the check in two route handlers.

## Research Log

### Where Pagination State Lives
- **Context**: Cursor pagination needs no server-side session/state — is that true here?
- **Findings**: Yes. Because `ticket_list()`'s sort is deterministic and cursor comparison is a pure string comparison against the already-filtered, already-visible row set, "the next page" is fully computable from `(cursor, limit, principal, current file contents)` alone. No stored pagination state, no server-side cursor token to invalidate or expire.
- **Implications**: The cursor value itself is just a ticket ID string — no opaque token encoding/decoding needed.

### Why the Consistency Check Belongs in `read_resource`, Not the Route
- **Context**: `since_revision` must apply to both `tickets` routes.
- **Findings**: `remote_web.py`'s `remote_tickets` and `remote_resource` route handlers are two separate FastAPI endpoint functions; both delegate to `read_resource()`. There is no shared "tickets-specific" layer between them today other than `read_resource()` itself and `_resource_tickets()`.
- **Implications**: The check goes in `read_resource()`, gated by `name == "tickets"`, rather than in either route handler or by adding a new shared helper the two routes would both need to remember to call.

## Architecture Pattern Evaluation

| Option | Description | Strengths | Risks / Limitations | Notes |
|--------|-------------|-----------|---------------------|-------|
| Extend `_resource_tickets` + `read_resource` in place | Add cursor/default-size/next_cursor/has_more to the existing builder; add the `since_revision` check to the existing dispatcher | No new module, no new route, both existing routes automatically covered | `read_resource` gains one resource-specific branch | Selected |
| New dedicated `/api/remote/v1/tickets/page` route | A new endpoint just for paginated access | Keeps the plain `tickets` response "simple" | Third route to keep in sync with the other two; splits one resource's behavior across two contracts for no functional reason | Rejected — the issue's own acceptance criteria describe extending the *existing* two routes, not adding a third |
| Opaque cursor token (e.g., base64-encoded offset+revision) | Cursor carries more than just the ID | Could embed revision-pinning directly in the cursor | Adds encode/decode/versioning surface for no current requirement; the plain ticket-ID string is already sufficient given the existing deterministic sort | Rejected per Simplification — the smallest design that satisfies the requirements |

## Design Decisions

### Decision: `_resource_tickets` calls `_int()` directly instead of `_limit()`
- **Context**: The default page size must change for `tickets` only; `_limit()` is shared by four other resource builders that must not change.
- **Alternatives Considered**: 1) Add a `default=` parameter to `_limit()` itself, defaulting to `None` so other callers are unaffected, and have `_resource_tickets` pass its own default. 2) Have `_resource_tickets` call `_int()` directly, bypassing `_limit()` entirely for this one resource.
- **Selected Approach**: Option 2.
- **Rationale**: `_limit()`'s entire body is a one-line wrapper around `_int()` plus slicing; calling `_int()` directly in `_resource_tickets()` (which already needs custom slicing logic for cursor/`next_cursor`/`has_more` anyway) is no more code than threading a new parameter through `_limit()` for a single caller.
- **Trade-offs**: None meaningful.
- **Follow-up**: None.

### Decision: cursor is the plain ticket-ID string, not an opaque token
- **Context**: See Architecture Pattern Evaluation.
- **Rationale**: `ticket_list()`'s sort is already by ID; "give me everything after ID X" is directly expressible without encoding anything. Simplification lens: no abstraction layer with only one implementation and no foreseeable second.
- **Trade-offs**: A cursor is human-readable and technically "guessable," but it grants no more access than the principal's own permission filtering already allows — a cursor for a ticket ID a principal cannot see is inert (that ID's neighbors in sort order are still filtered by `_visible_items` before pagination runs).
- **Follow-up**: None.

## Risks & Mitigations
- Risk: A concurrent write reorders/removes a ticket between two of a client's paginated requests, causing a gap or duplicate even without a revision mismatch being detected (e.g., a ticket is deleted, shifting no IDs but changing what "after cursor X" contains). — Mitigation: `since_revision` exists precisely to let a caller that cares about this detect *any* revision change between pages and restart; callers that omit it accept best-effort snapshot consistency, matching today's default (no consistency guarantee at all).
- Risk: Existing callers of `/api/remote/v1/tickets` that rely on receiving every ticket in one response now silently get a truncated page. — Mitigation: named explicitly as a compatibility-impacting change in the issue and PR description; `has_more`/`next_cursor` make the truncation observable rather than silent.

## References
- `lifetxt/remote_backend.py`, `lifetxt/remote_web.py`, `lifetxt/tickets.py`.
- GitHub Issue #124 — task-level scope, out-of-scope, and acceptance criteria.
