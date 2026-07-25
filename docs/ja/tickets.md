# 開発チケット

lifetxt はデータベースを使わず、プレーンテキストの Task モデルも置き換えずに、
Redmine 風のチケット管理を追加します。チケットは `record:ticket` を付けた通常の
`T` レコードで、既存のフィルタ・アジェンダ・レポートがそのまま理解します。チケット層
は、正規フィールド・粗い `[ ]`/`[x]` の上に載る詳細な `ticket_status`・検証・集約を
加えます。

チケットワークフローを必要としない運用上の懸念には、汎用の `record:issue` レコードが
引き続き使えます。

## フィールド

チケットは次の正規フィールドを持てます（レジストリ管理のものは設定で検証）。

`tracker`・`ticket_status`・`priority`・`severity`・`reporter`・`assignee`・
繰り返し `watcher`・`component`・`category`・`version`・`milestone`・`sprint`・
`est`・`elapsed`・`story_points`・`resolution`・`closed_by`・`branch`・繰り返し
`commit`/`pr`・`build`、および共有リレーションキー `parent`・`depends_on`・
`blocks`・`related`・`duplicate_of`・`replaced_by`。

## ステータス対応

`ticket_status` は詳細な状態で、粗い life.txt ステータスに対応づけられるため既存の
フィルタが機能し続けます。

| ticket_status                          | life.txt |
| -------------------------------------- | -------- |
| new, triaged, assigned                 | `[ ]`    |
| in_progress, review, testing           | `[/]`    |
| needs_info, blocked                    | `[?]`    |
| deferred                               | `[>]`    |
| resolved, closed                       | `[x]`    |
| rejected, duplicate, wont_fix          | `[-]`    |

矛盾する組（例: `[ ]` 行に `ticket_status:closed`）は `TK003` として報告されます。
対応は `ticketing.statuses` で上書き・拡張できます。

## 設定

```json
{
  "ticketing": {
    "id_prefix": "BUG",
    "trackers": ["bug", "feature", "task", "support"],
    "priorities": ["low", "normal", "high", "urgent"],
    "severities": ["minor", "major", "critical", "blocker"],
    "required_fields": ["assignee"],
    "defaults": { "tracker": "task", "priority": "normal" }
  }
}
```

## コマンド

```console
$ lifetxt ticket new "Login fails" --tracker bug --priority high --assignee alice --project web
$ lifetxt ticket list --tracker bug --open
$ lifetxt ticket show BUG-1
$ lifetxt ticket assign BUG-1 carol
$ lifetxt ticket edit BUG-1 --set severity=critical --set component=auth --unset milestone
$ lifetxt ticket link BUG-2 depends_on BUG-1
$ lifetxt ticket unlink BUG-2 depends_on BUG-1
$ lifetxt ticket close BUG-1 --status resolved --resolution "fixed in v2"
$ lifetxt ticket reopen BUG-1
$ lifetxt ticket validate
```

`ticket new` は `id_prefix` から次の id を採番します。`ticket show` は現在のレコード・
リレーション・被参照リンクを、何も変更せずに集約します。遷移は1回の書き換えで
チケットを更新します。`close` は終端ステータス・`closed_by`・`--resolution` を設定し、
`reopen` はそれらを解除します。

## 検証

`ticket validate` は次を報告します。

- `TK001` id の無いチケット
- `TK002` 未知の `ticket_status`
- `TK003` `ticket_status` が粗い life.txt ステータスと矛盾
- `TK004` 設定レジストリに無い値（tracker/priority/severity/component）
- `TK005` 設定された必須フィールドの欠落

## MCP

読み取り専用ツール: `list_tickets`・`get_ticket`・`validate_tickets`。チケットの
書き込みは CLI 経由です（ワークフロー強制のリモート書き込みは後続トラック）。
チケットは `ticket-v1.schema.json`、フィールドレジストリは
`ticket-field-registry-v1.schema.json` に従います。
