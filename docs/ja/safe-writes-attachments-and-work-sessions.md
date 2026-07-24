# Safe write・attachment・compound work session

この文書では、durable transaction基盤の後に追加したrevision-aware write経路を説明します。`life.txt`をauthoritative dataとして維持し、すべてのauthoritative mutationをsingle-file semantic compare-and-swap（CAS）またはjournal-backed multi-target transactionとして実行します。

## Semantic write contract

`lifetxt.write_operations`の共通write layerは、target lockを保持した状態でsemantic transformを実行します。Strict conflict detectionが必要な場合、呼び出し側は期待するSHA-256 revisionを指定します。対象は次のとおりです。

- quick captureとjournal append
- ID指定によるitem update/delete
- TUIとfzf/pecoのmulti-selection操作
- revision付きrestore/undo
- `life.txt`とconfig aliasを同時更新するtag merge
- digest/template append
- multi-file archive

Expected revisionが古い場合はstructured mutation conflictになります。Multi-file操作では最初のcommitより前にすべてのreplacementをstageし、durable transaction journalへ記録します。途中commit後に失敗してもtransaction commandからrecoveryできます。

External editorを終了した後の保存は、現時点では自動的にconflict-safeにはなりません。今後はtemporary copyを編集し、diffをrevision付きapply commandで反映するeditor workflowが必要です。

## Archive safety

Archiveは初回parse時に取得したrevisionを保持します。Destinationと変更対象の全source fileを一つのjournal-backed operationでcommitするため、選択後からcommit前に入った外部編集を上書きしません。

Scriptから利用する場合はtargetごとのrevisionを明示できます。

```bash
lifetxt archive active.txt \
  --destination archive.txt \
  --revision active.txt=<sha256> \
  --revision archive.txt=<sha256-or-missing>
```

正確なselector optionはarchive方法によって異なります。Resultにはjournalとcommit後のtarget revisionが含まれます。

## TUIとfzf/peco

TUIのdone、status、delete、detail、add、presence、timer、undoは共通mutation layerを使用します。複数fileにまたがる選択は一つのtransactionでcommitします。Undoは元操作が生成したrevisionを保持し、その後に外部編集がある場合はrestoreを拒否します。

fzf/pecoのdone/deleteは選択recordをfile単位にまとめ、各fileを一度だけsemantic transformします。旧direct writer用compatibility bridgeは削除しました。

PowerShell、Windows Terminal、WSL、macOS、Linux、fzf、pecoの実shell/terminal検証は引き続き必要です。

## Attachment transaction

Attachment fileは設定されたattachment root内に制限されます。File操作と`life.txt`参照を同じtransactionでcommitします。

- `put`: attachment rootへbytesをcopyし、item参照を追加・更新
- `reference`: 既存のconfined fileとrevisionを確認して参照を追加
- `delete`: fileとitem参照を同時削除
- `status`: mutationせずitem/attachment revisionを表示

Defaultではpath escape、symlink、executable/script系file、stale revisionを拒否します。

### CLI例

```bash
lifetxt attachment status life.txt \
  --file attachments/report.pdf \
  --pretty
```

```bash
lifetxt attachment put life.txt \
  --id T-1 \
  --file attachments/report.pdf \
  --source ./report.pdf \
  --item-revision <life-sha256> \
  --attachment-revision '<missing>' \
  --require-revisions \
  --pretty
```

```bash
lifetxt attachment delete life.txt \
  --id T-1 \
  --file attachments/report.pdf \
  --item-revision <life-sha256> \
  --attachment-revision <attachment-sha256> \
  --require-revisions \
  --pretty
```

`--allow-symlink`と`--allow-executable`は明示的なunsafe-policy overrideです。Untrusted path/contentには使用しないでください。

### Web・MCP

Web APIはattachment stateとmutation endpointを提供します。Strict modeではitemとattachmentの両revisionが必要で、欠落はHTTP 428、stale revisionはHTTP 409です。MCPはattachment put/delete/state toolを提供し、既存のfile-reference toolもfile attachmentを同じtransaction contractへroutingします。

Directory attachmentとplatform固有のopen-reference動作は今後の作業です。

## Compound work session

Work sessionはtask state、timer state、presenceを一つのrecoverable operationで更新します。

Startでは次を実行できます。

- Open taskをin-progressへ変更
- Timer state作成
- Presence record開始

Stopでは次を実行できます。

- Timer state削除
- Elapsed追加
- Optional task completion
- Presence終了

CLI・Web・MCPは同じitem/timer revision contractを使用します。

```bash
lifetxt start T-1 life.txt \
  --item-revision <life-sha256> \
  --timer-revision '<missing>' \
  --require-revisions
```

```bash
lifetxt stop life.txt \
  --item-revision <life-sha256> \
  --timer-revision <timer-sha256> \
  --require-revisions
```

Responseにはtransaction ID、journal path、recovery state、新しいtarget revisionが含まれます。

## Transaction policy

`transactions` config sectionでは次を設定できます。

```json
{
  "transactions": {
    "terminal_retention_days": 30,
    "max_transactions": 500,
    "max_total_bytes": 268435456,
    "max_transaction_bytes": 67108864,
    "require_private_permissions": true,
    "allow_newer_read_only": true,
    "evidence_include_paths": false
  }
}
```

Runtimeはcount/size limit、platformが提供するowner/private mode、newer journal versionのread-only inspection ruleを確認します。Abandon/archiveは後で検証できるintegrity manifestを生成します。

```bash
lifetxt safety transactions policy \
  --journal-dir .lifetxt-transactions \
  --pretty
```

```bash
lifetxt safety transactions archive \
  --journal-dir .lifetxt-transactions \
  --archive-dir transaction-archive \
  --older-than-days 30 \
  --force \
  --pretty
```

```bash
lifetxt safety transactions verify-backup \
  --backup-dir recovery-backup \
  --pretty
```

## Fault boundary

Journal実装にはartifact write、file fsync、replace、parent-directory fsync、target commit、compensation、cleanupにdeterministic fault pointがあります。Production動作を弱めず、unit/subprocess drillを再現できます。

ただし、これはreal power-loss portabilityの証明ではありません。実process termination、disk-full、Windows replace、antivirus/indexer、cloud sync filesystem、network filesystemはP0の実環境検証として残ります。

## Clock boundary audit

Release policyはPython sourceのdirect host-clock callをscanします。残すcallはすべて`config/release/clock-boundary-baseline-v1.json`へclassification、reason、removal condition付きで記録しなければなりません。未分類の新規callはrelease gateを失敗させます。

現在残している分類はmonotonic/operational timing、lock age、UTC audit/telemetry、time-only compatibility parsing、transaction retention、TUI animationです。Workflowの日付・時刻判断には共通context-local timezone clockを使用します。
