# life.txt 形式仕様

## 1. 概要

`life.txt` は、タスク、予定、締切、リマインダー、習慣、在席状態、メモを
1 item 1 行で記録するプレーンテキスト形式です。

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
| `[N]` | ノート |

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

## 4. title と value の規則

title と detail value は、空白やダブルクォートを含まない場合は裸の文字列として書けます。

```txt
[ ] T Write_Report due:2026-06-12
```

空白を含む場合はダブルクォートで囲みます。

```txt
[ ] E "Research Meeting" from:2026-06-08T13:00 to:2026-06-08T14:30
[N] N "Use more figures in the next presentation" project:research
```

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

custom key は許可されます。パーサは未知の key を可能な限り保持するべきです。

## 6. detail key の考え方

この形式では、known key と recommended key を分けて考えます。

- known key は、ツールが検証、補完、ヘルプで認識する key です。
- recommended key は、type や status ごとに最初に提示すべき短い推奨 key です。
- custom key も構文上は有効で、保持されるべきです。

この分離により、形式の拡張性を保ちながら対話ヘルプを短くできます。

## 7. 基本 key group

以下は共通語彙の説明です。すべての item に必須という意味ではありません。

### 7.1 Common keys

| Key | 意味 | 例 |
|---|---|---|
| `id` | 安定した item ID | `id:task_001` |
| `parent` | 親 item ID | `parent:task_001` |
| `project` | プロジェクトまたは作業領域 | `project:research` |
| `tag` | 自由タグ。複数回指定可能 | `tag:important` |
| `note` | 短い補足メモ | `note:"Check later"` |
| `url` | 関連 URL | `url:https://example.com` |

### 7.2 Time keys

| Key | 意味 | 例 |
|---|---|---|
| `from` | 期間の開始日時 | `from:2026-06-08T13:00` |
| `to` | 期間の終了日時 | `to:2026-06-08T14:30` |
| `on` | 終日の日付 | `on:2026-06-08` |
| `at` | リマインドまたは実行時刻 | `at:18:00` |
| `due` | 締切日または締切日時 | `due:2026-06-12` |
| `do` | 実行予定日または実行予定日時 | `do:2026-06-10` |
| `done` | 完了日または完了日時 | `done:2026-06-05` |

### 7.3 Workflow keys

| Key | 意味 | 例 |
|---|---|---|
| `reason` | キャンセル、延期、不確定の理由 | `reason:"Schedule changed"` |
| `moved_to` | 延期先の日付または置き換え item | `moved_to:2026-06-10` |

### 7.4 System keys

| Key | 意味 | 例 |
|---|---|---|
| `created` | 作成日または作成日時 | `created:2026-06-06` |
| `updated` | 最終更新日または最終更新日時 | `updated:2026-06-06T16:30` |

## 8. 日付と時刻

| 形式 | 意味 | 例 |
|---|---|---|
| `YYYY-MM-DD` | 日付 | `due:2026-06-12` |
| `YYYY-MM-DDTHH:MM` | ローカル日時 | `from:2026-06-08T13:00` |
| `HH:MM` | 時刻のみ | `at:18:00` |

範囲ベースのツールでは、`from/to` と `on` を期間として扱えます。
`due`、`do`、`at`、`moved_to` は時点または終日範囲として扱えます。

## 9. type 別 recommended keys

### 9.1 Task (`T`)

`T` は完了できる作業に使います。

推奨 key:

```txt
do due priority est project tag note id parent
```

| Key | 推奨理由 |
|---|---|
| `do` | いつ作業するか |
| `due` | いつまでに終えるか |
| `priority` | 相対的な重要度 |
| `est` | 見積作業量 |
| `project`, `tag`, `note`, `id`, `parent` | 整理と文脈付け |

例:

```txt
[ ] T Write_Report do:2026-06-10 due:2026-06-12 project:university priority:A
```

### 9.2 Event (`E`)

`E` はカレンダー予定に使います。

推奨 key:

```txt
from to on loc project tag note
```

| Key | 推奨理由 |
|---|---|
| `from`, `to` | 時刻付き予定の期間 |
| `on` | 終日予定の日付 |
| `loc` | 場所 |
| `project`, `tag`, `note` | 整理と文脈付け |

例:

```txt
[ ] E Seminar from:2026-06-08T13:00 to:2026-06-08T14:30 loc:university
```

### 9.3 Deadline (`D`)

`D` は予定そのものではない重要な締切に使います。

推奨 key:

```txt
due priority project tag note
```

| Key | 推奨理由 |
|---|---|
| `due` | 必須の締切 |
| `priority` | 相対的な重要度 |
| `project`, `tag`, `note` | 整理と文脈付け |

例:

```txt
[ ] D Scholarship_Form due:2026-06-20T17:00 project:university priority:A
```

### 9.4 Reminder (`R`)

