# Shared Git historical evidence contract

Status: implemented reader plus two consumers for #725 / #726 / #729 / #730.

## Decision

`lifetxt/historical_temporal.py`'s pre-existing `historical_snapshot()` (exact
revision) and `select_revision_as_of()` (committer-time cutoff) are the
shared, surface-neutral **HistoricalSnapshot** primitives every non-Temporal-
Thread read model reuses. They already satisfy the shared contract this
project's historical-evidence roadmap called for: repository identity,
requested selector, resolved full commit SHA, evidence mode
(`git_exact_revision` / `git_as_of`), tracked-path membership, no working-tree
fallback, and shallow/incomplete-history limitations.

`lifetxt.historical_temporal.read_historical_snapshot(paths, key=..., revision=None, as_of=None, ref=None)`
is the one new unified entry point: given exactly one of `revision`/`as_of`,
it composes the two existing primitives unchanged and returns the same
`HistoricalSnapshot` shape (`repo_root`, `items`, `diagnostics`, `historical`).
It introduces no second repository/ref/as-of resolution policy.

## Reuse boundary

```text
resolve_git_inputs / resolve_commit / select_revision_as_of
        |
        v
historical_snapshot()  (Git access only)
        |
        v
read_historical_snapshot()  (unified selector -> HistoricalSnapshot)
        |
        +--> thread_from_snapshot() -> Historical Temporal Thread (#707/#709, unchanged)
        +--> lifetxt show --revision/--as-of (#729)
        +--> lifetxt query --revision (#730)
```

Historical Temporal Thread's own call sites are unmodified: `thread
--revision`/`thread --as-of`/`thread --diff` already called
`historical_snapshot()`/`select_revision_as_of()`/`thread_from_snapshot()`
directly, so no migration was needed to satisfy "reuse the shared reader" --
only regression testing that it stayed unchanged.

## Consumers

1. **`lifetxt thread ID --revision REV` / `--as-of RFC3339 [--ref REF]`**
   (existing, #707/#709) — unchanged.
2. **`lifetxt show ID --revision REV` / `--as-of RFC3339 [--ref REF]`** (#729)
   — shows the item as it existed at the selected commit. A target missing
   at that revision is an error, never a fallback to the current item.
3. **`lifetxt query QUERY --revision REV`** (#730) — evaluates the existing,
   unmodified Query Language against the selected commit's tracked bytes.
   `--format json` wraps the result in `{"historical": ..., "items": [...]}`
   only when `--revision` is given; every other invocation is unchanged.
   `--as-of` is intentionally out of scope for this first `query` slice.

## Multi-file / workspace semantics

Only tracked bytes present at the selected commit are read. A requested
source path missing at that commit is reported via `missing_paths` /
`limitations`, never silently filled from the working tree. Multiple
repositories in one input set remain rejected. Untracked, generated, or
external sources are never inferred into a historical result.

## Disclosure risk (recorded, not yet addressed)

Git history can retain values a current `life.txt` no longer has (deleted
private records, prior field values). A future server/Remote Safe Mode
historical disclosure surface must define its own authorization/visibility
policy against this `HistoricalSnapshot` shape rather than assuming current
read permission transfers unchanged. That work is tracked separately and is
not implemented by this contract.

## Remaining boundary

No revision-listing/history-browsing helper exists; neither consumer needs
one. Server/API exposure, MCP/Web/TUI rollout, Git mutation, and merging
Native Semantic History with Git evidence remain explicit, unimplemented
follow-up work.
