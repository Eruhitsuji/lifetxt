# Requirements Document

## Project Description (Input)
The Web UI help modal's searchable command reference (added earlier in
this batch) had a search box and a filtered list, but no keyboard
selection: a user had to click a result with the mouse to run it, and
the rows had no click handler at all, so nothing happened either way. The
Ctrl+K command palette already has exactly this UX (`_cmdkMoveFocus`,
arrow-key selection, Enter-to-run). Add the same keyboard operation to the
help modal's command list for parity.

## Requirements

### Requirement 1: Arrow keys move selection through the filtered command list
**Objective:** As a Web UI user searching commands in the help modal, I
want to move the highlighted selection with the arrow keys, so that I can
pick a command without touching the mouse.

#### Acceptance Criteria
1. WHEN the search box has focus and the user presses ArrowDown, THE
   SYSTEM SHALL move the highlighted selection to the next command in the
   filtered list, wrapping to the first after the last.
2. WHEN the search box has focus and the user presses ArrowUp, THE SYSTEM
   SHALL move the highlighted selection to the previous command, wrapping
   to the last after the first.
3. WHEN the filtered list is empty, THE SYSTEM SHALL NOT change the
   selection or raise an error on ArrowDown/ArrowUp.
4. WHEN the filtered list changes (a new search is typed), THE SYSTEM
   SHALL reset the highlighted selection to the first result.

### Requirement 2: Enter runs the highlighted command
**Objective:** As a Web UI user, I want Enter to run the highlighted
command, so that I can select and execute a command without leaving the
keyboard.

#### Acceptance Criteria
1. WHEN the search box has focus, a command is highlighted, and the user
   presses Enter, THE SYSTEM SHALL close the help modal and run that
   command, matching the command palette's existing execution path
   (`runWebCommand`).
2. WHEN the highlighted command is TUI-only, THE SYSTEM SHALL close the
   modal and let the existing terminal-only toast explain why nothing
   happened, rather than silently doing nothing.
3. Clicking a command row SHALL behave identically to highlighting it with
   the arrow keys and pressing Enter.

### Requirement 3: Opening the modal enables keyboard navigation immediately
**Objective:** As a Web UI user pressing `?` for help, I want to be able
to start typing and navigating immediately, so that using the keyboard
path doesn't require an extra click to focus the search box first.

#### Acceptance Criteria
1. WHEN the help modal opens, THE SYSTEM SHALL focus the command search
   box rather than the modal's first button.
2. Existing Escape-to-close behavior for the help modal SHALL be
   unchanged.
