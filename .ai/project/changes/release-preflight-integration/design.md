# Design

Reuse all five producer workflows and their offline finish validators, common
candidate/aggregate contract and OCI layout assembler. Separate gh API/ZIP trust
boundary from controller orchestration. New entry is manual main only; public
release.yml cutover/reuse is owned by #1311 and remains unchanged.

Pin a 40-hex main-ancestor source SHA, explicit canonical version, own controller
SHA and actual run/attempt. Link an existing successful CI push/main run and Main
compatibility gate, without duplicating the full unit compatibility suite. Require
trusted controller context and repeat checks after collection. Source version
consistency is checked by every existing producer before success proof.

Core precedes Standalone, which precedes Desktop. Mini and OCI depend on Core.
Collector always runs to reject failed/skipped dependencies; uploads only on success.
Producers keep contents:read; collector/prepare add actions:read only. No secrets
inheritance, environment, PAT, publish/tag permissions or approval receipt.

Use gh API all-page listing and attempt-specific jobs/run endpoints. Bind all five
reusable workflow SHAs, 13 successful jobs and required build/component/upload
steps. Require unique expected target/run/attempt payload+proof names/IDs, matching
run/repository/controller SHA and creation within the successful producer window.
API exposes no uploader-job ID: fixed trusted workflow plus job/name/time is the
attribution boundary, not cryptographic attestation. Rehash downloaded ZIPs against
API digest/size before safe flat-file extraction; reject links/aliases/traversal,
CRC errors, encryption, empty files and expanded-size overflow. Do not execute
cross-platform binaries on the collector. Native smoke belongs to producer jobs.

Rebuild each common component from downloaded bytes/report/API artifact descriptor
using the existing producer finish; compare exact proof. Preserve Desktop stage
and public-name mapping, allowing only additive bundle toolchain fields. Aggregate
all 13 components and assemble both OCI layouts with unchanged blobs. Seal final
index digest and all report/index/blob file hashes, main-CI receipt and original
artifact references/expiry in one bundle. Re-read API/CI state and fail on drift.
Stage on the output filesystem and atomically rename only the complete success
bundle; no partial final success output or upload on failure.

The final artifact references original target payloads, so expiration of any input
invalidates future reuse. Consumer authenticates final artifact's own archive ID/
digest separately; no self-reference. New attempts require all 13 new proofs: only
Re-run all jobs is a build retry. Public-byte retry/authority remain #1311.

Review viewpoints: provenance, trust/byte boundaries, pagination, stale attempts,
archive handling, concurrency/expiry, distinct OCI digest kinds, least privilege.
Shared docs/traceability integrator Eruhitsuji; sequential after #1327, no concurrent
producer edits. Revert removes only new entry/helpers; public versions unaffected.

GitHub REST official workflow-runs, workflow-jobs and artifacts docs plus gh api
manual define these read-only interfaces. Local fixtures cannot establish real
native or transport success. Keep #1321/#1310 open until actual main dispatch.
