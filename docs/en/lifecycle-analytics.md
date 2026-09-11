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
items and can include a bounded duration distribution. `thread --metrics`,
`--replacement-analysis`, `--consistency-summary`, and
`--realization-analysis` are read-only projections over the bounded explicit
thread. The MCP `get_lifecycle_analytics` tool returns the same schema and
preserves provenance and limitations.

The interface is additive: existing `temporal-timeline-v1` fields are not
changed. Analytics do not read Git, mutate `life.txt`, or infer a due date from
the current item when history does not contain one.
