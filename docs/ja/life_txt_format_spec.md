# life.txt フォーマット仕様

## 1. 概要

`life.txt` は、タスク、予定、締切、リマインダー、習慣、在席状況、メッセージ、メモ、日記・日誌を記録するプレーンテキスト形式です。

```txt
[status] type title key:value key:value ...
```

空行は無視されます。`#` で始まる行はコメントです。多くの item は 1 行で書けますが、`|` で始まる継続行を使うと複数行の `body:` を直前 item に結合できます。

### 1.1 CLI 互換プロファイル

参照実装の CLI (`python -m lifetxt`) は、相互変換しやすい厳密なプロファイルとしてこの仕様を実装します。

| 項目 | CLI 互換ルール |
|---|---|
| 文字コード | 入力は UTF-8。UTF-8 BOM も受け付けます。出力は UTF-8 です。 |
| 改行 | 読み込み時は `LF`、`CRLF`、`CR` を受け付けます。serializer は `LF` を出力します。 |
| item 行 | `indent [status] type title details...` |
| 区切り | status、type、title、detail の間は 1 つの space が正規形です。複数 space は warning、tab は error です。 |
| コメント | `#` が 1 桁目にある行がコメントです。インデントされたコメントは warning 付きで無視されます。 |
| ファイル内 detail | detail は必ず `key:value` です。`key=value` はファイル構文ではありません。 |
| CLI helper 入力 | `assist -d`、`assist --add-detail`、対話 detail prompt では便宜上 `key=value` も入力できます。出力時は `key:value` になります。 |
| custom key | 未知の key も構文上は有効で保持されます。type に推奨されない key には warning が出る場合があります。 |
| 複数値 | 同じ key を複数回書きます。JSON/JSONL では各 detail は常に配列です。CSV では複数値を JSON 配列セルとして保存します。 |
| 階層 | 先頭 space は JSON の `indent` として保持されます。可能な場合、インデントから `parent:` を推論します。 |
| 複数行 body | `|` で始まる継続行は、改行を含む 1 つの `body:` 値になります。 |

command、filter、変換形式の詳細は [CLI ガイド](./cli.md) を参照してください。

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

### 4.1 user / team / tag / time / id の補足

#### 4.1.1 user / team / group

`user:` は、`owner:`、`assignee:`、`attendee:`、`person:`、`sender:`、`recipient:` のどれにも限定しない一般的な user 参照です。
役割が明確な場合は、より具体的な key を優先してください。

`team:` と `group:` は、team 単位・group 単位の ownership、routing、filter に使います。
CLI / Web の `--team` / `team=` filter は、item の `team:` / `group:` に加えて、config の `teams` membership も利用できます。

#### 4.1.2 tag filter

`tag:` は従来どおり複数回書けます。
CLI / Web では `--tag` / `tag=` はいずれかの tag に一致、`--tag-all` / `tag_all=` はすべての tag に一致、`--exclude-tag` / `exclude_tag=` は指定 tag を含む item を除外します。
config の `tags.aliases` と `tags.groups` は tag filter の展開に使えます。

#### 4.1.3 datetime

日時値は従来の `YYYY-MM-DDTHH:MM` に加えて、秒と timezone offset を含められます。

```txt
from:2026-06-08T13:00
from:2026-06-08T13:00:30
from:2026-06-08T13:00+09:00
from:2026-06-08T04:00Z
at:18:00:30
```

#### 4.1.4 id

`id:` は読み込み対象の複数 life.txt ファイル全体で一意であることを推奨します。
空白や引用符を含まない短い ASCII token を推奨しますが、iCalendar UID など外部 ID では `@` などの記号を含んでも構いません。
config の `ids.key` / `api.id_key` により、`id:` 以外の detail key を ID key として使えます。

引用文字列内では `"` を `\"`、`\` を `\\` としてエスケープします。

### 4.2 line continuation

物理行の末尾が backslash (`\`) の場合、次の物理行と結合してから parser に渡します。
長い item 行を分割するための構文です。

```txt
[ ] T Write_Report \
  due:2026-06-12 project:research
