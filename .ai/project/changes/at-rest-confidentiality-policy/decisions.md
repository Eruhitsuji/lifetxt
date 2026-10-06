# Decisions

- Recommend platform encryption plus permissions/isolation across all resolved mounts; protect backup copies separately.
- Defer application crypto pending a separate approved authenticated-encryption/storage/recovery design; no cipher or new dependency selected here.
- Reuse cap-durable-transaction-recovery and cap-lifetxt-backup-v1. Explicit-file backup coverage and confidentiality are separate operator checks.
- Keep keys outside plaintext configuration, data and evidence; retain recoverable historical generations and test before retirement.
- Preserve current plaintext revision and byte-format contracts. Secret capability/signed URLs require prevention/redaction, not reliance on disk encryption.
- Policy acceptance is the maintainer's merge decision. No production storage changes, encryption configuration or destructive operation performed.
