# Design

Pass datetime.datetime.max, the established Agenda open-ended end sentinel,
instead of None. Reuse Agenda date matching, ordering, span overlap and its
366-day cap for recurring expansion. Temporal Review still returns the first
limit upcoming rows after composition. Apply its existing project filter to
upcoming targets as well as historical events and carry-forward rows. Scoped
inputs are supplied by the #1154 dedicated target/history scope helper.

No public parameter/schema changes, new recurrence engine or authoritative
mutation. Alternative: choose a new arbitrary future window. Rejected because
it would exclude distant nonrecurring rows and change the shared Agenda policy.

Risks: recurrence is finite under the existing Agenda policy; ongoing spans
overlapping the period-end boundary can appear, per existing Agenda semantics.

Upcoming projection explicitly excludes native history records (including
malformed payloads), while timeline validation retains them. Carry-forward
continues to include only Task targets; native history consists of Note records.
