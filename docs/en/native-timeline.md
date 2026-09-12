# Native Temporal Timeline

`lifetxt timeline ID [PATH ...]` shows the bounded semantic history stored in
the current life.txt inputs. It reads `record:item_event`,
`record:progress_event`, `record:ticket_event`, and `record:time_entry` through
the shared adapter. It never reads or automatically merges Git history.

```bash
lifetxt timeline task-1 life.txt
lifetxt timeline task-1 life.txt --limit 25
lifetxt timeline task-1 life.txt --since 2026-09-01T00:00:00Z --until 2026-09-30T23:59:59Z
lifetxt timeline task-1 life.txt --event relation_added --limit 10
lifetxt timeline task-1 life.txt --json
```

The default limit is 100 valid events and the accepted range is 0–500. Events
are ordered deterministically by normalized time, record-kind rank, parent
sequence, and stable record ID. The result retains the original record kind,
record ID, meaning, timestamp, sequence, transaction, revision provenance,
payload, and validity.

`--since` and `--until` require offset-aware ISO 8601 timestamps and are
inclusive. `--event` accepts one normalized native event type. Multiple filters
use AND semantics. Filters are applied to the ordered valid stream before
`--limit`; `bounds.total_valid_events` is therefore the number matching the
filters. Invalid evidence, diagnostics, limitations, and per-domain
completeness still describe the full input history. Invalid timestamps, an
unknown event type, or `--since` after `--until` are rejected deterministically.
Omitting all filters preserves the original result.

Malformed records are excluded from the main `events` list and returned under
`invalid_events` with diagnostics. Gaps, duplicate identities, backwards time,
discontinuity, current-state disagreement, and truncation prevent a complete
claim. Missing creation evidence is a valid readable partial Timeline, not an
error and not inferred history. Completeness is reported separately for item,
progress, ticket, and time-entry domains.

The JSON result uses
[`temporal-timeline-v1.schema.json`](../../dist/schemas/temporal-timeline-v1.schema.json).
MCP clients can call the read-only `get_native_timeline` tool with the same
`id`, `limit`, `since`, `until`, and `event` contract. Its result is the shared
Timeline document plus the standard source-set `revision`; it does not write
the file or require Git.
For exact Git revisions, continue to use `thread --revision`, `thread --as-of`,
or `thread --diff`; those commands are unchanged.

## Semantic as-of reconstruction

`--as-of TIMESTAMP` reconstructs known/partial/unavailable per-field state at
an offset-aware RFC3339 timestamp, alongside (not instead of) the bounded
event list:

```bash
lifetxt timeline task-1 life.txt --as-of 2026-09-10T11:00:00Z
lifetxt timeline task-1 life.txt --as-of 2026-09-10T11:00:00Z --json
```

`--as-of` uses the same offset-aware RFC3339 cutoff parser as
`show --as-of`/`query --as-of` and rejects a naive or malformed timestamp
with the same message. It cannot be combined with `--summary`, an analysis
flag, or `--compare-window`/`--to-window`.

Each field reports one of three states:

- `known` -- reconstructed from a complete, gap-free item-event chain.
- `partial` -- reconstructed from an applicable event, but the item's event
  chain is not verified complete from creation, so an earlier gap could
  still change the answer.
- `unavailable` -- no applicable event exists at or before the cutoff, or
  this field has no atomic capture route today. **This never falls back to
  the item's current state.**

The projected fields are `status` (lifecycle status), `due` (the `due:`
schedule field, the only schedule field with an atomic capture route today),
`follows`/`realizes`/`replaced_by` (lifecycle relations, replayed from
`relation_added`/`relation_removed` events), and `on`/`from`/`to`/`at`
(always `unavailable` -- these schedule fields have no capture route yet).

This reuses the existing `native_timeline()`/`normalize_native_events()`
reader and `item_event_completeness()` unmodified; it never falls back to
current `life.txt` state and never composes Git.

The `semantic_as_of` field in the JSON result uses
[`semantic-as-of-v1.schema.json`](../../dist/schemas/semantic-as-of-v1.schema.json).
This is a distinct, bounded contract from `temporal-timeline-v1`'s event
list and from `temporal-thread-v1`'s Git-backed `historical`/`as of`
revision snapshot: it never reads Git, and it never claims a field's state
beyond what the captured `record:item_event` stream at or before the
cutoff actually supports.
