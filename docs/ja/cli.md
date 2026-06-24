# life.txt CLI ガイド

この文書は、次のコマンドで提供される CLI の詳細な使い方を説明します。

```sh
python -m lifetxt
```

CLI は外部依存なしで動作し、UTF-8 の `life.txt`、JSON、JSONL、CSV を扱います。
多くの読み込み系コマンドは、1 つ以上の path を受け取れます。path に `-` を指定するか
path を省略すると標準入力から読み込みます。

## 1. コマンド一覧

```sh
python -m lifetxt check [path ...]
python -m lifetxt ids [path ...]
python -m lifetxt links [path ...]
python -m lifetxt to-json [path ...]
python -m lifetxt to-jsonl [path ...]
python -m lifetxt import-ics [path ...]
python -m lifetxt sync-ics --url-env ENVVAR
python -m lifetxt filter [path ...]
python -m lifetxt from-json [path ...]
python -m lifetxt from-jsonl [path ...]
python -m lifetxt status [path ...]
python -m lifetxt agenda [path ...]
python -m lifetxt assist [options]
python -m lifetxt serve [path ...]
```

| Command | 目的 |
|---|---|
| `check` | life.txt の構文と意味的な警告を検査 |
| `to-json` | life.txt を JSON 配列へ変換 |
| `to-jsonl` | life.txt を JSONL へ変換 |
| `to-csv` | life.txt を CSV へ変換 |
| `import-ics` | iCalendar `.ics` の予定を life.txt event item に変換 |
| `sync-ics` | iCalendar URL を取得して life.txt event item を再生成 |
| `filter` | item を絞り込み、life.txt / JSON / JSONL で出力 |
| `from-json` | JSON を life.txt へ変換 |
| `from-jsonl` | JSONL を life.txt へ変換 |
| `from-csv` | CSV を life.txt へ変換 |
| `status` | `person:` ごとの最新 `S` status / presence を表示 |
| `agenda` | 日時範囲に関連する item を表示 |
| `assist` | 対話またはフラグで item を作成・更新 |
| `serve` | 任意機能の FastAPI REST API とブラウザGUIを起動 |

## 2. 共通仕様

### 2.1 入力 path

ファイルを読むコマンドでは、`path ...` は省略可能で、複数指定できます。
複数入力は指定順に読み込まれます。
`*.life.txt` や `projects/**/*.life.txt` のような glob も指定できます。
ディレクトリを指定した場合は、その直下の life.txt 風 `.txt` ファイルを読み込みます。

```sh
python -m lifetxt check life.txt
python -m lifetxt check work.life.txt home.life.txt
python -m lifetxt check "projects/**/*.life.txt"
python -m lifetxt check examples
python -m lifetxt check -
type life.txt | python -m lifetxt check
```

path を省略するか `-` を指定した場合、標準入力から読み込みます。
複数の入力 path を指定した場合、診断には line / column の前に source path が付きます。

### 2.2 出力 path

`-o` / `--output` を持つコマンドでは、指定したファイルに出力します。
指定しない場合は標準出力へ出力します。

`assist` の作成モードでは、`--output FILE` は生成した 1 行を `FILE` に追記します。
ファイル全体を上書きしません。`assist --update` では、`--output FILE` は更新後の
ファイル全体を `FILE` に書き込みます。

### 2.3 出力形式

| Format | 意味 |
|---|---|
| `text` | 人間向けの表または診断 |
| `life` | life.txt 行 |
| `json` | JSON 配列 |
| `jsonl` | 1 行 1 JSON object |

### 2.4 入れ子 item

インデントされた item 行は、階層化 record として parse されます。子 item に
`parent:` がない場合、nearest less-indented ancestor の ID key、通常は `id:`、
から `parent:` を推論します。

```txt
[ ] T Research_Project id:proj_research
  [ ] T Literature_Review id:task_lit
    [N] N Reading_Memo
```

JSON / JSONL では、インデントされた item に `indent` field が含まれます。
life output は既定で元の行を保持します。`--canonical` を使うと、推論された
`parent:` が detail として展開される場合があります。

### 2.5 終了コード

| Code | 意味 |
|---|---|
| `0` | 成功 |
| `1` | 検証エラーまたはコマンドエラー |
| `2` | サブコマンド不足などの CLI usage error |

## 3. `check`

life.txt の構文と意味的なルールを検査します。

