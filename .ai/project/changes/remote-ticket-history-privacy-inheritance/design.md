# Design

## Summary

`lifetxt/remote_backend.py`'s `_visible_items()` filters every item read for a
Remote Safe Mode response through `_access_for_item()`, which today always
reads `visibility`/`owner`/`groups`/`project` from the item's own `details`.
`record:ticket_event` and `record:time_entry` Notes never carry those fields
(confirmed by reading `lifetxt/ticket_activity.py`'s `build_ticket_event` and
`build_time_entry` field-by-field), so they always fell back to the default
tuple (`visibility="shared"`, no owner) regardless of their parent ticket's
actual privacy.

The fix adds a one-hop inheritance rule: when an item's `record:` detail is
`ticket_event` or `time_entry`, `_access_for_item()` resolves its `parent:` id
against an index of the full (pre-filter) item set. If the id resolves to
exactly one item, that parent's access tuple is used instead. If it resolves
to zero or more than one item, the Note falls back to its own default tuple --
the same "don't guess" discipline already used elsewhere in this codebase
(`lifetxt/links.py`'s `_unique_reference_target`, `lifetxt/
remote_ticket_write_core.py`'s `conflict_current_item`).

`_visible_items()` gained a third, optional `config` parameter so it can build
the id index with the project's configured `id_key` (`lifetxt.ids.
id_key_from_config`) rather than a hardcoded `"id"`. Its one call site,
`read_resource()`, already has `config` in scope.

## Interfaces and Contracts

- **ADDED**: `lifetxt.remote_backend._access_tuple(details)` -- private helper
  extracted from the body of `_access_for_item` so both the "own fields" and
  "inherited from parent" paths build the tuple identically.
- **MODIFIED**: `lifetxt.remote_backend._access_for_item(item, id_index=None)`
  -- new optional second parameter; when omitted, behavior is unchanged
  (returns the item's own tuple, `id_index=None` never triggers inheritance).
- **MODIFIED**: `lifetxt.remote_backend._visible_items(items, principal,
  config=None)` -- new optional third parameter; when omitted, `config=None`
  makes `id_key_from_config(None or {})` resolve to the default id key
  (`"id"`), preserving prior behavior for any caller that does not pass it.
- **MODIFIED**: `read_resource()`'s one call site now passes `config` through.
- **REMOVED**: none.

No public API, schema, or wire-format change. This is entirely internal to
the permission-filtering step; every Remote Safe Mode resource response shape
is unchanged.

## Alternatives

1. Have `build_ticket_event`/`build_time_entry` copy the parent's visibility/
   owner into the Note's own details at write time -- rejected: it would
   duplicate privacy state that can drift if the parent ticket's visibility
   changes later (the Note's copy would go stale), and it touches ticket
   mutation code (`lifetxt/ticket_activity.py`, `lifetxt/
   ticket_activity_mutation.py`), which `change.yml` places out of scope to
   keep this a pure read-path fix.
2. Filter history Notes out of Remote responses entirely unless their parent
   ticket is also present in the response -- rejected: overly broad (it would
   also hide history for *visible* tickets in resources that don't already
   include the ticket itself, e.g. a hypothetical future ticket-history-only
   resource) and doesn't generalize past the two current record kinds as
   cleanly as an explicit inheritance rule.
3. One-hop inheritance rule with a "don't guess" fallback (**selected**) --
   smallest change, reuses the existing filtering pass and the existing
   ambiguous-reference discipline already established elsewhere in the
   codebase, no new data model or write-path change.

## Risks

- **Recursion / cost**: bounded by construction -- the rule is a single,
  non-recursive dictionary lookup (`id_index.get(...)`), not a recursive
  walk, so a malformed file with a history-Note-parents-history-Note chain
  cannot cause unbounded work.
- **Over-restriction**: an ambiguous or missing `parent:` id falls back to
  the Note's own default (`visibility="shared"`), the same default used
  before this change -- no new case became *more* restrictive than before.
- **Under-restriction / bypass**: the inheritance rule only ever *narrows*
  visibility to match the parent's; it cannot make a Note visible to a
  principal who could not already see it under the old per-item check when a
  parent is present, and the id-index lookup uses the same set of items the
  rest of the read path already resolved (no new data source that could be
  spoofed independently of the file content itself).

## Operations Impact

None. No new configuration, no schema change, no new log output or
diagnostic. `lifetxt doctor` output is unchanged.

## Compatibility Impact

Behavior change for release notes: a Remote Safe Mode principal who could see
a ticket's `record:ticket_event`/`record:time_entry` history solely because
those Notes carried no visibility of their own will no longer see that
history once the parent ticket's visibility excludes them. Every other read
path (CLI, TUI, Web UI, MCP) is unaffected -- this change is scoped entirely
to Remote Safe Mode's permission filter.
