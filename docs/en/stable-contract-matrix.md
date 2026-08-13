# Stable Machine-Readable Contract Matrix

This matrix is the bounded inventory for #323. A schema is considered covered
only when the authoritative implementation emits or validates the contract and
the release policy publishes a versioned schema. Deferred surfaces are listed
as exceptions rather than inferred to be stable from a partial schema.

| Contract family | Authoritative surface | Schema evidence | Status |
| --- | --- | --- | --- |
| life item JSON/JSONL records | `lifetxt.serializer` | `item-v1`, `json-export-v1` | covered |
| diagnostics | `lifetxt.diagnostic_contract` | `diagnostic-v1` | covered; end-span completion remains #324 |
| capability and release reports | `surface_runtime`, `release_policy` | `capability-v1`, `release-manifest-v1` | covered |
| configuration and conflict responses | `config_writer`, mutation contract | `config-v1`, `conflict-v1` | covered |
| archive, attachment, and transaction operations | archive/attachment/transaction modules | corresponding `*-v1` schemas | covered |
| ticket, workflow, event, time-entry, version, and sprint records | ticket registries and surfaces | corresponding `ticket-*-v1` schemas | covered where the support matrix advertises the surface |
| Web endpoint-specific envelopes | `lifetxt.webapp` and route modules | `item-v1` for `/api/items` and `/api/items/{line_no}`; stable error envelope is asserted by focused tests | bounded read slice covered; other route groups remain follow-up work |
| MCP tool result envelopes | `lifetxt.mcp` tool registry | `item-v1` for `list_items` and `get_item` results | bounded read slice covered; deferred/write tools are not stable by default |
| experimental or deferred features | support matrix classification | no stable schema promised | explicit exception |

The schema version is `1`. The selected Web/MCP read slice tolerates additive
producer fields and preserves the stable error keys `error`, `message`, and
`detail`. Adding a stable contract or changing a response shape requires a
versioned schema decision and a compatibility-policy update.