```sh
python -m lifetxt check [path ...] [--format text|json] [--warnings-as-errors]
```

| Option | 意味 |
|---|---|
| `path ...` | 入力ファイル。`-` なら標準入力 |
| `--format text` | 人間向けの診断を表示 |
| `--format json` | 診断を JSON で表示 |
| `--warnings-as-errors` | warning がある場合も非ゼロ終了 |

例:

```sh
python -m lifetxt check life.txt
python -m lifetxt check life.txt --warnings-as-errors
python -m lifetxt check life.txt --format json
```

## 4. JSON 変換

### 4.1 `to-json`

life.txt を JSON 配列へ変換します。

```sh
python -m lifetxt to-json [path ...] [-o output.json] [--pretty] [filter options]
```

| Option | 意味 |
|---|---|
| `path ...` | 入力 life.txt。`-` なら標準入力 |
| `-o`, `--output` | 出力ファイル。省略時は標準出力 |
| `--pretty` | JSON を整形して出力 |
| `filter options` | `filter` と同じ item filter |

### 4.2 `to-jsonl`

life.txt を JSONL へ変換します。

```sh
python -m lifetxt to-jsonl [path ...] [-o output.jsonl] [filter options]
```

### 4.3 `from-json`

JSON item、JSON item 配列、または `{ "items": [...] }` を life.txt に変換します。

```sh
python -m lifetxt from-json [path ...] [-o life.txt]
```

### 4.4 `from-jsonl`

JSONL を life.txt に変換します。

```sh
python -m lifetxt from-jsonl [path ...] [-o life.txt]
```

### 4.5 `to-csv`

life.txt を CSV に変換します。CSV は `status`、`type`、`title` と、選択された item に含まれる detail key の列を持ちます。同じ detail key の複数値はセル内 JSON 配列として保存します。複数行の `body:` は quoted CSV cell として保存します。

```sh
python -m lifetxt to-csv [path ...] [-o output.csv] [filter options]
python -m lifetxt to-csv life.txt --type journal --project research -o journal.csv
```

### 4.6 `from-csv`

CSV を life.txt に戻します。CSV には `status`、`type`、`title` 列が必要です。それ以外の非空列は detail key として扱います。セルが JSON 配列の場合は、同じ key の複数値として読み込みます。

```sh
python -m lifetxt from-csv [path ...] [-o life.txt]
```

### 4.7 export filter option

`to-json`、`to-jsonl`、`to-csv` は出力前に item を絞り込めます。

`to-json` と `to-jsonl` は、出力前に item を絞り込めます。

| Option | 意味 |
|---|---|
| `--open` | 未完了 workflow item のみ。対象は `[ ]`、`[/]`、`[>]`、`[?]` |
| `--status VALUE` | status または alias で絞り込み。複数回指定または comma-separated |
| `--type VALUE` | type または alias で絞り込み。複数回指定または comma-separated |
| `--project VALUE` | `project:` で絞り込み。複数回指定または comma-separated |
| `--tag VALUE` | `tag:` で絞り込み。複数回指定または comma-separated |
| `--tag-all VALUE` | 指定した `tag:` をすべて持つ item のみ |
| `--exclude-tag VALUE` | 指定した `tag:` を持つ item を除外 |
| `--user VALUE` | `user/person/owner/assignee/attendee/sender/recipient` を横断して絞り込み |
| `--team VALUE` | `team:` / `group:` または config の team membership で絞り込み |
| `--person VALUE` | `person:` で絞り込み。`S` で `person:` がない場合は `self` |
| `--owner VALUE` | `owner:` で絞り込み。複数回指定または comma-separated |
| `--assignee VALUE` | `assignee:` で絞り込み。複数回指定または comma-separated |
| `--attendee VALUE` | `attendee:` で絞り込み。複数回指定または comma-separated |
| `--detail FILTER` | detail key または `key=value` で絞り込み。複数指定は AND |
| `--text TEXT` | title、元行、detail 値に対する大文字小文字を区別しない部分一致 |
| `--after VALUE` | この時刻以降に関連する item のみ |
| `--before VALUE` | この時刻以前に関連する item のみ |

