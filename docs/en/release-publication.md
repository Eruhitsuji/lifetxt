# Approved release publication

The sole public entry is `.github/workflows/release.yml` on manual `main`
dispatch. Tag pushes and `release:published` do not publish anything. The seven
retired primary/downstream workflow entries reject calls. Native build producers
remain the read-only `release-preflight-*.yml` workflows.

## Operator procedure

1. Merge the version PR and wait for its successful push/main compatibility gate.
   Select the exact 40-hex source SHA and human-selected version. Normal releases
   use `X.Y.Z`; corrections may use `X.Y.Z.N`. `N=0` is the same version as
   omitting N. The pipeline never chooses or increments N.
2. Run `release-preflight.yml` as described in [preflight](release-preflight.md).
   Retain its run/attempt, the `preflight-verified-<run>-<attempt>` artifact ID,
   and the `digest` field of `preflight-bundle.json`. Do not confuse the ZIP's
   SHA256 with that JSON bundle digest. All original payload/proof artifacts must
   remain available; expiration/deletion invalidates publication.
3. Dispatch **Release** (`release.yml`, branch `main`) with
   `preflight_artifact_id` and `bundle_digest`. Its read-only prepare job
   downloads the actual final ZIP and all 13 original target payloads, checks
   API provenance, source CI, reports, archive hashes, expiry and OCI graph.
   It generates a reviewable release plan and public inventory. Preparation
   also preserves the strict source release-policy/schema/golden/translation/
   write-route checks and CLI safety release-gate with jsonschema required.
   Preflight supplies the former profile's build/twine/clean-install checks;
   preparation makes no tag, registry or Release writes.
4. Read the prepare job summary. In the pending **pypi** environment deployment,
   Release Authority `Eruhitsuji` approves once with the exact displayed comment:

   ```text
   release <plan-digest> run <release-run-id>/<attempt>
   ```

   This comment is required, not an optional note. The script verifies the
   actual API approval history, reviewer type/login, environment, plan digest,
   release run and attempt before any public write. An absent reviewer rule or
   approval history fails closed. Approval on another plan/run cannot be reused.
5. The approved job re-downloads and revalidates preflight after the wait, compares
   the plan, checks the approval and fixes the tag to the approved source.
   It publishes only missing exact primary bytes: GHCR's version/v-version tags,
   GitHub assets, and wheel/sdist through the existing direct PyPI Trusted
   Publisher job. No release rebuild is performed. Existing bytes are downloaded
   and checked before they can be skipped; different bytes cause a stop.
6. After every primary is confirmed, a single finalizer uploads `SHA256SUMS`.
   A fresh read-only verify job independently downloads all GitHub assets and both PyPI distributions,
   checks the full GHCR graph and both platforms, and runs downloaded Linux
   Standalone/Mini CLI and conformance checks. Desktop metadata/mappings and
   private bundled Core smoke remain bound to the authenticated preflight.
7. A fresh finish job generates winget/Scoop manifests and the conda recipe from those verified
   inputs; update Homebrew using its existing credential, compare-and-swap and
   a remote content readback. Finally promote GHCR latest/major/minor aliases
   and GitHub Latest. All required machine checks, generators and Homebrew must
   succeed first. Numeric four-part ordering prevents older retries from
   downgrading Latest or an existing newer registry alias.

The workflow is globally serialized without cancellation. GitHub may supersede a
pending concurrency run; each surviving run still requires its own approval.
No PAT is introduced for tag/event chaining; all stages are explicit ordered
jobs/steps, so GITHUB_TOKEN event anti-recursion does not affect downstream execution.
Only publish-pypi uses the protected environment/OIDC; verify has read-only
permissions and no publish/Homebrew credentials, and finish executes controller
generators rather than product binaries. The one run-specific human approval
authorizes these explicit dependent stages; later jobs do not request it again.

## Required external settings

Keep PyPI Trusted Publisher owner `Eruhitsuji`, repository `lifetxt`, workflow
`release.yml`, environment `pypi`. Configure the GitHub `pypi` environment's
required reviewer as `Eruhitsuji` and its deployment branch policy to `main`.
Use prevent-self-review only when a different human initiates the run; a sole
maintainer cannot approve their own dispatched run with that option enabled.
No script enables bypass or approves a deployment. This implementation does not
claim these account settings were inspected or configured.

