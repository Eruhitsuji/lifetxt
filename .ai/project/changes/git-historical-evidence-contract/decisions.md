# Decisions

- **No human was available to synchronously answer #725's design questions.**
  Per the task's own explicit instruction, the design call was made
  autonomously and recorded here and in `design.md` rather than blocking.
  Independent human review before merge to `main` remains required (see
  `change.yml`'s `human_approvals_required`).
- **`read_historical_snapshot()` was added as a new function rather than
  modifying `historical_snapshot`/`select_revision_as_of` in place**, because
  Historical Temporal Thread's existing callers (`historical_temporal_thread`,
  `historical_temporal_thread_as_of`, and `cli.py`'s `--diff` path) already
  call those two primitives directly and correctly; changing their signatures
  would have risked the "zero regression" requirement #726 states explicitly.
  Leaving them untouched and adding a new composition function is the
  smallest change that satisfies both #726 (new shared entry point) and its
  own compatibility requirement (Temporal Thread unchanged).
- **No capability entry for `cap-lifecycle-temporal-thread` was edited.**
  That capability's own implementation and public interfaces are unchanged by
  this package (confirmed by full regression tests of
  `tests/test_historical_temporal.py`/`tests/test_temporal_diff.py`). A new
  capability, `cap-git-historical-read`, was created instead, since #729/#730
  demonstrate the shared reader is now genuinely public beyond Temporal
  Thread -- matching #726's own capability-impact guidance ("create a new
  reusable capability only if #725 explicitly decides the contract is
  independently public").
- **`query --revision`'s `--format json` output wraps items in a
  `{"historical": ..., "items": [...]}` envelope only when `--revision` is
  given.** Every other format, and the no-`--revision` case, are completely
  unchanged (locked in by `test_query_current_behavior_is_unchanged_without_revision`),
  matching #730's "current `lifetxt query` default behavior must not change"
  acceptance criterion.
- **`--as-of` was not added to `query` in this pass.** #730's own scope keeps
  v1 exact-revision-only; `--as-of` is left as an explicit, unimplemented
  follow-up rather than silently added beyond the issue's stated boundary.
- **Revision-listing/history-browsing helper was not built.** Neither `show`
  nor `query` needs it; adding one speculatively would violate #725's own
  "not an arbitrary Git log browser" non-goal.
- **#727/#728 (server disclosure) and #731 (commit worker) are not part of
  this package.** They are separate, higher-assurance issues with their own
  task contracts and are tracked as remaining work under the #724 epic.
