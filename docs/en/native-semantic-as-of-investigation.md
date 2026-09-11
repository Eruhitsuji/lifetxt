# Native semantic `as-of` reconstruction investigation (#759)

Status: investigation only. No runtime code, Format key, or schema changes.

## Question

[Git `as-of`](historical-as-of-semantics.md) already answers "what were the
tracked bytes at time T" from repository evidence. Native Semantic History
(`record:item_event`, `record:progress_event`, `record:ticket_event`,
`record:time_entry`, composed by the bounded
[Native Temporal Timeline](native-timeline.md)) is a second, independent
evidence source that exists with no Git dependency at all. This investigation
asks: can Native History reconstruct "what was true at time T" per field or
domain, safely, without falling back to current state and without inventing
new history semantics?

## Method

Read the actual capture, validation, and completeness code rather than
inferring behavior from the schema alone:

- `lifetxt/native_history.py` -- `record:item_event` field/type rules
  (`item_event_diagnostics`), stream-level continuity rules
  (`item_event_history_diagnostics`: sequence gaps as `W273`, backwards
  timestamps as `W274`, discontinuous status chains as `W276`, current-state
  disagreement as `W277`), and per-item coverage
  (`item_event_completeness`: `coverage` is `from_creation` or `partial`,
  `complete` is `true` only when the chain starts at `created` sequence 1
  **and** carries zero diagnostics).
