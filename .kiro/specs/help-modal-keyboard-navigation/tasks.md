# Implementation Plan

- [x] 1. Track _helpCmdEntries/_helpCmdIndex in renderHelpModalCommands and mark the focused row, adding row click handlers
  - _Requirements: 1.4, 2.3_
- [x] 2. Add _helpCmdMoveFocus (wraparound) and _runHelpModalCommand (close + runWebCommand)
  - _Requirements: 1.1, 1.2, 1.3, 2.1, 2.2_
- [x] 3. Wire a keydown listener on #help-command-search for ArrowDown/ArrowUp/Enter; focus the search box on open
  - _Requirements: 1.1, 1.2, 2.1, 3.1, 3.2_
- [x] 4. Add CSS for the focused/hovered row and cursor affordance
  - _Requirements: 2.3_
- [x] 5. Add regression tests (Node.js manual verification, Python source assertions) and live verification
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 2.1, 2.2, 2.3, 3.1, 3.2_
