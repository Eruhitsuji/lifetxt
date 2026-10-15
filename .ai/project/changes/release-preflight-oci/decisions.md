# Decisions

- Approved #1309 design; #1322 through #1326 merged before implementation.
- Issue #1320 refined to two focused helpers, new reusable workflow and offline
  regression suite. Existing public Dockerfile/workflow and proof contract untouched.
- Retain original OCI tar as one role, rather than weakening common role uniqueness.
- Use OCI-to-local-storage digest-preserving transfer and native Podman inspect;
  no registry transport or rebuild/conversion fallback, no QEMU success claim.
- Distinguish image manifest, config, per-arch index and final multiarch index digest.
- Real containers/native builds and Actions transport unavailable locally; explicitly
  not_run, tracked by #1321 before publication enablement. Fixtures are not runtime evidence.
- Independent implementation/integration reviews and human merge approval pending.
