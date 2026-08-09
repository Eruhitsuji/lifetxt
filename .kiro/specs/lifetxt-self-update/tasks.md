# Implementation Plan

- [x] 1. Add _lifetxt_install_root, _run_git_for_update (with UTF-8-safe decoding and timeout handling), and _reject_option_like_git_arg
  - _Requirements: 1.1, 4.1, 5.1, 5.2, 5.3_
- [x] 2. Add command_update: git-state guards (working tree, dirty check, detached HEAD), target resolution reusing update-check's helpers, dry-run/--yes branching, fetch-then-ff-only-merge
  - _Requirements: 1.2, 1.3, 1.4, 1.5, 1.6, 2.1, 2.2, 2.3, 3.1, 3.2, 3.3, 3.4_
- [x] 3. Register the update subparser and wire it to command_update
  - _Requirements: 2.1, 2.2_
- [x] 4. Document the command in docs/en/cli.md and docs/ja/cli.md
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.6, 2.1, 3.4_
- [x] 5. Add regression tests (git subprocess mocked) and live end-to-end verification against a disposable clone
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 2.1, 2.2, 2.3, 3.1, 3.2, 3.3, 3.4, 4.1, 5.1, 5.2, 5.3_
