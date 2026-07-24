# Safe process boundaries, directory attachments, and transaction administration

This release extends the revision-aware write foundation to external editors, directory/package attachments, versioned transaction policy administration, abrupt-process drills, and server-authoritative clock-skew reporting.

## Safe external editor sessions

`lifetxt edit` no longer gives the authoritative file directly to the editor. It creates a temporary copy, starts the configured editor against that copy, validates the edited life.txt text, and applies the replacement with a SHA-256 precondition.

```bash
lifetxt edit life.txt --editor "code --wait" --show-diff
```

Useful modes:

- `--review-only` returns the complete unified diff without writing.
- `--reconcile` performs a conservative line-based three-way reconciliation when the source changed while the editor was open. Overlapping line ranges are rejected.
- `--keep-temp` retains the edited temporary copy for manual recovery.
- `--dry-run` preserves the previous behavior of printing the editor command without launching it.

TUI and fzf/peco editor handoff use the same temporary-copy and revision-check contract. A source changed after editor launch is never silently overwritten.

## Directory and package attachments

The attachment command now supports deterministic directory references and packages in addition to regular files.

Reference a confined directory by its deterministic tree revision:

```bash
lifetxt attachment directory-reference life.txt \
  --id T-1 \
  --file ./attachments/specs \
  --require-revisions \
  --item-revision LIFE_SHA256
```

Create a deterministic ZIP package and update the life.txt reference in the same recoverable transaction:

```bash
lifetxt attachment package life.txt \
  --id T-1 \
  --source ./specs \
  --file ./attachments/specs.zip \
  --item-revision LIFE_SHA256 \
  --attachment-revision '<missing>' \
  --require-revisions
```

Packages use sorted paths, fixed ZIP metadata, per-file SHA-256 values, and an embedded `lifetxt-package-manifest.json`. Limits are enforced before the transaction commits:

- `attachments.max_files`
- `attachments.max_bytes`
- `attachments.max_file_bytes`
- `attachments.ignores`
- `attachments.allowed_mime`
- `attachments.blocked_mime`

Symlinks and non-regular filesystem entries are rejected by default.

Reconcile an externally modified attachment by verifying the previously recorded hash and replacing only the life.txt reference hash:

```bash
lifetxt attachment reconcile life.txt \
  --id T-1 \
  --file ./attachments/report.pdf \
  --recorded-revision PREVIOUS_SHA256 \
  --item-revision LIFE_SHA256 \
  --require-revisions
```

Validate and plan an operating-system open action:

```bash
lifetxt attachment open life.txt \
  --file ./attachments/report.pdf
```

The default is a reviewable command plan. `--execute` starts the platform opener. Open metadata is updated through a revision-checked JSON file; use `--no-record` to skip that metadata write.

## Versioned transaction policy

A standalone versioned policy file can supplement normal configuration. Point normal runtime configuration at it with `transactions.policy_file`.

Create or update policy values atomically:

```bash
lifetxt safety transactions policy-write \
  --journal-dir .lifetxt-transactions \
  --operator alice \
  --set max_transactions=750 \
  --set max_total_bytes=536870912 \
  --pretty
```

Use `--expected-revision` for strict policy CAS. Unknown policy keys are refused. Version 0/unversioned documents can be migrated explicitly:

```bash
lifetxt safety transactions policy-migrate \
  --journal-dir .lifetxt-transactions \
  --operator alice \
  --expected-revision POLICY_SHA256 \
  --pretty
```

Newer unknown policy versions are read as unsupported and are never automatically downgraded.

Run startup-equivalent checks without changing anything:

```bash
lifetxt safety transactions preflight \
  --journal-dir .lifetxt-transactions \
  --pretty
```

Add `--force` to create and permission-harden a missing journal root. Set `transactions.preflight_on_startup: true` to make writable Web and MCP startup fail when policy version, capacity, ownership, or private permissions are unsafe.

Administrative operations append bounded, revision-safe audit records containing operator identity:

```bash
lifetxt safety transactions audit \
  --journal-dir .lifetxt-transactions \
  --operator alice \
  --event policy-reviewed \
  --details-json '{"ticket":"OPS-42"}' \
  --pretty
```

Rotate old integrity-manifest archives only after reviewing the dry-run and adding `--force`:

```bash
lifetxt safety transactions rotate-archives \
  --archive-dir transaction-archive \
  --max-archives 100 \
  --max-archive-bytes 1073741824 \
  --force \
  --operator alice \
  --pretty
```

## Abrupt-process recovery drills

The drill command launches a child Python process, performs a two-target transaction, and exits with `os._exit` at a selected durable boundary. The parent inspects the journal, ages only the confirmed dead child locks past the normal stale threshold, and optionally resumes or compensates.

```bash
lifetxt safety transactions drill \
  --point after_journal_publish \
  --recovery resume \
  --pretty
```

```bash
lifetxt safety transactions drill \
  --point after_target_commit \
  --recovery compensate \
  --pretty
```

This is evidence for abrupt interpreter termination. It is not evidence for power loss, disk-controller behavior, Windows replacement semantics, antivirus/indexer interference, cloud synchronization, removable media, or network filesystems.

## Remote clock skew

`GET /api/time` and MCP `get_clock_status` return server-authoritative UTC time. Supplying a client timestamp measures signed and absolute skew. Configuration controls warning and rejection thresholds:

```json
{
  "clock": {
    "skew_warning_seconds": 30,
    "skew_reject_seconds": 300
  }
}
```

Naive timestamps without a UTC offset are rejected. Reports use `ok`, `warning`, `reject`, or `not_measured` and explicitly state whether a remote write is allowed. The server timestamp remains authoritative.

## Published contracts

The schema bundle adds:

- `editor-session-v1.schema.json`
- `directory-package-v1.schema.json`
- `attachment-open-v1.schema.json`
- `transaction-policy-admin-v1.schema.json`
- `transaction-preflight-v1.schema.json`
- `clock-skew-v1.schema.json`

Real platform verification and remote write enforcement remain separate release gates.
