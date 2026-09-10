# Native item events

`record:item_event` is the shared append-only evidence record for semantic
changes to ordinary life.txt items. It is a Note stored in the same life.txt
file as its parent. Existing files remain valid and no history is synthesized
or backfilled.

## Envelope

Every event has exactly one `record:item_event`, `id`, `parent`, `event`,
`at`, `sequence`, `transaction`, and `source_revision`. `at` is normalized UTC
and `source_revision` is the SHA-256 revision immediately before the compound
mutation. Optional `actor` and `source` identify who and which surface produced
the event. The stable identity is the pair `(record kind, id)`; sequence is
positive and scoped to the parent.

The closed event vocabulary is `created`, `status_changed`, `completed`,
`reopened`, `canceled`, `relation_added`, `relation_removed`, and
`schedule_changed`. Relations are limited to `follows`, `realizes`, and
`replaced_by`; schedules are limited to `on`, `due`, `from`, `to`, and `at`.
Unrelated title, type, or custom-field mutations are not item events in v1.

Example:

```text
[N] N Item_task-1_000002 record:item_event id:IE-task-1-000002 parent:task-1 event:completed at:2026-09-10T10:00:00Z sequence:2 transaction:ITX-task-1-000002 source_revision:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa actor:me source:cli before_status:[/] after_status:[x] completed_at:2026-09-10T10:00:00Z
```

## Validation and completeness

Duplicate identities, transactions, or parent sequences; gaps; backwards
timestamps; status discontinuities; invalid payload fields; and disagreement
with current status are diagnosed and make the stream non-authoritative. A
stream without a `created` event remains readable with `coverage:partial`; it
must never be presented as complete. Manual edits remain valid life.txt, but
cannot silently upgrade a partial history claim.

`record:progress_event`, `record:ticket_event`, and `record:time_entry` retain
their existing on-disk formats. The native-history adapter normalizes these
records for readers while preserving original record kind and ID. Remote Safe
Mode applies the parent item's access tuple to all four native history kinds.

The public JSON contract is
[`item-event-v1.schema.json`](../../dist/schemas/item-event-v1.schema.json).

## Captured mutations

The shared producer verifies the before and after item states, derives the
closed payload, and commits the state replacement plus event through one exact
revision write. Current CLI capture includes ID-bearing `quick` creation,
`start` status transition, `done`/`complete`, `reopen`, and `due`. Repeating
`complete` records both completion of the old instance and creation of the new
instance in the same write. The producer also supports typed cancellation and
lifecycle relation add/remove for surfaces that already have such an operation.

Dry runs append no event. A stale revision or payload/state disagreement writes
neither state nor event. Items without a stable configured ID keep their legacy
mutation behavior and therefore have partial native-history coverage. Existing
ticket and progress writers retain their specialized records and do not also
emit an item event.
