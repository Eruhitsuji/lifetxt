# Exact profile3 technical verification (#1531)

This task measures the candidate from #1530/#1532. It does not adopt it or
approve distribution, legal applicability, final source bundles or publication.
The implementer wrote and executed these tools; separate High review remains
required. runtime_verified and both distribution approval flags remain false.

## Inputs and trust boundary

Use a clean checkout of the current verification PR and the privately retained
checkpoint v2 (identity in profiles/unicode-minimal-3/retention.json). Verify the
archive and all member paths/types/duplicates before data-only extraction to a
new directory. Its original mapping-containing input archives are provenance,
not a final public corresponding-source bundle; never publish the checkpoint.

Static verification requires Linux, GNU patch and the fixed SDK llvm-ar whose
hash is bound by build-evidence.json. SDK binaries are not in the checkpoint.
An unavailable compiler/object tree is NOT RUN, not PASS. Windows reviewers may
execute the candidate/probe without claiming Linux build/object verification.

Set BUILD to the checkpoint's build directory, SOURCES to its inputs directory,
CURATED to the retained cpython-unicode-minimal.tar.gz, CANDIDATE to candidate,
AR to the verified SDK llvm-ar, MANIFEST to checkpoint-manifest.json:

```sh
python -m contrib.browser_check_poc.unicode_verify BUILD SOURCES CURATED CANDIDATE AR MANIFEST NEW_REPORT.json
```

The checker pins the manifest and rehashes all 10,573 retained build payloads,
including config.c, object files, both static libraries and source. It separately
pins all five candidate files; no missing/extra files or implicit profile fallback.
It then restages fixed inputs and compares 555 staged files, reconstructs curated
CPython with all nine fixed patches and compares 3,084 C/header/Python inputs.
Generated config.c and the installed/build libpython archive identities are
checked. Archive members and actual objects are scanned for the seven forbidden
module names; Unicode's ordinary _codecs module is a required positive control.

CPython configure recreated an **empty** Modules/cjkcodecs directory. Empty
generated directories are allowed; any non-directory payload within the removed
CJK/mapping source directories fails. The initial too-broad directory-existence
check failed and was corrected; output is retained in the local static log.

The stdlib ZIP must contain exactly the 18 reviewed encoding files plus cp437,
with its pinned source hash; extra codecs, missing files, duplicates, corruption
and bytecode caches fail. A matching source/object inventory is not a compiler
attestation or proof that arbitrary unknown byte patterns cannot exist in WASM.

## Native/parser and actual Node/WASM checks

```sh
python -m contrib.browser_check_poc.unicode_verify prepare-probe NEW_PROBE_INPUTS
node contrib/browser_check_poc/unicode_probe.mjs CANDIDATE NEW_PROBE_INPUTS NEW_WASM_REPORT.json
```

Prepare-probe uses current native Core/parser output, all 115 public examples,
and five focused cases. It sets only this temporary adapter's limit to 16KiB
and restores the native module setting. The existing Core/CLI/website are not
edited. The Node probe validates the exact five runtime hashes before importing
the local loader, uses no optional packages and compares every native result.
The output records the actual core.zip/adapter/case bytes as hashes.

Actual results: all 120 cases match, including the exact 16,384-byte boundary,
oversized ASCII/UTF-8 rejection and diagnostic truncation at 100. In WASM all
seven target builtins are absent and their imports fail with the expected module
name; 12 removed codecs each reject lookup, encode, decode and wrapper import.
UTF-8 Japanese/emoji, Unicode escapes, ASCII/Latin-1, UTF-16/32, JSON and datetime
work. A deliberately constructed legacy non-UTF8 ZIP filename decodes with cp437.
These are Node execution results, not browser/network/storage/Worker acceptance.
JA/EN Chromium product integration remains #1437.

## Residual source data and unresolved acceptance

The full reconstructed curated source tree is scanned for six named textual
families (gb18030, hkscs, jisx?0213, gb2312, big5, cp437), not merely a few code
extensions. The recorded result has **33 files with references** and **28 retained
CJK sample files**. References are not automatically licensed mapping data nor
proof of its absence. Generated CP437 data in zipimport, the cp437 overlay, and
retained tests/docs need source-specific classification. Private original inputs
also contain historical mappings. No source-wide resolved-removed conclusion is
made. Source curation/distribution choice and license acceptance remain #1398/
#1437; this PR alone must not close those gates.

verification.json contains the exact source/static/runtime identities, residual
paths and measured results. Independent execution/review, final source residual
classification and all publication judgments remain pending. No byte search,
module import failure or successful CI substitutes for copyright permission.
Rollback is revert this verification PR; it changes no deployed runtime.

## Local checks

```sh
python -m unittest tests.test_unicode_verify tests.test_unicode_runtime tests.test_unicode_minimal tests.test_traceability_gate tests.test_change_package_closeout
ruff check contrib/browser_check_poc/unicode_verify.py tests/test_unicode_verify.py
ruff format --check contrib/browser_check_poc/unicode_verify.py tests/test_unicode_verify.py
```
