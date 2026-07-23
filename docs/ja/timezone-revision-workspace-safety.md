# Revision・Timezone・Workspace Safety

この文書では、公開Web/MCP revision基盤と実行可能release policyの後に追加されたP0 safety layerを説明します。

## 1. Revision移行telemetryの永続化

Web serverは次の2 modeを明示的にサポートします。

- `observe`: revisionを送らない旧Web clientを移行期間中だけ受け入れます。fallback利用はすべて永続化され、responseにはdeprecation headerが付きます。
- `required`: 対応するすべてのlife.txt書き込みに`If-Match`または`X-Lifetxt-Expected-Revision`を要求します。preconditionがない場合はcompatibility fallbackより前にHTTP 428で拒否します。

Modeと移行証拠を設定します。

```json
{
  "web": {
    "revision_mode": "observe",
    "revision_metrics_path": ".cache/lifetxt/revision-metrics.json",
    "revision_migration_window_days": 14
  }
}
```

対応する環境変数は次のとおりです。

```text
LIFETXT_REVISION_MODE
LIFETXT_REVISION_METRICS_PATH
LIFETXT_REVISION_MIGRATION_WINDOW_DAYS
```

Metrics pathを指定しない場合、書き込み対象のlife.txtと同じdirectoryの`.lifetxt-revision-metrics.json`を使用します。これはauthoritativeなlife.txtではなく運用stateです。

### 移行状況を確認する

```bash
lifetxt safety revisions life.txt --pretty
```

Reportには次が含まれます。

- fallback総数
- API endpoint別件数
- observation開始時刻と最終fallback時刻
- 設定されたzero-use期間
- `ready_to_require_revisions`
- metrics fileのrevision

Web APIは次のとおりです。

```http
GET /api/revision-metrics
GET /api/revision-metrics/export
```

Export responseには`metrics_revision`が含まれ、同じ値が`X-Lifetxt-Metrics-Revision`にも返されます。

### Observation windowをresetする

Resetは運用証拠を削除する操作なので、metrics fileの正確なrevisionが必要です。

```bash
lifetxt safety revisions life.txt \
  --metrics-path .cache/lifetxt/revision-metrics.json \
  --reset \
  --expected-hash <sha256>
```

Stale hashでは、新しい証拠を消さずconflictになります。

### Mode切替条件

Serverが`required`を実装しているという理由だけで切り替えないでください。対応clientをrevision discoveryと`If-Match`へ移行し、文書化したobservation windowを完了させ、`ready_to_require_revisions`がtrueになるまで待ちます。条件は次の両方です。

1. fallback利用が0件
2. 設定されたobservation期間が完了

## 2. 共通timezone policy

Timezoneの解決順序は次のとおりです。

1. CLI `--timezone`
2. workspaceの`#! timezone:`
3. configの`defaults.timezone`
4. host timezone

CLI、extended CLI、Web request、MCP JSON-RPC request、legacy comparison helperは同じ解決済みtimezone contextを使用します。

Policyを確認します。

```bash
lifetxt safety timezone life.txt --pretty
```

Sampleを解釈します。

```bash
lifetxt safety timezone life.txt \
  --sample 2026-11-01T01:30 \
  --fold-policy later \
  --pretty
```

### 値の解釈規則

- Offset付きdatetimeはauthorが指定した瞬間を保持し、表示・比較時に解決済みtimezoneへ変換します。
- Naive datetimeは解決済みtimezoneのwall timeとして解釈します。
- Time-only値はtimezone変換前に明示的なdateへanchorします。
- `Asia/Kathmandu`の`+05:45`など、非整数時間offsetも保持します。

### DST fold

同じwall timeが2回現れる場合は曖昧です。defaultは`error`です。callerが次を選択します。

- `earlier`: 1回目
- `later`: 2回目

### DST gap

Clockが進み、存在しないwall timeになる場合があります。defaultは`error`です。callerは次を選択できます。

- `next`: gap後の最初の有効な分
- `previous`: gap前の最初の有効な分

誤設定で大きく移動しないよう、gap調整は最大3時間です。

## 3. 補償付きmulti-target transaction

`lifetxt.multi_target`は、複数fileへ影響する操作向けのdependency-free contractです。