```

これは次の logical line として解釈されます。

```txt
[ ] T Write_Report due:2026-06-12 project:research
```

末尾 backslash の後の空白は無視され、継続先行の先頭 space は取り除かれます。
ファイル末尾の bare backslash は error です。backslash で継続した item 行を
`|` body continuation line へ直接つなげることはできません。body は complete な
item 行の後に通常の `|` 行として書きます。

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

Encrypted detail value は inline tagged string として保存します。tool は file
を parse するために復号する必要はありません。現在の tag は次の通りです。

```txt
enc:XSK:BASE64
enc:GCM:BASE64
```

`enc:XSK:` は `encrypt --algorithm xsk` の dependency-free built-in format、
`enc:GCM:` は optional `cryptography` package を使う `encrypt --algorithm
aesgcm` の AES-GCM format です。`check`, `filter`, converter はこれらを
opaque な detail string として扱います。

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

階層の canonical な機械表現は明示的な `parent:` です。indentation は人が書きやすく読むための派生表現として扱います。`--canonical` を持つ CLI command は、親を推論できる場合に `parent:` を保持または追加し、item 行を unindented にして出力します。

## 6. detail key の考え方

- known key は、ツールが検証、補完、ヘルプで認識する key です。
- recommended key は、type や status ごとに最初に提示する短い推奨 key です。
- custom key も構文上は有効で、保持されます。

## 7. 基本 key group

### 7.1 Common keys

| Key | 意味 | 例 |
|---|---|---|
| `id` | 安定した item ID | `id:task_001` |
| `source` | 外部 tool または generated source | `source:ics` |
| `uid` | 外部 source の元 ID | `uid:event-1@example.com` |
| `project` | プロジェクト、作業領域 | `project:research` |
| `tag` | 自由タグ。複数指定可 | `tag:important` |
| `note` | 短い補足メモ | `note:"Check later"` |
| `body` | 長文本文。継続行でも記述可 | `body:short_text` |
| `url` | 関連 URL | `url:https://example.com` |

`id:` は読み込み対象の life.txt ファイル群の中で一意に保つことを推奨します。
validator は重複IDを warning `W213` として報告します。id-based API や update は
曖昧なIDを拒否する場合があります。

import / sync 由来の record では `source:` と `uid:` を併用します。例として
iCalendar sync は `source:ics uid:event-1@example.com` を書き、通常は同じ UID を
`id:` として使います。Todoist や GitHub のように source 内でだけ一意な ID は
`id:todoist-123` や `id:github-42` のように namespace を付けることを推奨します。

### 7.2 Link keys

| Key | 意味 | 例 |
|---|---|---|
| `parent` | 親 item、階層、message thread の親 | `parent:task_001` |
| `ref` | 他 item への汎用参照 | `ref:task_001` |
| `depends_on` | 先に完了・解決が必要な item | `depends_on:task_001` |
| `blocks` | この item が block している item | `blocks:task_002` |
| `related` | 弱い関連 item | `related:note_001` |

参照値は通常 `id:` を指します。config で `ids.key` / `api.id_key` を変更した場合は、その key を ID として扱います。存在しない参照、自己参照、`parent:` cycle は warning として報告されます。

依存関係の semantics:

- `depends_on:ID` は、現在の item が item `ID` の完了、取消、または open でない状態への移行を前提にしていることを表します。
- `blocks:ID` は、現在の item が item `ID` を block しているという独立した逆方向の主張です。`depends_on:` と必ず mirror させる必要はありません。
- open な依存状態は `[ ]`、`[/]`、`[>]`、`[?]` です。
- `check` は、`[x]` の item がまだ open な `depends_on:` prerequisite を持つ場合に `W224` を出します。
- `agenda` は、open item が open prerequisite に block されている場合、JSON / JSONL に `blocked: true` と `blocked_by` を含めます。text 出力では短い `blocked` 列を表示します。
- `health` は、open prerequisite に block されている open item に `W305` を出します。

複数の life.txt ファイルを 1 回の command invocation で読み込む場合、参照は読み込まれた入力全体に対して解決されます。たとえば `team.life.txt` の `parent:task_001` は、同じ command に `life.txt` も渡されていれば `life.txt` 内の `id:task_001` を参照できます。JSON / JSONL を出力する converter は、ファイル由来の record に `_source_file`、`_source_line`、複数行 record では `_source_end_line` を含めます。これらの `_source_*` field は command output の metadata であり、life.txt の detail key ではありません。`from-json` / `from-jsonl` は life.txt に戻すときに無視します。

