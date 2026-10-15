# Design

The stdlib-only offline helper defines a fixed versioned contract for candidate,
component and aggregate proof. Canonical JSON hashing binds all evidence fields.
Version normalization reuses lifetxt.versioning. Every component verifies actual
payload bytes under a target-specific directory; aggregation demands all 13
targets and refuses duplicate target/artifact identities. Reports and payloads
are separate to avoid archive/proof self-reference. No publication code exists.

Smoke outcomes, source identity and archive metadata are producer assertions.
The future trusted controller must independently reconcile those assertions with
GitHub API/job metadata. Hashes provide integrity rather than authenticity.
This task must not represent a full workflow, OCI validation, semantic binary
validation or environment approval as implemented. Detailed producer and consumer
contracts and CLI examples are in docs/en/release-preflight.md and its Japanese
counterpart. Exact roles/check names are schema 1 policy, not arbitrary user input.

Security review: reject noncanonical paths, symlinks, missing/unlisted files,
case aliases, unknown/duplicate JSON fields and partial/failed checks. Inputs
and outputs are local only; no token, network, shell or untrusted subprocess is
used by the helper. Callers provide private quiescent directories. Rollback is a
PR revert; current publication workflows and past public assets are unchanged.
