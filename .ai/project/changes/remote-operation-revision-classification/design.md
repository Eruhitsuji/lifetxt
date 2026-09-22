# Design

## Summary

Maintain an explicit classification for every mutating Remote v1 route.
Operational and session controls are added to the existing shared Web
no-revision registry. Both the compatibility fallback middleware and the
persistent required-mode middleware consult that same registry at request time.

## Security Boundary

The backup route remains protected by Remote protocol negotiation,
authentication, the `backup:run` scope, browser CSRF/origin checks, idempotency,
audit admission, one-active-run admission, cooldown, fixed service dispatch,
and bounded result tracking. Only an irrelevant whole-file revision check is
removed. The authoritative ticket-mutation route is classified separately and
continues to enforce its own exact `If-Match` and per-file CAS contract.

## Alternatives

- Exempt only the persistent middleware was rejected because the inner
  compatibility middleware would still inject a synthetic revision and record
  a fallback.
- Exempt all `/api/remote/v1/**` routes was rejected because ticket mutations
  authoritatively change life.txt data.
- Add an `If-Match` header in the browser was rejected because it would hide
  the route-classification defect and create a false dependency on life.txt.

## Rollback

Revert the shared-registry and classification changes. If deployment reveals a
regression, disable Remote backup admission while retaining scheduled backups.
