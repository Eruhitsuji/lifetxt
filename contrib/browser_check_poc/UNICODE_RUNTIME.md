# Isolated Unicode-minimal runtime build (#1530)

This is a build candidate, not the accepted profile2 or an approved distribution.
Parent #1436; independent object/stdlib/WASM/parity verification is #1531, final
integration is #1437, distribution/source-specific acceptance is #1398, and
publication is #1400. All existing profiles, locks and publication flags stay
unchanged. Keep candidates and corresponding source private until those gates pass.

## Stage fixed source

Use a clean checkout and the seven exact delivered archives in
`profiles/unicode-minimal-3/inputs.json`. These are modified profile2 source
archives, not replacements downloaded from original upstream URLs. Their notices
remain intact. The source-only curator verifies the original input and historical
130-removed/4927-retained/count/digest/output receipt. The reviewed 18-file source-only encoding list remains unchanged. Actual builder
smoke proved that zipfile needs cp437 even for ASCII filenames without a UTF-8
flag. The runtime stdlib therefore adds exactly one pinned CPython cp437 module
through a separate packaging overlay, with its original licence copied. This
does not enable legacy life.txt input; independent closure validation is #1531.

```sh
python -m contrib.browser_check_poc.unicode_runtime VERIFIED_SOURCE_DIRECTORY NEW_STAGE_DIRECTORY
```

The output directory must be new, its parent trusted, and the source directory
must remain immutable. Inputs are checked, copied and rehashed before use. All
staged files have SHA-256 in `stage-receipt.json`; `INCOMPLETE` marks a failed
stage and must never be bypassed. Rerun with a new directory after investigating
failure. The recipe never downloads a compiler or runs make implicitly.

The recipe disables `_multibytecodec`, `_codecs_cn`, `_codecs_jp`, `_codecs_kr`,
`_codecs_tw`, `_codecs_iso2022`; `_codecs_hk` was already disabled. The only
non-regular input members accepted are two exact, same-directory zstd test
symlinks in its pinned source archive. Expanded archive/header/padding bytes,
member sizes and counts are bounded. Libffi and hiwire recipes use pinned local
archives instead of git fetch. The existing xz/zstd/sqlite local-source recipes
and the HKSCS-free single-write stdlib/embed helper are reused.

## Explicit toolchain setup

Use Linux with host Python **3.14.2** including headers, GNU make/patch/sed,
autoconf, automake, libtool (including the libltdl development macros), m4, pkg-config, CMake and Node. Host-tool provenance
must be recorded; a version string is not binary identity. Host Python does not
replace the CPython source compiled for WASM. Host tools are not mandatory
lifetxt runtime dependencies.

Install emsdk under `PYODIDE_ROOT/emsdk/emsdk` from commit
`a620cf1d71c62dfdfbb0c01fe0a371e2af2dda6c` and install/activate **5.0.3**. It must
resolve to SDK release `065bfade0ee2c02138b83cb10049d8be95e146b6` with Emscripten
revision `285c424dfa9e83b03cf8490c65ceadb7c45f28eb`. Do not install `latest` or run
upstream's unpinned emsdk bootstrap target. Verify SDK `upstream/bin/clang` SHA-256
`141b521b24f86d0533968431cb2a3a08a202507e022ac8d0a02ec43b9585169e` before use.

Apply every pinned Pyodide `emsdk/patches/*.patch` in sorted order in the SDK's
`upstream/emscripten` directory. Compare its `src/struct_info_generated.json` to
Pyodide `src/js/struct_info_generated.json` with
`git diff --no-index --ignore-all-space`. Only after compiler sanity, patching
and comparison succeed create `emsdk/emsdk/.complete`. Record Node binary and
version actually used by the SDK and npm; do not assume the legacy host workaround
is needed on another host. Record `.emscripten` and patch identities privately.

The new recipe clears `_EMCC_CCACHE`: compile with the verified emcc directly.
Ccache is an optional speed optimization and not part of the compiled input
contract. A failed ccache build is not a successful compiler setup. npm uses the
pinned Pyodide `src/js/package-lock.json`; Emscripten ports and all fetched build
inputs must be retained/reconciled before distribution, not assumed covered by
this staging receipt alone.

```sh
cd PYODIDE_ROOT
. ./pyodide_env.sh
PYODIDE_JOBS=4 make all-but-packages COMPILEALL_OPTS=-j1 > build-attempt.log 2>&1
```

Record the actual exit code. `COMPILEALL_OPTS=-j1` avoids parallel compileall's
AF_UNIX requirement on restricted hosts. A successful make is only a compiled
candidate: hash the output WASM, JS, stdlib and exact loader/lock bytes, record
source revision, all source modifications, host/SDK/compiler identities and logs.
Never reuse old binary hashes or claim parser/browser acceptance without execution.

