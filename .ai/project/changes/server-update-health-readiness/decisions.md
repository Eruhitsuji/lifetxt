# Decisions

| Date | Decision | Owner | Rejected Alternative | Rationale | Follow-up |
| --- | --- | --- | --- | --- | --- |
| 2026-08-11 | Preserve `health_timeout` as per-request timeout and add `health_ready_timeout` for the total readiness deadline | Codex | Reinterpret `health_timeout` as the total readiness deadline | Existing configs may already rely on `health_timeout` bounding each request. A separate key avoids a subtle compatibility change while matching #281's suggested fallback naming. | None |
| 2026-08-11 | Retry all current `check_health()` failure records, including HTTP failures, until the deadline | Codex | Retry only connection-level exceptions | #281 explicitly asks to cover HTTP error followed by success where appropriate. The retry remains bounded and post-validation, so it does not weaken safety properties. | None |
| 2026-08-11 | Clamp `health_retry_interval` to a small positive floor before retrying | Codex security-review | Honor a configured zero as a no-sleep retry loop | A zero interval can create a tight loop of local HTTP requests until the readiness deadline. The clamp keeps the setting operator-tunable without turning a bad value into needless CPU/request pressure. | None |
