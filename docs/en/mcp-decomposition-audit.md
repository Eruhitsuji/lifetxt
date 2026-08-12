# MCP Decomposition Audit

Issue: #369  
Related: #360, #368  
Implementation follow-up: #387

## Responsibility Map

| Cluster | Current symbols | Boundary | Risk |
| --- | --- | --- | --- |
| Transport and dispatch | `run_stdio_server`, `handle_request`, `call_tool` | JSON-RPC/protocol infrastructure | High: preserve malformed-request errors and IDs |
| Context and startup | `McpContext`, `cmd_mcp` | Session/configuration state | High: preserve paths, revision policy, and server identity |
| Schemas and registry | `tool_schemas`, `TOOL_HANDLERS`, tool sets | Public MCP contract | High: preserve names, descriptions, and capability behavior |
| Resources/prompts | `resource_list`, `resource_read`, `prompt_list`, `prompt_get` | Stable read surface | Medium: first extraction candidate |
| Domain read handlers | `_tool_list_items`, `_tool_get_item`, agenda/graph/search handlers | Protocol-neutral service consumers | Medium: follow #368 ownership decisions |
| Mutations and delegated writes | create/update/delete/message/attachment handlers | Safety-sensitive mutation boundary | High: defer until read extraction is proven |

The first XS/S seam is the read-resource handler cluster, tracked by #387.
It keeps the transport and registry in `mcp.py` and preserves protocol and
schema behavior while depending on the shared-service decisions from #368.

## Compatibility Rules

Keep server name/version, initialize negotiation, JSON-RPC error mapping,
malformed-request containment, stable read schemas, and write refusal behavior
unchanged. No protocol rewrite or MCP write promotion is included.
