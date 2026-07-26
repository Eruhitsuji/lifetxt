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
