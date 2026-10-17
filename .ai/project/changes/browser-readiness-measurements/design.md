# Design

Reuse the isolated artifact and local HTTP handler. A dedicated server per
fresh browser context imposes optional 150ms GET latency and 524288 bytes/s
per response; concurrent responses do not share a cellular-style aggregate
budget. CSP and runtime pins stay unchanged. Native parser results are compared
at every completed check. Only synthetic inputs are used.

Record artifact/probe hashes, versions, date, case counts, timings and explicit
scope. Page CDP JS heap snapshots omit Worker memory and are not a peak-memory
measurement. Startup WASM heap capacity is not total browser usage.
Accessibility tree checks cover labels, status and keyboard semantics only.

Lifecycle: investigation design -> developer verification -> independent review.
Review measurements against claims, privacy boundaries, failure status and
shared registry integration after #1365. Rollback is a PR revert; no migration.

Public examples are read only. example_corpus.py reuses the existing Node probe
and pinned artifact, replacing only fixtures and their manifest entry. Each
input is hashed, invalid examples stay included, over-limit inputs are accounted
for, and empty or mismatched results fail. This is separate Node-only evidence,
not browser or complete CLI coverage.
