# プロジェクトとポートフォリオ

プロジェクトは `project:` 詳細に使われる値です。lifetxt は同じプロジェクトを共有する
アイテムを集約し、設定レジストリの静的メタデータを任意で統合して、進捗・健全性・
負荷・マイルストーン・リスク・意思決定・会議を報告します。新しいアイテム型は導入
しません。

## レコード

`record:` を付けた通常のアイテムでプロジェクトと成果物を記述します。

| レコード           | 型   | 主なキー                                       |
| ------------------ | ---- | ---------------------------------------------- |
| `record:project`   | N    | `project:`・`owner:`・`area:`・`state:`・`due:`・`do:`（開始）・`visibility:` |
| `record:milestone` | D    | `project:`・`due:`・`owner:`                    |
| `record:risk`      | N    | `project:`・`severity:`・`state:`・`owner:`     |
| `record:issue`     | N    | `project:`・`severity:`・`state:`               |
| `record:decision`  | N/J  | `project:`・`on:`（決定日）                     |
| `record:meeting`   | E    | `project:`・`on:`・`at:`                        |

`project:` を持つ通常のタスク・締切はプロジェクト作業として数えます。タスクは
`depends_on:` の対象が未完了なら**ブロック中**、`due:` が今日より前なら**期限超過**
です。

## レジストリ

変化の少ない静的メタデータは設定の `projects` に置きます。

```json
{
  "projects": {
    "web": {
      "display_name": "Website Revamp",
      "aliases": ["website"],
      "default_assignee": "alice",
      "default_area": "work",
      "visibility": "shared"
    }
  }
}
```

エイリアスは全コマンドで正式名に解決されます。進捗・リスク・意思決定などの変化する
データは設定ではなく life.txt レコードに残します。

## コマンド

```console
$ lifetxt project list                 # プロジェクトごとの進捗と健全性
$ lifetxt project show web             # 1プロジェクトの集約ハブ
$ lifetxt project health --all         # 健全性ラベルと算出式
$ lifetxt project timeline web         # 日付順のアイテム
$ lifetxt project workload web         # 担当者ごとの open/done/overdue
$ lifetxt project risks web            # 重大度順のリスク
$ lifetxt portfolio                    # 全プロジェクトの比較
```

レコードの作成（ワークスペースの書き込み先へ追記）:

```console
$ lifetxt project new payments --owner carol --area finance --due 2026-12-01
$ lifetxt project add milestone web "Launch MVP" --due 2026-08-15
$ lifetxt project add risk web "Latency spike" --severity high --owner bob
$ lifetxt project add decision web "Use Postgres" --on 2026-06-20
$ lifetxt project add meeting web "Kickoff" --on 2026-06-01
```

`--dry-run` で書き込まずに行内容だけを表示します。

## 算出の透明性

導出値はすべて算出方法を明示します。

- **進捗** = `done_tasks / non_cancelled_tasks * 100`。非キャンセル作業が無い場合は
  理由付きで `null`。
- **健全性** = 未対応の critical/high リスク、または進捗50%未満での期限超過があれば
  `red`、期限超過・ブロック・未対応の medium/low リスクがあれば `yellow`、それ以外は
  `green`。各レポートは理由と、データ不足による限界（例:「基準日が無いため期限超過は
  未評価」）を列挙します。
