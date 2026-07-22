# 共有ミューテーション経路

権威あるtext/JSONファイルの置換書き込みは、すべて `lifetxt.mutation` の共有ミューテーション契約へ入るようになりました。

## 互換境界

既存モジュールは歴史的に次のヘルパーをimportしています。

```python
from lifetxt.atomic import atomic_write_text, atomic_write_json
```

これらの名前は引き続き利用できます。現在は `mutation.write_text` の互換ファサードであり、公開APIを直ちに変更せずに次の共通動作を得ます。

- 対象ファイルごとのsidecar lock
- lock取得後の現在バイト列の再読込
- transform実行中にファイルが変更された場合の検出
- 原子的なバイト置換
- 対応環境でのpermission維持
- 書き込み後のhash検証
- 既存ファイル更新時のUTF-8 BOMと改行形式の保持

`atomic_write_bytes` は例外です。これは共有ミューテーションlock取得後にのみ使用する内部commit primitiveです。アプリケーションや各surfaceから直接呼び出してはいけません。

fzf/peco helperには、`open(..., "w")` を直接使うlife.txt writerが1箇所残っていました。package初期化時に狭い互換bridgeでこのhelperを置き換え、同じhelperを再利用するTUIのstatus/delete操作も共有経路へ通します。

## 対象surface

routing regression testでは、次の書き込み元を検証しています。

- atomic text/JSON互換API
- TUI `_mutate_rows` によるstatus変更
- TUI presence status transition
- WebのMessage acknowledgement
- MCPによるitem作成
- timerに紐づくitem更新
- fzf/peco action helper

WebとMCPのwrite helperはWeb file helperへ集約され、そこからatomic互換APIへ到達します。timerとTUIの大部分もatomic APIを使用しています。このため、これらは同一のlock/commit実装を共有します。

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
```

古いhashの場合は、新しいfileを上書きせず `MutationConflict` を送出します。

quick capture、item update、MCP、acknowledgement、timer、archive、undoへoperation固有のexpected hashを追加し、同時書き込みtestで古いwriterを拒否する作業は、次のrelease-safety taskとして残ります。

## 新規コードの移行規則

新しい権威的writerは `lifetxt.mutation` を直接importし、lock内の最新textに対して実行されるsemantic transformを渡してください。atomic互換APIは既存のreplacement型callerのために保持されるものであり、新しいsurface codeで推奨する入口ではありません。
