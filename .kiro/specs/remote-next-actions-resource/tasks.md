# Implementation Plan

- [ ] 1. Add the `next` resource builder and register it
  - Add `_resource_next(items, config, params)` to `remote_backend.py`
  - Register `"next"` in `RESOURCE_NAMES`, `resource_catalog()`, and `_BUILDERS`
  - Observable completion: `read_resource("next", paths, config, principal, {})` returns `{"count": N, "items": [...]}` for a real fixture
  - _Requirements: 1.1, 1.2, 2.1, 3.1, 3.2_
- [ ] 2. Add parameter bounds and permission-boundary tests
  - Test `limit` bound (0..1000) rejects invalid values like `_resource_search` does
  - Test `project`/`assignee` filtering
  - Test an item blocked by an invisible dependency is excluded, not promoted to actionable
  - Observable completion: new tests pass; a deliberately-reverted permission check fails them
  - _Requirements: 1.3, 1.4_
- [ ] 3. Document the resource
  - Add `next` to `docs/en/remote.md` / `docs/ja/remote.md`'s resource list
  - Observable completion: both docs name the resource and its three parameters
  - _Requirements: 2.1_
