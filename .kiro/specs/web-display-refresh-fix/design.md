# Design Document

## Overview
One-line fix: `configureAutoRefresh()` (`lifetxt/web_assets.py`) computes its Display/Kiosk fallback interval from `appConfig.web.display_refresh` instead of the hardcoded literal `"60"`, mirroring the sibling `configureNotificationPolling()` function's existing pattern of reading its fallback from `appConfig`.

## Boundary Commitments
### This Spec Owns
- `configureAutoRefresh()`'s fallback-interval computation only.
### Out of Boundary
- `configureNotificationPolling()` itself (already correct, used only as the reference pattern).
### Allowed Dependencies
- `appConfig.web.display_refresh` (already served by `/api/config`, confirmed live).

## File Structure Plan
### Modified Files
- `lifetxt/web_assets.py`
- `tests/test_lifetxt.py`

## Requirements Traceability
| Requirement | Design Element |
| --- | --- |
| 1.1, 1.2 | `const displayFallback = String(appConfig?.web?.display_refresh \|\| 60);` used as the Display/Kiosk branch of the existing ternary |
| 1.3 | The existing `firstParam(query(), ["refresh"], ...)` call is unchanged in structure -- URL param still takes priority |

## Testing Strategy
- Source-assertion test (matching this repo's established pattern for frontend JS, since no JS execution harness exists): fetch the served page, extract the `configureAutoRefresh` function body, assert it references `appConfig?.web?.display_refresh` and no longer contains the bare `"60"` literal.
- Live: real server with `web.display_refresh: 45` configured; confirm `/api/config` reports `45` and the served JS reads it.
