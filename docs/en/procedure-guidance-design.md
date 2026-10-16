# Human procedure guidance: proposed v1 contract

Status: **proposal awaiting Eruhitsuji's approval**, not a Format 1.0 amendment
or a shipped feature. Phase 0 / #1333; parent #1332. The Japanese counterpart
is [procedure-guidance-design.md](../ja/procedure-guidance-design.md).

## Decision request

Recommend approving D1–D4 together: D1 note-based opt-in profile and same-file
scope; D2 explicit human transitions and bounded loops; D3 separate native
domain-event authority with exact source/run revisions; D4 first release through
#1337 (definition, validation, diagrams), then separately release run support.
Alternatives and risks follow. Approval must identify this contract revision;
requesting implementation generally does not settle these new public/data contracts.
No approval is recorded yet. Final merge, release and deployment remain separate.

Rules: CTX-HUMAN-001, CTX-ASSURE-001, TASK_DECOMPOSITION unit of work,
AI_HUMAN_INTERACTION human approval for public API/data model changes.

## D1: Definition, compatibility and alternatives

| Option | Benefit | Cost / decision |
| --- | --- | --- |
| `[N] N` plus `proc_*` | Existing parser/body/ID/parent; not a Task | Recommended; general Notes views still show definitions |
| `[ ] T` template | Familiar checklist | Mixes reusable template with work completion; reject |
| Separate file of ordinary Notes | Keeps Notes lists smaller | Supported placement, not a new format; explicit file selection |
| New item type or separate DSL | Strong dedicated syntax | Breaks old clients or adds a second parser; defer |

No extension of KNOWN_KEYS or global `check` validation is proposed. Generic
Format parsing stays permissive; W106 for custom `proc_*` is expected. A normal
check succeeds with warnings; `--warnings-as-errors` fails. Passing generic check
does **not** validate procedure semantics. Legacy clients preserve keys through
supported text/JSON/JSONL serialization but cannot navigate/run procedures.
Third-party tools that discard unknown fields are unsuitable editors; retain a
backup and compare before replacing the source. Comments/spacing need not
roundtrip byte-for-byte. IDs, bodies and repeated values must roundtrip semantically.

Only explicit `proc_role:root` or `proc_role:step` opts an item in. Records with
unrelated custom keys, normal Tasks, `next:`, VM instructions and ordinary Notes
must not be reinterpreted. Profile validation runs only in procedure commands.
A selected definition requires `[N] N`, one canonical `id` per record, and exactly
one value for every profile field except `proc_case`. A configured alternate ID
key is rejected in v1 rather than silently mixing identities.

| Draft key | Allowed owner / cardinality / meaning |
| --- | --- |
| `proc_role` | root or step; one |
| `proc_version` | root only; exactly `1`; unknown version blocks interpretation |
| `proc_start` | root only; exactly one step ID |
| `proc_kind` | step only; exactly action, decision or end |
| `proc_next` | action only; exactly one step ID |
| `proc_case` | decision only; 2–16 repeated `label=STEP_ID` values |

Choice labels match `[a-z][a-z0-9_-]{0,31}` and are case-sensitive ASCII tokens;
no whitespace, expressions or evaluation. Targets use the existing canonical ID
rules; split `proc_case` at its first `=` and reject empty/invalid targets.
Human-readable translations belong in body text; labels retain stable identity.
Unknown `proc_*` keys on an opted-in record are profile errors (catch typos).
Other custom keys remain preserved, data-only attributes.

All steps belong to exactly one selected root through a single explicit `parent`
chain; ancestors are step or root Notes. No multiple parents, cycles, nested roots,
or implicit attachment by adjacency. Nested steps describe presentation hierarchy,
not implicit calls/returns. Input order determines display order, never execution
order. Explicit `parent` wins over indentation under current parser rules; the
profile requires the resulting parent to be unambiguous. Root has no `parent`.

