# Lifecycle analytics

`lifetxt timeline --summary --json --id ITEM` exposes the additive
`lifecycle-analytics-v1` result. The reader filters to valid native events
before aggregating, so `--limit` only bounds presentation; analytics are not
silently changed by a small display limit. Unsupported or incomplete history
is reported in `limitations` and `complete`.

Available projections are `duration`, `status-dwell`, `schedule-analysis`,
`relation-analysis`, `completion-cycles`, `transitions`, `gaps`, `cadence`,
`oscillation`, `provenance`, `progress-analysis`, `effort`,
`schedule-lead-time`, and `due-variance`. Two explicit windows can be compared
with `--compare-window START..END --to-window START..END`.

`lifecycle-stats --json` aggregates the same timeline reader across workspace
items and reports complete/partial/none coverage both per item and by
domain/project, with correct `total > limit` truncation semantics. It can
include a bounded duration distribution with deterministic min/max item IDs.
`thread --metrics`,
`--replacement-analysis`, `--consistency-summary`, and
`--realization-analysis` are read-only projections over the bounded explicit
thread. The MCP `get_lifecycle_analytics` tool returns the same schema and
preserves provenance and limitations.

Human-readable CLI output includes the same aggregate counts as JSON plus the
selected projection fields. Window comparison includes event-type deltas;
cadence uses the configured workspace timezone; partial history is never
reported as a definitive absence of schedule evidence.

The interface is additive: existing `temporal-timeline-v1` fields are not
changed. Analytics do not read Git, mutate `life.txt`, or infer a due date from
the current item when history does not contain one.
