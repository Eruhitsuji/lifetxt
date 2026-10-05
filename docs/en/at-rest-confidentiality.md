# At-rest confidentiality of attachments and recovery data

## Decision and limits

The supported baseline for sensitive deployments is **platform disk/filesystem/
dataset encryption plus least-privilege permissions and host isolation**, with
separate protection for backup destinations. lifetxt itself does not encrypt
attachment files, transaction artifacts or `.ltbackup` archives. This policy is
the recommendation from [#1098](https://github.com/Eruhitsuji/lifetxt/issues/1098);
merging its design PR accepts the policy, not an automatic storage migration.
Ordinary local use gains no key-management-service dependency.

Use an established platform facility, such as Linux LUKS/dm-crypt or Windows
BitLocker, covering **every** plaintext location below. Filesystem/dataset
protection is acceptable only if its content, metadata and auxiliary-file coverage
meet the deployment threat model. Encrypting only the final attachment directory
while leaving journals or backups on another unprotected volume is insufficient.
The existing `os-private-v1` evidence profile reports `encrypted_at_rest: false`;
its permission checks are not platform encryption detection. Permissions and
private directories prevent some local access; they are not
cryptographic protection against an offline disk reader.

## Threat model

Assume a trusted operating system, service account and application while running;
keep unlock/recovery secrets inaccessible to the attacker.

| Attacker / event | Protection and residual limits |
| --- | --- |
| Stolen or offline disk | Platform encryption can protect locked storage without its unlock/recovery keys. Unencrypted volumes, historical copies, exposed keys and an already unlocked running host remain outside this claim. |
| Stolen backup or off-host storage reader | Protect the backup independently. Source disk encryption does not travel with a file copied from an unlocked filesystem. Provider encryption protects only its documented boundary; use client-side backup encryption when the provider must not read content. |
| Another unprivileged local user | Restrictive directory/file ACLs, a dedicated service identity and process isolation are required. A mounted encrypted volume does not automatically deny authorized local reads. |
| Root/admin or application-process compromise | No confidentiality guarantee: a process authorized to read plaintext can leak it, and privileged attackers can obtain plaintext or keys. Server-side application encryption with keys available to that server does not solve this threat. |
| Modified data, replay, deletion or lost disk | Encryption alone does not establish application authenticity, freshness or availability. Existing revisions, integrity manifests and recovery checks detect some conflicts/corruption; unkeyed hashes are not proof against an attacker able to replace both content and hashes. Keep verified recoverable backups. |

Client-side **end-to-end encryption against an untrusted server** is a separate
capability. It needs client-held keys, encrypted protocol/storage contracts,
sharing/revocation and recovery design, and changes to server MIME inspection,
search and external-tool access. This policy does not claim E2EE.

## Plaintext and metadata inventory

Paths depend on actual configuration, environment and explicit operation targets.
Inventory each resolved path and its underlying mount, including linked directories
and remote mounts; a directory name under an encrypted parent is not proof that a
separate mounted filesystem is encrypted. Sources below describe the current
implementation, not automatic coverage discovery.

| Copy / surface | Location and creation boundary | Content / required protection |
| --- | --- | --- |
| Final local attachment or directory package | `attachments.root` (default: writable life.txt directory); Web uploads use `web-uploads/<random-id>/…`. `attachment_transactions.put_attachment`, package/reference operations. | Raw attachment/package bytes. Protect referenced local files too; an external path may have a different mount or owner. |
| Authoritative text and derived metadata | Writable life.txt and configured workspace sources; attachment open-reference metadata (`attachments.open_state_file`, default `.lifetxt-attachment-open.json`); configured state/config/diagnostic output files. | Titles, filenames, relative references, hashes, activity and private resource metadata can also be sensitive. Protect metadata, not just binary payloads. |
| Atomic replacement files | `atomic.atomic_write_bytes`: `.lifetxt-*.tmp` **beside the destination** for attachment, source, backup or restored file writes. | Plaintext replacement data. Normal cleanup is not secure erasure; a crash can leave remnants. Protect that directory/mount before writing. |
| Live recovery journals and durable-write temporaries | `transactions.journal_dir`, overridden by `LIFETXT_TRANSACTION_JOURNAL_DIR`; otherwise `.lifetxt-transactions` beside writable life.txt, or `.cache/lifetxt/transactions` without a write target. | `<transaction-id>/before-NNN.bin`, `after-NNN.bin` contain exact old/new bytes, including attachment bytes when that target is journaled. `journal.json` contains target paths/hashes/error metadata. `.lifetxt-tx-*` temporaries are beside each journal/artifact destination. |
| Terminal journal archives and abandonment backups | Operator-selected `archive_terminal` / `abandon_with_backup` destination, including integrity manifests. | Copies of the journal directory and byte artifacts, retained even after the live attachment changes or is deleted. Apply the same storage/ACL boundary. |
| Recovery working copies | `restore_backup(..., working_dir=...)`; default `<backup-dir>.restore-<random>` beside the retained transaction backup. `inspect` alone makes no working copy. | Resume/compensate works from a separate copy containing artifacts and writes targets. Protect both working-copy mount and restored targets. |
| Disaster-recovery archives, local status and restore outputs | Explicit backup sources or `backup.sources`; explicit destination or `backup.destination`; `.ltbackup` plus its same-directory atomic temp, status sidecar, and explicit restore destination. | `.ltbackup` is an **unencrypted ZIP**, not encrypted storage. Only selected existing files are included; attachments/journals are not recursively or automatically added from life.txt references. Manifests and status contain operational metadata. Restore writes plaintext. |
| Update backups | `server-update` configured `backup_paths` and timestamped `backup_dir`; only selected existing files. | Raw copies and source attributes, not encrypted archives; not a complete attachment/journal disaster snapshot. Verify destination directory/file access independently. |
| Off-host backup transfer | `backup.remote` / explicit rclone target; `backup_remote.upload_backup` copies the completed local archive with `rclone copyto`. | lifetxt adds no archive encryption. An operator-configured encrypted destination or established client-side tool must protect the remote copy; the local `.ltbackup` remains plaintext to its authorized reader. |
| Normal evidence export / support bundle | Explicit export destination; `transaction_journal.export_evidence` / workspace-safety support bundle. | Normal export is redacted: no attachment payload, authored text, raw absolute target path or error text. Hashes, fingerprints, operation/state/timing metadata remain; review before sharing. It is not a recoverable byte backup. |
| Raw evidence/operator copies, snapshots and Git history | Manual copied journal directories, copied artifacts, storage snapshots, exported archives, `.git` objects/remote repository if files were explicitly committed, editors and external viewers. | May retain full bytes or metadata after deletion. These are conditional copies, not automatic Web upload mirroring. The operator must include them in the inventory and restrict destinations. |
| Future provider download/cache/staging/spool | Any future resolver's selected cache directory, system temp, extraction destination, persistent queue or diagnostic evidence. | Whenever lifetxt persists provider bytes, they enter this same boundary. Adapter design must declare locations, limits, retention, cleanup and encryption before promising confidentiality. No generic provider cache is introduced here. |

Current Web upload buffers bounded bytes in memory; it does not create a multipart
spool file. Package creation and backup ZIP construction also use memory buffers.
This does **not** eliminate persisted copies: journal/final writes still occur,
and OS swap/pagefile, hibernation, core/crash dumps or a proxy request-body spool
can persist memory/content. Protect or disable such persistence according to the
platform/runbook. Reverse-proxy temp mounts are part of the deployment inventory.
A `PrivateTmp` service option isolates names; it is not encryption.

Bytes remaining exclusively at Google Drive, OneDrive, Dropbox, S3 or WebDAV are
outside lifetxt's guarantee. Provider/account/access/key policies belong to the
specific adapter/deployment design. This exclusion ends for any downloaded,
staged, cached, journaled or backed-up local copy; a reference-only model does not
imply either provider confidentiality or a hidden local mirror.

## Key custody, rotation and recovery

The deployment owner manages platform and backup keys using the chosen tool's
supported generation/unlock/recovery workflow. Keep unlock/recovery keys outside
life.txt, plaintext lifetxt config, repository history, logs, support bundles and
the data/backup they unlock. Use a protected OS/administrative secret store or
separately secured recovery escrow; lifetxt retains only existing non-secret
configuration/credential references. Unattended service unlock is a deliberate
host-security decision, not protection from that running host.

Keep recovery material for every retained encryption generation, including
platform-specific header/keyslot backup if required by that platform. Record
non-secret key/version identifiers and authorized recovery custodians. Test unlock
and recovery of a disposable copy, including the oldest retained backup, on a
separate authorized recovery environment before relying on unattended restart.
Loss of every valid key/recovery route makes encrypted data unrecoverable; lifetxt
cannot regenerate the key from a file hash or bypass the platform.

Distinguish changing an unlock credential/key wrapper from changing a data key.
A wrapper change may leave old ciphertext readable to someone with the old data
key or header. For suspected key disclosure, use the platform's documented
re-encryption/re-key procedure and cover retained snapshots/backups as well.
Never simply edit an encrypted backup tool's password and discard the previous
key. Validate the new protected copy and restoration before authorized retirement
of old copies/keys; this PR performs no re-encryption, deletion or retention change.

For off-host backups, an existing rclone `crypt` remote is one optional,
operator-managed client-side layer. It does not encrypt local archives or the
lifetxt process. Its normally obscured config password is not a secure secret
store: protect/encrypt the rclone config separately. Moving to a new crypt password
requires re-encrypting/copying data with both generations available. Download via
the decrypting tool into protected local storage, then run lifetxt backup verify /
restore on the recovered `.ltbackup`. Retention/listing compatibility for a chosen
crypt/provider setup must be tested before enabling deletion; no provider or key
service is installed or configured by this policy.

## Revisions, transactions and future application encryption

Transparent platform encryption leaves the application-visible bytes unchanged.
Existing plaintext SHA-256 attachment digests, source CAS revisions, directory
hashes, MIME/executable validation, journal integrity, CLI/TUI/Web/MCP and external
file tools retain their current semantics. Ciphertext on disk is the platform's
representation; do not substitute its hash into life.txt attachment references.
Format, journal and `.ltbackup` versions remain unchanged. Verify/restore after
unlock/decryption on protected storage; integrity checks do not certify that a
volume is encrypted. There is no data migration, automatic key generation or
`lifetxt encrypt` command in this change.

Application encryption is deferred because a final-file-only cipher leaves
journals, old revisions, backups and temporary files readable, while a complete
scheme changes multiple storage/recovery and access contracts. If a later threat
model requires it, a separate approved High-assurance design must specify:

- established authenticated encryption and a maintained library with an approved
  optional-dependency policy, rather than a custom cipher;
- per-object keys/nonces, authenticated object/version context, key storage and
  rotation, authorization, backup escrow and lost-key behavior;
- all inventory copies and plaintext-memory/spill limits; decrypt only within
  the validated access/MIME/recovery boundary;
- separate plaintext logical revision and ciphertext storage-integrity semantics,
  including hash/equality leakage, replay protection and versioned envelopes;
- transaction/crash recovery, protected migration/downgrade, old-key retention,
  interoperability and external-viewer/export contracts.

A server retaining decryption authority still cannot claim E2EE against itself.

## Operator verification

1. Resolve every inventory path, backup destination, mount and service account.
   Record only non-secret path classifications in shareable evidence.
2. Check platform encryption and unlock state using platform tools; verify all
   data, metadata, journal, backup, restore and temp mounts and auxiliary persistence.
   Set restrictive directory ACLs/ownership before first write; use a private
   service umask such as `0077` on POSIX and review inherited Windows ACLs.
   Do not assume a preserved existing file mode becomes stricter automatically.
3. Upload/attach harmless sample bytes in a disposable protected workspace. Inspect
   final files and journal artifact locations; compare before/after revisions.
   Verify a selected-file backup and a recovery working copy on protected storage.
   This identifies copies; it does not measure disk ciphertext.
4. Confirm remote backup encryption independently. Test downloading/decrypting,
   verifying and restoring to a separate protected location. Do not count source
   disk encryption or successful upload as remote encryption evidence.
5. Verify locked-storage access is denied under the chosen platform's test procedure
   and recovery succeeds with separately held escrow. Keep non-terminal journal
   evidence and required historical keys; do not delete data as an encryption test.
6. Review exports/logs for sensitive URLs and metadata. Possession-granting signed
   or capability URLs remain temporary secrets, not ordinary durable locators;
   prevent/redact leakage rather than treating encryption as its remedy.

TLS is separate: see [Web transport security](web-transport-security.md).
See [transaction recovery](transaction-recovery-and-strict-timers.md),
[backup format](backup-format-v1.md), and [Ubuntu deployment](../deployment/ubuntu-server.md).

Implementation sources: [attachment transactions](../../lifetxt/attachment_transactions.py),
[atomic writes](../../lifetxt/atomic.py), [journals](../../lifetxt/transaction_journal.py),
[backup](../../lifetxt/backup.py), [rclone transfer](../../lifetxt/backup_remote.py),
[update backups](../../lifetxt/server_update.py), [Web upload](../../lifetxt/web_attachment_upload.py).
Platform/tool references: [Linux dm-crypt](https://www.kernel.org/doc/html/latest/admin-guide/device-mapper/dm-crypt.html),
[fscrypt threat model](https://www.kernel.org/doc/html/latest/filesystems/fscrypt.html#threat-model),
[BitLocker](https://learn.microsoft.com/en-us/windows/security/operating-system-security/data-protection/bitlocker/),
[recovery keys](https://support.microsoft.com/en-us/windows/security/encryption/find-your-bitlocker-recovery-key),
[rclone crypt](https://rclone.org/crypt/). These describe tool-specific properties;
they are not evidence that a particular lifetxt deployment enabled them.
