# Backup Format (`lifetxt-backup-v1`)

Disaster-recovery backup snapshots (#836/#841), distinct from #731's
periodic local Git-commit worker:

| | Local Git-commit worker (#731) | Backup (#836) |
|---|---|---|
| Protects against | Edit/history mistakes in an existing repository | Host loss, disk failure, device loss, repository destruction |
| Where the recovery point lives | Inside the same local `.git` repository | A standalone archive file, optionally copied off-host |
| Mechanism | Periodic `git commit` | Explicit, integrity-verified snapshot archive |

The two mechanisms are never substitutes for each other: enabling one
does not make the other unnecessary.

## Container

One backup is a single `.ltbackup` file: a ZIP archive containing exactly
one `manifest.json` plus one `files/<index>` member per included source
file (`files/0`, `files/1`, ...). The archive is always built in memory
and committed to its destination path through the same shared
atomic-replace primitive `lifetxt/lifetxtz_codec.py` (#692/#693) already
uses, so an interrupted build can never leave a half-written `.ltbackup`
file at the destination -- either nothing exists there yet, or a complete
one does.

## Manifest (`manifest.json`)

```json
{
  "format": "lifetxt-backup-v1",
  "status": "complete",
  "created_at": "2026-01-15T03:00:00Z",
  "lifetxt_version": "1.0.3",
  "source_identity": "personal-workspace",
  "files": [
    {
      "path": "life.txt",
      "archive_name": "files/0",
      "size": 4821,
      "sha256": "…",
      "mtime": "2026-01-14T22:11:03+00:00"
    }
  ],
  "file_count": 1,
  "total_bytes": 4821
}
```

- `format` -- the only value this lifetxt version produces or accepts is
  `lifetxt-backup-v1`; an unrecognized (older or newer) value is refused
  with a distinct, actionable error rather than a best-effort read.
- `status` -- `"complete"` is the only value a backup can be restored or
  counted toward retention from. There is deliberately no other value a
  finished backup ever has; any other value marks an artifact that
  verification and pruning must reject.
- `created_at` -- UTC, ISO 8601. This, not filesystem modification time,
  is what `backup status`/pruning/listing sort by, so copying a backup
  file around never changes its effective age.
- `source_identity` -- a human-diagnostic label for which workspace this
  came from (for example a workspace name). Never a filesystem path,
  never a credential, never anything that would need redaction to share.
- `files[].path` -- a forward-slash relative path, safe to join onto any
  restore destination: never absolute, never containing `..`. When the
  source files share a common base directory, this preserves that
  relative structure (`sub/work.life.txt`); otherwise it is a
  disambiguated basename.
- `files[].sha256` -- SHA-256 over the exact bytes stored in the
  corresponding `files/<index>` archive member.

## Path/selection policy

`create_backup` only ever archives the exact paths its caller supplies --
it never walks a directory on its own. Credentials, rclone configuration,
and other secret-bearing files are excluded simply by never being part of
that explicit list; there is no separate "exclude" rule to keep in sync
with an "include everything" default, because there is no "everything"
default.

## Snapshot consistency boundary

Each source file's bytes are read independently, as close together in
time as this process can manage, but this is a best-effort sequential
read, not a cross-file transaction: lifetxt has no existing multi-file
read-lock/snapshot primitive for arbitrary reads (the transaction/journal
machinery that exists is for *writes*). Each file's recorded `mtime`
makes it possible to see, after the fact, whether the captured files were
genuinely simultaneous.

## Symlink/path-traversal handling

- At creation time, only regular files (`os.path.isfile`) are archived; a
  symlink is followed and its target's bytes are captured, matching how
  every other file in the same list is captured.
- At verification/restore time, every `files[].path` value is checked to
  be a safe, non-absolute, non-`..`-escaping relative path *before* any
  archive member is decompressed or any destination file is written.
  Restore additionally re-checks that the resolved destination stays
  under the requested destination directory as defense in depth.

## Resource limits

Both `manifest.json`'s and each `files/<index>` member's *declared*
(pre-decompression) size are checked against a fixed ceiling before that
member is ever decompressed, so a maliciously or accidentally oversized
archive is refused before it can exhaust memory.

## Forward/backward compatibility

`lifetxt-backup-v1` is the only version this lifetxt release both
produces and accepts. A future format revision that changes the manifest
shape in a backward-incompatible way must bump `format` to a new value
and ship an explicit migration or refusal note here; this version will
never guess at how to read a manifest it does not recognize.

## CLI

Verify an explicit archive as before, or verify the newest complete candidate
in the configured destination with one command:

```sh
lifetxt backup verify path/to/backup.ltbackup
lifetxt backup verify --latest
lifetxt backup verify --latest --destination path/to/backups
```

`--latest` uses the manifest's `created_at` ordering, ignores temporary or
incomplete artifacts, and verifies the selected archive with the same integrity
verifier as an explicit path. If the newest complete candidate is corrupt, the
command reports that failure and never falls back to an older backup.

See [`lifetxt backup`](cli.md) for `create`/`status`/`verify`/`restore`/
`prune`, and the [Ubuntu Server production runbook](../deployment/ubuntu-server.md#5-backup-and-restore)
for scheduled local/off-host operation and a conservative restore drill.
