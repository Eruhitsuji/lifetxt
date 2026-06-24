# life.txt フォーマット仕様

## 1. 概要

`life.txt` は、タスク、予定、締切、リマインダー、習慣、在席状況、メッセージ、メモを 1 item 1 行で記録するプレーンテキスト形式です。

```txt
[status] type title key:value key:value ...
```

空行は無視されます。`#` で始まる行はコメントです。

## 2. status 値

| Status | 意味 |
|---|---|
| `[ ]` | 未完了 |
| `[/]` | 進行中 |
| `[x]` | 完了 |
| `[-]` | キャンセル |
| `[>]` | 延期または移動 |
| `[?]` | 保留または不確定 |
| `[N]` | Note |

## 3. type 値

| Type | 名前 | 意味 |
|---|---|---|
| `T` | Task | タスク、TODO |
| `E` | Event | カレンダー予定 |
| `D` | Deadline | 締切 |
| `R` | Reminder | リマインダー |
| `H` | Habit | 習慣、繰り返し item |
| `N` | Note | メモ |
| `S` | Status / Presence status | 現在状態、在席状態 |
| `M` | Message | 人から人へのメッセージ、通知依頼 |
| `J` | Journal / Diary | 日記、日誌、作業ログ |

## 4. title と value の規則

title と detail value は、空白やダブルクォートを含まない場合は bare string として書けます。

```txt
[ ] T Write_Report due:2026-06-12
```

空白を含む場合は `"` で囲みます。

```txt
[ ] E "Research Meeting" from:2026-06-08T13:00 to:2026-06-08T14:30
[N] N "Use more figures in the next presentation" project:research
```

## 15. 追加仕様: user / team / tag / time / id

### 15.1 user / team / group

`user:` は、`owner:`、`assignee:`、`attendee:`、`person:`、`sender:`、`recipient:` のどれにも限定しない一般的な user 参照です。
役割が明確な場合は、より具体的な key を優先してください。

`team:` と `group:` は、team 単位・group 単位の ownership、routing、filter に使います。
CLI / Web の `--team` / `team=` filter は、item の `team:` / `group:` に加えて、config の `teams` membership も利用できます。

### 15.2 tag filter

`tag:` は従来どおり複数回書けます。
CLI / Web では `--tag` / `tag=` はいずれかの tag に一致、`--tag-all` / `tag_all=` はすべての tag に一致、`--exclude-tag` / `exclude_tag=` は指定 tag を含む item を除外します。
config の `tags.aliases` と `tags.groups` は tag filter の展開に使えます。

### 15.3 datetime

日時値は従来の `YYYY-MM-DDTHH:MM` に加えて、秒と timezone offset を含められます。

```txt
from:2026-06-08T13:00
from:2026-06-08T13:00:30
from:2026-06-08T13:00+09:00
from:2026-06-08T04:00Z
at:18:00:30
```

### 15.4 id

`id:` は読み込み対象の複数 life.txt ファイル全体で一意であることを推奨します。
空白や引用符を含まない短い ASCII token を推奨しますが、iCalendar UID など外部 ID では `@` などの記号を含んでも構いません。
config の `ids.key` / `api.id_key` により、`id:` 以外の detail key を ID key として使えます。

引用文字列内では `"` を `\"`、`\` を `\\` としてエスケープします。

## 5. details

detail は必ず `key:value` 形式です。

```txt
due:2026-06-12
priority:A
project:research
loc:"Meeting Room A"
```

複数値は同じ key を複数回書いて表します。

```txt
[ ] T Create_Slides project:research tag:important tag:thesis tag:presentation
```

custom key は許可されます。パーサは未知の key を可能な限り保持します。

## 5.1 入れ子 / 階層化 record

item 行はスペースでインデントして、視覚的な階層を表せます。1 階層は 2
スペースを推奨します。

```txt
[ ] T Research_Project id:proj_research due:2026-07-31
  [ ] T Literature_Review id:task_lit
    [N] N Reading_Memo
    | Summarize the related work section.
  [ ] E Lab_Meeting from:2026-07-06T13:00 to:2026-07-06T14:00
