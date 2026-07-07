# life.txt

`life.txt` は、タスク、予定、締切、リマインダー、習慣、在席状態、メッセージ、メモ、日記・日誌を
1 つの読み書きしやすいプレーンテキストファイルで管理するための形式です。

形式の詳細は [life_txt_format_spec.md](./life_txt_format_spec.md) を参照してください。
command 互換性、filter、出力形式、変換規則は [cli.md](./cli.md) を参照してください。

## 最小 life.txt

```txt
[ ] T Write_Report due:2026-06-12 project:university assignee:alice
[ ] E Seminar from:2026-06-08T13:00 to:2026-06-08T14:30 loc:university attendee:alice
[/] S Working from:2026-06-06T14:00 state:busy person:self
[ ] M "Review slides" sender:self recipient:alice notify_at:2026-06-06T09:00 channel:teams
[N] J "Research day" on:2026-06-23 mood:good tag:lab
| Read papers in the morning.
| Wrote parser tests in the afternoon.
[N] N Research_Memo project:research
```

## examples

サンプルファイルは [../../examples/](../../examples/) にあります。

- [minimal_life.txt](../../examples/minimal_life.txt): 最小構成のサンプル
- [tasks_life.txt](../../examples/tasks_life.txt): タスク、締切、メモ
- [events_life.txt](../../examples/events_life.txt): カレンダー予定
- [habits_reminders_life.txt](../../examples/habits_reminders_life.txt): 習慣とリマインダー
- [status_presence.txt](../../examples/status_presence.txt): 個人の在席状態
- [team_status_life.txt](../../examples/team_status_life.txt): 複数人の在席状態
- [messages_life.txt](../../examples/messages_life.txt): message と通知 record
- [diary_life.txt](../../examples/diary_life.txt): 複数行 body を含む日記・日誌
- [markdown_life.txt](../../examples/markdown_life.txt): safe Markdown title / body / note rendering の例
- [linked_life.txt](../../examples/linked_life.txt): `parent`、`ref`、`depends_on`、`blocks`、`related` による ID 参照
- [recurrence_time_life.txt](../../examples/recurrence_time_life.txt): timezone、小数秒、simple repeat、body、依存関係の例
- [hierarchy_life.txt](../../examples/hierarchy_life.txt): インデントによる入れ子 record と `parent:` 推論の例
- [agenda_life.txt](../../examples/agenda_life.txt): `agenda` コマンド用データ
- [json_roundtrip_life.txt](../../examples/json_roundtrip_life.txt): 繰り返し key と引用値
- [calendar_import.ics](../../examples/calendar_import.ics): `import-ics` 用の iCalendar 入力例

## CLI

このリポジトリには、外部依存のない Python CLI が含まれます。
詳細なコマンドの使い方とオプション一覧は [cli.md](./cli.md) を参照してください。
任意機能の FastAPI REST API とブラウザGUIについては [web.md](./web.md) を参照してください。

