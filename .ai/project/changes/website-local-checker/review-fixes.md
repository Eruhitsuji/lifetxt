# Product review remediation — issue 1399 (2026-10-26)

Source: main 9f4bb189a25b7adac73ca7ae53920ee0716d2481.
Owner request: fix issue 1399; execution contract is recorded on that issue.
Bug / High / S, complexity 3 (scope1/dependency0/uncertainty0/test2/ops0).
Adaptive-default W-model, implementation → developer verification → review.
Reuse cap-official-website and req-browser-local-check-v1.

## Changes and acceptance

- P-1: textContent summaries display location, severity, code, original message
  and optional hint. Both pages disclose English Core messages/hints; no Core
  translation or parser-contract change. Raw JSON is no longer the primary UI.
- P-2: all failure/timeout paths terminate the Worker, invalidate old replies,
  clear results and unlock controls, while retaining input only in page memory.
  Check retries without another paste. Explicit Cancel and pagehide clear input.
  Cancel remains usable when failed input is retained or text is edited.
- P-3: editing after startup reports a loaded runtime; warm checks do not claim
  to download it again. Ready transitions show checking rather than loading.
- P-4: performance.md separates fixture fill and 800-record repeated fill.
  Existing evidence yields JA 841.864 ms / EN 914.811 ms maximum repeated fill;
  rounded values are 842/915 ms. No new performance measurements are claimed.
- P-5: cold loading explains the approximately 14 MB transfer and connection
  dependence. No network completion estimate or public-network benchmark claimed.
- P-6 stays with issue 1400: publication profile enforcement is outside this fix.

## Verification and review viewpoints

UI fake-DOM regression checks both languages, diagnostic location/hint and
injection-shaped text, UTF8 bound, cold/warm timers, retained input for constructor,
Worker error, message decoding error, error reply and timeout; cancellation,
stale replies and pagehide are also covered. The browser probe is updated to
assert readable messages and retained offline/timeout input, including a retry
without another paste. Browser probe changes have not been executed here.

Self-review: inspected diff, output escaping, state transitions, stale reply IDs,
retention lifecycle, generated help, unchanged parser/CLI/network/storage/CSP
boundaries. No storage APIs or dependencies added. Scope: checker UI/build/probe,
dedicated tests and existing change package/traceability only.

Executed on Python 3.12.14 / Node 24.22.1:
- node tests/website_checker_ui.mjs: PASS (fake DOM only).
- python -m unittest tests.test_website_checker tests.test_website
  tests.test_website_pages_workflow tests.test_browser_check_poc
  tests.test_core_import_boundary tests.test_diagnostic_contract:
  34 tests, OK, 3 optional Web skips; real Node/WASM tests ran.
- python -m unittest tests.test_supported_runtime tests.test_traceability_gate
  tests.test_change_package_closeout: 19 tests, OK.
- python -m ruff check / format --check on changed Python files: PASS.
- python scripts/build_website_checker.py --output LOCAL_PREVIEW: PASS,
  20 Core modules, 288106-byte Core ZIP, 13531207-byte runtime (default preview).
- python -m unittest tests.test_website_checker_browser: SKIPPED; Chromium
  unavailable. Browser and headless-shell downloads both returned invalid ZIP
  content (end-of-central-directory missing). No browser PASS is inferred.

The existing historical browser evidence remains unchanged and does not verify
this head or profile2. Independent implementation/security and integration
reviews of the final head are pending; implementer self-review is not approval.
16KiB/100 diagnostics/120s cold/5s warm remain candidates pending Owner decision.
Profile2 final-artifact acceptance (1417), license gate (1398) and deployment
acceptance (1400) remain separate. No publication, merge or issue Close occurs.
Rollback: revert this PR; no data migration or stored-input change.
