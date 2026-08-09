# Implementation Plan

- [x] 1. Add _resolve_update_check_repo and the --repo flag; wire command_update_check to use it
  - _Requirements: 1.2, 1.3, 2.1, 2.2, 2.3, 3.1_
- [x] 2. Register update.repository in the config registry and config-v1.schema.json (generator plus mirrored dist file)
  - _Requirements: 1.1, 1.4_
- [x] 3. Document the setting in docs/en/config.md, docs/ja/config.md, docs/en/cli.md, docs/ja/cli.md
  - _Requirements: 1.1, 2.1_
- [x] 4. Add regression tests and live verification
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 2.1, 2.2, 2.3, 3.1_
