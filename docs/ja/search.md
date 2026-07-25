# グローバル検索

`find` は lifetxt が把握するすべて — life.txt アイテムと、算出される派生エンティティ
（プロジェクト・人物・グループ・エリア・staged インボックス提案）— を横断検索します。
結果はエンティティ種別ごとにグループ化され、一致したフィールドと短いスニペットが
付きます。直接スキャンし、ベンチマークが正当化するまでインデックスは作りません。

アイテム内のフィールド指定・正規表現検索には `search` を使います。`find` はより広い
横断ビューです。

## 使い方

```console
$ lifetxt find web
$ lifetxt find alice --type person
$ lifetxt find example.com          # url: 詳細に一致
$ lifetxt find roadmap              # アイテム body に一致
$ lifetxt find engineering --type group
$ lifetxt find widgets --json
```

## 検索対象

| エンティティ | 一致対象                                                |
| ------------ | ------------------------------------------------------- |
| `item`       | タイトル・body・任意の詳細値（project・url・tag など）  |
| `project`    | 名前・表示名・オーナー・エリア                          |
| `person`     | 人物名（担当者・送信者・プレゼンスなどから）            |
| `group`      | グループ名・エイリアス・メンバー                        |
| `area`       | エリア名                                                |
| `proposal`   | staged インボックス提案の行とソース                     |

`--type` は検索を1つ以上のエンティティ種別に限定します（フラグを繰り返すか、カンマ
区切りで指定）。`--limit` は種別ごとの結果数を制限します。

## MCP

AI クライアントは読み取り専用の `global_search` ツールを、同じ `term`・`types`・
`limit` 引数で使います。結果は `global-search-v1.schema.json` に従います。
