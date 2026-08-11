# Revision, Timezone, and Workspace Safety

この文書は public Web/MCP revision foundation と executable release policy の後に追加された P0 safety layer を説明します。

## Persistent revision migration telemetry

Web server は 2 modes を support します。

- `observe`: legacy Web writes without revision を一時的に accept し、fallback を persist して deprecation headers を返す。
- `required`: supported life.txt write は `If-Match` または `X-Lifetxt-Expected-Revision` を必須にし、missing precondition は HTTP 428 で fail する。

```json
{
  "web": {
    "revision_mode": "observe",
    "revision_metrics_path": ".cache/lifetxt/revision-metrics.json",
    "revision_migration_window_days": 14
  }
}
```

`lifetxt safety revisions life.txt --pretty` は fallback count、endpoint counts、observation start/latest fallback time、zero-use window、`ready_to_require_revisions`、metrics file revision を report します。reset は destructive operational state なので exact metrics revision が必要です。

## Shared timezone policy

resolved timezone の precedence は次の通りです。

1. CLI `--timezone` override
2. `#! timezone:` file directive
3. `defaults.timezone` in configuration
4. host timezone

CLI、extended CLI commands、Web requests、MCP JSON-RPC requests、legacy comparison helpers は resolved timezone context を共有します。

```bash
lifetxt safety timezone life.txt --pretty
lifetxt safety timezone life.txt --sample 2026-11-01T01:30 --fold-policy later --pretty
```

offset-aware datetimes は authored instant を保持し、display/comparison で resolved timezone へ convert されます。naive datetimes は resolved timezone の wall time として interpret されます。DST folds/gaps は default `error` です。

## Compensated multi-target transactions

`lifetxt.multi_target` は複数 file に影響する operation 用の dependency-free transaction contract です。timer JSON state plus life.txt item、attachment create/update/delete plus life.txt reference などが対象です。

implementation は absolute path order で locks を取得し、expected revisions を verify し、replacement を stage/validate し、targets を commit/verify し、later target failure 時には reverse order で compensate します。

これは unrelated files の portable filesystem-level atomicity を主張しません。current guarantee は in-process detection、ordered locking、preflight validation、verified commit、explicit compensation です。

## Workspace diagnostics and doctor

stable workspace diagnostics は malformed metadata directive、indentation issues、invalid timezone directive、duplicate IDs、dangling links、dependency cycles、corrupt timer state、unsafe write target、persisted fallback use、corrupt telemetry などを report します。

```bash
lifetxt doctor life.txt \
  --archive archive.txt \
  --timer-state .cache/lifetxt/timer.json \
  --revision-metrics .cache/lifetxt/revision-metrics.json \
  --pretty
```

stale lock cleanup は read-only plan が default です。actual removal には `--cleanup-stale` と `--force` が必要です。

## Practical migration sequence

1. `lifetxt safety timezone` を実行し、resolved timezone source を確認する。
2. Web revision mode がまだ `observe` の間に `lifetxt safety revisions` を実行する。
3. clients を revision discovery と `If-Match` に migrate する。
4. complete zero-fallback observation window を待つ。
5. report が `ready_to_require_revisions` を示した後だけ Web revision mode を `required` に切り替える。

## Scope boundaries

observe mode removal、既存 CLI/TUI handler migration、public timer/attachment handler integration、durable crash-recovery journals、real terminal/browser/fzf/SMTP verification、すべての direct `datetime.now()` boundary replacement は残る work です。
