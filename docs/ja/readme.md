# life.txt

`life.txt` は、タスク、予定、締切、リマインダー、習慣、在席状態、メモを
1 つの読み書きしやすいプレーンテキストファイルで管理するための形式です。

形式の詳細は [life_txt_format_spec.md](./life_txt_format_spec.md) を参照してください。

## 最小 life.txt

```txt
[ ] T Write_Report due:2026-06-12 project:university
[ ] E Seminar from:2026-06-08T13:00 to:2026-06-08T14:30 loc:university
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

## CLI

このリポジトリには、外部依存のない Python CLI が含まれます。

```sh
python -m lifetxt check life.txt
python -m lifetxt to-json life.txt --pretty
python -m lifetxt to-jsonl life.txt -o life.jsonl
python -m lifetxt status life.txt
python -m lifetxt status life.txt --format json --pretty
python -m lifetxt agenda life.txt --from 2026-06-06T13:00 --to 2026-06-06T18:00
python -m lifetxt agenda life.txt --around now --window 2h
python -m lifetxt from-json life.json -o life.txt
python -m lifetxt from-jsonl life.jsonl -o life.txt
```

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

`agenda` コマンドは、指定した日時範囲に関連する item を表示します。
`from/to` と `on` は期間として扱い、`due`、`do`、`at`、`moved_to` は
時点または終日範囲として扱います。

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
