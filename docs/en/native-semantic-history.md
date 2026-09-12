# Native semantic history

Status: implemented incrementally from the design approved in investigation
#712. Native history remains intentionally partial: only documented mutation
routes capture events, and existing or manually edited files are not backfilled.

## Decision

Human-meaningful history is a core lifetxt concept. The primary evidence that
a semantic operation occurred SHOULD live as a human-readable, append-only
record in `life.txt`. Git remains independent evidence for exact tracked bytes,
revision audit, and recovery. Neither source replaces the other.

History records are optional evidence, not a requirement for a valid file.
Existing files, direct text edits, and files with only current state remain
valid. lifetxt never invents or backfills events for changes it did not capture.

## Contract choice

Three representations were compared:

| Model | Strength | Problem | Decision |
| --- | --- | --- | --- |
| One record kind per operation | Payloads are explicit | Record kinds and readers multiply for every field | Do not extend this pattern for ordinary item lifecycle events |
| One generic key/value change record | Small initial implementation | Becomes a raw diff with ambiguous semantics and unbounded custom fields | Reject |
| Common envelope plus typed payload | Shared ordering/provenance with explicit domain meaning | Requires a maintained event registry and discriminated validation | Adopt |

New non-ticket lifecycle history uses `record:item_event`. Its common envelope
is `id`, `parent`, `event`, `at`, `sequence`, `transaction`, and
`source_revision`. `event` selects a closed, versioned payload shape; it does
not authorize arbitrary `field`/`before`/`after` logging. An optional `actor`
and a bounded `source` value may add provenance without changing event meaning.

Conceptual examples (not accepted by a dedicated validator until the contract
implementation issue lands):

```txt
[N] N Task_TASK-1_status_changed record:item_event id:IE-TASK-1-000002 parent:TASK-1 event:status_changed at:2026-09-10T00:00:00Z sequence:2 transaction:ITX-TASK-1-000002 source_revision:<sha256> before_status:todo after_status:doing

[N] N Task_TASK-1_relation_added record:item_event id:IE-TASK-1-000003 parent:TASK-1 event:relation_added at:2026-09-10T00:10:00Z sequence:3 transaction:ITX-TASK-1-000003 source_revision:<sha256> relation:follows target:TASK-0

[N] N Task_TASK-1_schedule_changed record:item_event id:IE-TASK-1-000004 parent:TASK-1 event:schedule_changed at:2026-09-10T00:20:00Z sequence:4 transaction:ITX-TASK-1-000004 source_revision:<sha256> field:due before:2026-09-15 after:2026-09-20
```

The typed payload registry, not the generic parser, limits fields:

| Event | Required semantic payload |
| --- | --- |
| `created` | item kind, title, and initial lifecycle status |
| `status_changed` | `before_status`, `after_status` |
| `completed`, `reopened`, `canceled` | previous and resulting lifecycle status; completion time when the operation writes one |
| `relation_added`, `relation_removed` | `relation` from `follows`, `realizes`, or `replaced_by`, plus one `target` |
| `schedule_changed` | `field` from `on`, `due`, `from`, `to`, or `at`, with an explicit missing marker or value on each side |

Completion, reopen, and cancellation operations emit their specific event,
not a second `status_changed` event for the same status transition. For
`schedule_changed`, exactly one of `before` or `before_missing:true` and exactly
one of `after` or `after_missing:true` is present. The allowlisted `field`
gives those otherwise generic value slots a bounded meaning.

`title` and item-type changes are meaningful but deferred from the first
capture slice. They need rename/identity and type-conversion rules before they
can be safely represented. Arbitrary custom details, formatting, ordering,
comments, whitespace, and raw line changes are not semantic events.

## Compatibility with existing history

`record:progress_event` remains its public, field-specific contract. Its raw
percentage/fraction values, `set`/`delta` operations, continuity rules, and
authoritative-chain behavior do not change. It is exposed to a future timeline
through a normalization adapter, not migration or duplicate writes.

