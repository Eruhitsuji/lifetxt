# Release independent review — 2026-10-16

## Target and authority

Target source: `f70abe4937051c41021f473db000dfb150d97a1f`, tree
`945e487dbe8d9a88df1cec0103418207c650722c`. PR #1331 head
`6706be3c4399ca63f352811ca86d55d37e08ed33` has the same tree.
Related work: #1308, #1310, #1321, #1311, #1305, #1312, #1313, #1314;
merged PRs #1328, #1330 and #1331.

The maintainer explicitly requested an independent review. Three separate AI
agents inspected the fixed source without implementing or editing it. Root
transcribed their results. These are post-merge reviews, not a claim that the
original merges had fresh pre-merge reviews. They do not grant human merge or
release authority. Record-only changes require their own review and human merge.

## Independent implementation/security

Reviewer: `/root/publication_review`. Confirmed P0/P1/P2 findings: 0.
Inspected release.yml, release_plan.py, release_remote.py, release_orchestrate.py,
channels/canonical, publication tests, all seven retired entry workflows,
requirements and Japanese publication guide. Checked exact approval identity,
plan/run/attempt binding, before/after artifact authentication, main-only entry,
write/read-only native isolation, no-clobber remote retries, canonical ordering,
Homebrew credential isolation and numeric Latest prevention.
This reviewer could not rerun tests before test dependencies were available;
the result is source inspection, not a separate test success claim.

## Independent preflight implementation

Reviewer: `/root/preflight_review`. Confirmed P0/P1/P2 findings: 0.
Inspected Actions pagination/job/step/artifact/time/hash/expiry binding, safe ZIP
extraction, complete 13-target collector and producer validator reuse, atomic
bundle success, Mini direct builder version/failure, immutable-source complete
Desktop TOML comparison and its narrow normalization, and OCI graph/index reuse.
Ran the nine actions/collect/mini/desktop/desktop_manifest/proof/oci/core/standalone
unittest modules: 113 tests passed, no skips. Source tree remained clean.

## Independent integration

Reviewer: `/root/integration_review`. Blocking findings: 0.
Inspected producer/consumer contracts and payload reconstruction, source/run/attempt
identity, Desktop public mappings and private payload exclusion, full canonical
inventory, shared Mini notes, partial PyPI publication, same-byte retry/new
dispatch, Homebrew compare-and-swap/readback, alias partial repair and numeric
version order, GitHub Latest last, native fixes and Japanese/English runbooks.
Ran publication/desktop_manifest/mini/collect/actions: 81 tests passed.
Ran oci/proof/desktop/standalone/core: 69 tests passed.
These 150 executions overlap with other reviewers' tests and are not an
additional count of unique test cases.

Root ran publication/traceability_gate/change_package_closeout on the same source:
54 tests passed using an isolated Python 3.12 environment with PyYAML/pytest.
No source mutation occurred during these runs. Existing main CI run 38839586000
and Mini CI run 38839585988 succeeded for the target commit.

## Disposition and verification boundary

No blocking code changes or evidenced new defect issues are required by these
reviews. The implementation/integration review gate is complete for the source
above. This documentation update synchronizes review ledgers; it does not change
workflows, runtime, permissions, package versions or published bytes.

Existing real preflight run 38822634032 supplies prior all-13-native/Actions
acceptance. The reviewers did not rerun native builds or download the final ZIP
again, and do not relabel fixture tests as native execution.

Maintainer-reported settings match required reviewer, pypi main-only branch,
Prevent self-review disabled (maintainer self-approval permitted), PyPI publisher identity, repository secret location and
Homebrew token repository/permissions/expiry. The token's identity with the saved
secret remains unverified. Actual PyPI OIDC, preserved-digest GHCR transfer,
Homebrew writes, publication/download checks, Latest and live failure recovery
remain first-publication checks under separate human authority in #1308.
Existing v1.0.4.1 must not be republished by the new pipeline. External submissions
and exhaustive Desktop GUI tests remain separated as #1306/#1307.

After this record PR merges, #1310/#1321 and recovery documentation #1314 can be
closed against their bounded implementation acceptance. #1308 and publication
acceptance tracking remain open until actual next-version release evidence is
recorded. Live publication has not been authorized or executed.