`--after` と `--before` は `now`、`YYYY-MM-DD`、`YYYY-MM-DDTHH:MM`、
`YYYY-MM-DDTHH:MM:SS`、`YYYY-MM-DDTHH:MM:SS.5`、
`YYYY-MM-DDTHH:MM+09:00`、`YYYY-MM-DDTHH:MM:SS.25+09:00` などを受け付けます。
時刻判定は `agenda` と同じルールを使います。
`on:` のない `at:HH:MM` は日付アンカーを持たないため、片側条件の `--after` /
`--before` では一致対象にしません。

例:

```sh
python -m lifetxt to-json life.txt --open --type task --pretty
python -m lifetxt to-jsonl work.life.txt home.life.txt --project research
python -m lifetxt to-json life.txt --assignee alice --pretty
python -m lifetxt to-json "projects/**/*.life.txt" --team research --tag-all urgent,review
python -m lifetxt to-json life.txt --after now --type event -o future_events.json
```

## 5. iCalendar import / sync

### 5.1 `import-ics`

Google Calendar の export などで得られる iCalendar `.ics` ファイルを、
life.txt の event item に変換します。

```sh
python -m lifetxt import-ics [path ...] [-o life.txt] [--append] [--project PROJECT] [--tag TAG]
```

| Option | 意味 |
|---|---|
| `path ...` | 入力 `.ics` ファイル。`-` なら標準入力 |
| `-o`, `--output` | 出力ファイル。省略時は標準出力 |
| `--append` | `--output` を上書きせず追記 |
| `--project PROJECT` | すべての取り込み予定に `project:PROJECT` を追加 |
| `--tag TAG` | すべての取り込み予定に `tag:TAG` を追加。複数回指定可能 |

変換対応:

| iCalendar field | life.txt output |
|---|---|
| `VEVENT` | `E` item |
| `SUMMARY` | title |
| `UID` | `id:` |
| `DTSTART` / `DTEND` | 時刻付き予定では `from:` / `to:` |
| `DTSTART;VALUE=DATE` | 終日予定では `on:` |
| `LOCATION` | `loc:` |
| `DESCRIPTION` | `note:` |
| `URL` | `url:` |
| `ORGANIZER` | `owner:` |
| `ATTENDEE` | 複数の `attendee:` |
| `CATEGORIES` | 複数の `tag:` |
| `RRULE` | `repeat:RRULE:...` |
| `STATUS:CANCELLED` | `[-]` と `reason:canceled` |
| `STATUS:TENTATIVE` | `[?]` |

注意:

- `VEVENT` component のみを取り込みます。
- Google Calendar の終日 `DTEND` は排他的です。複数日の終日予定は複数の
  `on:` に変換します。
- `TZID` 付きのローカル時刻は書かれている壁時計時刻をそのまま使います。
  UTC の `Z` 付き日時は、実行環境のローカルタイムゾーンへ変換して
  `YYYY-MM-DDTHH:MM` で出力します。
- `RRULE` は保持しますが、個別の予定へ展開しません。

例:

```sh
python -m lifetxt import-ics google_calendar.ics
python -m lifetxt import-ics google_calendar.ics -o imported_events.life.txt
python -m lifetxt import-ics google_calendar.ics -o life.txt --append --tag google
python -m lifetxt import-ics work.ics personal.ics --project calendar
```

出力例:

```txt
[ ] E "Research Meeting" id:event-1@example.com from:2026-06-08T13:00 to:2026-06-08T14:30 loc:"Meeting Room A" owner:"Prof. Smith" attendee:Alice tag:google
```

### 5.2 `sync-ics`

1 つ以上の iCalendar URL を取得し、生成用 life.txt ファイルを再生成します。
定期同期ではこの方式を推奨します。出力ファイルを上書きするため、実行するたびに
同じ予定が重複追記されません。

```sh
python -m lifetxt sync-ics --url-env LIFETXT_GOOGLE_CAL_ICS -o .generated/google_calendar.life.txt --cache-dir .cache/lifetxt --tag google
```

| Option | 意味 |
|---|---|
| `--url URL` | 取得する iCalendar URL。複数回指定可能 |
| `--url-env ENVVAR` | iCalendar URL を入れた環境変数。複数回指定可能 |
| `-o`, `--output` | 生成する life.txt 出力。省略時は標準出力 |
| `--cache-dir DIR` | 取得した生の `.ics` snapshot を保存する directory |
| `--dry-run` | 取得して生成結果を表示するが、出力ファイルと cache は書かない |
| `--project PROJECT` | すべての同期予定に `project:PROJECT` を追加 |
| `--tag TAG` | すべての同期予定に `tag:TAG` を追加。複数回指定可能 |
| `--timeout SECONDS` | 取得 timeout。既定値は 30 |
| `--user-agent VALUE` | HTTP User-Agent header |

