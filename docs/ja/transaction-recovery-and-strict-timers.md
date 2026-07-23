# Transaction RecoveryとStrict Timer Write

この文書では、補償付きmulti-target transactionの上に追加したdurable recovery layerを説明します。Transaction journal、明示的recovery action、timerのstrict revision、revision metricsの移設、deterministic clock、diagnostic、schema、support bundleを対象とします。

## 1. Durable journalが必要な理由

`lifetxt.multi_target`は、すべてのtargetをlockし、expected revisionを検証し、replacementをすべてstageしてから決定順でcommitします。同一process内で後続writeが失敗した場合は、commit済みtargetを補償します。しかしprocess終了、停電、OS障害がcommit途中で発生する可能性は残ります。

Transaction journalは、推測せずに中断状態を調査・復旧できる正確な証拠を保存します。無関係な複数fileに対してportableなfilesystem transactionを提供すると主張するものではありません。

## 2. Journalの場所と内容

Default journal directoryは、書き込み対象life.txtと同じdirectoryの`.lifetxt-transactions`です。Configまたは環境変数で変更できます。

```json
{
  "transactions": {
    "journal_dir": ".cache/lifetxt/transactions"
  }
}
```

```text
LIFETXT_TRANSACTION_JOURNAL_DIR
```

各transactionには固有directoryが作られ、`journal.json`とbefore/afterの正確なbinary artifactが保存されます。Versioned journalには次が含まれます。

- Transaction IDとoperation名
- Target pathとkind
- Expected、before、afterのSHA-256 revision
- Targetが以前存在したか、commit後に削除されるか
- Artifact名とhash
- Commitとcompensationの進行状況
- Created、updated、terminal timestamp
- Terminalまたはrecovery-required state
- 最後に観測したerror

Journalとartifactは、file fsync、atomic replace、parent directory fsyncの順で保存されます。

## 3. Journal state

Terminal stateは次のとおりです。

- `committed`: 全targetが記録済みafter revisionと一致
- `compensated`: 全targetが記録済みbefore revisionへ復元済み
- `abandoned`: Journalとartifactの完全なbackup後に明示的に放棄

Recovery stateには`prepared`、`committing`、`compensating`、`recovery_required`、`resume_failed`、`compensation_failed`があります。

Targetの現在hashが記録済みbefore/afterのどちらにも一致しない場合、recovery actionは上書きを拒否します。この場合は手動確認が必要です。

## 4. Transactionの確認と復旧

Journal一覧を表示します。

```bash
lifetxt safety transactions list --pretty
```

Directoryを明示する場合：

```bash
lifetxt safety transactions list \
  --journal-dir .cache/lifetxt/transactions \
  --pretty
```

Transaction IDまたはjournal pathで確認します。

```bash
lifetxt safety transactions inspect --journal TX_ID --pretty
```

残りのcommitを再開します。

```bash
lifetxt safety transactions resume --journal TX_ID --pretty
```

全targetをbefore revisionへ戻します。

```bash
lifetxt safety transactions compensate --journal TX_ID --pretty
```

Journalとartifactの完全なbackupを作成して放棄します。

```bash
lifetxt safety transactions abandon \
  --journal TX_ID \
  --backup-dir recovery-backups \
  --pretty
```

Binary artifactを含めず、metadataとhashをexportします。

```bash
lifetxt safety transactions export \
  --journal TX_ID \
  --output transaction-evidence.json \
  --pretty
```

古いterminal journalは明示的なforce付きで削除します。

```bash
lifetxt safety transactions cleanup \
  --older-than-days 30 \
  --force \
  --pretty
```

Non-terminal journalはretention cleanupで削除されません。

## 5. Doctorとstable diagnostic

`doctor --workspace-safety`はtransaction directoryを検出し、journal stateを一覧化します。Recovery-required transactionはhard failureとして扱われます。

```bash
lifetxt doctor --workspace-safety life.txt \
  --journal-dir .cache/lifetxt/transactions \
  --pretty
```

追加したstable diagnosticは次のとおりです。

