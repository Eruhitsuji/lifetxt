# At-rest confidentiality policy

Security/High, S (complexity 6: scope 1, dependencies 1, uncertainty 1, verification 1, operations 2). This is a source-backed design decision, not a cipher rollout. Reuse durable transaction recovery and backup-v1 capabilities; add one documentation capability. The linked bilingual policy is normative after maintainer acceptance.

Platform disk/filesystem/dataset encryption, restrictive ACLs and a dedicated service identity form the supported baseline. Off-host backups require an independent boundary and optional established client-side tooling where the provider is untrusted. Application encryption is deferred: final-file-only encryption misses transaction before/after bytes and backups. Server-held decryption keys cannot provide E2EE against that server.

Inventory follows attachment_transactions, atomic, transaction_journal, backup/backup_cli/backup_remote and server_update, including raw artifacts vs redacted evidence and explicit selected-file backup coverage. Future provider staging enters the boundary; exclusive provider bytes do not. Hashes, metadata, swap/core and external operator copies are residual exposure.

Key custody belongs to the operator, with protected separate escrow, generation retention, oldest-backup recovery drills and tool-supported rekeying. No mandatory KMS, application keys or secret settings are introduced. Platform transparency preserves plaintext revisions, MIME checks, journal integrity and external tools. No schema/default/version/provenance, data, migration or downgrade change. Revert documentation to roll back this PR; deployed platform/backup encryption requires its own reviewed migration and recovery procedure.

Verification checks source-copy behavior, current regression suites, documentation and governance. It does not establish deployment encryption or provider compatibility. Independent security/design and merge approval remain human responsibilities.