秘密 iCalendar URL は、shell history、script、document に残さないために
`--url-env` で渡すことを推奨します。

PowerShell 例:

```powershell
$env:LIFETXT_GOOGLE_CAL_ICS = "https://calendar.google.com/calendar/ical/..."
New-Item -ItemType Directory -Force .generated, .cache/lifetxt
python -m lifetxt sync-ics --url-env LIFETXT_GOOGLE_CAL_ICS -o .generated/google_calendar.life.txt --cache-dir .cache/lifetxt --tag google
python -m lifetxt check life.txt .generated/google_calendar.life.txt
python -m lifetxt agenda life.txt .generated/google_calendar.life.txt --around now --window 1d
```

定期同期する場合は、同じ内容を `.ps1` にして Windows Task Scheduler で実行します。
手書きの item はメインの `life.txt` に残し、ICS 由来の item は
`.generated/*.life.txt` に分離してください。`agenda`、`filter`、`to-json`、
`check` などは両方のファイルを同時に渡せます。

## 6. `filter`

解析済みの life.txt item を絞り込み、結果を life.txt、JSON、JSONL で出力します。
条件に合う部分集合を別の `life.txt` として保存したい場合に使います。

```sh
python -m lifetxt filter [path ...] [filter options] [--format life|json|jsonl] [-o output]
```

| Option | 意味 |
|---|---|
| `path ...` | 入力 life.txt。`-` なら標準入力 |
| `--format life` | 一致した life.txt 行を出力。既定値 |
| `--format json` | JSON 配列で出力 |
| `--format jsonl` | JSONL で出力 |
| `-o`, `--output` | 出力ファイル。省略時は標準出力 |
| `--pretty` | JSON を整形して出力 |
| `--canonical` | 元行ではなく正規化した life.txt 行を再生成 |

filter option は 4.5 の export filter option と同じです。
`--format life` では、一致した item の元行を既定で保持します。
引用や空白を正規化したい場合は `--canonical` を使います。

例:

```sh
python -m lifetxt filter life.txt --open --type task -o open_tasks.life.txt
python -m lifetxt filter life.txt --open --type task --canonical -o canonical_tasks.life.txt
python -m lifetxt filter life.txt --assignee alice -o alice_items.life.txt
python -m lifetxt filter life.txt --after now --type event -o future_schedule.life.txt
python -m lifetxt filter life.txt --type status --person self -o my_status.life.txt
python -m lifetxt filter work.life.txt home.life.txt --project research --format json --pretty
```

## 7. `status`

`person:` ごとの最新 `S` status / presence record を表示します。

```sh
python -m lifetxt status [path ...] [--format text|json|jsonl] [--person PERSON] [--active] [--pretty]
```

選択ルール:

- type `S` の item だけを対象にします。
- `person:` ごとに group 化します。
- `person:` がない場合は `self` として扱います。
- `from:` が最も新しい item を最新として選びます。
- `--active` を指定すると、`to:` を持つ終了済み log は除外します。

| Option | 意味 |
|---|---|
| `path ...` | 入力 life.txt。`-` なら標準入力 |
| `--format text` | 表で表示 |
| `--format json` | JSON 配列で表示 |
| `--format jsonl` | JSONL で表示 |
| `--person PERSON` | 特定 person のみ表示 |
| `--active` | `to:` のない現在有効な status item のみ対象 |
| `--pretty` | JSON を整形して出力 |

例:

```sh
python -m lifetxt status life.txt
python -m lifetxt status life.txt --active
python -m lifetxt status life.txt --person self
python -m lifetxt status life.txt --format json --pretty
```

## 8. `agenda`

日時範囲に関連する item を表示します。

```sh
python -m lifetxt agenda [path ...] [range options] [filter options] [output options]
```

範囲判定ルール:

- `from/to` は期間として扱います。
- `on` は終日範囲として扱います。
- `due`、`do`、`at`、`moved_to` は時点または終日範囲として扱います。
- type `S` で `to:` がない item は、`from:` 以降継続中として扱います。
- `at:HH:MM` は `on:` があればその日付と組み合わせ、なければ指定範囲内の各日付と組み合わせます。
- simple `repeat:` の `daily`、`weekly`、`monthly`、`yearly`、`weekdays` は展開します。
- `interval:`、`until:`、`count:` は simple repeat の展開を制限します。
- `on:` のない floating `at:` repeat は、両端がある bounded agenda range の中だけで展開します。