```sh
python -m lifetxt check life.txt
python -m lifetxt to-json life.txt --pretty
python -m lifetxt to-jsonl life.txt --open --type task -o open_tasks.jsonl
python -m lifetxt to-csv life.txt --type journal -o journal.csv
python -m lifetxt markdown life.txt --field all --format html -o markdown.html
python -m lifetxt import-ics google_calendar.ics -o life.txt --append --tag google
python -m lifetxt sync-ics --url-env LIFETXT_GOOGLE_CAL_ICS -o .generated/google_calendar.life.txt --cache-dir .cache/lifetxt --tag google
python -m lifetxt filter life.txt --open --type task -o open_tasks.life.txt
python -m lifetxt filter life.txt --open --type task --canonical -o canonical_tasks.life.txt
python -m lifetxt filter life.txt --assignee alice -o alice_items.life.txt
python -m lifetxt filter "projects/**/*.life.txt" --team research --tag-all urgent,review --exclude-tag archived
python -m lifetxt filter life.txt --after now --type event -o future_schedule.life.txt
python -m lifetxt filter life.txt --type status --person self -o my_status.life.txt
python -m lifetxt filter life.txt --type message --recipient alice -o alice_messages.life.txt
python -m lifetxt status life.txt
python -m lifetxt status life.txt --active
python -m lifetxt status life.txt --format json --pretty
python -m lifetxt notify life.txt --recipient self
python -m lifetxt notify life.txt --watch --interval 30
python -m lifetxt ids life.txt --assign --dry-run
python -m lifetxt ids "projects/**/*.life.txt" --assign --prefix item --dry-run
python -m lifetxt links life.txt --id task_report --direction incoming
python -m lifetxt agenda life.txt --from 2026-06-06T13:00 --to 2026-06-06T18:00
python -m lifetxt agenda life.txt --from 2026-06-06T13:00:30+09:00 --to 2026-06-06T18:00:00+09:00
python -m lifetxt agenda life.txt --around now --window 1w --format life -o agenda.life.txt
python -m lifetxt agenda life.txt --from 2026-06-06 --to 2026-06-06 --open
python -m lifetxt agenda life.txt --from 2026-06-06 --to 2026-06-06 --type task --project research
python -m lifetxt tui life.txt
python -m lifetxt fzf life.txt --open --type task --action done
python -m lifetxt timer start life.txt --id task_report
python -m lifetxt timer stop
python -m lifetxt stats life.txt --project research
python -m lifetxt git-hook status
python -m lifetxt completion bash
python -m lifetxt from-json life.json -o life.txt
python -m lifetxt from-jsonl life.jsonl -o life.txt
python -m lifetxt from-csv journal.csv -o journal.life.txt
python -m lifetxt serve life.txt --host 127.0.0.1 --port 8000
python -m lifetxt serve life.txt .generated/google_calendar.life.txt --write-file life.txt --read-only
python -m lifetxt config init -o .lifetxt.json
```

Local install:

```sh
python -m pip install -e .
lifetxt check examples/minimal_life.txt
```

多くの読み込み系コマンドは複数の入力 path、glob pattern、life.txt 風 `.txt` を含むディレクトリを受け取れます。`filter`、`to-json`、
`to-jsonl`、`to-csv` は `--open`、`--status`、`--type`、`--project`、`--tag`、
`--tag-all`、`--exclude-tag`、`--user`、`--team`、`--person`、`--owner`、`--assignee`、`--attendee`、`--sender`、`--recipient`、`--detail`、`--text`、
`--after`、`--before` などの item filter に対応します。`filter --format life` は
一致した item の元行を既定で保持します。正規化した life.txt 行を再生成したい場合は
`--canonical` を使います。`person:` は status / presence の対象者、`assignee:` は
担当者、`owner:` は責任者、`attendee:` は予定参加者に使います。

`import-ics` コマンドは、Google Calendar の export などの iCalendar `.ics` を
`E` event item に変換します。時刻付き予定は `from:` / `to:`、終日予定は `on:`、
参加者は `attendee:` になり、`--append` で既存の `life.txt` に追記できます。
Imported calendar events include `source:ics` and `uid:` metadata. Convenience
presets can import Markdown task lists, Todoist CSV exports, and GitHub Issues
JSON exports:

```sh
python -m lifetxt import-ics tasks.md --preset markdown --project inbox
python -m lifetxt import-ics todoist.csv --preset todoist --tag todoist
python -m lifetxt import-ics github_issues.json --preset github --project repo
```

定期的なカレンダー同期では、秘密 iCalendar URL を環境変数に入れて `sync-ics`
を使います。手書きの item は `life.txt` に残し、ICS 由来の item は
`.generated/google_calendar.life.txt` のような生成ファイルに分離し、`agenda` や
`check` には両方のファイルを渡します。
Use `--merge-existing --soft-delete-missing` to preserve comments in the
generated output while updating UID-backed records in place.

任意のWeb interfaceは別途依存を入れて起動します。

```sh
pip install -r requirements-web.txt
python -m lifetxt serve life.txt
```

