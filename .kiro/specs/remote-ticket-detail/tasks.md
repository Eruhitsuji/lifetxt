# Implementation Plan

> **This file is working material, not the task source of truth.**
>
> GitHub Issue #126 is the actionable task source for this spec (`.ai/managed/core/TASK_MANAGEMENT.md`).
> This breakdown is the execution plan for that issue's single PR on `ai/claude/126-remote-ticket-detail`.

## Tasks

- [ ] 1. Core: add the `ticket-detail` resource builder
  - Look up the ticket named by `params["id"]` only within the already-permission-filtered `items`; raise `REMOTE_TICKET_NOT_FOUND` (404) identically whether the ID is absent because it does not exist or because it is not visible
  - Pass the same filtered `items` to `ticket_view()` so relations/incoming_links never reference an invisible ticket's fields; redact the result the same way every other resource builder does
  - Observable completion: calling the builder directly with a filtered item set returns `ticket_view()`'s shape for a present, visible ticket, and raises the identical error for both a missing ID and a present-but-filtered-out ID
  - _Requirements: 1.1, 1.2, 1.3, 2.1, 2.2_

- [ ] 2. Integration: register the resource in dispatch and the capability catalog
  - Add the builder to `_BUILDERS`, add `"ticket-detail"` to `RESOURCE_NAMES`, add a `resource_catalog()` entry with `parameters: ["id"]`
  - Add a test reaching the resource through `read_resource("ticket-detail", ...)` (not just a direct call to the builder function), confirming end-to-end wiring
  - Observable completion: `read_resource("ticket-detail", paths, config, principal, {"id": ...})` returns the same shape task 1 verified at the unit level
  - _Depends: 1_
  - _Requirements: 1.1, 2.1, 2.2_

- [ ] 3. Validation: update documentation
  - Document the `ticket-detail` resource and its `id` parameter in `docs/en/remote.md` and `docs/ja/remote.md`
  - Observable completion: both documents list `ticket-detail` alongside the other resources with its parameter and not-found behavior
  - _Depends: 2_

- [ ] 4. Validation: register the change in the capability and traceability registries
  - Confirm whether `cap-remote-tickets-pagination` or another existing Remote read-backend capability already covers `remote_backend.py` broadly enough to extend, otherwise add a new entry, per the issue's reuse-check
  - Add a chain row to `.ai/project/TRACEABILITY.yml` linking `req-remote-ticket-detail-resource`, the capability, Issue #126, and this work's pull request
  - No numbered functional requirement: this task satisfies Issue #126's traceability acceptance criterion and the RULES.md Traceability Gate, not a requirements.md behavior
  - Observable completion: `tests.test_traceability_gate` passes for the resulting diff
  - _Depends: 3_