V1 takes one explicitly selected file, not a workspace glob. Index all IDs in that
file and reject any duplicate that could make selection ambiguous. Every target
must be an opted-in step under the same root in that file. No cross-file/root
jumps or URL/path resolution. Other files may contain the same IDs safely because
the source handle is part of identity. CLI refuses multiple input files; Web uses
its authorized source resolver, never a client-supplied filesystem path. Multiple
roots in one file are legal; exactly one is selected by `--id` with no default.

## Draft canonical example (not executable by current CLI)

```text
[N] N "Server maintenance" id:p_update proc_role:root proc_version:1 proc_start:s_check
[N] N "Inspect service" id:s_check parent:p_update proc_role:step proc_kind:action proc_next:s_backup
| Check service health and free space. Continue only after checking.
[N] N "Take backup" id:s_backup parent:p_update proc_role:step proc_kind:action proc_next:s_update
[N] N "Update manually" id:s_update parent:p_update proc_role:step proc_kind:action proc_next:s_verify
[N] N "Verification result" id:s_verify parent:p_update proc_role:step proc_kind:decision proc_case:ok=s_done proc_case:ng=s_rollback
| Choose ok or ng yourself; no command or condition is evaluated.
[N] N "Complete" id:s_done parent:p_update proc_role:step proc_kind:end
[N] N "Roll back manually" id:s_rollback parent:p_update proc_role:step proc_kind:action proc_next:s_verify
```

## D2: Transitions, refusal and limits

An action advances exactly one edge on explicit `next`; a decision advances one
edge on explicit `choose LABEL`. An end has no outgoing edges and requires explicit
`finish` to mark its run completed. No operation runs the written instructions.
Reading, displaying a graph or reaching an end never creates/completes a run.
No-op means a refused/absent operation with no event or state change, not an end.
An action without a next is invalid, never implicit completion. Pause/resume do
not traverse an edge; resume requires paused state and returns to the same step.
Abandon is terminal. Completed/abandoned runs reject all mutation; `show` works.
No undo/backtracking: start a distinct run to repeat work, preserving old evidence.

| Counterexample | Required proposed response |
| --- | --- |
| `proc_next:missing`, duplicate IDs, target in another root/file | Reject; never guess or load the target |
| Two starts, repeated singleton, multiple parents | Reject; never pick first/last silently |
| Decision with no cases, duplicate label, `OK` when only `ok` exists | Reject; no default branch |
| `proc_case:"disk_free>10=s_done"` | Invalid label, never evaluate expression |
| Action with cases / end with next / unknown version or kind | Reject incompatible profile fields |
| Unreachable step | Error; show diagnostics with source line, do not emit a usable graph |
| Reachable closed cycle with no route to an end | Error; every reachable step must have some route to an end |
| Cycle with an exit, including self-loop decision with an exit | Warning for viewing; explicit loop acknowledgement required at start |
| Missing next on action | Error, not no-op/end |
| Generic `depends_on`, `follows`, VM `next` | Retain their existing meanings; never procedure edges |
| Source edited during a run, even only comments | Source revision mismatch; block mutations, retain evidence |

Every run has hard guards: at most 1,000 successful edge traversals and 20 visits
to each step, counting the start visit. A transition that would exceed a guard is
refused without event; pause/abandon remain available. Loop acknowledgement never
raises guards. `start --allow-loops` is required for a cyclic definition, with Web
an equivalent explicit checkbox; reaching a limit offers inspection/abandon/new
run, never automatic restart. `finish` at an end uses no edge traversal.

Projection/validation limits: 10,000 parsed records per input; selected definition
at most 500 steps, 2,000 edges, parent depth 32; source at most 10 MiB; body per
step at most 64 KiB; graph output at most 2 MiB. Fail before partial usable output;
do not truncate a graph into an apparently valid procedure. Indexed resolution,
reachability and reverse end reachability are O(V+E); iterative traversals avoid
recursion limits. Preserve file order and case order; diagnostics sort by source
line then stable code. Renderers use local ordinal node IDs (avoiding sanitized-ID
collisions) and format-specific escaping; existing quoting helpers require tests
for labels/newlines/collisions, not blind reuse. No embedded links, scripts or HTML.

