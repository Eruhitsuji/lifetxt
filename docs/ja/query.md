# Query Language and Saved Views

lifetxt には 1 つの query language があり、CLI `query` command、saved views、MCP `run_query` tool で共有されます。一度書いた filter はどの surface でも同じように動作し、mistake は silent wrong result ではなく typed diagnostics として返ります。

## Grammar

query は whitespace-separated terms です。values は quoted にできます。

| Term | Meaning |
| --- | --- |
| `field:value` | membership または detail equality |
| `field:a,b` | 同じ field 内の values の OR |
| `field=value` | `:` と同じ |
| `field<DATE` `field>DATE` | date comparison (`<`, `>`, `<=`, `>=`, `!=`) |
| `progress<50%` `progress>=3/4` | [`progress:`](life_txt_format_spec.md#75-effort-keys) の ratio comparison (`<`, `>`, `<=`, `>=`, `!=`) |
| `-tag:value` | exclude。`exclude_tag:value` も可 |
| `open` | open workflow statuses のみ |
| `text:"free text"` | title への substring match。bare words も可 |

異なる fields は AND で結合されます。同じ field の複数 values は OR です。

### Fields

- **Membership**: `status`, `type`/`kind`, `project`, `tag`, `tag_all`, `user`, `person`, `owner`, `assignee`, `attendee`, `sender`, `recipient`, `team`
- **Dates**: `due`, `do`, `from`, `to`, `on`, `at`, `done`, `created`, `updated`
- **Progress**（ratio comparison）: `progress`。例: `progress<50%` や
  `progress>=3/4`。percentage と fraction のどちらの値も、validation で使う
  [`progress:`](life_txt_format_spec.md#75-effort-keys) parser と同じもので
  ratio に正規化されるため、item がどちらの表記を使っていても正しく比較され
  ます。item の `progress:` 値が invalid な場合、または `progress:` detail
  が無い場合は、どの `progress` comparison にも一致しません -- 値が無いこと
  を暗黙に `0%` とは扱いません。
- **Details** (equality): `area`, `context`, `loc`, `priority`, and any known key
- **Custom**（equality、opt-in）: [汎用 `custom_fields`](config.md#汎用-custom-field) の
  definition のうち `filterable: true` のもの
- **Text**: `text` / `q`, or bare words

unknown fields は `Q001` warning になり ignored されます。invalid dates は `Q002` error です。invalid な `progress` comparison value は `Q005` error です。warnings は result set と一緒に返りますが、errors は query を止めます。field typo が silently zero results にならず、malformed date や progress comparison が valid のふりをしないようにするためです。

### Custom field

top-level の [`custom_fields`](config.md#汎用-custom-field) 設定で宣言された field は、
その definition が `filterable: true` を設定している場合に限り、認識される
`field:value` / `field=value` equality query field になります：

```console
$ lifetxt query "energy:high"
$ lifetxt view run energetic-notes
```

`filterable: false`（既定）のまま残された field は、一致する item 上では
引き続き validation される metadata ですが、それを query すると未宣言の key
と全く同様に `Q001` が報告されます -- validation のために field を宣言する
ことは、それを黙って queryable にはしません。custom field に対する数値/日付の
比較演算子（`<`、`>` など）はまだ対応していません -- equality/membership
matching のみが対応しています。filterable な custom field を使う saved view
もこの同じ grammar を通じて実行されるため、別実装はなく、`view
validate`/`view run` は ad-hoc な query と全く同じように動作します。

## CLI

```console
$ lifetxt query "open project:web tag:urgent due<2026-08-01"
$ lifetxt query "area:work" --sort due --limit 10 --format table
$ lifetxt query "status:done project:web" --format json
$ lifetxt query "open text:\"release plan\""
$ lifetxt query "progress<50%" --sort progress
```

`--sort progress`（および `GET /api/items` の同じ `sort`/`order` query
parameter）は item を `progress:` の ratio で並び替えます。`progress:` が
無い、または parse できない item は、`--order asc`/`desc` に関わらず常に
有効な値を持つ item の後ろに来ます -- `progress` query field 自身が使う
「値が無いことを暗黙に `0%` とは扱わない」ルールと同じです。

`--explain` を付けると、検索結果を出さずに parser が query をどう解釈したかを
確認できます。既定の出力は人向けで、`--format json` を追加すると
`lifetxt-query-explain-v1` の machine-readable な JSON envelope になります。
diagnostics も explanation に含まれ、不正な query は終了コード 1 になります。

```console
$ lifetxt query 'open project:research due<2026-10-01' --explain
$ lifetxt query 'open project:research due<2026-10-01' --explain --format json
```

## Saved views

よく使う query は configuration の `saved_views` に保存します。

```json
{
  "saved_views": {
    "web_open":  { "query": "open project:web", "sort": "due", "limit": 10 },
    "overdue":   { "query": "open due<2026-07-25" },
    "urgent":    "tag:urgent"
  }
}
```

view は object (`query` と optional `sort`、`order`、`limit`) または plain query string です。実行と確認:

```console
$ lifetxt view list
$ lifetxt view show web_open
$ lifetxt view validate
$ lifetxt view run web_open --format table
```

saved views は `saved-view-v1.schema.json` で validate されます。`view validate` は empty (`V001`) または malformed (`V002`) queries を report します。

`view run` は saved query を適用してから optional sort、order、limit を適用します。そのため 1 つの saved definition を table、JSON、MCP output で再利用できます。

## MCP

AI clients は `run_query`、`list_saved_views`、`run_saved_view` を使います。grammar も results も human が見るものと同じで、query diagnostics も含まれます。