Web UI は Dashboard、Items、Agenda、Timeline、Focus、Review、Messages、
Team、Status、Notifications、Stats、Graph、Kiosk を header Workspace にまとめます。
record は中央 modal で開き、thread reply、dependency link、due quick action、
Markdown preview を確認できます。Review は project/custom date filter と
Markdown copy に対応し、Dashboard card と theme token は `web.dashboard.*` と
`web.theme.*` で設定できます。`Ctrl+K` で fuzzy Command Palette を開き、
recently opened records、undo history、export、theme toggle、kiosk mode などを
実行できます。共有したい view は URL parameter または config `views` preset で
扱います。公開用や常時表示用途では `--read-only`、複数 file を読みつつ書き込み先を
固定する場合は `--write-file FILE` を使ってください。詳細は [web.md](./web.md) を
参照してください。

端末向け補助機能として `tui`、`fzf`、`timer`、`stats`、`git-hook`、
`completion` があります。`fzf` は `fzf` または `peco` が PATH に必要です。
TUI は任意の `tui` extra を使えますが、依存なしの fallback 表示もあります。

## assist

入力補助は非対話型と対話型の両方に対応します。

```sh
python -m lifetxt assist --type task --title "Write Report" --due 2026-06-12 --project university --tag report
python -m lifetxt assist --type status --title "Working" --from 2026-06-06T14:00 --state busy --person self
python -m lifetxt assist --type message --title "Review Slides" --sender self --recipient alice --notify_at 2026-06-06T09:00
python -m lifetxt assist --type diary --title "Research day" --on 2026-06-23 --mood good --body "Read papers."
python -m lifetxt assist --type task --title "Write Report" --due 2026-06-12 --output new_life.txt
python -m lifetxt assist --interactive --append life.txt
```

作成モードでは、`assist --output FILE` は生成した行を `FILE` に追記します。
既存データは行番号または `id:` で更新できます。

```sh
python -m lifetxt assist --update life.txt --match-id task_001 --status done --done 2026-06-06
python -m lifetxt assist --update life.txt --line 3 --title "New Title" --add-detail tag=important
```

## status と agenda

`status` コマンドは、`person:` ごとに最新の `S` item を表示します。
`person:` が省略された場合、この集約では `self` として扱います。
`--active` を指定すると、`to:` を持つ終了済み status log は除外します。

`agenda` コマンドは、指定した日時範囲に関連する item を表示します。
`from/to` と `on` は期間として扱い、`due`、`do`、`at`、`moved_to` は
時点または終日範囲として扱います。
日時値は `2026-06-06T13:00:30.25+09:00` のように、秒、小数秒、明示的な
timezone を含められます。simple `repeat:` の `daily`、`weekly`、`monthly`、
`yearly`、`weekdays` は agenda と時刻 filter で展開され、`interval:`、
`until:`、`count:` で制限できます。`repeat:RRULE:...` も
`FREQ=DAILY|WEEKLY|MONTHLY|YEARLY`、`INTERVAL`、`COUNT`、`UNTIL`、
daily/weekly の `BYDAY` の dependency-free subset を展開します。

agenda filter は組み合わせて使えます。

```sh
python -m lifetxt agenda life.txt --from 2026-06-06 --to 2026-06-06 --open
python -m lifetxt agenda life.txt --from 2026-06-06 --to 2026-06-06 --status todo --type task
python -m lifetxt agenda life.txt --from 2026-06-06 --to 2026-06-06 --project research --tag urgent
python -m lifetxt agenda life.txt --from 2026-06-06 --to 2026-06-06 --team research --tag-all urgent,review
python -m lifetxt agenda life.txt --from 2026-06-06 --to 2026-06-06 --detail priority=A --text report
```

`--open` は未完了の workflow item のみを表示します。対象は `[ ]`、`[/]`、
`[>]`、`[?]` です。複数の `--detail key=value` は AND 条件です。
`--window` は秒、分、時間、日、週、30 日として近似した月、365 日として
近似した年を受け付けます。

## JSON 形状

