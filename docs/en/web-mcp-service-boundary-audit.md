# Web/MCP Shared Service Boundary Audit

Issue: #368  
Follow-up implementation: #385

## Scope

This audit covers the functions imported from `lifetxt.webapp` by
`lifetxt.mcp`, plus the other non-Web consumers found in the repository. It is
an ownership inventory only; no code is moved by #368.

## Import Inventory

| Function group | Current owner | Boundary classification | Other consumers | Decision |
| --- | --- | --- | --- | --- |
| `read_life_inputs`, `find_item_by_id`, `sort_items`, `limit_items` | `webapp.py` | Protocol-neutral read | `remote_backend.py`, `query.py`, tests | Candidate for shared read service |
| `items_response`, `links_response`, `api_item` | `webapp.py` | Web/MCP response shaping | `mcp.py`, Web handlers, tests | Keep response schemas at the protocol boundary until a schema-preserving adapter exists |
| `item_from_payload`, `message_item_from_payload`, `message_reply_from_payload` | `webapp.py` | Protocol-neutral mutation parsing | `mcp.py`, Web handlers, tests | Candidate for shared input/parser service |
| `append_item_to_file`, `update_item_by_id_in_file`, `delete_item_by_id_from_file` | `webapp.py` | Protocol-neutral mutation with write safety | `mcp.py`, Web handlers, tests | Candidate for shared mutation service; preserve revision and atomic-write checks |
| `read_text`, `write_text` | `webapp.py` | Protocol-neutral storage primitive | `mcp.py`, `surface_runtime.py`, tests | Extract only with transaction and compatibility coverage |
| `assign_auto_id_from_paths`, `auto_id_paths`, `normalize_server_paths` | `webapp.py` | Configuration/path policy | `mcp.py` and server setup | Keep policy centralized until its callers are split |
| `ack_message_in_file`, `snooze_message_in_file` | `webapp.py` | Protocol-neutral message mutation | `mcp.py`, Web handlers | Candidate for a later mutation cluster |
| `_subgraph` | `webapp.py` | Protocol-neutral graph read | `mcp.py` | Extract only with graph output and diagnostic tests |

## Ownership And Compatibility

The first shared ownership location should be a small protocol-neutral service
module, with no HTTP, MCP, or response-schema dependencies. It must accept the
same parsed inputs and return the same domain objects or diagnostics used today.
`webapp.py` remains the owner of HTTP routing and compatibility names; during
the transition it should re-export or delegate old helper names so existing Web
handlers, MCP imports, tests, and third-party imports do not change at once.

The extraction must retain:

- Web and MCP response schemas and diagnostic fields.
- revision checks, writable-path policy, and atomic write behavior.
- path normalization and ID assignment semantics.
- `surface_runtime` transaction wrappers around text reads and writes.

## First XS/S Extraction

The first extraction is the read-only cluster `read_life_inputs`,
`find_item_by_id`, `sort_items`, and `limit_items`, with `webapp.py` delegating
to the new service and retaining compatibility imports. #385 owns this code
change and its focused cross-surface tests. Response shaping and mutation
helpers remain in `webapp.py` until their contracts are covered by separate
implementation issues.

## Out Of Scope

This audit does not refactor routes, change MCP protocol behavior, promote MCP
writes, or move code. Those changes require the follow-up issue's acceptance
criteria and a separate review of write safety and compatibility.
