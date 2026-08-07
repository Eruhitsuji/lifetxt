# Implementation Plan

> **This file is working material, not the task source of truth.**
>
> GitHub Issue #124 is the actionable task source for this spec (`.ai/managed/core/TASK_MANAGEMENT.md`).
> This breakdown is the execution plan for that issue's single PR on `ai/claude/124-remote-pagination`.

## Tasks

- [ ] 1. Foundation: add a regression test pinning today's `tickets` resource output for an explicit `limit`
  - Assert an explicit-`limit` request returns the same `count`/`tickets` shape as today, with no `next_cursor`/`has_more` behavior change yet
  - Observable completion: this test passes against the pre-change implementation and continues to pass unmodified after tasks 2-4 land
  - _Requirements: 1.2_

- [ ] 2. Core: bounded default page size and cursor pagination
- [ ] 2.1 Add the bounded default page size, replacing `_limit()` with a direct `_int()` call in `_resource_tickets`
  - Introduce `_TICKETS_DEFAULT_PAGE_SIZE`; when `limit` is omitted, use it as the default instead of returning every row
  - Observable completion: a request omitting `limit` against a ticket set larger than the default returns exactly the default page size
  - _Requirements: 1.1, 1.3_

- [ ] 2.2 Add `cursor` filtering and `next_cursor`/`has_more` to the response
  - Filter to tickets sorting strictly after `cursor` before slicing to the page size; compute `has_more` from whether more rows remain after the returned page; set `next_cursor` to the last returned ticket's ID exactly when `has_more` is true
  - Observable completion: paginating with the reported `next_cursor` across multiple calls visits every visible ticket exactly once, with the last page reporting `has_more: false` and `next_cursor: null`
  - _Requirements: 2.1, 2.2, 2.3, 2.4_

- [ ] 3. Core: add the `since_revision` check to `read_resource`, gated to the `tickets` resource
  - Compute the workspace revision once, before filtering/building; when `since_revision` is supplied and does not match, raise a distinct Remote error before any read/filter/paginate work runs; when omitted, behavior is unchanged
  - Observable completion: a stale `since_revision` produces the new distinct error; a matching one, or an omitted one, behaves identically to a request with no `since_revision` at all
  - _Requirements: 3.1, 3.2, 3.3_
  - _Boundary: read_resource (dispatcher), independent of _resource_tickets's internal slicing logic in tasks 2.1/2.2_

- [ ] 4. Integration: exercise pagination and the consistency check through the real FastAPI routes
  - Add a TestClient-based test hitting `/api/remote/v1/tickets` (or `/api/remote/v1/resources/tickets`) that pages through a multi-ticket workspace end to end, and one exercising a stale `since_revision` through the route
  - Observable completion: both new route-level tests fail against a stub that only implements the unit-level behavior from tasks 2/3, and pass against the real routes
  - _Depends: 2.2, 3_
  - _Requirements: 1.1, 2.1, 2.2, 2.3, 2.4, 3.1, 3.2, 3.3_

- [ ] 5. Validation: confirm non-tickets resources are unaffected
  - Run the existing tests for the other resource builders (`items`, `links`, `agenda`, `search`, `projects`, `status`) to confirm none of them changed behavior
  - Observable completion: the other resources' existing tests pass unmodified
  - _Depends: 4_
  - _Requirements: 1.1, 1.2, 1.3, 2.1, 2.2, 2.3, 2.4, 3.1, 3.2, 3.3_

- [ ] 6. Validation: update documentation
  - Document `cursor`, `next_cursor`, `has_more`, `since_revision`, and the new default page size, including the compatibility-impacting default-size change, in `docs/en/remote.md` and `docs/ja/remote.md`
  - Observable completion: both documents describe all four new parameters/fields and the default-size change
  - _Depends: 4_

- [ ] 7. Validation: register the change in the capability and traceability registries
  - Confirm whether an existing Remote read-backend capability entry in `.ai/project/CAPABILITIES.yml` already covers `remote_backend.py`; extend it if so, otherwise add a new entry, per the issue's reuse-check
  - Add a chain row to `.ai/project/TRACEABILITY.yml` linking `req-remote-tickets-bounded-pagination`, the capability, Issue #124, and this work's pull request
  - No numbered functional requirement: this task satisfies Issue #124's traceability acceptance criterion and the RULES.md Traceability Gate, not a requirements.md behavior
  - Observable completion: `tests.test_traceability_gate` passes for the resulting diff
  - _Depends: 5, 6_
