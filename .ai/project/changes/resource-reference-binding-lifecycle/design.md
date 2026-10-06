> Concrete owner approval received 2026-10-07 for the active-session proposal.
> Original proposal-stage gate notes below are superseded for approved scoped runtime
> work; independent latest-head human security/integration and merge review remain pending.

# Durable opaque binding lifecycle — approved implementation design

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

## Storage and identity

Choose stdlib SQLite only, protected server-owned directory 0700 and files 0600.
Use no-symlink owned directory acquisition and revalidation; regular single-link
owned DB/WAL/SHM, local filesystem only. Refuse unsafe parents, links, permissions,
foreign owner, shared storage or multi-worker ownership. Hold a nonblocking
process-lifetime owner lock before opening SQLite. No path interpolated SQL,
extension loading or caller-selected database. SQLite cannot operate solely by
root FD: directory ancestry and trusted same-uid local-writer assumptions must
be documented and verified, otherwise refuse opening. This is not encryption;
#1098 storage/trust policy remains applicable.

Proposed tables: metadata(schema_version, install_generation, epoch),
bindings(workspace_id, source_id, canonical_item_id, association_generation,
reference, source_validator, resource_validator, policy_generation, state),
and tokens(namespace, token, epoch, binding_generation, full_validator, state).
Private association data identifies the exact enrolled existing attachment, never
permissions or secrets. Validators are full SHA-256 of the source/snapshot bytes.
No digests, paths, receipt IDs or ordinals are encoded in public IDs.
Only bounded private values may be persisted. Use secrets.token_hex(16) with
UNIQUE constraints and bounded collision retry inside BEGIN IMMEDIATE; collisions,
quota, corruption and lock timeout produce a safe service failure, never reuse.

All retained rows, including every token namespace, count toward 50,000; active
bindings count toward 10,000. State transitions and allocation commit together.
Busy timeout <=100ms, transaction deadline within overall 30s operation budget.
No work queue, automatic eviction, compaction or implicit epoch retirement.
Read operations never silently enroll or repair a damaged store.

## Restart, corruption and recovery

Choose the issue's conservative default: every process start installs a fresh
random in-memory epoch and retires prior public references/tokens transactionally.
Complete state may retain private enrollment intent, but cannot retain public IDs.
Any surviving DB/WAL/SHM copy/backup/rollback never yields current public authority.
Even restoring state during a running process cannot recreate its memory epoch;
validate persisted epoch plus owner lock before each transaction and fail closed
on replacement/identity uncertainty. Do not automatically create a replacement DB
over corrupt/lost state or delete historical state; operator explicitly provisions
new state. A fresh unprovisioned store has no usable enrollment.

This deliberately gives up stable IDs across clean restarts: there is no proven
rollback detector. It does not promise an immutable historical audit against a
privileged owner restoring all storage. Detectable invalid state refuses service;
operator-controlled retirement/deletion needs separate human action. Test WAL
recovery, missing/foreign sidecars, copied/restored databases, replacement while
open, concurrent ownership, partial transaction failure and clean restart.

## Enrollment and continuity

Only an owner-directed server enrollment boundary accepts a current verified
source/item/attachment snapshot. Browser/client discovery cannot supply paths,
create IDs or mutate sources. Explicit approved enrollment selectors are provisioned
out of band with the restricted client, never obtained from a raw manifest.
Canonical authored item IDs must be unique. Id-less, duplicate, ambiguous, uncertain,
missing files or unverifiable source snapshots do not enroll.

Record current whole-source bytes and exact committed association generation.
The initial implementation has no approved writer-continuity integration; therefore
ANY out-of-band source byte change invalidates that source's associations. Path,
ordinal, matching later bytes or receipt identity never prove continuity. A detach
or recreate gets a fresh generation and ID even for identical bytes/path. File byte
changes on an unchanged verified association rotate resource revision tokens;
source/policy changes never reuse old tokens. Verified rename/replacement retention
is deferred until a reviewed authoritative transaction continuity seam exists.

## Verification and operational risks

Tests: deterministic collision injection; concurrent atomic allocations; quota at
boundary; transaction rollback; read-only source unchanged; detach/recreate;
duplicate/id-less; cross-install/workspace; clean restart; lost/corrupt/backup DB,
WAL/SHM permissions and replay; multi-worker refusal; handle cleanup and contention.
Use synthetic fixture paths only in local tests, never publish locator/digest data.
Disable capability on store failure. Revert code after stopping consumer; do not
restore an old used epoch or automatically remove persistent state on rollback.

## Selected SQLite recovery policy

Use stdlib SQLite DELETE journal with synchronous FULL and single-owner locking.
Foreign/hot/restored WAL/SHM/journal files fail closed; no implicit recovery, import,
compaction or deletion. DB size capped at 256MiB, in addition to retained row quotas.
Opening any valid complete state rotates public epoch; restoring/copying cannot
restore public authority. Source continuity records full source hash plus verified
root/inode/size/mtime/ctime; identity fields are private, never descriptor metadata.
