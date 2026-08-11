# Delegated mutations, remote attachment contracts, and recovery evidence

この release は P0 safety foundation を 4 つの連動した領域へ拡張します。restart-safe delegated mutations、Web/MCP directory-package attachment parity、より広い subprocess fault drills、verified backup restoration です。また writable Web/MCP operations に対して、任意で server-authoritative clock precondition を追加します。

## Restart-safe delegated mutations

plugin や他の program が life.txt への変更を提案する必要がある場合は、この flow を使います。delegated command が受け取るのは private temporary copy であり、authoritative file ではありません。prepared proposal は exact source revision、edited content hash、diff hash、command arguments、output、validation result を保存します。

proposal を prepare します。

```bash
lifetxt safety delegated prepare \
  --path life.txt \
  --proposal .lifetxt-proposals/plugin-change.json \
  --command 'python plugin.py {file}' \
  --pretty
```

元の process や machine session が終了した後でも inspect できます。

```bash
lifetxt safety delegated inspect \
  --proposal .lifetxt-proposals/plugin-change.json \
  --pretty
```

proposal file と authoritative life.txt revisions がまだ一致する場合だけ apply します。

```bash
lifetxt safety delegated apply \
  --proposal .lifetxt-proposals/plugin-change.json \
  --expected-proposal-revision PROPOSAL_SHA256 \
  --pretty
```

life.txt を変えずに reject します。

```bash
lifetxt safety delegated reject \
  --proposal .lifetxt-proposals/plugin-change.json \
  --expected-proposal-revision PROPOSAL_SHA256 \
  --reason 'Not approved' \
  --pretty
```

prepared proposal files は、platform が対応している場合 owner-private permissions で書かれます。保存された edited text と unified diff は inspect/apply 前に hash-check されます。concurrent authoritative edit は通常の revision conflict になり、proposal は silent rebase も overwrite もされません。`--unsafe` は意図的な local recovery 用ですが、保存された source revision を bypass するため integrations から使うべきではありません。

重要な境界は、delegated command が real authoritative path を受け取らないことです。command が crash した場合、invalid life.txt を書いた場合、output 後に temporary copy をさらに編集した場合、または approval 前に user が real file を編集した場合でも、`inspect` と `apply` には推測で merge せず fail loudly するための hashes が記録されています。

## Remote attachment contract

Web と MCP surfaces は、CLI と同じ revision-aware directory/package operations を公開します。server は `/api/attachments/contract`、`/api/capabilities`、`get_capabilities`、`lifetxt://capabilities` で contract を publish します。

contract には次が含まれます。

- exact item、attachment、metadata revisions
- package retries 用の stable caller-provided transaction ID
- server-side package source confinement
- deterministic ZIP generation と embedded integrity manifests
- 1 MiB capped bounded chunk reads
- package-manifest inspection
- transaction status と permitted recovery actions
- platform attachment open commands の remote execution はしない

### Web operations

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

package request は server-confined source path を使います。

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

source は `attachments.remote_source_root` の下、または separate remote source root が未設定の場合は通常の attachment root の下に resolve されなければなりません。explicit local policy が許可しない限り、symlink と non-regular entries は拒否されます。

existing transaction ID を retry すると、新しい transaction を開始せず、current journal state と supported recovery actions を含む `DUPLICATE_TRANSACTION_ID` を返します。

bounded package/attachment chunk を読む例です。

```text
GET /api/attachments/chunk?path=./attachments/specs.zip&offset=0&limit=65536&attachment_revision=SHA256
```

embedded manifest と package members を inspect します。

```text
GET /api/attachments/package-manifest?path=./attachments/specs.zip&attachment_revision=SHA256
```

remote open operation は attachment を validate し、revision-checked open metadata を update できますが、返すのは operating-system command plan だけです。Web server と MCP server は opener を execute しません。その plan は trusted client side でのみ使ってください。remote attachment API は何を開く予定かを伝えますが、remote command-execution channel ではありません。

### MCP tools

対応する MCP tools は次の通りです。

- `attachment_directory_reference`
- `attachment_package`
- `attachment_reconcile`
- `attachment_open`
- `attachment_read_chunk`
- `attachment_inspect_package`
- `attachment_transaction_status`

