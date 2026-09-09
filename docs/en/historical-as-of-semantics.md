# Historical `as-of` semantics

Status: implemented Git-backed subset for #707 / #708 / #709.

## Decision

lifetxt does not reconstruct history from current item dates. The current file
is authoritative for **now**, but it does not prove which values or future
plans existed earlier. Git-backed historical thread modes are available only
when tracked bytes and their exact revision provenance supply that evidence.

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

## Implemented Git subset

1. **Exact revision**: `lifetxt thread ID --revision REV` resolves the
   commit-ish, reads only the requested paths present in its tree, and returns
   `temporal-thread-v1.historical` provenance. Missing paths make evidence
   incomplete; a missing target or revision is an error without fallback.
2. **Semantic diff**: `--diff REV_A..REV_B` compares two normalized historical
   threads as `temporal-diff-v1`. It distinguishes item/state, explicit edge,
   consistency, and derived changes and ignores serialization order.
3. **Git as-of selection**: `--as-of OFFSET_RFC3339 [--ref REF]` chooses the
   reachable commit whose committer timestamp is greatest and no later than
   the cutoff. `HEAD` is the default root; equal timestamps use maximum full
   SHA. Shallow history is explicitly incomplete.
4. **Typed event-history views**: reconstruct only the fields whose validated
   append-only event contract defines a complete chain, as progress delta does
   today. Missing baselines are reported as unavailable.
5. **Current temporal thread**: `temporal-thread-v1` describes current
   authoritative lifecycle assertions plus current derived date context. It is
   not historical reconstruction.

## Remaining boundary

The implemented contract is intentionally Git-only and CLI-only. Current input
resolution supplies the requested path manifest; untracked, generated, and
external sources are never inferred into a historical result. Git history
rewrite is not treated as independently verifiable truth, and a shallow clone
cannot claim complete selection history. Non-Git reconstruction still requires
a separately reviewed append-only history contract. TUI/API/MCP historical
surfaces remain future work.
