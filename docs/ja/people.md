# 人物・グループの概要ビュー

lifetxt は、ある人物に関するすべて — 担当作業、送受信メッセージ、会議、プレゼンス、
プロジェクト、待ち項目、チーム/グループ所属 — を1つのビューに集約します
（`lifetxt/people.py`）。project・group・delivery・status のロジックを再利用し、
レコードを複製しません。名前は設定のユーザーエイリアスで解決され、`me` と
`self`（または宣言済みの任意のエイリアス）は同一人物を指します。
`person_overview`・`people_list`・`group_overview` はアイテム集合・設定・基準日を
受け取る読み取り専用の決定的な関数で、CLI・MCP・[search.md](search.md) の
`find --type person` はすべて同じ関数を呼ぶため、「誰が誰か」で食い違うことは
ありません。

## コマンド

```console
$ lifetxt person list          # 見つかった全員とカウント
alice                open=1 messages=1 meetings=1
bob                  open=1 messages=0 meetings=1
carol                open=0 messages=1 meetings=0
dave                 open=0 messages=1 meetings=0
erin                 open=0 messages=1 meetings=0
self                 open=0 messages=1 meetings=0

$ lifetxt person show alice    # 1人の完全な概要
alice (al)
  presence: active 2026-08-10T08:00
  open=1 waiting=0 overdue=1 sent=0 received=1 meetings=1
  teams: -  groups: eng, oncall
  Assigned (open) (1):
    - [ ] Fix_login_bug @web due:2026-08-05
  Overdue (1):
    - [ ] Fix_login_bug @web due:2026-08-05
  Meetings (1):
    - [ ] Standup
  projects:
    - web (member, 1 task(s))

$ lifetxt person group eng     # グループのメンバーと負荷
eng (3 member(s)) open=1 overdue=1
  alice                open=1 overdue=1 received=1
  carol                open=0 overdue=0 received=1
  dave                 open=0 overdue=0 received=1
```

3つのサブコマンドはいずれも入力パスを受け付け（指定がなければ標準入力を読み）、
`--json` で完全な構造化文書を返します。

`person show` は解決後の人物について次を報告します。

- **presence** — 最新のアクティブなステータスレコード（`person:` が一致する
  `S` 種別アイテム。`S` 種別については
  [life_txt_format_spec.md](life_txt_format_spec.md) 参照）
- **assigned / waiting / overdue** — `assignee:` または `owner:` が一致する
  未完了の `T`（Task）・`D`（Deadline）アイテム。**カウントされるのは Task と
  Deadline のみ** — Reminder・Habit・Event に `assignee:`/`owner:` を付けても
  （キー自体はどの種別でも有効ですが）ここではカウントされません。「未完了」は
  ステータス `[ ]`・`[/]`・`[?]` を意味し、**waiting** は assigned の `[?]`
  部分集合、**overdue** は assigned のうち `due:` が基準日（既定は今日。呼び出し側が
  別の日付を渡すことも可能）より前のものです
- **messages sent / received** — `sender:`/`recipient:` が一致する `M` 種別
  アイテム。[messaging.md](messaging.md) 参照
- **meetings** — `attendee:` が一致する `E` 種別アイテム
- **projects** — （[projects.md](projects.md) の `collect_projects` による）
  本人がオーナーであるか、少なくとも1つ担当タスクを持つプロジェクト。各行は
  `owner`（真偽値）と `assigned_tasks`（そのプロジェクト内の担当タスク数）を
  報告します
- **memberships** — 本人を含むように解決されるチーム（`teams` 設定セクション、
  `user.teams`、`users.<name>.teams`）とグループ
  （[messaging.md](messaging.md#グループ) 参照）

一度も登場したことのない名前でも、エラーにはならず有効な全ゼロの概要が返ります
— `person show` は名前の存在を検証しません。

```console
$ lifetxt person show nosuchperson life.txt
nosuchperson
  open=0 waiting=0 overdue=0 sent=0 received=0 meetings=0
```

`person group` はグループを決定的に展開し、各メンバーの未完了作業・期限超過数・
受信メッセージ数と、グループ合計（`total_assigned_open`・`total_overdue`）を
表示します。`person show` と異なり、`person group` はグループ名を検証し、
未知のグループでは明確に失敗します。

```console
$ lifetxt person group nosuch life.txt
ERROR: Unknown group 'nosuch'. Known: oncall, eng
```

（終了コード1。`group show` や `message recipients` が未知グループに対して報告する
`G001` 相当の失敗と同じですが、`person group` は型付き診断ではなく単純な
`ValueError` として送出します。）

### `person list` はプレゼンスのみの人物も拾う

`person list` は、未完了 Task/Deadline の `assignee:`/`owner:`、Message の
`sender:`/`recipient:`、Event の `attendee:`、**または** `S`（ステータス/
プレゼンス）アイテムの `person:` として登場した全員をカウントします —
他の活動が一切なくてもです。

```console
$ printf '[ ] S ghost_status person:ghost state:away from:2026-08-10T08:00\n' | lifetxt person list
ghost                open=0 messages=0 meetings=0
```

`person show`/`--json` の `counts` オブジェクトは同じフィールド集合を反映します。
`assigned_open`・`waiting`・`overdue`・`messages_sent`・`messages_received`・
`meetings` — さらに `person list` の1行サマリーには含まれないトップレベルの
`presence`・`projects`・`memberships` フィールドも含みます。

## エイリアス

1人が複数の呼び名を持てます。設定済みユーザーは `user.aliases` から、それ以外の
人物は `users` からエイリアスを得ます。

```json
{
  "user": { "name": "self", "aliases": ["me"] },
  "users": { "alice": { "aliases": ["al"] } }
}
```

```console
$ lifetxt person show me
self (me)
  open=0 waiting=0 overdue=0 sent=1 received=0 meetings=0

$ lifetxt person show self
self (me)
  open=0 waiting=0 overdue=0 sent=1 received=0 meetings=0
```

`lifetxt person show me` と `lifetxt person show self` は同じ概要を返します
（`resolve_person` は集約の前に全てのエイリアスを正規名へマッピングします）。
`me` に割り当てられた作業は `person list` で `self` に集約されます。これは上の
`alice` に対して `person show alice`/`person show al` のどちらを使っても同じ
正規名解決が使われるのと同じ仕組みです — `person show alice` はヘッダーに
`alice (al)` と表示し、他に知られているエイリアスを示します。

`users.<name>.teams` は（トップレベルの `teams` 設定セクションや `user.teams`
と並んで）明示的な `teams.<team>.members` エントリなしに人物をチームメンバーに
する方法の1つです。`teams` と `groups` の組み合わせ方については
[messaging.md](messaging.md#グループ) を参照してください。

## MCP

AI クライアントは読み取り専用の `list_people`・`get_person`・
`get_group_overview` を使い（`lifetxt/mcp.py`）、CLI と同じ集約を再利用します
（`get_person` と `get_group_overview` は `name` 引数が欠けている場合、
`get_group_overview` は未知のグループ名の場合、CLI と同じエラー挙動として
`ValueError` を送出します）。人物概要は `person-overview-v1.schema.json` に
従います。
