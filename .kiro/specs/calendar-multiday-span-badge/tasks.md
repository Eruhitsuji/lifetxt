# Implementation Plan

- [x] 1. Compute dayIndex/dayTotal in loadCalendar()'s bucketing loop
  - _Requirements: 1.1, 1.2_
- [x] 2. Add the cal-entry-span badge to _calEntryHtml, shown only when dayTotal > 1
  - _Requirements: 1.1, 1.3_
- [x] 3. Add CSS for the badge and an I18N_PATTERNS entry for its tooltip
  - _Requirements: 1.4_
- [x] 4. Add regression tests (Python source assertions, Node.js manual verification, i18n coverage re-check) and live verification
  - _Requirements: 1.1, 1.2, 1.3, 1.4_
