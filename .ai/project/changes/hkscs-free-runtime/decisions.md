# Decisions

- Owner explicitly chose removal instead of HKSCS permission enquiry. No email is sent.
- Build from pinned Pyodide 314.0.7 / CPython 3.14.2 / Emscripten 5.0.3.
- Keep a separate candidate until source/distribution binding and independent
  review are complete; do not relabel official runtime hashes as custom bytes.
- SDK archive extraction uses TAR_OPTIONS=--no-same-owner on this container.
  SDK Node 22.16.0 terminated with SIGSEGV; use the existing Node 24.22.1
  executable through the SDK configuration and record this host adaptation.