## D3: Revision, evidence and storage authority

Definition identity is (authorized source handle, root ID, profile version).
`template_revision` is SHA-256 of the **exact UTF-8 source bytes**, using
`mutation.read_text_snapshot`, not serialized items, mtime, Web ETag or item hash.
Store a stable source handle, not an absolute/private path in exported events.
A run binds the full source revision at start; any source edit blocks next,
choose, resume and finish. Pause/abandon may record disposition against the
original bound revision, without resolving changed step content. The old run
remains inspectable by IDs and events, but cannot continue on a changed definition.
There is no automatic migration or frozen-body copy. Restore the exact original
file from an operator-owned backup before resuming, or abandon/start a fresh run.

Native History's closed `item_event` vocabulary is not extended or impersonated.
Propose a new native **domain** `record:procedure_event` (`[N] N`) in one explicit
run-log life.txt file distinct from the template. It is the sole run-state
authority, consistent with existing domain-event/native-history separation.
A future timeline adapter may project these events; generic item events must not
mirror them. No mutable run-status record, database or mandatory sidecar cache.

Proposed closed `procedure-event-v1` envelope: schema version, unique event ID,
run ID, sequence, transaction/request ID, UTC timestamp, actor ID, source handle,
root ID, template revision, event kind, previous-event digest and typed payload.
Start is sequence 1 with null previous digest and binds schema/version/guards,
loop acknowledgement and initial step. Subsequent events are exactly
`next`, `choose`, `pause`, `resume`, `finish`, `abandon`. Payload carries prior/next
step IDs and choice token only where applicable; no title, body, secret, URL,
command output or arbitrary user notes. Actor IDs are personal data: operator
access and backups must protect the log. Hash chaining detects accidental
corruption, not authenticated tamper-proof audit. This is a schema proposal, not
an implemented record format; exact field mapping/schema is a #1339 deliverable.

`procedure_run_model` reduces each validated ordered chain; derived status is
active/paused/completed/abandoned. Reject duplicate/gapped/reordered sequences,
unknown schema/event fields, wrong run/revision/previous digest, impossible step
or choice, guard mismatch, events after terminal state. UTC timestamps are not
the ordering authority. Start has a distinct run ID for every deliberate new run.
Replay is pure; it never reruns real-world operations. No state is recoverable
from a partial chain by guessing the missing operation.

The run-store uses the existing validated mutation/CAS/atomic writer with backup
and permissions. Compare exact template revision and exact run-log revision;
recheck the template immediately before committing the log, and report any
observed post-commit source change as a blocked run. A human editor does not share
an OS lock: do not claim portable atomicity across source+log. Every later
operation rechecks both. One append commits one logical event through atomic
whole-file replacement, not unsafe raw append. All writers to a shared log
contend on its file revision; distinct runs remain logically independent.
Require a unique request ID and expected step/sequence; a repeated request cannot
append twice. An uncertain response requires explicit reread: show the matching
committed event or a conflict, never automatic retry. Initial missing-log creation
uses the existing missing-state precondition, not an arbitrary empty-file hash.

Limit one run to 5,000 events and a log to 50,000 events / 32 MiB; reject before
writing beyond limits. Replay must validate bounds before materialization and
remain O(events). Rotation/compaction and retention automation are deferred;
operator may use a new explicit log for new runs, retaining old logs for old runs.
Never split an active chain. A corrupt log is read-only; recovery restores a
verified complete backup using existing operator recovery, preserving damaged
bytes. Interrupted commits must resolve to the old or new complete log under the
existing writer contract; journal uncertainty blocks writes. Revert software
without deleting template/logs; old clients can inspect Notes but cannot write
runs. No migration, rollback or data deletion is authorized by this document.

