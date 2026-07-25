# 委譲変更・リモート添付・復旧証跡

このリリースでは、P0の安全基盤を、再起動可能な委譲変更、Web/MCPのdirectory/package attachment、subprocess fault drill、検証済みbackup復元へ拡張します。また、書き込み可能なWeb/MCP操作へserver-authoritativeなclock preconditionを任意で適用できます。

## 再起動可能な委譲変更

Pluginや外部programがlife.txtの変更を提案するときに使用します。外部commandへ渡すのはprivateな一時copyであり、authoritative fileではありません。Proposalには元revision、編集後content hash、diff hash、command引数、標準出力、標準error、検証結果が保存されます。

Proposalを作成します。

```bash
lifetxt safety delegated prepare \
  --path life.txt \
  --proposal .lifetxt-proposals/plugin-change.json \
  --command 'python plugin.py {file}' \
  --pretty
```

元processやsessionの終了後にも内容を確認できます。

```bash
lifetxt safety delegated inspect \
  --proposal .lifetxt-proposals/plugin-change.json \
  --pretty
```

Proposal fileとauthoritative life.txtのrevisionが一致する場合だけ適用します。

```bash
lifetxt safety delegated apply \
  --proposal .lifetxt-proposals/plugin-change.json \
  --expected-proposal-revision PROPOSAL_SHA256 \
  --pretty
```

life.txtを変更せず却下します。

```bash
lifetxt safety delegated reject \
  --proposal .lifetxt-proposals/plugin-change.json \
  --expected-proposal-revision PROPOSAL_SHA256 \
  --reason 'Not approved' \
  --pretty
```

Platformが対応する場合、proposal fileはowner-private permissionで保存されます。保存された編集textとunified diffはinspect・apply前にhash検証されます。Authoritative fileが同時に変更された場合は通常のrevision conflictになり、自動rebaseや上書きはしません。`--unsafe`は意図的なlocal recovery用であり、integrationから使用すべきではありません。

## リモートattachment契約

WebとMCPから、CLIと同じrevision-awareなdirectory/package操作を利用できます。契約は`/api/attachments/contract`、`/api/capabilities`、`get_capabilities`、`lifetxt://capabilities`で公開されます。

契約に含まれる内容は次のとおりです。

- item・attachment・metadataのexact revision
- Package retry用のcaller-supplied transaction ID
- Server-side package source confinement
- 決定的ZIPと埋め込みintegrity manifest
- 最大1 MiBのbounded chunk read
- Package manifest検証
- Transaction statusと利用可能なrecovery action
- Remoteからplatform openerを実行しない制約

### Web操作

```text
GET  /api/attachments/contract
GET  /api/attachments/chunk
GET  /api/attachments/package-manifest
GET  /api/attachments/transactions/{transaction_id}
POST /api/attachments/directory-reference
POST /api/attachments/package
POST /api/attachments/reconcile
POST /api/attachments/open
```

Package request例です。

```json
{
  "id": "T-1",
  "source": "./specs",
  "path": "./attachments/specs.zip",
  "item_revision": "LIFE_SHA256",
  "attachment_revision": "<missing>",
  "transaction_id": "package-T-1-20260725"
}
```

Sourceは`attachments.remote_source_root`以下でなければなりません。別のremote source rootを設定していない場合は通常のattachment rootが使用されます。明示的なlocal policyがない限り、symlinkとnon-regular entryは拒否されます。

同じtransaction IDを再利用すると、新しいtransactionを開始せず、現在のjournal stateとrecovery actionを含む`DUPLICATE_TRANSACTION_ID`を返します。

Bounded chunkを読みます。

```text
GET /api/attachments/chunk?path=./attachments/specs.zip&offset=0&limit=65536&attachment_revision=SHA256
```

埋め込みmanifestと各package memberを検証します。

```text
GET /api/attachments/package-manifest?path=./attachments/specs.zip&attachment_revision=SHA256
```

