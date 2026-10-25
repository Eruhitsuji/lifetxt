# HKSCS-free candidate (#1415)

Owner chose removal rather than a permission enquiry. This is a separate build
candidate, not the official Pyodide runtime currently locked by `build.py`.
Do not substitute its hashes into the official-release provenance assertion.
The publication gate and both actual approval flags remain unchanged/false.
No permission email is sent.

## Source profile

`hkscs_free.py` verifies the existing `source-lock.json` upstream CPython hash,
removes `_codecs_hk.c`, `mappings_hk.h`, the `big5hkscs` wrapper, two mapping
samples and two HK-specific tests, and deletes the two encoding aliases.
It creates a curated archive with normalized metadata, a separate hash and a
removal receipt. Repeatability was checked on the recorded Linux host; byte
identity across different Python/zlib toolchains has not been established. Original notices, historical documentation, locale names and generator
references are retained; those references are not HKSCS mapping data.

Build staging also verifies the pinned Pyodide archive, adds `_codecs_hk` under
`*disabled*` in `cpython/Setup.local`, and makes a missing curated CPython input
fail rather than fall back to downloading the official archive. The xz, zstd
and SQLite recipes read verified local archives instead of unverified downloads. The original
upstream hash remains the provenance of the input, not the hash of curated bytes.

## Rebuild

Use a fresh directory and a Linux build host with Python 3.14.2 (including
headers), GNU make/patch/sed, autoconf/automake/libtool, cmake, pkg-config and
ccache. Cache files are the existing source lock's verified archives. These
commands stage the source; they do not install or publish a runtime:

```bash
python contrib/browser_check_poc/hkscs_free.py --build SOURCE_CACHE BUILD_DIRECTORY
```

The printed directory is the Pyodide build root. Install emsdk 5.0.3 at its
`emsdk/emsdk` location from emsdk commit
`a620cf1d71c62dfdfbb0c01fe0a371e2af2dda6c`. The SDK release identifier is
`065bfade0ee2c02138b83cb10049d8be95e146b6`; its Emscripten revision file reports
`285c424dfa9e83b03cf8490c65ceadb7c45f28eb`. Apply the pinned Pyodide
`emsdk/patches/*.patch` to `upstream/emscripten` in lexical order, verify
`src/struct_info_generated.json` against Pyodide's `src/js/struct_info_generated.json`
with `git diff --no-index --ignore-all-space`, then create the SDK `.complete`
marker. Do not create it if patching, compiler sanity or the comparison fails.

The SDK archives are downloaded by emsdk's normal versioned recipe. In this
container extraction requires `TAR_OPTIONS=--no-same-owner`. Bundled Node
22.16.0 crashed with SIGSEGV, so the local `.emscripten` `NODE_JS` points to the
existing Node 24.22.1. That host adaptation is part of the retained build
evidence, not a claim of bit-identical official release reproduction.
The container also rejects AF_UNIX sockets used by parallel compileall;
`COMPILEALL_OPTS=-j1` avoids that host limitation. The runtime stdlib ships
source `.py` files and excludes bytecode caches.

With the host Python 3.14.2 on PATH, run in the printed Pyodide directory:

```bash
PYODIDE_JOBS=4 make all-but-packages COMPILEALL_OPTS=-j1 > runtime-build.log 2>&1
```

This target builds CPython and the runtime without building all optional Python
packages. The staged root Makefile uses `hkscs_free_build.py` for single-write
JS embedding and a sorted, fixed-metadata stdlib ZIP built and CRC-checked in
memory. This avoids the duplicate append and incomplete ZIP observed during
the initial/incremental container build; the failures and corrected build are
retained in the change package logs. Preserve the complete log and nonzero status. Do not run a fixture
against the old npm runtime after a failed custom build. Copy the existing verified PoC `pyodide-lock.json` to `dist` (SHA256
`5dc2fc119108bc148c7457dc86e7675b5c87e1cafd420b9c34c1eaef7b36c010`).
This current PoC lock may be used only for the no-extra-package candidate's loader metadata; it is not
proof that any official wheel is compatible with the custom runtime.

## Verification and adoption boundary

After a successful build, the candidate `dist` directory must contain the five
runtime inputs used by the PoC. Run both probes from the lifetxt root:

```bash
python -m contrib.browser_check_poc.hkscs_free_verify PYODIDE_ROOT CURATED_DIRECTORY CANDIDATE SDK_LLVM_AR source-build-proof.json --source-cache SOURCE_CACHE
node contrib/browser_check_poc/hkscs_free_probe.mjs CANDIDATE wasm-proof.json
```

Stage a separate local test layout, then run the existing Core and real browser
probes; the layout command adds a Japanese/supplementary-character fixture:

```bash
python -m contrib.browser_check_poc.hkscs_free --probe CANDIDATE LOCAL_TEST_LAYOUT
node contrib/browser_check_poc/probe.mjs LOCAL_TEST_LAYOUT core-wasm-proof.json
python contrib/browser_check_poc/browser_probe.py --site LOCAL_TEST_LAYOUT --chromium CHROMIUM_EXECUTABLE --output browser-proof.json
```

The Python probe checks removed source paths, curated aliases, the disabled
builtin declaration, generated builtin module table, static library members,
stale HK object files and shipped stdlib. It reconstructs the curated CPython
source plus all nine locked patches and compares C, header and Python inputs,
and compares the five native dependency C/header source sets with locked archives. The Node probe actually instantiates
the candidate WASM, rejects module/codec lookup, tests Japanese codecs, and
hashes the exact five runtime inputs. These checks complement each other;
symbol absence alone is not an absence proof.

Also run the existing PoC/Core fixture probe with this candidate runtime and
the native regression suite. A Node run is not browser acceptance. Independent
final-head review and the separate source/distribution contract must bind the
custom artifact, curated CPython source, upstream patches, compiler receipt and
retained sources before website adoption. ICU permission evidence in #1414 is
independent of HKSCS removal and must still be reviewed. #1398/#1400 remain
blocked pending those steps; a source-removal receipt never grants publication.

## Final local checker profile (#1417)

The explicit `--hkscs-runtime` option in `scripts/build_website_checker.py` binds
this candidate to the complete checker and its ten same-origin source archives.
Prepare those archives with
`python -m contrib.browser_check_poc.custom_sources --upstream-cache CACHE --output NEW_DERIVED_CACHE`.
The derived hashes must match the reviewed `hkscs-distribution-lock.json`;
`--write-lock` is a maintenance operation requiring a new reviewed PR.
The custom builder requires the derived cache and has no old-runtime fallback.
Use `python -m contrib.browser_check_poc.distribution_audit ARTIFACT` for the
whole custom profile. `--require-publication` remains blocked pending acceptance.
See CUSTOM_SOURCE.md and DISTRIBUTION_REMAINING.md for source/acceptance scope.

The active fixed runtime/source/build records are retained in
`profiles/hkscs-free-1/`; historical change packages are not runtime configuration.
