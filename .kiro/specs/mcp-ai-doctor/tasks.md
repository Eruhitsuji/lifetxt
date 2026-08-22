# Implementation Plan

> **This file is working material, not the task source of truth.** See
> `.ai/managed/core/TASK_MANAGEMENT.md`. See #101 for the decision behind
> this.

Tracked by [#507](https://github.com/Eruhitsuji/lifetxt/issues/507), the
third implementation child of the #500 AI-integration epic. Standard
assurance, S-sized; no separate change package per
`.ai/project/changes/README.md`'s threshold.

## Tasks

- [ ] 1. Add the `ai doctor` CLI command
- [ ] 1.1 Add the `doctor` subparser under `ai` and `command_ai_doctor`
  - Resolve inputs the same way `ai setup generic` does; report a per-file exists/parse check; report a write-target check (OK naming the target, or FAIL with `resolve_write_target`'s own message); report a static profile-recommendation check
  - Observable: `lifetxt ai doctor` against a clean fixture workspace reports all-OK checks including the resolved write target; against a missing file it reports FAIL naming the file instead of raising
  - _Requirements: 1.1, 1.2, 1.3, 2.1, 2.2, 3.1, 3.2, 3.3_
  - _Boundary: command_ai_doctor_

- [ ] 2. Validation
- [ ] 2.1 Unit tests for health checks, ambiguity handling, and no-write guarantee
  - Cover a clean fixture, a missing input file, a parse-error fixture, an ambiguous multi-source workspace, `--format json` shape, and that the fixture directory's file set is unchanged after running the command
  - Observable: `python -m unittest tests.test_lifetxt` passes with the new cases
  - _Requirements: 1.1, 1.2, 1.3, 2.1, 2.2, 3.2, 3.3_
  - _Depends: 1.1_

- [ ] 2.2 (P) Document the command
  - Update `docs/en/ai-integration.md` / `docs/ja/ai-integration.md` and `docs/en/cli.md` / `docs/ja/cli.md`
  - Observable: `scripts/validate_release_docs.py` reports zero errors
  - _Boundary: Documentation_
