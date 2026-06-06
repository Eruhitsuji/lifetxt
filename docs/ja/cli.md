# life.txt CLI ガイド

この文書は、次のコマンドで提供される CLI の詳細な使い方を説明します。

```sh
python -m lifetxt
```

CLI は外部依存なしで動作し、UTF-8 の `life.txt`、JSON、JSONL を扱います。
多くのコマンドは、path に `-` を指定するか path を省略すると標準入力から読み込みます。

## 1. コマンド一覧

```sh
python -m lifetxt check [path]
python -m lifetxt to-json [path]
python -m lifetxt to-jsonl [path]
python -m lifetxt from-json [path]
python -m lifetxt from-jsonl [path]
python -m lifetxt status [path]
python -m lifetxt agenda [path]
python -m lifetxt assist [options]
```

| Command | 目的 |
|---|---|
| `check` | life.txt の構文と意味的な警告を検査 |
| `to-json` | life.txt を JSON 配列へ変換 |
| `to-jsonl` | life.txt を JSONL へ変換 |
| `from-json` | JSON を life.txt へ変換 |
| `from-jsonl` | JSONL を life.txt へ変換 |
| `status` | `person:` ごとの最新 `S` status / presence を表示 |
| `agenda` | 日時範囲に関連する item を表示 |
| `assist` | 対話またはフラグで item を作成・更新 |

## 2. 共通仕様

### 2.1 入力 path

ファイルを読むコマンドでは、`path` は省略可能です。

```sh
python -m lifetxt check life.txt
python -m lifetxt check -
type life.txt | python -m lifetxt check
```

`path` を省略するか `-` を指定した場合、標準入力から読み込みます。

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

### 2.4 終了コード

| Code | 意味 |
|---|---|
| `0` | 成功 |
| `1` | 検証エラーまたはコマンドエラー |
| `2` | サブコマンド不足などの CLI usage error |

## 3. `check`

life.txt の構文と意味的なルールを検査します。

```sh
python -m lifetxt check [path] [--format text|json] [--warnings-as-errors]
```

| Option | 意味 |
|---|---|
| `path` | 入力ファイル。`-` なら標準入力 |
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
python -m lifetxt to-json [path] [-o output.json] [--pretty]
```

| Option | 意味 |
|---|---|
| `path` | 入力 life.txt。`-` なら標準入力 |
| `-o`, `--output` | 出力ファイル。省略時は標準出力 |
| `--pretty` | JSON を整形して出力 |

### 4.2 `to-jsonl`

life.txt を JSONL へ変換します。

```sh
python -m lifetxt to-jsonl [path] [-o output.jsonl]
```

### 4.3 `from-json`

JSON item、JSON item 配列、または `{ "items": [...] }` を life.txt に変換します。

```sh
python -m lifetxt from-json [path] [-o life.txt]
```

### 4.4 `from-jsonl`

JSONL を life.txt に変換します。

```sh
python -m lifetxt from-jsonl [path] [-o life.txt]
```

## 5. `status`

`person:` ごとの最新 `S` status / presence record を表示します。

```sh
python -m lifetxt status [path] [--format text|json|jsonl] [--person PERSON] [--pretty]
```

選択ルール:

- type `S` の item だけを対象にします。
- `person:` ごとに group 化します。
- `person:` がない場合は `self` として扱います。
- `from:` が最も新しい item を最新として選びます。

| Option | 意味 |
|---|---|
| `path` | 入力 life.txt。`-` なら標準入力 |
| `--format text` | 表で表示 |
| `--format json` | JSON 配列で表示 |
| `--format jsonl` | JSONL で表示 |
| `--person PERSON` | 特定 person のみ表示 |
| `--pretty` | JSON を整形して出力 |

例:

```sh
python -m lifetxt status life.txt
python -m lifetxt status life.txt --person self
python -m lifetxt status life.txt --format json --pretty
```

## 6. `agenda`

日時範囲に関連する item を表示します。

```sh
python -m lifetxt agenda [path] [range options] [filter options] [output options]
```

範囲判定ルール:

- `from/to` は期間として扱います。
- `on` は終日範囲として扱います。
- `due`、`do`、`at`、`moved_to` は時点または終日範囲として扱います。
- type `S` で `to:` がない item は、`from:` 以降継続中として扱います。
- `at:HH:MM` は `on:` があればその日付と組み合わせ、なければ指定範囲内の各日付と組み合わせます。

### 6.1 範囲オプション

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
| `30m` | 30 分 |
| `2h` | 2 時間 |
| `1d` | 1 日 |
| `30` | 30 分 |

例:

```sh
python -m lifetxt agenda life.txt --from 2026-06-06 --to 2026-06-06
python -m lifetxt agenda life.txt --from 2026-06-06T13:00 --to 2026-06-06T18:00
python -m lifetxt agenda life.txt --around now --window 2h
```

### 6.2 フィルタオプション

| Option | 意味 |
|---|---|
| `--open` | 未完了 workflow item のみ表示。対象は `[ ]`、`[/]`、`[>]`、`[?]` |
| `--status VALUE` | status または alias で絞り込み。複数回指定または comma-separated |
| `--type VALUE` | type または alias で絞り込み。複数回指定または comma-separated |
| `--project VALUE` | `project:` で絞り込み。複数回指定または comma-separated |
| `--tag VALUE` | `tag:` で絞り込み。複数回指定または comma-separated |
| `--person VALUE` | `person:` で絞り込み。複数回指定または comma-separated |
| `--detail FILTER` | detail key または `key=value` で絞り込み。複数指定は AND |
| `--text TEXT` | title、元行、detail 値に対する大文字小文字を区別しない部分一致 |

例:

```sh
python -m lifetxt agenda life.txt --from 2026-06-06 --to 2026-06-06 --open
python -m lifetxt agenda life.txt --from 2026-06-06 --to 2026-06-06 --status todo --type task
python -m lifetxt agenda life.txt --from 2026-06-06 --to 2026-06-06 --project research --tag urgent
python -m lifetxt agenda life.txt --from 2026-06-06 --to 2026-06-06 --detail priority=A --text report
python -m lifetxt agenda life.txt --from 2026-06-06 --to 2026-06-06 --person alice
```

`--detail key` は key の存在を確認します。`--detail key=value` は detail value の完全一致です。
複数の `--detail` は AND 条件です。

### 6.3 出力オプション

| Option | 意味 |
|---|---|
| `--format text` | 表で表示 |
| `--format life` | 一致した life.txt 行を表示 |
| `--format json` | JSON 配列で表示 |
| `--format jsonl` | JSONL で表示 |
| `--pretty` | JSON を整形して出力 |

例:

```sh
python -m lifetxt agenda life.txt --from 2026-06-06 --to 2026-06-06 --format life
python -m lifetxt agenda life.txt --from 2026-06-06 --to 2026-06-06 --format json --pretty
```

## 7. `assist`

フラグまたは対話入力で life.txt item を作成・更新します。

```sh
python -m lifetxt assist [options]
```

### 7.1 非対話で作成

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
--id --parent --created --updated --done --due --do --from --to
--state --person --service --visibility --on --at --repeat
--project --context --loc --priority --est --tag --note --url
--reason --moved_to
```

### 7.2 対話で作成

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

### 7.3 既存 item の更新

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

## 8. alias

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

## 9. 実用例

検査と変換:

```sh
python -m lifetxt check life.txt
python -m lifetxt to-json life.txt --pretty -o life.json
python -m lifetxt to-jsonl life.txt -o life.jsonl
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
python -m lifetxt status life.txt
```
