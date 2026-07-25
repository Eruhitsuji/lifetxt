# 人物・グループの概要ビュー

lifetxt は、ある人物に関するすべて — 担当作業、送受信メッセージ、会議、プレゼンス、
プロジェクト、待ち項目、チーム/グループ所属 — を1つのビューに集約します。project・
group・delivery・status のロジックを再利用し、レコードを複製しません。名前は設定の
ユーザーエイリアスで解決され、`me` と `self`（または宣言済みの任意のエイリアス）は
同一人物を指します。

## コマンド

```console
$ lifetxt person list          # 見つかった全員とカウント
$ lifetxt person show alice    # 1人の完全な概要
$ lifetxt person group eng     # グループのメンバーと負荷
```

`person show` は解決後の人物について次を報告します。

- **presence** — 最新のアクティブなステータスレコード
- **assigned / waiting / overdue** — 担当する未完了タスク・締切
- **messages sent / received** — 送信者/受信者として
- **meetings** — 出席するイベント
- **projects** — オーナーまたは担当タスクを持つプロジェクト
- **memberships** — 所属するチーム・グループ

`person group` はグループを決定的に展開し、各メンバーの未完了作業・期限超過数・
受信メッセージ数と、グループ合計を表示します。

## エイリアス

次の設定で:

```json
{ "user": { "name": "self", "aliases": ["me"] } }
```

`lifetxt person show me` と `lifetxt person show self` は同じ概要を返し、`me` に
割り当てられた作業は `person list` で `self` に集約されます。

## MCP

AI クライアントは読み取り専用の `list_people`・`get_person`・`get_group_overview`
を使い、CLI と同じ集約を再利用します。人物概要は
`person-overview-v1.schema.json` に従います。