Web authorization is checked server-side for every read and mutation: visibility
of the definition/steps plus run-log access, write permission and actor ownership
for mutation. Bind actor from authenticated server context, not supplied JSON.
An operator identity is explicit for local CLI. Without trustworthy Web identity,
run writes stay disabled; existing source permissions alone cannot establish
per-run ownership. New auth policy is outside this Epic. Use existing If-Match
middleware plus distinct template/run-log revision preconditions; ETag never
upgrades a frozen form. Read-only pages perform GET only. CSRF/origin policy,
path confinement and sensitive error redaction reuse server boundaries. Missing,
hidden or unauthorized resources must not reveal bodies or private paths.

## Threat model and residual risk

Untrusted definitions, graph labels, URL input and concurrent editors are inputs.
Mitigate injection by escaped data-only text, explicit choice allowlists, ordinal
graph IDs, no eval/process/HTTP/MCP calls, no remote Mermaid service, and bounded
input/output. Secrets belong outside templates and logs: hashes do not redact a
source that already contains secrets. Authorized definition readers can see its
body; exports need the same privacy review as their source. Denial of service,
symlink/path escape, stale forms, two-tab/double-click and uncertain writes need
negative tests. Browser clipboard/download is explicit. No background execution,
notifications or remote sharing. Limits and CAS reduce risk but do not certify
instructions or real-world completion; the human remains responsible for actions.

## UX and rollout (all new commands are proposals)

Text editor only: read the Note template unchanged; create separate `[ ] T`
checklist records in a work file per occurrence with unique IDs and `ref:` links.
Write choices and interruption context manually in that work file. This does not
produce machine-verifiable run events. #1334 supplies bilingual baseline examples
using existing keys only; a separate opt-in example may demonstrate `proc_*`.

CLI: propose `procedure show FILE --id ROOT` (text default),
`procedure graph FILE --id ROOT --format text|mermaid|dot`, and
`procedure run start|show|next|choose|pause|resume|finish|abandon`.
Read commands never create logs. A write takes explicit source/log, run ID (start
returns a new ID), request ID, expected template/log revision and expected
step/sequence. No TTY default choice; missing arguments refuse. JSON/public
schema exposure is deferred until High contract approval; internal projection
is `projection-v1`, future Web adapter is `procedure-v1`, transition result is
`transition-v1`. These names are distinct boundaries, not interchangeable schemas.

Web: reuse record deep links and graph presentation, with text hierarchy,
keyboard controls, accessible status and 390 px viewport checks. Read view has
no run controls; explicit execution mode shows run/source revision and current
step. Reload/timeout rereads state; conflicts retain choice/context for review
but do not replay. Hide mutation controls for read-only/unauthenticated contexts.