### 7.3 People keys

| Key | 意味 | 例 |
|---|---|---|
| `user` | より狭い役割を決めない一般的な user 参照 | `user:alice` |
| `owner` | item に責任を持つ人 | `owner:alice` |
| `assignee` | 作業を担当する人 | `assignee:alice` |
| `attendee` | 予定の参加者。複数指定可 | `attendee:alice` |
| `person` | status / presence の対象者。主に type `S` 用 | `person:self` |
| `sender` | メッセージ送信元。主に type `M` 用 | `sender:self` |
| `recipient` | メッセージ送信先。複数指定可 | `recipient:alice` |
| `team` | item に関連する team | `team:research` |
| `group` | item に関連する user group | `group:lab` |

`person` は在席状態を記録する対象者に使います。type `S` 以外では、`owner`、`assignee`、`attendee` のような具体的な key を優先します。Message では `sender` と `recipient` を使います。`team` / `group` は team 単位の ownership、routing、filter に使います。

### 7.4 Time keys

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
| `ack` | 通知確認日または通知確認日時 | `ack:2026-06-06T09:05` |
| `snooze_until` | この日付・日時まで通知を抑止 | `snooze_until:2026-06-06T09:30` |

### 7.5 Effort keys

| Key | 意味 | 例 |
|---|---|---|
| `est` | 見積もり作業量または見積もり時間 | `est:2h` |
| `elapsed` | 実際の累積経過時間 | `elapsed:1h30m` |

`elapsed:` は `timer` CLI command が使用します。`25m`、`1h`、`1h30m`、bare minutes の `90` のような短い形式を推奨します。
parse 可能だが canonical でない duration は `W222`、`elapsed:1d` や `elapsed:90x` のような認識できない duration は `W226` として報告され、0 分として黙って扱われません。

### 7.6 Recurrence keys

| Key | 意味 | 例 |
|---|---|---|
| `repeat` | 繰り返し規則 | `repeat:daily` |
| `repeat_base` | `complete` が次回 occurrence を計算する起点: `due` または `done` | `repeat_base:done` |
| `interval` | N 単位ごとに繰り返す | `interval:2` |
| `until` | 最後の繰り返し日または日時 | `until:2026-12-31` |
| `count` | 最大 occurrence 数 | `count:10` |

simple `repeat:` として `daily`、`weekly`、`monthly`、`yearly`、`weekdays`
を推奨します。`RRULE:...` は外部互換のため保存でき、組み込み agenda と
time filter は dependency-free な subset として `FREQ=DAILY|WEEKLY|MONTHLY|YEARLY`、
`INTERVAL`、`COUNT`、`UNTIL`、daily/weekly の `BYDAY` を展開します。

`repeat_base` は CLI の `complete` command と MCP の `complete_item` tool
（repeat 付き task instance の次回 occurrence を生成する機能。CLI docs の
13.9 節を参照）にのみ影響し、agenda の仮想展開には影響しません。
`repeat_base:due`（デフォルト。config の `defaults.repeat_base` でも設定可）
は item の現在の `due:`/`do:` から進み、値が無ければエラーになります。
`repeat_base:done` は完了日から進みます。`BYDAY` の RRULE は `complete` の
occurrence 生成にはまだ対応していません。

### 7.7 Message keys

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

### 7.8 Journal keys

| Key | 意味 | 例 |
|---|---|---|
| `on` | 日記の日付 | `on:2026-06-23` |
| `at` | 日記の時刻 | `at:22:30` |
| `from`, `to` | entry が扱う時間範囲 | `from:2026-06-23T09:00 to:2026-06-23T18:00` |
| `mood` | 気分ラベル | `mood:good` |
| `weather` | 天気ラベル | `weather:sunny` |
| `loc` | 場所 | `loc:home` |
| `body` | 長文本文 | `| body line` |

### 7.9 Workflow keys

| Key | 意味 | 例 |
|---|---|---|
| `reason` | キャンセル、延期、不確定の理由 | `reason:"Schedule changed"` |
| `moved_to` | 延期先の日付または置き換え item | `moved_to:2026-06-10` |

