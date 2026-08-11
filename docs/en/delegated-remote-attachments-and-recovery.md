# Delegated mutations, remote attachment contracts, and recovery evidence

This release extends the P0 safety foundation in four connected areas: restart-safe delegated mutations, Web/MCP directory-package attachment parity, broader subprocess fault drills, and verified backup restoration. It also adds an opt-in server-authoritative clock precondition for writable Web and MCP operations.

## Restart-safe delegated mutations

Use this flow when a plugin or other program must propose a change to life.txt. The delegated command receives a private temporary copy, never the authoritative file. The prepared proposal stores the exact source revision, edited content hash, diff hash, command arguments, output, and validation result.

Prepare a proposal:

```bash
lifetxt safety delegated prepare \
  --path life.txt \
  --proposal .lifetxt-proposals/plugin-change.json \
  --command 'python plugin.py {file}' \
  --pretty
```

Inspect it after the original process or machine session has ended:

```bash
lifetxt safety delegated inspect \
  --proposal .lifetxt-proposals/plugin-change.json \
  --pretty
```

Apply it only if the proposal file and authoritative life.txt revisions still match:

```bash
lifetxt safety delegated apply \
  --proposal .lifetxt-proposals/plugin-change.json \
  --expected-proposal-revision PROPOSAL_SHA256 \
  --pretty
```

Reject it without changing life.txt:

```bash
lifetxt safety delegated reject \
  --proposal .lifetxt-proposals/plugin-change.json \
  --expected-proposal-revision PROPOSAL_SHA256 \
  --reason 'Not approved' \
  --pretty
```

Prepared proposal files are written with owner-private permissions where the platform supports them. Their stored edited text and unified diff are hash-checked before inspection or apply. A concurrent authoritative edit produces a normal revision conflict; the proposal is not silently rebased or overwritten. `--unsafe` exists for deliberate local recovery but bypasses the stored source revision and should not be used by integrations.
The important boundary is that the delegated command never receives the real
authoritative path. If the command crashes, writes invalid life.txt, edits the
temporary copy after producing output, or the user edits the real file before
approval, `inspect` and `apply` have enough recorded hashes to fail loudly
instead of guessing how to merge the result.

## Remote attachment contract

The Web and MCP surfaces now expose the same revision-aware directory/package operations as the CLI. The server publishes the contract through `/api/attachments/contract`, `/api/capabilities`, `get_capabilities`, and `lifetxt://capabilities`.

The contract includes:

- exact item, attachment, and metadata revisions;
- a stable caller-provided transaction ID for package retries;
- server-side package source confinement;
- deterministic ZIP generation and embedded integrity manifests;
- bounded chunk reads capped at 1 MiB;
- package-manifest inspection;
- transaction status and permitted recovery actions;
- no remote execution of platform attachment open commands.

### Web operations

```text
GET  /api/attachments/contract
GET  /api/attachments/chunk
GET  /api/attachments/package-manifest
GET  /api/attachments/transactions/{transaction_id}
POST /api/attachments/directory-reference
POST /api/attachments/package
POST /api/attachments/reconcile
POST /api/attachments/open
```

A package request uses a server-confined source path:

```json
{
  "id": "T-1",
  "source": "./specs",
  "path": "./attachments/specs.zip",
  "item_revision": "LIFE_SHA256",
  "attachment_revision": "<missing>",
  "transaction_id": "package-T-1-20260725"
}
```

The source must resolve beneath `attachments.remote_source_root`, or beneath the normal attachment root when a separate remote source root is not configured. Symlinks and non-regular entries remain rejected unless an explicit local policy permits them.

Retrying an existing transaction ID returns `DUPLICATE_TRANSACTION_ID` with the current journal state and supported recovery actions instead of starting another transaction.

Read a bounded package or attachment chunk:

```text
GET /api/attachments/chunk?path=./attachments/specs.zip&offset=0&limit=65536&attachment_revision=SHA256
```

Inspect the embedded manifest and every package member:

```text
GET /api/attachments/package-manifest?path=./attachments/specs.zip&attachment_revision=SHA256
```

The remote open operation validates the attachment and can update revision-checked open metadata, but it only returns an operating-system command plan. The Web server and MCP server do not execute the opener.
Use that plan on the trusted client side only. A remote attachment API can tell
you what would be opened, but it is not a remote command-execution channel.

