# Profile2 reviewer handoff (#1417)

This is a transfer and verification procedure, not a completed acceptance or
publication approval. Keep both publication flags false. Follow
[PUBLICATION_REVIEW.md](PUBLICATION_REVIEW.md) separately before publication.

## Transfer contract

The Owner provides the archive to the separate reviewer through an agreed
private channel or local copy, together with its filename, exact byte length,
SHA-256 and the source commit. Send the location privately; do not put private
paths, signed download URLs or credentials in public issues. The reviewer must
report how the bytes were received and distinguish Owner-reported provenance
from independently verified hashes. If the archive cannot be obtained, record
NOT RUN; source-only checks and reading an implementer's report do not replace
artifact execution. Never upload this unapproved distribution to public hosting.

The historical PR #1428 checkpoint is:

| Field | Expected value |
| --- | --- |
| File | `lifetxt-checker-profile2-pr1428.tar.gz` |
| Bytes | 82548588 |
| Archive SHA-256 | `a013d3773da97727542528f507c1f9ff8d9cbbc814a7e2ff92078781fe9eb039` |
| Payload manifest SHA-256 | `a1b6805c266d79e8e6adb81c5e63984b3a53ee898a8c0f7000a5b4e398d051ec` |
| Source commit | `4da6cdac01a9c6c612fe405371d3d5ff571b1a22` |
| Runtime profile | `lifetxt-hkscs-free-2` |

These identifiers describe the historical archive only. Changes to checker UI
or source metadata require a newly built artifact, new manifest/hash and review
against that commit. Do not label the old checkpoint as the current product.
Object/build-tree evidence is a separate checkpoint; the site archive alone
must not be described as an independent object-file inspection. The separate
build checkpoint's filename/hash/scope are recorded in
`.ai/project/changes/hkscs-rebuild-reverification/retention.json`.

## Receiver procedure

1. Recalculate the archive length and SHA-256 **before extraction** and compare
   them with the transfer contract. Reject mismatches. List members and reject
   absolute/parent-traversal paths, symlinks, hardlinks and special files. Extract
   only into a new isolated directory using safe extraction (for example Python
   3.12 `tarfile` with `filter="data"` after those checks); never overwrite the
   repository or an earlier candidate.
2. Verify the payload-manifest hash and every listed payload file's hash/length,
   plus missing and extra files. Record the manifest itself separately if it is
   intentionally outside its own list. Locate the site root by its
   `manifest.json` and `checker/` directory. Record both the payload-manifest
   identity and the site's manifest identity; these are different files.
3. Check out the exact source commit in a clean worktree and use its dependency
   pins. Use the historical source commit for the historical artifact; auditing
   it against changed current UI/template bytes is expected to fail. For current
   product acceptance, rebuild from the current commit with the same verified
   profile2 runtime and ten derived sources, then record its new identities.
4. Run the artifact integrity and publication-negative checks from that worktree
   (`SITE` denotes the extracted site directory):

   ```sh
   python -m contrib.browser_check_poc.distribution_audit SITE
   python -m contrib.browser_check_poc.distribution_audit SITE --require-publication
   ```

   The first must report integrity passed. The second must exit 1 while
   publication blockers remain; a successful integrity check is not approval.
   Confirm all five runtime hashes and profile2 identity. For explicit API use,
   call `custom_distribution.audit(site, runtime_profile="lifetxt-hkscs-free-2")`.
5. Set `LIFETXT_PROFILE2_ARTIFACT` to `SITE` and run
   `python -m unittest tests.test_hkscs_profile2 tests.test_custom_distribution`.
   Record executed test names and skips. The profile2 rehash/crossed-runtime
   mutation test must execute. **Do not** set `LIFETXT_CUSTOM_ARTIFACT` to profile2:
   that variable selects the legacy profile1 tests. The two profile1 actual-
   artifact tests may remain skipped when no profile1 artifact is supplied.
   Never mutate the transferred original; mutation tests use isolated copies.
6. Execute the real Node/WASM codec checks: HKSCS imports and encode **and
   decode** must fail, retained Big5 codecs must work, and the stdlib archive
   must not contain the removed codec. Inspect source/object evidence only when
   those files have actually been supplied; distinguish missing object evidence
   from executed source/stdlib/WASM checks. Do not count a script syntax or
   escaping error as a successful negative codec test.
7. Run the Node parity/boundary/repetition probe and
   `scripts/probe_website_checker.py` on the same artifact. Record Chromium
   executable/version/OS, JA/EN 16KiB boundaries, diagnostic cap, repeats,
   cancel/retry, failure recovery, network/storage and intro no-script checks.
   Missing browser prerequisites mean NOT RUN, not PASS. Use the current probe
   only with an artifact built from its corresponding current UI source.
8. Post a sanitized review record: reviewer/tool/session identity; code commit;
   archive, payload-manifest and site-manifest hashes; five runtime hashes;
   commands/results; actual versus record-only evaluation; skips/failures;
   source/object/stdlib/WASM scope; remaining risks and conditional judgment.
   Refer source-specific ICU applicability and whole-source retention to #1398,
   product limits to #1399 and live delivery/publication to #1400. Owner limited
   acceptance and independent review remain distinct from merge and deployment.

## Evidence status on 2026-10-26

The [independent execution report](https://github.com/Eruhitsuji/lifetxt/issues/1417#issuecomment-6413507506)
records receipt/hash verification, all 104 payload files, integrity and closed
publication gates, actual profile2 mutation checks and Node codec checks for
this historical checkpoint. It explicitly excludes its failed decode command,
object inspection and legacy profile1 actual-artifact tests. It is a Claude
Code AI review, not a human or legal approval. The Windows default-codepage
failure identified there is fixed by explicit UTF-8 JSON reads in
`tests/test_custom_distribution.py`. This procedure does not upgrade the report's
scope or change mapping acceptance states. Current-product browser observations
are recorded separately on #1399 and must retain their own commit/manifest scope.
