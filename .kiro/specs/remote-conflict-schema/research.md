# Research & Design Decisions

## Summary
- **Feature**: `remote-conflict-schema`
- **Discovery Scope**: Extension (light discovery per `design-discovery-light.md`)
- **Key Findings**:
  - The exact mechanism needed for `current_item`'s permission filter already exists in this module: `access_for_item(item)` + `can_access(principal, **access_for_item(item))` (`remote_ticket_write_core.py:109-131`), already used by `require_ticket_access`. No new permission logic is needed, only reuse.
  - The exact mechanism needed to re-read the current ticket after a conflict already exists too: `replay()` (`remote_ticket_write_core.py:208-235`) already does `read_text_snapshot(path, allow_missing=False)` -> `_parse_items` -> `_find_ticket` to get a `Ticket` object with `.to_dict()`. The conflict path needs the same three calls with `allow_missing=True` (the ticket file itself cannot have vanished mid-request the way a *missing ticket ID* can, but treating "cannot read" as "ticket not found" is the conservative, safe default).
  - `as_remote_error(exc)`'s only caller is `remote_ticket_writes.py:201`, inside a single `except Exception as exc: raise as_remote_error(exc)` block that already has `payload`, `principal`, `app.state.paths`, `key`, and `ticket_id_value` in scope. The signature needs to grow to accept this context; there is exactly one call site to update.
  - `request_hash()` (`remote_ticket_write_core.py:53-67`) already computes the "operation plus payload minus transaction_id/dry_run" shape needed for `attempted_change` — it just hashes it afterward. Extracting the un-hashed dict as a shared helper avoids duplicating the exclusion list.

## Research Log

### Attempted-Change and Current-Item Construction
- **Context**: Where do `attempted_change` and `current_item` get their data without inventing new plumbing?
- **Sources Consulted**: `lifetxt/remote_ticket_write_core.py`, `lifetxt/remote_ticket_writes.py`, `lifetxt/remote_access.py` (`can_access`), `lifetxt/mutation.py` (`read_text_snapshot`, `MutationConflict`).
- **Findings**:
  - `mutation.MutationConflict` already carries `.expected_hash` and `.actual_hash` (confirmed via its use in `remote_contracts_v6.py`, `webapp.py`, and `safety_compat_v2.py` — all three already build `{"error": "CONFLICT", "expected_revision": exc.expected_hash, "current_revision": exc.actual_hash, ...}` from it, just with extra non-schema keys this feature does not copy).
  - `request_hash()`'s exclusion list (`transaction_id`, `dry_run`) is exactly what `attempted_change` needs excluded too — the two should share one normalization function rather than keep two copies of the same exclusion list.
- **Implications**: No new data source. `as_remote_error` needs `payload`, `principal`, `paths`/`path`, `key`, and `ticket_id_value` passed in by its caller; `request_hash` gets refactored to call the new shared normalization helper instead of duplicating it.

### Missing-Ticket and Missing-File Edge Cases
- **Context**: What does `current_item` become when the ticket (or its file) cannot be re-read after the conflict?
- **Findings**: `read_text_snapshot(path, allow_missing=True)` returns an empty-text snapshot rather than raising when the file is gone; `_find_ticket` returns `None` when the ID is not present in parsed items (used this way already in `replay()`, where a `None` result is handled as "no prior replay" rather than an error).
- **Implications**: Both "file unreadable" and "ticket ID not found" collapse to the same `current_item: None` outcome required by Requirement 2 — no separate error path needed; this matches the schema's `current_item` being nullable specifically for this reason.

## Architecture Pattern Evaluation

| Option | Description | Strengths | Risks / Limitations | Notes |
|--------|-------------|-----------|---------------------|-------|
| Extend `as_remote_error` with optional context parameters | Add `payload`, `principal`, `paths`, `key`, `ticket_id_value` as optional keyword arguments, used only for the `MutationConflict` branch | One call site to update; `RemoteAccessError`/`ValueError` branches untouched; matches the function's existing single-dispatch-by-exception-type shape | Function signature grows | Selected |
| New `conflict_detail()` function called directly from `remote_ticket_writes.py`'s except block, bypassing `as_remote_error` for conflicts | Keeps `as_remote_error` unchanged | Splits conflict handling across two functions/call sites for what is conceptually one dispatch; the `except Exception` block would need to special-case `MutationConflict` itself, duplicating the `isinstance` check `as_remote_error` already does | Rejected — reintroduces the branching `as_remote_error` already centralizes |

## Design Decisions

### Decision: One shared normalization helper for `request_hash` and `attempted_change`
- **Context**: Both need "operation plus payload, minus `transaction_id`/`dry_run`".
- **Alternatives Considered**: 1) Keep `request_hash`'s inline dict comprehension and duplicate it for `attempted_change`. 2) Extract a shared `_normalized_change(operation, payload)` helper used by both.
- **Selected Approach**: Option 2.
- **Rationale**: A duplicated exclusion list is exactly the kind of drift this project's own `RULES.md` "Tracked Exceptions"/pinning precedent (the replace-retry policy test, `#116`) warns about — two copies of the same rule silently diverging.
- **Trade-offs**: None meaningful; this is a pure refactor of existing logic.
- **Follow-up**: None.

### Decision: `current_item` construction happens inside `as_remote_error`, not at the call site
- **Context**: `remote_ticket_writes.py`'s except block already has all the raw ingredients (`payload`, `principal`, `app.state.paths`, `key`, `ticket_id_value`); the question is whether it assembles `current_item` itself or passes ingredients through.
- **Alternatives Considered**: 1) Build `current_item` at the call site and pass the finished dict/`None` into `as_remote_error`. 2) Pass the raw ingredients and let `as_remote_error` do the re-read and permission check.
- **Selected Approach**: Option 2.
- **Rationale**: Keeps the re-read-and-filter logic (which only matters for conflicts) inside the function whose whole job is turning an exception into a Remote error, rather than making the route handler responsible for conflict-specific data assembly it does not otherwise need to know about. Matches the Single Responsibility principle from `design-principles.md`.
- **Trade-offs**: `as_remote_error` now does file I/O (a re-read) on the conflict path specifically, where it previously did none — acceptable since a conflict is already an error path re-reading is not performance-sensitive for.
- **Follow-up**: None.

## Risks & Mitigations
- Risk: A future caller of `as_remote_error` for a non-ticket conflict passes no context, silently getting `current_item: None` and an empty `attempted_change` — Mitigation: the function's docstring states explicitly that omitted context degrades gracefully to `null`/`{}` rather than raising, and the one real caller always supplies full context; a schema-conformance test still passes either way since `null` is a valid `current_item`.
- Risk: Client code elsewhere still reads the removed `requested_revision`/`comparison` field names — Mitigation: Requirement 3/4 acceptance criteria require running the existing CLI/TUI conflict tests, not just adding new ones, so a stale reader shows up as a test failure rather than a silent behavior change.

## References
- `lifetxt/remote_ticket_write_core.py`, `lifetxt/remote_ticket_writes.py`, `lifetxt/remote_client_writes.py`, `lifetxt/remote_access.py`, `lifetxt/mutation.py`.
- `dist/schemas/conflict-v1.schema.json`.
- GitHub Issue #122 — task-level scope, out-of-scope, and acceptance criteria.
