# Browser-local parser feasibility PoC (#1356)

**Experimental, local and synthetic-input only. Not the public website, an API,
or a complete replacement for `lifetxt check`.** See [RESULTS.md](RESULTS.md)
for the original conditional-GO decision. The follow-up actual Chromium results
and remaining acceptance gates are in [BROWSER_ACCEPTANCE.md](BROWSER_ACCEPTANCE.md).

## Reproduce

Use supported Python >=3.10 (3.12 was used), Node 24 (used here; no broader Node
compatibility claim), and npm. From the repository root:

```sh
python -m pip install -e ".[dev]"
npm ci --prefix contrib/browser_check_poc --ignore-scripts
python contrib/browser_check_poc/build.py --output .cache/browser-check
python -m http.server 8788 --bind 127.0.0.1 --directory .cache/browser-check
```

Open `http://127.0.0.1:8788/` on the **same machine**. Do not open the HTML using
`file://`. Each build needs a new output path; existing output is refused, never
deleted. The builder rejects the Core, website, change records and PoC source
folders as output. It does not modify the production Pages artifact/workflow.

Paste synthetic life.txt, choose **Check**, and inspect the JSON diagnostics
(severity/code/category/message/line/column/hint where supplied by Core).
`scope` explicitly identifies parser/item validation. `supported_format=false`
and `valid=false` reject an unknown version even if the permissive parser emits
no diagnostic. Warnings remain warnings. Display stops after 100 diagnostics;
`diagnostic_count` and `truncated` describe the full parsing result.

**Cancel / clear runtime** terminates the Worker and clears input/output. It is
available during startup and after a result. Timeout also discards them. Check
again to create a fresh runtime. Nothing executes until Check. Editing alone
does not fetch the runtime. Limits are experimental: 65536 UTF-8 bytes, 120s
startup and 5s warm execution. They are not production performance guarantees.

Generate repeatable evidence without claiming a browser test:

```sh
node contrib/browser_check_poc/probe.mjs .cache/browser-check .cache/wasm.json
node contrib/browser_check_poc/worker_probe.mjs .cache/browser-check .cache/worker.json
python contrib/browser_check_poc/compare_cli.py --output .cache/cli.json
node contrib/browser_check_poc/test_ui.mjs
python -m unittest tests.test_browser_check_poc tests.test_core_import_boundary tests.test_diagnostic_contract tests.test_website
```

The first command runs real WASM in Node; the second uses `worker_threads` with
a browser-worker shim, the same `worker.mjs`, local-only source reads and a UI
heartbeat. The UI test uses fake DOM/Worker objects; it is not rendering or
screen-reader evidence. `compare_cli.py` provides an empty explicit config and
stdin to the real CLI, independently of the parser adapter. Two observed
CLI-only differences are recorded rather than hidden or reimplemented.

Actual browser regression (optional dependencies; never a deployment):

```sh
python -m pip install playwright
python -m playwright install chromium
# Set this to the installed Chromium executable, not a browser profile.
export LIFETXT_BROWSER_BIN=/absolute/path/to/chromium
LIFETXT_REQUIRE_BROWSER_CHECK=1 python -m unittest tests.test_browser_check_poc_browser
python contrib/browser_check_poc/browser_probe.py --site .cache/browser-check --chromium "$LIFETXT_BROWSER_BIN" --output .cache/browser-result.json --screenshots .cache/browser-screenshots
```

Without the runtime, Playwright or executable, the optional unittest skips;
`LIFETXT_REQUIRE_BROWSER_CHECK=1` makes missing prerequisites fail explicitly.
The probe creates an ephemeral browser context and a loopback HTTP server,
uses synthetic fixtures only, and does not bypass CSP or web security.

## Design and privacy boundary

