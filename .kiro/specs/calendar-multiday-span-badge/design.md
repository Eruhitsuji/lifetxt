# Design Document

## Overview
`loadCalendar()`'s bucketing loop now iterates `_calRecordDayPlacements(record)`
with `.forEach((placement, i) => ...)`, attaching `dayIndex: i + 1` and
`dayTotal: placements.length` to each bucket entry (placements are already
chronologically ordered, since `record.matches` is server-sorted).
`_calEntryHtml` gains two new parameters (`dayIndex`, `dayTotal`) and
renders a `.cal-entry-span` badge (`${dayIndex}/${dayTotal}`, `title="Day
${dayIndex} of ${dayTotal}"`) only when `dayTotal > 1`. A new
`I18N_PATTERNS` entry translates the `title` tooltip for Japanese.

## Boundary Commitments
### This Spec Owns
- The `dayIndex`/`dayTotal` computation in `loadCalendar()`'s bucketing
  loop, `_calEntryHtml`'s new parameters and badge rendering, the
  `.cal-entry-span` CSS, and the new `I18N_PATTERNS` entry.
### Out of Boundary
- `_calRecordDayPlacements` itself -- unchanged, already returns
  chronologically-ordered placements.
- Any spanning-bar/connected-cell visual redesign -- explicitly rejected in
  favor of this lighter per-cell badge, matching the decision already made
  when the underlying placement fix was scoped.
### Allowed Dependencies
- None new; reuses `escapeHtml`, the existing `I18N_PATTERNS` mechanism.

## File Structure Plan
### Modified Files
- `lifetxt/web_assets.py` -- CSS, `_calEntryHtml`, `loadCalendar()`,
  `I18N_PATTERNS`.
- `tests/test_lifetxt.py` -- regression tests (existing call-site assertion
  updated for the new parameters, new badge-presence test).

## Requirements Traceability
| Requirement | Design Element |
| --- | --- |
| 1.1, 1.3 | `dayTotal > 1 ? <span class="cal-entry-span">...</span> : ""` |
| 1.2 | `placements.forEach((placement, i) => ...)` -- `i` follows the already-chronological placement order |
| 1.4 | `title="Day ${dayIndex} of ${dayTotal}"` (translated at runtime via the existing `I18N_ATTRIBUTES`/`title` walker); new `I18N_PATTERNS` entry `[/^Day (\d+) of (\d+)$/, "$2日間中 $1日目"]` |

## Testing Strategy
- Manual Node.js verification (not part of the committed suite): extracted
  `_calRecordDayPlacements`/`_calEntryHtml`/`escapeHtml` source; confirmed a
  3-day record produces badges "1/3", "2/3", "3/3" in chronological order,
  and a single-day record renders no `cal-entry-span` element at all.
- Python source-assertion tests: the existing multi-day-placement test's
  render-call-site assertion updated for the new `dayIndex`/`dayTotal`
  arguments; a new test confirms `cal-entry-span` markup and the
  `dayTotal > 1` guard are present in the served page.
- `tests.test_release_policy`/`tests.test_web_i18n` re-run to confirm the
  new dynamic tooltip text does not create an untranslated-chrome gap
  (learned from the earlier help-modal translation-coverage regression in
  this same batch).
- Live verification: real `lifetxt serve` process with a 3-day `on:`/`on:`/
  `on:` fixture and a plain single-day fixture; served page confirmed to
  contain the `cal-entry-span` markup.