| Code | 内容 |
|---|---|
| `F123` | Transaction journalが読めない、または構造的に破損 |
| `F124` | Commitが中断され、明示的recoveryが必要 |
| `F125` | Compensationが中断または失敗 |
| `F126` | Targetが記録済みbefore/afterの両方からdiverge |

`--cleanup-transactions`、`--transaction-retention-days`、`--force`により、古いterminal journalをdoctorから削除できます。

## 6. Redacted support bundle

Support bundleにはversion、hash、diagnostic、policy output、recovery metadataを含めます。一方、life.txt本文、transaction artifact、credential、cookie、token、raw absolute pathは除外します。

```bash
lifetxt doctor --workspace-safety life.txt \
  --support-bundle lifetxt-support.json \
  --pretty
```

Absolute pathはdeterministicなpath pseudonymへ置換されます。運用metadataから環境特性を推測できる可能性はあるため、共有前に内容を確認してください。

## 7. Timerのstrict revision contract

Timer operationはtimer JSON stateとlife.txtの両方に触れる場合があります。Startとstopでは2つのrevisionを使い、pause、resume、cancelではtimer-state revisionを使います。

Timer statusから現在revisionを取得し、mutation requestに渡します。Required modeではrevision不足をwrite前に拒否します。Stale revisionはconflictになり、成功responseには両revisionとtransaction evidenceが含まれます。

CLI例：

```bash
lifetxt timer start life.txt --id T-1 \
  --item-revision ITEM_SHA256 \
  --timer-revision '<missing>'

lifetxt timer stop life.txt \
  --item-revision ITEM_SHA256 \
  --timer-revision TIMER_SHA256

lifetxt timer pause --timer-revision TIMER_SHA256
```

Web request例：

```json
{
  "action": "start",
  "item_id": "T-1",
  "item_revision": "ITEM_SHA256",
  "timer_revision": "<missing>"
}
```

MCP timer toolも同じ`item_revision`と`timer_revision`を公開します。Web/MCPのstatus responseがrevision discovery stepです。

すべてのcompound work-sessionとattachment pathが同じpublic contractへ移行するまでは、capability matrixを保守的な状態に維持します。

## 8. Revision metricsの移設とevidence

Local metrics pathを含めず、revision migration evidenceをexportできます。

```bash
lifetxt safety revisions life.txt \
  --export-evidence revision-migration-evidence.json \
  --pretty
```

正確なexpected revisionを指定してmetrics storeを移設します。

```bash
lifetxt safety revisions life.txt \
  --metrics-path old/revision-metrics.json \
  --relocate new/revision-metrics.json \
  --expected-hash METRICS_SHA256 \
  --pretty
```

Copyではなくmoveする場合は`--delete-source`を追加します。Source削除とdestination作成はjournal対象となり、server instance ID、observation開始、counter、zero-use windowをserver restartやpackage upgrade後も維持します。

## 9. Deterministic timezone clock

Timezone policyはcontext-localな`now`、`today`、`utcnow`とdeterministicな`clock_context`を提供します。主要なagenda、review、notification、timer、completion、journal、invoice、standup、Web、MCP、CLI境界は、それぞれhost clockを直接参照せず共通clockを使います。

これにより、同じfrozen instantを異なる設定timezoneで解釈し、midnight、DST fold/gap、非整数時間offsetをdeterministicにtestできます。

## 10. 公開schemaとrelease evidence

Draft 2020-12 bundleは21文書です。追加した5 contractは次のとおりです。

- `transaction-journal-v1.schema.json`
- `transaction-recovery-v1.schema.json`
- `timer-operation-v1.schema.json`
- `support-bundle-v1.schema.json`
- `revision-migration-evidence-v1.schema.json`

Release gateはgenerated/published schema、representative instance、duplicate `$id`拒否、network-freeな`referencing.Registry`による全local `$ref`を検証します。

## 11. 残る境界

実際の停電fault injection、すべてのlegacy CLI/TUI/fzf write、すべてのattachment handler、compound work-session capability enforcement、実terminal/browser/SMTP/platform検証は未完です。これらは明示的なP0として残します。
