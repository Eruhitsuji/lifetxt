# Requirements Document

## Project Description (Input)
The Web UI's Calendar view does not correctly render records that match more
than one day (a multi-day all-day span expressed as several `on:DATE` detail
values, or several repeat occurrences visible in the same grid). The server
already returns every matching day as its own entry in `record.matches`
(verified directly via `lifetxt.agenda.agenda_records`: a record with
`on:2026-08-10 on:2026-08-11 on:2026-08-12` produces three `matches` entries
when queried over a range covering all three days). The frontend's
`_calRecordDay(record)` (`lifetxt/web_assets.py`) reads only `matches[0]`,
so the record is placed in exactly one calendar cell -- the earliest matched
day -- and silently dropped from every other day it actually falls on. This
matches the user's bug report: Google Calendar-imported multi-day all-day
events (and any other record with more than one `on:` value) do not appear on
every day they span in the Web UI calendar.

A parallel investigation (the report's own "check whether the same
phenomenon occurs elsewhere" ask) covered two adjacent areas:
- **Other record kinds**: the placement bug is in the generic per-record
  calendar-cell placement path, not anything event(`E`)-specific -- it
  affects every kind (`T`/`E`/`N`/etc.) that can carry multiple `on:` values.
  Fixing the generic path fixes all kinds at once; no kind-specific handling
  is needed or in scope.
- **Timeline view**: confirmed, by calling `agenda_records()` directly with
  both a full-week range and a single-day range against the same multi-day
  fixture, that the server already filters `matches` down to only the
  entries inside the requested window before the frontend ever sees them.
  Timeline queries exactly the visible window (today/24h/week) and renders
  one chronological row per record, not a per-day grid, so it already shows
  the correct day-specific match whenever it is re-queried for a different
  window. No defect was found in Timeline's handling of multi-day records;
  it is explicitly out of scope for this change.

## Requirements

### Requirement 1: Every matched day gets its own calendar-cell entry
**Objective:** As a Web UI user viewing the Calendar, I want a record with
more than one matched day to appear on every one of those days, so that
multi-day all-day events (including ones imported from Google Calendar) are
not silently missing from most of the days they cover.

#### Acceptance Criteria
1. When a record's `matches` array contains more than one entry with a
   distinct day, the Calendar view shall render that record in the calendar
   cell for every one of those distinct days.
2. When two or more matches fall on the same day (e.g. duplicate `on:`
   values, or an `occurrence_start`-based repeat record combined with an
   overlapping `on:` value), the Calendar view shall render the record only
   once in that day's cell.
3. Each day's rendered entry shall reflect that day's own match time/detail
   (via its `when` value), not always the first match's, so that a
   time-of-day shown in one day's cell is not silently copied from a
   different day.
4. Records with no `matches` array (a plain single `when`/`occurrence_start`
   field, e.g. non-agenda-derived records) shall continue to render exactly
   as before -- this requirement changes multi-match placement only.

### Requirement 2: No regression to single-day and repeat-occurrence records
**Objective:** As a Web UI user, I want records that only ever match one day
to keep rendering exactly as they did before this change.

#### Acceptance Criteria
1. When a record has exactly one match (a plain `due:`/`do:` item, a single
   `on:` value, or one repeat occurrence), the Calendar view shall render it
   in exactly one cell, identical to prior behavior.
2. The existing overflow ("+N more") behavior for a day with more entries
   than fit in its cell shall be unaffected by this change.
