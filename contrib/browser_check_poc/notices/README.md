# Runtime notice snapshots — independent acceptance pending

The current inventory contains **25 notice documents** (23 preceding #1411,
plus the full official Unicode License V3 and UCD 16.0.0 ReadMe). Original source
URLs, retrieval details, hashes and selection/normalization are recorded in
[provenance.json](provenance.json). [components.json](components.json) maps known
components/versions to the applicable documents and, where relevant, sections.
The CPython incorporated-software list is explicitly incomplete upstream.

The generated **Third-party notices** page, `notices/index.html`, links every
retained document, component metadata and source downloads. Both checker pages
and the generated source index link that page. In this repository, see
[delivery and evidence limits](../SOURCE_DELIVERY.md) and
[the runtime inventory](../RUNTIME_INVENTORY.md); there is no generated index
in the source tree.

Unicode License V3 was retrieved unchanged from the official Unicode site on
2026-10-25 (its current copyright range is 1991–2026). The original UCD16 ReadMe
retains its 2024 copyright and terms reference. The scope includes UCD16-derived
CPython character/name/type tables, unicode.org mapping-derived encodings and
CJK generated tables. This is not a new provenance claim for every individual
mapping input; independent scope/attribution assessment remains required.

The complete CPython software notice document covers mimalloc, SipHash24,
strtod/dtoa and Mersenne Twister. HACL/decimal aggregates retain all distinct
leading licence comments found in the checked 40/41 source/header files. Full
archives preserve other inline/per-file terms. LLVM runtime subtree licences
are retained whole; their presence does not map every linked object.

The Core ZIP contains unchanged lifetxt sources and its MIT LICENSE. Optional
wheels listed in pyodide-lock.json are not downloaded or shipped by this build.
These notices and source archives are technical evidence, not legal clearance
or publication approval. Both status snapshot flags remain false.
