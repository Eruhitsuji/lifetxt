# Actual browser follow-up — 2026-10-17 (#1360)

Actual headless Chromium passes the bounded parser experiment. This advances
the conditional GO; it does not approve adoption, publication, full CLI parity
or all-browser/device accessibility. #1358 retains those product gates.

## Execution and evidence

`browser-evidence.json` retains the generated manifest, exact file hashes,
probe hash, 16 native reference comparisons and sanitized network/storage
observations. Base Core: `17583a3ec1946f38a3ae4122ff3cbce36d11378d` plus
the #1360 isolated builder/notices and test additions. Core and PoC UI/Worker
bytes are unchanged from #1359. The original Node evidence remains separate.

Python 3.12 / Playwright 1.64.0 drove Chromium **153.0.8010.0** on local Linux
over loopback HTTP. Test tooling used the binary packaged by pinned
`@sparticuz/chromium@153.0.0` (not shipped with the PoC); its Brotli binary and
SwiftShader assets were unpacked locally because its convenience extraction
attempt failed on a temporary font-directory ownership operation. Only
`--no-sandbox --disable-dev-shm-usage` launch flags were supplied. Neither CSP
nor browser web security was disabled. This container run is not evidence of
the browser's OS process sandbox or a physical mobile device.

Reproduction commands and optional/required dependency behavior are in README.
The standalone probe writes JSON only after all assertions pass. A failed run
must not be reported as a current pass using an older retained output.

| Check | Observed result |
| --- | --- |
| Native reference vs actual browser Worker | 16/16 exact result objects |
| Lazy startup and warm reuse | No Worker/runtime fetch before Check, no HTTP on warm corpus; warm check works offline |
| Primary-context network | 30 same-origin GET requests, all without query or body; asset reloads after cancellation included |
| Storage snapshot | Empty local/session storage, IndexedDB, Cache API, service workers and cookies |
| Boundaries | Oversized UTF-8 refused without HTTP; diagnostic HTML remains text |
| Failure lifecycle | Cancel clears and restarts, initialization cancel, failed download/retry, held-asset startup timeout clear/re-enable |
| Timeout fixture | Real DOM/Worker; 120001ms page timer fast-forwarded, not a 120-second wall-clock measurement |
| HTTP/CSP | WASM `application/wasm`, module JS MIME; separate inline-script negative fixture blocked by unchanged CSP |
| Layout and keyboard | 1280/640/390/320px no horizontal overflow; Enter check, Tab order, 3px visible focus, label/status roles |
| Mobile emulation | 390px, touch, device scale factor 3; Japanese input parses and W203 shown; not physical Safari |

Request recording and empty error arrays concern the primary successful
context; separate negative-test contexts intentionally produce failures. This
is not an OS packet capture or universal proof that every browser/extension
cannot record data. Static HTTP caching is distinct from input persistence.

Cold interaction was about 2.32s, of which Worker startup reported 2.16s and
first parse 130ms. Warm 1/100/1000/2000 simple-record parsing reported about
0.5/2.1/16.3/32.2ms. These single-run wall-clock observations over loopback
exclude realistic download bandwidth and are not mobile performance promises.
The 31,457,280-byte WASM buffer is allocated heap capacity at startup, not
peak process/tab memory. Automation interaction wall times are kept separate.

## Visual/accessibility limits

The 390px screenshot was inspected: layout wraps without overflow, but this
test image lacks CJK fonts and shows Japanese glyphs as boxes. Japanese parsing
is evidenced, Japanese visual quality is **not** accepted. Screenshots remain
local probe output; the retained JSON records the manual inspection separately
from the automated probe's `screenshots_inspected=false` default.

CDP visual scale 2 was exercised; pinch/visual scaling is **not desktop browser
zoom at 200%**. Physical iPhone/Android, Firefox, Safari, screen reader behavior,
desktop zoom and peak/low-memory/throttled-network testing remain open in
#1356/#1358. Role/label/focus assertions are not a screen-reader audit.

## Distribution licences: partial improvement, not clearance

The local artifact now includes upstream Pyodide 314.0.7 MPL-2.0, CPython 3.14.2
combined licence and Emscripten 5.0.3 MIT/NCSA texts. `notices/provenance.json`
records exact upstream URLs, original/stored hashes and whitespace normalization;
tests enforce stored hashes and preserve `complete_distribution_audit=false`.
The manifest covers these copied notices as well as executable assets.

Version evidence comes from upstream Pyodide's tagged
[Makefile.envs](https://github.com/pyodide/pyodide/blob/314.0.7/Makefile.envs).
That build also enables libraries such as zlib, bzip2, libffi, hiwire, lzma,
SQLite and zstd. They require an exact shipped-binary/component/version mapping
and corresponding notice/source-availability review; the top-level npm licence
and three texts do not establish completeness. A package index lists available
wheels, not proof all those wheels were shipped or requested.

Before public distribution: finish that inventory, confirm notice/source
delivery against actual artifact contents, obtain independent review and Owner
approval under #1358. No production runtime, website, workflow or Settings were
changed; no deployment, real records or external processing were used.
