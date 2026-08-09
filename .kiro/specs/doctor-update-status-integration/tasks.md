# Implementation Plan

- [x] 1. Add --check-update/--repo/--update-timeout to the doctor subparser
  - _Requirements: 1.1, 1.5, 1.6_
- [x] 2. Add the update check row to command_doctor, reusing update-check's resolution helpers, fail-open on any error
  - _Requirements: 1.2, 1.3, 1.4, 2.1, 2.2_
- [x] 3. Document --check-update in docs/en/cli.md and docs/ja/cli.md, including the doctor check table
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6_
- [x] 4. Add regression tests and live verification
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 2.1, 2.2_
