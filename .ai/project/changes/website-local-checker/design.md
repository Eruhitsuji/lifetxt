# Local checker

Feature / High, adaptive-default W-model. M score 6 (scope2, dependency1,
uncertainty1, tests2, ops0): UI, Worker, bounded adapter and bilingual page
construction are one vertical behavior; distribution and deployment are
already separated into #1398/#1400. Reuse cap-official-website and the existing
PoC import closure, engine and five hash-pinned runtime files. No Core edits.
Source origin/main, dedicated feature/1399-local-checker, final base main.
Executor Codex; independent implementation/security/integration reviewer and
Merge Authority Eruhitsuji. No publication approval inferred.

Explicit build_website_checker builds only a local preview; the existing
website builder and workflow stay introduction-only. Keep checker assets in
one same-origin directory, outside translated HTML pages. Page scripts are
external modules; metadata escapes all copy. Limits live in one JS module;
the Python adapter independently checks the same UTF8 bound. The adapter
uses the same native parser/diagnostic serializer as the PoC.

Text enters a read-only textarea and FFI function argument, never Python source.
Rendering uses textContent. No storage, input upload, service worker or general
Python execution is offered. Busy input is read-only. Cancel/pagehide/error/
timeout clear input/results and terminate the Worker. Correlation IDs reject
late replies; cold/warm timers are separate and Worker creation/post errors
recover. Native grammar/diagnostics remain English where Core supplies them;
UI guidance and status are bilingual. The display names the parser-only scope.

Meta CSP is early and page-specific. Worker script trust comes from the pinned
same-origin artifact; this is not a user-code sandbox. Actual Pages delivery,
Worker response policy constraints, immutable artifacts, full notice/source
compliance, navigation/SEO and operational acceptance remain #1400 work.
The local preview is noindex and absent from the production sitemap/navigation.

Tests: native parser parity, actual Node Worker/WASM, fake DOM lifecycle,
loopback Chromium page/network/storage/boundary/recovery observations, and
unchanged introduction website/Pages contract. No physical-device or full
accessibility claim. Rollback is an independently reviewed revert; no deployed
state changes in this PR.
