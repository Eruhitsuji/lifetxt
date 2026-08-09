# Implementation Plan

- [x] 1. Add _git_commit_summary (bounded, fail-open on git errors)
  - _Requirements: 1.1, 1.2, 2.1, 2.2_
- [x] 2. Wire the commit list into command_update's dry-run and --yes success messages/JSON
  - _Requirements: 1.1, 1.2, 1.3, 1.4_
- [x] 3. Document the preview in docs/en/cli.md and docs/ja/cli.md
  - _Requirements: 1.1, 1.2, 1.3_
- [x] 4. Add regression tests and live verification against a real disposable clone
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 2.1, 2.2_
