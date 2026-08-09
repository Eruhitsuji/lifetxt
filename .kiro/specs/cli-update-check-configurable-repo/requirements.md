# Requirements Document

## Project Description (Input)
`lifetxt update-check` (added earlier in this batch) hardcoded the checked
repository as `Eruhitsuji/lifetxt`, with no way to point it elsewhere. This
is a real gap for anyone running a fork: their `update-check` would silently
compare their fork's running version against the upstream project's
releases, which is at best confusing and at worst tells a fork's users to
"update" when there is nothing for them to update to. Found via direct user
feedback immediately after `update-check` merged. Add a configurable
repository, with the hardcoded name kept only as the last-resort default.

## Requirements

### Requirement 1: The checked repository is configurable
**Objective:** As someone running a fork of lifetxt, I want `update-check`
to compare against my fork's own releases by default, so that I am not
misled by comparisons against an unrelated upstream repository.

#### Acceptance Criteria
1. THE SYSTEM SHALL support a configuration key (`update.repository`)
   naming the GitHub `owner/name` repository `update-check` compares
   against.
2. WHEN `update.repository` is set, THE SYSTEM SHALL use it instead of the
   built-in default.
3. WHEN `update.repository` is not set, THE SYSTEM SHALL fall back to the
   built-in default (`Eruhitsuji/lifetxt`).
4. THE SYSTEM SHALL register `update.repository` in the configuration
   metadata registry so `lifetxt config explain update.repository` and
   generated documentation describe it, per this project's configuration
   setting completion rule.

### Requirement 2: A one-off override is available without editing configuration
**Objective:** As a user checking a specific repository once (or before
deciding to persist a fork's identity in configuration), I want a CLI flag
that overrides the configured or default repository for a single run.

#### Acceptance Criteria
1. THE SYSTEM SHALL support a `--repo OWNER/NAME` flag on `update-check`.
2. WHEN `--repo` is given, THE SYSTEM SHALL use it regardless of any
   configured `update.repository` value.
3. THE SYSTEM SHALL validate that the resolved repository (from either
   source) looks like `OWNER/NAME`, and fail loudly with a clear error
   rather than sending a malformed API request when it does not.

### Requirement 3: No change to existing default behavior
**Objective:** As an existing user of `update-check` with no configuration
or flag set, I want identical behavior to before this change.

#### Acceptance Criteria
1. WHEN neither `--repo` nor `update.repository` is set, THE SYSTEM SHALL
   behave exactly as it did before this change (checking
   `Eruhitsuji/lifetxt`).
