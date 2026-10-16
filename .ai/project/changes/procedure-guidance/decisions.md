# Decision ledger

| ID | Recommendation | Alternative / tradeoff | State |
| --- | --- | --- | --- |
| D1 | Notes + proc_*; same-file canonical IDs | Tasks mix template/run; new type/DSL harms compatibility; cross-file deferred | Awaiting owner |
| D2 | Explicit next/choice/finish, acknowledged exit-capable cycles with hard guards | No unbounded loops, automatic conditions or arbitrary execution | Awaiting owner |
| D3 | Separate procedure_event native domain log; exact source/log CAS | item_event is closed; mutable run state duplicates authority; frozen bodies copy private data | Awaiting owner |
| D4 | First release through #1337, runs/Web later | Phase 1-only is earlier but must be labeled definition browsing | Awaiting owner |

No approval recorded. Rules CTX-HUMAN-001 / CTX-ASSURE-001 apply. Record owner's
reviewed-commit decision on #1332 and #1333 before promoting children. Merging a
proposal is not itself schema approval. High is proposed for #1336/#1338/#1339/
#1340/#1341/#1343 and #1342 if exposing an endpoint; each task needs its exact
contract and owner acceptance before implementation. Merge stays human-only.

Self-review addressed graph ID sanitization collisions with ordinal node IDs,
and rejected a portable atomicity claim across externally editable template and
log: recheck before commit, and block subsequent operations on changed revision.
Self-review is not independent approval. No child implementation/release tests
are claimed passed.

## Owner approval and delivery grouping (2026-10-16)

D1–D4 were explicitly approved in the visible user instruction following merge
of PR #1345 into e76125ed. The earlier Awaiting owner cells above are the
historical proposal state, superseded by this approval. Records are linked from
#1332/#1333; #1333 is closed. Phase 0 approval does not claim downstream evidence.

The owner requested about three PRs to finish: (1) #1334–#1337, (2) #1338–#1341,
(3) #1342–#1343. This supersedes the earlier one-child-per-PR and intra-stage
merge dependencies. Representative Issues are #1335/#1340/#1343. Each stage is a
coherent M unit (complexity 6); stage 1 combines mutually dependent definition,
strict validation and diagrams so their public meaning is reviewed together.
Start each stage from current origin/main after the preceding stage merges;
base=main, no intermediate sub-PRs, no permanent next/develop branch. The
source/branch of stage 1 is e76125ed / feature/1332-procedure-readonly. Owner,
independent reviewer, integrator and merge authority: Eruhitsuji. Executor: Codex.

Read-only admission uses a bounded byte reader and mutation.hash_bytes (the
same primitive as read_text_snapshot), avoiding an unbounded allocation. A
minimal entrypoint dispatch follows existing flow's pattern: bypass speculative
timezone pre-reads because procedures perform no date calculations. FIFO input
proved the need; invalid files must be refused before any blocking read.
Generic reference diagnostics are not traversed during procedure admission;
only syntax is parsed, then the dedicated bounded graph/ID checks apply.

## Stage 2 implementation mapping

PR #1346 was merged into 99bd4491; owner requested continuation. This implements
#1338–#1341 under the approved D2/D3 and three-PR plan: feature/1340-procedure-run
from that main commit, base=main, High / M / complexity 6. The typed transition,
closed native event, single-log CAS/recovery and CLI form one acceptance boundary.

The exact envelope is procedure-event-v1.schema.json in this package. Start
freezes only control IDs/kinds/edges, not body/title/private paths, so stale source
runs can be replayed and disposed of without silently continuing a new template.
Single-line Note detail event_data stores canonical JSON. No Native item_event or
mutable status authority is introduced. Request ID is unique across the log;
explicit show --request-id returns the original committed receipt without retry.

The existing multi_target writer is reused for one log target with its existing
journal, exact revisions and fault/recovery policy. Template bodies are never
journal targets. Source is rechecked before commit, and postcommit changes return
blocked with the event retained. External editors are not part of a portable
cross-file transaction. CLI actors are attribution only; Web identity remains a
separate stage-3 server contract. Event-only schema is retained here, not added to
the general published schema catalog. Runtime validates graph/digest/sequence and
calendar semantics beyond structural JSON Schema.
