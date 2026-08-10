# 共有ミューテーション経路

権威あるtext/JSONファイルの置換書き込みは、すべて `lifetxt.mutation`（`lifetxt/mutation.py`）の共有ミューテーション契約へ入るようになりました。

## 互換境界

既存モジュールは歴史的に次のヘルパーをimportしています。

```python
from lifetxt.atomic import atomic_write_text, atomic_write_json
```

これらの名前は引き続き利用できます。現在は `mutation.write_text`（`lifetxt/atomic.py`）の互換ファサードであり、公開APIを直ちに変更せずに次の共通動作を得ます。

- 対象ファイルごとのsidecar lock
- lock取得後の現在バイト列の再読込
- transform実行中にファイルが変更された場合の検出
- 原子的なバイト置換
- 対応環境でのpermission維持
- 書き込み後のhash検証
- 既存ファイル更新時のUTF-8 BOMと改行形式の保持

`atomic_write_bytes` は例外です。これは共有ミューテーションlock取得後にのみ使用する内部commit primitiveです。アプリケーションや各surfaceから直接呼び出してはいけません。

fzf/peco helperには、`open(..., "w")` を直接使うlife.txt writerが1箇所残っていました。package初期化時に狭い互換bridgeでこのhelperを置き換え、同じhelperを再利用するTUIのstatus/delete操作も共有経路へ通します。

## Sidecar lockの詳細

`apply_text_mutation` はtargetを触る前に `lifetxt.mutation.FileLock` を取得します。このlockはexclusive creation（`O_CREAT | O_EXCL`）で作られるcross-platformなsidecar fileなので、サードパーティ依存なしでWindowsとPOSIXの両方で同じ動作をします。

```text
<target-path>.lifetxt.lock
```

Lock fileには、writerが処理を進める前にfsync済みの小さなJSON metadataが書き込まれます。

```json
{
  "version": 1,
  "token": "HOSTNAME-1234-1699999999000000000",
  "pid": 1234,
  "host": "HOSTNAME",
  "operation": "task.create",
  "target": "/abs/path/life.txt",
  "created": "2026-08-10T10:00:00Z"
}
```

Lockの既定値（`lifetxt.mutation` モジュール定数）：

| 定数 | 既定値 | 内容 |
|---|---|---|
| `DEFAULT_LOCK_TIMEOUT` | `5.0` 秒 | 競合中のlockをcallerが待つ最大時間 |
| `DEFAULT_POLL_INTERVAL` | `0.05` 秒 | 待機中のcallerがlock作成を再試行する間隔 |
| `DEFAULT_STALE_LOCK_AFTER` | `300.0` 秒 | Stale-lock recoveryを検討し始める最小経過時間 |

Stale-lock recoveryは保守的です。lockが除去・再試行されるのは、次のすべてを満たす場合だけです。`stale_after` より古いこと、`host` が現在のhostと一致すること（別machineのlockには触れません）、`pid` が現在のhostで実行されていないと確認できること、そしてstaleness確認から除去までの間にlock fileの`mtime`・inode・sizeが変化していないこと（解放直後に別のwriterが再取得したlockを奪わないため）。いずれかを満たさない場合、callerは`timeout`まで待ち続けた後に`LockTimeout`を送出します。そのmessageには現在のlock owner（host/pid/operation）のJSON metadataが埋め込まれるため、運用者はどのprocessがfileを保持しているか判別できます。

明示的にlockを解放しないcaller（強制終了やWindows強制終了によるcrash）はlock fileを残します。次のwriterは`stale_after`を待って自動回収する（owner processの死亡が確認できる場合）か、確認できない場合（host不一致やprocess確認が不確実な場合）は`timeout`いっぱい待って`LockTimeout`を送出し、人手での解決を促します。これはliveness目的のfallbackであり、分散lock managerではありません——2つの本物のwriterが同時に動く状況を、普通のsidecar lockより強く保護するものではありません。現在保持中のlockとその経過時間をCLIから確認するには `lifetxt safety locks`（`lifetxt.extra_safety`）を使用してください。

