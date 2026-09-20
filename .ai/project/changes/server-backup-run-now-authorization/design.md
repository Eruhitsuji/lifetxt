# Design

## Outcome

Do not add a run-now route to the ordinary Web application. A future operation
may be added only to Remote Safe Mode as
`POST /api/remote/v1/operations/backup-runs`, guarded by a new explicit
`backup:run` scope. The endpoint admits an asynchronous request and dispatches
only the already generated `lifetxt-backup.service`; that service continues to
execute `lifetxt backup run-scheduled --config ...`.

This package records a design decision for #868. It intentionally contains no
runtime implementation. Server-side implementation is #870 and an optional
authenticated Remote browser control is #871; both remain blocked pending
owner approval.

## Existing boundaries examined

| Surface | Existing property | Run-now conclusion |
| --- | --- | --- |
| Ordinary Web (`lifetxt.webapp`) | Broad local/trusted-LAN editing surface; deployment may put authentication in a reverse proxy, but the application has no principal/scope authorization model | Keep status-only. Proxy authentication alone cannot authorize an operational mutation. |
| Remote Safe Mode (`lifetxt.remote_web`) | Authenticated principals, scopes, HTTPS enforcement, protocol negotiation, browser CSRF/Origin protection, per-principal rate limiting, request IDs, and structured audit | Only acceptable HTTP trust boundary, with a new explicit scope. |
| Backup orchestration (`lifetxt.backup_cli.run_scheduled`) | Resolves configured sources/destination, uses one exclusive destination lock, records local and remote outcomes independently, then applies configured retention | Reuse unchanged; do not build a second backup path. |
| Generated `lifetxt-backup.service` | Hardened one-shot unit with fixed executable and config path | Use as the only dispatch target; never accept a unit or command from the request. |
| Generic server service control | Operationally powerful and intentionally narrow | Do not expose arbitrary service-control input or broaden its allowlist. |

## Interface and authorization

The future server operation is `POST /api/remote/v1/operations/backup-runs`.
It has no body fields that alter backup configuration. The server derives the
configured service and operation entirely from trusted deployment state.

Authorization requires all of the following:

1. Remote Safe Mode is enabled and the negotiated protocol version advertises
   the operation (planned protocol v2).
2. A valid bearer or browser-session principal is present.
3. That principal is granted `backup:run` explicitly. The scope is not included
   transitively in the existing owner/admin/write roles.
4. Browser-session requests pass the existing CSRF and Origin checks.
5. Generic and operation-specific rate limits pass.
6. The fixed backup runner and durable audit sink are available.

Any missing precondition refuses before service dispatch. Reverse-proxy-only
operators continue to use `systemctl start lifetxt-backup.service` or the CLI.

## Admission and lifecycle

- A client sends an idempotency key. Repeating the same principal/key pair
  returns the same operation admission instead of starting another unit.
- A separate admission lock/state prevents multiple accepted requests from
  accumulating while systemd has not yet begun the one-shot service. The
  destination lock inside `run_scheduled` remains defense in depth for timer,
  CLI, and HTTP races.
- The operation-specific budget starts at one admitted run per principal per
  15 minutes. It is independent of the generic request budget.
- Acceptance returns `202 Accepted` with an opaque operation ID and a
  secret-free status URL. Execution never blocks the HTTP request.
- Status is bounded to admitted/running/completed/refused and normalized local
  and remote outcomes. It excludes paths, remote targets, credentials, raw
  adapter errors, process output, and journal contents.
- Local success remains success even if remote upload fails. The UI must not
  collapse that case into total failure or claim off-host protection.

## Audit and failure behavior

Every accepted and rejected attempt uses the existing Remote audit path and
records the authenticated principal, request ID, operation ID when allocated,
decision/outcome, and a stable sanitized reason. It does not record request
secrets, paths, targets, raw stderr, or credentials. Audit unavailability is a
pre-dispatch failure, not a reason to run without evidence.

The endpoint fails closed when Remote Safe Mode, the scope, protocol feature,
runner, admission store, or audit store is unavailable. A dispatch failure is
reported as a sanitized operation failure. The timer and CLI retain their
existing behavior and do not depend on the HTTP surface.

## UI boundary

The ordinary Web Server view introduced by #867 remains read-only. A button may
later be added only to authenticated `/remote` by #871 and only when both the
server capability and `backup:run` scope are visible. It must confirm that the
configured run can create locally, upload off-host, and prune according to
retention; submit a fresh idempotency key; handle `202`; and show local/remote
results separately.

## Required security test matrix for #870/#871

- Missing, invalid, expired, and revoked credentials.
- Every existing role and scope combination, proving no implicit grant.
- Browser CSRF/Origin absence and mismatch.
- Unsupported protocol/capability negotiation.
- Repeated idempotency key, double click, concurrent distinct keys, timer race,
  CLI race, and already-running service.
- Generic and dedicated rate-limit exhaustion.
- Missing runner, missing audit sink, dispatch failure, process failure, local
  success/remote failure, and total failure.
- Sanitization of paths, remote names, credentials, argv, stderr, and journal
  content in API responses and audit events.
- Single-worker guard behavior and restart/recovery behavior of admission state.
- Confirmation, keyboard accessibility, and mobile layout for the Remote UI.

## Non-goals

No restore, prune, delete, arbitrary upload, arbitrary command/service start,
schedule editing, source selection, destination selection, or credential
management is exposed. This decision does not change backup format v1 or
scheduled backup semantics.
