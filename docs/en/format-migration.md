# Format 1.0 Migration Boundary

`format migrate PATH` is an explicit, revision-checked migration workflow.
It currently supports one lossless transition: an unversioned document gains
the leading `#! format_version: 1` directive. The command defaults to preview
mode; `--write` is required to mutate the file.

The workflow is intentionally conservative:

- a document declaring the current version is a no-op;
- a document declaring an unsupported version is rejected without writing;
- writes use the same content-hash mutation contract as `format canon --write`;
- `format downgrade --to VERSION` is inspection-only until a versioned loss
  matrix exists, and reports that no downgrade mapping is supported.

Canonical whitespace, encoding, and Unicode normalization remain the separate
responsibility of `format canon`. A future migration may add a source-version
mapping only with representative fixtures, an explicit loss report, and a
corpus/migration version decision.
