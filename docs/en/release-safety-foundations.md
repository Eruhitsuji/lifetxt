# Release safety and Format 1.0 foundations

This batch adds dependency-free safety services before remote writes and Format 1.0 are declared stable.

For the versioning, deprecation, migration, and stable-support boundary, see
the [Stable compatibility policy](release-compatibility-policy.md). Format 1.0
and `LIFETXT_CANON_V1` are covered contracts; experimental and deferred
surfaces remain outside the stable promise.

## Revision-required operations

`lifetxt.safe_ops` exposes seven operation contracts:

- `quick_capture`
- `item_update`
- `mcp_write`
- `notification_acknowledgement`
- `timer_state`
- `archive`
- `undo`

Every operation requires `expected_hash`. Omitting it raises `ExpectedRevisionRequired`; passing a stale hash raises `MutationConflict`. Text transforms execute against the current in-lock text. Timer state uses the same rule for JSON.

```python
from lifetxt.mutation import read_text_snapshot
from lifetxt.safe_ops import quick_capture

snapshot = read_text_snapshot("life.txt")
quick_capture(
    "life.txt",
    "[ ] T Review release id:T-review",
    expected_hash=snapshot.content_hash,
)
```

## Safety commands

### Mutation locks

```bash
lifetxt safety locks life.txt --stale-after 300 --pretty
```

The output includes lock owner metadata, age, PID liveness when it can be checked locally, and whether the lock is proven stale. The command does not delete locks.

### Server read/write target diagnostics

```bash
lifetxt safety serve-target life.txt --write-file shared/life.txt --pretty
```

This warns when the server reads one target but writes another. It also detects Windows drive-relative paths such as `C:relative\life.txt`, which are not absolute paths.

### Timezone precedence

```bash
lifetxt safety timezone life.txt --timezone Asia/Tokyo --pretty
```

Timezone precedence is:

1. CLI override
2. `#! timezone:` file directive
3. `defaults.timezone` in config
4. host timezone

IANA timezone names are validated with `zoneinfo`. Explicit offsets inside datetime values remain authoritative for those values.

### Write-route audit

```bash
lifetxt safety write-routes --root . --pretty
lifetxt safety write-routes --root . --strict
```

The audit parses Python ASTs and reports direct `os.replace`, `atomic_write_bytes`, and direct write-mode `open` calls outside the low-level mutation boundary. `--strict` returns a non-zero exit code when findings exist.

### Release gate

```bash
lifetxt safety release-gate life.txt --root . --pretty
```

The gate reports:

- an executable stale-hash CAS probe;
- timezone-aware datetime round-trip behavior;
- golden-corpus presence;
- packaging metadata presence;
- published schema bundle presence;
- write-route findings;
- stable format diagnostics for requested files.

## Format 1.0 draft commands

### Version and policy report

```bash
lifetxt format info life.txt --pretty
```

The current directive is:

```text
#! format_version: 1
```

Unversioned files remain readable in compatibility mode. Unsupported versions are reported and must not be rewritten before migration.

The draft canonical form is named `LIFETXT_CANON_V1`:

- UTF-8 without BOM;
- LF line endings;
- NFC Unicode normalization;
- no trailing spaces or tabs;
- one final LF for non-empty files;
- case-sensitive identifiers and values;
- lowercase canonical detail keys;
- metadata precedence of CLI, file directive, config, then built-in default.

### Stable JSON diagnostics

```bash
lifetxt format check life.txt --pretty
```

Each diagnostic has `severity`, `code`, `message`, `source`, `line`, `column`, `span`, and `hint` fields. Parser diagnostics and Format 1.0 policy diagnostics use one response shape.

### Canonical check and repair

```bash
lifetxt format canon life.txt --pretty
lifetxt format canon life.txt --write --pretty
```

`--write` performs the repair with the exact hash of the file that was inspected, so an intervening edit causes a conflict instead of being overwritten.

### Schema bundle

```bash
lifetxt format schemas dist/schemas --pretty
```

The initial versioned schemas cover:

- item payloads;
- diagnostics;
- capability documents;
- conflict responses.

Each schema uses JSON Schema draft 2020-12 and an HTTPS `$id`.

## Capability document

```bash
lifetxt capabilities --authentication token --pretty
lifetxt capabilities --read-only --authentication session --pretty
```

The versioned response reports format, canonical, and schema versions; supported operations; authentication mode; read-only state; writable targets; optional features; and SHA-256 revision-precondition support. This is the base contract for future remote clients.

## Safety boundary checklist

- Do not mutate a file that declares an unsupported `#! format_version:` until a migration path is chosen.
- Use `format canon --write` only with the inspected revision; an intervening edit should be a conflict.
- Treat `lifetxt capabilities` as the advertised contract for clients rather than inferring write safety from individual commands.
