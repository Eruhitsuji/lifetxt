# Source Code Form acquisition and delivery (#1409, #1411)

The five-file Pyodide 314.0.7 runtime is unchanged. Its bytes match the official
core release archive identified in source-lock.json. That release identifies
Pyodide commit b1e4fcc2488962f6360a97f19b9982d6fdb5d16f. This is an upstream
release/recipe relationship, not a bit-reproducible build or signed object map.

## Obtain sources and notices

In generated artifacts, open the **Source downloads** link in either checker
page, then the archive links in `sources/index.html`. The **Third-party notices**
link opens `notices/index.html`, which lists every retained notice and its known
component/version/section. Both indexes link each other. SHA256, versions and
required source/patch members are in `sources/source-lock.json`; the complete
567-file stdlib mapping and correspondence limits are in
`sources/source-provenance.json`. The exact shipped stdlib ZIP also contains
its Python source, including generated configuration.

In this repository, see [Pyodide MPL terms](https://github.com/Eruhitsuji/lifetxt/blob/main/contrib/browser_check_poc/notices/pyodide-314.0.7.txt),
[component inventory](https://github.com/Eruhitsuji/lifetxt/blob/main/contrib/browser_check_poc/notices/components.json), [notice provenance](https://github.com/Eruhitsuji/lifetxt/blob/main/contrib/browser_check_poc/notices/provenance.json),
and [source correspondence](source-provenance.json). These notice/template links open repository documentation; the generated indexes above provide local artifact navigation.

Pyodide and hiwire sources retain MPL-2.0 rights and terms. Other source archives
retain their own original per-file notices. No local runtime bytes or runtime
sources are modified. Upstream patches and build scripts remain in the complete
Pyodide/hiwire archives. Archive contents may include tests or alternative
implementations not linked into WASM; source presence is not binary inclusion.

日本語：日本語・英語のチェックページの「ソース取得」から、版・SHA256付きの
ソース一式を取得できます。「第三者ライセンス一覧」は全noticeへのリンクを含みます。
PyodideとhiwireはMPL-2.0、その他のソースは各アーカイブ内の条件に従います。

## Delivery modes and retention policy

- Development preview: default builds are offline and emit upstream acquisition
  links, lock, correspondence report and this document. These links are a
  development aid and **cannot satisfy the publication gate**. GitHub generated
  archives/tag URLs can change bytes or disappear; hash mismatch must fail.
- Publication candidate: `scripts/build_website_checker.py --publication-candidate
  --source-cache CACHE --output NEW_DIRECTORY` requires all ten verified archives
  and puts them beside the index on the same origin. Missing, partial, changed or
  unlisted payloads are rejected. The core binary archive is verification-only
  and is never offered as source. Builds perform no downloads.

For public distribution, the operator must retain the exact source archives,
lock, notices, correspondence report and manifest under Owner control for **at
least the entire period the corresponding binary is available**. Keep them
available with any retained older binary; do not replace their bytes under the
same version. If delivery fails, suspend binary availability until sources are
restored. Keep a backup of the verified bundle; never regenerate a changed
upstream archive and silently accept a new hash. The final review record requires
an Owner reference accepting this retention responsibility. No such commitment
or hosting operation is fabricated by this PR; approval remains pending.

This same-origin policy addresses this project's continuity risk. It is not a
claim that MPL universally requires self-hosting. Mozilla MPL 2.0 sections 3.1/3.2
and the official FAQ are interpretation references, not legal clearance:
https://www.mozilla.org/MPL/2.0/ and https://www.mozilla.org/en-US/MPL/2.0/FAQ/ .

## Correspondence and review limits

`source-provenance.json` distinguishes recipe SHA256 (CPython), Emscripten port
SHA512 (zlib/bzip2), recipe commit (hiwire/libffi), official-release source commit
(Pyodide), recipe version/tag (Emscripten), and recipe URL+version without an
upstream hash (xz/zstd/SQLite). The archive SHA256 recorded here binds the bytes
we retrieved; it cannot retroactively attest the inputs of an upstream build.
Actual WASM zstd/SQLite/UCD versions and mimalloc configuration are separately
probed. The xz mirror archive equals the official tukaani.org artifact retrieved
2026-10-25; this does not attest which bytes upstream used. liblzma's linked
version remains unavailable through the measured Python interface.

All nine CPython patches apply without fuzz; 535 stdlib files match CPython,
29 Pyodide, 2 patched CPython, and 1 generated sysconfig source matches a pinned
hash and inspected build constants. This does not map every WASM object. The
actual emsdk-used Emscripten commit and a bitwise rebuild remain unverified.

P2-6/P2-7 Owner decision is **pending**: the proposed evidence policy is to use
the official release identity, recipes, patch application, stdlib byte mapping
and measured runtime versions, explicitly accepting the remaining build-input
uncertainty. Alternatively commission a fixed-toolchain rebuild and compare
WASM bytes or exports/configuration. Neither option becomes “verified” by an
approval alone. Independent reviewers must assess the chosen evidence scope.

## Publication gate and independent re-review

`distribution_audit` covers both PoC and final checker outputs. A checker
manifest covers the entire site, including introduction assets, both checker
pages, runtime, Core ZIP, active assets, all notices, sources and provenance.
Allowlists and source-byte comparisons reject changes even after manifest
rehashing. Core ZIP is regenerated as a canonical uncompressed ZIP with fixed
metadata and compared in full, including its end-of-file bytes. Generated text
uses explicit UTF-8/LF, checkout attributes preserve source/snapshot bytes, and
manifest keys use POSIX-path order. The normal introduction-only build and Pages workflow remain separate.

`--require-publication` evaluates the data contract in `publication_gate.py`
instead of unconditionally failing. It requires the final checker profile,
verified same-origin source bundle, a clean checkout, exact reviewed commit and
manifest hash, all P1/P2 dispositions, independent implementation/distribution
and integration reviews, Owner residual-risk decisions, retention commitment,
and separate explicit Owner publication approval. Actual evidence is pending,
so `complete_distribution_audit=false` and `public_distribution_approved=false`.

Use an **external** JSON review record supplied by `--review-record FILE` after
review of the final commit and artifact. Keeping it outside the artifact avoids
a circular “commit a review → new unreviewed head” dependency. See
[the pending record template](https://github.com/Eruhitsuji/lifetxt/blob/main/contrib/browser_check_poc/publication-review.example.json). Do not change
repository/artifact bytes to fill that record: any source change requires a new
commit, build and review. Historical source inventories keep
their false snapshot fields; only the evaluated current audit report represents
the operative publication gate. Record authors and referenced decisions must be
verified by the human reviewer outside this offline validator. It checks evidence
shape/binding, not signatures or GitHub permissions, and cannot grant authority.

A successful gate is evidence for a human decision, not a deployment command.
Merge, #1400 product acceptance, publication and deployment retain their separate
Owner boundaries. This PR does not close #1398/#1400 or enable either flag.


## Second-review corrections and human boundary

The gate now accepts schema2 records only. All implementing AI tools are listed
and compared to this task's pinned tool inventory; reviewer tool names and GitHub
logins are case-insensitive, and evidence/reference fields must point to this
repository's GitHub issue/PR comments or reviews. This is **syntax checking**, not
proof of truthful authorship. The report always includes authority_verified=false
and human_reference_verification_required=true. A record's approval fields can
never replace the human checks in the
[publication review runbook](https://github.com/Eruhitsuji/lifetxt/blob/main/contrib/browser_check_poc/PUBLICATION_REVIEW.md).

Generated copies of this document and the notice README replace repository
`blob/main` links with the exact build commit; links in the source document are
ordinary repository navigation. No file embeds its own not-yet-created commit.

UCD3.2 legacy tables and non-Unicode CJK inputs are itemized separately in the
[mapping assessment](https://github.com/Eruhitsuji/lifetxt/blob/main/contrib/browser_check_poc/notices/mapping-attribution.json).
Original GB2312 and JIS X 0213 header terms are now retained. HKSCS permission
scope and the licence for the ICU grant applicability remain pending independent acceptance, explicit
publication blockers. Neither current Unicode V3 nor CPython's top-level terms
are claimed to clear those inputs. N-3 must have a source-specific documented
resolution or Owner judgment, verified independently before #1400 proceeds.


## #1413 source-specific permission follow-up

The official ICU data XML has now been located and byte-compared: it equals the
CPython XML except for one additional trailing LF in CPython. The repository's
licence scope declaration and complete grant (including original ICU terms)
are pinned, verified and retained as a notice. Independent applicability
acceptance is still pending, so N-7 remains fail-closed. HKSCS needs an actual
source-specific clarification/grant or a separately verified removal/replacement;
no written permission has been received. See
[permission evidence and next action](https://github.com/Eruhitsuji/lifetxt/blob/main/contrib/browser_check_poc/PERMISSION_RESOLUTION.md).
