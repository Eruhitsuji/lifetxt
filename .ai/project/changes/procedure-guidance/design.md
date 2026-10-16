# Human procedure guidance: definitions, local runs and Web

Contract: [English](../../../../docs/en/procedure-guidance-design.md) /
[日本語](../../../../docs/ja/procedure-guidance-design.md).
Usage: [English](../../../../docs/en/procedure-guidance.md) /
[日本語](../../../../docs/ja/procedure-guidance.md).

Current state: stages 1/2 merged; W1 was approved and the complete Web stage is
implemented in PR #1349, pending independent latest-head review and CI.

Historical stages 1/2 mapping follows. D1–D4 and the three-PR grouping were approved by Eruhitsuji. Stage 1 (#1334–#1337)
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

Self-review and full-suite findings: event timestamps use the common injectable
timezone_policy.utcnow (not a new direct host clock). Postcommit blocked status
checks canonical source identity as well as exact bytes, including identical-byte
symlink retargets. Hash chains validate order/content but do not authenticate
history or prove an untruncated tail without trusted backup/journal evidence.

## Stage 3 read-only Web and historical write decision (superseded by W1 below)

Stage 2 merged as #1347 into 18d5c905; the owner requested continuation.
The final planned branch is feature/1343-procedure-web → main. #1342 is the
bounded definition browser. #1343 still needs the explicit server actor/ownership
contract required by change.yml. W1 is fully specified in
[web-write-contract.md](web-write-contract.md), including identity, credential
sharing, source/log selection, ownership, allowed operations and recovery. No
Web run endpoint or auth change is implemented before W1 approval. Continue the
same draft PR after approval to preserve the three-PR delivery grouping.

The new procedure_web adapter uses the existing configured read sources and
canonical ID policy. It accepts source tokens rather than paths, projects one
file/root with the existing validator, and returns procedure-v1. Catalog parsing
reuses the extracted bounded read_procedure_source helper; existing CLI behavior
is unchanged. Source paths/details are excluded from HTTP output. Existing
read-only and Bearer middleware remain authoritative. Procedure routes are
GET-only; their revision middleware boundary rejects unsafe methods through
normal route dispatch instead of allocating a generic template transaction.

The dedicated UI is packaged with the wheel; More contains one link. All server
text enters textContent and DOM APIs, with no Markdown/HTML/Mermaid evaluator.
No CDN or mandatory renderer dependency. SVG nodes/edges are data-only and link
to a complete keyboard-accessible step list containing hierarchy, instructions,
previous/next and definition status. Large valid graphs fall back to that complete
list. Deep links bind configured source token and root ID, language is en/ja, and
stale asynchronous responses cannot replace a newer selected definition. No run
or Task state is represented by a definition status. No template/log/task writes,
new config, Remote/MCP capability or automated action.

## W1 run implementation

W1 is approved. procedure_run_web.py isolates the authenticated transport and
ownership projection from the existing pure/run-store layers. GET and POST use
server-selected configured source and sidecar; owner checks run both before and
after receipt/run inspection. Closed JSON is streamed with an 8 KiB limit and
rejects duplicate keys, non-string operation tokens, boolean sequences and extra
actor/path fields. Origin/Fetch Metadata and exact displayed source If-Match are
checked before write_run. The existing store enforces the independent log CAS,
request uniqueness, source/root/actor/current step/sequence and durable journal.
Uncertain outcomes return path-free recovery guidance; receipts never replay.

procedure_run_web.js is assembled inside the dedicated page's existing closure,
so credentials are in memory only. All operations freeze a displayed snapshot
before the first async yield and disable the entire control group. A pending
request blocks further mutations until its read-only receipt is inspected.
Selection generations and source/root checks prevent delayed responses painting
a different selected procedure. Reload preserves only run ID and requires token
entry again. Pause/abandon remain on the original run after definition changes.
Definition-only and explicit-run sections are separate, with textContent-only
instructions, mobile wrapping, keyboard controls and status announcements.