```

インデントされた item に `parent:` が明示されていない場合、パーサは nearest
less-indented ancestor の ID key、通常は `id:`、から `parent:` を推論してよいです。
上の例では `Literature_Review` と `Lab_Meeting` は `parent:proj_research`、
`Reading_Memo` は `parent:task_lit` を継承します。

ancestor に ID がない場合、item 自体は有効ですが ID link として階層を表せないため
warning を出します。`parent:` を明示した場合は、明示値を優先します。
インデントされた `|` body 継続行も許可され、直前 item の `body:` に結合されます。

## 6. detail key の考え方

- known key は、ツールが検証、補完、ヘルプで認識する key です。
- recommended key は、type や status ごとに最初に提示する短い推奨 key です。
- custom key も構文上は有効で、保持されます。

## 7. 基本 key group

### 7.1 Common keys

| Key | 意味 | 例 |
|---|---|---|
| `id` | 安定した item ID | `id:task_001` |
| `project` | プロジェクト、作業領域 | `project:research` |
| `tag` | 自由タグ。複数指定可 | `tag:important` |
| `note` | 短い補足メモ | `note:"Check later"` |
| `url` | 関連 URL | `url:https://example.com` |

`id:` は読み込み対象の life.txt ファイル群の中で一意に保つことを推奨します。
validator は重複IDを warning `W213` として報告します。id-based API や update は
曖昧なIDを拒否する場合があります。

### 7.2 Link keys

| Key | 意味 | 例 |
|---|---|---|
| `parent` | 親 item、階層、message thread の親 | `parent:task_001` |
| `ref` | 他 item への汎用参照 | `ref:task_001` |
| `depends_on` | 先に完了・解決が必要な item | `depends_on:task_001` |
| `blocks` | この item が block している item | `blocks:task_002` |
| `related` | 弱い関連 item | `related:note_001` |

参照値は通常 `id:` を指します。config で `ids.key` / `api.id_key` を変更した場合は、その key を ID として扱います。存在しない参照、自己参照、`parent:` cycle は warning として報告されます。

### 7.2 People keys

| Key | 意味 | 例 |
|---|---|---|
| `owner` | item に責任を持つ人 | `owner:alice` |
| `assignee` | 作業を担当する人 | `assignee:alice` |
| `attendee` | 予定の参加者。複数指定可 | `attendee:alice` |
| `person` | status / presence の対象者。主に type `S` 用 | `person:self` |
| `sender` | メッセージ送信元。主に type `M` 用 | `sender:self` |
| `recipient` | メッセージ送信先。複数指定可 | `recipient:alice` |

`person` は在席状態を記録する対象者に使います。type `S` 以外では、`owner`、`assignee`、`attendee` のような具体的な key を優先します。Message では `sender` と `recipient` を使います。

### 7.3 Time keys

| Key | 意味 | 例 |
|---|---|---|
| `from` | 期間の開始日時 | `from:2026-06-08T13:00` |
| `to` | 期間の終了日時 | `to:2026-06-08T14:30` |
| `on` | 終日の日付 | `on:2026-06-08` |
| `at` | リマインダーまたは実行時刻 | `at:18:00` |
| `due` | 締切日または締切日時 | `due:2026-06-12` |
| `do` | 実行予定日または実行予定日時 | `do:2026-06-10` |
| `done` | 完了日または完了日時 | `done:2026-06-05` |
| `notify_at` | メッセージ通知日または通知日時 | `notify_at:2026-06-06T09:00` |
| `notify_from` | 通知期間の開始 | `notify_from:2026-06-06T09:00` |
| `notify_to` | 通知期間の終了 | `notify_to:2026-06-06T17:00` |

### 7.4 Recurrence keys

| Key | 意味 | 例 |
|---|---|---|
| `repeat` | 繰り返し規則 | `repeat:daily` |
| `interval` | N 単位ごとに繰り返す | `interval:2` |
| `until` | 最後の繰り返し日または日時 | `until:2026-12-31` |
| `count` | 最大 occurrence 数 | `count:10` |

