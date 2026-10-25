# Review remediation design

Bug / High, adaptive Kanban + W-model; architecture/design to implementation,
developer verification and PR review. Size M, score6 (scope2/dependency1/
uncertainty1/test2/ops0): one cohesive publication-artifact contract requires
source, notice, artifact and gate changes together; independent review and live
publication remain separate #1398/#1400 work. Existing cap-official-website and
PoC source/notice/audit builders are extended, no alternate engine is introduced.

Source origin/main 372ddca1, branch fix/browser-distribution-review, PR base main.
Integrator/Owner Eruhitsuji owns narrow shared registry edits. No parallel
executor. Implementation and integration reviews must examine the final head.
No managed standards, public runtime bytes or production workflow changes.

Notice inventory validates fixed official HTTPS origins, original/stored hashes
and component references. Generated static notice index lists every notice with
known components and sections; JA/EN UI and source page link it. Unicode scope
retains current official V3 text and original UCD16 copyright metadata without
claiming complete per-input mapping attribution. Source delivery now includes
source-provenance.json and uses its own fixed allowlist/byte validation.

The final checker profile receives a whole-site manifest, exact intro/page/asset
comparisons, unchanged Core source ZIP validation and all runtime/notice/source
checks. Regenerating hashes cannot bless changed content. Publication candidates
require all ten offline-verified source archives on the same origin. Default link
mode is still available for development, always publication-blocked. Owner must
commit to keeping the original source bundle throughout binary availability.

The publication gate consumes externally retained independent-review evidence,
not flags supplied by a builder. It binds the final source commit and exact
manifest hash, requires clean build inputs, P1/P2 dispositions, two independent
review viewpoints, retained verified/unverified scope, Owner risk decisions,
source retention commitment and separate publication approval. Evidence is kept
outside the reviewed artifact to avoid the circular commit problem. The offline
tool does not authenticate authors or decision URLs; human verification is
mandatory. It neither merges nor deploys. Historical inventory snapshots remain
false and cannot approve distribution. Actual gate remains blocked with no
review/Owner record. Synthetic accepted records test the future path only.

Runtime evidence runs Node against the previously hash-validated retained WASM,
without fetching packages. zstd/SQLite/UCD and mimalloc must match expected
versions/configuration. Source probe still checks all nine patches/567 stdlib
files; generated sysconfig now additionally checks pinned bytes and selected AST
constants without executing that source. Archive evidence types retain limits,
including URL+version without upstream hashes and unobserved liblzma version.

Security viewpoints: source origin/redirect/path validation, no archive execution,
no automatic downloads, HTML escaping/static CSP, symlink rejection, fixed
allowlists, rehashed mutation rejection, explicit stale-evidence blocking and
separate human authority. Runtime probe executes only already hash-validated
pinned WASM; patch applies only to safe temporary files. Complexity is O(total
artifact/source bytes); source archive size remains bounded by the lock, and the
source/probe tooling never enters the interactive Worker or user-input path.

Test viewpoints: synthetic normal/error gate paths, source/notice URL and byte
mutations, rehashed final UI/runtime/Core/metadata mutations, all-notice local
navigation, actual source cache+Node proof reproduction, complete candidate
build/audit, UTF-8 and website no-script regressions, lint and traceability.
Windows execution itself is unavailable; Linux with simulated cp932 defaults
checks encoding behavior, not a claim of full Windows certification.

Rollback: human-reviewed revert; no deployed checker or data migration. Preserve
the final reviewed source/manifest/bundle before any future distribution action.


Second-review refinements: explicit LF writes plus scoped checkout attributes;
canonical stored Core ZIP and full-byte comparison; all notice metadata including
README linked; exact-build-commit documentation rendering. Gate records now use
schema2 with normalized tool/login identities and repository discussion URLs,
and always label authority as unverified. Human URL verification is required by
PUBLICATION_REVIEW.md, not silently inferred by the offline validator. CJK input
classification and source-specific terms results are bound to selected archive
members; HKSCS/ICU questions remain explicit pending publication blockers.
