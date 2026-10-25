# Technical review of #1409 / #1411 / #1413 / #1415 / #1417

Review baseline: main 197583c88072b37cbc27ce198bbbb1b483c374ed, 2026-10-25 JST.
Reviewer: Codex, current review session. This is a fresh technical inspection
of the merged implementations and retained evidence. Original implementer was
also Codex. Consequently this is **not** the separate-tool/human final acceptance
required by publication_gate.py and PUBLICATION_REVIEW.md. The correction in
#1421 is now implemented by this reviewer and needs another reviewer. No GitHub
Approve, accepted mapping resolution, human decision or deployment is claimed.

## Per-Issue result and close conditions

| Issue | Acceptance coverage inspected | Technical result | Close condition |
| --- | --- | --- | --- |
| #1409 | Official release/5 runtime byte identity; eleven fixed upstream downloads, ten delivered sources; nine patches; stdlib source mapping; notices and source links; offline builds; altered/missing/extra files and false gates | No new source-delivery defect found. Full fixed-source audit re-executed and reproduced source-provenance.json, including all nine patches and 567 stdlib entries. | Implementation complete, but original independent distribution/retention acceptance is still pending in #1398. Owner may close the implementation scope only with that remaining acceptance explicitly retained in the parent. |
| #1411 | P1-1..4 notice/source/artifact requirements; P2-5..8 evidence/limitations/gate; P3-9..11 portability/links/sysconfig; N-1..7 follow-up fixes | Rehashed synthetic mutations rejected, LF/cp932 simulation and Core ZIP full-byte comparison pass; source-specific mapping blockers remain effective even with otherwise-valid claims; no new finding in this remediation scope. Read prior Claude reviews and N-7 correction separately from current checks. | Technical remediation complete. Final exact-head/manifest review, source retention and Owner dispositions remain #1398/#1400 requirements; this Codex pass cannot populate their independent accepted reviews. |
| #1413 | Fixed ICU revision/terms/XML and shipped notice; original input hash; source-specific uncertainty; HKSCS enquiry versus removal path | Fresh official ICU files and original CPython were hash checked. CPython XML is exactly ICU XML plus one LF. Original Unicode/ICU grant is included whole and linked. Pinned upstream README explicitly identifies licence scope; no new permission was obtained. HKSCS remains removal direction under #1415/#1417, not a claimed HKSARG grant. | Investigation implementation complete. Source-specific applicability acceptance and exact custom distribution remain parent gates. Do not close as permission received or legally certified. |
| #1415 | Seven source removals, aliases and disabled builtin; fixed staging; source/object/library/config/stdlib checks; actual WASM/codec fixtures in retained evidence | P2 R-1: standalone verifier trusted workspace receipts and curated input without reconstruction from locked upstream. Fixed in #1421; real upstream reconstruction matches both retained profile/removal receipts exactly. Original build/object/WASM/browser logs were inspected, not re-executed here. | Merge/review #1421 and repeat source/object verification on retained build tree; independent removal acceptance remains #1398. No close before the correction is integrated. |
| #1417 | Explicit custom runtime; fixed five bytes; ten derived sources including modified MPL source/helper MIT notice; complete artifact allowlist and original-byte checks; actual pending data and fail-closed gate | Synthetic mutations/proof drift/missing-source/old-runtime rejection pass. Fixed source/object/runtime/ICU receipts cross-bind; recorded JA/EN browser, 27 Node cases and 30 repeats inspected as historical evidence. R-1 affects its removal-evidence producer. | Merge/review #1421, rebuild the final custom artifact at the resulting head and review that exact manifest with retained custom runtime. Final independent distribution/integration acceptance, retention and public approval stay in #1398/#1400. |

## R-1 (P2): source evidence producer can trust a self-consistent changed input

Before the fix, verify() read build-profile.json and source-removal.json from the
workspace. It compared four build files to the profile's hashes, the curated
archive to the removal receipt's hash, then reconstructed compiler sources from
that same curated archive. It never reconstructed the curated archive or staged
build inputs from locked upstream CPython/Pyodide. A changed source plus matching
receipt/hash could describe an unpinned build. The separate final distribution
lock already rejects different pinned runtime/source bytes; no publication bypass
was demonstrated. This is a trust-boundary defect in standalone evidence.

Correction: verify_staging() calls the existing hash-locked staging generator
in a new temporary directory. It compares both complete receipt objects, the
curated archive digest and the four actual changed build inputs before any
runtime read or llvm-ar invocation. No runtime/source lock or public flag changes.

New negative regression uses real curation/staging on synthetic pinned archives:
original accepted; changed receipt, curated archive plus both receipt hashes,
compiler input plus profile hash and absent upstream archive are rejected.
Fresh real upstream staging also matches the retained fixed profile/removal
receipts exactly. A preliminary synthetic fixture lacked tools/; it failed
before reaching the assertion, was corrected, then all five subcases passed.

## Executed versus historical evidence

Fresh: 83 related tests collected, 80 passed and 3 skipped; full official source
comparison with all eleven archives and five official runtime files; four ICU
inputs plus CPython XML/notice correspondence; real fixed staging reconstruction;
all ten derived custom archives regenerated and matched the fixed lock; ICU
comparison repeated against curated CPython; ruff on contrib/browser_check_poc,
lifetxt, tests and scripts; format/diff checks.
The first baseline run had 82 tests and 5 skips; acquiring sources enabled two
previously skipped actual-source/ICU checks. This is not 83 successful executions.

Skipped: two actual-custom-artifact tests (candidate bytes unavailable), plus
the Node/default website test expecting its preconfigured npm runtime location.
The official runtime was independently extracted for the source audit, but was
not substituted for the custom candidate. Fresh custom WASM/object/browser tests
were not executed. Original recorded source/object/Node/Chromium successes and
build logs were inspected as historical evidence only. No physical device,
Windows, Safari/Firefox, cross-host binary or live Pages acceptance is claimed.

The source fetch was read-only. A redundant concurrent subset download collided
with an already-created cache file and refused overwrite; the full fetch then
completed and the cache passed the complete audit. This harness race is not a
product defect and no partial download was accepted as valid source.

## Closeout disposition

Keep the original five Issues open for now with these explicit per-Issue
conditions. This avoids representing this same-tool technical review as the
separate final acceptance their contracts request. All implementable correction
work is in #1421; final review/merge is the remaining PR boundary. After that,
#1409/#1411/#1413 can be closed as implementation/investigation tasks while
retaining the specified parent acceptance gates, and #1415/#1417 can be closed
when the retained-build/final-manifest rechecks and separate review are recorded.
Neither issue closeout nor a merge grants publication.
