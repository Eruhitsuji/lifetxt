# Web Route Decomposition Audit

Issue: #371

## Current boundary

`lifetxt.webapp.create_app()` owns route registration, application state,
authentication, the read-only guard, exception normalization, and the route
handlers themselves. The current route inventory is:

- bootstrap and policy: `/`, `/api/time`, `/api/health`, `/api/config`,
  `/api/commands`, plus the read-only and bearer-auth middleware;
- core reads and validation: `/api/items`, `/api/links`, `/api/complete`,
  `/api/check-line`, `/api/items/parse`, `/api/graph`, `/api/blockers`;
- analytics: `/api/chart/tasks`, `/api/chart/habits`, `/api/chart/mood`,
  `/api/chart/elapsed`, `/api/chart/habits-heatmap`, and
  `/api/stats/summary`;
- review and planning: `/api/review`, `/api/agenda`, `/api/status`,
  `/api/notifications`;
- communication and work state: `/api/messages*`, `/api/timer`, and
  `/api/work-session`;
- mutation and storage: `/api/attachments*`, `/api/status` (POST),
  `/api/shorthand/parse`, `/api/items*`, and item completion/deletion routes.

The route functions close over `app.state`, so extraction must pass an explicit
state/dependency object or preserve a thin registration adapter. `create_app`
must remain the public factory. Middleware order and the exception handler are
application-wide concerns and are not part of the first route-group move.

## Compatibility invariants

Any extraction must preserve each route's method and path, status codes,
response shape, validation behavior, authentication and read-only decisions,
and the existing `create_app` import and factory contract. The dependency-free
core import path must not import FastAPI.

## First implementation slice

The first safe XS/S slice is the read-only analytics group: the five
`/api/chart/*` routes and `/api/stats/summary`. They share `lifetxt.stats`, do
not mutate workspace state, and have no message, timer, attachment, or item
write coupling. Keep registration in `create_app` through a compatibility
adapter until route-level parity tests cover paths, methods, representative
payloads, status codes, and auth/read-only behavior.

Follow-up implementation issue: #393 extracts this analytics group behind a
small router/registration helper, adds route-level parity coverage, and leaves
`create_app` as the stable application factory.