simple `repeat:` として `daily`、`weekly`、`monthly`、`yearly`、`weekdays`
を推奨します。`RRULE:...` は外部互換のため保存できますが、組み込み agenda
の展開対象は simple repeat です。

### 7.5 Message keys

| Key | 意味 | 例 |
|---|---|---|
| `sender` | メッセージ送信元 | `sender:self` |
| `recipient` | メッセージ送信先。複数指定可 | `recipient:alice` |
| `body` | title より長いメッセージ本文 | `body:"Please review the slides"` |
| `notify_at` | 単一の通知時刻 | `notify_at:2026-06-06T09:00` |
| `notify_from`, `notify_to` | 通知期間 | `notify_from:2026-06-06T09:00 notify_to:2026-06-06T17:00` |
| `ack` | 通知確認日時 | `ack:2026-06-06T09:05` |
| `snooze_until` | この日時まで通知を抑止 | `snooze_until:2026-06-06T09:30` |
| `channel` | 配信経路 | `channel:teams` |

### 7.6 Workflow keys

| Key | 意味 | 例 |
|---|---|---|
| `reason` | キャンセル、延期、不確定の理由 | `reason:"Schedule changed"` |
| `moved_to` | 延期先の日付または置き換え item | `moved_to:2026-06-10` |

### 7.7 System keys

| Key | 意味 | 例 |
|---|---|---|
| `created` | 作成日または作成日時 | `created:2026-06-06` |
| `updated` | 最終更新日または最終更新日時 | `updated:2026-06-06T16:30` |

## 8. 日付と時刻

| 形式 | 意味 | 例 |
|---|---|---|
| `YYYY-MM-DD` | 日付 | `due:2026-06-12` |
| `YYYY-MM-DDTHH:MM` | ローカル日時 | `from:2026-06-08T13:00` |
| `YYYY-MM-DDTHH:MM:SS` | 秒付きローカル日時 | `from:2026-06-08T13:00:30` |
| `YYYY-MM-DDTHH:MM:SS.sss` | 小数秒付きローカル日時 | `from:2026-06-08T13:00:30.5` |
| `YYYY-MM-DDTHH:MM+09:00` | timezone offset 付き日時 | `from:2026-06-08T13:00+09:00` |
| `YYYY-MM-DDTHH:MM:SS.sss+09:00` | 秒・小数秒・timezone 付き日時 | `from:2026-06-08T13:00:30.25+09:00` |
| `YYYY-MM-DDTHH:MMZ` | UTC 日時 | `from:2026-06-08T04:00Z` |
| `HH:MM` | 時刻のみ | `at:18:00` |
| `HH:MM:SS` | 秒付き時刻 | `at:18:00:30` |
| `HH:MM:SS.sss` | 小数秒付き時刻 | `at:18:00:30.5` |
| `HH:MM+09:00` | timezone offset 付き時刻 | `at:18:00+09:00` |

範囲ベースのツールでは、`from/to`、`notify_from/notify_to`、`on` を期間として扱えます。`due`、`do`、`at`、`moved_to`、`notify_at` は時点または終日範囲として扱えます。

timezone が明示された値は、比較や表示の前に実行環境の local timezone に正規化される場合があります。小数秒は最大 6 桁まで扱います。

### 8.1 繰り返し semantics

simple recurrence は `repeat:` と、任意の `interval:`、`until:`、`count:` で表します。

```txt
[ ] H Stretch repeat:daily at:18:00
[ ] H Review repeat:weekly interval:2 on:2026-06-01 until:2026-12-31
[ ] H Workday_Checkin repeat:weekdays at:09:00 count:10
```

agenda と time filter は、`from/to`、`at` + `on`、bounded range 内の floating
`at`、`on`、`due` / `do` / `moved_to` / `notify_at` の順で anchor を選び、
simple repeat を展開します。`interval:2` は 2 単位ごとの繰り返し、`count:`
は anchor から数えた最大 occurrence 数、`until:` は inclusive な終了日時です。
`on:` のない floating `at:` は安定した日付 anchor がないため、片側だけの
time filter では一致対象にしません。

