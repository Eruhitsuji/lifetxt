# Remote compatibility negotiation

Remote protocol version 2 publishes an explicit compatibility manifest from `GET /api/remote/v1/capabilities`. The manifest supplements the minimum/current protocol headers and the capability revision; it does not enable remote writes.

This document covers `lifetxt/remote_compatibility_v21.py`, the module that builds the manifest and the `evaluate_compatibility()` report. See [remote.md](remote.md) for the resource catalog the same capability document also advertises (`roles`, `resources`, `authentication`), and [remote-client-writes.md](remote-client-writes.md) for how `lifetxt remote test`/`lifetxt remote permissions` present this data at the CLI.

## Published metadata

`install_remote_compatibility_v21()` wraps the server's base capability builder: it keeps every field the base document already publishes (`protocol`, `roles`, `resources`, `authentication`, `mutation_policy`, `features`, and so on -- see [remote.md](remote.md) and [remote-ticket-writes.md](remote-ticket-writes.md)) and layers five additional top-level fields on top, then recomputes `capability_revision` over the merged payload:

- `server`: the package name and server package version.
- `schema_bundle`: the exact number of published schemas and a SHA-256 revision of the canonical schema bundle.
- `contracts`: discovered minimum/current schema versions and exact schema names for configuration, workspace manifests, transaction journals/policies, clock handling, ticket/custom-field/workflow/event/time/planning contracts, attachments, and Remote resources.
- `optional_dependencies`: whether the declared Web (`fastapi`, `uvicorn`) and TUI (`textual`, `watchdog`) dependency groups are available in the running process.
- `compatibility`: the client rules for unknown fields, missing optional features, removed features, future protocols, and explicit downgrade selection.

All metadata is aggregate. It contains no local paths, credentials, source text, parser messages, or record contents. The compatibility fields participate in `capability_revision`, so a client can detect a changed server contract without comparing the complete payload.

`contracts` recognizes exactly twelve domain names (`lifetxt/remote_compatibility_v21.py`'s `_CONTRACT_PATTERNS`): `configuration`, `workspace_manifest`, `transaction_journal_policy`, `clock`, `ticket`, `ticket_custom_field`, `ticket_workflow`, `ticket_event`, `time_entry`, `ticket_planning`, `attachment`, and `remote_resource`. Each domain's `minimum`/`current`/`schemas` are derived by scanning every published schema filename for a substring pattern (`ticket-workflow` for the `ticket_workflow` domain, `attachment`/`directory-package`/`package-manifest` for `attachment`, and so on) -- there is no hand-maintained, mutually-exclusive mapping. Verified against a real running server, this means one schema file can legitimately satisfy more than one domain at once: `ticket-version-v1.schema.json` appears in both the `ticket` domain's schema list (it contains the substring `ticket-v`) and the `ticket_planning` domain's schema list (it also contains `ticket-version`). A caller checking `required_contracts=["ticket_planning"]` for presence only needs that one schema published, not a `ticket-planning`- or `ticket-sprint`-named schema specifically.

## Client behavior

A client should calculate the overlap between its supported protocol range and the server's minimum/current range. It may proceed only when the requested protocol is inside that overlap. Unknown capability fields are ignored. Missing optional dependencies disable the corresponding feature. Removed features must fail explicitly rather than silently falling back. Unsupported future protocol numbers continue to fail with `REMOTE_VERSION_UNSUPPORTED`.

`lifetxt remote test PROFILE` includes a deterministic compatibility report with the client and server ranges, overlap, selected protocol, manifest presence, and warnings for older or newer servers. Protocol version 1 remains supported as the headerless compatibility default and does not require the expanded manifest. Verified against a real server (client and server both at protocol 2), the report looks like this:

```json
{
  "ok": true,
  "status": "compatible",
  "requested_protocol": 2,
  "client": {"minimum": 1, "current": 2},
  "server": {"minimum": 1, "current": 2},
  "overlap": [1, 2],
  "selected_protocol": 2,
  "manifest_present": true,
  "warnings": [],
  "header_status": "present-and-consistent"
}
```

## Domain-aware contract warnings

Callers that depend on a specific published contract domain (for example `ticket_workflow` or `attachment`) can pass `required_contracts` to `evaluate_compatibility()`: either a list of domain names for a presence-only check, or a mapping of domain name to minimum required version for a presence-and-version check. Each domain that is absent, unavailable, or below its required minimum version adds one warning naming that domain to the compatibility report. An unknown domain name (one not published by `contracts`) raises an error immediately rather than warning silently forever. This check is purely client-side and advisory: the server never rejects a request based on it, and omitting `required_contracts` leaves the report unchanged.

Calling `evaluate_compatibility()` directly against a real capability document confirms the exact warning and error text a caller should expect:

```pycon
>>> evaluate_compatibility(caps, required_contracts={"ticket_workflow": 99})["warnings"]
["Required contract 'ticket_workflow' is at version 1, below the required minimum 99."]
>>> evaluate_compatibility(caps, required_contracts=["not_a_real_domain"])
ValueError: Unknown required contract domain(s): not_a_real_domain. Valid domains: attachment, clock,
configuration, remote_resource, ticket, ticket_custom_field, ticket_event, ticket_planning,
ticket_workflow, time_entry, transaction_journal_policy, workspace_manifest.
```

`required_contracts` is a parameter of the shared `evaluate_compatibility()` function, not exposed as its own `lifetxt remote` CLI flag today -- a client that wants this check has to call the Python function directly (as `lifetxt/remote_compatibility_v21.py`'s own test suite does) or reimplement the same presence/version comparison against the `contracts` field it already receives inside `lifetxt remote test PROFILE`'s `capabilities` object.

## Capability-revision header integrity

The `X-Lifetxt-Remote-Capability-Revision` header and the capability body's own `capability_revision` field are set from the same server-computed value, so a client can detect a reverse proxy or cache that strips or rewrites the header by comparing the two. `lifetxt remote test` reports a `header_status` field: `"present-and-consistent"` when both agree, `"missing"` when the header was absent from the response, or `"mismatch"` when the header disagrees with the body — the latter two also add a warning to the compatibility report.

This field only appears in `evaluate_compatibility()`'s output when the caller passes `capability_revision_header` at all (passing `None` explicitly still reports `"missing"`; omitting the parameter entirely skips the check and the key is absent from the result). `install_remote_client_compatibility_v21()` wires `lifetxt remote test` to always pass this parameter (using the response's actual `X-Lifetxt-Remote-Capability-Revision` header value), so in practice every `lifetxt remote test` report includes `header_status` -- the omitted-parameter case only matters for code calling `evaluate_compatibility()` directly, such as the compatibility checks other surfaces (a future TUI or MCP compatibility check) might add independently. Verified directly: passing a header value that does not match the body's `capability_revision` produces `"mismatch"` and the warning `"Capability-revision header does not match the response body; a proxy may be rewriting or caching it."`; passing `None` produces `"missing"` and `"Capability-revision header is missing from the response; a proxy may be stripping it."`; passing the matching value produces `"present-and-consistent"` with no added warning.
