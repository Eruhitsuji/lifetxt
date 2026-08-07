# Requirements Document

> **Authoritative copy lives in the change package, not here.** This change is Standard assurance
> and M-sized with a written split-justification (GitHub Issue #122), below the
> `.ai/project/changes/README.md` change-package threshold — the issue and its pull request carry
> the authoritative record; this file is the working spec.

## Project Description (Input)

remote-conflict-schema: Make Remote ticket-mutation conflicts conform to dist/schemas/conflict-v1.schema.json end-to-end. Server side (lifetxt/remote_ticket_write_core.py::as_remote_error) must emit a detail payload with error:"CONFLICT", expected_revision, current_revision, attempted_change (normalized like request_hash()), and current_item (permission-filtered current ticket row, or null if no longer visible). Client side (lifetxt/remote_client_writes.py: RemoteMutationConflict, mutate_ticket) must consume these fields directly instead of re-fetching a snapshot and building a partial _bounded_comparison(), while keeping automatic_retry:False and next_actions as additive client-only fields. See GitHub Issue #122 for full scope, out-of-scope (does NOT touch webapp.py/remote_contracts_v6.py/safety_compat_v2.py's separate non-conformant conflict producers, does NOT touch the schema itself), and acceptance criteria.

## Boundary Context

- **In scope**: the Remote ticket-mutation conflict path only — server-side conflict construction in the ticket-mutation write handler, and client-side conflict consumption in the Remote ticket-write client.
- **Out of scope**: every other conflict-producing surface in the project (general item mutations, attachment reconciliation, and other existing `"CONFLICT"`-shaped producers) — this feature does not change or fix their conformance to the standard conflict shape. No change to the standard conflict schema itself. No new fields beyond what that schema already defines (no generated-event or affected-side-record data in this feature).
- **Adjacent expectations**: this feature depends on the existing standard conflict shape continuing to define exactly its current fields, and on the existing permission/visibility filtering used for ordinary ticket reads being reusable for the conflict's current-item check.

## Requirements

### Requirement 1: Schema-conformant conflict detail

**Objective:** As a Remote client developer, I want a ticket-mutation conflict response to carry the full standard conflict shape, so that I can build correct conflict handling without guessing which fields are missing.

#### Acceptance Criteria

1. When a ticket mutation is rejected because the authoritative revision changed, the Remote Ticket Mutation Service shall include `expected_revision`, `current_revision`, and `attempted_change` in the conflict detail.
2. The Remote Ticket Mutation Service shall set the conflict detail's `error` field to the fixed value `"CONFLICT"`.
3. The Remote Ticket Mutation Service shall not include any field in the conflict detail other than `error`, `expected_revision`, `current_revision`, `attempted_change`, and `current_item`.
4. Where the requested operation included fields to unset, the conflict detail's `attempted_change` shall reflect those unset fields.

### Requirement 2: Permission-filtered current item

**Objective:** As a Remote operator, I want a conflict's current-item data limited to what I am already allowed to see, so that a conflict cannot become a way to read data I do not have access to.

#### Acceptance Criteria

1. When a ticket mutation conflict occurs and the principal can still see the current ticket under its existing read permissions, the Remote Ticket Mutation Service shall include that ticket as `current_item` in the conflict detail.
2. When a ticket mutation conflict occurs and the principal can no longer see the current ticket under its existing read permissions, the Remote Ticket Mutation Service shall set `current_item` to `null` rather than omitting it or including the filtered-out data.

### Requirement 3: Single round-trip conflict presentation

**Objective:** As a Remote client operator, I want conflict information available immediately from the failed request, so that resolving a conflict does not cost an extra network round trip.

#### Acceptance Criteria

1. When a ticket mutation request fails with a conflict, the Remote Ticket Client shall present `expected_revision`, `current_revision`, `attempted_change`, and `current_item` using only the data returned by that failed request.
2. The Remote Ticket Client shall not issue an additional read request to construct conflict presentation data.

### Requirement 4: Preserved recovery guidance

**Objective:** As a Remote client operator, I want conflicts to keep telling me they were not auto-resolved and what I can do next, so that existing recovery workflows keep working.

#### Acceptance Criteria

1. The Remote Ticket Client shall continue to report that a conflict was not automatically retried.
2. The Remote Ticket Client shall continue to offer the existing set of next actions for a conflict.
3. While presenting a conflict, the Remote Ticket Client shall keep the automatic-retry and next-action information distinguishable from the fields defined by the standard conflict shape.
