# Requirements Document

## Project Description (Input)
The user is deploying one lifetxt server on a trusted local network for multiple clients (Web browser, CLI/TUI via `lifetxt remote` profiles, and MCP/AI agents) to view and edit shared data. Remote Safe Mode's per-principal rate limiting (`lifetxt.remote_access.RateLimiter`, used for both general request throttling and browser login throttling) and its opaque browser-session store (`lifetxt.remote_sessions.BrowserSessionStore`) are both confirmed, by reading their implementations directly, to be plain in-process state (`defaultdict(deque)` behind a `threading.Lock`; an `OrderedDict` inside one Python object) with no shared backend. `lifetxt serve`'s own CLI has no `--workers` flag and can only ever launch a single process (confirmed via `serve --help`), so this risk does not exist for a server launched through lifetxt's own CLI as documented. It becomes real only if the ASGI application object is launched directly by an external multi-worker process manager (gunicorn, `uvicorn --workers N`, or a PaaS platform's default multi-worker mode) instead of `lifetxt serve`. Under that condition, a request landing on a different worker than the one that authenticated or rate-limited it sees a different rate-limit counter and a different session table -- silently weakening login throttling (enabling a distributed brute-force across workers) and producing inconsistent session/revocation behavior, without any error or warning today. This matches `todo.md`'s "P1: Remote Safe Mode follow-up" line 72's explicitly offered alternative to a full durable multi-worker session backend: "explicit single-worker enforcement." Add a startup-time guard that fails loudly (refuses to start) when Remote Safe Mode is enabled and the process detects a common multi-worker signal (the `WEB_CONCURRENCY` environment variable, a de facto standard several platforms and process managers set, reporting more than 1 worker), with an explicit, documented opt-out for operators who have made an informed decision to accept the reduced consistency. This is a Security/High assurance change per `.ai/managed/core/ASSURANCE_LEVELS.md`'s escalation rules (authentication/authorization-adjacent) and requires human review before merge; detection is necessarily best-effort (not every multi-worker deployment sets `WEB_CONCURRENCY`), which must be stated plainly rather than implied to be comprehensive.

## Boundary Context

- **In scope**: A startup-time check, run once per worker process at `create_app()` time, that raises when Remote Safe Mode is enabled, a multi-worker signal is detected, and no explicit opt-out is configured. The opt-out setting itself, registered in `config_registry.py`. Documentation of the limitation and the opt-out.
- **Out of scope**: Building a real shared/durable session or rate-limit backend (a much larger effort explicitly deferred by `todo.md` line 72/157 as "a documented multi-worker session backend" -- a separate, future spec). Detecting every possible multi-worker deployment topology (out of reach for an in-process check; this spec commits only to the common, detectable `WEB_CONCURRENCY` signal). Any change to `lifetxt serve`'s own CLI (it already cannot express multi-worker deployment).
- **Adjacent expectations**: This spec does not change how `RateLimiter` or `BrowserSessionStore` behave -- it only decides, at startup, whether it is safe to proceed given their existing process-local design. A future durable-backend spec would remove the need for this guard rather than conflict with it.

## Requirements

### Requirement 1: Server refuses to start Remote Safe Mode under a detected multi-worker deployment
**Objective:** As an operator deploying lifetxt so multiple clients share one server, I want the server to refuse to start rather than silently run with inconsistent per-worker security state, so that I find out about the problem before it causes an incident.

#### Acceptance Criteria
1. When `remote.enabled` is true and the `WEB_CONCURRENCY` environment variable is present and parses to an integer greater than 1, the application factory shall refuse to construct the app and raise an error identifying the cause.
2. While `remote.enabled` is false, the application factory shall not perform this check at all, regardless of `WEB_CONCURRENCY`.
3. If `WEB_CONCURRENCY` is absent, empty, or does not parse as an integer, the application factory shall proceed without raising (fail open on absent/malformed signal, not fail closed by treating "unknown" as "unsafe" -- the check only acts on an unambiguous positive signal).
4. If `WEB_CONCURRENCY` parses to `1` or less, the application factory shall proceed without raising.

### Requirement 2: Operators can explicitly accept the risk
**Objective:** As an operator who has made an informed decision to run Remote Safe Mode under multiple workers anyway (understanding the consistency trade-off), I want an explicit configuration override, so that I am not permanently blocked by a check that cannot know my specific deployment is acceptable to me.

#### Acceptance Criteria
1. When a new configuration key explicitly acknowledging the risk is set to true, the application factory shall proceed even when the multi-worker signal from Requirement 1 is present.
2. The configuration key shall default to false/absent, so the guard is active by default for every existing deployment.

### Requirement 3: The limitation and the override are documented
**Objective:** As an operator reading the deployment documentation, I want the single-process constraint and how to override it explained where the rest of the Remote deployment guidance lives, so that I understand why the server refused to start and what my options are.

#### Acceptance Criteria
1. `docs/en/remote.md` and `docs/ja/remote.md` shall state that Remote Safe Mode's rate limiting and browser-session store are process-local, name the specific consequence (inconsistent throttling and session state across workers), and document the `WEB_CONCURRENCY` detection and the override key.
2. The documentation shall state plainly that detection is best-effort and does not cover every possible multi-worker deployment topology, so operators do not read the guard's silence as a guarantee of single-worker deployment.
