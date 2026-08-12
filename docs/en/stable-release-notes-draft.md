# Stable Release Notes Draft

This draft is prepared for the first stable release. The release version and
tag are intentionally left to the release decision; this document must not be
read as a published release announcement.

## Stable boundary

The stable core is the dependency-light CLI and local life.txt workflow. The
supported format write path is unversioned input to Format 1.0. Existing
Format 1.0 documents are no-ops for migration. Legacy, unknown, future, and
downgrade transformations remain inspection-only or refusal-before-write.
See [Format migration](format-migration.md) and the
[compatibility matrix](format-compatibility-matrix.md).

## Verification status

CI covers the supported Python range, release policy, clean wheel smoke, and
native Windows/macOS core CLI smoke. External support requires the real-host
procedure in [External Environment Verification](external-environment-verification.md).
The four OS rows are not considered verified merely because CI passes.

## Known limitations

- Web writes remain subject to the strict revision evidence and deployment
  gates; read-only Web schema coverage is bounded and route-specific.
- MCP writable tools, Remote writes, and SMTP delivery are not stable promises
  without their dedicated evidence and authorization contracts.
- TUI, browser-engine, fzf/peco, cloud-sync, removable, and network filesystem
  support is limited to environments explicitly recorded by the release
  evidence matrix.
- Diagnostic spans are complete only for the parser families covered by the
  linked issues; diagnostics without source boundaries retain their existing
  representation.

## Installation smoke

Release validation must use a clean wheel or sdist in a fresh virtual
environment, not an editable checkout:

```text
python -m lifetxt --help
lifetxt --help
python -m lifetxt check examples/minimal_life.txt
```

The exact artifact hash, Python version, OS, and result must be recorded using
the external verification procedure before a stable tag is promoted.
