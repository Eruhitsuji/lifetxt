# Research Log

## Summary

This is an extension of the existing `server-update` flow. The relevant integration point is `lifetxt.server_update.run_server_update`, which already restarts services and calls `check_health()` once after validation. The change should keep `check_health()` as the single-attempt primitive and add a bounded retry wrapper at the orchestrator boundary.

## Research Log

### Existing Health Flow

- `DEFAULT_CONFIG` contains `health_url` and `health_timeout`.
- `check_health(url, timeout)` returns `None` when no URL is configured, an `ok: true` record on HTTP success, and an `ok: false` record on `HTTPError`, `URLError`, `OSError`, or `ValueError`.
- `run_server_update()` calls `check_health()` once after all stopped services are restarted and after `validated_restart_incomplete` has been ruled out.

### Design Decisions

- Preserve `health_timeout` as the per-request timeout to avoid changing the meaning of an existing configuration key.
- Add `health_ready_timeout` for the total readiness deadline and `health_retry_interval` for sleep duration between failed attempts.
- Retry all current `check_health()` failures until the deadline, including HTTP failures, because the issue explicitly allows HTTP error followed by success where appropriate.
- Use dependency injection for `sleep` and `monotonic` in the retry helper so tests can cover timing deterministically without slow sleeps.