Reuse `HOMEBREW_TAP_TOKEN` with Contents read/write on only
`Eruhitsuji/homebrew-tap`. A missing/invalid token blocks Homebrew and Latest;
primary artifacts may already be published and must be preserved. No winget,
Scoop or conda submission credential is needed for generation.

The optional repository variable `RELEASE_CRITICAL_BLOCKER`, when nonempty,
stops the publication stages and promotion for a known critical finding. A
finding discovered while a stage is running still requires human incident
handling; do not interpret an earlier green check as accepting that finding.

## Canonical inventory and receipts

`release-inventory.json` records source/version/candidate digest, exact asset
names, hashes, byte sizes, roles and target attribution. Public scope: Core
wheel/sdist/SBOM/provenance, five Standalone executables, all Desktop installers,
and Mini executables/checksum/build-info/release notes. Identical shared Mini
notes are deduplicated; all other duplicate or case-conflicting names fail.
Private Desktop bundled Core and OCI archives are excluded. The one LF-only
`SHA256SUMS` covers the complete payload inventory plus `release-inventory.json`
and excludes itself. Historical per-workflow manifests are no longer published.

`release-primary-receipts-<run>-<attempt>` and
`release-verification-receipts-<run>-<attempt>` retain earlier publication and
read-only verification evidence, including failures. The final
`release-receipts-<run>-<attempt>` retains the plan, machine receipt, failure
receipt when present, and generated manual-submission files for 90 days.
Channel states distinguish `verified`, `generated`, `blocked` and
`manual_required`; overall states progress through `primary_published`, `primary_verified`,
`verified` (including downstream), and `accepted` only after alias/Latest
readback. A failure receipt's blocked stage overrides an earlier receipt;
a partially promoted alias is not accepted. Generated external manifests do
not mean submitted, reviewed, registered or install-tested. The exhaustive
Desktop GUI install/upgrade/uninstall matrix is explicitly `not_verified`.
Those external/manual checks are nonblocking; concrete critical defects block.

## Failure and recovery

| Classification | Action |
| --- | --- |
| `preflight_failure` | Publish nothing. Fix by PR and redo preflight at the new SHA; the same unpublished number may be reused. |
| `publish_retryable` | Re-read every remote object, keep source/tag/bytes/digests fixed, retry only missing operations. |
| `published_source_defect` | Preserve old tag/bytes. Human selects a new version, merges its PR, then repeats CI/preflight/approval. |
| `external_manual_required` | Submit generated winget/Scoop/conda files through the external owner's normal process; do not claim external publication. |
| `critical_blocker` | Stop publication/Latest. Ask Release Authority for incident/withdrawal decisions; do not silently replace artifacts. |

For a publish retry, dispatch a **new release run** with the same original
preflight artifact ID and bundle digest, and approve its new plan. Existing
matching tag/Release/assets/PyPI/GHCR bytes and matching Homebrew content are
safe no-ops. Only missing work is written. Use a new dispatch rather than
GitHub's Re-run failed jobs: its old prepared plan binds an earlier attempt and
will be rejected. If preflight inputs expired, stop and inspect retained
remote evidence; rebuilding a published number is not an authorized recovery.

Conflicting source/tag, alternate `vX.Y.Z.0` tag, unknown assets, duplicate
names, CRLF, checksum/version mismatch, permission/API failure and newer Latest
all stop the flow. There is no tag move, asset clobber, automatic N increment,
or registry version-tag overwrite. A failed alias promotion can be repaired
only from the same verified digest after all checks; GitHub Latest is last.

Historical example: v1.0.4 partially published before source defects were
fixed. Its tag/bytes stayed intact; v1.0.4.1 was a separately selected correction.
The later downstream ordering failure could be retried with identical bytes.
The missing Desktop checksum problem is now blocked by the full inventory
finalizer. These historical versions are examples, never retry targets for
this new pipeline: existing Releases lack its immutable inventory binding.

## Validation boundary

Offline tests exercise all 13 real producer validators with synthetic payloads,
partial remote services, approval/expiry/identity faults, immutable uploads,
checksum failures and downstream ordering. They do not certify a live public
release. A separately approved first real release must still validate the
PyPI OIDC exchange, GHCR transport, protected environment and Homebrew token.
The successfully retained preflight run 38822634032 certifies build/preflight
transport only and has no publication authority.