## `apply_text_mutation` の実行手順

`apply_text_mutation(path, operation, expected_hash=...)` は次の順で実行します。

1. `path`のsidecar lockを取得。
2. 現在のバイト列を`TextSnapshot`（`before`）として読み込む。ファイルが存在せず`operation.create`がfalseなら`FileNotFoundError`。
3. `expected_hash`が指定されており、それが`before.content_hash`と一致しなければ即座に`MutationConflict`。Transformは古いcontentに対して一度も実行されません。
4. `operation.transform(current_text)`で置換textを計算し、validatorがあれば`operation.validate(replacement)`を実行。
5. 既存fileのencoding/BOM（新規作成時はcallerの既定値）で置換textをencodeし、hashを計算。
6. ファイルをもう一度読み込み（`latest`）、そのhashを`before.content_hash`と比較。これは、手順2から6の間にlockを迂回した書き込みやfilesystemの挙動でfileが変化していないかを確認する保護であり、`expected_hash`を指定していない呼び出しでも不一致なら`MutationConflict`を送出します。
7. 計算した置換内容が現在のcontentと異なる場合のみ`atomic_write_bytes`でcommit。意味的に変化のないtransformはfileにもmtimeにも触れません。
8. 書き込み後のfileを再読込し、hashが一致することを確認。不一致なら`"<operation> post-write verification"`という名前の`MutationConflict`を送出——成功を無条件に信じず、commit自体の破損や外部干渉を検出します。
9. lockを解放し、`MutationResult(path, operation, before_hash, after_hash, changed, created, snapshot)`を返す。

手順3と6は役割が異なる2つのconflict検査です。手順3は、callerがすでに古いと分かっているfile versionを基に動いていたことを拒否します。手順6は、lock中に本来起こり得ないはずの予期しない変化——全writerがこの共有層を通っていれば構造的に起こらないはずのもの——を、想定に頼らず実際に確認します。

## 対象surface

routing regression test（`tests/test_shared_surface_mutation_routing.py`）では、次の書き込み元を検証しています。

- atomic text/JSON互換API
- fzf/peco direct writerの置き換え
- TUI `_mutate_rows` によるstatus変更
- TUI presence status transition
- timerに紐づくitem更新
- WebのMessage acknowledgement
- MCPによるitem作成

WebとMCPのwrite helperはWeb file helperへ集約され、そこからatomic互換APIへ到達します。timerとTUIの大部分もatomic APIを使用しています。このため、これらは同一のlock/commit実装を共有します。Web/MCP層はこの上にさらに独自のoptimistic-concurrency契約（ETag/If-Match、`expected_file_hash`）を追加しています。詳細は[public-surface-revisions.md](public-surface-revisions.md)を参照してください。

## 楽観的並行制御は引き続き明示的

置換書き込みを共有層へ通すことで、同時commitを直列化し、lock中のtransform実行時に発生した変更を検出できます。ただし、呼び出し元が事前に作成した置換内容について、どの古いfile versionを基に計算したかを共有層が自動推測することはできません。

先に読み、後から書くcallerはsnapshotを取得してhashを渡します。

```python
from lifetxt.mutation import mutate_text, read_text_snapshot

snapshot = read_text_snapshot("life.txt")
result = mutate_text(
    "life.txt",
    lambda current: current + "[ ] T New task\n",
    expected_hash=snapshot.content_hash,
    operation="task.create",
)
print(result.after_hash)
```

古いhashの場合は、新しいfileを上書きせず `MutationConflict` を送出します。実fixtureで確認すると、古いhashは正確に次のように再現されます。