同じ key を複数回書いても往復変換できるように、detail は常に配列として表現します。

```json
{
  "status": "[ ]",
  "type": "T",
  "title": "Create_Slides",
  "details": {
    "project": ["research"],
    "tag": ["important", "thesis"]
  }
}
```

## テスト

```sh
python -m unittest discover
```

## 追加: Message type と external config

Message records use type `M`. `sender:` と `recipient:` が必須で、`notify_at:` で単一通知時刻、`notify_from:` / `notify_to:` で通知期間を指定できます。
本文が長い場合は、title を短く保ち `body:` に本文を書けます。

```sh
python -m lifetxt assist --type message --title "Review Slides" --sender self --recipient alice --notify_at 2026-06-06T09:00
python -m lifetxt filter life.txt --type message --recipient alice -o alice_messages.life.txt
python -m lifetxt agenda life.txt --from 2026-06-06 --to 2026-06-06 --recipient alice
```

`agenda` では `notify_at` を時点、`notify_from/notify_to` を通知期間として扱います。Web API では `/api/messages` で Message item の一覧と作成ができます。

外部 config の `ids.auto: true` を使うと、新規作成時に `id:` が未指定の item へ自動IDを付与できます。採番前に config の `paths` と `write_file` を走査するため、複数の `life.txt` を読み込む構成でも既存IDとの衝突を避けます。
重複IDは warning `W213` として報告されます。
`python -m lifetxt ids life.txt` で存在するID、欠落ID、重複IDを監査できます。
`ids --assign --dry-run` で既存データへのID付与予定を確認し、`--backup` 付きで安全に反映できます。
`ids.key` / `api.id_key` を設定すると、`id:` 以外の detail key を ID key として使えます。

item は ID で相互参照できます。`parent:` は階層や message thread、`ref:` は汎用参照、`depends_on:` は前提、`blocks:` は後続 item のブロック、`related:` は弱い関連に使います。`check` は存在しない参照、自己参照、`parent:` cycle、完了済み item が open な prerequisite に依存している状態を warning として報告します。`agenda` と `health` は open prerequisite に block されている open item を表示します。関係の一覧は `python -m lifetxt links life.txt` で確認できます。依存関係だけを見たい場合は `python -m lifetxt links life.txt --relation depends_on --relation blocks` を使えます。
インデントされた item 行でも階層を表現できます。子 item に `parent:` がない場合、nearest less-indented ancestor の `id:` から `parent:` を推論します。

```txt
[ ] T Research_Project id:proj_research
  [ ] T Literature_Review id:task_lit
    [N] N Reading_Memo
```

VS Code 用の基本的な syntax highlight と snippet は [../../editors/vscode/lifetxt](../../editors/vscode/lifetxt) にあります。設定方法と今後の language server 方針は [editor.md](./editor.md) を参照してください。
`users`、`teams`、`tags.aliases` / `tags.groups` は `--user`、`--team`、tag filter の展開に使われます。

Message 通知は `ack:` で確認済みにでき、`snooze_until:` で指定時刻まで通知を抑止できます。
`notify --watch` は `notifications.state_file` に通知済みIDを保存し、再起動後の重複通知を抑えられます。

External JSON config は `--config FILE`、`LIFETXT_CONFIG`、`.lifetxt.json`、`lifetxt.config.json` で利用できます。

```sh
python -m lifetxt config init -o .lifetxt.json
python -m lifetxt --config .lifetxt.json config show
```

## Journal / Diary と CSV

日記・日誌は type `J` を使います。alias は `journal`、`diary`、`log`、`entry` です。status は `[N]` を推奨します。長文は `body:` と、直前 item に続く `|` 継続行で表現できます。
`body:` は `J` 専用ではなく、詳細な task、event description、message、note にも使えます。短い補足は `note:`、長文は `body:` と使い分けます。

`to-csv` は `to-json` と同じ filter option を使えます。CSV は `status`、`type`、`title` と detail key の列を持ち、同じ key の複数値はセル内 JSON 配列として保存します。
