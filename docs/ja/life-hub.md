# ライフハブ: 日次コマンドセンター・エリア・被参照リンク

ライフハブのコマンドは、life.txt ワークスペースを「今日やるべきこと」「エリア別の
整理」「アイテム同士のつながり」を一望できる場所に変えます。すべてのコマンドは
共有の集約を読み取るため、CLI・MCP・将来の Web で同じ内容を見られます。

## 日次コマンドセンター

`today` は一日を決定的に集約します。

```console
$ lifetxt today
$ lifetxt today --mode morning --horizon 5
$ lifetxt today --person self --json
```

バケット:

- **overdue** — `due:` が今日より前のタスク/締切
- **due today** — `due:` が今日
- **upcoming** — `due:` が期間内（既定3日）
- **blocked** — `depends_on:` の対象が未完了
- **waiting** — ステータス `[?]`
- **messages** — 未処理の `M` アイテム（`--person` で絞り込み可）
- **habits** — 未処理の `H` アイテム
- **captures** — `project:`・`due:`・`assignee:` の無い未整理タスク（インボックス）
- **project attention** — green 以外のプロジェクトと健全性の理由
- **safety** — 設定の妥当性の簡易シグナル

同じ集約は MCP ツール `get_command_center` からも利用できます。

## エリア

`area:` は `project:` の上位にある任意の整理軸です。アイテムのエリアは自身の
`area:` 詳細から、プロジェクトのエリアはレコードまたはレジストリの `default_area`
から決まります。エリアはデータに現れる値そのものであり、`work`・`research`・
`health`・`home`・`finance`・`family`・`learning` はあくまで例で、強制ではありません。

```console
$ lifetxt area list
$ lifetxt area show work
```

MCP: `get_areas`。

## 被参照リンク（backlinks）

`backlinks` は「このアイテムを何が参照しているか」— リンクグラフの入力側 — を
関係（`parent`・`ref`・`depends_on`・`blocks`・`related`）ごとに表示します。

```console
$ lifetxt backlinks T-1
$ lifetxt backlinks T-1 --json
```

MCP: `get_backlinks`。

## MCP でのプロジェクト参照

プロジェクトとポートフォリオの集約は、読み取り専用ツール `get_projects`・
`get_project`・`get_portfolio` として AI クライアントに公開されます。CLI の
`project`/`portfolio` と同じ `lifetxt/projects.py` を再利用するため、透明な進捗・
健全性の算出式を含め、人が見る内容とモデルが見る内容が一致します。