### 7.10 System keys

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
[ ] E Training repeat:RRULE:FREQ=WEEKLY;BYDAY=MO,WE;COUNT=6 from:2026-06-01T09:00 to:2026-06-01T10:00
```

agenda と time filter は、`from/to`、`at` + `on`、bounded range 内の floating
`at`、`on`、`due` / `do` / `moved_to` / `notify_at` の順で anchor を選び、
simple repeat を展開します。`interval:2` は 2 単位ごとの繰り返し、`count:`
は anchor から数えた最大 occurrence 数、`until:` は inclusive な終了日時です。
`on:` のない floating `at:` は安定した日付 anchor がないため、片側だけの
time filter では一致対象にしません。`repeat:RRULE:...` では `FREQ`、
`INTERVAL`、`COUNT`、`UNTIL` を読み、`FREQ=DAILY` / `FREQ=WEEKLY` では
`BYDAY` も利用できます。`UNTIL` は life.txt の datetime 構文または
`20260630`、`20260630T090000` のような iCalendar basic 形式を使えます。
requested date/time range は half-open interval `[start, end)` として扱います。
date-only の end boundary、例えば `--to 2026-06-12` は `2026-06-13T00:00`
として解釈し、同日 `23:59:59.5` は含め、翌日 `00:00` ちょうどは除外します。
より複雑な RRULE は text として保持しますが、dependency-free core では展開しません。
`check` は対応外の RRULE feature を検出した場合、recurrence warning `W223`
を出します。

## 9. type 別 recommended keys

ここでの recommended keys は、入力補助や簡易helpで最初に出す短い候補です。
許可されるkeyの完全な一覧ではありません。`body`、`ref`、`depends_on`、
`blocks`、`related`、`created`、`updated` などの known key は、必要な文脈が
ある場合に引き続き利用できます。

### 9.1 Task (`T`)

```txt
do due priority assignee owner project tag id
```

例:

```txt
[ ] T Write_Report do:2026-06-10 due:2026-06-12 project:university priority:A assignee:alice
```

### 9.2 Event (`E`)

```txt
from to on loc attendee project id
```

例:

```txt
[ ] E Seminar from:2026-06-08T13:00 to:2026-06-08T14:30 loc:university attendee:alice
```

### 9.3 Deadline (`D`)

```txt
due priority owner assignee project id
```

例:

```txt
[ ] D Scholarship_Form due:2026-06-20T17:00 project:university priority:A owner:alice
```

### 9.4 Reminder (`R`)

```txt
at on project context note id
```

例:

```txt
[ ] R Take_Medicine at:2026-06-06T21:00 project:health
```

### 9.5 Habit (`H`)

```txt
repeat at on project tag id
```

例:

```txt
[ ] H English_Study repeat:daily at:18:00 project:english
[ ] H Weekly_Review repeat:weekly interval:2 on:2026-06-01 until:2026-12-31 project:life
```

### 9.6 Note (`N`)

```txt
project tag note body url id
```

例:

```txt
[N] N Research_Memo project:research note:"Use figures before detailed explanation"
```

### 9.7 Journal / Diary (`J`)

`J` は日記、日誌、長めの作業ログを記録する type です。`D` は Deadline として既に使うため、Diary は Journal の `J` を使います。status は `[N]` を推奨します。

推奨 key:

```txt
on mood project tag body id
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
from state to person service visibility
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
sender recipient notify_at notify_from notify_to channel priority body id parent
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

## 12. Safe Markdown subset

Markdown は、quoted title、quoted detail value、複数行 `body:` の表示用
markup として利用できます。これは life.txt の基本文法を変更しません。
parser は raw text を保持し、renderer が必要に応じて安全な Markdown subset
として解釈します。

対応する inline syntax:

| Syntax | Meaning |
|---|---|
| `` `code` `` | Inline code |
| `**bold**` | Strong emphasis |
| `*italic*` | Emphasis |
| `[label](https://example.com)` | Safe link。`http`、`https`、`mailto` のみ link として描画 |

複数行 `body:` で対応する block syntax:

| Syntax | Meaning |
|---|---|
| `# Heading`, `## Heading`, `### Heading` | Heading |
| Blank-line separated text | Paragraph |
| `- item` or `* item` | Unordered list |
| `1. item` | Ordered list |
| Triple backtick fences | Code block |

