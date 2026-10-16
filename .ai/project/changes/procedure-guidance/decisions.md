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