`record:ticket_event` and `record:time_entry` likewise remain the ticket-domain
audit/activity contracts. They can be normalized into timeline entries while
retaining their own event vocabulary, author, revision field, validation, and
privacy inheritance.

An event's stable identity is `(record kind, id)`. A shared `transaction` may
correlate records created by one mutation but does not make them duplicates.
Git evidence is never silently deduplicated with a native event: Git proves a
revision state, while the native record states the semantic operation.

## Authority and disagreement

| Question | Primary evidence | Boundary |
| --- | --- | --- |
| What is true now? | Current `life.txt` | History does not override current state |
| What semantic operation was captured? | Valid native event | Proves only its typed operation and payload |
| Is the captured history complete? | Validated native chain and coverage result | Completeness is per item and semantic domain, never global by implication |
| What did the tracked file contain at a revision? | Exact Git tree/blob | Does not prove why a domain change occurred |
| What raw text or formatting changed? | Git diff | Not a semantic event source |
| What is planned? | Current future-facing fields and lifecycle relations | A current plan is not evidence that it existed earlier |

When current state, native events, and Git evidence disagree, readers preserve
each source and report a limitation. They do not choose a hidden winner or
repair data automatically. Current `life.txt` remains authoritative for now;
valid native records remain evidence that an operation was recorded; Git
remains evidence of exact tracked bytes.

## Ordering, append-only behavior, and completeness

- Event time is an offset-aware instant normalized to UTC. Per-parent positive
  `sequence` is the semantic order within its record-kind stream; timestamps
  may be equal but must not move backwards.
- IDs are stable and unique within their record kind. Sequences begin at 1 and
  are contiguous for each record-kind stream. A transaction ID correlates all
  records written atomically with one current-state mutation.
- Supported writers update current state and append required events through one
  validated, exact-revision, atomic mutation path. They do not update or delete
  earlier events.
- A `created` event at sequence 1 establishes from-creation coverage for the
  generic item-event stream. A stream beginning after an item already existed
  is valid but explicitly partial.
- Completeness is evaluated per semantic domain. It requires valid structure,
  continuous before/after projections, contiguous ordering, and agreement of
  the last captured value with current state. It never means that every byte or
  every custom detail change was captured.
- A malformed, duplicate, gapped, discontinuous, or backwards event remains
  readable as plain text but is excluded from authoritative projection and
  marks its affected stream incomplete. A timeline may display it separately
  with diagnostics; semantic as-of reconstruction must not use it.
- Direct text editing remains first-class. An uncaptured edit can make the
  affected domain partial or inconsistent, but it never makes the file invalid
  and is never converted into a guessed event.

Across specialized streams, the normalized timeline sorts by UTC event time,
then a published fixed record-kind rank, then stream sequence and stable ID.
This tie-break is deterministic presentation order, not inferred causality.
A shared transaction is the only first-slice cross-stream correlation claim.

## Read-model and CLI direction

The first native read model is a bounded **Temporal Timeline**:

```text
record:item_event -----+
record:progress_event -+--> normalized native timeline
record:ticket_event ---+       + provenance, validation, completeness
record:time_entry -----+
```

The planned command is `lifetxt timeline ID [--json]`. It reads native semantic
events, orders them deterministically, preserves their record kind and stable
ID, and reports per-source/per-domain completeness. `timeline` is preferred to
`history` because it names a semantic chronological view rather than suggesting
an exact revision log.

`lifetxt thread ID --revision/--as-of` remains Git-backed exact-state
reconstruction. Native-event semantic as-of reconstruction, a
`--source native|git|all` switch, and automatic native/Git composition are
deferred until the timeline contract has real completeness and provenance
evidence. The first timeline must not claim that it can reconstruct complete
past item state.

Without Git, users can read current state and native events directly and use the
native timeline; exact historical revisions and Git diffs are unavailable.
With Git, the same native behavior remains available alongside historical
thread and diff commands. No command silently changes source based on whether a
repository happens to exist.