Raw HTML は subset に含めません。renderer は必ず escape してください。
未対応 Markdown syntax は text として保持します。JSON、JSONL、CSV、life.txt
出力は raw Markdown text を保持し、HTML rendering は Web API/UI と
`markdown` CLI command で利用できます。

```txt
[N] J "Research **day**" on:2026-06-26
| # Summary
|
| Implemented **safe Markdown** rendering.
|
| - Parser keeps raw Markdown text
| - Web UI shows sanitized previews
|
| See [project docs](https://example.com/lifetxt).
```

## 13. Status / Presence state 値

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

## 14. Note / Journal ルール

note status `[N]` は通常 note type `N` または journal type `J` と組み合わせます。

```txt
[N] N Research_Memo project:research
[N] J "Research day" on:2026-06-23
```

## 15. Reference Implementation Notes

現在の reference implementation は、この grammar を CLI、JSON/JSONL/CSV
converter、FastAPI API、browser GUI で共通利用します。多くの読み取り系 command
は複数 file、directory、glob pattern、stdin を受け付けます。machine-readable
record を出力する command は、file 由来の input に `_source_file`、
`_source_line`、`_source_end_line` を付与する場合があります。これらの
`_source_*` field は command output metadata であり、life.txt detail key では
ありません。converter は life.txt に戻すとき、これらの metadata を無視します。

Web UI は複数の life.txt file を同時に読み込めます。`.generated/*.life.txt`
のような generated file は慣例的に read-only として扱い、
`serve --write-file FILE` で create、update、message thread 操作用の書き込み先を
指定します。`serve --read-only` は line validation 以外の write endpoint を
無効化します。URL parameter と config-defined view preset は UI state であり、
file syntax ではありません。

## 16. 形式文法

```ebnf
life_file         = { blank_line | comment_line | item_line | continuation_line } ;
blank_line        = { " " | "\t" } ;
comment_line      = "#", text ;
item_line         = indent, status, space, type, space, string, { space, detail } ;
continuation_line = indent, "|", [ space ], body_text ;

indent            = { " " } ;
space             = " " ;
status            = "[ ]" | "[/]" | "[x]" | "[-]" | "[>]" | "[?]" | "[N]" ;
type              = "T" | "E" | "D" | "R" | "H" | "N" | "S" | "M" | "J" ;
detail            = key, ":", string ;

key               = bare_key ;
bare_key          = key_char, { key_char } ;
key_char          = ? space、colon、double quote 以外の文字 ? ;

string            = bare_string | quoted_string ;
bare_string       = bare_char, { bare_char } ;
bare_char         = ? space または double quote 以外の文字 ? ;
quoted_string     = '"', { quoted_char | escape }, '"' ;
quoted_char       = ? double quote または backslash 以外の文字 ? ;
escape            = "\\\"" | "\\\\" ;

body_text         = text ;
text              = ? 行末までの任意の文字 ? ;
```

補足:

- CLI validator は `[a-z][a-z0-9_]*` に合う lowercase snake_case の key を推奨しますが、parser は構文上有効な custom key を保持します。
- quoted string の閉じ `"` の直後は space または行末である必要があります。
- bare string には space と double quote を含められません。serializer は tab、backslash、空文字列など、正規の bare string として安全でない値を quoted string にします。
- continuation line は item の直後に必要です。JSON/JSONL/CSV から life.txt に戻す場合、複数行 `body:` は `|` 継続行として出力されます。
- `key=value` は CLI helper の入力だけで使える便宜記法です。ファイル構文には含めません。

## 17. 完全な例

```txt
[ ] T Write_Report do:2026-06-10 due:2026-06-12 project:university priority:A assignee:alice
[ ] E Seminar from:2026-06-08T13:00 to:2026-06-08T14:30 loc:university project:research attendee:alice
[/] S Working from:2026-06-06T14:00 state:busy person:self
[/] S "Research Focus" from:2026-06-06T16:00 state:focus person:self note:"Replies may be slow"
[x] S Sleeping from:2026-06-05T01:00 to:2026-06-05T08:30 state:sleeping person:self
[ ] M "Review slides" sender:self recipient:alice notify_at:2026-06-06T09:00 channel:teams
[N] N "Use more figures in the next presentation" project:research
```