- `lifetxt/native_history_mutation.py` -- the actual atomic capture routes
  wired into `lifetxt/cli.py`: `quick` emits `created`; `start`/`done`/
  `complete`/`reopen` emit `status_changed`/`completed`/`reopened` (via
  `commit_item_mutation_with_event`/`commit_item_mutations_with_events`);
  `due` is the **only** schedule field wired to `schedule_changed`
  (`field="due"` at `lifetxt/cli.py:8514`); ticket `link`/`unlink` emit
  `relation_added`/`relation_removed` for `follows`/`realizes`/
  `replaced_by` (#721, `RELATION_FIELDS` in `native_history.py`).
- `lifetxt/native_timeline.py` -- the existing bounded, deterministic,
  ordered, deduplicated, validated event stream (`native_timeline()`,
  `normalize_native_events()`) every domain below would replay from.
- `lifetxt/progress_history.py` and `lifetxt/progress_delta.py` -- the
  existing progress-boundary reconstruction (#697/#700), already shipped
  and already the working precedent for "reconstruct a bounded quantity
  from a validated append-only chain, refusing an unavailable baseline
  rather than inferring one."
- `lifetxt/ticket_activity.py` -- the existing ticket-event/time-entry
  domain, which already has its own audit trail and is out of this
  investigation's scope (it is not part of Native Semantic History's
  `record:item_event` envelope and already has its own reconstruction
  precedent via `validate_ticket_history`).

## Reconstructability matrix

| Domain | Reconstructable? | Evidence | Boundary |
| --- | --- | --- | --- |
| Lifecycle status (`[ ]`/`[x]`/`[/]`/... at time T) | **Partial**, per item | Ordered `status_changed`/`completed`/`reopened`/`canceled` events, replayed by `at <= T` | Complete only when `item_event_completeness()` reports `coverage: from_creation` and `complete: true` for that item; an item with no captured event history at all is **not reconstructable** (not "assume current"), and an item whose chain does not start at `created` is reconstructable only from its first captured event onward |
| Completion / reopen / cancellation | **Partial**, per item | Same `completed`/`reopened`/`canceled` events (a subset of the status family above), `before_status`/`after_status`/optional `completed_at` | Identical boundary to lifecycle status; the completion-specific fact ("was this item completed as of T") is answerable exactly when the general status chain is |
| Schedule field `due:` | **Partial**, per item | `schedule_changed` events with `field="due"`, `before`/`after` or `before_missing`/`after_missing`, captured by the `due` CLI command only | Complete only where the capture chain is unbroken; a `due:` value ever set by any other command or by direct editing has no event evidence and is **not reconstructable** |
| Schedule fields `on:`/`from:`/`to:`/`at:` | **Not reconstructable today** | None -- `schedule_changed` capture exists in the shared mutation helper (`native_history_mutation.py`) but no CLI command wires any of these four fields to it | Extending capture to these fields is a distinct, separately-scoped follow-up; this investigation does not authorize it |
| Lifecycle relations `follows:`/`realizes:`/`replaced_by:` | **Partial**, per relation instance | `relation_added`/`relation_removed` events, captured only by the ticket link/unlink route (#721) | A relation set through direct editing, `assist`, or any other command has no event evidence; reconstructable only for relations that were ever mutated through that one route |
| Progress (`progress:`) | **Complete within its existing bounded contract** | `record:progress_event` chain, already reconstructed by the shipped `lifetxt stats --progress-delta` (#697/#700) | Already implemented; not new scope for this investigation. Recorded here only to confirm it is the working precedent the other domains above follow |

No domain above is ever reconstructed by reading current life.txt state and
assuming it held earlier. Every "Partial" result in the matrix is bounded by
the same rule progress delta already established: an unavailable baseline (no
event, or an incomplete/invalid chain) is reported as unavailable, never
inferred.

## Baseline / unknown-field rule

For any field or domain with no applicable captured event evidence at time T:

- If the target item itself has zero relevant events (e.g. no `status_changed`
  family event at all), the field is **unknown**, not "assumed unchanged from
  creation" and not "assumed equal to current."
- If events exist but the ordered, filtered (`at <= T`) subsequence does not
  reach an authoritative starting point (no `created` event, or
  `item_event_history_diagnostics` reports a defect for the relevant span),
  the field is **partial evidence, not a confirmed historical value** -- it
  must be reported with the same diagnostics/limitations vocabulary
  `native_timeline()` already uses (`invalid_events`, `limitations`,
  `completeness`), not silently upgraded to a confident answer.
- A field this project has genuinely never captured events for (`on:`/
  `from:`/`to:`/`at:`, or any relation never routed through link/unlink) is
  **not reconstructable at all** -- this is a capture-coverage gap, not a
  reconstruction failure, and must be reported as such rather than answered
  from current bytes.

## Replay semantics

The replay rule for every reconstructable domain is the same, and it reuses
existing contracts rather than inventing new ones:

1. Take `native_timeline()`'s existing bounded, ordered, deduplicated, valid
   event stream for the target item (reusing `normalize_native_events()` and
   its existing sort key unmodified).
2. Filter to events with `at <= T` (the requested cutoff), the same
   inclusive-before-cutoff convention `historical_temporal.select_revision_as_of`
   already uses for Git commits, and reuse `historical_temporal.parse_cutoff`
   for validating the offset-aware RFC3339 `T` value itself so there is no
   second timestamp-format policy.
3. Fold that filtered subsequence in order, one domain at a time:
   status/completion via the `status_changed`/`completed`/`reopened`/
   `canceled` family; `due:` via `schedule_changed` where `field == "due"`;
   each relation kind via `relation_added`/`relation_removed`.
4. Reuse `item_event_completeness()`/`native_history_completeness()`
   unmodified to decide, per domain, whether the folded result is `complete`
   (chain from creation, no diagnostics up to the cutoff) or merely
   `partial`/`unavailable` -- the existing completeness contract, not a new
   one.
5. Never read current life.txt state as a substitute for a domain the fold
   could not resolve.

This reuses every existing engine (`native_timeline`, `normalize_native_events`,
`item_event_completeness`, `parse_cutoff`) unmodified; it needs one new, small,
pure fold function per domain and no second validator.

## Proposed minimal result contract

The existing `temporal-timeline-v1` projection (a filtered *list of events*)
does not suffice on its own: it does not answer "what was the status/due/
relation-set at T" without the caller re-implementing the fold in step 3
above themselves, which is exactly the kind of second implementation this
project's reuse discipline exists to prevent.

Recommendation: a new, narrow, versioned read contract --
**`semantic-as-of-v1`** -- distinct from both `temporal-timeline-v1` (event
list) and Git `temporal-thread-v1.historical` (byte-level revision). Shape:

```json
{
  "schema": "semantic-as-of-v1",
  "target_id": "task-1",
  "as_of": "2026-06-01T00:00:00+00:00",
  "source": "native_life_txt",
  "git_composed": false,
  "fields": {
    "status": {"state": "known", "value": "[x]", "as_of_event": "task-1#4"},
    "due": {"state": "unavailable", "reason": "no_schedule_changed_capture"},
    "relations.follows": {"state": "known", "value": ["previous-task"]}
  },
  "completeness": { /* reuse native_history_completeness() shape */ },
  "limitations": ["..."],
  "diagnostics": ["..."]
}
```

Each field entry is independently `known`/`partial`/`unavailable`; there is no
single document-level "complete" flag that could mask one field's gap behind
another field's coverage.

## Native-vs-Git authority boundary

This stays exactly as `historical-as-of-semantics.md` already states it: Git
`as-of` proves tracked-byte state at a commit; Native semantic `as-of` proves
domain-field state from a validated append-only event chain. Neither
supersedes the other, and this investigation does not merge them -- a future
composition (e.g. cross-checking a Native projection against a Git-tracked
byte state at the same instant) is out of scope and not recommended without
further evidence, matching the existing, deliberately narrow
`native-git-history-consistency-v1` precedent (bounded verification, not
fallback).

## Recommendation

Ship `semantic-as-of-v1` as a new, small, pure projection function reusing
`native_timeline()`/`normalize_native_events()`/`item_event_completeness()`
unmodified, exposed first through the CLI only (matching this project's
established CLI-first precedent for every prior Native History slice).
TUI/Web/MCP exposure is deferred, matching how `temporal-thread-v1` and
`temporal-timeline-v1` were both shipped CLI-first before later surfaces.

## Follow-up issues

Decomposed into three XS/S issues so no single change mixes the new
projection engine with its first consumer or its documentation:

1. **Add the `semantic-as-of-v1` projection engine** -- a new, small, pure
   `lifetxt.native_semantic_as_of` module implementing the replay in
   "Replay semantics" above over the unmodified shared readers, with its own
   focused test suite covering every row of the reconstructability matrix
   (including the two "not reconstructable today" rows reporting
   `unavailable`, never a guess).
2. **Expose it as `lifetxt timeline ID --as-of TIMESTAMP`** -- a CLI-only
   consumer of (1), text and `--json` output, reusing
   `historical_temporal.parse_cutoff` for the timestamp and adding no second
   cutoff-parsing policy. No TUI/Web/MCP change in this slice.
3. **Publish the `semantic-as-of-v1` JSON Schema and EN/JA documentation**
   for the shape (1) produces, following this project's existing schema
   generator convention (`schema_extensions_v*.py` plus regenerated
   `dist/schemas/*.json`) rather than a hand-written schema file.
