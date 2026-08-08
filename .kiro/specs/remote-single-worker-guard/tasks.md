# Implementation Plan

- [ ] 1. Add `validate_single_worker_deployment` and wire it into `create_app`
  - Add `import os` and the new function to `remote_sessions.py`
  - Call it from `remote_web.py`'s `create_app()` beside the existing `validate_session_configuration` call
  - Observable completion: constructing an app with `remote.enabled=true` and `WEB_CONCURRENCY=4` raises `RemoteAccessError` (`REMOTE_MULTI_WORKER_UNSUPPORTED`); unset `WEB_CONCURRENCY` does not
  - _Requirements: 1.1, 1.2, 1.3, 1.4_
- [ ] 2. Register the override key
  - Add `remote.allow_multi_worker` to `config_registry.py` (boolean, default false)
  - Observable completion: `lifetxt config explain remote.allow_multi_worker` renders correctly; setting it true suppresses the raise under `WEB_CONCURRENCY=4`
  - _Requirements: 2.1, 2.2_
- [ ] 3. Cover with tests
  - Unit tests for all five requirement-1/2 branches (raise, override, disabled, absent/malformed signal, `<=1`)
  - Integration test through `create_app()` itself, not just the standalone function
  - Observable completion: new tests pass and fail correctly when the check is temporarily removed
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 2.1, 2.2_
- [ ] 4. Document the limitation and override
  - Update `docs/en/remote.md` / `docs/ja/remote.md`
  - Observable completion: both docs name the process-local components, `WEB_CONCURRENCY` detection, the override key, and state detection is best-effort
  - _Requirements: 3.1, 3.2_
