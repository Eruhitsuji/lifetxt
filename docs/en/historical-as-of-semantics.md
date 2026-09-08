# Historical `as-of` semantics

Status: Phase 3 investigation result for #699 / #702.

## Decision

lifetxt cannot yet expose a general `lifetxt as-of DATE` command from the
current file alone. The current file is authoritative for **now**, but it does
not prove which values or future plans existed at an earlier date. A date in an
item is domain time, not evidence that the item was already recorded then.

Historical output is authoritative only when it is reconstructed from one of
the evidence sources below and names that source and revision explicitly.

## Evidence inventory

| Source | What it can prove | Boundary |
| --- | --- | --- |
| Git blob/tree at an exact commit | The complete tracked life.txt bytes at that revision | Commit time is repository evidence, not necessarily domain/event time; uncommitted and external files are absent |
| Git history selected by a cutoff | The latest reachable commit at or before the cutoff | Requires an explicit repository/ref and deterministic author-vs-committer timestamp policy; rewritten/shallow history may be incomplete |
| `record:ticket_event` / `record:time_entry` | Fields and activity represented by a complete validated event chain | Cannot reconstruct unrelated item fields or pre-chain state; no backfill may be invented |
| `record:progress_event` | Progress boundaries represented by a complete validated chain | Proves progress only; an unavailable baseline remains unavailable |
| undo snapshots, current revision hashes, transaction journal | Conflict/recovery evidence for their documented retention window | Not a durable historical database and not a supported general as-of source |
| current life.txt dates (`on:`, `due:`, `created:`, etc.) | Domain dates currently asserted | Do not prove that the assertion existed at the requested historical time |

## Safe implementable subsets

1. **Git-revision view**: parse the exact life.txt bytes from a caller-selected
   commit and label the result with repository, ref/commit SHA, selected time
   policy, and completeness caveats. This is a future feature and must not
   silently fall back to the working tree.
2. **Typed event-history views**: reconstruct only the fields whose validated
   append-only event contract defines a complete chain, as progress delta does
   today. Missing baselines are reported as unavailable.
3. **Current temporal thread**: `temporal-thread-v1` describes current
   authoritative lifecycle assertions plus current derived date context. It is
   not historical reconstruction.

## Required contract before a general command

A future implementation issue must define: evidence-source selection; Git
repository/ref and timestamp policy; multi-file membership at a revision;
history completeness and retention flags; timezone/cutoff semantics; behavior
for untracked/generated/external files; output provenance; and deterministic
errors when evidence is missing. If non-Git historical reconstruction is
required, a new append-only item-change history contract is needed first.

Until that contract exists, there is deliberately no general `as-of` CLI/API/
MCP surface. Consumers must not infer historical state from current items or
from `follows:`/`realizes:`/`replaced_by:` edges.