The builder packages 20 explicitly named, unmodified Core modules into an
in-memory Python-import ZIP, derived from the observed import closure (#1055).
It adds the existing diagnostic serializer and a small parser-only adapter.
The allowlist is **experimental**, not proof that all optional/dynamic imports
for every possible Format feature are included. No user configuration, workspace,
CLI bootstrap, Web/Remote server or release module is bundled. The imported
closure still includes some internal helpers such as config/atomic; no mutation
operation is invoked. Inspect `manifest.json` for source hashes and base commit.

A module Worker loads self-hosted, version-pinned Pyodide and the Core ZIP once.
Input is passed as a Python function argument through FFI, never interpolated
into Python source. Results use `textContent`, never `innerHTML`. No input
fetch/POST, storage API, service worker or third-party CDN is used by the PoC
UI. CSP limits scripts, workers and connections to its own origin. It is a
read-only check, **not** a general Python execution sandbox. The runtime and
Core must be trusted. Browser extensions, browser autofill/session behavior,
platform logs, or a compromised runtime are not covered by an absolute
"nothing can ever record anything" claim.

The source has no persistence. Actual Chromium network/storage inspection now
covers the bounded paths in BROWSER_ACCEPTANCE.md; other target browsers and
independent review remain required before a product-wide privacy promise. The
Node source-read hook is only evidence for the tested adapter paths. A timeout
must terminate the Worker, since a long synchronous Python call cannot be
cancelled by a JavaScript flag in that same worker. Main-thread execution was
not implemented; it offers no benefit for this use case and adds UI-blocking
risk. SharedArrayBuffer/COOP/COEP interruption was not required by this PoC.

## Dependencies, licences and updates

Current mapping and unresolved gates: [RUNTIME_INVENTORY.md](RUNTIME_INVENTORY.md).
Before creating output, the builder refuses missing/modified notices or any of
the five runtime files differing from the retained inventory. An intentional
upgrade needs renewed inventory/notice review; changing a hash alone is not review.

- `package.json` pins Pyodide **314.0.7**; `package-lock.json` fixes npm integrity
  and transitive dependencies. The installed Pyodide package declares MPL-2.0;
  `ws` and `@types/emscripten` declare MIT. They are tooling/runtime-package
  dependencies; only the five named runtime files are copied for the browser.
- Generated Core ZIP contains the project's MIT LICENSE and unchanged sources.
- `notices/` retains sixteen upstream notice texts with provenance/hashes and a
  partial component inventory; the builder copies them into the local artifact.
- Pyodide's binary/std-library distribution also incorporates CPython and other
  upstream code. npm's top-level licence is **not** a complete binary notice/SBOM
  audit. Full upstream licences, required notices/source obligations and their
  inclusion in a public artifact are a mandatory #1358 gate. Do not publish the
  current generated PoC as a production distribution.
- On update, change the exact version deliberately, regenerate the lock with npm,
  inspect dependency/licence changes, rebuild to a new path, compare every corpus
  result with native/CLI, check optional import closure and remeasure on actual
  target browsers/mobile. Retain manifest hashes, independent review and a
  previous verified artifact for rollback. Do not use an unpinned `latest` CDN.

## References

Official Pyodide [module Worker guidance](https://pyodide.org/en/stable/usage/webworker.html)
and [self-hosted core distribution](https://pyodide.org/en/stable/usage/downloading-and-deploying.html)
were read on 2026-10-17 (documentation version 314.0.7). The official guidance
supports module Workers and static hosting with correct WASM MIME headers;
these are upstream design references, not evidence that this PoC passed Safari.
Related: #1350, #1353, #1356, #1358, #1360, #827 and #1055.

## Additional browser engines (#1364)

[ENGINE_MATRIX.md](ENGINE_MATRIX.md) documents the portable real-engine runner,
explicit optional/required unittest modes and sanitized evidence. Firefox page
creation is blocked by this host's sandbox permissions; WebKit lacks OS libraries.
Neither is accepted. The runner's success path passes on the existing Chromium;
that smoke is not evidence of Firefox, WebKit, Safari or physical mobile support.

## Remaining readiness measurements (#1366)

`readiness_probe.py` measures two fresh Chromium contexts: loopback baseline
and server-paced GET responses (150ms delay, 524288 bytes/s **per response**).
This is not aggregate cellular throttling, a physical device or Safari evidence.
It compares exact 65536-byte input, 30 runs of 2000 records and a 500-diagnostic
case with native results, then checks rejection, AX semantics, network/storage,
clearing and restart. Page CDP heap snapshots and startup WASM capacity have
different scopes; neither measures total peak memory. Forced-GC observations
are diagnostic and separate from normal interaction. Input-fill automation time
is recorded separately from Check-to-result time and Worker parse time.

```sh
python contrib/browser_check_poc/readiness_probe.py \
  --site .cache/browser-check-site \
  --chromium /path/to/chromium \
  --output .cache/current-readiness.json
python -m unittest tests.test_browser_check_poc_readiness
```

Use the build instructions above to create the local artifact first. The CLI
exits nonzero for blocked/failed/partial measurements. Missing optional test
tooling skips only when not required. To require a fresh run through unittest:
set `LIFETXT_BROWSER_BIN`, `LIFETXT_RUN_READINESS=1` and
`LIFETXT_REQUIRE_READINESS=1`. These tests deliberately include paced downloads
and long-input editing and can take several minutes. Preserve a failed run's
output; do not substitute retained evidence for the current command result.

See [READINESS.md](READINESS.md) for measured results and open resource questions,
and [MANUAL_ACCEPTANCE.md](MANUAL_ACCEPTANCE.md) for the remaining actual-device,
assistive-technology, desktop zoom, Japanese rendering and distribution gates.
No public checker, production script permission or deployment is added here.

For the read-only public-example corpus comparison with the same Core ZIP:

```sh
python contrib/browser_check_poc/example_corpus.py \
  --site .cache/example-corpus-site \
  --output .cache/current-examples.json
```

Use a new output directory. The retained 115-case Node result is separate from
browser observations and does not establish complete Format/CLI compatibility.

### Distribution integrity gate (#1398)

The builder now checks its complete fixed artifact allowlist after generating
`manifest.json`. `python -m contrib.browser_check_poc.distribution_audit ARTIFACT`
emits component/source-delivery status and hash evidence. Use
`--require-publication` for a nonzero exit while any publication gate remains
open. Current source correspondence and independent distribution review remain
blocked; see the explicit artifact/source disposition in RUNTIME_INVENTORY.md.


### Fixed source acquisition and offline delivery (#1409)

The generated PoC and local checker now link to `sources/index.html`. The default
artifact contains pinned upstream download links; the offline bundle option
copies all ten verified source archives (about 76.5 MB, fetched only by explicit
maintainer action). No source archive is fetched when a visitor checks text.

```sh
python -m contrib.browser_check_poc.source_delivery fetch --cache .cache/runtime-source-cache
python -m contrib.browser_check_poc.source_delivery verify --cache .cache/runtime-source-cache
python contrib/browser_check_poc/build.py --output .cache/poc-with-sources --source-cache .cache/runtime-source-cache
python scripts/build_website_checker.py --output .cache/checker-with-sources --source-cache .cache/runtime-source-cache
python -m contrib.browser_check_poc.source_probe --cache .cache/runtime-source-cache --runtime contrib/browser_check_poc/node_modules/pyodide --output .cache/source-provenance.json
```

Every build needs a new output directory. `source_probe` additionally needs Node and the
`patch` utility; it applies upstream patches to temporary data files, never
executes the downloaded source or changes installed Python. The full-source
optional regression is enabled with `LIFETXT_RUN_SOURCE_AUDIT=1`,
`LIFETXT_SOURCE_CACHE` and `LIFETXT_SOURCE_RUNTIME`. Default tests use explicitly
synthetic archives and do not infer upstream acceptance from an optional skip.
See SOURCE_DELIVERY.md and source-provenance.json for measured relationships,
licences, limits and open independent-review gates. This is not public clearance.


### Review remediation and final checker audit (#1411)

All 29 notice documents are linked from the generated notice index. The source
index includes the full correspondence report. Public candidates require the
complete ten-source same-origin bundle; upstream link mode is development-only.

```sh
python scripts/build_website_checker.py --output .cache/checker-candidate --source-cache .cache/runtime-source-cache --publication-candidate
python -m contrib.browser_check_poc.distribution_audit .cache/checker-candidate
python -m contrib.browser_check_poc.distribution_audit .cache/checker-candidate --require-publication
```

The last command currently fails as intended: final-head independent review and
Owner decisions are pending. A future `--review-record FILE` binds a separate
verified record to the final commit and artifact manifest, without modifying
reviewed bytes. See [SOURCE_DELIVERY.md](SOURCE_DELIVERY.md) and the pending
[record template](publication-review.example.json). Actual status flags remain
false; synthetic gate success is not approval or deployment.


The second review adds explicit LF writes/checkout preservation, canonical stored
Core ZIP byte checking, schema2 record identities/references with an always-false
authority_verified field, and [mandatory human reference checks](PUBLICATION_REVIEW.md).
See [mapping attribution](notices/mapping-attribution.json) for legacy UCD3.2 and
source-specific CJK terms. HKSCS permission scope and independent acceptance of the located ICU grant remain
publication blockers; generic Unicode/CPython notices do not clear them.


## #1413 source-specific permission follow-up

The official ICU data XML has now been located and byte-compared: it equals the
CPython XML except for one additional trailing LF in CPython. The repository's
licence scope declaration and complete grant (including original ICU terms)
are pinned, verified and retained as a notice. Independent applicability
acceptance is still pending, so N-7 remains fail-closed. HKSCS needs an actual
source-specific clarification/grant or a separately verified removal/replacement;
no written permission has been received. See
[permission evidence and next action](https://github.com/Eruhitsuji/lifetxt/blob/main/contrib/browser_check_poc/PERMISSION_RESOLUTION.md).

HKSCS-free runtime candidate: [HKSCS_FREE.md](HKSCS_FREE.md). This isolated
build/verification profile does not replace the currently audited official runtime
or grant publication approval.
