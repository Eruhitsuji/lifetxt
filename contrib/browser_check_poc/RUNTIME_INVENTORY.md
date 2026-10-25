# Current runtime distribution inventory — #1398 / #1411

This document describes the current PR candidate. It is bounded technical
provenance, not a complete SBOM, legal clearance or reproducible-build proof.
The five runtime files remain byte-identical to the pinned Pyodide 314.0.7
release; source lock and observed file hashes bind their identity. Both actual
publication flags remain false, and #1398/#1400 remain blocked.

## What is shipped and checked

| Object | Evidence and terms | Limit |
| --- | --- | --- |
| Pyodide JS/glue and WASM | Official core release SHA256 and 5/5 npm byte identity; Pyodide source commit b1e4fcc2488962f6360a97f19b9982d6fdb5d16f; MPL/third-party notices | No signed/reproducible upstream build attestation |
| CPython 3.14.2 | Recipe archive SHA256, all nine upstream patches apply without fuzz; PSF/combined software notices | Full WASM linked-object attribution unverified |
| hiwire / libffi | Recipe commits, source archives and MPL/MIT notices | Exact linked-file subset unverified |
| zlib 1.3.1 / bzip2 1.0.6 | Emscripten port SHA512 pins; original terms retained | Archive relationship does not attest upstream build inputs |
| zstd 1.5.7 / SQLite 3.39.0 | Actual WASM versions match recipe; source archive hashes retained | Upstream recipe itself has no input hash |
| liblzma / XZ 5.2.2 candidate | Recipe URL/version; retained mirror bytes equal independently retrieved official tukaani.org bytes | Actual linked liblzma version not exposed by measured interface |
| Emscripten / LLVM / musl | Recipe 5.0.3; source archives and original subtree notices for libc++, libcxxabi, compiler-rt, libunwind, llvm-libc and musl | Actual emsdk-used Emscripten commit and every linked object unverified |
| Expat / HACL / mpdecimal | Runtime imports/versions; original notices, distinct leading headers from checked HACL40/decimal41 files | Exact linked subsets not established |
| mimalloc / SipHash24 / dtoa / Mersenne Twister | CPython software-notice sections; actual WITH_MIMALLOC=1; _random builtin observed | Do not infer every file is linked |
| stackframe / MiniLZ4 | Vendored source and original notices | No claim of arbitrary npm-wheel inclusion |
| stdlib ZIP | All 567 regular files mapped: CPython535, Pyodide29, patched CPython2, generated sysconfig1; exact ZIP hash | Generated sysconfig hash/AST constants checked; no rebuild attestation |
| Core ZIP | Twenty unchanged modules and MIT LICENSE; canonical stored ZIP, fixed timestamps/platform/modes; full ZIP bytes regenerated and compared | No CLI/Remote engine bundled; intentional source changes require renewed review |
| Checker/UI/site | Whole-site manifest, fixed allowlist, actual source-byte comparisons and parsed notice/source navigation | Local candidate only; production workflow does not publish it |

Optional wheels in pyodide-lock.json are an available-package index, not shipped
wheels. No optional packages are automatically fetched. All 28 notice documents,
README and three metadata files are linked from the static notice index. All
ten source archives are required on the same origin for a publication candidate;
upstream-link mode remains a development aid and cannot pass the record gate.

## Character data and mapping sources

[Mapping attribution](notices/mapping-attribution.json) records the exact retained
CPython generator/input-member hashes and a source-specific terms assessment.

| Source | Checked basis and retained terms | Open scope |
| --- | --- | --- |
| Unicode UCD16 and legacy UCD3.2 | makeunicodedata.py old_versions; actual unicodedata/ucd_3_2_0 runtime versions; official current V3 and both release ReadMes | Historical per-input exceptions need independent acceptance |
| Unicode MAPPINGS subset | CP932/936/949/950, JIS0208/0212, BIG5 and identified eight-bit inputs; Unicode terms | Do not label every CJK or eight-bit contribution Unicode-only |
| HKSARG HKSCS-2004 | genmap_tchinese.py explicitly calls licence restrictive; official clauses5/15 reviewed | Derived-table permission scope unresolved; publication blocker |
| Historical ICU GB18030 XML | genmap_schinese.py plus retained XML version3 | No licence declaration found in the retained XML; matching historical ICU terms unresolved; publication blocker |
| JIS X 0213:2004 mapping | Original retained wakaba-web input header expressly allows use/modification/distribution; original earthian/I'O copyright retained | Independent acceptance of scope required |
| GB2312 historical FreeBSD endpoint | Actual retained table identifies Unicode1991–1999 rights and product-use/notice-preservation terms; leading header retained | Hosting domain is not a licence; independent acceptance required |

The CPython source archive's presence does **not** establish that PSF terms
replace a third-party input's terms. In particular, this PR does not clear the
HKSCS/ICU questions by assuming Unicode V3 applies. Source and notice retention
are evidence for that evaluation, not its result.

## Reproduction and gates

See [SOURCE_DELIVERY.md](SOURCE_DELIVERY.md) for commands and source retention.
The source probe checks all 11 verification archives, selected member hashes,
recipe pins, nine patches, all stdlib files and actual WASM versions. New output
must reproduce source-provenance.json; changed source/runtime hashes must never
be accepted merely to make an audit green.

Generated text uses UTF-8/LF regardless of host defaults. Checkout attributes
preserve original notice bytes and LF source assets; Core ZIP uses stored entries
to avoid zlib-version differences. Manifest order is POSIX-path order. Git commit
and manifest hash still change on intentional content/revision changes.

The offline gate checks **record shape/binding**, not identity or authority.
`authority_verified=false` and `human_reference_verification_required=true` are
always visible, even with a syntactically accepted record. Approval fields in
that report are unverified record claims. Follow [PUBLICATION_REVIEW.md](PUBLICATION_REVIEW.md)
to authenticate every reference before using the result for a human decision.
Owner decisions on P2-6/P2-7, HKSCS/ICU permission scope, source retention and
separate publication remain pending; browser/product acceptance remains #1400.
Stop for changed bytes, missing sources/notices, unresolved permission scope,
failed tests or stale review. Merge, release, deployment and rollback each remain
separate human decisions. No library upgrade or security clearance is implied.

Historical reports remain in Git history and their dated change packages; this
current inventory intentionally does not interleave obsolete blocker lists.
