# Design: Shared Git historical workspace snapshot reader

## #725 investigation findings

Reading `lifetxt/historical_temporal.py` (the module #707/#708/#709 already
built) before writing any code found that the shared contract #725 asked to
define largely **already exists**:

- `historical_snapshot(paths, revision, key=..., resolved_commit=None,
  metadata=None)` already resolves an exact commit-ish to a full commit SHA,
  reads only tracked bytes at that commit, never falls back to the working
  tree, and returns `repo_root`/`items`/`diagnostics`/`historical`
  (`mode`, `requested_revision`, `resolved_commit`, `requested_paths`,
  `loaded_paths`, `missing_paths`, `evidence_complete`, `limitations`).
- `select_revision_as_of(paths, cutoff, ref=None)` already resolves a
  committer-time cutoff to one selected commit, deterministically
  (`maximum_full_sha` tie-break), and reports `history_complete` /
  `limitations` for a shallow repository.
- `lifetxt/cli.py`'s own `command_thread` (`--diff`) already calls
  `historical_snapshot`/`thread_from_snapshot` directly rather than through a
  second Git-loading path, confirming the existing module already separates
  Git access from Temporal Thread's own domain composition
  (`thread_from_snapshot`).

So the answer to #725 question 2 (reuse boundary) is: **`historical_snapshot`
and `select_revision_as_of` are already the shared, surface-neutral
primitives.** No duplication exists to extract. The one genuine gap is a
*unified* entry point: a caller wanting either an exact revision or an as-of
cutoff currently has to know to call two different functions in the right
sequence (as `historical_temporal_thread_as_of` itself does). That gap is
closed by `read_historical_snapshot()` (#726), a thin wrapper with the exact
same two-primitive composition already proven by Temporal Thread's own as-of
path -- it introduces no second repository/ref/as-of resolution policy.

## Answers to #725's five questions

1. **Minimal responsibilities of the shared snapshot** — already satisfied by
   `historical_snapshot`'s existing return shape (see above). No new fields
   were needed.
2. **Reuse boundary** — `historical_snapshot`/`select_revision_as_of` are the
   shared primitives; `thread_from_snapshot` (which applies
   `temporal_thread()`) is the Temporal-Thread-specific composition layer
   and stays there, unmoved.
3. **Revision catalog / history listing** — not needed for this slice. Both
   selected consumers (`show`, `query`) resolve exactly one revision or one
   as-of cutoff; neither browses history. Deferred until a consumer
   demonstrates the need.
4. **Workspace / multi-file semantics** — unchanged from the existing
   primitives: only tracked bytes at the selected commit are read; a
   requested path missing at that commit is reported via `missing_paths`/
   `limitations`, never silently filled from the working tree; multiple
   repositories remain rejected by the existing `resolve_git_inputs`.
5. **First non-Temporal-Thread consumer** — `lifetxt show --revision`/
   `--as-of` (#729), the cheapest and highest-value per #725's own
   recommendation criteria. A second consumer, `lifetxt query --revision`
   (#730), was implemented in the same pass once the shared seam made it
   trivially small (matching #730's own allowance to fold in `--as-of` "if
   the reusable selector is small enough to reuse safely in the same
   issue" -- here it was `query`'s exact-revision v1 slice that stayed
   deliberately narrow, per #730's own scope).

## Security / disclosure considerations (recorded per #725, not implemented)

Git history can retain records/values a current `life.txt` no longer has
(deleted private records, prior field values). Reusing a current read
permission check for historical evidence is not automatically sufficient.
Before any server/Remote Safe Mode historical disclosure (#727/#728) ships,
that follow-up work must define its own authorization/visibility policy
against this same `HistoricalSnapshot` shape rather than assuming current
policy transfers unchanged. This package does not implement that policy;
#727/#728 remain open, higher-assurance follow-up work.

## Follow-up decomposition

Per #725's request to decompose into 1-3 XS/S issues, the pre-filed issues
#726 (reader), #729 (show), #730 (query) matched this decomposition exactly
and needed no further splitting.
