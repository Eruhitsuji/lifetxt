# Local checker development preview (#1399)

This is an isolated implementation of `/ja/check/` and `/en/check/`, not an
approved public distribution. Standard `scripts/build_website.py` and the Pages
workflow still generate only the introduction site and do not copy these files.

From the repository root (Python >=3.10, Node 24 used for WASM tests):

```sh
npm ci --prefix contrib/browser_check_poc --ignore-scripts
python scripts/build_website_checker.py --output .cache/checker-preview
python -m http.server 8788 --bind 127.0.0.1 --directory .cache/checker-preview
```

Use a new output directory each time. Open `http://127.0.0.1:8788/ja/check/` or
`http://127.0.0.1:8788/en/check/`. Paste synthetic text and choose Check. It loads
about 14 MB from the same origin only on the first check. Normal input editing
cannot start the runtime. The existing twenty Core modules, PoC engine and five
pinned Pyodide runtime files are reused; the adapter preserves the native
parser/item diagnostic contract with a 16,384 UTF-8-byte candidate bound.
The display shows at most 100 diagnostics, with total and displayed counts.
This does not include all `lifetxt check` CLI diagnostics.

Cancel clears input/results and terminates the runtime. Error/timeout does the
same; paste again and retry after restoring the connection. A new worker starts
on the next Check. Normal browser HTTP caching of **static runtime assets** may
allow another cold worker to start offline; this is distinct from persisting
input. The app uses no browser storage APIs. The Python function receives text
as an FFI argument and the UI writes textContent; no user input is evaluated as
code or included in a network URL or body.

## Verification

```sh
python -m unittest tests.test_website_checker tests.test_website
node tests/website_checker_ui.mjs
LIFETXT_BROWSER_BIN=/path/to/chromium LIFETXT_REQUIRE_WEBSITE_CHECKER=1 python -m unittest tests.test_website_checker_browser
python scripts/probe_website_checker.py --site .cache/checker-preview --chromium /path/to/chromium --output .cache/checker-browser.json --screenshots .cache/checker-screenshots
```

The first suite runs real Node/WASM if the pinned runtime and Node exist;
otherwise that specific test explicitly skips. Fake DOM checks are separately
labelled and do not claim browser rendering. Required browser mode fails for
missing prerequisites. The probe creates a temporary browser context and binds
its static server to loopback. Only synthetic fixtures are used. Full raw local
failure logs remain local; the change package retains sanitized results.

## Publication boundary

16 KiB / 100 diagnostics / 120-second startup / 5-second warm budget remain
candidate settings until focused acceptance and Owner review. No claim is made
about all desktop Chromium variants, physical devices, Safari, Firefox,
assistive technology or OS peak memory. The Pages deployment is unchanged.

The generated page uses an early meta CSP (no unsafe-inline, same-origin
script/worker/connect, wasm-unsafe-eval limited to these pages). A meta CSP is
not an HTTP response header and does not establish a separate Worker response
policy or frame-ancestors protection. #1400 must accept actual Pages MIME,
Worker trust/CSP behavior, complete hash-bound artifact allowlist, notices,
corresponding-source delivery, language/navigation/SEO integration and rollback.
#1398 must resolve and independently accept full runtime attribution and
Pyodide/hiwire corresponding source first. Current notices are a partial
inventory and are not a source-delivery attestation. Do not publish this preview.
