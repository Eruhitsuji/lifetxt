# Runtime distribution inventory — #1362, 2026-10-17

The current #1411 disposition is at the end of this document; earlier dated sections are historical evidence.

This is an incremental source-based candidate inventory, **not a complete SBOM,
legal clearance, publication approval or reproducible-build attestation**.
The five-file runtime is hash-bound in `notices/components.json`.
`complete_distribution_audit=false` and `public_distribution_approved=false`
remain enforced. #1358 owns distribution/adoption gates.

Sixteen upstream notice texts (the original three plus thirteen additions),
source URLs, stored SHA-256 and normalization/selection instructions are in
`notices/provenance.json`. All sixteen, provenance, components and notice README
enter the isolated artifact and its manifest. Before creating output, the builder
validates notice hashes/references and all five runtime hashes. This prevents
silently reusing this inventory for other binaries, not incomplete attribution.

Pyodide tag `314.0.7` resolves to `b1e4fcc2488962f6360a97f19b9982d6fdb5d16f`.
Its [CPython recipe](https://github.com/pyodide/pyodide/blob/b1e4fcc2488962f6360a97f19b9982d6fdb5d16f/cpython/Makefile),
[link flags](https://github.com/pyodide/pyodide/blob/b1e4fcc2488962f6360a97f19b9982d6fdb5d16f/Makefile.envs)
and Emscripten 5.0.3 port recipes identify the following candidates. Recipe pins
are not a signed claim about the npm binary's build.

| Component | Identified version/source | Evidence and retained notice |
| --- | --- | --- |
| Pyodide / CPython | 314.0.7 / 3.14.2 | Runtime versions; MPL/combined CPython notices |
| Emscripten | 5.0.3 | Tagged build pin only; MIT/NCSA |
| libffi | f08493d249d2067c8b3207ba46693dd858f95db3 | Recipe pin, `_ctypes` imports; MIT |
| hiwire | 6a1e67280a15d929ebeceee54a6358c9c8d5f697 | Recipe pin; MPL |
| liblzma / XZ | 5.2.2 | Recipe archive, `_lzma` imports; COPYING summary |
| zstd | 1.5.7 | Recipe archive, `_zstd` imports; BSD |
| SQLite | 3.39.0 | Runtime and recipe agree; public-domain disclaimer |
| zlib | 1.3.1 | Runtime and port agree; README with Zlib notice |
| bzip2 | 1.0.6 | Port recipe, `_bz2` imports; bzip2 notice |
| Expat | 2.7.3 | Runtime version; CPython vendored COPYING |
| stackframe / error-stack-parser | Pyodide vendored subtree | compat.ts imports it; MIT |
| MiniLZ4 | Emscripten vendored JavaScript | LZ4 build flag; complete leading MIT comment |
| musl / libc++ | Emscripten vendored subtrees | COPYRIGHT/libc++ licence; per-object map unverified |
| HACL* | CPython vendored subtree | Setup.local and hash builtins; one complete representative licence header, not all files |
| Other CPython/LLVM pieces | Not exhaustively mapped | Explicit gap, not implicitly covered by top-level notices |

The runtime declares 91 builtins; `_bz2`, `_lzma`, `_ctypes`, `_zstd` imports
succeed. Import success does **not** establish linked-library versions: only
zlib, SQLite and Expat exposed the version values measured here. The parser need
not use all modules, but the whole WASM/stdlib ZIP is distributed. Conversely,
the package index lists available wheels, not proof those wheels are shipped.

## Reproduce

```sh
npm ci --prefix contrib/browser_check_poc --ignore-scripts
python contrib/browser_check_poc/build.py --output .cache/inventory-site
node contrib/browser_check_poc/inventory_probe.mjs .cache/inventory-site .cache/inventory-observed.json
python -m unittest tests.test_browser_check_poc
```

The Node probe validates manifest runtime hashes and emits measured versions and
builtins, not browser acceptance or a full SBOM. Compare its output with retained
`notices/components.json`. Do not change hashes simply to accept unexpected bytes.
Intentional upgrades require renewed source/notice review. Snapshots normalize
LF and trailing whitespace; MiniLZ4/HACL retain the complete leading licence
comment only. Zlib README is retained whole to preserve notice context.

## Remaining publication blockers

1. Finish file/object-level attribution, including other CPython code/data,
   Unicode data, decimal code and LLVM compiler-rt/libunwind. One HACL header
   does not cover all HACL/KreMLin/per-file notices.
2. Map exact shipped npm binary build, patches, source revisions and linked
   objects. Recipe pins and runtime version strings cannot attest the full build.
3. Review corresponding-source delivery for Pyodide **and hiwire** MPL portions,
   including modifications, against the actual artifact. Source URLs alone
   are not a compliance conclusion.
4. Independent distribution/legal review and Owner adoption/publication approval.
   Browser and physical-device gates remain separate.

No product dependency, parser behavior, website, workflow, Settings or deployment
changed. Inventory checks are local and use no user records.

## #1398 distribution audit (2026-10-24)

The isolated builder now audits its finished artifact. Run independently:

```sh
python -m contrib.browser_check_poc.distribution_audit .cache/inventory-site
python -m contrib.browser_check_poc.distribution_audit .cache/inventory-site --require-publication
```

The first command verifies integrity and emits JSON. It may succeed while
`publication=blocked`: **integrity is not licence clearance**. The second command
always exits nonzero with the present incomplete inventory. No website build or
Pages workflow calls or bundles this experimental artifact.

The audit binds the entire manifest, a fixed file allowlist, the five runtime
byte hashes, exact npm lock digest and package pin, notices/provenance, original
UI/Worker/adapter bytes, and all twenty unchanged Core sources plus MIT LICENSE
inside Core ZIP. Extra files, symlinks, missing files and altered assets fail,
even if their manifest hashes are rewritten. The manifest is a local integrity
record, not a signature against an attacker editing both source and policy.
Core ZIP hashes change when upstream Core changes and require renewed review.

### Artifact / source / attribution disposition

| Shipped object | Source basis / retained notice | Current disposition |
| --- | --- | --- |
| `pyodide.mjs` | pinned Pyodide commit above; MPL; stackframe notice | Unchanged from hash-bound npm bytes. Full corresponding source archive and applied patch correspondence **not provided/verified**. |
| `pyodide.asm.mjs` | Pyodide, Emscripten, MiniLZ4; recipe references above | Generated glue; exact build/source map **unverified**. |
| `pyodide.asm.wasm` | CPython, hiwire, libffi, zlib, SQLite, XZ, zstd, bzip2, Expat, HACL, musl, libc++ candidates in `components.json` | Runtime/recipe evidence is partial; per-object mapping, other LLVM/CPython data and patches **unverified**. No unnecessary-module removal performed. |
| `python_stdlib.zip` | CPython 3.14.2 combined licence; exact ZIP bytes pinned | Whole shipped archive counts, including parser-unused contents. Full per-file/code/data attribution **incomplete**. |
| `pyodide-lock.json` | pinned runtime package index | Describes optional wheels; not proof those wheels are shipped. No auto-download of optional packages is introduced. |
| `core.zip` | original twenty project modules + project MIT LICENSE | Exact archive membership and unchanged source bytes verified by audit. No CLI/API/Remote modules added. |
| UI / Worker / adapter / fixtures | repository MIT sources | Copied from source; active assets byte-compared. Synthetic fixture expectations generated by native parser. |

For MPL Pyodide **and hiwire**, the operator must obtain and retain the exact
corresponding source, applicable modifications/build patches and licence texts,
provide a durable acquisition mechanism to recipients, and have an independent
distribution evaluator accept the binary/source relationship and delivery notice.
The references in `components.json` identify candidates; this change does not
claim that a URL or recipe alone fulfils those obligations. Fixed source archives and an offline self-hosting mode are now implemented by
#1409; their recipe/release relationship is recorded in source-provenance.json.
Independent acceptance of that evidence and full object-level attribution remain open.
This is a **publication blocker**, not a legal adequacy determination.

### Upgrade / stop / rollback

Never edit a hash just to accept unexplained bytes. An intentional upgrade must
review package/lock/integrity/version, all five actual runtime files, whole-archive
attribution, notices, source delivery and synthetic/native/browser checks, then
update the audit policy in a reviewed PR. There is no CDN/latest fallback.
Stop publication for any unknown attribution, missing corresponding source,
changed byte, failed check or stale independent review. Keep the prior reviewed
revision, manifest and immutable artifact; deployment/rollback remains a separate
Owner operation. Until distribution review and source gates are complete, keep
`complete_distribution_audit=false` and `public_distribution_approved=false`.


## #1409 source acquisition and evidence (2026-10-24)

`source-lock.json` fixes ten complete source archives (76,504,570 bytes) plus
an official core release archive used only for verification. The release
SHA256 matches GitHub's published digest and its five named runtime files are
byte-identical to the shipped npm files. No local runtime bytes were modified.
The release points to the retained Pyodide commit; this establishes a concrete
upstream release/recipe relationship, not a signed build or reproducible-build proof.

`source-provenance.json` records clean application of all nine CPython patches,
the recipe SHA256 for CPython, matching Emscripten SHA512 pins for zlib/bzip2,
and mappings for all 567 regular files in python_stdlib.zip: 535 unchanged
CPython sources, 29 exact Pyodide sources, 2 CPython files matching upstream
patches, and 1 generated sysconfig module already shipped as Python source.

The notice inventory now contains 23 texts: the original sixteen plus the whole
CPython incorporated-software licence document, all distinct leading copyright/
licence comments found in 40 HACL and 41 decimal source/header files, and four
LLVM runtime subtree licence documents. This does not establish that every
source file in those archives is linked into the binary. Original per-file
notices remain inside the full source archives. Unicode data licensing and the
complete WASM linked-object attribution still need independent evaluation.

Generated `sources/index.html` provides fixed upstream acquisition links by
default. `--source-cache CACHE` instead verifies all ten source archives offline
and copies them into that directory. Partial source bundles, missing licence/
patch members, corrupted payloads, changed metadata, extra source files and
symlinks fail. CLI `source_delivery fetch` is an explicit maintainer download;
build and Worker never download these archives automatically. The local-only
checker builder forwards this option and copies the source directory. Production
introduction build and Pages workflow still do not distribute the checker.

Full procedure and boundaries: [SOURCE_DELIVERY.md](SOURCE_DELIVERY.md).
`complete_distribution_audit` and `public_distribution_approved` remain false.
Independent distribution and integration review, source-hosting continuity and
Owner publication approval are separate gates under #1398/#1400.


## #1411 review remediation (2026-10-25, current disposition)

The notice inventory now has 25 documents, all reachable from generated
`notices/index.html`, both checker pages and the source index. Unicode License
V3 and original UCD16 ReadMe retain official bytes/hash/date; components include
UCD-derived tables and unicode.org mapping-derived codecs. Retained source
archives preserve other per-file terms. Historical statements above about
missing sources, one representative HACL notice or unmeasured zstd are superseded
by the bounded results below; they are not current missing-work claims.

| Additional component/evidence | Retained terms / limit |
| --- | --- |
| Unicode Character Database 16.0.0 derived tables | Unicode License V3 + original UCD16 ReadMe; runtime UCD16 observed |
| unicode.org mapping-derived encodings/CJK tables | Unicode License V3; per-input attribution scope awaits independent acceptance |
| mimalloc | CPython incorporated-software notice, mimalloc section; actual WITH_MIMALLOC=1 |
| SipHash24 | Same notice, SipHash24 section; source-level component, no per-object attribution |
| strtod/dtoa | Same notice, strtod/dtoa section; source-level component |
| Mersenne Twister | Same notice, Mersenne Twister section; _random builtin observed |
| zstd 1.5.7 / SQLite 3.39.0 | Runtime versions match recipe versions; recipe has no archive hash |
| xz 5.2.2 archive | Mirror bytes equal official tukaani.org bytes; actual linked version not measured |

`source-provenance.json` now distinguishes the correspondence basis of all 11
archives. Actual runtime observations are reproducible via runtime_probe.mjs.
All nine patches and all 567 stdlib files remain checked; generated sysconfig
classification additionally requires its exact SHA256 and inspected constants.
Full object mapping, bitwise reproducibility and the actual emsdk Emscripten
commit are **unverified**, not facts established by an Owner acceptance.

The final website checker now has a whole-site manifest and fixed-source audit.
Publication candidates require all ten sources on the same origin. Owner source
retention responsibility covers the entire binary-distribution period; acceptance
is pending. Link mode remains a blocked development aid.

The data-driven publication gate checks final-head independent review and
artifact identity with P1/P2 dispositions and separate Owner approval. Synthetic
positive tests demonstrate evaluation only, never actual approval. Both actual
flags stay false. See [SOURCE_DELIVERY.md](SOURCE_DELIVERY.md) for current
commands, evidence limits and pending P2-6/P2-7 decisions. #1398 and #1400 remain
blocked until final-head independent re-review and the required Owner decisions.
