> Concrete owner approval received 2026-10-07 for the active-session proposal.
> Original proposal-stage gate notes below are superseded for approved scoped runtime
> work; independent latest-head human security/integration and merge review remain pending.

# Current-authority descriptor resolver — approved implementation design

## Authority, phase and dependencies

This is a concrete design proposal, not owner approval or executable behavior.
The owner's request authorizes refinement and a reviewable Draft PR. The issue's
explicit Inbox/concrete-design gate remains effective until owner approval.
Method: adaptive-default + W-model. Change type: Security. Assurance: High.
Accountable owner and Merge Authority: Eruhitsuji; implementer: Codex.
Independent human design/security and final integration review remain required.

Latest inspected main includes #1110 / PR #1124's approved bearer-only schemas,
#1112's investigation and #1115 / PR #1123's confined reader integration.
Reuse docs/en/resource-reference-resolution.md as the normative wire contract,
remote_access, collaboration membership, remote_backend item visibility,
attachment policies and attachment_snapshot.read_snapshot. No replacement writer,
provider fetching, Format changes, mandatory dependency or .ai/managed edits.

Owner decisions requested together: accept these concrete persistence/resolution/
delivery designs, proposed configuration boundary, sequential subunits and High
risk treatment. Until accepted, no runtime/schema/config edits and no capability
advertisement. Approval authorizes implementation, not merge/release/deployment.

## Domain seam and ordering

Resolver depends on the approved store and confined snapshot service, not HTTP.
Accept canonical selectors or opaque references and current trusted request context;
never accept filesystem paths or trust a supplied principal dictionary as authority.
Reload authoritative server configuration and principal registry at each operation,
reject disabled/replaced identity, require read, explicit selected-workspace membership,
source role, item visibility and metadata policy. Full/chunk additionally require
explicit attachment:read; owner/editor role and ordinary read do not imply it.

Use existing workspace/source handles and item visibility semantics. Require a
single exact canonical authored item and committed enrolled attachment. Reject
id-less/duplicate/hidden/removed/wrong-workspace/corrupt/uncertain state uniformly,
before returning a locator, resource count, validator or existence-specific result.
Do not fall back to a line number, basename, ordinal or path equivalence.

## Consistent bounded authoritative snapshots

Confined reading must cover source bytes as well as resource bytes. Read at most
1MiB/source, 5,000 items/source and 10,000/selected workspace; cap+1 detects excess.
Reuse the Linux helper only where its root/permissions/kernel/filesystem prerequisites
are verified. Parse the same source bytes whose full SHA-256 binds the source token.
Use current configuration/membership/policy generation in request context; re-read
and compare source/config/membership/association before serialization and before
emission. No stale cache used as current authority. Snapshot helpers are sequential
within the enclosing admission slot so they do not multiply active HTTP work.

Discovery returns 0..16 currently visible eligible descriptors for the authorized
item; hidden associations do not contribute counts. >16 visible descriptors or
>32KiB encoded result returns static RESOURCE_LIMIT. No partial truncation.
Actions look up in selected install/workspace first; establish current live
association and authorization before comparing supplied revisions. Both exact
source/resource tokens are required; map to complete source/snapshot SHA-256 and
policy generation, never short hashes, ETags or provider revisions.

An authorized changed file on a continuous association rotates its token and gives
STALE_REVISION for the old expectation. Uncertain source edits invalidate association
and give RESOURCE_UNAVAILABLE. Revocation takes precedence over stale reporting;
regrant still repeats all current checks, with no resurrection of retired binding.

## Descriptor/disclosure

Construct a fresh closed descriptor shape from #1110, never redact a raw item.
Default display_name is Attachment; no derived basename/provider URL. Initial
presentation omits size_bytes/media_type/content_digest; explicit separate current
policy permits these. Authored label must satisfy Unicode/UTF-8 and safe-classification
rules. MIME only verified contract enum; digest only full exact snapshot SHA-256
with explicit disclosure authorization. Do not echo raw exceptions or selectors.
No stored authority in the binding index. No provider fetching or source mutation.

## Verification and residual trust

Domain tests cover IDOR, selected workspace, membership/scope/source/item revocation,
role without byte grant, credential rotation, wrong-workspace token, duplicate/id-less,
removed/recreated, whole-source/resource changes, hidden counts, default label/digest
omission, metadata policy revision and sanitized errors. Real approved Linux helper
integration is mandatory; mocked reader successes are domain tests only. Same-uid
malicious writers/privileged host compromise remain outside the reader guarantee.
Byte checks continue in transport; domain success alone is not safe delivery proof.