### 8.1 範囲オプション

| Option | 意味 |
|---|---|
| `--from VALUE` | 範囲開始。`now`、`YYYY-MM-DD`、`YYYY-MM-DDTHH:MM` |
| `--to VALUE` | 範囲終了。`now`、`YYYY-MM-DD`、`YYYY-MM-DDTHH:MM` |
| `--around VALUE` | 範囲中心。省略時は `now` |
| `--window VALUE` | `--around` の半幅。省略時は `1h` |

`--from/--to` と `--around` は同時には使いません。
範囲指定がない場合は `--around now --window 1h` と同じ扱いです。

`--window` の duration:

| Form | 意味 |
|---|---|
| `15s` | 15 秒 |
| `30m` | 30 分 |
| `2h` | 2 時間 |
| `1d` | 1 日 |
| `1w` | 1 週間 |
| `1mo` | 1 か月。30 日として近似 |
| `1y` | 1 年。365 日として近似 |
| `30` | 30 分 |

例:

```sh
python -m lifetxt agenda life.txt --from 2026-06-06 --to 2026-06-06
python -m lifetxt agenda life.txt --from 2026-06-06T13:00 --to 2026-06-06T18:00
python -m lifetxt agenda life.txt --from 2026-06-06T13:00:30.25+09:00 --to 2026-06-06T18:00:00.5+09:00
python -m lifetxt agenda life.txt --around now --window 2h
python -m lifetxt agenda life.txt --around now --window 1w
python -m lifetxt agenda life.txt --from 2026-06-01 --to 2026-06-30 --type habit
```

### 8.2 フィルタオプション

| Option | 意味 |
|---|---|
| `--open` | 未完了 workflow item のみ表示。対象は `[ ]`、`[/]`、`[>]`、`[?]` |
| `--status VALUE` | status または alias で絞り込み。複数回指定または comma-separated |
| `--type VALUE` | type または alias で絞り込み。複数回指定または comma-separated |
| `--project VALUE` | `project:` で絞り込み。複数回指定または comma-separated |
| `--tag VALUE` | `tag:` で絞り込み。複数回指定または comma-separated |
| `--tag-all VALUE` | 指定した `tag:` をすべて持つ item のみ |
| `--exclude-tag VALUE` | 指定した `tag:` を持つ item を除外 |
| `--user VALUE` | user 関連 detail を横断して絞り込み |
| `--team VALUE` | `team:` / `group:` または config の team membership で絞り込み |
| `--person VALUE` | `person:` で絞り込み。複数回指定または comma-separated |
| `--owner VALUE` | `owner:` で絞り込み。複数回指定または comma-separated |
| `--assignee VALUE` | `assignee:` で絞り込み。複数回指定または comma-separated |
| `--attendee VALUE` | `attendee:` で絞り込み。複数回指定または comma-separated |
| `--detail FILTER` | detail key または `key=value` で絞り込み。複数指定は AND |
| `--text TEXT` | title、元行、detail 値に対する大文字小文字を区別しない部分一致 |

例:

```sh
python -m lifetxt agenda life.txt --from 2026-06-06 --to 2026-06-06 --open
python -m lifetxt agenda life.txt --from 2026-06-06 --to 2026-06-06 --status todo --type task
python -m lifetxt agenda life.txt --from 2026-06-06 --to 2026-06-06 --project research --tag urgent
python -m lifetxt agenda life.txt --from 2026-06-06 --to 2026-06-06 --assignee alice
python -m lifetxt agenda life.txt --from 2026-06-06 --to 2026-06-06 --detail priority=A --text report
python -m lifetxt agenda life.txt --from 2026-06-06 --to 2026-06-06 --person alice
```

`--detail key` は key の存在を確認します。`--detail key=value` は detail value の完全一致です。
複数の `--detail` は AND 条件です。

### 8.3 出力オプション

| Option | 意味 |
|---|---|
| `--format text` | 表で表示 |
| `--format life` | 一致した元の life.txt item 行を表示 |
| `--format json` | JSON 配列で表示 |
| `--format jsonl` | JSONL で表示 |
| `-o`, `--output` | 出力ファイル。省略時は標準出力 |
| `--pretty` | JSON を整形して出力 |

