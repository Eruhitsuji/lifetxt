# Requirements Document

> **Authoritative copy lives in the change package, not here.**
>
> For non-trivial work, and for anything at High or Regulated assurance, this content is distilled
> into `.ai/project/changes/<change-id>/requirements.yml`, which is what reviewers and the other
> executors read. See `.ai/project/changes/README.md` for when a change package is required.

## Project Description (Input)

Data integrity suite for lifetxt.

Who has the problem: lifetxt users and operators who keep authoritative personal or project records in one or more `life.txt` files and need to know whether records, references, generated files, attachments, transactions, and workspaces remain internally consistent.

Current situation: integrity-related checks exist across `check`, `ids`, `workspace validate`, `ticket validate`, `ticket validate-history`, file attachment verification, transaction recovery utilities, and server-update integrity checks. Users must know which command to run, and there is no single read-only integrity report or staged repair plan covering the most important cross-file consistency classes.

What should change: add a cc-sdd planned suite of small implementation slices that first introduces a read-only `lifetxt integrity` report, then adds repair planning, cross-file registry auditing, import/sync reconciliation, recovery-focused integrity diagnosis, and selectable strictness profiles without weakening the permissive life.txt parser.

## Boundary Context

- **In scope**: read-only integrity reporting, machine-readable diagnostics, explicit repair plans, cross-file ID/reference audits, generated-source reconciliation, transaction/recovery integrity checks, strict validation profiles, and documentation for these workflows.
- **Out of scope**: silent automatic repair, background bidirectional sync, direct deletion or migration of user data, changing the base parser to reject unknown custom keys, replacing existing commands, or merging external systems wholesale into life.txt.
- **Adjacent expectations**: reuses existing parser, validator, ID/link diagnostics, workspace diagnostics, file reference verification, sync/import metadata, transaction journal and manifest checks, revision preconditions, and proposal-first mutation patterns.

## Requirements

### Requirement 1: Integrated read-only integrity report

**Objective:** As a lifetxt user, I want one integrity command to aggregate existing consistency checks, so that I can understand the health of my data without knowing every specialized command.

#### Acceptance Criteria

1. When the user runs `lifetxt integrity` for one or more input files, the CLI shall report syntax, duplicate ID, missing ID, dangling reference, dependency, file reference, workspace, and ticket-history diagnostics that apply to the supplied context.
2. When the user runs `lifetxt integrity --json`, the CLI shall emit a machine-readable report with stable diagnostic code, severity, source file, line where available, item ID where available, message, hint, and check category.
3. If a participating specialized check cannot run because required context is missing, then the CLI shall report that check as skipped or blocked with an actionable reason rather than silently omitting it.
4. The `lifetxt integrity` command shall not write, modify, delete, archive, or migrate any file.

### Requirement 2: Repair plan generation

**Objective:** As a lifetxt user, I want proposed repairs separated from writes, so that I can review consistency fixes before changing authoritative data.

#### Acceptance Criteria

1. When the user runs `lifetxt integrity plan`, the CLI shall output a deterministic repair plan for supported mechanical fixes without changing any source file.
2. If a diagnostic has no safe mechanical repair, then the plan shall mark it as manual and preserve the diagnostic evidence that explains why.
3. Where a plan includes a candidate write, the plan shall record the expected source revision for every file that would be changed.
4. The repair plan shall be serializable as JSON and suitable for later review, proposal staging, or revision-checked application by a separate task.

### Requirement 3: Cross-file ID and reference registry

**Objective:** As a user with multiple workspace sources, I want ID and reference checks across all loaded files, so that cross-file relationships fail loudly when they become ambiguous or broken.

#### Acceptance Criteria

1. When multiple files are supplied through explicit paths, globs, directories, or a named workspace, the integrity suite shall detect duplicate IDs across the complete loaded source set.
2. When link fields reference an ID that is missing, duplicated, or self-referential in an invalid way, the integrity suite shall report a diagnostic naming the source reference and the candidate target state.
3. While a named workspace has a configured write target, the integrity suite shall distinguish read-only source diagnostics from write-target diagnostics.
4. Where archive or generated files are intentionally included, the integrity suite shall identify their source role in the report rather than treating all files as equivalent writable sources.

### Requirement 4: Import and sync reconciliation audit

**Objective:** As a user importing calendar, task, or issue data, I want source and UID reconciliation checks, so that re-imports and generated files do not create silent duplicate or conflicting records.

#### Acceptance Criteria

1. When records contain `source:` and `uid:` details, the integrity suite shall detect duplicate source-UID pairs across the selected files.
2. If a generated-source record appears to conflict with a manually maintained record, then the integrity suite shall report the conflict without choosing a winner.
3. Where an import or sync mode supports merge-existing or soft-delete semantics, the integrity suite shall identify stale, deleted, or locally modified generated records when the evidence is available.
4. The integrity suite shall not contact external services while performing this audit.

### Requirement 5: Recovery and transaction integrity diagnosis

**Objective:** As an operator, I want recovery evidence and transaction manifests checked from one place, so that interrupted or divergent writes are visible before further mutation.

#### Acceptance Criteria

1. When transaction journal or backup evidence is configured or discovered, the integrity suite shall report whether manifests verify and whether current files match recorded before or after revisions.
2. If recovery evidence is incomplete, corrupt, unsupported, or newer than the current reader can safely interpret, then the integrity suite shall report a blocked diagnostic with a non-destructive next step.
3. When recovery status is healthy, the integrity suite shall report that no recovery action is required without modifying evidence files.
4. The integrity suite shall not perform resume, compensate, abandon, restore, archive rotation, or cleanup actions.

### Requirement 6: Strict validation profiles

**Objective:** As a user or operator, I want optional stricter integrity profiles, so that automation and release checks can require stronger invariants while normal life.txt editing remains permissive.

#### Acceptance Criteria

1. When the user selects the default profile, the integrity suite shall preserve the existing permissive behavior for unknown custom keys.
2. When the user selects a strict profile, the integrity suite shall escalate configured integrity classes such as missing IDs, unresolved references, missing source UID, missing file hashes, or ticket-history gaps according to the profile.
3. If a profile changes severity for a diagnostic, then the JSON report shall identify both the original diagnostic severity and the effective profile severity.
4. The strict profile shall be opt-in and shall not change how existing `check` parses ordinary life.txt files unless a separate issue explicitly changes that command.

### Requirement 7: Implementation governance and rollout

**Objective:** As a maintainer, I want this broad suite decomposed into Ready issues, so that each part can be reviewed, tested, and reverted independently.

#### Acceptance Criteria

1. When implementation starts, each code-changing slice shall have a GitHub Issue with acceptance criteria, write scope, assurance level, review viewpoints, test viewpoints, and traceability target.
2. If a slice changes public CLI behavior, schemas, or data mutation behavior, then the slice shall update English and Japanese documentation and traceability records in the same PR.
3. Where a slice crosses multiple domains or introduces data-changing behavior, the slice shall use an appropriate change package rather than relying only on this cc-sdd working spec.
