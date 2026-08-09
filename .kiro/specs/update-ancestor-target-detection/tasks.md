# Implementation Plan

- [x] 1. Generalize command_update's "nothing to do" check from exact equality to ancestry via git merge-base --is-ancestor
  - _Requirements: 1.1, 1.2, 1.3, 1.4_
- [x] 2. Update the mocked test dispatchers for the new merge-base call and add a dedicated regression test
  - _Requirements: 1.1, 1.2, 1.3_
- [x] 3. Live-verify against a disposable clone (ancestor case and normal forward-update case)
  - _Requirements: 1.1, 1.2, 1.3, 1.4_
