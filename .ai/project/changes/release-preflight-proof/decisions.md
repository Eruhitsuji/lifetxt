# Decisions

- 2026-10-15: Eruhitsuji approved #1309 architecture, then explicit correction
  number and failure behavior in chat; no release/tag/configuration approval.
- #1315 implements only the offline proof contract. Producer builds, GitHub
  authenticity, OCI content validation, retention/approval and public manifests
  remain in #1316–#1321/#1311/#1305.
- Canonical JSON digests are deterministic but not signatures. Component
  artifact archive digest is declared by the producer and must later be checked
  against trusted Actions metadata, not equated with individual file hashes.
- Schema 1 is fixed to all 13 targets; arbitrary subsets cannot pass aggregation.
