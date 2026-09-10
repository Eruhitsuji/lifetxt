# Design: native semantic history

The living English and Japanese design is recorded in:

- `docs/en/native-semantic-history.md`
- `docs/ja/native-semantic-history.md`

The selected model is a common `record:item_event` envelope with a closed,
typed payload registry. Existing `record:progress_event`,
`record:ticket_event`, and `record:time_entry` contracts remain unchanged and
participate through normalization adapters.

Current `life.txt`, native semantic records, and Git exact revisions answer
different questions. Disagreement is exposed as a limitation rather than
silently reconciled. Completeness is per item and semantic domain, and direct
text editing remains valid without inferred events.

The first read model is a native-only, bounded Temporal Timeline. Existing
Git-backed `thread --revision/--as-of` remains exact-state reconstruction;
semantic as-of and multi-source composition are deferred.
