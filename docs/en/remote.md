# Remote Safe Mode

Remote Safe Mode exposes a small authenticated read surface for life.txt workspaces. It is disabled by default, keeps authoritative files local, and does not enable authoritative remote mutations.

## Security model

Set `remote.enabled: true` to expose the Remote API. Every API request authenticates as a configured principal. The built-in roles are `owner`, `editor`, `reader`, and `auditor`; they expand to explicit `read`, `write`, `admin`, and `audit` scopes. Project, group, owner, and visibility grants are checked in addition to scopes.

Bearer secrets are never stored in configuration or client profiles. A principal references an environment variable through `token_env`. A trusted reverse proxy may assert `X-Lifetxt-Principal` only when the direct peer belongs to `remote.trusted_proxies`; forwarded protocol and host headers are trusted only from those peers.

Non-loopback access requires HTTPS. `remote.allow_loopback_http` exists only for local development. Absolute local paths, credential-shaped fields, raw source text, and detailed parser diagnostics are removed or redacted from Remote responses.

The audit sink must not be the authoritative life.txt input or writable file. Remote startup fails when `remote.audit_log` aliases an authoritative source.

## Protocol negotiation

Remote protocol version 1 remains the compatibility default when no version header is sent. New clients should request version 2:

```http
X-Lifetxt-Remote-Version: 2
```

Every API response includes:

```text
X-Lifetxt-Remote-Version
X-Lifetxt-Remote-Min-Version
X-Lifetxt-Remote-Capability-Revision
X-Request-ID
```

Unsupported versions fail with `REMOTE_VERSION_UNSUPPORTED` and HTTP 426. Version 2 adds browser sessions, CSRF/origin checks, the resource catalog, aggregate diagnostics, and capability revision negotiation.

## Configuration example

```json
{
  "remote": {
    "enabled": true,
    "browser_ui": true,
    "allow_loopback_http": false,
    "rate_limit_per_minute": 120,
    "browser_login_rate_limit_per_minute": 10,
    "browser_session_ttl_seconds": 28800,
    "browser_session_idle_seconds": 1800,
    "browser_session_max": 256,
    "session_cookie_name": "lifetxt_remote_session",
    "csrf_header": "X-CSRF-Token",
    "allowed_origins": ["https://life.example.test"],
    "audit_log": ".cache/lifetxt/remote-audit.jsonl",
    "audit_max_bytes": 5242880,
    "principals": [
      {
        "id": "alice",
        "role": "editor",
        "token_env": "LIFETXT_REMOTE_ALICE_TOKEN",
        "projects": ["web"],
        "groups": ["engineering"],
        "visibilities": ["public", "shared", "team"]
      }
    ],
    "trusted_proxies": ["10.0.0.0/8"]
  }
}
```

Set the secret outside the configuration file:

```console
export LIFETXT_REMOTE_ALICE_TOKEN='replace-with-a-random-secret'
```

`allowed_origins` accepts only bare HTTP(S) origins. Cookie and CSRF header names must be valid HTTP tokens. Invalid session configuration fails at server startup.

## Browser session

Enable `remote.browser_ui` and open `/remote`. The browser exchanges a Bearer token once for an opaque server-side session. The token is cleared from the page after login and is never written to local storage, session storage, cookies, profiles, responses, or audit details.

The session cookie is:

- opaque and server-side;
- `HttpOnly`;
- `SameSite=Strict`;
- `Secure` outside the explicit loopback-development exception;
- restricted to `/api/remote/`;
- invalidated by logout, principal removal/disablement, expiry, eviction, or server restart.

Unsafe browser-session requests require both the configured CSRF header and an exact allowed `Origin`. Login also requires an exact allowed origin and has a separate per-client rate limit. Logging in again rotates the cookie and revokes the previous session.

Browser-session endpoints require protocol version 2:

```text
POST /api/remote/v1/browser/login
GET  /api/remote/v1/browser/session
POST /api/remote/v1/browser/logout
```

## HTTP read surface

Compatibility routes:

```text
GET  /api/remote/v1/capabilities
GET  /api/remote/v1/session
GET  /api/remote/v1/snapshot
GET  /api/remote/v1/tickets
GET  /api/remote/v1/projects
GET  /api/remote/v1/audit
POST /api/remote/v1/write-check
```

