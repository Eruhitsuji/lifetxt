# Decisions and limits

2026-10-25 Owner requested all review fixes, self-review and PR. #1411 is the
ready child implementation contract; #1398/#1400 publication dependencies remain
blocked. The review input targets main 372ddca1 and is retained at
https://github.com/Eruhitsuji/lifetxt/issues/1398#issuecomment-6386098797 .

P1-4: choose same-origin source bundles for all publication candidates rather
than claiming upstream generated archive permanence. A retention policy and
required Owner evidence are implemented, but no Owner retention commitment,
hosting acceptance or publication authorization is fabricated.

P2-6: local hashes bind our retrieved archives. They do not prove what upstream
compiled when its recipe lacked a hash. Actual zstd/SQLite observations and
xz official-byte equality strengthen the recorded scope; linked liblzma version
and upstream input-byte identity remain unverified. Owner judgment is pending.

P2-7: recommend official release byte identity + recipes + patch application +
stdlib mapping + runtime observations as the bounded evidence policy, with
remaining input/rebuild uncertainty recorded. A fixed-toolchain rebuild is the
alternative. Neither an acceptance nor this implementation makes unperformed
rebuilds or emsdk commit mapping verified. Independent review and Owner decision
remain pending in the template and final report.

P2-8: final review records remain outside the artifact, bound to current commit
and manifest; review authentication is a human responsibility. Actual pending
record never passes. Positive test data are explicitly synthetic.

P3-9: the Windows path failure originates in scripts/check_website.py using
str(relative_path) while expected HTML paths use slash separators. Change to
as_posix; this is an offline validator fix, not a production renderer/workflow
change. Extend the task write scope accordingly; same reviewed defect class.

Unicode current official License V3 bytes and UCD16 ReadMe were retrieved
2026-10-25, retaining their original copyright ranges and hashes. The historic
mapping-input scope is documented for independent evaluation; no blanket legal
sufficiency determination is made. No dependency upgrade or security acceptance
of the legacy runtime libraries is implied by licence remediation.


## Second independent review (2026-10-25)

Input: https://github.com/Eruhitsuji/lifetxt/pull/1412#issuecomment-6390737165
(target 499c164a). Scope remains #1411/PR1412; N-1–N-6 are corrections of this
same artifact contract. The root checkout attributes and introduction-builder
LF-only write changes are required by N-1; product rendering/workflow behavior
is unchanged. Native Windows is unavailable, so no claim of a native Windows
rerun is made. Test both cp932 and CRLF defaults together, plus full-file equality.
Canonical Core ZIP stores entries with fixed platform metadata to avoid host
ZIP/zlib differences and reject trailing bytes.

N-2: retain compatibility approval fields as explicitly unverified record claims,
always emit authority_verified=false and human_reference_verification_required,
require schema2 repository comment/review URLs and normalized identities, and pin
all implementing AI tools outside the review record. Human reference verification
is a mandatory #1400 runbook step. The validator does not fetch or authenticate
GitHub decisions, and syntactic success never grants authority.

N-3: inspected the exact CPython archive inputs. GB2312's FreeBSD-hosted original
actually bears Unicode1991–1999 terms; JISX0213 has an independent permission
header. Both complete leading headers are retained and source-hash verified.
Legacy UCD3.2 is observed and recorded separately. HKSCS source explicitly calls
its licence restrictive; official terms clauses5/15 were examined. Historical
ICU XML carries no licence declaration in the retained file. Neither question
is cleared by generic PSF/Unicode text; source-specific assessment is pending,
not approved or silently dropped. mapping-attribution.json records investigation
results and remaining blockers; N-3 disposition must be independently reviewed
and tied to an Owner decision. No raw HKSCS mapping was fetched/redistributed.

N-6: replace the interleaved historical inventory with a current-only inventory;
retain earlier evidence in Git history. Build-time documentation rendering pins
repository links to the actual commit without embedding a self-referential SHA.
