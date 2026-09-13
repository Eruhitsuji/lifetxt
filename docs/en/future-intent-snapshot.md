# Future Intent Snapshot

This is the investigation outcome for #812. A Future Intent Snapshot is a
bounded, deterministic projection of records that describe planned work or a
future constraint at an explicit evaluation time.

The first implementation slice should include only:

- `T` records with an explicit planned execution (`do:` or `on:`/`at:`)
- `D` records with an explicit deadline (`due:`)
- `R` reminders with an explicit scheduled time
- `G` goals and `P` personal goals when they have explicit future evidence

The projection must preserve record IDs, source locations, and the original
time vocabulary. It must not infer success, failure, missed execution, or
causality. Plan-vs-actual composition may classify only explicit states such as
`planned`, `schedule_changed`, `canceled`, `explicitly_realized`, and
`still_open_at_end`. Missing evidence remains `unobserved`, never `completed`.

The snapshot is intentionally separate from Temporal Life Review (#808) and
Historical Personal Context (#809): those features consume observed history or
as-of semantic state, while this investigation defines future intent only.
