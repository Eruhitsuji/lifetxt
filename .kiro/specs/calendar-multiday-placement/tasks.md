# Implementation Plan

- [x] 1. Replace `_calRecordDay` with `_calRecordDayPlacements`, returning one placement per distinct matched day
  - _Requirements: 1.1, 1.2, 1.4, 2.1_
- [x] 2. Thread a day-specific `when` through `_calEntryHtml` and `loadCalendar()`'s bucketing/render call site
  - _Requirements: 1.3, 2.2_
- [x] 3. Add regression test confirming the fix and catching the prior single-day-only function
  - _Requirements: 1.1, 1.2, 1.3_
- [x] 4. Investigate Timeline and other record kinds for the same phenomenon; record findings (no code change needed)
  - _Requirements: (investigation only, not requirement-mapped)_