すべての writable MCP tool は optional `client_time` input を publish します。これにより clients は clock precondition が required になる前から contract を discover できます。

## Remote write clock precondition

server-authoritative clock enforcement は次で有効にします。

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

writable Web requests は configured header に offset-aware timestamp を含める必要があります。missing timestamp は HTTP 428 `CLIENT_TIME_REQUIRED`、invalid timestamp または excessive skew は HTTP 409 `CLOCK_SKEW` を返します。successful responses には measured clock state と skew headers が含まれます。parser-only endpoints は authoritative state を mutate しないため clock header なしで利用できます。

writable MCP calls は `client_time` argument で同じ policy を使います。capability documents は enforcement が enabled かどうかと expected Web header を report します。

この check は client/server 間の大きな clock disagreement を検出します。exact resource revisions、transaction IDs、authentication、authorization、transaction recovery の代替ではありません。enforcement が disabled の場合でも、clients は header または MCP `client_time` を送れます。その場合の response clock report は diagnostic です。enforcement が enabled の場合、offset-aware timestamp のない writable calls は mutation 前に失敗します。

## Expanded subprocess fault matrix

drill は transaction-directory creation、before/after artifact persistence、journal publication、target commit、file fsync、replace、parent-directory fsync の周辺にある 16 named boundaries を cover します。

full deterministic subprocess matrix を実行します。

```bash
lifetxt safety transactions drill \
  --matrix \
  --recovery auto \
  --pretty
```

1 つの boundary を実行し、recovery を繰り返して idempotent terminal behavior を示します。

```bash
lifetxt safety transactions drill \
  --point after_journal_publish \
  --recovery auto \
  --repeat-recovery \
  --pretty
```

pre-journal boundaries では、`auto` は both targets が unchanged であることを確認してから unpublished orphan transaction directory を remove します。published journals では normal stale-lock handling を使って journal を resume します。compensation は明示的に選べます。

この matrix が証明するのは `os._exit` による abrupt Python interpreter termination 後の behavior です。physical power-loss durability、storage-controller ordering、disk-full handling、Windows replacement behavior、antivirus/indexer interaction、cloud synchronization、removable media、network filesystem behavior は証明しません。

## Verified backup restoration

abandoned transaction backups は immutable evidence として残ります。restoration はまず original integrity manifest を verify します。`inspect` は working copy を作らず evidence を読みます。`resume` と `compensate` は backup を separate working directory に copy し、その copy から recover します。

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

operation は recovery 後に original backup を再 verify し、working copy 用に fresh integrity manifest を書きます。optional operator authorization は次で有効にできます。

```json
{
  "transactions": {
    "require_operator_authorization": true,
    "authorized_operators": ["alice", "on-call"]
  }
}
```

これは local allow-list boundary であり、authenticated roles や OS access controls の代替ではありません。encrypted evidence profiles、key rotation、role-backed authorization、real incident handoff drills は今後の release work です。

remote または multi-user recovery surface では、authorization は `--operator` ではなく authenticated principal context から derive します。recovery role、scope、project limit、destructive action の approval separation は次で設定します。

```json
{
  "transactions": {
    "require_authenticated_recovery_authorization": true,
    "recovery_authorized_roles": ["recovery-admin"],
    "recovery_required_scopes": ["recovery"],
    "recovery_allowed_projects": ["default"],
    "require_destructive_recovery_approval": true
  }
}
```

backup からの `resume` と `compensate` は destructive recovery action です。approval separation が有効な場合、approval identity は authenticated recovery operator と別でなければなりません。local single-operator use ではこれらの設定を disabled のままにできますが、それは local-only administration の stable-release limitation であり、remote authorization として扱ってはいけません。

incident handling では、まず `inspect` を優先してください。これは working copy を作らず retained evidence を読むため、transaction を resume、compensate、abandon、または escalate すべきか判断する最も低 risk な方法です。

## Published schemas

schema bundle は次を追加します。

- `delegated-mutation-proposal-v1.schema.json`
- `attachment-remote-operation-v1.schema.json`
- `attachment-chunk-v1.schema.json`
- `directory-package-inspection-v1.schema.json`
- `transaction-restore-v1.schema.json`
- `fault-drill-matrix-v1.schema.json`
- `remote-write-clock-v1.schema.json`