```pycon
>>> mutate_text("life.txt", lambda t: t + "x", expected_hash="0" * 64, operation="task.create")
Traceback (most recent call last):
  ...
lifetxt.mutation.MutationConflict: task.create conflict for /abs/path/life.txt: expected content hash 0000000000000000000000000000000000000000000000000000000000000000, found 56421fc3a950440da9132becd234f37007c7467c68904813ed3504ca854034f9. Reload the file and retry.
```

quick capture、item update、MCP、acknowledgement、timer、archive、undoへoperation固有のexpected hashを追加し、同時書き込みtestで古いwriterを拒否する作業は継続中のrelease-safety taskです。あるsurfaceが実際にこれを強制しているかどうかは、`tests/test_shared_surface_mutation_routing.py`の現在のcoverageを確認してから判断してください。

## `mutate_text`・`write_text`・`mutate_json`

`mutate_text`は、単純な`transform` callableから`MutationOperation`を組み立てて`apply_text_mutation`を呼ぶ薄いconvenience wrapperです。`write_text`はさらに一歩進み、置換text全体を渡す`text=`（旧`atomic_write_text`と同じ全置換契約）か、lock内の現在contentから置換を計算する`transform=` callable（新規コードで推奨）のどちらか一方を受け付けます——両方は指定できません。

```python
from lifetxt.mutation import write_text

# 旧atomic_write_textと同じ全置換:
write_text("life.txt", "entirely new content\n", operation="cli.replace")

# semantic transform、新規コードではこちらを推奨:
write_text(
    "life.txt",
    transform=lambda current: current + "[ ] T Another task\n",
    operation="cli.append",
)
```

`mutate_json`は同じtext契約の上にJSON parse/dumpを重ねます。現在のtextをJSONとしてdecodeし（fileが空/未存在で`create=True`の場合は`default`を使用）、decode済みの値で`transform(value)`を呼び、既定では`json.dumps(..., indent=2, sort_keys=True)`で再直列化します（`pretty=False`ならcompactな`(",", ":")` separatorに切り替わります）。これは`lifetxt.revision_telemetry`やtimer state writerが基盤として使うprimitiveです。

複数fileを同時に変更する書き込み——attachment操作がstored fileと`life.txt`参照の両方を更新する場合など——は`lifetxt.mutation`単体では表現しません。`lifetxt.multi_target.apply_multi_target`を使用し、file単位で`MutationOperation`に相当する`TargetPlan`をstageし、全targetをlockし（lock順序deadlockを避けるためpath順）、任意でdurable transaction journalを記録します。Journal形式とrecovery commandは[transaction-recovery-and-strict-timers.md](transaction-recovery-and-strict-timers.md)、この上に構築されたsemantic write layer（`lifetxt.write_operations`）は[safe-writes-attachments-and-work-sessions.md](safe-writes-attachments-and-work-sessions.md)を参照してください。

## 新規コードの移行規則

新しい権威的writerは `lifetxt.mutation` を直接importし、lock内の最新textに対して実行されるsemantic transformを渡してください。atomic互換APIは既存のreplacement型callerのために保持されるものであり、新しいsurface codeで推奨する入口ではありません。

## 関連文書

- [public-surface-revisions.md](public-surface-revisions.md) —— WebとMCPが同じcontent-hash契約を`ETag`/`If-Match`と`expected_file_hash`としてどう公開しているか。
- [transaction-recovery-and-strict-timers.md](transaction-recovery-and-strict-timers.md) —— 複数fileを同時に変更する必要がある場合のdurable journal。
- [safe-writes-attachments-and-work-sessions.md](safe-writes-attachments-and-work-sessions.md) —— CLI/TUI/Web/MCPのitem・attachment・work session書き込み向けに、この契約の上に構築されたsemantic write layer（`lifetxt.write_operations`）。
- [process-boundaries-attachments-and-transaction-admin.md](process-boundaries-attachments-and-transaction-admin.md) —— 外部エディタセッション。結果はこのrevision-checked write pathを通して反映されます。
