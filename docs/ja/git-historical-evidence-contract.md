# 共有 Git historical evidence contract

Status: #725 / #726 / #729 / #730 向けの reader と 2 つの consumer を実装済み。

## Decision

`lifetxt/historical_temporal.py` に既に存在する `historical_snapshot()`（exact
revision）と `select_revision_as_of()`（committer-time cutoff）が、Temporal
Thread 以外の read model からも再利用できる共有・surface-neutral な
**HistoricalSnapshot** primitive である。repository identity、requested
selector、resolved full commit SHA、evidence mode
（`git_exact_revision` / `git_as_of`）、tracked-path membership、working tree
への no-fallback、shallow/incomplete history の limitations は、すでにこの
2 関数で満たされている。

`lifetxt.historical_temporal.read_historical_snapshot(paths, key=..., revision=None, as_of=None, ref=None)`
が唯一新しく追加された統一エントリポイントである。`revision`/`as_of` のどちらか
一方のみを受け取り、既存 2 primitive をそのまま composition して同じ
`HistoricalSnapshot`（`repo_root`, `items`, `diagnostics`, `historical`）を返す。
repository/ref/as-of の第二の resolution policy は導入しない。

## Reuse boundary

```text
resolve_git_inputs / resolve_commit / select_revision_as_of
        |
        v
historical_snapshot()  (Git access のみ)
        |
        v
read_historical_snapshot()  (統一 selector -> HistoricalSnapshot)
        |
        +--> thread_from_snapshot() -> Historical Temporal Thread (#707/#709, 変更なし)
        +--> lifetxt show --revision/--as-of (#729)
        +--> lifetxt query --revision (#730)
```

Historical Temporal Thread 自身の呼び出し箇所は無変更である: `thread
--revision`/`thread --as-of`/`thread --diff` はすでに
`historical_snapshot()`/`select_revision_as_of()`/`thread_from_snapshot()` を
直接呼んでいたため、「shared reader を再利用する」ための移行作業は不要で、
挙動が変わっていないことを回帰テストで確認するのみで済んだ。

## Consumers

1. **`lifetxt thread ID --revision REV` / `--as-of RFC3339 [--ref REF]`**
   （既存、#707/#709） — 無変更。
2. **`lifetxt show ID --revision REV` / `--as-of RFC3339 [--ref REF]`**（#729）
   — 選択した commit 時点の item を表示する。その revision に target が存在
   しない場合はエラーとし、current item へは決してフォールバックしない。
3. **`lifetxt query QUERY --revision REV`**（#730） — 既存・無変更の Query
   Language を、選択した commit の tracked bytes に対して評価する。
   `--format json` は `--revision` 指定時のみ結果を
   `{"historical": ..., "items": [...]}` で包む。それ以外の呼び出しは無変更。
   この最初の `query` slice では `--as-of` は意図的に scope 外。

## Multi-file / workspace semantics

選択した commit に存在する tracked bytes のみを読む。選択した commit に
存在しない requested source path は `missing_paths` / `limitations` として
報告され、working tree から補完されることはない。複数 repository を跨ぐ
入力は引き続き拒否される。generated/untracked/external source を historical
evidence として推測することはない。

## Disclosure risk（記録のみ、未対応）

Git history には current `life.txt` からすでに削除された private record や
過去の値が残っている場合がある。将来 server / Remote Safe Mode で historical
evidence を公開する際は、current read permission をそのまま流用するのではなく、
この `HistoricalSnapshot` 形状に対する独自の authorization/visibility policy
を定義しなければならない。その作業は別途追跡されており、本 contract では
実装しない。

## Remaining boundary

revision listing / history browsing helper は存在せず、いずれの consumer も
必要としていない。server/API 公開、MCP/Web/TUI rollout、Git mutation、
Native Semantic History との merge は、明示的な未実装のフォローアップとして
残る。
