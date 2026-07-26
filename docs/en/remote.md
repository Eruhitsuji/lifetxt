# Remote Safe Mode

Remote Safe Mode exposes a deliberately small authenticated HTTP surface for reading life.txt data and for validating revision-aware writes. It is disabled by default.

## Security model

Enable it with `remote.enabled: true`. Every remote request must authenticate as a configured principal. Principals use one of four roles: `owner`, `editor`, `reader`, or `auditor`. Roles expand to explicit `read`, `write`, `admin`, and `audit` scopes. Project and visibility grants are checked in addition to scopes.

Bearer secrets are never stored directly in configuration. Set `token_env` on a principal and place the secret in that environment variable. A trusted reverse proxy may assert `X-Lifetxt-Principal` only when the direct peer address belongs to `remote.trusted_proxies`; asserted IDs must already exist in the principal registry.

HTTPS is mandatory outside loopback. `remote.allow_loopback_http` exists only for local development. Browser UI remains disabled unless `remote.browser_ui` is explicitly enabled.

Every remote write requires an exact `If-Match` revision. Missing revisions return `REVISION_REQUIRED`; stale revisions return `REVISION_CONFLICT`. Remote routes attach request IDs, apply per-principal rate limits, redact absolute local paths, and can append bounded JSONL audit events.

## Configuration example

```json
{
  "remote": {
    "enabled": true,
    "allow_loopback_http": false,
    "rate_limit_per_minute": 120,
    "audit_log": ".cache/lifetxt/remote-audit.jsonl",
    "principals": [
      {
        "id": "alice",
        "role": "editor",
        "token_env": "LIFETXT_REMOTE_ALICE_TOKEN",
        "projects": ["web"],
        "visibilities": ["public", "shared"]
      }
    ],
    "trusted_proxies": ["10.0.0.0/8"]
  }
}
```

## Remote HTTP routes

- `GET /api/remote/v1/capabilities`
- `GET /api/remote/v1/session`
- `GET /api/remote/v1/snapshot`
- `GET /api/remote/v1/tickets`
- `GET /api/remote/v1/projects`
- `GET /api/remote/v1/audit`
- `POST /api/remote/v1/write-check`

The write-check route verifies authenticated write scope and exact revision handling without mutating authoritative data. Ticket mutations remain routed through existing exact-revision ticket contracts.

## Dependency-free client

```console
lifetxt remote profile-set home https://life.example.test --token-env LIFETXT_REMOTE_TOKEN
lifetxt remote profile-list
lifetxt remote test home
lifetxt remote snapshot home
lifetxt remote export home snapshot.json
lifetxt remote tui home
```

Profiles store only the server URL, TLS preference, and the environment-variable name containing the token. The read-only remote TUI renders snapshots without adding a Web dependency.
