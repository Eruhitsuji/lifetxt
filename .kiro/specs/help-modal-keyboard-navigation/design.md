# Design Document

## Overview
Mirrors the Ctrl+K command palette's existing keyboard-navigation pattern
(`_cmdkIndex`/`_cmdkMoveFocus`) for the help modal's command list.
`renderHelpModalCommands()` now tracks `_helpCmdEntries`/`_helpCmdIndex`,
marks the current row with a `.focus` class, and attaches a click handler
to every row (previously absent -- rows were unclickable). A new
`_helpCmdMoveFocus(delta)` moves the selection with wraparound, and
`_runHelpModalCommand(index)` closes the modal and delegates to the
existing `runWebCommand`, which already handles the TUI-only case with an
informative toast. `openHelpModal()`'s `openManagedModal` call now focuses
`#help-command-search` instead of the modal's first button.

## Boundary Commitments
### This Spec Owns
- `_helpCmdEntries`/`_helpCmdIndex` state, `_helpCmdMoveFocus`,
  `_runHelpModalCommand`, the row click handlers added in
  `renderHelpModalCommands`, the new `keydown` listener on
  `#help-command-search`, and `openHelpModal`'s focus-target change.
### Out of Boundary
- The Ctrl+K command palette (`_cmdkMoveFocus`, etc.) -- unchanged,
  used only as the reference pattern.
- `runWebCommand`, `matchingCommands`, `COMMAND_CATALOG` -- unchanged,
  reused as-is.
- The global Escape handler that already closes the help modal -- reused
  unmodified; no Escape handling is duplicated in the new listener.
### Allowed Dependencies
- `runWebCommand`, `closeHelpModal`, `_helpCmdEntries` (populated by
  `renderHelpModalCommands`, already existing).

## File Structure Plan
### Modified Files
- `lifetxt/web_assets.py` -- CSS (`.help-command-row.focus`/`:hover`,
  `cursor: pointer`), `renderHelpModalCommands`, `_helpCmdMoveFocus`,
  `_runHelpModalCommand`, `openHelpModal`, new `DOMContentLoaded` listener.
- `tests/test_lifetxt.py` -- regression test.

## Requirements Traceability
| Requirement | Design Element |
| --- | --- |
| 1.1, 1.2 | `_helpCmdMoveFocus(delta)`: `(_helpCmdIndex + delta + length) % length` |
| 1.3 | `if (!_helpCmdEntries.length) return;` guard |
| 1.4 | `renderHelpModalCommands()` resets `_helpCmdIndex = matches.length ? 0 : -1` on every render (every keystroke) |
| 2.1, 2.2 | `_runHelpModalCommand(index)`: `closeHelpModal(); runWebCommand("/" + command.name);` -- identical call shape to the palette's own `entry.run()`, so the existing terminal-only toast in `runWebCommand` fires unchanged |
| 2.3 | Each row gets `row.addEventListener("click", () => _runHelpModalCommand(i))` in the same render pass that assigns `.focus` |
| 3.1 | `openManagedModal(document.getElementById("help-modal"), "#help-command-search")` (previously `"button"`) |
| 3.2 | No change to the existing document-level `Escape` handler, which already checks `#help-modal`'s `open` class before calling `closeHelpModal()` |

## Testing Strategy
- Manual Node.js verification (not part of the committed suite): extracted
  `_helpCmdMoveFocus`/`_runHelpModalCommand` against a stub `document` and
  spy `closeHelpModal`/`runWebCommand` -- confirmed forward/backward
  wraparound, a no-op on an empty list, `Enter` closing the modal and
  calling `runWebCommand("/help")` for the highlighted entry, and an
  invalid index being a no-op.
- Python source-assertion test (established pattern): fetch the served
  page, assert `_helpCmdMoveFocus`/`_runHelpModalCommand` exist, the new
  `keydown` listener handles `ArrowDown`/`ArrowUp`/`Enter`, and
  `openHelpModal` passes `"#help-command-search"` as its focus target.
- Live verification: real `lifetxt serve` process, served page confirmed
  to contain the new functions.
- Full suite plus `tests.test_release_policy`/`tests.test_web_i18n`
  re-run to confirm no new untranslated-chrome gap (this change adds no
  new user-visible static or dynamic text, only behavior).
