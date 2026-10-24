# Source Code Form acquisition and delivery (#1409)

This local preview uses **unchanged bytes** from the five-file Pyodide 314.0.7
runtime. The npm files were byte-compared with the upstream core release archive
whose published SHA256 is retained in source-lock.json. The release identifies
commit b1e4fcc2488962f6360a97f19b9982d6fdb5d16f. This is a concrete upstream
release relationship, not proof of a bit-for-bit source rebuild or signed object map.

## Obtain Source Code Form

Open sources/index.html in the generated artifact. It links the exact source archives, versions,
SHA256 values and original licences. Pyodide and hiwire source is governed by
MPL-2.0; recipients retain the rights provided by that licence. A copy is in
[the notices](../notices/pyodide-314.0.7.txt). The other source archives preserve
their own copyright and licence terms. Source archives can contain test/tools or
alternative implementations that are not shipped in the WASM; their presence
must not be read as proof of binary inclusion.

日本語：ソース一覧から固定版のソースとライセンスを取得できます。Pyodideとhiwireは
MPL-2.0の対象です。他のソースは各アーカイブ内のライセンスに従います。

There are two explicit delivery modes:

- Default isolated build: fixed upstream acquisition links plus the complete
  source lock and this document. Each archive was retrieved and hash-checked
  during this investigation. Hosting continuity remains an operator responsibility.
- `build.py --source-cache CACHE`: all ten source archives are verified offline
  and copied next to this document. The index links those local files. The upstream
  binary release archive is a verification input and is never shipped as source.

A self-hosted source bundle is an operational choice, not a claim that MPL always
requires self-hosting. Mozilla MPL 2.0 sections 3.1/3.2 require availability of the
covered Source Code Form and notification of acquisition terms/location:
https://www.mozilla.org/MPL/2.0/ and https://www.mozilla.org/en-US/MPL/2.0/FAQ/ .
This inventory does not issue a legal adequacy determination.

## Build relationship and modifications

Pyodide's source archive retains Makefile.envs, cpython/Makefile, Setup.local,
the CPython patches and build scripts. hiwire's archive retains its source,
Makefile and upstream patches. CPython is the recipe-pinned original 3.14.2
archive. Emscripten and the port/library source archives retain vendored runtime
code and notices; zlib's overwritten zconf.h is in Emscripten's source archive.
The zlib and bzip2 archive SHA512s also match the respective Emscripten port pins.
No local runtime source patches or runtime file removals are made by lifetxt.
Do not mistake that for an assertion that upstream binaries have no patches.

## Gates still open

Complete WASM linked-object attribution, generated-build details, Unicode data
licensing scope and independent distribution evaluation remain review items.
A retained upstream source archive and a licence text are evidence, not automatic
publication approval. The audit keeps complete_distribution_audit=false and
public_distribution_approved=false. The official website and Pages workflow do
not publish this local PoC. #1398/#1400 retain the publication decision.
