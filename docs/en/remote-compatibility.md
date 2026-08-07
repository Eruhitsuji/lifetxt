# Remote compatibility negotiation

Remote protocol version 2 publishes an explicit compatibility manifest from `GET /api/remote/v1/capabilities`. The manifest supplements the minimum/current protocol headers and the capability revision; it does not enable remote writes.

## Published metadata

The capability response includes:

- `server`: the package name and server package version.
- `schema_bundle`: the exact number of published schemas and a SHA-256 revision of the canonical schema bundle.
- `contracts`: discovered minimum/current schema versions and exact schema names for configuration, workspace manifests, transaction journals/policies, clock handling, ticket/custom-field/workflow/event/time/planning contracts, attachments, and Remote resources.
- `optional_dependencies`: whether the declared Web (`fastapi`, `uvicorn`) and TUI (`textual`, `watchdog`) dependency groups are available in the running process.
- `compatibility`: the client rules for unknown fields, missing optional features, removed features, future protocols, and explicit downgrade selection.

All metadata is aggregate. It contains no local paths, credentials, source text, parser messages, or record contents. The compatibility fields participate in `capability_revision`, so a client can detect a changed server contract without comparing the complete payload.

## Client behavior

A client should calculate the overlap between its supported protocol range and the server's minimum/current range. It may proceed only when the requested protocol is inside that overlap. Unknown capability fields are ignored. Missing optional dependencies disable the corresponding feature. Removed features must fail explicitly rather than silently falling back. Unsupported future protocol numbers continue to fail with `REMOTE_VERSION_UNSUPPORTED`.

`lifetxt remote test PROFILE` includes a deterministic compatibility report with the client and server ranges, overlap, selected protocol, manifest presence, and warnings for older or newer servers. Protocol version 1 remains supported as the headerless compatibility default and does not require the expanded manifest.

## Domain-aware contract warnings

Callers that depend on a specific published contract domain (for example `ticket_workflow` or `attachment`) can pass `required_contracts` to `evaluate_compatibility()`: either a list of domain names for a presence-only check, or a mapping of domain name to minimum required version for a presence-and-version check. Each domain that is absent, unavailable, or below its required minimum version adds one warning naming that domain to the compatibility report. An unknown domain name (one not published by `contracts`) raises an error immediately rather than warning silently forever. This check is purely client-side and advisory: the server never rejects a request based on it, and omitting `required_contracts` leaves the report unchanged.

## Capability-revision header integrity

The `X-Lifetxt-Remote-Capability-Revision` header and the capability body's own `capability_revision` field are set from the same server-computed value, so a client can detect a reverse proxy or cache that strips or rewrites the header by comparing the two. `lifetxt remote test` reports a `header_status` field: `"present-and-consistent"` when both agree, `"missing"` when the header was absent from the response, or `"mismatch"` when the header disagrees with the body — the latter two also add a warning to the compatibility report. This field only appears when the client opts into the check; it is absent from reports that do not request it.
