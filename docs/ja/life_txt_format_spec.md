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

パーサは未知の custom key を可能な限り保持するべきです。

## 6. 推奨 detail key

| Key | 意味 | 例 |
|---|---|---|
| `id` | item ID | `id:task_001` |
| `parent` | 親 item ID | `parent:task_001` |
| `created` | 作成日または作成日時 | `created:2026-06-06` |
| `updated` | 更新日または更新日時 | `updated:2026-06-06T16:30` |
| `done` | 完了日または完了日時 | `done:2026-06-05` |
| `due` | 締切日または締切日時 | `due:2026-06-12` |
| `do` | 実行予定日または実行予定日時 | `do:2026-06-10` |
| `from` | 開始日時 | `from:2026-06-08T13:00` |
| `to` | 終了日時 | `to:2026-06-08T14:30` |
| `on` | 終日の日付 | `on:2026-06-08` |
| `at` | リマインドまたは実行時刻 | `at:18:00` |
| `repeat` | 繰り返し規則 | `repeat:daily` |
| `state` | 在席状態、現在状態 | `state:busy` |
| `person` | 状態の対象者 | `person:self` |
| `service` | 由来または対象サービス | `service:teams` |
| `project` | プロジェクト名 | `project:research` |
| `context` | コンテキスト、状況 | `context:home` |
| `loc` | 場所 | `loc:"Meeting Room A"` |
| `priority` | 優先度 | `priority:A` |
| `est` | 見積時間 | `est:90m` |
| `tag` | タグ | `tag:important` |
| `note` | 補足メモ | `note:"Check later"` |
| `url` | 関連 URL | `url:https://example.com` |
| `reason` | 理由 | `reason:"Schedule changed"` |
| `moved_to` | 延期先の日付または item | `moved_to:2026-06-10` |
| `visibility` | 公開範囲 | `visibility:team` |

## 7. 日付と時刻

| 形式 | 意味 | 例 |
|---|---|---|
| `YYYY-MM-DD` | 日付 | `due:2026-06-12` |
| `YYYY-MM-DDTHH:MM` | ローカル日時 | `from:2026-06-08T13:00` |
| `HH:MM` | 時刻のみ | `at:18:00` |

範囲ベースのツールでは、`from/to` と `on` を期間として扱えます。
`due`、`do`、`at`、`moved_to` は時点または終日範囲として扱えます。

## 8. type 別推奨 key

| Type | 推奨 key |
|---|---|
| `T` | `do due project context priority est tag note url id parent created updated done` |
| `E` | `from to on loc project tag note url id created updated` |
| `D` | `due project priority tag note url id created updated done` |
| `R` | `at on project context priority tag note url id created updated done` |
| `H` | `repeat at on project context priority tag note id created updated done` |
| `N` | `project context tag note url id parent created updated` |
| `S` | `from state to person service loc project note visibility` |

## 9. Status / Presence status (`S`)

### 9.1 目的

`S` は Teams、Discord、Slack などのチャットツールにある在席状態に近い、
人または対象の現在状態を記録するために使います。

### 9.2 必須 key

`S` では以下が必須です。

```txt
from state
```

`from:` は状態の開始日時、`state:` は状態値です。

```txt
[/] S Working from:2026-06-06T14:00 state:busy
```

### 9.3 任意 key

推奨される任意 key は以下です。

```txt
to person service loc project note visibility
```

`person:` が省略された場合、ツールは `self` と解釈してよいです。

### 9.4 有効状態とログ

`to:` がない場合、その status は現在有効な状態として扱えます。

```txt
[/] S Working from:2026-06-06T14:00 state:busy person:self
```

`to:` がある場合、過去の状態ログとして扱えます。

```txt
[x] S Working from:2026-06-06T14:00 to:2026-06-06T16:00 state:busy person:self
```

現在有効な status item には `[/]`、終了済みログには `[x]` を推奨します。
これは推奨ルールであり、パーサは通常の status 構文規則を使います。

### 9.5 推奨 state 値

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

### 9.6 集約ツールでの扱い

ツールは `person:` ごとに `from:` が最も新しい `S` item を選び、最新の
在席状態として集約できます。

`to:` がない場合、範囲ベースのツールは `from:` 以降継続中として扱えます。
`to:` がある場合、`from/to` を状態の期間として扱えます。

### 9.7 例

```txt
[/] S Working from:2026-06-06T14:00 state:busy person:self
[/] S Away from:2026-06-06T15:30 state:away person:self
[/] S "Research Focus" from:2026-06-06T16:00 state:focus person:self note:"Replies may be slow"
[x] S Sleeping from:2026-06-05T01:00 to:2026-06-05T08:30 state:sleeping person:self
```

## 10. Note ルール

note status `[N]` は通常 note type `N` と組み合わせます。

```txt
[N] N Research_Memo project:research
```

## 11. 簡易文法

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

## 12. 完全な例

```txt
[ ] T Write_Report do:2026-06-10 due:2026-06-12 project:university priority:A
[ ] E Seminar from:2026-06-08T13:00 to:2026-06-08T14:30 loc:university project:research
[/] S Working from:2026-06-06T14:00 state:busy person:self
[/] S "Research Focus" from:2026-06-06T16:00 state:focus person:self note:"Replies may be slow"
[x] S Sleeping from:2026-06-05T01:00 to:2026-06-05T08:30 state:sleeping person:self
[N] N "Use more figures in the next presentation" project:research
```
