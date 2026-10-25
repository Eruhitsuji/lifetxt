# Distribution readiness and remaining work (#1417)

This is a readiness ledger, not publication approval. Implementation merge,
byte integrity, independent distribution acceptance and deployment are distinct.
The current public Pages build remains introduction-only.

| Requirement | Implemented / observed | Remaining acceptance |
| --- | --- | --- |
| Unicode and source-specific CJK notices | Original notices, UCD16/UCD3.2 attribution and exact ICU data grant retained by #1412/#1414 | Independent applicability assessment of the exact ICU input and complete notice scope |
| HKSCS removal | #1416 built and executed the fixed variant; this profile delivers curated CPython and no HKSCS builtin/object/wrapper/aliases | Independent acceptance of removal proof and final custom distribution |
| Corresponding source | Ten same-origin archives; modified Pyodide/MPL sources and helper MIT notice; curated CPython; exact Core/stdlib source | Verify existing Owner retention commitment against the exact published bundle and retain it throughout binary availability |
| Whole checker integrity | Explicit custom profile pins all runtime/source/notice/Core/UI bytes; rehashing changed assets cannot bless them | Final-head independent implementation/distribution and integration review |
| Local product browser acceptance | Recorded Linux Chromium153 JA/EN, 16KiB boundaries, Unicode, repeated checks, worker cancellation/retry/timeout, network/storage checks | Human acceptance of the bounded evidence; physical devices, other browsers, OS peak memory and public Pages remain unverified |
| Publication and deployment | Existing manual Pages/human approval boundaries preserved | Separate Owner go-live decision and #1400 implementation/approval, then actual public-delivery smoke |

## Existing decisions

Owner selected HKSCS removal rather than permission enquiry. The prepared enquiry
is historical and unsent; no external email is authorized by this work. Existing
Owner scope, residual-risk and source-retention decisions recorded in #1398 are
not discarded. They must be applied to the actual custom artifact without
relabeling unverified correspondence or licence applicability as verified.

ICU evidence in #1414 is useful after HKSCS removal because the remaining
GB18030/ICU-derived table is still included. Removal does not waive that separate
licence assessment. Neither a merge nor a synthetic offline approval record is
proof that an independent evaluator has accepted the grant or the final bytes.

## Review handoff

Review the final PR for #1417 at its exact current head. Check the retained
custom source lock, modified source archives, original/helper notices, measured
runtime hashes and source/object checks, actual final checker/browser evidence,
negative mutations, and the pending source-specific statuses. Confirm all
references and reviewer identities manually according to PUBLICATION_REVIEW.md.
Any later push invalidates a review tied to the previous head.

The evaluator remains fail-closed for actual pending HKSCS-removal and ICU
acceptance, even with an otherwise-valid Owner/review claim. Both actual flags
remain false until a reviewed evidence change legitimately clears all gates;
that change itself still does not authorize deployment.

## Publication sequence after acceptance

1. Independently review/accept the custom distribution, source-specific terms,
   retained-source plan and bounded browser results; resolve findings in a PR.
2. Bind any approval record to the exact source head and complete manifest.
   Run the custom audit with --require-publication; do not substitute the legacy
   official-runtime profile or remove its blockers.
3. Complete #1400's separately reviewed Pages integration and JA/EN discovery links using the explicit
   custom profile. Keep introduction pages no-script, checker-only CSP/Worker,
   manual workflow_dispatch and human environment approval. Confirm MIME, paths,
   immutable artifact/revision and a rollback revision before publication.
4. Owner explicitly authorizes and performs publication/deployment. Then inspect
   the actual public delivery, source/notice links and minimal checker smoke;
   record failures or rollback instead of calling a local run live acceptance.

Merged child implementations #1414/#1416 are recorded as merged milestones.
Their open acceptance/review work stays visible in #1398/#1400; this ledger does
not fabricate a review, close unresolved Issues, change flags or deploy.
