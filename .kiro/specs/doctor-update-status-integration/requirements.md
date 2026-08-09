# Requirements Document

## Project Description (Input)
`lifetxt doctor` (system diagnostics) and `lifetxt update-check` (read-only
GitHub release/tag comparison) both landed in the same recent batch but
never talk to each other -- an operator running `doctor` for a full health
picture has no way to see whether a newer lifetxt version exists without
running a second, separate command. Add an opt-in `--check-update` flag to
`doctor` that reuses `update-check`'s own resolution logic and adds an
`update` row to the report, without making plain `doctor` (no flag) require
network access.

## Requirements

### Requirement 1: doctor can optionally report update status
**Objective:** As a user running `lifetxt doctor` for a full health check, I
want to optionally see whether a newer lifetxt version exists, so that I
don't have to run a second command for that information.

#### Acceptance Criteria
1. WHEN `--check-update` is not given, THE SYSTEM SHALL make no network
   request and SHALL NOT include an `update` row in the report.
2. WHEN `--check-update` is given and a newer release/tag exists, THE
   SYSTEM SHALL add an `update` row with `WARN` severity naming the
   available version and the command to run.
3. WHEN `--check-update` is given and the running version is already the
   latest (or ahead of it), THE SYSTEM SHALL add an `update` row with `OK`
   severity.
4. WHEN `--check-update` is given and the target repository has no
   published releases or tags, THE SYSTEM SHALL add an `update` row with
   `OK` severity stating that clearly, not an error.
5. THE SYSTEM SHALL support `--repo OWNER/NAME` to override which
   repository `--check-update` queries, using the same resolution
   (`--repo`, then `update.repository` config, then the built-in default)
   as `update-check`.
6. THE SYSTEM SHALL support `--update-timeout SECONDS` (default `5`) to
   bound the network request `--check-update` makes.

### Requirement 2: A failed update check never fails doctor
**Objective:** As a user running `doctor --check-update` without network
access, I want the rest of the health report to remain accurate and doctor
to exit successfully, so that a temporary network issue never masquerades
as a local install problem.

#### Acceptance Criteria
1. WHEN the update check fails for any reason (network error, API error,
   an unparseable response), THE SYSTEM SHALL add an `update` row with
   `WARN` severity describing the failure, and SHALL continue evaluating
   every other check normally.
2. THE SYSTEM SHALL NOT let an update-check failure or an available update
   change `doctor`'s exit code -- only `FAIL`-severity checks do that,
   unchanged from existing behavior.
