# Design: append-only progress event history

## Context and boundary

Issue #695 needs exact period-boundary progress deltas. The existing current
item, undo, backup, snapshot, and revision facilities cannot reconstruct a
complete, ordered timeline with exact before/after representations. Issue #696
therefore selected an explicit append-only record, and #697 implements that
prerequisite without implementing aggregation.

## Record contract

A progress event is a normal immutable Note (`[N] N`) marked
`record:progress_event`. It contains one each of `id`, `parent`, `at`,
`sequence`, `transaction`, `source_revision`, `operation`, and
`after_progress`. It contains exactly one of `before_progress` or
`before_missing:true`. Values pass through the shared `parse_progress`
validator, while their raw percentage/fraction spelling is retained.

The timestamp is offset-aware and serialized as second-precision UTC. Event
IDs are deterministic from parent and sequence. Sequences start at 1 and are
contiguous per parent. Adjacent `after_progress` and `before_progress` values
must match exactly, not merely by numeric ratio, so a representation change
such as `4/10` to `40%` remains explicit evidence.

## Mutation path

`command_progress` reads a snapshot and resolves the target. Non-dry-run
writes require its configured stable ID. `apply_progress_mutation` then uses
the shared compare-and-set mutation primitive. Inside the lock it reparses and
resolves the target, checks the expected prior raw value, chooses the next
sequence, builds the event with the snapshot hash, updates the item through
`transform_items_text`, appends the event, reparses the result, and commits
once. Any conflict or validation error occurs before replacement and leaves
the original bytes intact.

## Integrity and availability

`progress_history_diagnostics` emits `W231`-`W243` for malformed required
fields, unresolved parents, timestamp/sequence/hash/operation/value errors,
duplicate identities, sequence gaps, continuity breaks, backwards timestamps,
and disagreement with current progress. `authoritative_progress_events`
returns the ordered chain only when the selected parent and all its events
produce no such diagnostic. Generic/manual edits remain legal; they create an
observable incomplete chain rather than being silently repaired. Absence of
events is valid and means history is unavailable, not zero change.

## Security and privacy

Progress events contain raw user progress values and identifiers. The existing
Remote Safe Mode history-record rule is extended so a uniquely resolved parent
supplies the event's project, visibility, owner, and group tuple. Resolution is
one-hop and non-recursive. As with the existing ticket history rule, a missing
or ambiguous parent falls back to the Note's own access tuple instead of
guessing. No new network, credential, execution, or secret surface is added.

## Compatibility, migration, and rollback

The format is additive: old readers continue to parse the event as a Note.
Known event-owned keys are registered so compatibility checking does not emit
generic generated-record warnings for valid events. Existing files are not
rewritten and historical progress writes are not backfilled. Rolling back the
code leaves ordinary Note lines in the file and preserves current progress;
operators may retain those lines for a later upgrade. Deleting event lines is
not an automated rollback because it would destroy evidence.
