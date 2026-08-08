# Design Document

## Overview

**Purpose**: Fail loudly, at startup, when Remote Safe Mode is enabled and the process detects it is one of several worker processes sharing one ASGI application -- because `RateLimiter` and `BrowserSessionStore` are both plain in-process state with no shared backend, so per-worker divergence silently weakens login throttling and session consistency rather than producing a visible error.

**Users**: Operators deploying lifetxt so multiple clients (Web/CLI/MCP) share one server. Directly relevant to the "one server, multiple clients" deployment this batch targets.

**Impact**: Additive startup check only. No change to `RateLimiter`, `BrowserSessionStore`, or any request-time behavior. A deployment through `lifetxt serve` (no `--workers` flag exists) is never affected by this check in practice; it exists for the case where the ASGI app is launched by an external multi-worker manager.

### Goals
- Detect the common `WEB_CONCURRENCY > 1` signal and refuse to start Remote Safe Mode.
- Provide an explicit, off-by-default configuration override for operators who accept the trade-off.
- Document the limitation (best-effort detection) plainly, not as a guarantee.

### Non-Goals
- Building a shared/durable rate-limit or session backend (separate, larger, future spec -- `todo.md` lines 72/157).
- Detecting every possible multi-worker topology (Kubernetes replicas, multiple independent `lifetxt serve` processes behind a load balancer, etc. are out of reach for an in-process env-var check and are not claimed to be covered).
- Any change to `lifetxt serve`'s CLI surface.

## Boundary Commitments

### This Spec Owns
- The new startup check function and its call site in `create_app()`.
- The new `remote.allow_multi_worker` configuration key (registry metadata, default, documentation).

### Out of Boundary
- `RateLimiter` / `BrowserSessionStore` implementations -- unmodified.
- Any other Remote Safe Mode validation (`validate_session_configuration`, `validate_remote_storage`) -- unmodified, this check is added alongside them, not merged into them (different concern: config *shape* validity vs. *deployment-topology* safety).

### Allowed Dependencies
- `os.environ` (read-only, `WEB_CONCURRENCY`).
- The existing `remote.enabled` / `_remote(config)` accessor pattern already used throughout `remote_sessions.py`.
- `RemoteAccessError` (existing exception type used by every other Remote startup validation, e.g. `REMOTE_SESSION_CONFIG_INVALID`, `REMOTE_AUDIT_PATH_CONFLICT`).

### Revalidation Triggers
- If `RateLimiter` or `BrowserSessionStore` ever gain a shared/durable backend, this guard becomes unnecessary and should be removed or made conditional on backend choice.
- If `lifetxt serve` ever gains a `--workers` flag, that flag's implementation must consult this same check (or set `WEB_CONCURRENCY` itself) rather than bypassing it.

## File Structure Plan

### Modified Files
- `lifetxt/remote_sessions.py` -- new `validate_single_worker_deployment(config)` function, placed next to `validate_session_configuration`.
- `lifetxt/remote_web.py` -- call the new function in `create_app()`, next to the existing `validate_session_configuration(app.state.config)` call.
- `lifetxt/config_registry.py` -- register `remote.allow_multi_worker`.
- `docs/en/remote.md`, `docs/ja/remote.md` -- document the limitation and override.
- `tests/test_remote_compatibility_v21.py` or a more specific existing session-config test module (confirm during implementation which file already covers `validate_session_configuration`, and place the new tests beside it).

No new files.

## Requirements Traceability

| Requirement | Design Element |
| --- | --- |
| 1.1, 1.2, 1.3, 1.4 | `validate_single_worker_deployment(config)`: returns immediately if `not remote.get("enabled")`; reads `os.environ.get("WEB_CONCURRENCY")`; returns immediately if absent/unparseable/`<= 1`; raises `RemoteAccessError("REMOTE_MULTI_WORKER_UNSUPPORTED", ..., 500)` when `> 1` and no override |
| 2.1, 2.2 | Same function checks `remote.get("allow_multi_worker")` before raising; key registered in `config_registry.py` with `default=False` |
| 3.1, 3.2 | Manual documentation edits |

## Components and Interfaces

