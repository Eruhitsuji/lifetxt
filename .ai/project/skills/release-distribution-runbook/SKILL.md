---
name: release-distribution-runbook
description: Operate lifetxt approved release publication, verify distribution channels, and recover preflight/partial publication/source defects without moving tags or replacing public bytes.
---

# Release distribution runbook

Read [English operator guide](../../../../docs/en/release-publication.md) or
[Japanese operator guide](../../../../docs/ja/release-publication.md), then use
[preflight](../../../../docs/en/release-preflight.md) for build inputs.
Apply the repository AGENTS/task/review rules to any implementation repair.

## Prepare and authorize

1. Confirm human-selected version PR merge and successful push/main CI for the
   exact source SHA. Preserve optional numeric N; never choose/increment it.
2. Run `release-preflight.yml` on main. Require all 13 targets and the collector
   to succeed. Record run/attempt, final artifact ID, bundle JSON digest and
   expiry. Inspect actual logs before diagnosing failure. Preserve all original
   artifacts; the final bundle references them rather than containing binaries.
3. Dispatch `release.yml` on main with `preflight_artifact_id` and
   `bundle_digest`. Read its prepared source/version/inventory/plan summary.
4. Have Release Authority Eruhitsuji approve the pending pypi environment once
   with the exact summary comment `release <digest> run <run-id>/<attempt>`.
   Treat this as the publication decision, separately from PR merge/version
   selection. Do not approve it yourself, simulate history, enable bypass,
   change secrets or trigger an actual release without human authority.
5. Observe ordered primary → canonical → remote verification → downstream →
   Latest stages. Never dispatch retired primary/downstream entries.

Require the pypi environment reviewer and main branch policy; preserve PyPI's
release.yml/pypi Trusted Publisher identity. Missing approval history fails
closed even with an unprotected environment. Reuse existing Homebrew credential;
report missing Contents read/write on Eruhitsuji/homebrew-tap as blocked and
hold Latest. Do not claim external account configuration was inspected.

## Diagnose and recover

Read `release-failure.json` and stage logs before the earlier channel receipt.
A blocked stage overrides an earlier primary_verified/verified receipt; do not
report acceptance until Latest readback and an accepted receipt exist.

| Evidence | Classification and permitted next step |
| --- | --- |
| Preflight failed, nothing published | preflight_failure: fix PR, new SHA preflight; same unpublished version may be reused. |
| Network/ordering failure, remote tag/source/hash still exact | publish_retryable: new release dispatch using the original preflight ID/digest; new run-specific approval, only missing writes. |
| Published bytes need source changes | published_source_defect: preserve old version; human chooses correction N, version PR/CI/preflight/approval from the beginning. |
| Generated winget/Scoop/conda awaiting external review | external_manual_required: provide generated artifact and normal external submission instructions, never claim published. |
| Conflicting hash/source/tag, unsafe Latest, critical/security/data-loss finding | critical_blocker: stop; Release Authority decides incident/withdrawal action. |

Use new dispatch, not Re-run failed jobs with an earlier attempt's plan.
Authenticate all current remote bytes before retrying. Never overwrite a
mismatching existing asset, move a tag, rebuild a published version, or silently
change OCI version tags. On artifact expiry/deletion, stop for retained evidence
and human recovery decision; do not regenerate permission to reuse a number.
Repair partial latest/major/minor aliases only to the original verified index;
GitHub Latest is last and numeric ordering must still allow promotion.

Use v1.0.4 → v1.0.4.1 only as a historical source-defect example. Do not operate
on those existing releases through the new immutable-binding pipeline.
For a known critical finding, use the documented RELEASE_CRITICAL_BLOCKER human
setting/incident procedure; do not clear it on behalf of the authority.

## Verify and report

Report each channel from actual remote state/download evidence, not workflow
green alone. Require the single LF SHA256SUMS to match complete primary inventory
plus release-inventory.json (excluding itself), including every Desktop installer.
Exclude private Desktop bundled Core and OCI archives. Require exact PyPI
wheel/sdist bytes/metadata and both GHCR platforms/index/blob hashes. Retain
representative downloaded Standalone/Mini smoke and preflight Desktop metadata.

Distinguish verified primary/Homebrew from generated winget/Scoop/conda and
manual_required external submissions. Keep exhaustive Desktop GUI matrix
not_verified; it is nonblocking unless a concrete critical defect exists.
Record run URL/attempt, source SHA/version, stage, receipt and next human action.
Keep signed URLs, credentials and personal machine paths out of issues/reports.
Use [distribution sections 4 and 6](../../../../docs/en/distribution.md) for
the concrete winget/Scoop and conda submission destinations and commands.

For code repairs, add a disposable offline regression, follow the repository
High package/traceability/review process, create a PR into main and wait for
human merge. Treat live release and settings changes as separate authority.
