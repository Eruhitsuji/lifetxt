# life.txt

`life.txt` は、タスク、予定、締切、リマインダー、習慣、在席状態、メモを
1 つの読み書きしやすいプレーンテキストファイルで管理するための形式です。

形式の詳細は [life_txt_format_spec.md](./life_txt_format_spec.md) を参照してください。

## 最小 life.txt

```txt
[ ] T Write_Report due:2026-06-12 project:university assignee:alice
[ ] E Seminar from:2026-06-08T13:00 to:2026-06-08T14:30 loc:university attendee:alice
[/] S Working from:2026-06-06T14:00 state:busy person:self
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
- [agenda_life.txt](../../examples/agenda_life.txt): `agenda` コマンド用データ
- [json_roundtrip_life.txt](../../examples/json_roundtrip_life.txt): 繰り返し key と引用値
- [calendar_import.ics](../../examples/calendar_import.ics): `import-ics` 用の iCalendar 入力例

## CLI

このリポジトリには、外部依存のない Python CLI が含まれます。
詳細なコマンドの使い方とオプション一覧は [cli.md](./cli.md) を参照してください。

```sh
python -m lifetxt check life.txt
python -m lifetxt to-json life.txt --pretty
python -m lifetxt to-jsonl life.txt --open --type task -o open_tasks.jsonl
python -m lifetxt import-ics google_calendar.ics -o life.txt --append --tag google
python -m lifetxt sync-ics --url-env LIFETXT_GOOGLE_CAL_ICS -o .generated/google_calendar.life.txt --cache-dir .cache/lifetxt --tag google
python -m lifetxt filter life.txt --open --type task -o open_tasks.life.txt
python -m lifetxt filter life.txt --open --type task --canonical -o canonical_tasks.life.txt
python -m lifetxt filter life.txt --assignee alice -o alice_items.life.txt
python -m lifetxt filter life.txt --after now --type event -o future_schedule.life.txt
python -m lifetxt filter life.txt --type status --person self -o my_status.life.txt
python -m lifetxt status life.txt
python -m lifetxt status life.txt --active
python -m lifetxt status life.txt --format json --pretty
python -m lifetxt agenda life.txt --from 2026-06-06T13:00 --to 2026-06-06T18:00
python -m lifetxt agenda life.txt --around now --window 1w --format life -o agenda.life.txt
python -m lifetxt agenda life.txt --from 2026-06-06 --to 2026-06-06 --open
python -m lifetxt agenda life.txt --from 2026-06-06 --to 2026-06-06 --type task --project research
python -m lifetxt from-json life.json -o life.txt
python -m lifetxt from-jsonl life.jsonl -o life.txt
```

多くの読み込み系コマンドは複数の入力 path を受け取れます。`filter`、`to-json`、
`to-jsonl` は `--open`、`--status`、`--type`、`--project`、`--tag`、
`--person`、`--owner`、`--assignee`、`--attendee`、`--detail`、`--text`、
`--after`、`--before` などの item filter に対応します。`filter --format life` は
一致した item の元行を既定で保持します。正規化した life.txt 行を再生成したい場合は
`--canonical` を使います。`person:` は status / presence の対象者、`assignee:` は
担当者、`owner:` は責任者、`attendee:` は予定参加者に使います。

`import-ics` コマンドは、Google Calendar の export などの iCalendar `.ics` を
`E` event item に変換します。時刻付き予定は `from:` / `to:`、終日予定は `on:`、
参加者は `attendee:` になり、`--append` で既存の `life.txt` に追記できます。

定期的なカレンダー同期では、秘密 iCalendar URL を環境変数に入れて `sync-ics`
を使います。手書きの item は `life.txt` に残し、ICS 由来の item は
`.generated/google_calendar.life.txt` のような生成ファイルに分離し、`agenda` や
`check` には両方のファイルを渡します。

## assist

入力補助は非対話型と対話型の両方に対応します。

```sh
python -m lifetxt assist --type task --title "Write Report" --due 2026-06-12 --project university --tag report
python -m lifetxt assist --type status --title "Working" --from 2026-06-06T14:00 --state busy --person self
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

agenda filter は組み合わせて使えます。

```sh
python -m lifetxt agenda life.txt --from 2026-06-06 --to 2026-06-06 --open
python -m lifetxt agenda life.txt --from 2026-06-06 --to 2026-06-06 --status todo --type task
python -m lifetxt agenda life.txt --from 2026-06-06 --to 2026-06-06 --project research --tag urgent
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