## 9. type 別 recommended keys

### 9.1 Task (`T`)

```txt
do due priority assignee owner est project tag note body id parent ref depends_on blocks related
```

例:

```txt
[ ] T Write_Report do:2026-06-10 due:2026-06-12 project:university priority:A assignee:alice
```

### 9.2 Event (`E`)

```txt
from to on loc attendee owner project tag note
```

例:

```txt
[ ] E Seminar from:2026-06-08T13:00 to:2026-06-08T14:30 loc:university attendee:alice
```

### 9.3 Deadline (`D`)

```txt
due priority owner assignee project tag note
```

例:

```txt
[ ] D Scholarship_Form due:2026-06-20T17:00 project:university priority:A owner:alice
```

### 9.4 Reminder (`R`)

```txt
at on owner project context note
```

例:

```txt
[ ] R Take_Medicine at:2026-06-06T21:00 project:health
```

### 9.5 Habit (`H`)

```txt
repeat interval until count at on owner project tag note body ref related
```

例:

```txt
[ ] H English_Study repeat:daily at:18:00 project:english
[ ] H Weekly_Review repeat:weekly interval:2 on:2026-06-01 until:2026-12-31 project:life
```

### 9.6 Note (`N`)

```txt
project context tag note body url id parent ref related
```

例:

```txt
[N] N Research_Memo project:research note:"Use figures before detailed explanation"
```

### 9.7 Journal / Diary (`J`)

`J` は日記、日誌、長めの作業ログを記録する type です。`D` は Deadline として既に使うため、Diary は Journal の `J` を使います。status は `[N]` を推奨します。

推奨 key:

```txt
on at from to mood weather loc person project tag note body url id parent ref related created updated
```

例:

```txt
[N] J "Research day" on:2026-06-23 mood:good tag:lab
| Read papers in the morning.
| Wrote parser tests in the afternoon.
```

### 9.8 Status / Presence status (`S`)

`S` はチャットツール風の現在状態や在席状態に使います。

必須 key:

```txt
from state
```

推奨 key:

```txt
from state to person service loc project note body ref related visibility
```

`to:` がない場合は現在有効な状態として扱えます。`to:` がある場合は過去の状態ログとして扱えます。

例:

```txt
[/] S Working from:2026-06-06T14:00 state:busy person:self
[x] S Sleeping from:2026-06-05T01:00 to:2026-06-05T08:30 state:sleeping person:self
```

### 9.9 Message (`M`)

`M` は人から人へのメッセージ、通知予約、配信依頼を記録するための type です。外部サービスへの送信 API そのものではなく、life.txt 上で構造化して保持し、ツールが表示、絞り込み、後続処理に使える record です。

必須 key:

```txt
sender recipient
```

推奨 key:

```txt
sender recipient notify_at notify_from notify_to ack snooze_until channel service priority project tag note body url id parent ref related created updated
```

| Key | 推奨理由 |
|---|---|
| `sender` | 送信元の人または agent |
| `recipient` | 送信先。複数人には key を繰り返す |
| `notify_at` | 単一の通知または配信時刻 |
| `notify_from`, `notify_to` | 通知可能期間、配信期間 |
| `ack` | 通知確認済み。ツールは再通知しない |
| `snooze_until` | この日時まで通知を抑止 |
| `channel` | `teams`、`discord`、`slack`、`email` などの経路 |
| `service` | 由来または対象サービス |
| `priority`, `project`, `tag`, `note`, `url`, `id`, `parent`, `created`, `updated` | 経路、文脈、追跡性 |

例:

```txt
[ ] M "Review slides" sender:self recipient:alice notify_at:2026-06-06T09:00 channel:teams
[/] M "Daily reminder" sender:lifetxt recipient:self notify_from:2026-06-06T09:00 notify_to:2026-06-06T17:00 channel:desktop
[x] M "Sent review request" sender:self recipient:alice done:2026-06-06T09:05
```

