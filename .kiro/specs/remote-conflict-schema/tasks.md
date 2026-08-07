# Implementation Plan

> **This file is working material, not the task source of truth.**
>
> GitHub Issue #122 is the actionable task source for this spec (`.ai/managed/core/TASK_MANAGEMENT.md`).
> This breakdown is the execution plan for that issue's single PR on `ai/claude/122-remote-conflict-schema`.

## Tasks

- [ ] 1. Foundation: extract the shared payload-normalization helper
  - Pull the "operation plus payload, minus `transaction_id`/`dry_run`" logic out of `request_hash()` into its own function, with `request_hash()` calling it unchanged
  - Observable completion: `request_hash()`'s existing tests still pass unmodified, proving the extraction changed nothing observable yet
  - _Requirements: 1.4_

- [ ] 2. Core: schema-conformant conflict detail, on both server and client
- [ ] 2.1 Extend `as_remote_error` with conflict context parameters and build the schema-shaped detail
  - Add the optional `payload`, `principal`, `paths`, `key`, `ticket_id_value` parameters; for a `MutationConflict`, build `detail` with exactly `error="CONFLICT"`, `expected_revision`, `current_revision`, `attempted_change` (via the helper from task 1)
  - Leave the `RemoteAccessError` and `ValueError` branches unchanged
  - Observable completion: a `MutationConflict` raised with a known payload produces a `detail` with exactly those four keys and no others yet (task 2.2 adds the fifth)
  - _Requirements: 1.1, 1.2, 1.3_

- [ ] 2.2 Add permission-filtered `current_item` re-read
  - Re-read the current ticket the same way `replay()` already does (`read_text_snapshot` -> parse -> find), then filter it through `access_for_item`/`can_access` before including it
  - Set `current_item` to `None` when the ticket cannot be found or the principal cannot see it under that filter
  - Observable completion: a conflict where the principal can still see the ticket includes its full dict as `current_item`; a conflict where the principal's grants no longer cover it (or the ticket ID is not found, including a `create`-operation conflict) yields `current_item: None`
  - _Requirements: 2.1, 2.2_

- [ ] 2.3 (P) Read the new fields directly on the client and drop the extra round trip
  - Update `RemoteMutationConflict` to carry `expected_revision`/`current_revision`/`attempted_change`/`current_item` sourced from the server `detail` (the shape is fully fixed by `design.md`, so this does not need 2.1/2.2's code to exist yet); remove `mutate_ticket()`'s `snapshot(profile)` re-fetch and `_bounded_comparison()` call on the conflict path
  - Keep `as_dict()`'s `automatic_retry: False` and `next_actions` as additive fields, clearly separate from the server-sourced ones
  - Observable completion: a test built from a stubbed conflict response (independent of the real server) shows the conflict object populated with all four server-sourced fields while asserting the stub's read/snapshot endpoint was never called
  - _Requirements: 3.1, 3.2, 4.1, 4.2, 4.3_
  - _Boundary: remote_client_writes.py_

- [ ] 3. Integration: update the ticket-mutation route's call site and add an end-to-end schema-conformance test
  - Pass `payload`, `principal`, `app.state.paths`, `key`, `ticket_id_value` at the route's existing `except Exception as exc: raise as_remote_error(exc)` call site
  - Add a test asserting the resulting `detail` validates against `dist/schemas/conflict-v1.schema.json` end-to-end through the route, not just the unit-level function calls from tasks 2.1/2.2
  - Add a test exercising the real client (task 2.3) against a real conflicting server response, confirming the two ends of the contract actually agree
  - Observable completion: the end-to-end schema-conformance test fails if the call site does not pass the new context, and passes once it does; the client-against-real-server test fails if the field names on either side disagree
  - _Depends: 2.2, 2.3_
  - _Requirements: 1.1, 1.2, 1.3, 2.1, 2.2_

- [ ] 4. Validation: update existing conflict-path assertions and confirm non-conflict behavior is unaffected
  - Update any existing test or CLI/TUI rendering code still reading the removed `requested_revision`/`comparison` field names
  - Run the existing create/edit/transition/comment/log_time happy-path Remote ticket-mutation tests to confirm they are unaffected
  - Observable completion: the full existing Remote ticket-write test file passes with no reference to the removed field names remaining
  - _Depends: 3_
  - _Requirements: 3.1, 3.2, 4.1, 4.2, 4.3_

- [ ] 5. Validation: register the change in the capability and traceability registries
  - Confirm whether an existing Remote ticket-write capability entry in `.ai/project/CAPABILITIES.yml` already covers `remote_ticket_write_core.py`/`remote_client_writes.py`; extend it if so, otherwise add a new entry, per the issue's reuse-check
  - Add a chain row to `.ai/project/TRACEABILITY.yml` linking `req-remote-ticket-conflict-schema-conformance`, the capability, Issue #122, and this work's pull request
  - No numbered functional requirement: this task satisfies Issue #122's traceability acceptance criterion and the RULES.md Traceability Gate, not a requirements.md behavior
  - Observable completion: `tests.test_traceability_gate` passes for the resulting diff
  - _Depends: 4_
