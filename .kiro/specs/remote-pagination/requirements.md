# Requirements Document

> **Authoritative copy lives in the change package, not here.** This change is Standard assurance
> and M-sized with a written split-justification (GitHub Issue #124), below the
> `.ai/project/changes/README.md` threshold — the issue and its pull request carry the
> authoritative record; this file is the working spec.

## Project Description (Input)

remote-pagination: Add a bounded default page size and cursor-based pagination to the Remote `tickets` resource (`lifetxt/remote_backend.py::_resource_tickets`, `lifetxt/remote_web.py`'s `/api/remote/v1/tickets` and `/api/remote/v1/resources/tickets` routes). Today `_limit()` only caps the response when a caller explicitly passes `limit`; omitting it returns every visible ticket. Add: a bounded default page size when `limit` is omitted; an optional `cursor` parameter returning tickets sorted strictly after a given ticket ID, using `ticket_list()`'s existing deterministic ID sort; `next_cursor`/`has_more` in the response; and an optional `since_revision` parameter that fails loudly with a distinct error when the workspace changed since the caller's earlier page, instead of silently mixing pages from different revisions. See GitHub Issue #124 for full scope, out-of-scope (no other resource, no ETag/cache-control/rate-limit/compression/SSE work), and acceptance criteria.

## Boundary Context

- **In scope**: the `tickets` resource only — its response shape, its two existing routes (`/api/remote/v1/tickets` and `/api/remote/v1/resources/tickets`), and the permission-filtered, deterministically-sorted list it already produces.
- **Out of scope**: every other Remote read resource (`items`, `links`, `agenda`, `search`, `projects`, `status`); ETag/`If-None-Match`/`Cache-Control`/rate-limit/compression/retry-backoff behavior; SSE/WebSocket or any push delivery; any write/mutation endpoint.
- **Adjacent expectations**: this feature depends on `ticket_list()`'s existing sort-by-ID behavior continuing to hold, and on `_visible_items()`'s permission filtering continuing to run before any resource builder sees the rows.

## Requirements

### Requirement 1: Bounded default page size

**Objective:** As an operator of a large workspace, I want a Remote tickets request that does not specify a page size to still return a bounded response, so that a single request cannot force the server to serialize an unbounded number of tickets.

#### Acceptance Criteria

1. When a tickets request omits the page-size parameter, the Remote Tickets Resource shall return at most a fixed default number of tickets rather than every visible ticket.
2. When a tickets request supplies an explicit page-size parameter within the existing allowed range, the Remote Tickets Resource shall honor that value exactly as it does today.
3. The Remote Tickets Resource shall apply the default or requested page size after permission filtering, so the count of returned tickets never includes tickets the requesting principal cannot see.

### Requirement 2: Cursor-based pagination

**Objective:** As a Remote client operator working through a large ticket list, I want to request the next page after where I left off, so that I can retrieve the full visible set across multiple bounded requests without missing or repeating tickets.

#### Acceptance Criteria

1. Where a cursor is supplied, the Remote Tickets Resource shall return only tickets that sort strictly after the cursor in the resource's existing deterministic order.
2. The Remote Tickets Resource shall report a next-page cursor that, when supplied on a subsequent request, continues immediately after the last ticket of the current page.
3. When a page reaches the end of the visible set, the Remote Tickets Resource shall report that no further pages remain.
4. While a caller pages through the full visible set using the reported cursors and default or fixed page size, the Remote Tickets Resource shall return every visible ticket exactly once, with no duplicates and no gaps.

### Requirement 3: Cross-page consistency signal

**Objective:** As a Remote client operator paginating across several requests, I want to know when the workspace changed since my earlier page, so that I do not silently assemble a result set mixing tickets from different points in time.

#### Acceptance Criteria

1. Where a caller supplies the revision its previous page was generated from, and the workspace's current revision no longer matches it, the Remote Tickets Resource shall refuse the request with an error distinct from other Remote errors, rather than returning a page.
2. Where a caller supplies the revision its previous page was generated from, and it still matches the workspace's current revision, the Remote Tickets Resource shall return the requested page normally.
3. Where a caller does not supply a previous-page revision, the Remote Tickets Resource shall behave exactly as it does today: each page independently reports its own revision, and no consistency check is performed.
