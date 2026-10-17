# Feasibility result — 2026-10-17 (#1356)

**Conditional GO for further browser validation using a self-hosted module
Worker and existing Python Core. Not approved for public deployment.** A local
PoC and real Node WASM execution are available; actual browser/mobile acceptance
is still blocked by this execution environment. Adoption/design follow-up: #1358.

## What ran

Engine base: `e59ef2b6ef2fb8f34edc86fccf7fcbb4d274d9fc` (1.0.4.1),
plus this isolated PoC working tree. Node 24.19.0, Pyodide314.0.7 / Python3.14.2
WASM; native reference Python3.12.14. The Pyodide runtime is pinned and installed
from npm. Generated file and PoC source hashes are retained in `evidence.json`.
This is not a general Python3.14 support declaration for lifetxt.

| Probe | Measured result |
| --- | --- |
| Native parser vs WASM | 16/16 identical result objects |
| Actual browser Worker source under Node shim | 16/16 identical to native corpus |
| CLI stdin with empty config vs parser diagnostics | 14/16 identical, including supplied positions/hints/categories/messages |
| Oversize Unicode input | Refused by adapter and worker; bytes, not character count |
| UI lifecycle fixture | Lazy startup, warm reuse, text-only output, cancel, timeout, stale response rejection pass |
| Worker thread | Main-thread heartbeat continues during startup; termination completes, including a fresh pending startup |
| Production static site | Existing no-script checker still passes; no PoC runtime enters its artifact |

Fixtures include empty, valid, Japanese/emoji, malformed quotes, unknown custom
keys, warning, line/column position, current/future format directives, duplicate
IDs, missing references, timezone directive, multiline body, HTML/Python-like
text, completed-parent and native-history records. A finite corpus is evidence
for these inputs, not an exhaustive Format conformance proof.

## CLI differences (must remain visible)

1. Completed parent with unfinished child: parser emits W103; CLI also emits
   **W225** through its additional parent/workflow pass.
2. `record:item_event`: parser exposes generic custom-field warnings. CLI's
   dedicated native-history pass suppresses/replaces some of these and emits
   **W261/W263/W264/W265/W266** for the tested incomplete event.

The parser therefore cannot be labelled a complete CLI `check` replacement.
CLI additionally calls progress/native history and attachment checking and has
configuration/multiple-file/source/filter behaviors not reproduced here. Keep
those out of the first parser-only UI or factor an approved pure shared check
contract in a separate task. No checks were copied into JavaScript.

The future-version fixture returns no parser/CLI diagnostic in this invocation,
but the parser metadata is `unsupported`. The PoC adapter deliberately exposes
`supported_format=false` / `valid=false`; it does not silently claim support for
a future Format. This is an adapter acceptance guard, not changed Core grammar.

## Size and timing observations

| Component | Raw bytes | gzip estimate (local, not HTTP evidence) |
| --- | ---: | ---: |
| 20-module Core ZIP | 76,645 | ZIP is already compressed |
| Pyodide WASM | 9,598,218 | 3,528,803 |
| Runtime JS module | 1,250,344 | 259,957 |
| Loader module | 17,931 | 7,152 |
| Python standard library ZIP | 2,545,637 | 2,503,129 |
| Pyodide package lock data | 119,077 | 26,335 |
| Runtime total | 13,531,207 (~12.90 MiB) | 6,325,376 (~6.03 MiB) |

Initial Node runtime initialization with local assets was about **1.90s**
in the retained final run. This excludes module import before the timer, npm download,
network latency and browser startup. It is not a cold mobile-download estimate.
One direct warm run measured approximately 0.17/2.76/21.76/40.89ms for
1/100/1000/2000 simple valid records (19/1900/19000/38000 UTF-8 bytes).
These are wall-clock times, not CPU measurements. The worker probe's first parse and subsequent parse are separate observations
in the JSON; first-use costs differ. No repeated-distribution benchmark, thermal
throttling test or performance guarantee is claimed.

The pinned runtime's internal WASM heap buffer reports **31,457,280 bytes** for
these probes. This is allocated linear memory, not total live heap, process RSS,
peak memory or browser/mobile memory. More complex records and repeated sessions
need real-device measurement. The 64KiB/100 diagnostic output/120s startup/5s
execution bounds are experimental proposals, not accepted production limits.

## Browser/mobile/network limitations

The local static server started, but the cloud browser could not reach
`http://127.0.0.1:8788/` (`net::ERR_CONNECTION_REFUSED`); it runs separately.
No actual desktop-browser execution, mobile engine/device, WASM MIME/CSP/CORS,
200% zoom, screen-reader, visual layout, download-network trace or browser storage
inspection is claimed. Node execution, fake DOM tests and upstream browser support
information cannot substitute for those acceptance items. The minimal browser
PoC exists but its browser execution criterion is **unverified**, tracked in
#1356 and #1358. It is not a production-ready or fully completed browser gate.

The Node Worker fixture restricts its source fetch shim to `core.zip` and
`adapter.py`; it observes those reads at startup and none for warm checks. The
Pyodide Node loader reads its local runtime files. UI source has no input network
calls/storage API, and input stays a function argument with text-only rendering.
This supports the design; a complete browser-level privacy test remains required.

## Recommended path and alternatives

Use self-hosted, pinned Pyodide in a module Worker for a clearly labelled
**parser and item validator** experiment. It reuses exact authoritative Python
code and avoids a second parser. A JS implementation could reduce download size
but would need a separate conformance contract and ongoing duplicate semantics;
there is no measured JS alternative here. An external API changes the privacy
and operations boundary and is not selected for this initial use case. A
main-thread Python implementation risks blocking UI and has no measured benefit.

Before adopting this approach, #1358 requires actual desktop/Safari/iPhone and
network/storage verification, broader Core import/Format coverage, production
limits/UX, a full runtime licence/notice audit, and an allowlisted script/CSP
boundary that preserves no-script ordinary pages. Owner must decide the product
scope and approve the architecture; divide ready work into small implementation
Issues. This PR neither lifts the site's script prohibition nor dispatches Pages.

## Verification and review

Focused repository run: 41 tests, 2 optional Web diagnostic tests skipped (Web
extras not installed), all executed tests pass. Ruff (including PoC Python),
focused format, approved mypy boundary and JS syntax checks pass. Actual WASM,
worker shim and CLI comparison run separately from the offline unittest suite.
The full runtime suite was not rerun for an isolated contrib investigation; PR
CI remains the integration gate. Self-review found and fixed a missing warm-check
timeout flag, ambient-module-dependent ZIP collection and an unfixed ZIP licence
entry timestamp. Independent latest-head
review and merge are owned by Eruhitsuji. Revert this isolated PR to remove the
experiment; no user data migration or public-service rollback is involved.
