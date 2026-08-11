# Server Update Health Readiness Design

`lifetxt.server_update.check_health()` remains the single-attempt primitive. A new `wait_for_health()` helper owns readiness retry and is called only from the validated tail of `run_server_update()` after service restart has succeeded.

The config model preserves existing `health_timeout` semantics as the per-request timeout and adds:

- `health_ready_timeout`: total readiness deadline after restart.
- `health_retry_interval`: delay between failed attempts.

The returned `health_check` object records:

- `ok`
- `attempts`
- `elapsed_seconds`
- `request_timeout`
- `ready_timeout`
- `retry_interval`
- `attempt_timeout`
- final `status_code`, `body`, or `error` from the last attempt

Dry-run reports include `would_check_health_url`, `would_use_health_timeout`, `would_use_health_ready_timeout`, and `would_use_health_retry_interval`.

`health_retry_interval` is clamped to a small positive floor before retrying so an accidental zero value cannot create a tight request loop during the readiness window.

Each attempt's network timeout is capped to the remaining readiness deadline. This preserves `health_timeout` as the per-request maximum without allowing one slow request to exceed `health_ready_timeout`.

Security boundary: readiness retry performs repeated HTTP reads and sleeps only. It does not introduce additional git commands, package installs, service actions, file writes, or data rollback.
