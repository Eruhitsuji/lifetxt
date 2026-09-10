# Native Temporal Timeline

`lifetxt timeline ID [PATH ...]` shows the bounded semantic history stored in
the current life.txt inputs. It reads `record:item_event`,
`record:progress_event`, `record:ticket_event`, and `record:time_entry` through
the shared adapter. It never reads or automatically merges Git history.

```bash
lifetxt timeline task-1 life.txt
lifetxt timeline task-1 life.txt --limit 25
lifetxt timeline task-1 life.txt --json
```

The default limit is 100 valid events and the accepted range is 0–500. Events
are ordered deterministically by normalized time, record-kind rank, parent
sequence, and stable record ID. The result retains the original record kind,
record ID, meaning, timestamp, sequence, transaction, revision provenance,
payload, and validity.

Malformed records are excluded from the main `events` list and returned under
`invalid_events` with diagnostics. Gaps, duplicate identities, backwards time,
discontinuity, current-state disagreement, and truncation prevent a complete
claim. Missing creation evidence is a valid readable partial Timeline, not an
error and not inferred history. Completeness is reported separately for item,
progress, ticket, and time-entry domains.

The JSON result uses
[`temporal-timeline-v1.schema.json`](../../dist/schemas/temporal-timeline-v1.schema.json).
For exact Git revisions, continue to use `thread --revision`, `thread --as-of`,
or `thread --diff`; those commands are unchanged.