Remote openはattachmentを検証し、revision-checkedなopen metadataを更新できますが、OS command planを返すだけです。Web/MCP serverがopenerを実行することはありません。

### MCP tool

対応するMCP toolは次のとおりです。

- `attachment_directory_reference`
- `attachment_package`
- `attachment_reconcile`
- `attachment_open`
- `attachment_read_chunk`
- `attachment_inspect_package`
- `attachment_transaction_status`

すべてのwritable MCP toolは任意の`client_time`入力を公開し、clock preconditionがrequiredになる前からclientが契約を検出できます。

## リモート書き込みclock precondition

次の設定で有効化します。

```json
{
  "clock": {
    "require_remote_write_time": true,
    "client_time_header": "X-Lifetxt-Client-Time",
    "skew_warning_seconds": 30,
    "skew_reject_seconds": 300
  }
}
```

Writable Web requestにはoffset-aware timestampをconfigured headerで指定します。Headerがない場合はHTTP 428 `CLIENT_TIME_REQUIRED`、timestampが無効またはskewが大きすぎる場合はHTTP 409 `CLOCK_SKEW`を返します。成功responseにはclock stateとskew headerが付与されます。Parser-only endpointはauthoritative stateを書き換えないため、clock headerなしで利用できます。

Writable MCP callでは同じpolicyを`client_time`引数で適用します。Capability documentはenforcementの有無とWeb header名を公開します。

このcheckはclient/server間の大きな時刻差を検出します。Exact resource revision、transaction ID、authentication、authorization、transaction recoveryの代わりではありません。

## 拡張subprocess fault matrix

Transaction directory作成、before/after artifact、journal publish、target commit、file fsync、replace、parent-directory fsyncの前後を含む16境界を検証できます。

全matrixを実行します。

```bash
lifetxt safety transactions drill \
  --matrix \
  --recovery auto \
  --pretty
```

1境界を実行し、terminal recoveryの再実行も確認します。

```bash
lifetxt safety transactions drill \
  --point after_journal_publish \
  --recovery auto \
  --repeat-recovery \
  --pretty
```

Pre-journal境界では、`auto`が両targetの未変更を確認してからunpublished orphan transaction directoryを削除します。Journal publish後は通常のstale-lock処理を使用してresumeします。Compensationは明示的に選択できます。

このmatrixが証明するのは`os._exit`によるPython interpreterの突然の終了です。物理的電源断、storage controller、disk-full、Windows replace、antivirus/indexer、cloud sync、removable media、network filesystemを証明するものではありません。

## 検証済みbackup復元

Abandonされたtransaction backupはimmutable evidenceとして保持されます。復元前に元backupのintegrity manifestを検証します。`inspect`はworking copyを作らず証跡だけを読み、`resume`と`compensate`は別のworking directoryへcopyしてから復旧します。

```bash
lifetxt safety transactions restore-backup \
  --backup-dir transaction-backups/TX-ID \
  --restore-action inspect \
  --operator alice \
  --pretty
```

```bash
lifetxt safety transactions restore-backup \
  --backup-dir transaction-backups/TX-ID \
  --restore-action compensate \
  --working-dir recovery/TX-ID \
  --operator alice \
  --pretty
```

復旧後に元backupを再検証し、working copy用の新しいintegrity manifestを作成します。Operator allow-listは次の設定で有効化できます。

```json
{
  "transactions": {
    "require_operator_authorization": true,
    "authorized_operators": ["alice", "on-call"]
  }
}
```

これはlocal allow-list境界であり、authenticated roleやOS access controlの代替ではありません。Encrypted evidence、key rotation、role-backed authorization、実際のincident handoff drillは今後のrelease作業です。

## 公開schema

次のschemaを追加します。

- `delegated-mutation-proposal-v1.schema.json`
- `attachment-remote-operation-v1.schema.json`
- `attachment-chunk-v1.schema.json`
- `directory-package-inspection-v1.schema.json`
- `transaction-restore-v1.schema.json`
- `fault-drill-matrix-v1.schema.json`
- `remote-write-clock-v1.schema.json`
