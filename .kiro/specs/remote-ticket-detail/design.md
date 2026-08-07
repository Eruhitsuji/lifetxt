# Design Document

> **Authoritative copy lives in the change package, not here.** This change is Standard assurance
> and S-sized (GitHub Issue #126), below the `.ai/project/changes/README.md` threshold — the
> issue and its pull request carry the authoritative record; this file is the working spec.

## Overview

**Purpose**: Expose the existing `ticket_view()` aggregation as a Remote read resource, `ticket-detail`, so a client can fetch one ticket's full fields/relations/incoming-links without reconstructing them from the bounded `tickets` list resource.

**Users**: Any Remote reader of `/api/remote/v1/resources/ticket-detail`.

**Impact**: Additive only — a new resource name; no existing resource or route changes behavior.

### Goals
- One ticket's full detail, permission-filtered, reusing `ticket_view()` as-is.
- Nonexistent and invisible tickets are indistinguishable in the response.

### Non-Goals
- `history`, `time-entry`, `version`, `sprint`, `dependency`/`watcher`/`attachment` as their own resources.
- Any change to `ticket_view()`, `access_for_item()`, or `can_access()`.

## Boundary Commitments

### This Spec Owns
- The new `ticket-detail` resource builder and its `_BUILDERS`/`RESOURCE_NAMES`/`resource_catalog()` registration.
- Documentation of the new resource.

### Out of Boundary
- `tickets.ticket_view()` and every function it calls — reused unmodified.
- `remote_access.access_for_item()`/`can_access()` — reused unmodified.
- Every resource named out of scope in the issue.

### Allowed Dependencies
- `tickets.ticket_view`, `tickets.iter_tickets`, `tickets.ticket_id_of`, `tickets.id_key`.
- `remote_backend.read_resource()`'s existing permission-filter-before-dispatch order.
- `remote_ticket_write_core`'s `REMOTE_TICKET_NOT_FOUND` error code (reused by value, not by import, matching how error codes are used as plain strings elsewhere in this module).

### Revalidation Triggers
- `ticket_view()`'s output shape changes.
- `read_resource()` stops passing the permission-filtered `visible` list to builders.

## Architecture

### Existing Architecture Analysis
`read_resource()` already reads, permission-filters to `visible`, and dispatches to `_BUILDERS[name](visible, config, params)` — the same sequence every existing resource (including `_resource_links`, the closest existing single-ID-parameter precedent) relies on.

### Architecture Integration
- **Selected pattern**: one new builder function, reusing `ticket_view()` (see `research.md`).
- **New components rationale**: no new component beyond the one builder function; no new route (the existing `/api/remote/v1/resources/{resource_name}` route already dispatches by name).

### Technology Stack

| Layer | Choice / Version | Role in Feature | Notes |
|-------|------------------|------------------|-------|
| Backend / Services | Python (stdlib only) | New `_resource_ticket_detail` builder | Reuses `tickets.ticket_view` |

## File Structure Plan

### Modified Files
- `lifetxt/remote_backend.py` — add `_resource_ticket_detail(items, config, params)`; register it in `_BUILDERS`, `RESOURCE_NAMES`, and `resource_catalog()`.
- `tests/test_remote_backend_v20.py` — new tests for the resource.
- `docs/en/remote.md`, `docs/ja/remote.md` — document the new resource.
- `.ai/project/CAPABILITIES.yml`, `.ai/project/TRACEABILITY.yml` — capability/traceability registration (reuse-vs-new confirmed at implementation time).

### Not Modified
- `lifetxt/tickets.py`, `lifetxt/remote_access.py`, `lifetxt/remote_web.py` — the generic `/api/remote/v1/resources/{resource_name}` route already covers any resource name without a route-level change.

## Requirements Traceability

| Requirement | Summary | Components | Interfaces | Flows |
|-------------|---------|-------------|------------|-------|
| 1.1-1.3 | Ticket detail resource | `_resource_ticket_detail` | `ticket_view()` reuse | N/A — single function, no multi-step flow needing a diagram |
| 2.1-2.2 | Indistinguishable not-found | `_resource_ticket_detail` | `REMOTE_TICKET_NOT_FOUND` | N/A |

## Components and Interfaces

| Component | Domain/Layer | Intent | Req Coverage | Key Dependencies (P0/P1) | Contracts |
|-----------|---------------|--------|---------------|----------------------------|-----------|
| `_resource_ticket_detail` | `lifetxt.remote_backend` | Look up one ticket in the permission-filtered set and return its full detail | 1.1, 1.2, 1.3, 2.1, 2.2 | `tickets.ticket_view` (P0, existing), `read_resource`'s filter-before-dispatch order (P0, existing) | Service |

### Remote Read Backend Domain

#### `_resource_ticket_detail`

| Field | Detail |
|-------|--------|
| Intent | Build the `ticket-detail` resource's `data` payload for one ticket ID |
| Requirements | 1.1, 1.2, 1.3, 2.1, 2.2 |

**Responsibilities & Constraints**
- Looks up the ticket only within the `items` argument it receives (already permission-filtered by `read_resource()`); must never accept or fall back to an unfiltered item source.
- Raises `RemoteAccessError("REMOTE_TICKET_NOT_FOUND", ..., 404)` identically whether the ID is absent from `items` because it does not exist or because it is not visible — a single code path, not two branches that happen to produce the same error.
- Passes the same `items` list to `ticket_view(..., items=items, ...)` so relations/incoming_links are computed only against visible tickets.

**Dependencies**
- Inbound: `read_resource` (P0, sole caller)
- Outbound: `tickets.ticket_view`, `tickets.iter_tickets`, `tickets.ticket_id_of`, `tickets.id_key` (all P0, existing)

**Contracts**: Service [x] / API [ ] / Event [ ] / Batch [ ] / State [ ]

##### Service Interface
```python
def _resource_ticket_detail(items, config, params):
    """Return ticket_view()'s output for the ticket named by params["id"],
    looked up only within the already-permission-filtered items. Raises
    REMOTE_TICKET_NOT_FOUND (404) identically for a nonexistent ticket ID
    and for one that exists but is not in items.
    """
```
- Preconditions: `items` is the permission-filtered set `read_resource()` already produces.
- Postconditions: returns `redact_remote_value(ticket_view(...))` for a found, visible ticket; raises for anything else.
- Invariants: no code path returns partial data or a different error shape for "not found" vs. "not visible."

**Implementation Notes**
- Integration: register in `_BUILDERS["ticket-detail"]`, add `"ticket-detail"` to `RESOURCE_NAMES`, add a `resource_catalog()` entry with `parameters: ["id"]`.
- Validation: found/visible, nonexistent-ID, existing-but-invisible-ID (asserted identical to nonexistent), relation-to-invisible-ticket cases.
- Risks: none beyond `research.md`.

## Error Handling

### Error Strategy
Reuses the existing `REMOTE_TICKET_NOT_FOUND` code and the existing `RemoteAccessError` mechanism `read_resource()`'s callers already handle — no new error shape introduced.

## Testing Strategy

### Unit Tests
- A visible ticket's `ticket-detail` response matches calling `ticket_view()` directly with the same filtered item set — Requirement 1.1.
- A relation field pointing at an existing-but-invisible ticket ID does not expose that ticket's fields through `relations`/`incoming_links` — Requirement 1.2.
- Response redaction matches the existing pattern (no local paths) — Requirement 1.3.
- A nonexistent `id` and an existing-but-invisible `id` produce byte-identical error responses — Requirement 2.1, 2.2.
