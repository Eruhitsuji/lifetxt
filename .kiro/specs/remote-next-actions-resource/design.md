# Design Document

## Overview

**Purpose**: Expose `lifetxt.nextaction.next_action_items` (already the shared CLI/TUI/MCP actionable-item definition) as a new `next` resource in Remote Safe Mode's read-resource catalog, so a remote Web/CLI/MCP client sharing one server can ask "what's actionable for me" without reimplementing the logic against raw item data.

**Users**: Remote clients on a trusted local network -- a person's browser or `lifetxt remote` CLI/TUI session, or an MCP-driven AI agent connected through a Remote-backed transport.

**Impact**: Purely additive: one new resource name, one new builder function, one new catalog entry. No existing resource, permission rule, or write path changes.

### Goals
- `next` becomes a valid resource name accepted by `read_resource()`.
- Its output is the actionable-item set computed over the same permission-filtered items every other resource already receives, using `next_action_items` unmodified.
- It's discoverable through `resource_catalog()` like every other resource.

### Non-Goals
- Changing `nextaction.py`'s actionable/blocking logic.
- Any write/mutation path for next-actions.
- Cross-file dependency-reason disclosure beyond what `next_action_items`/`blocked_map` already do (no `dependency_unknown`-style reason codes here -- out of scope, matches this resource's existing sibling `dependency-universe` work only for ticket-project reports, not next-actions).

## Boundary Commitments

### This Spec Owns
- `remote_backend._resource_next` (new function).
- The `next` entries in `RESOURCE_NAMES`, `resource_catalog()`, and `_BUILDERS`.

### Out of Boundary
- `lifetxt.nextaction` itself -- consumed unmodified.
- `_visible_items`/permission filtering -- consumed unmodified; `read_resource()` already computes `visible` before calling any builder, so `_resource_next` receives the same filtered list `_resource_items`/`_resource_tickets` do.
- `_item_rows` -- consumed unmodified for row shaping (redaction, `editable: false`, dropped `source`/`text`/`markdown`).

### Allowed Dependencies
- `lifetxt.nextaction.next_action_items`
- `lifetxt.ids.id_key_from_config`, imported and called locally the same way `_resource_links` (remote_backend.py:322-327) already does, to get the key `next_action_items` needs independently of `_item_rows`'s own internal key lookup
- `remote_backend._int`, `remote_backend._item_rows` (existing helpers)

### Revalidation Triggers
- If `next_action_items`'s parameter names or filtering semantics change, this resource's parameter list must be revisited.
- If `_item_rows`'s row shape changes, this resource's response shape changes with it automatically (shared code, not duplicated).

## File Structure Plan

### Modified Files
- `lifetxt/remote_backend.py` -- add `_resource_next`, register in `RESOURCE_NAMES`, `resource_catalog()`, `_BUILDERS`.
- `tests/test_remote_backend_v20.py` (existing home for this module's resource tests, per `cap-remote-tickets-pagination`/`cap-remote-ticket-detail-view`) -- new test class.
- `docs/en/remote.md`, `docs/ja/remote.md` -- add `next` to the resource list.

No new files; no schema changes (reuses `remote-read-response-v1.schema.json`'s existing generic envelope, same as `items`/`agenda`).

## Requirements Traceability

| Requirement | Design Element |
| --- | --- |
| 1.1, 1.4 | `_resource_next(items, config, params)` calls `next_action_items(items, key=..., ...)` where `items` is already the `visible` list `read_resource()` passes to every builder |
| 1.2 | `params.get("project")`, `params.get("assignee")` passed straight through; `params.get("limit")` bounded via `_int` |
| 1.3 | `_int(params.get("limit"), default=None, minimum=0, maximum=1000, name="limit")` -- mirrors `_resource_search`'s existing bound (1000), tighter than `tickets`' 5000 default max since next-actions are meant to be a short, actionable list, not a full listing |
| 2.1 | `RESOURCE_NAMES` gains `"next"`; `resource_catalog()` gains `{"name": "next", "parameters": ["project", "assignee", "limit"]}` |
| 3.1 | Return shape `{"count": len(rows), "items": _item_rows(rows, config)}`, identical shape to `_resource_items`'s return |
| 3.2 | No change needed: `read_resource()` wraps every builder's output in the same envelope already |

## Components and Interfaces

### `remote_backend._resource_next(items, config, params)`
```python
def _resource_next(items, config, params):
    from .nextaction import next_action_items
    from .ids import id_key_from_config

    key = id_key_from_config(config or {})
    limit = _int(params.get("limit"), default=None, minimum=0, maximum=1000, name="limit")
    rows = next_action_items(
        items,
        key=key,
        limit=limit,
        project=params.get("project"),
        assignee=params.get("assignee"),
    )
    return {"count": len(rows), "items": _item_rows(rows, config)}
```
Placed alongside `_resource_agenda`/`_resource_search`, before `_BUILDERS`.

## Testing Strategy

- Unit: `read_resource("next", paths, config, principal, params)` returns only actionable items (open/in-progress status, no someday/waiting tag, not blocked), matching `next_action_items`'s own converged definition -- reuse fixtures from `tests/test_nextaction.py`/`tests/test_extra_cli.py` where practical rather than re-deriving the actionable-item rules.
- Unit: an item blocked by a dependency the principal cannot see (private/invisible target) is excluded (blocked), not silently promoted to actionable -- direct test of the "conservative on invisible blockers" boundary decision.
- Unit: `project`/`assignee`/`limit` parameters filter as expected; an invalid `limit` (negative, non-integer, over 1000) raises `RemoteAccessError` the same way `_resource_search`'s limit does.
- Unit: `next` appears in `resource_catalog()`'s output.
- Live verification: start a real `lifetxt serve` process with `remote.enabled: true`, request `/api/remote/v1/resources/next` with a real bearer token, and read the actual response body.
