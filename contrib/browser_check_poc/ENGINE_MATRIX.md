# Additional engine validation — #1364, 2026-10-17

**Firefox and WebKit acceptance are blocked in this environment, not passed.**
This report does not add Safari/iPhone compatibility or remove #1358 gates.
The portable runner's successful path was checked using the existing test
Chromium, independently of the previous Chromium-specific probe.

| Engine/tooling | Actual outcome | Limit |
| --- | --- | --- |
| Playwright Firefox 157.0, build 1555 | Version reported; page creation crashed before HTTP acceptance | DEBUG browser log contains sandbox uid_map EPERM and child signal 11 |
| Playwright WebKit 27.2, build 2370 | Downloaded; launch refused before page creation | 21 missing shared libraries, including GTK4 and GStreamer |
| Chromium 153.0.8010.0 | Portable runner corpus 16/16 and bounded checks passed | Existing local container binary, headless, no physical-device claim |

Both extra engines were installed using Playwright 1.64.0's normal installer.
Its first CDN responses were truncated archives; the installer's own configured
fallback mirror completed the downloads. No access restriction was bypassed.
Firefox's OS permission error was not worked around. No sandbox preference,
CSP, web-security setting or OS library/security configuration was weakened.
The explicit local Chromium smoke uses the previously documented container-only
`--no-sandbox --disable-dev-shm-usage`, not evidence of its OS process sandbox.

`engine-evidence.json` retains sanitized blocked results and manifest/runtime
hashes, plus separate successful Chromium evidence. The blocked capture predates
adding the Chromium smoke option and an origin trailing-slash correction; both
capture hashes are preserved. Firefox/WebKit never reached acceptance and were
not retried after that blocked-status capture. Final runner hash is in the Chromium
capture; no current Firefox/WebKit pass is inferred from that code adjustment.

The runner covers real Worker/native corpus, unchanged inline-script CSP
negative test, MIME, lazy/warm/offline behavior, primary-context requests/storage,
HTML-as-text, UTF-8 limit, viewport/focus and cancel/clear/restart. Those assertions
are currently **evidenced in Chromium only**. Recorded requests are not an OS
packet capture; storage/API snapshots are bounded, not an absolute privacy proof.
Negative CSP fixtures use a separate context from successful error recording.

## Reproduce on a supported host

```sh
python -m pip install playwright==1.64.0
python -m playwright install firefox webkit
npm ci --prefix contrib/browser_check_poc --ignore-scripts
python contrib/browser_check_poc/build.py --output .cache/engine-site
python contrib/browser_check_poc/engine_matrix.py --site .cache/engine-site --engines firefox webkit --output .cache/engines.json
```

The host must already provide the required OS libraries and permit browser
sandbox initialization. Have its administrator prepare that environment; this
probe does not modify it. The command returns nonzero for **blocked or failed**
engines, and writes the result with explicit statuses. An empty/partial result
cannot pass. For unittest enforcement:

```sh
LIFETXT_BROWSER_ENGINES=firefox,webkit LIFETXT_REQUIRE_BROWSER_ENGINES=1 python -m unittest tests.test_browser_check_poc_engines
```

Without engine opt-in the real-engine unittest skips; two offline status/failure
regressions still run. Explicitly selected engines that cannot launch/page/check
do not silently skip or pass. Missing optional packages may skip unless required
mode is set. To validate the runner on Chromium, select `chromium` and provide
`LIFETXT_BROWSER_BIN` as described in README; that is not an extra-engine pass.

## Remaining acceptance

Re-run Firefox on an OS allowing its sandbox and WebKit on a host with the
listed libraries. Playwright's [official browser guidance](https://playwright.dev/python/docs/browsers)
distinguishes its patched WebKit from branded Safari: a WebKit pass still would
not be a physical iPhone/Safari acceptance. Actual iPhone/Android, Safari,
screen readers, desktop 200% zoom, CJK visual quality, low-memory/slow-network
performance and complete licence/source-delivery review remain open in #1358.
No public site, Core, Worker/UI behavior, workflow, Settings or deployment changed.
