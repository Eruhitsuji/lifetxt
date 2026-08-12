# Stable Web and MCP Schema Validation

The bounded #404 validation slice covers the read-only item listing surfaces:

| Surface | Operation | Schemas | Status |
| --- | --- | --- | --- |
| Web | `GET /api/items` | `item-v1.schema.json`; shared diagnostic key contract | validated in `tests/test_stable_surface_schemas.py` |
| MCP | `list_items` | `item-v1.schema.json`; shared diagnostic key contract | validated in `tests/test_stable_surface_schemas.py` |

Both tests exercise a valid response and a response containing a parser
diagnostic. Item payloads are validated directly against the versioned schema
bundle. Diagnostic payloads are checked against the current shared diagnostic
contract because `diagnostic-v1.schema.json` still requires `source`, `column`,
and `span` fields that are not emitted for every existing diagnostic family;
that mismatch remains a follow-up rather than being hidden by this test.

This slice deliberately excludes write endpoints, browser-engine behavior,
Remote operations, and experimental/deferred MCP tools. The remaining Web
route groups and MCP read tools are not silently considered covered; they remain
follow-up work in the stable contract matrix.
