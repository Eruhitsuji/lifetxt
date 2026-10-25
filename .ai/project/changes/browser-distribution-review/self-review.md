# Implementer self-review — #1411

Informational only; this is not independent review or approval. Review scope:
base 372ddca1 to the implementation commit in this branch, then the final PR
head/CI. The final commit ID is reported on the PR; this file cannot embed its
own commit hash. Independent implementation/distribution and integration review
must bind that exact head and artifact manifest.

| Finding | Implemented disposition | Remaining boundary |
| --- | --- | --- |
| P1-1 | Official Unicode V3 text and UCD16 original ReadMe/hash/date, UCD/mapping components, restricted HTTPS origins | Independent assessment of scope/notice adequacy |
| P1-2 | Static index links all 25 notices and component/section metadata; both UI languages, PoC and source page link it; audit checks navigation and bytes | Final-head independent confirmation |
| P1-3 | Whole-site checker manifest, fixed allowlist and source-byte comparisons, source/runtime/notice/Core checks | Product publication integration remains #1400 |
| P1-4 | Publication candidates require all ten verified same-origin archives; link mode cannot pass gate; source retention policy/required Owner record | Owner retention commitment and hosting acceptance pending |
| P2-5 | mimalloc/SipHash24/dtoa/Mersenne Twister in components and current inventory with original notice sections | Exact linked-object subset not claimed |
| P2-6 | Per-archive evidence kinds; WASM zstd/SQLite/UCD/mimalloc checks; official xz bytes equal mirror | Recipe inputs without hashes and linked liblzma version remain unverified; Owner decision pending |
| P2-7 | Bounded evidence policy and fixed-toolchain-rebuild alternative documented | No bitwise rebuild or emsdk-used-commit attestation; Owner decision pending |
| P2-8 | Data-driven gate with synthetic positive/negative tests, exact commit/manifest binding, clean inputs, review viewpoints, retention and separate approval | Offline record authors/decision URLs must be human-authenticated; actual gate blocked |
| P3-9 | UTF-8 I/O explicit; generated site paths use as_posix; simulated cp932 build/delivery checks | Native Windows run not performed |
| P3-10 | Repository-relative docs links resolve; generated indexes separately describe local navigation | None identified in changed documentation |
| P3-11 | Pinned sysconfig SHA256 and selected AST constants; full provenance copied and audited | Generated configuration is shipped source, not a reproducible-build claim |

Self-review corrections: moved symlink checks before artifact reads; required
exact generated index bytes as well as parsed links; rejected unsafe notice
basenames/origins; checked manifest hash shape and malformed review objects;
required Owner source retention record; kept review records external to avoid
self-referential commits; added dirty-input blocking. Corrected a notice-section
label against the original CPython document. Used explicit repository documentation URLs for context-dependent README/delivery links so the copied Markdown also avoids broken artifact-relative paths. Synthetic fixture failures were
fixed before reporting the final passing tests; no failed run is counted as a
pass. Final changed-file review confirms no Core/Format/CLI runtime behavior,
production builder, Pages workflow, managed standard, settings or runtime binary
changes. No raw user data, credentials or local host paths are published.

Security review: archives remain hash/size locked, validated members only, no
archive code execution; explicit fetch only; runtime probe executes already
verified pinned WASM without package downloads. All scripts remain local tooling.
Generated indexes escape metadata and disallow active content. Neither gate nor
manifest is a signature or authorization service; human review is required.
No broad security support claim is made for legacy runtime library versions.

Result: implementation ready for independent review, with the Owner decisions
above explicitly pending. Actual complete_distribution_audit and
public_distribution_approved remain false; #1398/#1400 remain blocked.


## Second-round self-review (N-1–N-6)

The independent review of 499c164a was correct: encoding simulation did not
exercise Windows newline translation; record claims could look authoritative;
CJK source classification was overbroad; ZIP trailing bytes and README discovery
needed stronger checks. The following fixes were re-reviewed:

- N-1: generated writes explicitly use UTF-8/LF; scoped checkout attributes keep
  source assets LF and original snapshots byte-exact. Full candidate builds under
  cp932+CRLF defaults compare every file/manifest against normal output. ZIP
  entries use fixed platform/mode/time and STORE to avoid zlib-version variation.
  Native Windows itself is not available; use a new worktree after attributes
  change. This is a simulation result, not native-Windows certification.
- N-2: schema2 compares case-insensitive logins/tools and complete implementing
  tool inventory pinned outside the review record; every evidence/reference
  must be a same-repository GitHub comment/review URL. Case aliases, substituted
  implementer lists and x/external-URL references are rejected. A successful
  structural record still has authority_verified=false and requires human
  verification; PUBLICATION_REVIEW.md mandates opening/authenticating every URL.
  This code never claims to verify signatures, authors or human authority.
- N-3: UCD3.2 is observed and listed; Unicode MAPPINGS, HKSCS, historical ICU,
  JISX0213 and GB2312 are separated. Source-member hashes bind classifications.
  Original JIS/GB headers are retained; GB2312's FreeBSD endpoint actually serves
  a Unicode-copyrighted table. HKSCS derived-table permission and historical ICU
  terms remain unresolved, explicitly recorded and publication-blocking. These
  are not falsely marked cleared by this self-review or generic licence text.
- N-4: complete regenerated ZIP bytes reject trailing bytes and comment metadata
  changes even with a matching rewritten manifest. Member checks also remain.
- N-5: README and all 32 notice/metadata destinations are linked, checked and
  served successfully in real JA/EN Chromium navigation.
- N-6: current-only runtime inventory replaces obsolete interleaved sections;
  generated Markdown repository links bind the actual build commit. Original
  source documentation remains navigable without embedding its own commit hash.

No Core behavior, pinned runtime binary, workflow, deployment or approval flag
was changed. Core source bytes remain unchanged; only its ZIP container is now
canonical (288106 bytes instead of the earlier compressed 76646). The roughly
211KB increase is explicit and Node/WASM fixture behavior still passes. Owner
P2-6/P2-7 decisions, source retention and source-specific permission acceptance
remain pending. All new tests are regression tests for reported defects;
synthetic positive records are not real approvals.
