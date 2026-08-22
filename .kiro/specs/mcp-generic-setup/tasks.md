# Implementation Plan

> **This file is working material, not the task source of truth.** See
> `.ai/managed/core/TASK_MANAGEMENT.md`; actionable work lives in GitHub
> Issues. See #101 for the decision behind this.

Tracked by [#505](https://github.com/Eruhitsuji/lifetxt/issues/505), the
second implementation child of the #500 AI-integration epic. Standard
assurance, S-sized; no separate change package needed per
`.ai/project/changes/README.md`'s threshold.

## Tasks

- [ ] 1. Add the `ai setup generic` CLI command
- [ ] 1.1 Add the `ai`/`setup`/`generic` nested subparsers and `command_ai_setup_generic`
  - Resolve input paths and write target using the same helpers `lifetxt mcp` uses (`resolve_write_target`, `normalize_server_paths`), never constructing an `McpContext`
  - Default `--profile` to `read`; accept `assist`/`full` via `argparse choices=`
  - Print a `python -m lifetxt mcp ...` command line and a generic `mcpServers` JSON snippet in text mode; print one JSON object in `--format json` mode
  - Observable: `lifetxt ai setup generic` against a fixture workspace prints a command whose arguments match the fixture's resolved paths/write-file, defaulting to `--profile read`
  - _Requirements: 1.1, 1.2, 1.3, 2.1, 2.2, 2.3, 3.1, 3.2_
  - _Boundary: command_ai_setup_generic_

- [ ] 2. Validation
- [ ] 2.1 Unit tests for resolution, profile defaulting, and no-write guarantee
  - Cover default-to-read, explicit `--profile assist`/`full`, invalid `--profile` rejection, `--format json` shape, and that the fixture directory's file set is byte-for-byte unchanged after running the command
  - Observable: `python -m unittest tests.test_lifetxt` passes with the new cases
  - _Requirements: 1.1, 1.2, 1.3, 2.1, 2.2, 2.3, 3.1, 3.2_
  - _Depends: 1.1_

- [ ] 2.2 (P) Document the command
  - Update `docs/en/ai-integration.md` / `docs/ja/ai-integration.md` (client setup section) and `docs/en/cli.md` / `docs/ja/cli.md` (command reference)
  - Observable: `scripts/validate_release_docs.py` reports zero errors
  - _Requirements: none beyond documenting 1-3 accurately_
  - _Boundary: Documentation_
