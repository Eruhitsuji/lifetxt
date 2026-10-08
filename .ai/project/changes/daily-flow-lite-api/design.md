# Read-only Web adapter

Implementation -> Developer Verification -> Independent Review, adaptive-default,
continuous Kanban / W-model, Feature / S / High. Codex implements and self-reviews;
Eruhitsuji independently reviews implementation/security/integration and merges.

The GET route delegates to daily_flow_web, then build_daily_flow unchanged. Reuse
CLI byte reader, parser/diagnostics and strict window validator, timezone policy,
workspace archive roles and core read_scope. No adapter scheduling or ranking.
Registered server paths are the admission boundary; never expand query-selected
paths or import other configured workspace files. Canonicalize/deduplicate aliases.
First active source directive/config resolves timezone. One UTC reference clock,
in-memory copied config and exact-byte source hashes per request. Read bounded
inputs and recheck source identities/content after calculation; retry once in full.
Second mismatch returns generic source_changed. IO failure returns generic
occupancy_unavailable with no partial inventory, counts, source refs or free slots.
Invalid query/config/scope returns generic 400 (required/length validation 422).
Core partial/blocked responses are 200 with explicit completeness. No write adoption.

Security/threat review: existing local api.token grants full registered-workspace
access, not principal-filtered Remote access. Restricted-resource credentials
remain denied by the existing outer legacy guard. Candidate scope is not an ACL;
all authorized active occupancy/dependency context reaches the core. No query path
admission, no source text/absolute paths in output. Hash provenance is opaque;
revisions indicate freshness only. No background work or persistent proposal.
No-cache success/400; pre-existing authentication behavior retained.

Self-review found both legacy runtime layers pre/post-reading writable-file
revisions and synthesizing write contracts even for nonexistent methods. Add exact
/api/daily-flow passthrough to surface_runtime and surface_runtime_compat only.
The outer auth/restricted guard and read-only guard remain active. This endpoint's
own bounded multi-file snapshot is authoritative; it deliberately has no unrelated
single-writable-file ETag. Startup metrics initialization remains unchanged.
Existing endpoints keep both legacy runtime wrappers unchanged.

Resource bounds: CLI 16 MB/file; aggregate 4 million decoded chars; shared hard
limits unchanged. No occupancy truncation. No new dependency/config key/schema
artifact. Native FastAPI OpenAPI generates query contract from route annotations;
canonical response version is shared core, not an independent Web schema.
Snapshot is not filesystem atomicity and cannot prevent edits after publication.
Rollback is a scoped revert without data migration.
