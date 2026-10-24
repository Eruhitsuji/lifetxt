# Decisions

2026-10-24 Owner requested #1398-#1400 implementation. #1399's contract permits
isolated implementation while distribution approval blocks publication.
Use a separate explicit preview builder so merging code cannot accidentally
bundle Pyodide into the current Pages artifact. Shared-file integration and
publication require accepted prior results on latest merged main under #1400.

Keep 16 KiB, 100 diagnostics and cold/warm budgets visible as candidate settings;
Owner receives focused measurements rather than an unmeasured guarantee.
Original Playwright Chrome/Headless downloads failed as invalid ZIP archives;
use the separately installed test-only @sparticuz/chromium 153.0.0 to observe
the actual product page. It is not a product dependency. No browser security/CSP
bypass is used; standard container --no-sandbox is recorded as test environment.

An initial offline-failure test failed because ordinary browser HTTP caching can
load static runtime assets offline. This does not imply input persistence.
Revised failure injection explicitly aborts a package GET while offline, then
restores it for recovery. Preserve that failed run locally rather than claiming
it passed. Full source-delivery attribution remains blocked in #1398.
