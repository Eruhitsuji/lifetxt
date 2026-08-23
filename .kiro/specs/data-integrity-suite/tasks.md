# Implementation Plan

> **This file is working material, not the task source of truth.**
>
> In this repository, actionable work lives in GitHub Issues.
> `.ai/managed/core/TASK_MANAGEMENT.md` makes Issues the source of truth, and
> `.ai/managed/core/INDEX.md` lists "no implementation without a reviewable task source"
> in the non-overridable baseline. Use this breakdown to file Ready issues before implementation.

Issue #517 was created for the first read-only implementation slice. Remaining
issue candidates still need to be filed before implementation starts.

Recommended change type: Feature for read-only reporting slices; Feature or Migration only if later repair application mutates data. Recommended assurance: Standard for read-only slices, High for any data-changing repair application.

## Issue Candidates

- [x] 1. Implement the read-only `lifetxt integrity` report
  - Add a non-mutating CLI report that aggregates parser, validator, ID/reference, file reference, workspace, and ticket-history diagnostics available from existing modules.
  - Support text and JSON output with normalized diagnostic fields.
  - Observable: a fixture with syntax, duplicate-ID, dangling-reference, and workspace diagnostics produces one combined JSON report and no file content changes.
  - Tracked by: https://github.com/Eruhitsuji/lifetxt/issues/517
  - _Requirements: 1.1, 1.2, 1.3, 1.4_
  - _Boundary: IntegrityCLI, IntegrityRunner, CheckAdapters, ReportRenderer_

- [ ] 2. Add strict integrity profiles
  - Add opt-in profile mapping for default and strict severity behavior without changing `lifetxt check`.
  - Preserve base severity and effective severity in JSON output.
  - Observable: the same missing-ID fixture remains warning-level by default and escalates under strict profile while ordinary `lifetxt check` output remains unchanged.
  - _Requirements: 6.1, 6.2, 6.3, 6.4_
  - _Boundary: ProfileMapper, ReportRenderer_
  - _Depends: 1_

- [ ] 3. Add cross-file ID and reference registry auditing
  - Detect duplicate IDs and broken, ambiguous, or invalid references across explicit paths, globs, directories, and named workspaces.
  - Distinguish writable, read-only, archive, and generated source roles where that role is known.
  - Observable: a multi-file workspace fixture reports cross-file duplicate IDs and dangling references with source file and target-state evidence.
  - _Requirements: 3.1, 3.2, 3.3, 3.4_
  - _Boundary: CheckAdapters_
  - _Depends: 1_

- [ ] 4. Add local import and sync reconciliation audit
  - Detect duplicate `source:` plus `uid:` pairs and local manual/generated conflicts without contacting external services.
  - Report stale, deleted, or locally modified generated records only when local evidence is available.
  - Observable: generated ICS and manual fixtures produce duplicate and conflict diagnostics while tests assert no network access.
  - _Requirements: 4.1, 4.2, 4.3, 4.4_
  - _Boundary: CheckAdapters_
  - _Depends: 1_

- [ ] 5. Add recovery and transaction integrity diagnosis
  - Surface manifest verification, before/after revision matching, corrupt evidence, unsupported evidence, and healthy no-action states through the integrity report.
  - Keep every recovery action out of scope.
  - Observable: recovery fixtures report healthy, divergent, corrupt, and unsupported states without modifying journal, backup, or evidence files.
  - _Requirements: 5.1, 5.2, 5.3, 5.4_
  - _Boundary: CheckAdapters_
  - _Depends: 1_

- [ ] 6. Add non-mutating repair plan generation
  - Produce deterministic JSON plans for supported mechanical repairs and manual classifications for unsafe repairs.
  - Include expected source revisions for every candidate target.
  - Observable: `lifetxt integrity plan` emits stable JSON from diagnostics and changes no source file.
  - _Requirements: 2.1, 2.2, 2.3, 2.4_
  - _Boundary: PlanBuilder_
  - _Depends: 1, 2, 3, 4, 5_

- [ ] 7. Document, trace, and verify each implementation slice
  - For each code-changing issue, update English and Japanese docs, capability records, traceability records, and targeted tests in the same PR.
  - For any future data-changing repair application, create a separate change package with approval, rollback, and retained verification evidence.
  - Observable: every PR linked to this suite contains a meaningful traceability entry and uses project commands from `.ai/project/COMMANDS.yml`.
  - _Requirements: 7.1, 7.2, 7.3_
  - _Boundary: Implementation governance_

## Suggested GitHub Issues

Use these as issue titles after `gh` authentication is restored:

1. `Add read-only lifetxt integrity report`
2. `Add strict integrity profile severity mapping`
3. `Audit cross-file IDs and references in integrity report`
4. `Audit local import and sync source UID reconciliation`
5. `Report recovery and transaction integrity through integrity`
6. `Generate non-mutating integrity repair plans`

Each issue should include lifecycle phase `Implementation`, assurance `Standard` unless it mutates data, write scope from the relevant task boundary above, and test viewpoints covering CLI output, JSON contracts, no-write guarantees, and regression coverage for existing commands.
