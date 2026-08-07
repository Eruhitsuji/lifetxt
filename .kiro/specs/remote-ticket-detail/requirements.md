# Requirements Document

> **Authoritative copy lives in the change package, not here.** This change is Standard assurance
> and S-sized (GitHub Issue #126), below the `.ai/project/changes/README.md` threshold — the
> issue and its pull request carry the authoritative record; this file is the working spec.

## Project Description (Input)

remote-ticket-detail: Add a permission-aware Remote read resource, `ticket-detail`, returning one ticket's full detail (fields, relations, incoming links, time totals) via the existing `tickets.ticket_view()` function, which is not currently exposed through `remote_backend.py`'s resource dispatch. Takes an `id` parameter. Must be indistinguishable in response shape whether the ticket ID does not exist or exists but is not visible to the principal. See GitHub Issue #126 for full scope, out-of-scope (no history/time-entry/version/sprint/watcher/attachment resources, no change to `ticket_view`/`access_for_item`/`can_access` themselves), and acceptance criteria.

## Boundary Context

- **In scope**: one new Remote read resource, `ticket-detail`, built on the existing `ticket_view()` function and the existing `_visible_items()`/`access_for_item()`/`can_access()` permission filtering.
- **Out of scope**: `history` (ticket events), `time-entry`, `version`, `sprint`, `dependency` (as its own resource beyond what `ticket_view()`'s `relations` already returns), `watcher` (as its own resource beyond `ticket_summary()`'s existing `watchers` field), and `attachment` metadata — each is further work with its own permission-model question, not resolved here.
- **Adjacent expectations**: this feature depends on `ticket_view()`'s existing output shape and on `_visible_items()` continuing to filter every item (including ones referenced only through relations) before this resource sees them.

## Requirements

### Requirement 1: Ticket detail resource

**Objective:** As a Remote client operator, I want to fetch one ticket's full detail — not just its summary row — so that I can see its custom fields, relations, and incoming links without reconstructing them client-side from the list resource.

#### Acceptance Criteria

1. When a `ticket-detail` request supplies the `id` of a ticket the principal can see, the Remote Ticket Detail Resource shall return that ticket's full detail matching `ticket_view()`'s existing shape.
2. The Remote Ticket Detail Resource shall compute relations and incoming links only against tickets the principal can independently see, so a relation to an invisible ticket does not expose that ticket's fields or confirm its existence.
3. The Remote Ticket Detail Resource shall redact its response using the same rules already applied to every other Remote read resource.

### Requirement 2: Indistinguishable not-found response

**Objective:** As a Remote operator, I do not want to be able to tell, from the response alone, whether a ticket ID does not exist or exists but is hidden from me, so that a private ticket's existence cannot be probed.

#### Acceptance Criteria

1. When a `ticket-detail` request supplies an `id` that does not correspond to any ticket, the Remote Ticket Detail Resource shall respond with a not-found error.
2. When a `ticket-detail` request supplies the `id` of a ticket that exists but the principal cannot see, the Remote Ticket Detail Resource shall respond with the identical not-found error used for a nonexistent ticket, with no field distinguishing the two cases.
