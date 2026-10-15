# Design

Reuse Core context/source and Standalone native-host validation. Retain the
two musl targets, Zig setup, locked Cargo tests/build, actual Mini runtime/version
checks and existing Core conformance. Use fresh temporary target directories.

Read ELF64 headers and program/dynamic tables in stdlib to verify machine IDs,
bounds, load segments, no interpreter or external library dependencies; do not
depend on localized ldd text or execute a loader just to classify staticness.
Permit static PIE metadata without dependencies. This does not prove code safety.

Smoke runs the actual binary and existing scripts; the `python` alias used by
conformance must match the supported helper interpreter. The success report
binds runtime/static/conformance checks, toolchain, candidate/run/target and all
four file roles. Upload payload first and revalidate ELF/inventory/digests before
common component creation. Proof artifact contains candidate/report/component.

Notes retain the existing shared public filename and strict-subset language,
with identical bytes across arches. The canonical consumer deduplicates only
same-name/same-hash notes (handoff on #1305), never conflicting bytes. No new
canonical writer or public trigger. Parent collects both target artifacts and
authenticates their Actions metadata in #1321. Revert removes the producer;
already-public versions/tags/bytes are unaffected.
