# Design: lifecycle temporal thread

## Summary

The existing link graph remains the only engine for stored relations.
`follows:` stores successor-to-predecessor, `realizes:` stores actual-to-plan,
and `replaced_by:` keeps old-to-new supersession. Inverse names are read-model
labels only. `temporal_thread()` builds a bounded undirected neighborhood over
those stored directed edges and embeds the unchanged `temporal_context()`
result under `derived`.

## Interfaces and contracts

- ADDED: `follows:ID`, `realizes:ID`, diagnostics W230/W231.
- ADDED: `temporal-thread-v1`, `lifetxt thread`, TUI `/thread`, Web
  `/api/temporal-thread/{id}`, MCP `get_temporal_thread`.
- MODIFIED: shared reference registries, schemas, docs, and Web item drawer.
- REMOVED: none.

## Bounds and failure behavior

Explicit traversal defaults to depth 8 and 50 nodes, with hard ceilings of 32
and 500. Derived neighbors default to 7 days and 20 items, capped at 500.
Negative values, zero node capacity, an unidentifiable target, or any duplicate
workspace ID fail loudly. Missing/ambiguous relation targets remain visible to
the shared diagnostic/link APIs but do not become resolved thread nodes.

## Historical boundary

Current dates and relations describe current authoritative content, not what
was known earlier. Exact Git snapshots and complete typed event chains are the
only identified evidence-backed subsets. A general as-of surface is deferred
until source selection, cutoff policy, provenance, and completeness are fixed.

## Compatibility and rollback

The grammar is additive; old readers preserve the new details as custom keys.
No file migration or rewrite occurs. Rollback removes the new readers/surfaces
while leaving user-authored details intact as ordinary custom data.
