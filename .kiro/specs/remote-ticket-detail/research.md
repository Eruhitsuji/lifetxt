# Research & Design Decisions

## Summary
- **Feature**: `remote-ticket-detail`
- **Discovery Scope**: Extension (light discovery)
- **Key Findings**:
  - `tickets.ticket_view(item, config, items=None, key="id")` already exists and returns exactly the shape this feature needs (summary, fields, relations, incoming_links, est/elapsed/resolution) — no new domain logic required, only a new resource builder wiring it into `remote_backend.py`.
  - `remote_backend.read_resource()` already passes the *permission-filtered* `visible` item set into whichever builder runs (`_BUILDERS[name](visible, config, params)`). Passing that same `visible` list as `ticket_view()`'s `items=` parameter means relations/incoming_links are automatically computed only against visible tickets — Requirement 1.2 falls out of existing behavior, not new code.
  - `REMOTE_TICKET_NOT_FOUND` (`remote_ticket_write_core.py:143-148`) is the existing error code for "no such ticket" on the write side. Reusing it here (rather than inventing a new code) keeps one meaning per error code across the read and write surfaces.
  - `tickets.iter_tickets(items)` + `tickets.ticket_id_of(item, key)` + `tickets.id_key(config)` are the existing primitives for "find the one ticket item with this ID" — the same primitives `next_ticket_id()` already uses elsewhere in the same module.

## Research Log

### Not-Found Indistinguishability
- **Context**: Requirement 2 needs "does not exist" and "exists but invisible" to produce byte-identical responses.
- **Findings**: Because the lookup loop only ever iterates the already-permission-filtered `visible` list (not the full unfiltered `items`), a ticket the principal cannot see is already absent from that list by the time the lookup runs — there is no separate "found but not visible" branch to accidentally handle differently. The two cases collapse into one code path by construction, not by a manual equality check between two error branches.
- **Implications**: No special-casing needed; correctness follows directly from reusing `read_resource()`'s existing filter-before-dispatch order.

## Architecture Pattern Evaluation

| Option | Description | Strengths | Risks / Limitations | Notes |
|--------|-------------|-----------|---------------------|-------|
| New `_resource_ticket_detail` builder in `remote_backend.py`, reusing `ticket_view()` | One new function, no new module | Matches every existing resource builder's shape | None | Selected |
| Expose `ticket_view()` output as an extra field on the existing `tickets` list resource per row | Avoids a new resource name | Would force every list response to carry full detail for every row, defeating the pagination/bounded-size work from #124 | Rejected — directly conflicts with #124's "bounded default page size" goal |

## Design Decisions

### Decision: reuse `REMOTE_TICKET_NOT_FOUND` rather than a new error code
- **Context**: This is a new read path; it could mint its own not-found code.
- **Rationale**: The write-side `existing_ticket_path()` already uses `REMOTE_TICKET_NOT_FOUND` for "no such ticket" (case: not present in the writable file, regardless of visibility). Using the same code on the read side means a client only needs to know one code for "this ticket ID is not usable by me," matching Simplification.
- **Trade-offs**: None.
- **Follow-up**: None.

## Risks & Mitigations
- Risk: A future change to `read_resource()` passes the *unfiltered* `items` (not `visible`) to some builder, silently reopening the visibility leak this feature currently avoids by construction. — Mitigation: the acceptance criteria and tests assert the not-found-indistinguishability behavior directly, so a regression there fails a test rather than passing silently.

## References
- `lifetxt/tickets.py` (`ticket_view`, `iter_tickets`, `ticket_id_of`, `id_key`).
- `lifetxt/remote_backend.py` (`read_resource`, `_resource_links` as the closest existing id-parameter precedent).
- `lifetxt/remote_ticket_write_core.py:143-148` (`REMOTE_TICKET_NOT_FOUND` precedent).
- GitHub Issue #126.