`R` は特定の日付、時刻、日時でのリマインダーに使います。

推奨 key:

```txt
at on project context note
```

| Key | 推奨理由 |
|---|---|
| `at` | リマインド時刻または日時 |
| `on` | `at:` が時刻のみの場合の日付 |
| `project`, `context`, `note` | 整理と文脈付け |

例:

```txt
[ ] R Take_Medicine at:2026-06-06T21:00 project:health
```

### 9.5 Habit (`H`)

`H` は繰り返し行う行動に使います。

推奨 key:

```txt
repeat at on project tag note
```

| Key | 推奨理由 |
|---|---|
| `repeat` | 繰り返し規則 |
| `at`, `on` | 時刻または日付の基準 |
| `project`, `tag`, `note` | 整理と文脈付け |

例:

```txt
[ ] H English_Study repeat:daily at:18:00 project:english
```

### 9.6 Note (`N`)

`N` はメモや覚え書きに使います。

推奨 key:

```txt
project context tag note url id parent
```

| Key | 推奨理由 |
|---|---|
| `project`, `context`, `tag` | 整理と検索 |
| `note` | title が短い場合の補足本文 |
| `url` | 関連資料 |
| `id`, `parent` | 他 item との関連付け |

例:

```txt
[N] N Research_Memo project:research note:"Use figures before detailed explanation"
```

### 9.7 Status / Presence status (`S`)

`S` はチャットツール風の現在状態や在席状態に使います。

必須 key:

```txt
from state
```

推奨 key:

```txt
from state to person service loc project note visibility
```

| Key | 推奨理由 |
|---|---|
| `from` | 状態の開始日時 |
| `state` | 在席状態 |
| `to` | 終了済みログの終了日時 |
| `person` | 状態の対象者 |
| `service` | 由来または対象サービス |
| `loc`, `project`, `note`, `visibility` | 文脈と公開範囲 |

例:

```txt
[/] S Working from:2026-06-06T14:00 state:busy person:self
```

## 10. status 別 recommended keys

以下は workflow status 値ごとの推奨です。type 別推奨 key を補助するものです。

### 10.1 Not Completed (`[ ]`)

推奨 key:

```txt
do due priority project tag note
```

未完了の作業を計画するために使います。

### 10.2 In Progress (`[/]`)

推奨 key:

```txt
do due project context note updated
```

現在作業中の内容と最終更新を示すために使います。

`S` では、`to:` がない現在有効な状態に `[/]` を推奨します。

### 10.3 Completed (`[x]`)

推奨 key:

```txt
done project tag note
```

`done:` で完了時刻を記録します。

`S` では、`to:` がある終了済みログに `[x]` を推奨します。

### 10.4 Canceled (`[-]`)

推奨 key:

```txt
reason updated note
```

`reason:` でキャンセル理由を記録します。

### 10.5 Deferred Or Moved (`[>]`)

推奨 key:

```txt
moved_to reason updated note
```

`moved_to:` で新しい日付や置き換え item を記録します。

### 10.6 Pending Or Uncertain (`[?]`)

推奨 key:

```txt
note updated
```

不確定な点や確認待ちの内容を `note:` に書きます。

### 10.7 Note Status (`[N]`)

推奨 key:

```txt
project context tag note url
```

`[N]` は通常 type `N` と組み合わせます。

## 11. Status / Presence state 値

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

ツールは `person:` ごとに `from:` が最も新しい `S` item を選び、最新の
在席状態として集約できます。

`to:` がない場合、範囲ベースのツールは `from:` 以降継続中として扱えます。
`to:` がある場合、`from/to` を状態の期間として扱えます。

## 12. Note ルール

note status `[N]` は通常 note type `N` と組み合わせます。

```txt
[N] N Research_Memo project:research
```

## 13. 簡易文法

```ebnf
life_file     = { blank_line | comment_line | item_line } ;
item_line     = status, space, type, space, string, { space, detail } ;
status        = "[ ]" | "[/]" | "[x]" | "[-]" | "[>]" | "[?]" | "[N]" ;
type          = "T" | "E" | "D" | "R" | "H" | "N" | "S" ;
detail        = key, ":", string ;
key           = bare_key ;
string        = bare_string | quoted_string ;
space         = " " ;
```

## 14. 完全な例

```txt
[ ] T Write_Report do:2026-06-10 due:2026-06-12 project:university priority:A
[ ] E Seminar from:2026-06-08T13:00 to:2026-06-08T14:30 loc:university project:research
[/] S Working from:2026-06-06T14:00 state:busy person:self
[/] S "Research Focus" from:2026-06-06T16:00 state:focus person:self note:"Replies may be slow"
[x] S Sleeping from:2026-06-05T01:00 to:2026-06-05T08:30 state:sleeping person:self
[N] N "Use more figures in the next presentation" project:research
```