- timer JSON stateと関連life.txt item
- attachmentの作成・更新・削除とlife.txt reference

実装は次の順序で処理します。

1. absolute path順にすべてのsidecar lockを取得
2. 1件も書き込む前にすべてのexpected revisionを検証
3. 1件も書き込む前にすべてのreplacementをstage・validate
4. 各targetをcommitして再検証
5. 後続targetが失敗した場合、commit済みtargetを逆順で補償
6. rollback failureを隠さず`MultiTargetCommitError`へ含める

これは、無関係な複数fileに対するportableなfilesystem-level atomicityを主張するものではありません。Commit中にprocessまたはmachineが停止した場合、backupまたは将来のdurable transaction journalによる復旧が必要です。現在の保証は、process内での失敗検出、lock順序、preflight validation、commit検証、明示的compensationです。

### Timerとitemの例

```python
from lifetxt.multi_target import timer_and_item_transaction
from lifetxt.mutation import read_text_snapshot

result = timer_and_item_transaction(
    "timer.json",
    lambda state: {"running": True, "item_id": "T-1"},
    read_text_snapshot("timer.json").content_hash,
    "life.txt",
    lambda text: text.replace("[ ] T Focus", "[/] T Focus"),
    read_text_snapshot("life.txt").content_hash,
)
```

既存の公開timer・attachment handlerがこのcontractをend-to-endで使用するまでは、capability matrixのrevision enforcementをcompleteとして扱いません。

## 4. Workspace diagnostics

追加されたstable diagnostic codeは次のとおりです。

| Code | 内容 |
|---|---|
| `F111` | Malformed metadata directive |
| `F112` | Leading indentation内のtab |
| `F113` | 2 spaces単位でないindentation |
| `F114` | Invalid timezone directive |
| `F115` | Active/archive間のduplicate ID |
| `F116` | Dangling link |
| `F117` | Missing parent |
| `F118` | Dependency cycle |
| `F119` | Corrupt timer state |
| `F120` | Unsafeまたはmismatched write target |
| `F121` | 永続化されたlegacy revision fallback利用 |
| `F122` | Corrupt revision telemetry |

Diagnosticはstableな`source`、`line`、`column`、`span`、`code`、`severity`、`message`、`hint`を保持し、deterministicにsortされます。

## 5. 統合doctor

次のように実行します。

```bash
lifetxt doctor life.txt \
  --archive archive.txt \
  --timer-state .cache/lifetxt/timer.json \
  --revision-metrics .cache/lifetxt/revision-metrics.json \
  --pretty
```

Reportには次が含まれます。

- workspace read/write target
- timezone policy
- revision移行ready状態
- active/stale lockの証拠
- stable workspace diagnostics
- optional dependencyの利用可否

### Stale lock cleanup

Defaultはread-only inspectionです。`--force`なしのcleanup requestは計画だけを表示します。

```bash
lifetxt doctor life.txt --cleanup-stale --stale-after 300 --pretty
```

削除には両方が必要です。

```bash
lifetxt doctor life.txt \
  --cleanup-stale \
  --force \
  --stale-after 300 \
  --pretty
```

削除前に、lockが現在もstaleと証明できること、inode・size・mtimeが変化していないことを再確認します。

## 6. 公開schema

Schema bundleはDraft 2020-12の21文書になりました。新規documentは次を対象にします。

- revision metrics
- timezone policy
- workspace diagnostics
- doctor output
- multi-target result
- JSON export
- proposal
- saved view
- remote profile
- group
- per-recipient delivery state
- transaction journalとrecovery
- strict timer operation
- redacted support bundle
- revision migration evidence

Authoritative bundleを生成します。

```bash
lifetxt format schemas dist/schemas --pretty
```

Release gateはgenerated版とpublished版の一致、representative instance、published schema間のlocal `$ref`解決を検証します。

## Scope boundary

このbatchでは次を完了済みとは扱いません。

- 実際のzero-use observation window前のobserve mode削除
- 既存CLI/TUI quick capture・archive・undo handlerの移行
- 公開timer・attachment handlerへのmulti-target contract接続
- multi-target commitのdurable crash-recovery journal
- 実terminal、browser engine、fzf/peco、SMTP検証
- recurrence・timer・notification・completionに残るすべてのdirect `datetime.now()`境界の置換
