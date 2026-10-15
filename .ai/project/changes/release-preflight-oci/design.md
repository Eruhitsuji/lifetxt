# Design

Reuse Core context/source checks and Standalone native host validation. A read-only
reusable workflow builds once per native Linux arch with the unchanged Dockerfile.
Export OCI media types, suppress extra attestation manifests, label version/revision.
Keep original OCI tar as the one existing oci-layout role; no proof schema change.

Separate stdlib graph/archive checks from runtime orchestration. Never extractall;
bound entries/size/JSON and reject links, sparse files, aliases, external descriptors,
unreferenced blobs and invalid graph/identity. Digest every referenced blob.
Skopeo --preserve-digests imports into local containers-storage (not a registry).
Rootful Podman must report identical manifest AND config digest before native
version/help/check/uid/read-only Web smoke. Pin local execution to config ID with
pull=never. Loopback Web, networkless CLI, cleanup on failure, no rebuild fallback.

After payload upload, safely re-open tar and compare graph/all bytes with sealed
report before common component creation. Retain separate target/run/attempt proof
artifacts for 30 days. Parent must authenticate Actions API/job references (#1321).

Offline assemble requires both validated layouts, reuses all blobs and writes a
deterministic amd64/arm64 index, returning its exact digest. It cannot authenticate
proofs or authorize publication. Controller must bind final index bytes/digest into
evidence before approval (#1321); future transfer (#1311) uses --all and
--preserve-digests, verifies remote index digest, never rebuilds or converts.

References: OCI image-spec image-layout.md; Docker OCI exporter documentation;
Skopeo docs/skopeo-copy.1.md (--preserve-digests fails when preservation is impossible).
Review security/provenance/digest-kind/ABI distinction and read-only boundary.
Revert removes new producer; no existing release/tag/bytes change.