## 10. status 別 recommended keys

### 10.1 Not Completed (`[ ]`)

```txt
do due priority project tag note ref related
```

未完了の作業や未送信の Message に使います。

### 10.2 In Progress (`[/]`)

```txt
do due project context note updated
```

`S` では、`to:` がない現在有効な状態に `[/]` を推奨します。`M` では通知が有効、または配信中であることを表せます。

### 10.3 Completed (`[x]`)

```txt
done project tag note
```

`S` では、`to:` がある終了済みログに `[x]` を推奨します。`M` では送信済み、配信済み、または完了を表せます。

### 10.4 Canceled (`[-]`)

```txt
reason updated note
```

`M` ではメッセージまたは通知のキャンセルを表せます。

### 10.5 Deferred Or Moved (`[>]`)

```txt
moved_to reason updated note
```

`M` では配信延期を表せます。

### 10.6 Pending Or Uncertain (`[?]`)

```txt
note updated
```

`M` では配信状態や相手の応答が不明な状態を表せます。

### 10.7 Note Status (`[N]`)

```txt
project context tag note body url ref related
```

`[N]` は通常 type `N` または `J` と組み合わせます。

## 11. 複数行 body

`|` で始まる行は、直前の item の `body:` detail として扱います。`|` の直後の 1 つの空白は区切りであり本文には含めません。空行を本文に入れる場合は `|` だけの行を使います。

`body:` は `J` 専用ではありません。短い補足は `note:`、長文は `body:` と使い分け、詳細な task、event description、message、note、journal に利用できます。

```txt
[ ] T Write_Report due:2026-06-12 project:university
| Include the method section and references.

[N] J "Research day" on:2026-06-23 mood:good
| First paragraph.
|
| Second paragraph.
```

孤立した `|` 行は構文エラーです。

## 12. Status / Presence state 値

type `S` の `state:` 推奨値:

| State | 意味 |
|---|---|
| `available` | 対応可能 |
| `busy` | 取り込み中 |
| `away` | 離席中 |
| `offline` | オフライン |
| `dnd` | 応答不可 |
| `focus` | 集中中 |
| `sleeping` | 睡眠中 |
| `commuting` | 移動中 |
| `working` | 作業中 |
| `studying` | 勉強中 |
| `meeting` | 会議中 |
| `custom` | カスタム状態 |

`person:` が省略された場合、ツールは `self` と解釈してよいです。

## 13. Note / Journal ルール

note status `[N]` は通常 note type `N` または journal type `J` と組み合わせます。

```txt
[N] N Research_Memo project:research
[N] J "Research day" on:2026-06-23
```

## 13. 簡易文法

```ebnf
life_file     = { blank_line | comment_line | item_line | continuation_line } ;
item_line     = indent, status, space, type, space, string, { space, detail } ;
continuation_line = indent, "|", [ space ], text ;
indent        = { " " } ;
status        = "[ ]" | "[/]" | "[x]" | "[-]" | "[>]" | "[?]" | "[N]" ;
type          = "T" | "E" | "D" | "R" | "H" | "N" | "S" | "M" | "J" ;
detail        = key, ":", string ;
key           = bare_key ;
string        = bare_string | quoted_string ;
space         = " " ;
```

## 14. 完全な例

```txt
[ ] T Write_Report do:2026-06-10 due:2026-06-12 project:university priority:A assignee:alice
[ ] E Seminar from:2026-06-08T13:00 to:2026-06-08T14:30 loc:university project:research attendee:alice
[/] S Working from:2026-06-06T14:00 state:busy person:self
[/] S "Research Focus" from:2026-06-06T16:00 state:focus person:self note:"Replies may be slow"
[x] S Sleeping from:2026-06-05T01:00 to:2026-06-05T08:30 state:sleeping person:self
[ ] M "Review slides" sender:self recipient:alice notify_at:2026-06-06T09:00 channel:teams
[N] N "Use more figures in the next presentation" project:research
```
