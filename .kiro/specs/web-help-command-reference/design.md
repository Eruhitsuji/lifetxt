# Design Document

## Overview
Add a "Commands" section to the existing `#help-modal` (`lifetxt/web_assets.py`):
a search `<input>` and a `<div id="help-command-list">`, rendered by a new
`renderHelpModalCommands()` function that reuses the already-existing
`matchingCommands(typed)` helper (the same one the command palette's
`renderCmdkCommands` uses) rather than reimplementing filtering.
`openHelpModal()` resets the search box and calls the new renderer whenever
the modal opens.

## Boundary Commitments
### This Spec Owns
- The new HTML section inside `#help-modal`, `renderHelpModalCommands()`,
  and `openHelpModal()`'s call to it.
### Out of Boundary
- The command palette (`renderCmdk`/`renderCmdkCommands`/`openCmdk`) --
  unchanged, reused as the source of truth for matching behavior.
- `/api/commands` and `COMMAND_CATALOG`/`loadCommandCatalog()` -- unchanged,
  reused as-is.
- The keyboard-shortcuts table and its rendering -- unchanged.
### Allowed Dependencies
- `COMMAND_CATALOG`, `loadCommandCatalog()`, `matchingCommands()`,
  `escapeHtml()` (all pre-existing).

## File Structure Plan
### Modified Files
- `lifetxt/web_assets.py` -- CSS for the new list/rows, HTML section inside
  `#help-modal`, `renderHelpModalCommands()`, `openHelpModal()` wiring, and
  new `ja` dictionary entries for the new static strings.
- `tests/test_lifetxt.py` -- regression test.

## Requirements Traceability
| Requirement | Design Element |
| --- | --- |
| 1.1, 1.2 | New `<input id="help-command-search">` and `<div id="help-command-list">` inside `#help-modal`; `renderHelpModalCommands()` called with an empty search value on open |
| 1.3, 2.2 | `renderHelpModalCommands()` calls `matchingCommands(typed)` -- identical matcher to the command palette |
| 1.4 | Each row renders `/name usage`, `(/alias)` when present, and `summary` |
| 1.5 | `command.web === false` renders a `.help-command-badge` reading "TUI only" |
| 1.6 | Empty `matches` renders a `.help-command-empty` message instead of an empty list |
| 2.1 | `renderHelpModalCommands()` awaits `loadCommandCatalog()` only if `COMMAND_CATALOG` is still empty, then reads from the same shared array the palette populates |

## Testing Strategy
- Source-assertion test (established pattern): fetch the served page,
  assert the new element IDs and `renderHelpModalCommands` exist, assert it
  calls `matchingCommands(typed)` and `loadCommandCatalog()` rather than a
  second implementation, and assert `openHelpModal()` calls the new
  renderer.
- Manual Node.js verification (not part of the committed suite): extracted
  `fuzzyMatch`/`escapeHtml`/`commandByName`/`matchingCommands`/
  `renderHelpModalCommands` against a stub `document` and a small
  `COMMAND_CATALOG` fixture -- confirmed unfiltered listing, filtering by a
  query, the TUI-only badge appearing only on `web: false` commands, and the
  empty-state message for a non-matching query.
- Live verification: real `lifetxt serve` process, `GET /api/commands`
  confirms the real catalog shape (31 commands, a mix of `web: true/false`
  in this run), and `GET /` confirms the served page contains the new
  markup.
- `tests/test_web_i18n.py` (unmodified) confirms the new `ja` dictionary
  entries are present and are genuinely Japanese.
