# Decisions

- Reuse `workspace_timeline()` and `agenda_records()` unmodified rather than
  building a second historical-event or occurrence-matching engine.
- Treat currently open tasks as explicit "carry forward" context, not history;
  never synthesize a past state for them.
- "Upcoming" reuses `agenda_records()` bounded to the review's own `until`
  boundary with no upper limit, so a reviewed period's carry-forward horizon
  matches the same occurrence semantics `agenda`/`next` already use.
