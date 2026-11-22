# Release preparation design

Use the existing versioning contract: release_parts("1.0.5.0") gives (1, 0, 5, 0); canonical_release and semver_metadata give 1.0.5. No separate alias tag. Update the authoritative Python version and Mini crate version and lock, plus the existing explicit import test. Desktop continues to use its existing packaging setter and Editor retains independent SemVer.

The preparation PR has no format migration, new dependency, registry write or deployment. Confirm current source and full main compatibility CI after merge. The existing 14-target read-only preflight produces the exact distribution bytes. The operator runs release.yml with the verified artifact ID and bundle digest and the human Release Authority approves its specific plan and run. Preserve all previously published bytes and tags.

Shared metadata and traceability are owned by the Integrator (Eruhitsuji); no competing PR was returned at planning. Stop for conflicts. Revert this version PR before publication if necessary. After publication use immutable retry or a human-selected correction version under the runbook. Do not mark external registrations or GUI acceptance verified by CI alone.
