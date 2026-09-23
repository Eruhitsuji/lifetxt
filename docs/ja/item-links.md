# アイテムリンク

lifetxt のレコードをその正規の `id:` 値で指し示すための、ホストに依存しない
2 つの方法（#835 / #840）。特定の Web デプロイメントのホスト・ポート・パス
を埋め込む必要がない。

## 正規の識別子: `id:` detail

レコードの `id:` detail（ワークスペースが別のキー名を設定している場合は
`ids.key`）が唯一の安定した識別子であり、CLI・TUI・Web API・Web UI・MCP の
すべてがこの ID で既にレコードを解決している: `GET /api/items/{id}`
([web.md](web.md))、`lifetxt.ids.resolve_item_by_id`、MCP の `get_item`、
そして下記の `?id=` Web ディープリンクは、すべて同じ完全一致リゾルバで
同じ ID を検索する。

## `lifetxt://item/<id>` 論理 URI

```text
lifetxt://item/<id>
```

例:

```text
lifetxt://item/task-001
```

これはアドレスではなく論理的な**識別子**参照であり、どのデプロイメント・
ホスト・ポートが解決できるかを一切示さない。Web デプロイメントはこれを
自身のローカルディープリンク形式（`/?id=task-001`。
[レコードのディープリンク](web.md#record-deep-links) 参照）に変換し、
他のクライアント（スクリプト・通知・生成されたレポートなど）は自身の
アイテムを開く仕組みで解決してよい。

エンコードが必要な ID（`/`・`?`・`#`・空白を含む）は URI 内でパーセント
エンコードされる。例えば ID `a b` は `lifetxt://item/a%20b` となる。

### パース／フォーマット

`lifetxt.item_uri`（Python）は、各クライアントが独自に URI をパースする
のではなく利用すべき、唯一の共有パーサー／リゾルバの接点である:

```python
from lifetxt.item_uri import format_item_uri, parse_item_uri, web_deep_link

format_item_uri("task-001")
# -> "lifetxt://item/task-001"

parse_item_uri("lifetxt://item/task-001")
# -> "task-001"

web_deep_link("task-001", base_url="https://lifetxt.example.invalid")
# -> "https://lifetxt.example.invalid/?id=task-001"
```

同じ接点は life.txt ファイルを一切必要とせず（純粋な識別子変換であり、
アイテム検索ではない）CLI からも利用できる:

```sh
python -m lifetxt item-uri format task-001
python -m lifetxt item-uri format task-001 --base-url https://lifetxt.example.invalid
python -m lifetxt item-uri parse "lifetxt://item/task-001"
python -m lifetxt show "lifetxt://item/task-001" life.txt
```

`show` は通常の ID と論理 URI のどちらも受け付けるため、最後の command は
`lifetxt show task-001 life.txt` と同じ record を表示する。不正な `lifetxt:` URI
は URI error、正しい形式だが存在しない ID は通常の item-not-found error になる。

### 「不正な形式」と「未知の ID」の違い

`parse_item_uri`（および `item-uri parse`）は URI 自体の**形**――スキーム、
空でない ID セグメント、セグメント内にエンコードされていない `/`・`?`・
`#` が無いこと――のみを検証する。該当 ID を持つレコードが実際に存在するか
は一切確認しない。構文的には正しい URI が、現在どのレコードにも一致しない
（あるいは呼び出し側に閲覧権限がない）場合は、まったく別の、後続の失敗
――呼び出し側が次に行う検索の結果としての「見つからない」または
「権限がない」――であり、ここでの「不正な形式」と意図的に混同しない。

### 設計上の制約

- 永続化される識別子はあくまで life.txt 内の通常の `id:` detail のまま
  である。この URI はその識別子の可搬な**表現**にすぎず、新しい識別子
  体系ではなく、life.txt 自体に書き込まれることもない。
- この機能では OS 全体に対する `lifetxt://` プロトコルハンドラの登録は
  行わない。
- `lifetxt://item/<id>` URI の解決は、呼び出し側の通常のワークスペース・
  ソース・認可境界を一切バイパスしない: URI を ID に変換する処理と、その
  ID を検索する処理は別の 2 段階であり、2 段階目は通常の `id:` 参照が
  既に通る検索とまったく同じものである。

## レコードのディープリンク（Web）

`?id=`/`?line=` を使った Web UI のディープリンクとリンクコピー機能
（#838/#839）については、web.md の
[レコードのディープリンク](web.md#レコードのディープリンク) を参照。
