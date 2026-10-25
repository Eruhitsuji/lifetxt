# HKSCS-free corresponding source (profile lifetxt-hkscs-free-1)

This is a custom build, not the unmodified official Pyodide release. Public
acceptance remains pending. Both distribution approval flags remain false.

The adjacent source-lock.json binds the ten archives actually provided here.
Pyodide and CPython have been modified; their original input hashes/URLs are
recorded separately from delivered archive hashes. All original licence files
remain in the archives. Modified Pyodide Source Code Form remains under MPL-2.0;
CPython and the other archives retain their original notices and terms. Required
binary/source/notice retention applies throughout any future public availability.

Changes made by lifetxt on 2026-10-25:

- CPython: remove Modules/cjkcodecs/_codecs_hk.c, mappings_hk.h,
  Lib/encodings/big5hkscs.py, both cjkencodings/big5hkscs samples and both HK-only
  test modules; remove the two codec aliases from encodings/aliases.py.
- Pyodide: disable _codecs_hk in cpython/Setup.local; consume the curated/local
  CPython/xz/zstd/SQLite inputs without silently downloading uncurated CPython;
  replace append-based JS embedding and disk-seeking ZIP construction with
  tools/hkscs_free_build.py (single write, normalized metadata, complete CRC).
  The packaging omits the tooling-only .cursorrules symlink; regular upstream
  sources, licences, SDK and CPython patches are retained.
- No Core/parser/CLI behavior or original third-party licence is changed.

Rebuild from these delivered archives:

1. Extract modified pyodide-source.tar.gz. Copy curated cpython-source.tar.gz to
   cpython/downloads/Python-3.14.2.tgz; copy xz-source.tar.gz, zstd-source.tar.gz and
   sqlite-source.tar.gz to cpython/downloads/ under those names. Never substitute
   the original HKSCS-containing CPython archive.
2. Follow the pinned SDK/host setup in the repository HKSCS_FREE.md (emsdk5.0.3,
   fixed SDK release and patches, host Python3.14.2). The delivered Pyodide tree
   contains those SDK/CPython patches. libffi/hiwire recipes pin the same commits
   as the supplied archives; optional wheel rebuilds are outside this profile.
3. Run PYODIDE_JOBS=4 make all-but-packages COMPILEALL_OPTS=-j1.
   Use the pinned loader pyodide-lock.json solely with no extra packages; no
   compatibility claim is made for official optional binary wheels.
4. Run source/object, actual WASM and final-checker/browser verification. Inspect
   this package's source-build-proof.json and wasm-proof.json for the exact tested
   candidate hashes. They are evidence, not independent compiler attestation.

The ICU byte/notice comparison is re-run against this curated archive, not only
the original upstream CPython. Recheck with
`python -m contrib.browser_check_poc.permission_probe verify --cache FIXED_ICU_CACHE --source-cache DELIVERED_SOURCE_CACHE --custom-source-profile`.
The adjacent icu-proof.json records exact XML/notice equality and still-pending
independent applicability acceptance; it is not a legal acceptance record.

The exact shipped Python source (including generated configuration) is also in
../runtime/python_stdlib.zip; Core source and its MIT LICENSE are in ../core.zip.
The source-build proof reconstructs nine CPython patches, matches source inputs
and checks module registration, installed static archive, object and stdlib
absence. Cross-host bit reproducibility is not established. A different binary
requires a new fixed profile and independent review; hashes must not be relabelled
as official release identity.

HKSCS is absent in this profile. Historical mapping attribution and the source
terms remain as audit history. Independent acceptance of this removal, the
source-specific ICU grant, remaining licence applicability, reviewed source
retention, exact final-head review and human publication/deploy authorization
are still required. An Owner risk claim alone does not clear those gates.

Current source-specific acceptance states are reviewed data in
profiles/hkscs-free-1/mapping-attribution.json in the repository and in the
packaged notices/mapping-attribution.json. Historical measurement booleans are
not current publication authority; the separate evaluator and human review apply.
