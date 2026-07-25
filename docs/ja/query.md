# クエリ言語と保存ビュー

lifetxt には単一のクエリ言語があり、CLI の `query` コマンド、保存ビュー、MCP の
`run_query` ツールで共有されます。一度書いたフィルタはどのサーフェスでも同じ結果に
なり、誤りは黙って誤った結果を返すのではなく型付き診断として報告されます。

## 文法

クエリは空白区切りの項の列です。値は引用符で囲めます。

| 項                       | 意味                                                |
| ------------------------ | --------------------------------------------------- |
| `field:value`            | メンバーシップまたは詳細の等価                       |
| `field:a,b`              | フィールド内の値の OR                                |
| `field=value`            | `:` と同じ                                          |
| `field<DATE` `field>DATE`| 日付比較（`<`・`>`・`<=`・`>=`・`!=`）               |
| `-tag:value`             | 除外（`exclude_tag:value` も可）                     |
| `open`                   | 未完了のワークフローステータスのみ                  |
| `text:"free text"`       | タイトルへの部分一致（素の語句も可）                |

異なるフィールド同士は AND、同一フィールドの複数値は OR で結合されます。

### フィールド

- **メンバーシップ**: `status`・`type`/`kind`・`project`・`tag`・`tag_all`・
  `user`・`person`・`owner`・`assignee`・`attendee`・`sender`・`recipient`・`team`
- **日付**: `due`・`do`・`from`・`to`・`on`・`at`・`done`・`created`・`updated`
- **詳細（等価）**: `area`・`context`・`loc`・`priority` ほか既知キー
- **テキスト**: `text` / `q`、または素の語句

未知のフィールドは `Q001` 警告として無視され、不正な日付は `Q002` エラーになります。

## CLI

```console
$ lifetxt query "open project:web tag:urgent due<2026-08-01"
$ lifetxt query "area:work" --sort due --limit 10 --format table
$ lifetxt query "status:done project:web" --format json
```

## 保存ビュー

よく使うクエリを設定の `saved_views` に保存します。

```json
{
  "saved_views": {
    "web_open":  { "query": "open project:web", "sort": "due", "limit": 10 },
    "overdue":   { "query": "open due<2026-07-25" },
    "urgent":    "tag:urgent"
  }
}
```

ビューはオブジェクト（`query` と任意の `sort`・`order`・`limit`）または単なる
クエリ文字列です。実行と確認:

```console
$ lifetxt view list
$ lifetxt view show web_open
$ lifetxt view validate
$ lifetxt view run web_open --format table
```

保存ビューは `saved-view-v1.schema.json` で検証され、`view validate` は空
（`V001`）や不正（`V002`）なクエリを報告します。

## MCP

AI クライアントは `run_query`・`list_saved_views`・`run_saved_view` を使います。
文法も結果（クエリ診断を含む）も人が見るものと同一です。