The existing CLI `ticket link` / `ticket unlink` route captures
`relation_added` / `relation_removed` item events for the lifecycle fields
`follows`, `realizes`, and `replaced_by`. The relation state change and event
append share one exact-revision mutation: duplicate adds are no-ops, failed or
stale writes leave no orphan event, and other relation fields retain their
existing behavior. Other mutation surfaces remain a documented coverage gap;
there is no migration or backfill.

## Implementation impacts

Follow-up implementation must include:

- shared envelope, typed registry, validators, normalization adapters, and
  parent access-policy inheritance;
- exact-revision compound writes for selected CLI/TUI/Web/API/MCP mutation
  paths, with unsupported generic/manual mutation paths disclosed as coverage
  limitations;
- `item-event-v1` and `temporal-timeline-v1` JSON Schemas before public JSON
  output, plus schema compatibility tests;
- English and Japanese format, CLI, and relevant surface documentation;
- capability/traceability updates and High-assurance data-integrity,
  compatibility, privacy, and atomicity evidence.

No migration or backfill is required. Rollback of future writers must stop new
event emission without deleting records already written; old parsers continue
to accept the Notes through permissive custom-key parsing.

## Follow-up issues

1. [#713](https://github.com/Eruhitsuji/lifetxt/issues/713) defines the shared
   item-event contract, validators, schemas, and adapters.
2. [#714](https://github.com/Eruhitsuji/lifetxt/issues/714) captures the selected
   lifecycle mutations atomically after #713.
3. [#715](https://github.com/Eruhitsuji/lifetxt/issues/715) adds the bounded
   native Temporal Timeline after #713; it can proceed independently of #714.

## Cross-surface capture parity (#767)

Automatic Native History capture is currently CLI-only. `lifetxt done`,
`complete`, `reopen`, and `due` each call
`native_history_mutation.commit_item_mutation_with_event`/
`augment_item_mutation_with_event` directly, so a supported CLI mutation
always produces its matching typed `record:item_event` in the same atomic
write as the state change.

Web UI/API (`PUT /api/items/id/{id}`, which Remote TUI also uses as its
authoritative write route), local TUI row edits
(`lifetxt.tui_backend.LocalTuiBackend.apply_semantic_changes`), and Remote
TUI's own edits do **not** call any Native History producer today. A
status/due/relation change made from any of those surfaces currently
produces no `record:item_event` at all -- this is a real gap, not a design
choice, and it is the concrete finding of the #767 investigation.

To make closing this gap safe rather than speculative,
`lifetxt.native_history_mutation.infer_item_event_specs(before, after)` is a
new, pure, file-I/O-free classifier reusing the exact same event vocabulary
and field scope `augment_item_mutation_with_event` already emits (status
family, the `due:` schedule field, and the `follows`/`realizes`/
`replaced_by` relations) over a before/after `Item` pair. It duplicates no
event-shape logic and is fully unit-tested
(`tests/test_native_history_mutation.py::InferItemEventSpecsTests`), but it
is not yet wired into any live write path.

Wiring it in safely requires each of Web UI/API's `update_item_in_file`,
`lifetxt.write_operations.mutate_items`/`mutate_item_files` (which both CLI
generic paths and local TUI already use), and Remote TUI's edit route to
build their replacement text and commit it together with any inferred
event(s) in one atomic write -- the same one-write guarantee #714 already
established for CLI's dedicated commands. That is a change to this
project's shared, heavily-used mutation primitives themselves, not a
localized fix, and is deliberately **not** attempted in this pass per this
project's own [Task Decomposition Standard](../../.ai/managed/core/TASK_DECOMPOSITION.md)
guidance to split a task when independent write paths cannot be safely
reviewed together. It remains a recorded, explicit follow-up rather than a
silently dropped requirement.

Until that follow-up lands, editing an item from the Web UI, local TUI, or
Remote TUI is exactly as valid a workflow as it always was -- it simply
does not (yet) produce Native History evidence for that change, the same
documented, non-inferred partial-completeness behavior direct/manual text
edits already have.
