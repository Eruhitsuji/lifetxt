# Requirements Document

## Project Description (Input)
lifetxt has no command that tells the user whether a newer version exists.
The project has no PyPI distribution, so "the latest version" can only mean
the latest published GitHub Release for `Eruhitsuji/lifetxt`, falling back
to the latest tag when no Release has been published (confirmed: this
repository currently has neither). Add `lifetxt update-check`, a read-only
command that compares the running version against that latest published
version and reports the result, without installing or modifying anything.
This is scoped separately from, and is a prerequisite building block for, a
separate `lifetxt update` self-update command (tracked as its own,
higher-assurance change).

## Requirements

### Requirement 1: Compare the running version against the latest published GitHub version
**Objective:** As a lifetxt user, I want to check whether a newer release
exists, so that I know when to consider updating without leaving the CLI.

#### Acceptance Criteria
1. WHEN the user runs `lifetxt update-check`, THE SYSTEM SHALL query the
   GitHub API for the latest published Release of `Eruhitsuji/lifetxt`.
2. IF no Release has been published, THE SYSTEM SHALL fall back to querying
   the most recently created tag.
3. IF neither a Release nor a tag exists, THE SYSTEM SHALL report that
   nothing was found to compare against, and exit with status 0 (this is
   not an error).
4. WHEN a latest version is found, THE SYSTEM SHALL report one of: the
   running version is older (`update_available`), newer
   (`ahead_of_latest`), or equal (`up_to_date`) to the latest found
   version.
5. IF the found release/tag name cannot be parsed as a version, THE SYSTEM
   SHALL report that explicitly rather than guessing a comparison result.
6. THE SYSTEM SHALL support `--format text` (default, human-readable) and
   `--format json` (machine-readable, including `current_version`,
   `repository`, `latest_version`, `kind`, `url`, and `status`).

### Requirement 2: The check is strictly read-only and network-bounded
**Objective:** As a lifetxt user, I want `update-check` to never modify my
system and never hang indefinitely, so that it is always safe to run.

#### Acceptance Criteria
1. THE SYSTEM SHALL NOT write, install, or modify any file as part of
   `update-check`.
2. THE SYSTEM SHALL make at most two GitHub API requests (release lookup,
   then tag lookup only if no release was published).
3. THE SYSTEM SHALL support a `--timeout SECONDS` option bounding each
   network request, defaulting to 10 seconds.
4. IF the network request fails (DNS/connection failure, or an HTTP error
   other than "no release published"), THE SYSTEM SHALL fail loudly with a
   clear error and non-zero exit status, rather than silently reporting
   "up to date".
