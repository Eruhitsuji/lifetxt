# Design Document

## Overview
Replace the Calendar view's single-day placement function
(`_calRecordDay(record)`, `lifetxt/web_assets.py`) with
`_calRecordDayPlacements(record)`, which returns one `{day, when}` pair per
distinct matched day instead of always reading `matches[0]`. `loadCalendar()`
buckets each record into every returned day's cell (deduplicated per day),
and `_calEntryHtml` takes the day-specific `when` as an explicit second
parameter so each cell's rendered entry reflects its own day rather than
always the first match.

## Boundary Commitments
### This Spec Owns
- `_calRecordDay`/`_calRecordDayPlacements`, `_calEntryHtml`'s `when`
  computation, and `loadCalendar()`'s day-bucketing loop and rendering call
  site (all in `lifetxt/web_assets.py`).
### Out of Boundary
- The Timeline view (`_tlDisplayInfo`, `loadTimeline()`). Investigated and
  found not to exhibit the same defect: it queries the exact visible window
  and the server already returns only the matches inside that window, so
  `matches[0]` is always the correct (and only relevant) entry for a
  chronological single-row-per-record list. No change made.
- The server-side `lifetxt.agenda.agenda_records`/`item_time_matches`
  match-generation logic, which already returns every matching day
  correctly (verified directly) -- the defect is presentation-only.
- The Calendar grid's day-header/weekday-name construction, empty-state
  handling, and overflow "+N more" button, all unchanged.
### Allowed Dependencies
- `record.matches[i].start` (already present per-match from the server).
- `record.occurrence_start` (unchanged single-occurrence fast path).

## File Structure Plan
### Modified Files
- `lifetxt/web_assets.py` -- `_calRecordDayPlacements`, `_calEntryHtml`,
  `loadCalendar()`.
- `tests/test_lifetxt.py` -- regression test.

## Requirements Traceability
| Requirement | Design Element |
| --- | --- |
| 1.1, 1.2 | `_calRecordDayPlacements` iterates `record.matches`, dedupes by day via a `Set`, returns one placement per distinct day |
| 1.3 | `_calEntryHtml(record, dayWhen)` uses `dayWhen` first when computing its `when` string; `loadCalendar()`'s render call site passes each bucket entry's own `when` |
| 1.4, 2.1 | `_calRecordDayPlacements` falls back to `occurrence_start` (single placement) then plain `record.when` (single placement) when `matches` is absent/empty, preserving prior single-day behavior byte-for-byte |
| 2.2 | `loadCalendar()`'s day-bucketing `Map` and overflow slicing are otherwise unchanged |

## Testing Strategy
- Source-assertion test (matching this repo's established pattern for
  frontend JS): fetch the served page, assert `_calRecordDayPlacements`
  exists and `_calRecordDay(` no longer does, and assert the per-day
  rendering call site passes `entry.when` rather than relying on the
  default first match.
- Manual/one-time verification (not part of the committed suite): a
  Node.js run of the extracted function source against four cases --
  3-day multi-day event places on all 3 days; an `occurrence_start`-based
  repeat record places once; a plain `matches`-less record places once via
  its `when` fallback; per-day HTML differs by day. All four passed.
- Server-side confirmation (not a new test, a design-time check): direct
  calls to `lifetxt.agenda.agenda_records()` confirm `matches` already
  contains one entry per matched day in range, and that Timeline's
  per-window query already receives only the in-window subset -- the basis
  for excluding Timeline from this change's scope.