### `lifetxt.remote_sessions.validate_single_worker_deployment(config)`
```python
def validate_single_worker_deployment(config):
    """Refuse to start Remote Safe Mode under a detected multi-worker deployment.

    RateLimiter and BrowserSessionStore are both plain in-process state (see
    their own implementations): a request landing on a different worker than
    the one that authenticated or rate-limited it sees a different counter
    and a different session table. lifetxt serve itself has no --workers
    flag and can only launch a single process; this only fires when the ASGI
    app is launched directly by an external multi-worker manager.

    Detection is necessarily best-effort: WEB_CONCURRENCY is a de facto
    standard several platforms/process managers set for this purpose, but
    its absence does not prove a single-worker deployment.
    """
    remote = _remote(config)
    if not remote.get("enabled"):
        return
    if remote.get("allow_multi_worker"):
        return
    raw = os.environ.get("WEB_CONCURRENCY")
    if not raw:
        return
    try:
        workers = int(raw)
    except (TypeError, ValueError):
        return
    if workers > 1:
        raise RemoteAccessError(
            "REMOTE_MULTI_WORKER_UNSUPPORTED",
            "Remote Safe Mode's rate limiting and browser-session store are "
            "process-local and unsafe under multiple worker processes "
            "(WEB_CONCURRENCY=%s detected). Run a single worker, or set "
            "remote.allow_multi_worker=true to start anyway with reduced "
            "throttling and session consistency." % raw,
            500,
        )
```
Requires `import os` in `remote_sessions.py` (not currently imported there -- confirm and add).

### Call site: `remote_web.py`'s `create_app()`
Add `validate_single_worker_deployment(app.state.config)` immediately after the existing `validate_session_configuration(app.state.config)` call, inside the same `if app.state.remote_enabled:` block (the new function is itself also enabled-gated internally, so the outer `if` is redundant-but-consistent with the existing call's placement -- keep it for readability, matching the file's existing style).

### `config_registry.py` entry
```python
"remote.allow_multi_worker": _entry(
    "boolean",
    False,
    "Acknowledge that Remote Safe Mode's rate limiting and browser-session "
    "store are process-local and start anyway under a detected multi-worker "
    "deployment (WEB_CONCURRENCY > 1). Reduces throttling and session "
    "consistency across workers.",
),
```

## Testing Strategy

- Unit: `remote.enabled=True` + `WEB_CONCURRENCY=4` (monkeypatched env) -> raises `RemoteAccessError` with code `REMOTE_MULTI_WORKER_UNSUPPORTED`.
- Unit: same, but `remote.allow_multi_worker=True` -> does not raise.
- Unit: `remote.enabled=False` + `WEB_CONCURRENCY=4` -> does not raise (check never activates).
- Unit: `remote.enabled=True` + `WEB_CONCURRENCY` unset/empty/non-numeric -> does not raise (fails open on absent/malformed signal, per Requirement 1.3).
- Unit: `remote.enabled=True` + `WEB_CONCURRENCY=1` -> does not raise.
- Integration: `create_app()` itself raises under the same conditions (proves the wiring, not just the standalone function) -- reuse the existing pattern from whatever test already exercises `validate_session_configuration`'s call site.
- Live verification: launch a real `lifetxt serve`-equivalent app construction with `WEB_CONCURRENCY=2` set in the environment and `remote.enabled=true`, confirm it refuses to start; confirm it starts normally with `WEB_CONCURRENCY` unset (the actual `lifetxt serve` path, unaffected).

## Security Considerations

This is itself a security-hardening change (Security/High assurance per `ASSURANCE_LEVELS.md`'s escalation rules: authentication/authorization-adjacent). Key points for reviewer attention:
- **Fails safe, not silent**: the alternative to this guard is not "no risk," it's "silent, undetectable weakening of login throttling and session consistency." A refusal to start is the correct failure mode.
- **Detection is incomplete by design and by necessity**: this is not a comprehensive multi-worker detector. It catches the common `WEB_CONCURRENCY` case and documents that it does not cover every deployment topology. This must not be presented to users as a guarantee.
- **Opt-out is explicit and off by default**: `remote.allow_multi_worker` requires a deliberate configuration change; the guard is active for every existing deployment with no migration needed (new key, absent = current safe behavior preserved for single-worker deployments, which is what `lifetxt serve` already produces).
- **No new attack surface**: reads one environment variable already trusted per this project's own established rule ("Environment variables and CLI flags are trusted values") and one existing config key; raises before any request is served.
