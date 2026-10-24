# Focused candidate acceptance (2026-10-24)

Actual product preview, Chromium 153.0.8010.0, Ubuntu 24.04 x86_64,
headless 1280x900 over loopback HTTP. Synthetic records only. Test host has
Noto Sans CJK JP for Japanese visual inspection; the product adds no font download.

| Measurement | Japanese | English |
| --- | --- | --- |
| Native-parity cases | 22/22 | 22/22 |
| Maximum input fill (all cases) | 330 ms | 312 ms |
| Cold Check-to-result | 2117 ms | 2212 ms |
| Max Worker check (all cases) | 96 ms | 107 ms |
| Repeated 800-record checks | 30/30 | 30/30 |
| Maximum repeated Check-to-result | 77 ms | 94 ms |

These are bounded synthetic observations, not universal latency guarantees.
16,384 UTF8 bytes exactly is accepted (ASCII and Japanese); 16,385 is rejected
before Worker submission. 100/500 diagnostics preserve total count while
showing at most 100. Known parser-vs-CLI differences remain explicit.

Recommendation: retain 16 KiB / 100 diagnostics for this limited candidate;
retain conservative 120s cold / 5s warm timeout budgets pending Owner acceptance
and real deployment/network evaluation. No smaller limit was substituted.
The initial 54KB/2000-record concern does not become a claim that all resource
problems are solved. CDP page-only heap metrics are recorded separately and
exclude Worker/WASM/OS peak; they cannot prove absence of leaks. Broad physical
low-memory testing is outside the approved initial scope.

Network observations were same-origin GETs without query/body. Local/session
storage, IndexedDB, cookies, Cache API, Service Worker registrations and watched
page persistence calls remained empty. Ordinary HTTP caching of static assets
can make a cold Worker load offline; load failure was injected explicitly.
Input is never placed in static assets or URLs by the app. Extensions, browser
session restoration and OS capture are outside these observations.

Japanese/English screenshots were inspected after installing a test-host CJK
font. Earlier missing-font tofu was an environment problem; no product font or
CSP relaxation was introduced. Full screen-reader conformance is unverified.

#1398 source/attribution approval and independent High reviews are still open;
#1400 must verify the actual publication artifact/CSP/MIME/operational contract
and obtain separate Owner merge and deployment authorization.
