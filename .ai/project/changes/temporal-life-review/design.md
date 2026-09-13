# Design

`build_temporal_review()` composes existing engines rather than adding a new
history source:

- `workspace_timeline()` supplies the bounded, deduplicated event stream for
  the requested `since`/`until` (or `--week`) window; the review only groups
  and counts those events (`created`/`completed` excluded from "changed",
  `completed` counted separately, `reopened`/`canceled`/`schedule_changed`
  counted as "reopened_or_rescheduled").
- `agenda_records()` supplies the "upcoming" section: items with an occurrence
  at or after the review's `until` boundary, with no upper bound, matching the
  same match/format helpers `agenda`/`next` already use.
- Carry-forward is a direct scan of `items` for open Task-kind records, scoped
  by `--project` the same way the rest of the review is; it makes no claim
  about their status *during* the reviewed period.

`command_review --temporal` is a thin CLI adapter: it resolves `--since`/
`--until`/`--week`/`--project`/`--limit`, calls `build_temporal_review()`, and
renders the result as text or JSON. Completeness and limitations reported by
`workspace_timeline()` are surfaced unchanged.
