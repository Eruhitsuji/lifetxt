# Implementation Plan

- [x] 1. Add the search input and command-list container to the help modal, with supporting CSS
  - _Requirements: 1.1, 1.6_
- [x] 2. Add renderHelpModalCommands(), reusing matchingCommands()/COMMAND_CATALOG, and wire it into openHelpModal()
  - _Requirements: 1.2, 1.3, 1.4, 1.5, 2.1, 2.2_
- [x] 3. Add ja translations for the new static strings
  - _Requirements: 1.1_
- [x] 4. Add regression test and manual verification
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 2.1, 2.2_
