# Design

See `.kiro/specs/remote-single-worker-guard/design.md` for the full cc-sdd design document (Overview, Boundary Commitments, File Structure Plan, Requirements Traceability, Components and Interfaces, Testing Strategy, Security Considerations). Summary below per this change package's own format.

## Summary

`lifetxt.remote_access.RateLimiter` and `lifetxt.remote_sessions.BrowserSessionStore` are both plain in-process state with no shared backend (confirmed by reading their implementations: `defaultdict(deque)` behind a `threading.Lock`; an `OrderedDict` inside one Python object). Under an external multi-worker deployment, a request landing on a different worker than the one that authenticated or rate-limited it sees a different counter and a different session table -- silently weakening login throttling and producing inconsistent session/revocation behavior.

Adds `lifetxt.remote_sessions.validate_single_worker_deployment(config)`, called from `remote_web.py`'s `create_app()` beside the existing `validate_session_configuration` call. When `remote.enabled` is true, `WEB_CONCURRENCY` (a de facto standard several platforms/process managers set) parses to an integer greater than 1, and `remote.allow_multi_worker` is not set, it raises `RemoteAccessError("REMOTE_MULTI_WORKER_UNSUPPORTED", ..., 500)`.

`lifetxt serve` itself has no `--workers` flag and can only ever launch a single process, so this guard only ever fires when the ASGI application object is launched directly by an external multi-worker manager (gunicorn, `uvicorn --workers N`, a PaaS platform's default multi-worker mode) instead of through lifetxt's own CLI.

## Key design decisions

1. **Fail closed on a positive signal, fail open on an absent one.** The check only acts when `WEB_CONCURRENCY` unambiguously indicates more than one worker. It does not treat the absence of the signal as proof of a safe single-worker deployment, and documentation states this plainly rather than implying comprehensive coverage.
2. **Off-by-default, explicit opt-out.** `remote.allow_multi_worker` requires a deliberate configuration change. No existing deployment is affected without an operator explicitly setting `WEB_CONCURRENCY` in their own environment first.
3. **New function, not merged into `validate_session_configuration`.** Different concern: config *shape* validity vs. *deployment-topology* safety. Kept separate for clarity and to avoid conflating two independently-reviewable checks.