Protocol-version-2 routes:

```text
GET /api/remote/v1/resources
GET /api/remote/v1/resources/{resource}
GET /api/remote/v1/diagnostics
```

The shared read backend currently publishes:

- `items`: visible items with text, type, project, open-only, and bounded-result filters;
- `tickets`: visible tickets filtered by project, status, and assignee, with bounded default-size cursor pagination (see below);
- `ticket-detail`: one visible ticket's full detail (fields, relations, incoming links, time totals), given its `id`; a nonexistent ID and an existing-but-invisible ID produce the identical `REMOTE_TICKET_NOT_FOUND` error;
- `projects`: project summaries derived from the same visible item set;
- `ticket-report`: the shared ticket/project aggregation contract;
- `links`: relation records filtered by ID, direction, and relation;
- `status`: latest visible status records;
- `agenda`: visible records in a bounded time range;
- `search`: safe search over visible items, projects, and people;
- `next`: actionable items from the same shared definition `lifetxt next`, the TUI `/next` view, and the MCP `get_next_actions` tool use, filtered by `project`, `assignee`, and a bounded `limit` (default unbounded, maximum 1000); an item blocked by a dependency the principal cannot see stays excluded rather than being promoted to actionable.

Unknown resources and unsupported parameters fail closed. All resources use the same principal filtering and source revision. Diagnostics contain aggregate severity/code counts and operational checks, not record text, source paths, or parser messages.

Example request:

```http
GET /api/remote/v1/resources/tickets?project=web&status=review&limit=50
Authorization: Bearer <token>
X-Lifetxt-Remote-Version: 2
```

### Tickets pagination

A `tickets` request without `limit` returns at most 200 tickets rather than every visible ticket; an explicit `limit` still behaves as before, up to the existing cap of 5000. The response's `data` gains two fields: `next_cursor` (the last returned ticket's ID, or `null` when this page reached the end of the visible set) and `has_more`. Pass `next_cursor` back as `cursor` to continue: only tickets sorting strictly after that ID are returned, in the resource's existing deterministic ID order.

A client paginating across several requests can optionally pass `since_revision` (the `revision` value from an earlier page). If the workspace changed since then, the request fails with `REMOTE_RESOURCE_REVISION_CHANGED` instead of silently returning a page mixed from a different revision; the client should restart pagination from the first page. Omitting `since_revision` preserves today's behavior exactly: each page independently reports its own `revision` with no consistency check.

```http
GET /api/remote/v1/resources/tickets?limit=50&cursor=TK-0050
Authorization: Bearer <token>
X-Lifetxt-Remote-Version: 2
```

This pagination contract currently applies only to `tickets`; every other resource above keeps its existing unbounded-unless-`limit`-is-given behavior.

## Dependency-free client

Profiles are stored with `remote-profile-v3`. A version-2 profile is migrated in memory to version 3 by adding TLS verification and protocol-version defaults. Profiles contain only the URL, TLS preference, protocol version, and token environment-variable name.

```console
lifetxt remote profile-set home https://life.example.test \
  --token-env LIFETXT_REMOTE_TOKEN \
  --protocol-version 2

lifetxt remote profile-list
lifetxt remote profile-show home
lifetxt remote test home
lifetxt remote resources home
lifetxt remote get home tickets --param project=web --param status=review
lifetxt remote diagnose home
lifetxt remote snapshot home
lifetxt remote export home snapshot.json
lifetxt remote tui home
lifetxt remote profile-remove home
```

The client sends a request ID, an offset-aware client timestamp, and the selected protocol version. It rejects a server that omits negotiation headers for protocol 2 or returns a different version.

## Write boundary

Every admitted remote write requires an exact `If-Match` revision. Missing revisions fail with `REVISION_REQUIRED`; stale revisions fail with `REVISION_CONFLICT`.

`POST /api/remote/v1/write-check` verifies authentication, write scope, browser-session CSRF/origin protection, and exact revision handling. It always returns `authoritative_mutation: false`. Authoritative Remote mutations remain disabled until an operation publishes and enforces complete permission, privacy, event-history, clock, idempotency, multi-target transaction, and recovery contracts.
