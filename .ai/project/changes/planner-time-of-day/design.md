# Design

GET /api/config publishes today and offset-aware current_datetime from one
workspace timezone-policy clock snapshot. Planner uses monotonic elapsed time
and a two-minute maximum sample age; resume invalidates the clock. The existing
one-minute config loop is reused, with one in-flight synchronization. Slow (>10s),
missing, invalid, failed or date-inconsistent time falls back to Standard.

The Today summary adds links and CSS emphasis only. It never reorders sections
or canonical proposals, hides records, or starts a Daily Flow request. Visible
Morning/Daytime sections link to existing server-ranked Tasks and Schedule;
Daytime marks ongoing/future candidate cards without removing others. Evening
links to completion evidence from the existing bounded scoped Temporal Review,
Habits and Journal. Generation checks reject stale day/scope results; summary
content is cleared during loading. Review errors are isolated and labeled.

Custom HH:MM boundaries require Morning < Daytime < Evening and are stored in
lifetxt_planner_prefs_v1.time_bands. Legacy/malformed values restore just the
bands; existing explicit section settings remain higher priority. Reset removes
local overrides. No new runtime dependency, server config key or authoritative
data field. Rollback the isolated UI/config timestamp addition; no migration.
