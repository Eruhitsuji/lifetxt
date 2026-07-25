# グループ・メッセージング・配信状態

lifetxt は、フラットな人の一覧を解決可能なグループに変え、人/チーム/グループが
混在する宛先へメッセージを作成し、受信者ごとの確認状態を追跡します。すべて
life.txt レコードと設定から導かれ、ドリフトする別ストアはありません。

## グループ

グループは設定の `groups` セクションに定義します。メンバーは人・チーム
（`team:name`）・他グループを指定でき、入れ子にできます。

```json
{
  "teams":  { "platform": { "members": ["carol", "dave"] } },
  "groups": {
    "oncall": { "members": ["alice", "bob"], "disabled_members": ["bob"] },
    "eng":    { "members": ["oncall", "team:platform"], "aliases": ["engineering"] }
  }
}
```

展開は決定的です。重複と無効メンバーは除去され、循環は検出され（ループしない）、
未知メンバーは報告されます。

```console
$ lifetxt group list
$ lifetxt group show eng
$ lifetxt group validate
```

診断: `G001` 未知グループ、`G002` 循環、`G003` 空/宛先なし。

## 宛先解決

送信前に、参照が誰に展開されるかを確認できます。

```console
$ lifetxt message recipients "group:eng,erin"
```

結果は元の参照と解決後の宛先集合の両方を保持するため、監査証跡に「誰を宛先にしたか」
を残しつつ、メッセージ本体は読みやすいままです。

## メッセージ作成

```console
$ lifetxt message send "Deploy tonight" --to "eng,erin" --ack-policy all
$ lifetxt message send "Ping" --to "oncall" --sender alice --dry-run
```

書き込まれる Message アイテムは、解決後の人を `recipient:`、元のグループ/チーム参照を
監査用に `group:` として保持します。`--ack-policy` は `any`（既定）・`all`・明示的な
件数を受け付けます。

## 配信状態

配信状態はメッセージレコード自体から導かれます。`ack:` は確認、`read:` は既読、
`skip:` はスキップを表します。各受信者は `delivery-state-v1` レコード
（pending / read / acknowledged / skipped）に対応します。

```console
$ lifetxt message status
$ lifetxt message status --id M-9 --policy all
```

確認ポリシーが完了を決めます。`any` は1人の確認で完了、`all` は skip を除く全員が必要、
件数はその数だけ必要です。1人の確認だけで `all` のメッセージが完了することはありません。

## MCP

AI クライアントは読み取り専用の `list_groups`・`resolve_recipients`・
`get_delivery_state` を使い、CLI と同じ展開・配信ロジックを再利用します。
