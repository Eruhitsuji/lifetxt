# Human procedure guidance: definition and local run stages

Contract: [English](../../../../docs/en/procedure-guidance-design.md) /
[日本語](../../../../docs/ja/procedure-guidance-design.md).
Usage: [English](../../../../docs/en/procedure-guidance.md) /
[日本語](../../../../docs/ja/procedure-guidance.md).

D1–D4 and the three-PR grouping were approved by Eruhitsuji. Stage 1 (#1334–#1337)
merged as PR #1346 into 99bd4491. Stage 2 (#1338–#1341) starts from that latest
origin/main on feature/1340-procedure-run, base=main. It is High / M / complexity 6:
transition/model/store/CLI form one explicit operation and recovery boundary.
Stage 3 Web starts after stage 2 merges. No intermediate sub-PRs or integration
branch. No merge/release/deployment authority is delegated to the executor.

Lifecycle: approved requirements/design → implementation → developer verification
→ independent implementation/integration review. Adaptive-default / W-model.
Owner, independent reviewer, integrator and merge authority: Eruhitsuji; executor
Codex. Latest-head stage-2 independent reviews are pending, not replaced by self-review.

## Reuse and module boundaries

Stage-1 procedure_definition/validation/graph retain their immutable, bounded,
data-only semantics. Existing parser/ID/quote primitives are reused; strict
profile validation stays separate from generic check. Normal W106, links/VM/flow,
Task statuses, Native item_event, timezone and external execution are unchanged.

- procedure_transition.py: pure explicit action/decision/end/pause/resume/finish/
  abandon transitions; validates graph/cursor, template binding and hard guards.
- procedure_run_model.py: closed procedure-event-v1, canonical digests, immutable
  state, pure replay and lossless single-line Note/JSON interchange. No I/O.
- procedure_run_store.py: explicit source/log admission, actor/source/step/sequence/
  request/revision checks, bounded read, existing single-target CAS/journal commit.
- procedure_run_cli.py: required explicit non-TTY commands, current instructions,
  read-only show/list/request receipt. procedure_cli adds minimal registration;
  taxonomy records that the top-level command now also has write operations.

## Persistence and authority

The exact schema is procedure-event-v1.schema.json in this package, not a new
entry in the generic public schema catalog. Each Note has fixed status/type/
title and exactly record/id/event_data. event_data is closed canonical JSON;
unknown fields/schemas and invalid calendar times fail at runtime. Start freezes
only control IDs, step kinds and edges, plus the original full source-byte SHA
and finite guards. No title/body/private path/secret/URL/command output is copied.
Graph semantics are validated on replay; subsequent payloads must match exact
sequence, previous digest, actor/source/root/revision, choice and current step.
Request IDs are unique across the whole log. show --request-id is an inspection
receipt, not idempotent automatic execution. Log events are the sole run authority;
journal before/after artifacts are recovery backups, not another mutable state.

The source handle is SHA-256 of the normalized canonical path, not basename or
content hash. Hashing is pseudonymization, not guaranteed path anonymity. Source
and log aliases, hardlinks, symlink log targets, generated/read-only logs and
nonregular files are rejected. Log body syntax/joins/unknown records cannot hide
extra payloads. The initial missing-log sentinel remains distinct from an empty
file's SHA. Existing UTF-8 BOM and CRLF survive replacement and count toward bounds.

## CAS, failure and recovery

Only the separate log is a target of multi_target.apply_multi_target. Its shared
lock, expected hash, staging, durable transaction journal, before/after artifacts,
atomic replacement, postverify and operator resume/compensation policy are reused
unchanged. Pending/corrupt journals block writes; no automatic recovery is added.
Source binding/hash and log permissions/path are checked before target commit.
External editors do not share a portable two-file transaction; a source change
observed after commit returns blocked while retaining the committed event.
Every later operation checks again. Changed/missing/invalid sources allow only
inspection and pause/abandon against the original binding, not continuation.
Restore exact original bytes through operator backup procedures or start a new run.

CLI actor tokens are local attribution and not authentication. They do not grant
server identity or Web write permission. Web remains a separately gated stage-3
server adapter. Access to logs, actor IDs and protected recovery artifacts must
follow existing local permissions/privacy policy. Digest chains detect accidental
corruption, not authenticated tamper-proof audit or proof of real-world work.

## Evidence and limits

Tests cover explicit transition tables, choice/guard/terminal refusal, schema and
semantic tampering, sequence/digest/binding/replay/roundtrip, independent runs,
two writers, request receipts, stale/invalid source, aliases, permissions,
BOM/CRLF/size caps, pre/postcommit faults, compensation and actual process crash
followed by existing operator journal resume. Every CLI lifecycle step is also
run in a fresh non-TTY child process. Existing parser/diagram/VM/flow and shared
mutation/journal/work-session regressions remain required. Commands/results and
skips are retained in verification.yml; plans are not reported as evidence.

Run/log/event limits: 5,000 / 50,000 / 32 MiB / 2 MiB event JSON; persisted IDs
256 characters, actor/request tokens 64. Hop/step-visit guards remain 1,000 / 20.
Replay admission is bounded by encoded bytes, event count and frozen control size;
transition traversal operates on the bounded graph. No automatic rotation,
retention deletion, migration, rollback, release or deployment is authorized.
Revert code without deleting existing definitions or event logs. Corruption
requires preserving damaged data and explicit verified-backup/operator recovery.
