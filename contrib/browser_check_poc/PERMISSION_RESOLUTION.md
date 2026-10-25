# Source-specific permission investigation — #1413

Current direction (#1417): HKSCS removal is implemented in the fixed custom candidate and complete local checker profile. The enquiry draft is historical and unsent. ICU byte/grant evidence is rechecked against curated CPython; independent applicability/distribution acceptance is still pending. See DISTRIBUTION_REMAINING.md.


Baseline: main 946d8c0402804856c8d71b61b918c1c9af9ccdef, Pyodide314.0.7,
CPython3.14.2 source archive SHA256
c609e078adab90e2c6bacb6afafacd5eaf60cd94cf670f1e159565725fcd448d.
This is evidence for independent acceptance, not a newly obtained licence,
legal opinion or public-release approval. Both actual flags remain false.

## ICU: source-specific grant located

The earlier assertion that no applicable licence had been located is superseded
by this investigation. The exact official ICU data repository at commit
`bae5ca647fa41703393dbf00240ec1b807a9c353` contains all of:

- `charset/data/xml/gb-18030-2000.xml`: 845974 bytes, SHA256
  a0eccd5460cff9d5ea32194369971286c11af80fb1b09c4d9d77ff046e22b5cc.
- `README.md`: SHA256 ec67319a4c85e3b38534b84ec5732c48421adfa239e3f9edc76e72a35ef563a8;
  identifies charset as character-set mapping data and explicitly releases the
  repository contents under its LICENSE.
- `charset/readme.txt`: SHA256 e87d028fcc8c29c073ce9f0747d473e3697783670d4aeae964897decd8830615;
  describes the mapping data and known format limitations, with no additional
  licence restriction identified there.
- `LICENSE`: 5131 bytes, SHA256
  f72db45707e93c90c4bf400edfa5d38ce44fe692789e385548e627459c1bf6c9;
  contains Unicode V3 and the retained original ICU1.8.1–57.1 copyright/permission
  notice. The full original bytes are now shipped as a third-party notice.

The CPython member `Tools/unicode/python-mappings/gb-18030-2000.xml` is 845975
bytes, SHA256 47350d44c6db23e0f0c9e9f4a1bf2e966369f52357fd01425bc06b9aaf83f943.
It equals the pinned official ICU XML **plus exactly one LF byte at EOF**.
No XML element, mapping, comment, encoding or other byte differs. This narrowly
recorded transformation is tested; arbitrary whitespace/content changes fail.

Thus the proposed applicability basis is the official grant for this specific
same mapping dataset, not a current unrelated ICU software licence. Original
ICU terms permit modification/distribution subject to notice/documentation
conditions. The combined upstream grant is retained whole, and the generated
notice index makes it reachable with the identified component. Distribution
acceptance still requires an independent reviewer to check the source binding,
scope declaration, any applicable exceptions, and fulfilment of those terms.
No independent acceptance link is invented. N-7 continues to block this input
until a valid source-specific resolution record has been reviewed and retained.

Pinned primary references:

- https://github.com/unicode-org/icu-data/blob/bae5ca647fa41703393dbf00240ec1b807a9c353/README.md
- https://github.com/unicode-org/icu-data/blob/bae5ca647fa41703393dbf00240ec1b807a9c353/LICENSE
- https://github.com/unicode-org/icu-data/blob/bae5ca647fa41703393dbf00240ec1b807a9c353/charset/data/xml/gb-18030-2000.xml
- https://github.com/unicode-org/icu-data/blob/bae5ca647fa41703393dbf00240ec1b807a9c353/charset/readme.txt

## HKSCS: actual additional permission has not been received

CPython's exact `genmap_tchinese.py` names the HKSARG HKSCS-2004 input and calls
its licence restrictive. The official terms reviewed on 2026-10-25 contain a
restriction on adaptation/distribution (clause5) and a limited complete,
unmodified distribution permission with conditions (clause15). No text found
in this investigation clearly extends that exception to generating, compiling
and redistributing the adapted CPython mapping tables in this WASM product.
This is an unresolved applicability question, not a conclusion that all use of
HKSCS or all CPython distributions is prohibited.

The following do not supply that missing grant: the Owner's risk acceptance,
top-level PSF/Unicode terms, other products shipping a codec, or a similar IBM/
ICU table under another licence. The ICU repository's IBM1375:2004 UCM was
examined as an alternative, but similarity of mappings is not proof that the
rights in the original HKSARG-derived table have changed. No relicensing or
runtime substitution is claimed.

Official recipient verified from the Digital Policy Office's **CCLI-specific**
contact page: Common Chinese Language Interface Support Team,
`clis@digitalpolicy.gov.hk` (not the unrelated CCLI music service, not the
character-inclusion mailbox and not an inferred personal address).

- Terms: https://www.ccli.gov.hk/en/archive/terms_hkscs-2004-big5-iso.html
- Official contact: https://www.digitalpolicy.gov.hk/en/our_work/data_governance/policies_standards/ccli/contact/

The primary pages were read via web retrieval. Direct HTTP requests in this
execution environment returned interstitial HTML without the terms/contact
content; those responses are **not** retained as authoritative evidence.
No raw HKSARG mapping file was downloaded or redistributed during this task.
[The exact proposed enquiry](HKSCS_PERMISSION_REQUEST.md) is ready for review
and explicit send authorization. It has not been sent and no reply is claimed.

## Removal/replacement fallback if a grant is unavailable

A valid technical alternative is a separately reviewed custom runtime build:
remove `_codecs_hk` and its generated HKSCS tables from the CPython build recipe,
remove/adjust `big5hkscs` stdlib registration, and ensure corresponding shipped
source archives also exclude the affected generated tables. Merely disabling a
UI option, deleting Python wrappers, removing an export, or stripping a symbol
name does not remove the data from WASM and does not resolve this issue.

That alternative needs a pinned toolchain/build recipe, new runtime/source
hashes, verified object/data absence, updated notices/provenance, all native/WASM
parser fixtures and browser checks, plus fresh independent distribution review.
The product accepts UTF-8 text, but that fact alone is not proof a runtime
rebuild has no indirect effect. No existing runtime byte, ABI or source bundle
has been changed under the guise of a licence-status update. If clarification
is refused or unavailable, use a dedicated build task rather than marking the
current runtime resolved.

## Reproduce the ICU evidence without executing fetched code

```sh
python -m contrib.browser_check_poc.permission_probe fetch --cache CACHE
python -m contrib.browser_check_poc.permission_probe verify --cache CACHE --source-cache LOCKED_SOURCE_CACHE
```

The first command explicitly downloads four fixed raw GitHub files with locked
revision, size and SHA256; it rejects redirects/changed bytes and does not replace
existing files. The second is offline and verifies those inputs, the pinned
CPython source/member, the single-LF correspondence, official scope statement,
and exact shipped licence. It prints pending independent acceptance and false
public flags. Neither command sends messages, requests permissions from others,
changes the licence gate or publishes anything.
