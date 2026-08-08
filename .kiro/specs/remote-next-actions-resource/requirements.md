# Requirements Document

## Project Description (Input)
The user is deploying one lifetxt server on a trusted local network for multiple clients (Web browser, CLI/TUI via `lifetxt remote` profiles, and MCP/AI agents) to view and edit shared data. `lifetxt.nextaction` already defines the single, shared "what should I work on next" logic used by CLI `next`, the TUI `/next` view, and the MCP `get_next_actions` tool (`cap-next-actionable-convergence`), but Remote Safe Mode's read-resource catalog (`lifetxt/remote_backend.py` `RESOURCE_NAMES`/`_BUILDERS`) does not expose it -- confirmed by grepping `remote_backend.py`/`remote_web.py`/`remote_compatibility_v21.py` for any reference to `nextaction`/`next_action` and finding none. A remote client (a person on another machine, or an MCP-driven AI agent) currently has no permission-aware way to ask the shared server "what's actionable right now" without building the equivalent of `next_action_items` themselves against the raw `items`/`tickets` resources. This matches `todo.md`'s "P1: Remote Safe Mode and Remote Workspace Access" line 160: "Expand permission-aware read-only resource coverage to the remaining safe local surfaces: item show/filter/review/next..." Add a `next` read resource to the existing catalog, reusing `lifetxt.nextaction.next_action_items` unmodified against the same permission-filtered item set every other resource already uses, with `project`/`assignee`/`limit` parameters mirroring the function's own filters. This is read-only and reuses the existing shared actionable-item definition and existing permission-filtering pipeline, so it stays Standard assurance.

## Boundary Context

- **In scope**: A new `next` resource in `remote_backend.py`'s catalog, its parameters, its registration in `RESOURCE_NAMES`/`resource_catalog()`/`_BUILDERS`, and its response shape.
- **Out of scope**: Any change to `lifetxt.nextaction`'s actionable-item definition itself (already converged and tested elsewhere). Any write/mutation capability for next-actions. Any change to how blocking is computed -- this resource passes the already permission-filtered item set into the existing `next_action_items`/`blocked_map` functions unmodified, so a blocker the requesting principal cannot see is conservatively treated as blocking (an unresolved `depends_on:` reference in the filtered set), matching the project's existing "do not guess toward exposure/actionability" discipline used elsewhere (e.g. `cap-ticket-dependency-universe`'s `dependency_unknown` handling).
- **Adjacent expectations**: Depends on `lifetxt.nextaction.next_action_items` and the existing `_visible_items`/`_item_rows`/`redact_remote_value` pipeline in `remote_backend.py` remaining stable; does not introduce a new permission model.

## Requirements

### Requirement 1: A permission-aware "next actions" Remote resource exists
**Objective:** As a Remote client (Web/CLI/MCP) connected to a shared lifetxt server, I want to request the actionable items relevant to me, so that I don't have to reimplement the actionable-item definition myself against raw item/ticket data.

#### Acceptance Criteria
1. When a Remote client requests the `next` resource, the server shall return the same set of actionable items `lifetxt.nextaction.next_action_items` would compute over the principal's permission-filtered item set.
2. The `next` resource shall accept `project`, `assignee`, and `limit` parameters with the same filtering semantics `next_action_items` already implements.
3. If an unsupported parameter value is supplied for `limit` (non-integer, negative, or above the resource's maximum), the server shall reject the request the same way other bounded resources in this catalog already do.
4. The `next` resource shall never include an item the requesting principal cannot otherwise see via any other resource in this catalog.

### Requirement 2: The resource is discoverable
**Objective:** As a Remote client, I want to discover the `next` resource and its parameters through the existing capability/resource-catalog mechanism, so that I don't need out-of-band documentation to find it.

#### Acceptance Criteria
1. The `next` resource shall appear in `RESOURCE_NAMES` and in the list returned by `resource_catalog()`, alongside its accepted parameters.

### Requirement 3: Response shape is consistent with the rest of the catalog
**Objective:** As a Remote client author, I want the `next` resource's response envelope to look like every other resource's, so that my client code does not need resource-specific unwrapping logic.

#### Acceptance Criteria
1. The `next` resource's data payload shall follow the same `{"count": N, "items": [...]}` shape `items`/`tickets` already use, with each row built through the existing `_item_rows` (structured item representation, redacted, non-editable) rather than a new row format.
2. The overall response shall carry the same envelope (`schema`, `resource`, revision, generated-at) every resource already receives from `read_resource()` unmodified.
