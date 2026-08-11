# Implementation Plan

> **This file is working material, not the task source of truth.**
>
> GitHub Issue #281 is the authoritative task contract for this implementation.

- [x] 1. Add server-update health readiness retry
  - Add health readiness timing defaults and normalize timing values inside `lifetxt/server_update.py`.
  - Add a deterministic `wait_for_health` helper around `check_health`.
  - Wire the helper into `run_server_update` after successful service restart and expose dry-run readiness fields.
  - _Requirements: 1, 2_
  - _Boundary: `lifetxt/server_update.py`_

- [x] 2. Cover readiness behavior with tests
  - Add deterministic unit tests for immediate success, transient connection failure followed by success, repeated failure until deadline, and HTTP error followed by success.
  - Add or adjust orchestration tests so a transient post-restart health failure produces `updated`, while exhausted readiness still produces `validated_health_check_failed`.
  - Confirm restart failure still avoids health checks and returns `validated_restart_incomplete`.
  - _Requirements: 1, 2_
  - _Boundary: `tests/test_server_update.py`_
  - _Depends: 1_

- [x] 3. Update operator docs and traceability
  - Document `health_ready_timeout` and `health_retry_interval` in CLI and Ubuntu Server deployment docs.
  - Record the High assurance change package, capability impact, and verification evidence.
  - _Requirements: 2_
  - _Boundary: docs and `.ai/project/**` records_
  - _Depends: 1, 2_

## Implementation Notes

- The feature preserves `health_timeout` as a per-request timeout and adds `health_ready_timeout` for the total readiness deadline.
