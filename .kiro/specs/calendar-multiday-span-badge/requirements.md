# Requirements Document

## Project Description (Input)
The Calendar view's earlier fix (`cap-calendar-multiday-placement`) made a
multi-day record appear on every day it matches, but each cell's entry
looks identical and independent -- there is no visual cue that, say, three
adjacent cells are actually one continuous 3-day trip rather than three
unrelated same-titled records. A full connecting spanning-bar redesign was
explicitly considered and rejected earlier in favor of the simpler
per-cell-placement approach; this adds a lightweight "day X of Y" indicator
to each placement instead, without redesigning the grid.

## Requirements

### Requirement 1: Multi-day records show a day-position indicator
**Objective:** As a Web UI user viewing the Calendar, I want a multi-day
record's cells to indicate their position within the span, so that I can
tell at a glance that several cells belong to the same continuous event.

#### Acceptance Criteria
1. WHEN a record has more than one day placement, THE SYSTEM SHALL show a
   compact "day index / total days" badge on each of its cell entries.
2. THE SYSTEM SHALL number the badge in chronological order (day 1 is the
   earliest matched day).
3. WHEN a record has only one day placement, THE SYSTEM SHALL NOT show any
   badge, so single-day records are visually unchanged.
4. THE badge SHALL be a full tooltip ("Day X of Y") on hover, and SHALL be
   translated into Japanese when the interface language is Japanese.

## Out of Scope
- A connecting visual bar spanning adjacent grid cells (explicitly
  considered and rejected during the original multi-day placement work in
  favor of independent per-cell placement).
- Any change to which days a record is placed on (owned by the existing
  `_calRecordDayPlacements`, unmodified).