### MCP tools

The equivalent MCP tools are:

- `attachment_directory_reference`
- `attachment_package`
- `attachment_reconcile`
- `attachment_open`
- `attachment_read_chunk`
- `attachment_inspect_package`
- `attachment_transaction_status`

Every writable MCP tool publishes an optional `client_time` input so clients can discover the clock precondition before it becomes required.

## Remote write clock precondition

Enable server-authoritative clock enforcement with:

```json
{
  "clock": {
    "require_remote_write_time": true,
    "client_time_header": "X-Lifetxt-Client-Time",
    "skew_warning_seconds": 30,
    "skew_reject_seconds": 300
  }
}
```

Writable Web requests must include an offset-aware timestamp in the configured header. Missing timestamps return HTTP 428 `CLIENT_TIME_REQUIRED`; invalid or excessive skew returns HTTP 409 `CLOCK_SKEW`. Successful responses include the measured clock state and skew headers. Parser-only endpoints remain usable without the clock header because they do not mutate authoritative state.

Writable MCP calls use the same policy through the `client_time` argument. Capability documents report whether enforcement is enabled and which Web header is expected.

This check detects gross client/server clock disagreement. It does not replace exact resource revisions, transaction IDs, authentication, authorization, or transaction recovery.
When enforcement is disabled, clients may still send the header or MCP
`client_time`; the response clock report is diagnostic. When enforcement is
enabled, writable calls without an offset-aware timestamp fail before mutation.

## Expanded subprocess fault matrix

The drill now covers 16 named boundaries around transaction-directory creation, before/after artifact persistence, journal publication, target commit, file fsync, replace, and parent-directory fsync.

Run the full deterministic subprocess matrix:

```bash
lifetxt safety transactions drill \
  --matrix \
  --recovery auto \
  --pretty
```

Run one boundary and repeat recovery to demonstrate idempotent terminal behavior:

```bash
lifetxt safety transactions drill \
  --point after_journal_publish \
  --recovery auto \
  --repeat-recovery \
  --pretty
```

For pre-journal boundaries, `auto` verifies that both targets remain unchanged before removing an unpublished orphan transaction directory. For published journals, it uses normal stale-lock handling and resumes the journal. Compensation remains available explicitly.

The matrix proves behavior after abrupt Python interpreter termination through `os._exit`. It does not prove physical power-loss durability, storage-controller ordering, disk-full handling, Windows replacement behavior, antivirus/indexer interaction, cloud synchronization, removable media, or network filesystem behavior.

## Verified backup restoration

Abandoned transaction backups remain immutable evidence. Restoration first verifies the original integrity manifest. `inspect` reads evidence without creating a working copy; `resume` and `compensate` copy the backup to a separate working directory and recover from that copy.

```bash
lifetxt safety transactions restore-backup \
  --backup-dir transaction-backups/TX-ID \
  --restore-action inspect \
  --operator alice \
  --pretty
```

```bash
lifetxt safety transactions restore-backup \
  --backup-dir transaction-backups/TX-ID \
  --restore-action compensate \
  --working-dir recovery/TX-ID \
  --operator alice \
  --pretty
```

The operation verifies the original backup again after recovery and writes a fresh integrity manifest for the working copy. Optional operator authorization can be enabled with:

```json
{
  "transactions": {
    "require_operator_authorization": true,
    "authorized_operators": ["alice", "on-call"]
  }
}
```

This is a local allow-list boundary, not a replacement for authenticated roles or OS access controls. Encrypted evidence profiles, key rotation, role-backed authorization, and real incident handoff drills remain release work.
For incident handling, prefer `inspect` first. It reads the retained evidence
without creating a working copy, which makes it the lowest-risk way to decide
whether a transaction should be resumed, compensated, abandoned, or escalated.

## Published schemas

The schema bundle adds:

- `delegated-mutation-proposal-v1.schema.json`
- `attachment-remote-operation-v1.schema.json`
- `attachment-chunk-v1.schema.json`
- `directory-package-inspection-v1.schema.json`
- `transaction-restore-v1.schema.json`
- `fault-drill-matrix-v1.schema.json`
- `remote-write-clock-v1.schema.json`
