# Preliminary evidence (2026-10-03)

## Baseline

* `origin/main`: `0d340f0e24b60d3ee6cd95186ac0fd9bec6b715a`
* Python used for repository evidence: 3.12.3 (`pyproject.toml` supports >=3.10)
* default `python`: 3.6.5 (unsupported; `import lifetxt` fails at
  `importlib.resources`)
* Node: 24.19.0
* `uv`: 0.12.22; `pywrangler`/workers-py: 1.17.6; Wrangler: 4.147.0
* baseline: supported-runtime 2 tests passed; focused safety/config/archive 101
  tests passed

## CPython evidence

`smoke_native.py` completed for 0/1/10/100/500 deterministic Japanese records.
It called the authoritative parser/check path, `convert_text("life", "json", …)`,
`resolve_quick_input`, and explicit-time priority classification. Unterminated
quoted input returned structured `E018` diagnostics. The native adapter is
stateless and contains no subprocess, fetch, persistence, or raw-body logging.

The 500-record check took approximately 0.0296 seconds on this Windows CPython
3.12 host. This is not a Cloudflare CPU measurement and must not become a
public request limit.

## Import boundary finding

On CPython 3.12, `import lifetxt` succeeds but takes about 0.42 seconds cold and
loads 353 modules; `subprocess`, `socket`, and `pathlib` are present in the
resulting module graph. This is evidence that package-root eager initialization
is broader than the stateless PoC semantics. It is not by itself proof of
Pyodide incompatibility. The Worker must not add a Cloudflare-specific
workaround; if Pyodide confirms the semantic modules work while root import is
unsuitable, the recommendation is **GO WITH PLATFORM-NEUTRAL CORE-IMPORT
REFACTOR**.

## Cloudflare status

Local validation completed with `uv run pywrangler dev` and Wrangler 4.147.0.
The selected compatibility date is `2026-10-03` with `python_workers`; the
local toolchain selected CPython/Pyodide 3.14.2. This is runtime evidence for
the PoC only, not a project-wide Python 3.14 support declaration.

HTTP evidence at the local Wrangler port (`127.0.0.1:1461`):

* `/health`: 200, `{"ok": true}`
* `/v1/info`: 200, engine `1.0.3`, base engine revision recorded, runtime metadata
* `/v1/check`: minimal and Japanese/Unicode inputs 200/valid; malformed quoted
  input 200/invalid with `E018`; 100-record deterministic fixture 200/valid
* internal non-contractual smoke: conversion, quick input, and priority matrix
  all completed successfully

Wrangler reported 1,998 attached modules, 28,574.17 KiB total, and 9,047.18
KiB of vendored modules. These are local bundle observations, not deployed
compressed size. Worker memory and CPU counters were not observable locally.

## Preliminary adapter recommendation

The native Worker handler is currently preferred: it is working in Pyodide,
has a small explicit route surface, and avoids an additional ASGI compatibility
layer. FastAPI was not added to the Worker bundle; therefore no measured
FastAPI-vs-native CPU or bundle comparison is claimed. Qualitatively, FastAPI
would add routing/validation/OpenAPI benefit but also startup/package surface
and another compatibility layer. A production choice still requires a later
contract-focused comparison.

## Provisional decision

**GO WITH CORE-IMPORT REFACTOR candidate**, pending a cleaner import-boundary
experiment. Core semantics work in local Pyodide 3.14.2, but the authoritative
package root eagerly exposes a broad module graph and produces a large bundle.
No Cloudflare-specific workaround should be added. A platform-neutral
pure-core import boundary should be evaluated before production API design.

## Temporary Cloudflare deployment evidence

Deployment was approved for this investigation only.

* Worker: `lifetxt-cloudflare-public-api-poc`
* URL: `https://lifetxt-cloudflare-public-api-poc.leo10070021.workers.dev`
* Version: `3a4d4cd3-c971-4109-921b-04b2f8362a55`
* Engine/base revision reported by the deployed PoC: `0d340f0e24b60d3ee6cd95186ac0fd9bec6b715a`
* Adapter implementation was deployed from the uncommitted working tree based
  on that engine revision, and was later captured for review in PR #1056 at
  commit `abcbd06040cc1399cba33861f4dccd0d47112dcd`. The reported base
  revision is therefore not the exact source commit for the complete adapter.
* Startup time: 2479 ms
* Upload: 28,577.58 KiB; gzip 6,343.52 KiB
* Deploy duration: 141.50 sec upload plus 0.68 sec trigger update
* Compatibility: `2026-10-03`, `python_workers`, Python/Pyodide 3.14.2

All bounded endpoint requests returned HTTP 200. The invalid request returned
`valid=false` with `E018`; valid minimal, Japanese, 10, 100, and 500-record
requests returned the expected item counts. The internal smoke returned
successful conversion, `QuickInput`, and deterministic priority classification.

Cloudflare `wrangler tail --format json` observations (milliseconds):

| Request | CPU time | Wall time | Outcome |
|---|---:|---:|---|
| health | 17-18 | 17-18 | ok |
| info | 5-17 | 6-18 | ok |
| shared smoke | 119-137 | 119-137 | ok |
| check, 1 record | 3-5 | 3-6 | ok |
| check, 10 records | 4 | 4 | ok |
| check, 100 records | 16-17 | 17 | ok |
| check, 500 records | 47-49 | 47-49 | ok |

No `Exceeded Resources`, memory error, exception, or truncated invocation was
observed. Client wall time was much higher (roughly 45-180 ms warm and up to
about 1.7 s for some health/info requests) because it includes network/TLS;
it must not be treated as CPU time.

The 100/500-record CPU results exceed the documented Free-plan 10 ms CPU
budget, even though these test invocations completed successfully. This is
evidence for conservative later request limits, not a limit decision in #827.

## Final feasibility classification for #827

**GO WITH CORE-IMPORT REFACTOR**.

The platform-neutral import-boundary follow-up is tracked in [#1055](https://github.com/Eruhitsuji/lifetxt/issues/1055).

The authoritative Core runs on the deployed Python Worker runtime and the
native adapter is practical for small bounded work. The package-root/import
boundary and approximately 6.3 MiB compressed upload remain unsuitable as an
unexamined production foundation. FastAPI was not deployed; native already
proves the required path and avoids adding a second production runtime.

## Deployment decision request

The approved deployment was performed only for the named temporary Worker. No
production deployment was performed. The command used was:

```powershell
uv run pywrangler deploy
```

No account ID, token, secret, datastore, custom domain, or deployment workflow
is included in this repository. Rollback is redeploying the prior verified
stable revision; cleanup is deleting the PoC Worker through Cloudflare's
dashboard/API after confirmation.

## Final repository verification

The supported-runtime (2 tests), targeted configuration/archive/safety (101
tests), change-package closeout,
compile, native shared-core smoke, and integration checks passed. The captured
repository full suite completed with 4,974 tests, 313 skips, 14 failures, and
2 errors on this Windows host; the failures were existing host/environment
issues (cp932 decoding, temporary Git cleanup permissions, process-tree timing,
PATH/editor naming, and unrelated mutation/CLI tests), not Cloudflare PoC
failures. The change-package-specific closeout test passed after adding the
required `decisions.md`.
