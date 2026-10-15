# Decisions

- #1309 design approved; #1322 through #1325 prerequisites merged before work.
- Refined #1319 to a read-only producer and offline ELF/evidence tests; existing
  crate/version/conformance scripts and shared helper contracts remain unchanged.
- Replace ldd wording with direct ELF ABI structural checks; verify against
  native ELF header constants and real static/dynamic ELF fixtures.
- Local Cargo/Zig unavailable: fixtures do not certify actual Mini builds or
  conformance; retain both native runs/Actions transport as #1321 integration.
- Shared notes are byte-identical across arches; future canonical consumer
  deduplicates only identical content. No second SHA256SUMS writer.
- Independent implementation/integration reviews and human merge remain pending.