## Developer verification

```sh
python -m unittest tests.test_unicode_runtime tests.test_unicode_minimal tests.test_traceability_gate tests.test_change_package_closeout
ruff check contrib/browser_check_poc/unicode_runtime.py tests/test_unicode_runtime.py
ruff format --check contrib/browser_check_poc/unicode_runtime.py tests/test_unicode_runtime.py
```

The synthetic recipe tests run without SDK/compiler/downloads. They do not prove
that a compiled Python boots or that mapping data is absent in linked WASM.
Actual attempts and environment/outputs are recorded separately. Do not call
runtime/source-specific license or public distribution accepted from these tests.

## Known limitations and next gate

The historical gzip receipt is fail-closed and can differ across zlib versions.
A new content receipt requires actual source and independent evaluation, not a
fabricated digest. Upper-bound gzip members/tar trailing data are not strictly
rejected. Retained tests/docs/internal zipimport may contain other encoding
references or data: #1531 must inspect source/object/stdlib/WASM separately and
report actual findings. The initial actual WASM booted but Python `zipfile` failed with unknown cp437;
the overlay fixes that focused builder smoke. Full package/parser closure and
source-specific acceptance remain unverified.

Independent latest-head implementation/security and integration review, CI and
Owner merge are required. No profile adoption, source-specific resolved-removed,
public flags, website, Pages or deployment changes are included. Revert this PR
for rollback; the candidate is an isolated directory, not a live deployment.


## This host's preparation notes (2026-11-07)

Host tools were installed in a user-owned prefix, not system directories. The
original `.deb` URLs/SHA-256 are the fixed `host_tool_packages` entries in the
existing profile2 procurement record. Autoconf/automake/autotools-dev/libtool/m4
and libltdl7/libltdl-dev were used. Relocate their `/usr/share/` references and
references to `/usr/bin/{m4,autom4te,autoconf,autoheader,autoreconf,automake,aclocal,libtoolize}`
to that prefix; preserve `/usr/bin/perl` and `/bin/sh`. Add local `aclocal` and
`automake` aliases to the provided `*-1.16` programs. Set `PERL5LIB`,
`AUTOM4TE_CFG`, `AUTOMAKE_LIBDIR` and `ACLOCAL_PATH` to the relocated data paths.
Those host-specific adaptations and hashes belong in the retained private build
checkpoint. On a normal host with system packages they are unnecessary. Do not
copy a relocated configuration from another absolute path without verification.


## Actual builder smoke

The initial 18-file candidate compiled and booted with UTF-8 Japanese/emoji but
reading a freshly created ZIP with `sample.txt` failed: `LookupError: unknown
encoding: cp437`. The overlay is taken from `Python-3.14.2/Lib/encodings/cp437.py`
of the pinned input archive, SHA-256
`5c2a5015cd36cf7f561269f33dec4c323093d3d88b0673969accdabdcb9ce2cb`.
Its header identifies VENDORS/MICSFT/PC/CP437.TXT. That attribution and the
CPython licence are retained; this is not source-specific legal acceptance.
Only stdlib packaging changes, not the compiled C source or historical source-only
archive. A fresh final stage reproduces the same compiled-stage source receipts.
Actual make attempts, outputs and final smoke are in the candidate build evidence.


`all-but-packages` does not generate a package index. Builder smoke copies the
verified existing `pyodide-lock.json` (119077 bytes, SHA-256
`5dc2fc119108bc148c7457dc86e7675b5c87e1cafd420b9c34c1eaef7b36c010`)
into the isolated candidate and loads with `packages: []`. No optional binary
package ABI compatibility is claimed. This inherited index is a recorded test
input, not adoption of the old runtime or an approved new distribution manifest.

Final builder result: make attempt 6 built the native/runtime candidate; attempt
7 packaged the cp437 overlay successfully. The initial and final WASM SHA is
`5566748c285a67d1a4e37ea149a221969d8e1872c92c2704fd5e7c08dee24598`.
All five candidate file hashes, host identities and failed attempts are in
`profiles/unicode-minimal-3/build-evidence.json`. Native WASM and stdlib startup
smoke is limited developer evidence; runtime_verified remains false pending #1531.
The final new recipe's stage was rerun from the pinned archives and matched the
source inputs of the incremental compile/package run. This is not a separate
second full compile or a cross-host bit-reproducibility claim.

The private checkpoint retains original mapping-containing input archives as
provenance. It is not a final public corresponding-source bundle. #1437/#1398
must choose the exact distributable derived sources and audit their scope; do
not publish the checkpoint or infer resolved-removed for all retained inputs.
