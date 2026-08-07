# Research & Design Decisions

## Summary
- **Feature**: `next-agenda-priority-ranking`
- **Discovery Scope**: Extension (light discovery)
- **Key Findings**:
  - `command_next`'s existing default sort is a fixed 4-key lexicographic tuple `(priority_key, due, created, line)`; there is no existing sort-strategy seam, so adding a second order requires one new branch, not a refactor.
  - `lifetxt/nextaction.py` documents itself as the *shared* actionable-item definition for `next`/TUI/MCP, but `command_next` does not actually use it — a real, pre-existing discrepancy, filed separately as #138 and explicitly kept out of this spec's boundary.
  - The project already has an established, reused pattern for "today" in this exact module (`timezone_today()`, used by `command_workload` and `command_someday` in `lifetxt/extra_core.py`), so this feature has no new decision to make about clock/timezone handling — it reuses the existing call.

## Research Log

### `next`'s current selection and sort logic
- **Context**: Needed to know exactly what `--rank` would reorder, and whether any existing seam already supports alternate orders.
- **Sources Consulted**: `lifetxt/extra_core.py:40` (`command_next`), `lifetxt/extra_common.py:279` (`_blocked`), `lifetxt/extra_common.py:287` (`_priority_key`), `lifetxt/extra_common.py:136` (`_date_value`), `lifetxt/extra_cli.py:65-77` (`next` argparse definition).
- **Findings**: Single function, single fixed sort key, no plugin/strategy abstraction. Priority ordering already buckets: single-letter A-Z, then integer, then other string, then blank — reused as-is per the requirements' "factor scope" decision.
- **Implications**: The design adds exactly one new function (`_rank_key`) and one new branch in `command_next`, rather than introducing a general sort-strategy interface (see Simplification decision below).

### CLI/TUI/MCP actionable-item definition discrepancy
- **Context**: While tracing `command_next`, `lifetxt/nextaction.py`'s module docstring claims a shared definition across `next`, the TUI `/next` view, and MCP `get_next_actions`.
- **Sources Consulted**: `lifetxt/nextaction.py` (`is_actionable`, `next_action_items`, `ACTIONABLE_KINDS`, `PARKED_TAGS`, `PRIORITY_ORDER`), `lifetxt/tui_app.py:358`, `lifetxt/mcp.py:2479-2482`.
- **Findings**: Only the TUI and MCP actually call into `nextaction.py`. `command_next` has independent, divergent logic (Task-kind-only, no someday/maybe/waiting tag exclusion, file-local rather than workspace-wide blocking, a different priority-ordering scheme).
- **Implications**: Confirmed with the user this is out of this spec's boundary (see requirements.md and design.md Boundary Commitments). Filed as issue #138. This design ranks the item set `command_next` produces today, unchanged by that discrepancy.

### "Today" resolution for overdue detection
- **Context**: Requirement 2 needs a concrete, deterministic "today" to classify an item as overdue.
- **Sources Consulted**: `lifetxt/timezone_policy.py:272` (`today()`), call sites at `lifetxt/extra_core.py:290` (`command_workload`) and `lifetxt/extra_core.py:392` (`command_someday`).
- **Findings**: Both existing commands in the same module already call `timezone_today()` with no arguments to get a deterministic, timezone-policy-aware "today" rather than reading the host clock directly.
- **Implications**: `_rank_key`/`command_next` reuse the identical call, so ranked "overdue" status stays consistent with the rest of the project's existing timezone-aware behavior without introducing a new decision.

## Design Decisions

### Decision: Extend the existing fixed sort key instead of a pluggable sort-strategy abstraction
- **Context**: `--rank` needs to select between two orders (default vs. ranked) at CLI invocation time.
- **Alternatives Considered**:
  1. Introduce a general `SortStrategy` interface/registry so future orders (e.g., a future `agenda` ranking, or a future weighted-score mode) can be added without touching `command_next` again.
  2. A single boolean branch (`if args.rank: ... else: ...`) selecting between the current lambda and a new `_rank_key` function.
- **Selected Approach**: Option 2.
- **Rationale**: The requirements confirm exactly one new order is in scope for this iteration (agenda and any future scoring model are explicitly out of scope). Per the Simplification lens, an interface with a single real implementation and no committed second consumer is speculative abstraction the design principles explicitly warn against.
- **Trade-offs**: A future ranking mode (e.g., for `agenda`) will need its own small addition rather than dropping into an existing registry — judged acceptable since that future spec would also need to decide its own item-selection and factor scope, which a shared registry could not anticipate today.
- **Follow-up**: None required now; revisit only if a second concrete ranking consumer is actually scoped.

### Decision: Reuse `_priority_key` and `_date_value` unchanged rather than reimplementing
- **Context**: Requirement 2's priority/due/created tie-break keys must match `next`'s existing semantics exactly (per the requirements' "factor scope" decision).
- **Alternatives Considered**:
  1. Reimplement equivalent logic inside `_rank_key` for isolation.
  2. Call the existing `_priority_key`/`_date_value` helpers directly.
- **Selected Approach**: Option 2.
- **Rationale**: These helpers are already the single source of truth for `next`'s current priority/date semantics; reimplementing risks silent drift between the default and ranked orders for the exact fields Requirement 1 requires to stay consistent.
- **Trade-offs**: `_rank_key` is coupled to these helpers' exact bucket/default conventions (documented as a Revalidation Trigger in design.md) — accepted, since decoupling would reintroduce the drift risk this decision avoids.
- **Follow-up**: None.

## Risks & Mitigations
- A future change to `_priority_key`'s bucket ordering silently changes ranked output too — mitigated by recording this as an explicit Revalidation Trigger in `design.md` rather than leaving it implicit.
- Computing `timezone_today()` once per invocation (not per item) means a `next --rank` run that starts just before a timezone-policy midnight boundary and produces output just after could show a small window of inconsistency — accepted as negligible for a single-shot CLI command; documented in design.md's Implementation Notes rather than engineered around, since introducing per-item clock reads would be the actual regression (results could then differ *within* a single invocation).

## References
- `.ai/project/RULES.md` "Design Principles" — "Preserve old public CLI behavior when introducing richer reports; use explicit modes or unambiguous new flags." — directly shaped Requirement 1 and the `--rank` flag decision.
- `todo.md` P1 "Workflow Follow-ups" — existing `next --explain` roadmap entry, confirmed out of scope for this iteration but recorded so a future spec does not conflict with this one's flag/ordering choices.