例:

```sh
python -m lifetxt agenda life.txt --from 2026-06-06 --to 2026-06-06 --format life
python -m lifetxt agenda life.txt --from 2026-06-06 --to 2026-06-06 --format json --pretty
python -m lifetxt agenda life.txt --around now --window 1w --format life -o agenda.life.txt
```

## 9. `assist`

フラグまたは対話入力で life.txt item を作成・更新します。

```sh
python -m lifetxt assist [options]
```

### 9.1 非対話で作成

```sh
python -m lifetxt assist --type task --title "Write Report" --due 2026-06-12 --project university
python -m lifetxt assist --type status --title "Working" --from 2026-06-06T14:00 --state busy --person self
```

基本オプション:

| Option | 意味 |
|---|---|
| `-s`, `--status` | status または alias。例: `[ ]`、`done`、`note` |
| `-t`, `--type` | type または alias。例: `T`、`task`、`status` |
| `--title` | item title |
| `-d`, `--detail` | `key=value` または `key:value`。複数回指定可能 |
| `-o`, `--output` | 生成行をファイルに追記 |
| `--append` | 生成行をファイルに追記 |
| `--no-check` | 生成行の validation を省略 |

known detail key には直接フラグもあります。各フラグは複数回指定できます。

```txt
--id --parent --ref --depends_on --blocks --related --created --updated --done --due --do --from --to
--state --user --person --owner --assignee --attendee --sender --recipient --team --group --service --channel
--visibility --notify_at --notify_from --notify_to --ack --snooze_until --on --at --repeat
--interval --until --count
--project --context --loc --priority --est --tag --note --body --mood --weather --url
--reason --moved_to
```

### 9.2 対話で作成

```sh
python -m lifetxt assist --interactive
python -m lifetxt assist --interactive --append life.txt
```

対話ヘルプ:

| Input | 意味 |
|---|---|
| `?` | 現在の prompt に応じた help |
| `?type` | type help |
| `?status` | status help |
| `?detail` | 推奨 detail key |
| `?all` | known detail key 全体 |
| `?due` | detail key 個別 help |

対応 terminal では、Tab で type、status、detail-key 候補を補完できます。
Up/Down で入力履歴を呼び出せます。`--no-completion` で補完と line editing を無効化できます。

### 9.3 既存 item の更新

行番号または完全一致の `id:` で item を選択して更新します。

```sh
python -m lifetxt assist --update life.txt --line 3 --title "New Title"
python -m lifetxt assist --update life.txt --match-id task_001 --status done --done 2026-06-06
python -m lifetxt assist --update life.txt --match-id task_001 --add-detail tag=important
python -m lifetxt assist --update life.txt --match-id task_001 --remove-detail tag
python -m lifetxt assist --update life.txt --match-id task_001 --output updated_life.txt
```

更新オプション:

| Option | 意味 |
|---|---|
| `--update FILE` | 既存 life.txt を読み込んで更新 |
| `--line N` | `N` 行目の item を選択 |
| `--match-id ID` | `id:` が `ID` と完全一致する item を選択 |
| `--add-detail key=value` | detail value を追加 |
| `--remove-detail key` | 指定 key の value をすべて削除 |
| `--output FILE` | 更新後のファイル全体を別ファイルに書き出し |

`--output` がない場合、update mode は入力ファイルへ書き戻します。

## 10. `serve`

任意機能の FastAPI REST API とブラウザGUIを起動します。

先にWeb依存を入れます。

```sh
pip install -r requirements-web.txt
```

server を起動します。

```sh
python -m lifetxt serve life.txt --host 127.0.0.1 --port 8000
```

ブラウザで `http://127.0.0.1:8000/` を開きます。

| Option | 意味 |
|---|---|
| `path ...` | 読み込む life.txt ファイル。省略時は `life.txt` |
| `--write-file FILE` | 作成、更新、削除に使うファイル |
| `--host HOST` | bind host。既定値は `127.0.0.1` |
| `--port PORT` | bind port。既定値は `8000` |

REST API は `/api/items`、`/api/agenda`、`/api/status`、`/api/health` を提供します。
詳細は [web.md](./web.md) を参照してください。

## 11. alias

status alias:

| Alias | Status |
|---|---|
| `todo`, `open` | `[ ]` |
| `progress`, `doing`, `in_progress` | `[/]` |
| `done`, `complete`, `completed` | `[x]` |
| `cancel`, `canceled`, `cancelled` | `[-]` |
| `defer`, `deferred`, `moved` | `[>]` |
| `pending`, `unknown` | `[?]` |
| `note`, `n` | `[N]` |

type alias:

| Alias | Type |
|---|---|
| `task`, `todo` | `T` |
| `event`, `calendar` | `E` |
| `deadline`, `due` | `D` |
| `reminder`, `remind` | `R` |
| `habit`, `recurring` | `H` |
| `note`, `memo` | `N` |
| `status`, `presence`, `presence_status`, `state` | `S` |

## 12. 実用例

検査と変換:

```sh
python -m lifetxt check life.txt
python -m lifetxt to-json life.txt --pretty -o life.json
python -m lifetxt to-jsonl life.txt --open --type task -o open_tasks.jsonl
```

絞り込んだ life.txt ファイルを作成:

```sh
python -m lifetxt filter life.txt --open --type task -o open_tasks.life.txt
python -m lifetxt filter life.txt --after now --type event -o future_schedule.life.txt
python -m lifetxt filter life.txt --type status --person self -o my_status.life.txt
```

カレンダー予定を取り込む:

```sh
python -m lifetxt import-ics google_calendar.ics -o life.txt --append --tag google
```

秘密 iCalendar URL からカレンダー予定を同期する:

```sh
python -m lifetxt sync-ics --url-env LIFETXT_GOOGLE_CAL_ICS -o .generated/google_calendar.life.txt --cache-dir .cache/lifetxt --tag google
```

現在時刻付近の未完了 item を表示:

```sh
python -m lifetxt agenda life.txt --around now --window 2h --open
```

今日の未完了 task を表示:

```sh
python -m lifetxt agenda life.txt --from 2026-06-06 --to 2026-06-06 --open --type task
```

チームの現在状態を表示:

```sh
python -m lifetxt status life.txt --active
```

ブラウザGUIを起動:

```sh
pip install -r requirements-web.txt
python -m lifetxt serve life.txt
```

## 追加: Message type と external config

### Message type (`M`)

`M` は人から人へのメッセージ、通知予約、配信依頼を記録する type です。

必須 detail:

```txt
sender recipient
```

主な推奨 detail:

```txt
sender recipient notify_at notify_from notify_to channel service priority project tag note url id parent created updated
```

例:

```sh
python -m lifetxt assist --type message --title "Review Slides" --sender self --recipient alice --notify_at 2026-06-06T09:00
python -m lifetxt agenda life.txt --from 2026-06-06 --to 2026-06-06 --recipient alice
python -m lifetxt filter life.txt --type message --recipient alice -o alice_messages.life.txt
python -m lifetxt to-json life.txt --type message --sender self --pretty
```

Message の日時判定では、`notify_at` は時点、`notify_from/notify_to` は通知期間として扱われます。

### external config

任意のコマンドで `--config FILE` を指定できます。省略時は `LIFETXT_CONFIG`、`.lifetxt.json`、`lifetxt.config.json` の順で探索します。

```sh
python -m lifetxt config init -o .lifetxt.json
python -m lifetxt --config .lifetxt.json config show
python -m lifetxt agenda --config .lifetxt.json --around now --window 1d
```

主な config key:

| Key | 意味 |
|---|---|
| `paths` | life.txt 読み込み系コマンドの default input files |
| `write_file` | `serve` の default writable file |
| `message.default_sender` | type `M` 作成時の default `sender:` |
| `message.default_channel` | type `M` 作成時の default `channel:` |
| `web.host`, `web.port` | `serve` の default bind 設定 |
| `sync_ics.sources` | `sync-ics` の default iCalendar sources |
## Additional: notify resident app and expanded config

### `notify`

type `M` の通知対象を表示、または `--watch` で常駐 polling します。

```sh
python -m lifetxt notify life.txt --recipient self
python -m lifetxt notify life.txt --recipient self --format json --pretty
python -m lifetxt notify life.txt --watch --interval 30
```

対象は type `M`、open workflow status (`[ ]`, `[/]`, `[>]`, `[?]`)、`recipient:` が一致する item です。`notify_at:` は単一通知時刻、`notify_from:` / `notify_to:` は通知期間として扱います。

### expanded config

`user.name` で自身のデフォルト名を指定できます。`message.default_sender` が空の場合、Message 作成時の `sender:` は `user.name` になります。