Phase 1 alone (#1334/#1335) is a useful intermediate read view but lacks strict
branch validation/diagrams: label it explicitly as definition browsing if shipped.
Recommend initial user-facing release through #1337 so branches and diagrams
agree; run support and Web are later releases, with their own approvals. No
release number/tag or deployment is selected here.

## Child implementation contract and acceptance matrix

All branches begin at then-current origin/main; one Issue/branch/PR each, final
base main. No integration branch needed for this sequential plan. Maintainer
Eruhitsuji owns requirements and merge; Codex executes; human independent review
is pending. Add required CAPABILITIES/TRACEABILITY and package records in each
implementation contract before Ready. This Phase 0 write scope excludes global
registry edits, production code, normative Format specs and runnable fixtures.

| Issue | Dependency after #1333 approval/merge | Scope boundary | Assurance / proof |
| --- | --- | --- | --- |
| #1334 | none | ja/en guide, examples only | Quick: two independent occurrences, generic check |
| #1335 | none | procedure_definition.py, focused test, minimal CLI show dispatch | Standard: stable hierarchy/source/order/bounds, parser/links regressions; no public JSON schema |
| #1336 | #1335 | procedure_validation.py + focused test; no generic validator changes | High: choice/termination/loop/bounds/negative fixtures |
| #1337 | #1336 | procedure_graph.py, minimal graph dispatch, tests, ja/en CLI | Standard: text/Mermaid/DOT equivalence, injection/collision, subprocess |
| #1338 | #1336 | procedure_transition.py + focused test only | High: pure transition table, guards/stale revision, no I/O |
| #1339 | #1335 | procedure_run_model.py, schema, tests, design records | High: closed domain-event mapping, roundtrip/replay/privacy/corruption |
| #1340 | #1338/#1339 | procedure_run_store.py, thin transaction adapter, fault tests | High/M: CAS and crash recovery form one atomic-event contract |
| #1341 | #1340 | procedure_cli.py, minimal dispatch, tests, ja/en guide | High: non-TTY start/choose/pause/restart/resume/finish, duplicate request |
| #1342 | #1337 | procedure-only Web adapter/assets, minimal registration, tests | High if new endpoint: GET-only auth/XSS/390 px/keyboard/browser |
| #1343 | #1341/#1342 | procedure-only write adapter/UI, targeted tests | High/M: owner auth, two runs/tabs, stale forms, fault/browser recovery |

Recommended numerical work order: #1333 → #1334 → #1335 → #1336 → #1337 →
#1338 → #1339 → #1340 → #1341 → #1342 → #1343. Dependencies permit some
parallelism but this request will be handled sequentially. Shared cli.py/Web
registration is limited to dispatch/resource hooks; no planner/top redesign.
Before each task, refine exact existing-file paths and schema mapping in that
Issue, confirm size/High acceptance and dependencies merged, then mark Ready.
Approval of Phase 0 does not assert unrun downstream tests passed or waive
latest-head independent reviews, CI, feature-freeze policy or merge approval.

## Source and duplication audit (main 204fc69e0796a29e8ecf98fa822e64fd866ac028)

| Existing source / Issue | Reuse | Boundary / evidence |
| --- | --- | --- |
| Format spec; parser.py, serializer.py, validator.py; tests/test_roundtrip_golden.py | Note/body/custom key/ID/parent and interchange | W106 is advisory, no procedure semantics |
| cap-graph-link-foundation; links.py; tests/test_links.py | ID index, graph formatting primitives | Relation edges remain relations; sanitized IDs can collide |
| #1140; docs/en/text-editor-only-workflow.md (ja counterpart) | restricted editor workflow | Procedure template/run example is additional, not duplicated weekly guide |
| #562; vm.py; tests/test_vm.py, tests/test_vm_cli.py | diagram construction/escaping experience | VM CFG/opcodes and execution not reused semantically |
| #563; webapp.py, mcp.py; tests/test_mcp_expansion.py | existing filtered graph presentation | No procedure MCP exposure or temporal-edge mixing |
| #564; links.py topological_order/critical_path/shortest_path | iterative/indexed graph techniques | Procedure cycles are bounded human paths, not a task DAG |
| #565; integrity.py; tests/test_integrity.py | read-only diagnostic pattern | No new generic integrity repair |
| #835; docs/en/web.md, Web item route | canonical record deep links | No host URL stored as definition identity |
| #1296; work_session.py, web_assets_js_22.js; tests/test_work_session_v4.py | frozen revisions, double-submit and transaction UI patterns | Timer/work-session state never becomes a procedure run |
| cap-native-semantic-history; native_history.py; docs/en/native-semantic-history.md; tests/test_native_history.py | domain-event authority and provenance principles | item_event closed vocabulary cannot accept procedure transitions |
| mutation.py; tests/test_safety_foundation.py; docs/en/web.md | exact source-byte snapshot, CAS, validated atomic write | File/source/run/HTTP revisions are distinct preconditions |

All seven related Issues were fetched and are closed. Closed tracker checkboxes
are not implementation evidence; source/tests above ground reuse decisions.
Current generic checks/roundtrip results are retained in the change package's
verification record. Proposed semantic rejection, persistence and browser behavior
remain unimplemented and are acceptance plans, not passed tests.
