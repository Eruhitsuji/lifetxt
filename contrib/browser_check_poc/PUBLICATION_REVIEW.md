# Human reference verification before #1400 publication

The offline gate is a **record-shape and artifact-binding checker**. It performs
no GitHub API requests, signature validation, login authentication or authority
checks. `authority_verified` is always false. Even if a supplied record makes
`public_distribution_approved` true, that value means **the supplied record
claims approval**, not that this tool authenticated it. Do not use the JSON
boolean or a green exit status alone as permission to publish.

Before using `--require-publication`, the human Owner must:

1. Check out the final PR head in a clean worktree, build the complete ten-source
   candidate, audit it and record the exact commit and manifest SHA256. Confirm
   CI and the latest independent review both target that head. A change to
   bytes/commit requires a new build and renewed review.
2. Open **every** findings evidence URL, both review URLs, the source-retention
   URL and publication-approval URL directly on GitHub. The offline validator
   only checks the repository/comment/review URL shape. Confirm the referenced
   objects exist, have not been withdrawn/edited into a conflicting decision,
   and concern this exact commit/artifact. A URL alone is not proof.
3. Check the actual GitHub author/login against each record's login. Logins are
   case-insensitive. For an AI-assisted review, read the explicit tool/session
   declaration in the comment; verify it is separate from **all** implementing
   tools (currently Codex). The posted GitHub author may be the Owner relaying
   an AI review; this does not turn the review into a human technical review.
   A human review must really have been performed by a human. The offline tool
   cannot distinguish truthful declarations from fabricated ones.
4. Verify P1-1–P1-4, P2-5–P2-8 and N-1–N-3/N-7 dispositions against the actual fixes
   and evidence. For P2-6/P2-7 and N-3, require verified scope, remaining risks,
   and the Owner's explicit decision. For HKSCS/ICU in particular, require a
   source-specific permission/terms resolution or verifiable removal; a generic
   PSF/Unicode claim or Owner risk acceptance is **not** a resolution. For N-7,
   the gate reads the packaged `notices/mapping-attribution.json` and rejects
   every unresolved publication-blocker. HKSCS-2004 and ICU GB18030 may change
   to `resolved-terms-confirmed`, `resolved-removed` or
   `resolved-owner-judgment` **only when independently supported by source-
   specific facts**. Each input needs a `resolution` object: matching
   `status`, `source_id`, `source_archive_sha256`, `owner`, substantive
   `basis`, `verified_scope`, `remaining_risk`, and same-repository
   `evidence_reference` and `independent_review_reference`. A missing
   resolution, a renamed/pending blocker, or an approval claim alone fails.
   Open these links and verify the actual source terms/byte removal and
   applicability to the distributed binary. Offline validation **does not**
   prove legal permission or authenticate the evidence. There is currently
   **no accepted HKSCS/ICU resolution**; keep publication blocked.
5. Confirm the Owner's actual source-retention commitment covers the entire
   period corresponding binaries remain available, including retained older
   versions. Confirm delivery/backup/restore of the exact ten-source bundle.
6. Confirm a **separate explicit Owner publication decision** actually exists
   for this commit and manifest. It must not be inferred from merge, review,
   CI, a synthetic fixture, the offline result or earlier publication approvals.
7. Retain a human-authored verification note with the actual references, author
   checks, implementing/reviewing tool identities, exact commit/manifest,
   decisions and unresolved scope. Do not ask the implementing AI to invent it.
   Populate the external schema2 record only from these verified facts, then run
   the checker with `--review-record FILE --require-publication` against the
   same artifact. Report shape/binding success alongside the human note.
8. Separately decide merge, #1400 product acceptance and deployment. Neither
   command in this runbook merges, publishes nor deploys anything.

Do not fill the pending example with invented names, placeholder URLs, accepted
statuses or evidence from a different revision. The template remains pending.
The current record contains no accepted Owner/independent decisions; actual
flags remain false. This runbook prepares review; it is not a completed review.

For private checkpoint transfer, receiver hash/safety checks, profile-specific
execution and historical-versus-current artifact scope, follow
[REVIEWER_HANDOFF.md](REVIEWER_HANDOFF.md). That procedure is not an acceptance
record and does not change the pending publication decisions above.
