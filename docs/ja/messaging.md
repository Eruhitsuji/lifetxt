# グループ・メッセージング・配信状態

lifetxt は、フラットな人の一覧を解決可能なグループに変え、人/チーム/グループが
混在する宛先へメッセージを作成し、受信者ごとの確認状態を追跡します。すべて
life.txt レコードと設定から導かれ、ドリフトする別ストアはありません。メッセージは
普通の `M` タイプアイテムであり、「送信」とは他のすべての権威的な変更と同じ
アトミックライターで検証済みの `[ ] M ...` 行を追記することを意味します。

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

`teams` は独立した設定セクションです（`lifetxt/config.py` の
`config_team_members`）。チームのメンバーは常に人であり、グループを含みません。
`teams` エントリなしでも `user.teams` / `users.<name>.teams` からチームを暗黙的に
構築できます。1人ごとの設定セクションについては
[people.md](people.md#エイリアス) を参照してください。

展開は決定的です。重複と無効メンバーは除去され、循環は検出され（ループしない）、
未知メンバーは報告されます。

```console
$ lifetxt group list
oncall               1 member(s), 1 disabled
eng                  3 member(s), 0 disabled

$ lifetxt group show eng
eng (3 resolved member(s)):
  - alice
  - carol
  - dave

$ lifetxt group validate
All groups are valid.
```

`group list`・`group show`・`group validate` はいずれも `--json` を受け付け、
同じデータを構造化文書として返します。`group show --json` はグループの生の
`definition` と診断も含みます。

### 診断

| コード | 重大度 | 意味 |
| --- | --- | --- |
| `G001` | error | 参照が未定義のグループを指している。 |
| `G002` | error | グループが直接的、または入れ子を通じて自分自身を含む。 |
| `G003` | warning | グループ（またはその参照）が0人に解決される — 全メンバーが未知・無効、またはグループが空。 |

```console
$ lifetxt group show loop      # groups: {"loop": {"members": ["loop"]}}
loop (0 resolved member(s)):
  [ERROR] G002: Group cycle detected: loop -> loop.

$ lifetxt group validate       # groups: {"silent": {"members": ["alice"], "disabled_members": ["alice"]}}
[WARNING] G003: Group 'silent' is empty.
```

循環や未知グループへの参照はその時点で展開を止め、ループしたり推測したりしません。
`expand_group`（`lifetxt/groups.py`）は空リストを返し、診断を記録します。

## 宛先解決

送信前に、参照が誰に展開されるかを確認できます。

```console
$ lifetxt message recipients "group:eng,erin"
Resolved 4 recipient(s) from group:eng, erin:
  - alice
  - carol
  - dave
  - erin
```

結果は元の参照と解決後の宛先集合の両方を保持するため（`--json` 出力の
`references`・`recipients`・`expansion`・`diagnostics`）、監査証跡に「誰を宛先に
したか」を残しつつ、メッセージ本体は読みやすいままです。`group:`・`team:`・
`user:`・`person:` のプレフィックスなしの名前は、まずグループディレクトリと
チームディレクトリに対して解決されます。グループやチームの名前と偶然一致する名前は、
明示的にプレフィックス（`person:name`）を付けない限り、その人物ではなくグループ/
チームとして解決されます。

未知グループへの参照解決は `group show` と同じ形で失敗します。

```console
$ lifetxt message recipients "group:nosuch"
Resolved 0 recipient(s) from group:nosuch:
  [ERROR] G001: Unknown group 'nosuch'.
```

（`message recipients` はいずれかの診断が error のとき終了コード1を返します。）

## メッセージ作成

```console
$ lifetxt message send "Deploy tonight" --to "eng,erin" --ack-policy all
Appended message to life.txt (4 recipient(s)):
  [ ] M Deploy_tonight sender:self recipient:alice recipient:carol recipient:dave recipient:erin group:eng ack_policy:all

$ lifetxt message send "Ping" --to "oncall" --sender alice --dry-run
[ ] M Ping sender:alice recipient:alice group:oncall
```

書き込まれる Message アイテムは、解決後の人を `recipient:`（1人につき1つ、重複除去
済み）として列挙し、元のグループ/チーム参照を監査用に `group:` として保持します
— ただし参照が自分自身の文字列以外に展開された場合のみで、素の人物参照は `group:`
を生成しません。`--ack-policy` は `any`（既定）・`all`・明示的な件数を受け付け、
`any` と異なる場合のみ `ack_policy:` として書き込まれます。`--sender` は設定済み
ユーザーが既定値です（`user.name` → `defaults.person` → `message.default_sender`
→ リテラルの `self` の順）。`--body` はタイトルと同じ空白→アンダースコア変換で
`body:` を追加します。`--dry-run` は書き込まずに行だけを出力し、`--output` は
解決後の書き込み先ではなく指定ファイルに追記します。

宛先解決が失敗、または誰にも解決されない場合、`message send` は書き込みを拒否します。

```console
$ lifetxt message send "Test" --to "group:nosuch" --dry-run
ERROR: G001 Unknown group 'nosuch'.

$ lifetxt message send "x" --to "group:silent"    # silent の唯一のメンバーは無効化済み
ERROR: No recipients resolved.
```

（いずれも終了コード1で、life.txt には書き込まれません。）

### Message アイテムを直接書く

Message アイテムの作成方法は `message send` だけではありません。
`lifetxt quick`・`lifetxt assist`（およびそのエイリアス `lifetxt new`）も
`--kind M` を受け付け、手書きのアイテムを作成できます。この経路にはグループ/
チームの展開はありませんが、`apply_config_defaults_to_item`（`lifetxt/cli.py`）が
`message` 設定セクション（`message.default_sender`・`message.default_channel`・
`message.default_service`）から `sender:`・`channel:`・`service:` を、まだ存在
しない場合に補完します。宛先集合をグループ/チームから決めたいときは
`message send` を、`recipient:` を手で書いたり `message send` にフラグのない
通知タイミング詳細（`notify_at:`・`notify_from:`/`notify_to:`）を付けたいときは
`quick`/`assist` を使います。

### 検証

`lifetxt check` は、どのように書かれたかに関わらず全ての `M` アイテムを検証します。

- `E205` — `sender:` を持たない Message アイテム（error。クリーンな check を阻害）。
- `E206` — `recipient:` を持たない Message アイテム（error）。複数の受信者は
  `recipient:` を繰り返します。1つの `recipient:` 詳細行にカンマ区切りリストを
  入れることはできません。
- `W210` — `notify_from:`/`notify_to:` の片方だけが存在する。
- `W211` — `notify_to:` が `notify_from:` より前。
- `W212` — Message アイテムでステータス `[N]` を使用（ワークフローステータスが
  推奨されます）。

```console
$ printf '[ ] M NoSenderOrRecipient\n' | lifetxt check
1: ERROR E205: Message items require sender:PERSON.
1: ERROR E206: Message items require recipient:PERSON. Repeat recipient: for multiple recipients.
```

## 配信状態

配信状態はメッセージレコード自体から導かれます。`ack:` は確認、`read:` は既読、
`skip:` はスキップを表します。各受信者は `delivery-state-v1` レコード
（pending / read / acknowledged / skipped）に対応します — `delivered` と
`failed` もスキーマの状態列挙に含まれますが、現時点でこの機能がそれらを
書き込むことはありません。将来の配信トランスポート連携のために予約されています。

```console
$ lifetxt message status
$ lifetxt message status --id M-9 --policy all
```

`message status` は（アイテムを読む他のコマンドと同様に）1つ以上の入力パスを
受け付け、指定がなければ標準入力を読みます。`--id` は1つのメッセージの `id:`
詳細に絞り込み、`--policy` はそのレポートに限りメッセージ自身の `ack_policy:`
詳細を上書きします（ファイルへの書き戻しはありません）。`--json` はメッセージ
ごとの完全なサマリー（`message_id`・`title`・`recipient_count`・状態別
`counts`・`acknowledgement`・`states`）を出力します。

```console
$ lifetxt message status
Deploy_tonight [M-9] recipients=4 ack=2/3 (all) open
    alice            acknowledged
    carol            acknowledged
    dave             read
    erin             skipped
```

（4人受信者のメッセージに `... ack:alice ack:carol read:dave skip:erin
ack_policy:all` を付けた場合）

確認ポリシーが完了を決めます。`any` は1人の確認で完了、`all` は skip を除く
全員が必要、件数はその数だけ必要です（skip を除いた受信者数が上限）。1人の
確認だけで `all` のメッセージが完了することはありません — スキップされた受信者は
分子・分母の両方から除外されるため、スキップされていない全員が確認すれば `all`
のメッセージも完了します。

### 注意点: `ack:` は `lifetxt check` から日時キーに見える

`ack` は共有の `DATE_OR_DATETIME_KEYS`（`lifetxt/model.py`）の1つで、`M` に
限らず全アイテム種別で使われるリストです。このルールは配信状態機能より前から
存在し、`ack:` の他の用途（例: リマインダーの確認）のために定義されています。
その結果、`delivery.py` がこの機能のために `ack:` を意図的に受信者名のリストとして
読んでいるにもかかわらず、`lifetxt check` は Message アイテムの `ack:PERSON` 値
それぞれに対して `W203` を出します。

```console
$ lifetxt check life.txt
life.txt:6: WARNING W203: ack: should use YYYY-MM-DD or YYYY-MM-DDTHH:MM, optionally with :SS, fractional seconds, and timezone.
```

同様に `read:`・`skip:`・`ack_policy:` は `KNOWN_KEYS` / `MESSAGE_RECOMMENDED_KEYS`
のいずれにも含まれていないため、`check` はこれらを未知キーではなく `W106`
（「custom」キー、そのまま保持）として報告します。これらの警告はどちらも
`check` の終了コードをブロックせず（error ではなく warning）、配信の追跡にも
影響しません — アイテムは有効なままで `message status` も正しく読みます —
が、`ack:`/`read:`/`skip:` を使う Message アイテムが完全にクリーンな `check`
を通ると期待しないでください。

## MCP

AI クライアントは読み取り専用の `list_groups`・`resolve_recipients`・
`get_delivery_state` を使い（`lifetxt/mcp.py`）、CLI と同じ展開・配信ロジックを
再利用します。`resolve_recipients` の `to` はカンマ区切り文字列と参照のリストの
どちらでも受け付けます。`get_delivery_state` は `message status --id`/`--policy`
と同じ `id`/`policy` フィルタを受け付け、`{"count": N, "messages": [...]}` を
返します。メッセージを送信したり `ack:`/`read:`/`skip:` を変更する MCP ツールは
現時点で存在しません — 作成と確認は CLI/TUI/Web の操作のままです。AI クライアントが
新規アイテム（Message アイテムを含む）を直接書き込まず人によるレビュー用に
*提案*するための Unified Inbox ツールについては [inbox.md](inbox.md#mcp) を
参照してください。

メッセージの送受信数を人物ごと・グループごとのサマリーに集約する概要ビューに
ついては [people.md](people.md) も参照してください。
