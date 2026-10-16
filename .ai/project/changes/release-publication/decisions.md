# Decisions

- Follow human-approved #1309 state and correction flow; user requested the
  remaining related implementation together. Keep child write ownership explicit
  and central workflow/shared metadata sequential under Eruhitsuji as Integrator.
- Preserve release.yml/pypi direct Trusted Publisher identity. Use one pypi
  environment approval plus API history with exact run plan comment, rather than
  assuming environment configuration was inspected or accepting a boolean input.
- Retire old entries atomically instead of retaining manual bypass switches.
  Ordered central stages replace the old three downstream event workflows.
- Reject published bytes conflicts and unknown inventories; do not adopt historical
  Releases through this new pipeline or silently add metadata to them.
- Keep canonical/public inventory separate from private preflight evidence. Do not
  use last-writer-wins merge_sha256sums for immutable finalization.
- Use new dispatch for bounded retry with a new plan approval and the same original
  preflight. No automatic retry loops or release-number increments. Expired input
  needs retained-evidence/human recovery, not permission to rebuild old versions.
- Existing Homebrew token is reused; no new PAT for event chaining. Homebrew is a
  required public channel; winget/Scoop/conda external registration is manual.
- Keep product binary execution in a fresh read-only verify job. Publisher alone
  has OIDC/environment; controller-only finish has no OIDC and consumes a
  same-plan primary_verified receipt. Repeat byte/expiry authentication per job
  rather than inheriting a publisher workspace or credentials into native smoke.
- Legacy shell-publication tests are replaced by rejection/canonical regressions;
  native Mini/version/conformance tests remain in preflight. Do not test dead
  publishing code as if it were still a supported path.
- Actual successful preflight is recorded in the prior integration/fix packages.
  Independent review results are not invented from human merge messages.
- Cutover also reads legacy GHCR alias indexes emitted by docker/metadata-action
  raw v-prefixed tags and BuildKit attestations. Read/hash both runnable platform
  manifests/configs and normalize only the leading tag v before the existing
  numeric parser. Ignore only explicit unknown/unknown attestation descriptors
  referencing those exact runnable manifests; reject unknown/unbound descriptors
  and mixed platform versions. This fixture is derived from the old workflow and
  upstream contracts, not a claim that the live legacy registry graph was read.
  Sources: https://github.com/docker/metadata-action and
  https://docs.docker.com/build/metadata/attestations/attestation-storage/
