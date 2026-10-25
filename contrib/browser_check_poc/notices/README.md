# Runtime notice snapshots — independent acceptance pending

The current inventory contains **29 notice documents** (including the original GB2312/JIS X 0213 headers, UCD3.2 release ReadMe and complete official ICU data licence). Original source
URLs, retrieval details, hashes and selection/normalization are recorded in
[provenance.json](provenance.json). [components.json](components.json) maps known
components/versions to the applicable documents and, where relevant, sections.
The CPython incorporated-software list is explicitly incomplete upstream.

The generated **Third-party notices** page, `notices/index.html`, links every
retained document, component metadata and source downloads. Both checker pages
and the generated source index link that page. In this repository, see
[delivery and evidence limits](https://github.com/Eruhitsuji/lifetxt/blob/main/contrib/browser_check_poc/SOURCE_DELIVERY.md) and
[the runtime inventory](https://github.com/Eruhitsuji/lifetxt/blob/main/contrib/browser_check_poc/RUNTIME_INVENTORY.md); there is no generated index
in the source tree.

Unicode License V3 was retrieved unchanged from the official Unicode site on
2026-10-25 (its current copyright range is 1991–2026). The original UCD16 ReadMe
retains its 2024 copyright and terms reference. The Unicode scope includes UCD16 and legacy UCD3.2 tables and identified Unicode MAPPINGS inputs. CJK tables also use HKSCS, historical ICU, JIS X 0213 and GB2312 sources; [mapping attribution](mapping-attribution.json) distinguishes their terms and open permission questions. This is not a new provenance claim for every individual
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


The official ICU data repository's complete licence is now retained, including
original ICU1.8.1–57.1 terms. Exact XML/source correspondence and its limited
single-LF transformation are recorded in mapping-attribution.json. This is a
source-specific grant candidate pending independent acceptance, not a grant
for HKSARG material. HKSCS remains unresolved and no enquiry has been sent.
