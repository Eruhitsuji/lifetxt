# Design

Repair the native checker path relative to the existing Mini working-directory.
Generate each checksum in the artifact directory so only the distributed basename
is recorded. Checkout the tag in the publish job to reuse the existing
scripts/merge_sha256sums.py from the same source as the binaries. Verify Mini
checksums before making release calls. Inspect the declared release asset
inventory; a present manifest must download successfully. Merge it with the
fresh Mini checksums and upload only dist/lifetxt-mini assets.

The shared merger gives later inputs precedence, as in existing Core and
standalone workflows. This is not an atomic remote transaction. Other publishers
can update SHA256SUMS between the read and upload; #911 requires all primary
uploads to finish and the final asset inventory/checksums to be reconciled before
acceptance. Cross-channel serialization changes remain outside this task.

Review/security: bounded synthetic fixtures, fake gh only, no credential reads or
production calls. Test viewpoints: exact shell/cwd, two architectures, no prior
manifest, Core/standalone preservation, corrupt binary, download failure, malformed
manifest/inventory, tagged-source helper checkout, unchanged tag-push authorization.
Coding viewpoints: reuse existing merger, keep only Mini workflow changed; new
fixture extraction uses stdlib and no optional YAML dependency in the CI lane.
Compatibility: asset names, Mini subset/version, official targets, tag-push-only
publish authorization and runtime behavior remain unchanged.
