# Browser readiness measurements — #1366, 2026-10-17

Bounded desktop observations pass. **Product adoption, resource budgets and public distribution are not accepted.** #1358 retains those gates.

Python 3.12.14 / Playwright 1.64.0 / Chromium 153.0.8010.0 on local Linux. The executable came from `@sparticuz/chromium@153.0.0` (test tooling only), SHA-256 `53a15d6c3a3d27dfb54c4ba60278b1683136f70cf1e67e989da7dfbd3d451ef0`. Standard Playwright Chromium download failed with an invalid ZIP; local extraction of the pinned npm package succeeded. Launch flags match the earlier PoC: `--no-sandbox --disable-dev-shm-usage`; CSP and web security were not disabled. This does not test the OS process sandbox.

`readiness-evidence.json` records UTC time, actual executable version, probe/manifest hashes, artifact files and per-profile observations. Both contexts are fresh within one browser process; OS caches and machine scheduling are uncontrolled. “Cold” means the first Check in that context, not a freshly installed device. The second profile adds 150ms before GET handling and paces each response at 524288 bytes/s. Concurrent responses have independent budgets; this is not a cellular aggregate-bandwidth model or physical mobile performance.

| Observation | Loopback | Paced responses |
| --- | ---: | ---: |
| First Check to result (s) | 2.37 | 21.91 |
| 64KiB single-record Worker parse (ms) | 10.10 | 10.30 |
| 2000-record Worker parse, median (ms) | 30.05 | 29.70 |
| 2000-record automated fill, median (s) | 3.38 | 3.42 |
| CDP page embedder snapshot after stress (MiB) | 457.33 | 175.42 |
| CDP page embedder snapshot after forced GC (MiB) | 42.55 | 42.57 |

Both profiles compare every completed result object with native CPython: a valid exactly 65536-byte title, thirty 2000-record checks and 500 warnings truncated to 100 displayed diagnostics. The next byte is refused without HTTP. Warm checks do not request assets. Cancellation clears input/output and restart succeeds. Observed successful-context requests are same-origin GETs without query/body; local/session storage, IndexedDB, Cache API, service workers and cookies are empty at the snapshot. These are bounded observations on synthetic records, not universal input-privacy guarantees.

The actual accessibility tree has the labelled textbox, Check button and status role. Tab reaches Check with a visible 3px focus outline. This is not screen-reader acceptance. No new Japanese screenshot, physical device, branded Safari or desktop-menu 200% zoom evidence was obtained; MANUAL_ACCEPTANCE.md records exact remaining steps.

## Resource finding: do not adopt limits from parser speed alone

The repeated input is 54000 bytes. Automated textarea fill takes about 3.4 seconds per iteration while Worker parsing takes about 30ms. Fill is measured separately; Check-to-result time excludes it. Playwright fill is not a measurement of a real person’s typing or Japanese IME latency, but the gap warrants investigation of long multiline editing/rendering.

CDP `Runtime.getHeapUsage` is sampled on the page target. Its `embedderHeapUsedSize` grew substantially during stress, remains high immediately after clearing, and falls after an explicitly forced GC. These are snapshots of a browser-internal metric, **not RSS, total tab/process memory, a sampled peak, proof of a leak or evidence that normal interaction will collect promptly**. Startup WASM heap capacity is separately 31457280 bytes (30MiB), not total memory usage. Worker peak memory and low-memory recovery remain unknown. No resource threshold is waived by the bounded “passed” status.

Resource-budget follow-up: #1367.

Before adopting the experimental 64KiB/100-diagnostic/120s-startup/5s-check budgets, measure real editing, process memory and normal GC on supported browsers and low-memory devices. Do not lower limits or change UI/Core silently in this investigation.

## Public-example import/conformance expansion

`example-evidence.json` records **115 / 115** exact native/parser-only Node WASM result matches, with 0 excluded files. The collector visits all `examples/**/*.txt`, including invalid/counterexample inputs, and records each relative name, byte count and SHA-256. Non-UTF-8 or native execution errors fail; an empty corpus cannot pass; over-limit files are explicitly accounted for. This run includes 111 valid results and 4 diagnosed invalid results.

The existing Node probe and the same 20-module Core ZIP are reused. Only the experimental fixture set and its manifest entry change. The result supports the current import closure on these examples; it does not establish future dynamic-import closure, all Format 1.0 combinations, browser compatibility, native-history validation or full CLI equivalence. The earlier CLI 14/16 diagnostic comparison and its two scope differences remain unchanged.

## Reproduce

```sh
npm ci --prefix contrib/browser_check_poc --ignore-scripts
python contrib/browser_check_poc/build.py --output .cache/readiness-site
python contrib/browser_check_poc/readiness_probe.py --site .cache/readiness-site --chromium /path/to/chromium --output .cache/current-readiness.json
python contrib/browser_check_poc/example_corpus.py --site .cache/example-corpus-site --output .cache/current-examples.json
python -m unittest tests.test_browser_check_poc_readiness
```

Use new build directories. Node is needed for examples; Playwright and a local Chromium are optional local test tooling for actual measurements. The browser CLI exits nonzero for partial/blocked/failed measurements; example generation/probing exceptions also exit nonzero. Do not substitute old retained JSON after a failed command. Required-mode browser unittest commands and manual handoff are in README.md / MANUAL_ACCEPTANCE.md.

No production code, website, CSP, workflow, Settings, deployment or real records changed. Incomplete binary attribution/MPL source delivery and independent distribution review remain in RUNTIME_INVENTORY.md / #1358.
