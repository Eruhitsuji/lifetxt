# ネイティブ item event

`record:item_event` は通常の life.txt item に対する意味のある変更を表す、
共通の追記専用 evidence record です。親 item と同じ life.txt に Note として
保存されます。既存ファイルはそのまま有効で、履歴の推測や backfill は行いません。

## envelope

各 event は `record:item_event`、`id`、`parent`、`event`、`at`、
`sequence`、`transaction`、`source_revision` をそれぞれ1つ持ちます。
`at` は正規化した UTC、`source_revision` は compound mutation 直前の
SHA-256 revision です。任意の `actor` と `source` で実行者と surface を
記録できます。安定 identity は `(record kind, id)` の組で、正の sequence は
親ごとに採番します。

閉じた event 語彙は `created`、`status_changed`、`completed`、`reopened`、
`canceled`、`relation_added`、`relation_removed`、`schedule_changed` です。
relation は `follows`、`realizes`、`replaced_by`、schedule は `on`、`due`、
`from`、`to`、`at` に限定します。title、type、任意 custom field の変更は v1
の item event ではありません。

例:

```text
[N] N Item_task-1_000002 record:item_event id:IE-task-1-000002 parent:task-1 event:completed at:2026-09-10T10:00:00Z sequence:2 transaction:ITX-task-1-000002 source_revision:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa actor:me source:cli before_status:[/] after_status:[x] completed_at:2026-09-10T10:00:00Z
```

## validation と completeness

identity、transaction、親内 sequence の重複、gap、時刻の逆行、status の
不連続、不正 payload、現在 status との不一致を診断し、その stream を
authoritative として扱いません。`created` event がない stream も
`coverage:partial` として読めますが、complete と表示してはいけません。
手動編集は有効な life.txt のままですが、partial な履歴を暗黙に complete
へ昇格させません。

既存の `record:progress_event`、`record:ticket_event`、`record:time_entry` の
保存形式は変更しません。native-history adapter は元の record kind と ID を
保持して reader 向けに正規化します。Remote Safe Mode では4種類すべてが
親 item の access tuple を継承します。

公開 JSON contract は
[`item-event-v1.schema.json`](../../dist/schemas/item-event-v1.schema.json) です。

## capture 対象の mutation

共通 producer は変更前後の item state を検証して閉じた payload を導出し、
state の置換と event を1回の exact-revision write で確定します。現在の CLI
では、IDを持つ `quick` の作成、`start` の status 遷移、`done` / `complete`、
`reopen`、`due` を capture します。繰り返し `complete` は古い instance の
完了と新しい instance の作成を同じ write に記録します。既存 surface に対応
operation がある場合に利用できる typed cancellation と lifecycle relation の
追加・削除も producer が提供します。

dry-run は event を追加しません。stale revision または payload と state の
不一致では state と event のどちらも書きません。安定した設定済み ID がない
item は従来の mutation 動作を保つため、native-history coverage は partial
です。既存の ticket / progress writer は専用 record を維持し、item event を
二重に出力しません。
