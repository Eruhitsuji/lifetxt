# Safe writes, attachments, and compound work sessions

This document describes the revision-aware write routes introduced after the durable transaction foundation. The implementation keeps `life.txt` authoritative while ensuring that every authoritative mutation is either a single-file semantic compare-and-swap (CAS) or a journal-backed multi-target transaction.

## Semantic write contract

The shared write layer in `lifetxt.write_operations` performs transformations while the target lock is held. Callers provide the expected SHA-256 revision when strict conflict detection is required. The layer covers:

- append-only captures and journal entries;
- ID-addressed item updates and deletion;
- multi-selection TUI and fzf/peco actions grouped by source file;
- revision-checked restore and undo;
- tag merge across `life.txt` and configuration aliases;
- digest and template append operations;
- multi-file archive operations.

A stale expected revision raises a structured mutation conflict. A multi-file operation stages every replacement before the first commit and records a durable transaction journal. A failure after a partial commit remains recoverable through the transaction commands.

External-editor sessions are not automatically conflict-safe after the editor exits. A future editor workflow should edit a temporary copy and apply the resulting diff through an explicit revision-checked command.

## Archive safety

Archive operations retain the revision captured during the initial parse. The destination and every modified source file are committed as one journal-backed operation. This prevents a source edit made between selection and commit from being overwritten.

Use one or more explicit revisions when scripting an archive:

```bash
lifetxt archive active.txt \
  --destination archive.txt \
  --revision active.txt=<sha256> \
  --revision archive.txt=<sha256-or-missing>
```

The exact command options depend on the archive selector being used. The transaction result identifies the journal and committed target revisions.

## TUI and fzf/peco writes

TUI done, status, delete, detail, add, presence, timer, and undo routes now use the shared mutation layer. Multi-file selections are committed as one transaction. Undo records the revision produced by the original write and refuses to restore over a later external edit.

fzf/peco done and delete actions group selected records by file and use one semantic transform per file. The old direct writer compatibility bridge has been removed.

Real shell and terminal verification remains required for PowerShell, Windows Terminal, WSL, macOS, Linux, fzf, and peco behavior.

## Attachment transactions

Attachment files are confined to the configured attachment root. A file operation and its `life.txt` reference are committed together. Supported operations are:

- `put`: copy bytes into the attachment root and add/update the item reference;
- `reference`: attach an existing confined file after validating its revision;
- `delete`: remove the file and its item reference together;
- `status`: report the item and attachment revisions without mutation.

By default, path escape, symlinks, executable/script-like files, and stale revisions are rejected.

### CLI examples

```bash
lifetxt attachment status life.txt \
  --file attachments/report.pdf \
  --pretty
```

```bash
lifetxt attachment put life.txt \
  --id T-1 \
  --file attachments/report.pdf \
  --source ./report.pdf \
  --item-revision <life-sha256> \
  --attachment-revision '<missing>' \
  --require-revisions \
  --pretty
```

```bash
lifetxt attachment delete life.txt \
  --id T-1 \
  --file attachments/report.pdf \
  --item-revision <life-sha256> \
  --attachment-revision <attachment-sha256> \
  --require-revisions \
  --pretty
```

`--allow-symlink` and `--allow-executable` are explicit unsafe-policy overrides and should not be enabled for untrusted paths or content.

### Web and MCP

The Web API exposes attachment state and mutation endpoints. Strict mode requires both the item and attachment revisions; missing revisions return HTTP 428 and stale revisions return HTTP 409. MCP provides attachment put, delete, and state tools, while the existing file-reference tool routes file attachments through the same transaction contract.

Directory attachments and platform-specific open-reference behavior remain separate follow-up work.

## Compound work sessions

A work session updates task state, timer state, and presence as one recoverable operation.

Start can:

- change an open task to in-progress;
- create timer state;
- open a presence record.

Stop can:

- delete timer state;
- add elapsed time;
- optionally complete the task;
- close presence.

CLI, Web, and MCP use the same item/timer revision contract.

```bash
lifetxt start T-1 life.txt \
  --item-revision <life-sha256> \
  --timer-revision '<missing>' \
  --require-revisions
```

```bash
lifetxt stop life.txt \
  --item-revision <life-sha256> \
  --timer-revision <timer-sha256> \
  --require-revisions
```

Responses include the transaction ID, journal path, recovery state, and new target revisions.

## Transaction policy

The `transactions` configuration section supports:

```json
{
  "transactions": {
    "terminal_retention_days": 30,
    "max_transactions": 500,
    "max_total_bytes": 268435456,
    "max_transaction_bytes": 67108864,
    "require_private_permissions": true,
    "allow_newer_read_only": true,
    "evidence_include_paths": false
  }
}
```

The runtime verifies count and size limits, owner and private-mode expectations where the platform exposes them, and read-only inspection rules for newer journal versions. Abandon and archive operations create integrity manifests that can be verified later.

```bash
lifetxt safety transactions policy \
  --journal-dir .lifetxt-transactions \
  --pretty
```

```bash
lifetxt safety transactions archive \
  --journal-dir .lifetxt-transactions \
  --archive-dir transaction-archive \
  --older-than-days 30 \
  --force \
  --pretty
```

```bash
lifetxt safety transactions verify-backup \
  --backup-dir recovery-backup \
  --pretty
```

## Fault boundaries

The journal implementation exposes deterministic fault points around artifact writes, file fsync, replace, parent-directory fsync, target commits, compensation, and cleanup. These hooks support repeatable unit and subprocess drills without weakening production behavior.

They are not evidence of real power-loss portability. Real process termination, disk-full behavior, Windows replacement semantics, antivirus/indexer interference, cloud-synchronized filesystems, and network filesystems remain explicit P0 verification work.

## Clock boundary audit

Release policy scans Python source for direct host-clock calls. Every retained call must appear in `config/release/clock-boundary-baseline-v1.json` with a classification, reason, and removal condition. New unclassified uses fail the release gate.

Current retained categories include monotonic/operational timing, lock age, UTC audit and telemetry timestamps, time-only compatibility parsing, transaction retention, and TUI animation. Workflow date/time decisions must use the shared context-local timezone clock.

## Verified operator notes

- A revision precondition is meaningful only when it is captured from the same source set the write will later mutate.
- Attachment writes that touch both bytes and life.txt metadata should be treated as transactions, not as a file copy followed by a best-effort note update.
- `--allow-symlink`, `--allow-executable`, and similar flags are local policy overrides, not safe defaults for content received from another person or system.