主な追加 config key:

| Key | Meaning |
|---|---|
| `user.name` | 自身の標準ユーザ名 |
| `user.display_name` | UI 表示名 |
| `notifications.recipient` | 通知対象者。空なら `user.name` |
| `notifications.lookahead` | 未来方向の通知検出幅 |
| `notifications.grace` | 過去方向の取りこぼし許容幅 |
| `notifications.poll_seconds` | 常駐通知と Web 通知の polling 秒数 |
| `notifications.desktop` | `notify --watch` の簡易 desktop 通知 default |
| `web.notification_poll_seconds` | Web UI 通知 polling 秒数 |
| `web.notification_lookahead` | Web UI 通知の未来方向検出幅 |
| `api.id_key` | id として扱う detail key。現在は `id` |
| `ids.auto` | 新規作成時に `id:` を自動付与するか |
| `ids.key` | 自動IDを書き込む detail key。通常は `id` |
| `ids.prefixes` | type ごとの自動ID prefix |
| `views` | Web UI のURL preset定義 |
| `sync_ics.generated_paths` | generated/read-only として扱うファイル一覧 |

`ids.auto` が `true` の場合、`assist`、`/api/items`、`/api/messages`、Message
reply の新規作成時に `id:` が未指定なら自動付与されます。既存IDは config
の `paths`、`write_file`、必要に応じて `--output` / `--append` の対象から収集されるため、
複数の `life.txt` を読み込む構成でも衝突を避けます。
`check` は重複IDを warning `W213` として報告します。複数入力ファイル間の重複も対象です。

### Notification acknowledgement and snooze

`ack:` がある Message は通知済みとして扱われ、`notify` と Web 通知の対象から外れます。
`snooze_until:` が未来の日時を指す場合、その時刻までは通知を抑止します。
`notify --watch` は `notifications.state_file` に通知IDを保存し、再起動後も同じ通知を繰り返さないようにできます。

| Key | Meaning |
|---|---|
| `notifications.state_file` | `notify --watch` の通知済みIDを保存するJSON file |
| `notifications.snooze_default` | Web UI / API の default snooze duration |

### `ids`

`ids` は item ID の監査用コマンドです。ファイルは変更しません。
`ids --assign` は一時ファイル経由でatomicに書き換えます。安全のため、実行前に
`--dry-run` で確認し、必要なら `--backup` で `FILE.bak` を作成してください。

```sh
python -m lifetxt ids life.txt
python -m lifetxt ids life.txt archive.life.txt --only duplicates
python -m lifetxt ids life.txt --only missing --format json --pretty
python -m lifetxt ids life.txt --assign --dry-run
python -m lifetxt ids life.txt --assign --backup
```

| Option | Meaning |
|---|---|
| `--key KEY` | 監査する detail key。省略時は config の `ids.key`、`api.id_key`、または `id` |
| `--only all` | summary、duplicate IDs、missing IDs を表示 |
| `--only present` | 存在するID一覧を表示 |
| `--only missing` | IDがないitemだけ表示 |
| `--only duplicates` | 重複IDだけ表示 |
| `--format text|json|jsonl` | 出力形式 |
| `--assign` | IDがないitemへIDを付与 |
| `--dry-run` | ファイルを書き換えず予定だけ表示 |
| `--backup` | `--assign` で変更前に `FILE.bak` を作成 |
## 追加: links

`links` は item 間の ID 参照を一覧表示するコマンドです。対象 key は `parent:`、`ref:`、`depends_on:`、`blocks:`、`related:` です。

```sh
python -m lifetxt links life.txt
python -m lifetxt links life.txt --id task_report --direction incoming
python -m lifetxt links life.txt --id task_report --direction outgoing --format json --pretty
python -m lifetxt links life.txt --relation depends_on --relation blocks
```

| Option | 意味 |
|---|---|
| `--id ID` | 指定 ID に接続する link だけを表示 |
| `--direction incoming|outgoing|both` | `--id` 指定時の方向 |
| `--relation RELATION` | `depends_on` などの relation key に絞り込み。複数指定またはカンマ区切り可 |
| `--key KEY` | ID として扱う detail key |
| `--format text|json|jsonl` | 出力形式 |

`check` は存在しない参照を `W215`、自己参照を `W216`、`parent:` cycle を `W217`、重複 ID による曖昧な参照を `W218` として報告します。
