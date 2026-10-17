# Runtime distribution inventory — #1362, 2026-10-17

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
