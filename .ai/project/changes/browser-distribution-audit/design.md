# Distribution audit

Reuse cap-official-website and the existing #1362 inventory. Operations / High,
adaptive-default W-model, S score 5. Source origin/main; PR base main.
Owner and independent reviewer Eruhitsuji; executor Codex. Separate
implementation/distribution and integration review entries are pending.

The builder audits after writing the manifest. File allowlist, original notices,
runtime hashes, lock hash and Core ZIP membership/source bytes must agree.
The audit reports integrity separately from publication, which remains blocked.
No new third-party dependencies or runtime behavior changes. Existing synthetic
fixture build tests retain their explicitly synthetic runtime identities.

Security: reject path/membership drift, extra files, symlinks and manifest-only
re-hashing; no user data or network call in audit. Failure stops build.
Coding: reuse the inventory and builder constants; isolate audit responsibility.
Test: mutate actual artifacts including manifest rehash attacks; retain all
existing PoC and introduction-only website regressions.

Rollback: human-reviewed revert of this PR restores prior isolated builder.
No deployed product is changed. Source references are not legal clearance.
