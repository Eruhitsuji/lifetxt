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
python -m lifetxt sources [path ...]
python -m lifetxt to-json [path ...]
python -m lifetxt to-jsonl [path ...]
python -m lifetxt to-csv [path ...]
python -m lifetxt markdown [path ...]
python -m lifetxt import-ics [path ...]
python -m lifetxt sync-ics --url-env ENVVAR
python -m lifetxt filter [path ...]
python -m lifetxt from-json [path ...]
python -m lifetxt from-jsonl [path ...]
python -m lifetxt from-csv [path ...]
python -m lifetxt status [path ...]
python -m lifetxt notify [path ...]
python -m lifetxt agenda [path ...]
python -m lifetxt assist [options]
python -m lifetxt tui [path ...]
python -m lifetxt fzf [path ...]
python -m lifetxt timer start path --id ID
python -m lifetxt timer pause
python -m lifetxt timer resume
python -m lifetxt timer stop
python -m lifetxt timer summary [path ...]
python -m lifetxt stats [path ...]
python -m lifetxt git-hook install
python -m lifetxt completion bash
python -m lifetxt serve [path ...]
python -m lifetxt mcp [path ...]
python -m lifetxt config init
python -m lifetxt config show
python -m lifetxt init
python -m lifetxt doctor
python -m lifetxt quick "Title"
python -m lifetxt done [path ...]
python -m lifetxt assign [path ...]
python -m lifetxt batch [path ...]
python -m lifetxt archive [path ...]
python -m lifetxt undo [path ...]
python -m lifetxt summary [path ...]
python -m lifetxt inbox [path ...]
python -m lifetxt cleanup [path ...]
python -m lifetxt health [path ...]
python -m lifetxt review [path ...]
python -m lifetxt who [path ...]
python -m lifetxt search PATTERN [path ...]
python -m lifetxt snapshot [path ...]
python -m lifetxt lint [path ...]
python -m lifetxt diff FILE_A FILE_B
python -m lifetxt plot [path ...]
python -m lifetxt export-heatmap [path ...]
python -m lifetxt migrate [path ...]
python -m lifetxt from-markdown [path ...]
python -m lifetxt deps [path ...]
python -m lifetxt tag list [path ...]
python -m lifetxt watch [path ...] -- COMMAND
python -m lifetxt encrypt [path ...]
python -m lifetxt decrypt [path ...]
python -m lifetxt share [path ...]
python -m lifetxt digest [path ...]
python -m lifetxt template list
```

| Command | 目的 |
|---|---|
| `check` | life.txt の構文と意味的な警告を検査 |
| `ids` | item ID の存在、欠落、重複を監査 |
| `links` | item 間の ID 参照を表示 |
| `sources` | 各 item を所有する入力ファイルを表示 |
| `to-json` | life.txt を JSON 配列へ変換 |
| `to-jsonl` | life.txt を JSONL へ変換 |
| `to-csv` | life.txt を CSV へ変換 |
| `markdown` | safe Markdown field を HTML / text / JSON / JSONL として描画 |
| `import-ics` | iCalendar `.ics` の予定を life.txt event item に変換 |
| `sync-ics` | iCalendar URL を取得して life.txt event item を再生成 |
| `filter` | item を絞り込み、life.txt / JSON / JSONL で出力 |
| `from-json` | JSON を life.txt へ変換 |
| `from-jsonl` | JSONL を life.txt へ変換 |
| `from-csv` | CSV を life.txt へ変換 |
| `status` | `person:` ごとの最新 `S` status / presence を表示 |
| `notify` | type `M` の通知対象を表示、または常駐監視 |
| `agenda` | 日時範囲に関連する item を表示 |
| `assist` | 対話またはフラグで item を作成・更新 |
| `tui` | task、agenda、status を端末ダッシュボードで表示 |
| `fzf` | `fzf` または `peco` で item を選択し action を実行 |
| `timer` | item の作業時間を計測し `elapsed:` に記録 |
| `stats` | task、habit、mood、project の統計を表示 |
| `git-hook` | life.txt 検査用 Git hook を導入または確認 |
| `completion` | shell completion script を生成 |
| `serve` | 任意機能の FastAPI REST API とブラウザGUIを起動 |
| `mcp` | AI client 向けの stdio MCP server を起動 |
| `config` | 外部 JSON config を作成または表示 |
| `init` | 対話形式の初回セットアップ。life.txt と .lifetxt.json を作成 |
| `doctor` | Python version、file、dependency、data の問題を検査 |
| `quick` (`q`) | 新規 item をすばやく作成して file に追記 |
| `done` | item を完了にし `done:TODAY` を追記 |
| `assign` | 既存 item の `assignee:` を変更 |
| `batch` | 複数の life.txt file に対して単純な操作を一括適用 |
| `archive` | 完了/中止済み item を別 file へ移動またはコピー |
| `undo` | 直前の書き込み操作前の状態に file を復元 |
| `summary` | life.txt file の概要を素早く表示 |
| `inbox` | project / due / assignee が未設定の open task を一覧表示 |
| `cleanup` | 問題を報告し、次に実行すべき command を提案するガイド付きナビゲーター |
| `health` | 停滞した task、未実施の habit、迫った deadline などの健全性チェック |
| `review` | 完了 task、habit、mood、elapsed time の期間サマリーを表示 |
| `who` | 各 person の最新 `S` item によるチーム presence サマリー |
| `search` | title や field 値の部分一致・正規表現で item を検索 |
| `snapshot` | life.txt file をタイムスタンプ付きで point-in-time backup |
| `lint` | key 名の typo、tag の大小文字、重複 key など style を検査 |
| `diff` | 2つの life.txt file の意味的な差分を表示 |
| `plot` | task/habit/mood/elapsed の統計を bar chart で表示 (text/SVG/PNG) |
| `export-heatmap` | task/habit の活動量を dependency-free SVG heatmap として出力 |
| `migrate` | life.txt file に in-place で format migration を適用 |
| `from-markdown` | Markdown task list (`- [ ] title`) を life.txt item に変換 |
| `deps` | `depends_on:`/`blocks:` の依存関係を tree 表示 |
| `tag` | tag 管理: list、rename、merge |
| `watch` | life.txt file の変更を監視し、変更のたびに command を再実行 |
| `encrypt` | passphrase で選択した field 値を in-place で暗号化 |
| `decrypt` | `enc:` 付き field 値を in-place で復号 |
| `share` | filter + review + chart をまとめた自己完結型 HTML/Markdown report を出力 |
| `digest` | `review` のサマリーを Slack、email、または local file へ送信 |
| `template` | 再利用可能な named item template を list / apply |

## 2. 共通仕様

### 2.0 外部 config

任意のコマンドで、subcommand の前に `--config FILE` を指定できます。省略時は
`LIFETXT_CONFIG`、`.lifetxt.json`、`lifetxt.config.json` の順で探索します。

```sh
python -m lifetxt config init -o .lifetxt.json
python -m lifetxt --config .lifetxt.json check
python -m lifetxt agenda --config .lifetxt.json --around now --window 1d
```

`paths` は life.txt 読み込み系 command の default input files、`write_file` は
`serve` の writable file、`message` は type `M` の作成 default、`sync_ics` は
calendar sync の default source / output を指定します。

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
ファイル入力の場合、診断には line / column の前に source path が付きます。
stdin のみの場合は source path を省略します。

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

階層の canonical form は明示的な `parent:` です。`--canonical` は indentation を除去し、推論できる場合は `parent:` を保持または追加します。

### 2.5 終了コード

| Code | 意味 |
|---|---|
| `0` | 成功 |
| `1` | 検証エラーまたはコマンドエラー |
| `2` | サブコマンド不足などの CLI usage error |

### 2.6 フォーマット互換性

CLI は [life_txt_format_spec.md](./life_txt_format_spec.md) のファイル文法に従います。互換性で重要な点は次の通りです。

- life.txt ファイル内の detail は `key:value` のみです。
- `key=value` は `assist -d`、`assist --add-detail`、対話 detail prompt などの helper 入力だけで使える便宜記法です。
- JSON / JSONL では、detail は値が 1 つでも常に配列です。
- CSV 変換では `status`、`type`、`title` 列が必須です。それ以外の非空列は detail になり、JSON 配列セルは同じ key の複数値になります。
- `filter`、`agenda`、`stats`、`to-json`、`to-jsonl`、`to-csv`、`markdown` は status、type、project、tag、user、team、detail、text、time filter の実装を共有します。
- `check`、`ids`、`links`、各 converter は同じ parser を使うため、ある読み込み command が受け付ける構文は他の読み込み command でも受け付けます。
- 複数入力ファイルは ID 重複と参照検査では 1 つの論理集合として扱われます。

command 対応表:

| Command | life.txt 読み込み | life.txt 書き込み | 構文検証 | item filter |
|---|---:|---:|---:|---:|
| `check` | yes | no | yes | no |
| `ids` | yes | `--assign` 時のみ | yes | no |
| `links` | yes | no | yes | relation filter |
| `to-json`, `to-jsonl`, `to-csv`, `markdown` | yes | no | yes | yes |
| `from-json`, `from-jsonl`, `from-csv` | no | yes | serializer rule | no |
| `filter` | yes | yes | yes | yes |
| `status` | yes | no | yes | `--person`, `--active` |
| `notify` | yes | no | yes | notification 固有 |
| `agenda` | yes | `--format life -o` 時のみ | yes | yes |
| `assist` | update 時は yes | yes | `--no-check` 以外 yes | no |
| `import-ics`, `sync-ics` | `.ics` | yes | generated item validation | no |
| `tui` | yes | no | yes | dashboard 固有 |
| `fzf` | yes | `done` と `delete` action | yes | yes |
| `timer` | yes | `start` と `stop` が 1 item を更新 | yes | summary filter |
| `stats` | yes | no | yes | yes |
| `git-hook` | no | Git hook のみ | no | no |
| `completion` | no | 任意の script output | no | no |
| `serve` | yes | API/UI 経由で yes | yes | URL/API filter |

### 2.x format compatibility note

life.txt の detail は file 内では `key:value` です。`key=value` は `assist`
などの helper input でのみ受け付けます。行末の `\` は次の物理行と結合され、
`check`、`filter`、`agenda`、converter などすべての読み取り系 command で
同じ logical-line parser により扱われます。

### 2.y Cross-file input set

1 回の command で読み込まれたファイル群は、ID check と reference 解決では 1 つの logical input set として扱われます。`parent:`、`ref:`、`depends_on:`、`blocks:`、`related:` は、同時に読み込まれた任意のファイル内の ID を参照できます。cross-file reference を解決したい場合は、関連ファイルをすべて path / glob / config paths で渡してください。

## 3. `check`

life.txt の構文と意味的なルールを検査します。

```sh
python -m lifetxt check [path ...] [--format text|json] [--warnings-as-errors]
python -m lifetxt check life.txt --severity warning --category reference
python -m lifetxt check life.txt --code E010,W213 --format json
```

| Option | 意味 |
|---|---|
| `path ...` | 入力ファイル。`-` なら標準入力 |
| `--format text` | 人間向けの診断を表示 |
| `--format json` | 診断を JSON で表示 |
| `--warnings-as-errors` | warning がある場合も非ゼロ終了 |
| `--severity error|warning` | severity で絞り込み。複数回指定または comma-separated |
| `--code CODE` | `E010` や `W213` などの診断 code で絞り込み。複数回指定または comma-separated |
| `--category CATEGORY` | 診断 category で絞り込み。複数回指定または comma-separated |

診断 filter は出力と終了コードの両方に適用されます。たとえば
`--category reference` は reference category に一致した診断だけで終了コードを決め、
無関係な syntax や style の診断は対象外にします。

Category:

| Category | 主な診断 |
|---|---|
| `syntax` | status、type、title、detail syntax などの parser error |
| `schema` | core status/type value の不正 |
| `style` | key style と custom-key recommendation |
| `time` | date/time value format と range warning |
| `status` | presence/status item rule |
| `message` | message item sender/recipient/notification rule |
| `id` | duplicate ID と unsafe ID-like value |
| `reference` | missing/self/cyclic/ambiguous reference |
| `recurrence` | `repeat:`、`RRULE:`、`interval:`、`count:` recommendation |
| `workflow` | status/detail workflow と dependency-state recommendation |
| `semantic` | 上記に含まれない semantic diagnostic |

例:

```sh
python -m lifetxt check life.txt
python -m lifetxt check life.txt --warnings-as-errors
python -m lifetxt check life.txt --format json
python -m lifetxt check life.txt --category id,reference
```

### 3.1 `ids`

item ID を監査します。既定ではファイルを変更しません。`--assign` を指定した場合だけ、ID がない item に ID を追加できます。

```sh
python -m lifetxt ids [path ...] [--only all|present|missing|duplicates]
```

| Option | 意味 |
|---|---|
| `path ...` | 入力 life.txt。`-` なら標準入力 |
| `--key KEY` | 監査する detail key。省略時は config の `ids.key`、`api.id_key`、または `id` |
| `--only all` | summary、duplicate IDs、missing IDs を表示 |
| `--only present` | 存在する ID 一覧を表示 |
| `--only missing` | ID がない item だけ表示 |
| `--only duplicates` | 重複 ID だけ表示 |
| `--format text|json|jsonl` | 出力形式 |
| `--pretty` | JSON を整形して出力 |
| `--assign` | ID がない item へ ID を付与 |
| `--dry-run` | ファイルを書き換えず予定だけ表示 |
| `--backup` | `--assign` で変更前に `FILE.bak` を作成 |
| `--prefix PREFIX` | `--assign` で使う ID prefix。省略時は type 別 config prefix |

例:

```sh
python -m lifetxt ids life.txt
python -m lifetxt ids life.txt archive.life.txt --only duplicates
python -m lifetxt ids life.txt --only missing --format json --pretty
python -m lifetxt ids life.txt --assign --dry-run
python -m lifetxt ids life.txt --assign --backup
python -m lifetxt ids "projects/**/*.life.txt" --assign --prefix item --dry-run
```

### 3.2 `links`

`parent:`、`ref:`、`depends_on:`、`blocks:`、`related:` など、item ID を指す関係を表示します。

```sh
python -m lifetxt links [path ...]
python -m lifetxt links life.txt --id task_report --direction incoming
python -m lifetxt links life.txt --id task_report --direction outgoing --format json --pretty
python -m lifetxt links life.txt --relation depends_on --relation blocks
python -m lifetxt links life.txt --chain task_report
python -m lifetxt links life.txt --chain task_report --format json --pretty
```

| Option | 意味 |
|---|---|
| `path ...` | 入力 life.txt。`-` なら標準入力 |
| `--id ID` | この ID に接続する link だけ表示 |
| `--chain ID` | この ID の dependency blocker chain を表示 |
| `--direction incoming|outgoing|both` | `--id` 使用時の向き。既定値は `both` |
| `--relation RELATION` | `depends_on` などの relation key で絞り込み。複数回指定または comma-separated |
| `--key KEY` | ID として扱う detail key。省略時は config の `ids.key`、`api.id_key`、または `id` |
| `--format text|json|jsonl|mermaid|dot` | 出力形式。`--chain` は `text`、`json`、`jsonl` に対応 |
| `--pretty` | JSON を整形して出力 |

`check` は存在しない参照 (`W215`)、自己参照 (`W216`)、`parent:` cycle (`W217`)、曖昧な参照 (`W218`)、完了済み item の `depends_on:` prerequisite がまだ open な場合 (`W224`) も報告します。

依存関係の動作:

- `depends_on:ID` は `ID` が open の間、現在の item を block します。
- `blocks:ID` は現在の item が open の間、`ID` を block する独立した主張です。
- `health` は block されている open item を `W305` として報告します。
- `links --chain ID` と `deps --root ID` は同じ blocker chain を terminal 向け tree として表示します。
  direct `depends_on:` blocker と inverse `blocks:` blocker の両方を含めます。

### 3.3 `sources`

parse された item の source ownership を表示します。手書きファイル、generated calendar
file、archive file を同時に読むとき、どの item がどのファイル由来か確認するために使います。

```sh
python -m lifetxt sources [path ...]
python -m lifetxt sources "projects/**/*.life.txt" --format json --pretty
python -m lifetxt sources life.txt archive.life.txt --missing-id
```

| Option | 意味 |
|---|---|
| `path ...` | 入力 life.txt、directory、glob、または標準入力の `-` |
| `--key KEY` | item ID として表示する detail key。省略時は config の `ids.key`、`api.id_key`、または `id` |
| `--missing-id` | 選択した ID key がない item だけ表示 |
| `--format text|json|jsonl` | 出力形式 |
| `--pretty` | JSON を整形して出力 |

report には source path、line range、選択 ID、parent ID、type、status、title、
indentation level、detail count が含まれます。同じ論理入力集合に対する duplicate ID
と reference check も実行し、warning は stderr に出力します。

## 4. 変換と rendering

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
| `--occurrences` | 保存済み item ではなく、計算された agenda occurrence record を出力 |
| `filter options` | `filter` と同じ item filter |

ファイル由来の入力では、各 JSON object に `_source_file` と `_source_line` が含まれます。複数行 record では `_source_end_line` も含まれます。これらは tool 用 metadata であり、`from-json` では life.txt の detail key として扱われません。

`--occurrences` を指定すると、`to-json` は保存済み source item ではなく
計算済み agenda record を出力します。この mode では `--after` と `--before` が
両方必要です。範囲内の対応済み `repeat:` / `RRULE:` を展開し、`agenda` と同じ
filter を適用します。生成された record には、可能な場合 `generated: true`、
`source_id`、`occurrence_start`、`occurrence_end`、`occurrence_index`、
`repeat_rule` が含まれます。

### 4.2 `to-jsonl`

life.txt を JSONL へ変換します。

```sh
python -m lifetxt to-jsonl [path ...] [-o output.jsonl] [--occurrences] [filter options]
```

JSONL の各行は `to-json` と同じ shape で、ファイル由来の入力では `_source_file` と line metadata を含みます。
`--occurrences` 時は各行が 1 つの計算済み agenda occurrence record になり、
`--after` と `--before` が必要です。

### 4.3 `from-json`

JSON item、JSON item 配列、または `{ "items": [...] }` を life.txt に変換します。

```sh
python -m lifetxt from-json [path ...] [-o life.txt]
```

`--canonical` を指定すると、JSON の `indent` から推論できる階層を明示的な `parent:` に変換し、unindented な life.txt を出力します。

### 4.4 `from-jsonl`

JSONL を life.txt に変換します。

```sh
python -m lifetxt from-jsonl [path ...] [-o life.txt]
```

`from-jsonl` も `from-json` と同じ `--canonical` option を受け付けます。

### 4.5 `to-csv`

life.txt を CSV に変換します。CSV は `status`、`type`、`title` と、選択された item に含まれる detail key の列を持ちます。同じ detail key の複数値はセル内 JSON 配列として保存します。複数行の `body:` は quoted CSV cell として保存します。

```sh
python -m lifetxt to-csv [path ...] [-o output.csv] [--occurrences] [filter options]
python -m lifetxt to-csv life.txt --type journal --project research -o journal.csv
```

`--occurrences` を指定すると、`to-csv` は安定した列 schema の agenda
occurrence CSV を出力します。列は `when`、`key`、`line`、`source_id`、
`occurrence_start`、`occurrence_end`、`occurrence_index`、`repeat_rule`、
`status`、`type`、`title`、`blocked`、`blocked_by`、`details`、`text` です。
この mode でも `--after` と `--before` が両方必要です。

### 4.6 `from-csv`

CSV を life.txt に戻します。CSV には `status`、`type`、`title` 列が必要です。それ以外の非空列は detail key として扱います。セルが JSON 配列の場合は、同じ key の複数値として読み込みます。

```sh
python -m lifetxt from-csv [path ...] [-o life.txt]
```

`from-csv` も `--canonical` を受け付けます。

### 4.7 `markdown`

選択した field の safe Markdown subset を描画します。この command はファイルを変更しません。raw の title / body / note を読み取り、HTML、plain text、JSON、JSONL として出力します。

```sh
python -m lifetxt markdown [path ...] [--field body] [--format html|text|json|jsonl]
python -m lifetxt markdown life.txt --field all --format json --pretty
python -m lifetxt markdown examples/markdown_life.txt --type journal -o body.html
```

| Option | 意味 |
|---|---|
| `path ...` | 入力 life.txt file、directory、glob、または stdin 用の `-` |
| `--field title|body|note|all` | 描画する field。複数回指定または comma-separated。既定は `body` |
| `--format html|text|json|jsonl` | 出力形式。既定は `html` |
| `-o`, `--output` | 出力 file。省略時は stdout |
| `--pretty` | JSON を整形して出力 |
| `filter options` | `filter` と同じ item filter |

JSON / JSONL record には `source`、`line`、`type`、`status`、`title`、
`field`、`index`、`raw`、`html`、`text` が含まれます。Markdown source 内の
raw HTML は escape され、`javascript:` のような unsafe link は link として描画しません。

### 4.8 export filter option

`to-json`、`to-jsonl`、`to-csv`、`markdown` は出力前に item を絞り込めます。

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
| `--occurrences` | `to-json`、`to-jsonl`、`to-csv` で、保存済み item ではなく bounded agenda occurrence を出力 |

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
python -m lifetxt to-json life.txt --occurrences --after 2026-06-01 --before 2026-06-30 --pretty
python -m lifetxt to-csv life.txt --occurrences --after 2026-06-01 --before 2026-06-30 -o occurrences.csv
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
- `RRULE` は `repeat:RRULE:...` として保持します。対応している subset は
  import 時ではなく、`agenda` と time filter で後から展開します。

例:

```sh
python -m lifetxt import-ics google_calendar.ics
python -m lifetxt import-ics google_calendar.ics -o imported_events.life.txt
python -m lifetxt import-ics google_calendar.ics -o life.txt --append --tag google
python -m lifetxt import-ics work.ics personal.ics --project calendar
```

出力例:

```txt
[ ] E "Research Meeting" id:event-1@example.com source:ics uid:event-1@example.com from:2026-06-08T13:00 to:2026-06-08T14:30 loc:"Meeting Room A" owner:"Prof. Smith" attendee:Alice tag:google
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

Current additions:

- `import-ics --preset markdown|todoist|github` can import Markdown task lists,
  Todoist CSV exports, and GitHub Issues JSON exports as `T` items.
- ICS-derived records now include `source:ics` and `uid:` metadata.
- `sync-ics --merge-existing --soft-delete-missing` preserves comments in the
  generated output, updates matching UID-backed records, and marks missing
  `source:ics` events as `[-] reason:missing_from_feed`.

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
| `--format table` | STATUS/TYPE/TITLE/PROJECT の table を出力 (`--width` 80 未満では compact な1行形式) |
| `--width N` | `--format table` の列幅 (文字数)。既定値 `0` は terminal width を自動検出 |
| `--limit N` | 出力する item を最大 N 件に制限 (`0` は無制限) |
| `-o`, `--output` | 出力ファイル。省略時は標準出力 |
| `--pretty` | JSON を整形して出力 |
| `--canonical` | 元行ではなく、明示的な `parent:` を使う unindented life.txt 行を再生成 |

filter option は 4.8 の export filter option と同じです。
`--format life` では、一致した item の元行を既定で保持します。
引用や空白を正規化したい場合は `--canonical` を使います。
階層も正規化したい場合は `--canonical` を使います。出力では indentation を使わず、推論済みまたは明示済みの `parent:` を detail として書きます。
terminal で素早く確認したい場合は `--format table` が便利です。`agenda` や
`stats` の table と同様、狭い terminal (または `--width 80` 未満) では
自動的に compact な1行形式に切り替わります。

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

## 8. `notify`

type `M` の通知対象を 1 回表示するか、`--watch` で常駐 polling します。

```sh
python -m lifetxt notify [path ...] [--recipient PERSON] [--watch]
python -m lifetxt notify life.txt --recipient self --email --email-to me@example.com --dry-run
python -m lifetxt notify life.txt --watch --email --email-to me@example.com --interval 60
```

選択ルール:

- type `M` の item だけを対象にします。
- open workflow status (`[ ]`、`[/]`、`[>]`、`[?]`) だけを対象にします。
- `recipient:` が選択 recipient と一致する必要があります。
- `notify_at:` は単一通知時刻として扱います。
- `notify_from:` / `notify_to:` は通知期間として扱います。
- `ack:` がある item は通知済みとして除外します。
- 未来の `snooze_until:` がある item は、その時刻まで抑止します。

| Option | 意味 |
|---|---|
| `path ...` | 入力 life.txt。`-` なら標準入力 |
| `--recipient PERSON` | 通知対象者。省略時は config の `notifications.recipient` または `user.name` |
| `--lookahead VALUE` | 未来方向の通知検出幅。例: `0m`、`5m`、`1h` |
| `--grace VALUE` | 過去方向の取りこぼし許容幅 |
| `--watch` | 終了せず繰り返し polling |
| `--interval SECONDS` | `--watch` の polling 秒数 |
| `--desktop` | 対応環境では簡易 desktop 通知も表示 |
| `--email` | 通知対象を plain text email としてまとめて送信 |
| `--email-to ADDRESS[,ADDRESS...]` | email 宛先。省略時は `notifications.email.to` |
| `--email-subject TEXT` | email subject のベース。省略時は `notifications.email.subject` |
| `--smtp-host-env ENVVAR` | SMTP host を格納する環境変数。省略時は `notifications.email.smtp_host_env` または `LIFETXT_SMTP_HOST` |
| `--smtp-user-env ENVVAR` | SMTP username を格納する環境変数。省略時は `notifications.email.smtp_user_env` または `LIFETXT_SMTP_USER` |
| `--smtp-pass-env ENVVAR` | SMTP password を格納する環境変数。省略時は `notifications.email.smtp_pass_env` または `LIFETXT_SMTP_PASS` |
| `--dry-run` | `--email` 時に SMTP 接続せず、送信予定本文を表示 |
| `--state-file PATH` | `--watch` の通知済み ID を保存する JSON file |
| `--no-state` | `--watch` で通知済み状態を保存しない |
| `--format text|json|jsonl` | one-shot mode の出力形式 |
| `--pretty` | JSON を整形して出力 |

例:

```sh
python -m lifetxt notify life.txt --recipient self
python -m lifetxt notify life.txt --recipient self --format json --pretty
python -m lifetxt notify life.txt --watch --interval 30
python -m lifetxt notify life.txt --email --email-to me@example.com --dry-run
```

email 通知は SMTP 認証情報を環境変数から読みます。life.txt 本文や config には
秘密情報を保存せず、必要に応じて `notifications.email.*` で環境変数名だけを
変更してください。

## 9. `agenda`

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
- `repeat:RRULE:...` は dependency-free subset として
  `FREQ=DAILY|WEEKLY|MONTHLY|YEARLY`、`INTERVAL`、`COUNT`、`UNTIL`、
  daily/weekly の `BYDAY` を展開します。
- `on:` のない floating `at:` repeat は、両端がある bounded agenda range の中だけで展開します。

### 9.1 範囲オプション

| Option | 意味 |
|---|---|
| `--from VALUE` | 範囲開始。`now`、`YYYY-MM-DD`、`YYYY-MM-DDTHH:MM` |
| `--to VALUE` | 範囲終了。`now`、`YYYY-MM-DD`、`YYYY-MM-DDTHH:MM` |
| `--after VALUE` | `agenda` では `--from` の alias。filter preset と共有するときに便利 |
| `--before VALUE` | `agenda` では `--to` の alias。filter preset と共有するときに便利 |
| `--around VALUE` | 範囲中心。省略時は `now` |
| `--window VALUE` | `--around` の半幅。省略時は `1h` |

`--from/--to`、`--after/--before`、または `--around` のいずれかを使います。
同じ command で `--from` と `--after`、または `--to` と `--before` は混在できません。
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
python -m lifetxt agenda life.txt --after 2026-06-06 --before 2026-06-06
python -m lifetxt agenda life.txt --from 2026-06-06T13:00 --to 2026-06-06T18:00
python -m lifetxt agenda life.txt --from 2026-06-06T13:00:30.25+09:00 --to 2026-06-06T18:00:00.5+09:00
python -m lifetxt agenda life.txt --around now --window 2h
python -m lifetxt agenda life.txt --around now --window 1w
python -m lifetxt agenda life.txt --from 2026-06-01 --to 2026-06-30 --type habit
```

### 9.2 フィルタオプション

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
| `--blocked [only|hide|all]` | dependency-blocked record を絞り込み。単独の `--blocked` は `--blocked only` と同じ |
| `--unblocked` | `--blocked hide` の後方互換 alias |

例:

```sh
python -m lifetxt agenda life.txt --from 2026-06-06 --to 2026-06-06 --open
python -m lifetxt agenda life.txt --from 2026-06-06 --to 2026-06-06 --status todo --type task
python -m lifetxt agenda life.txt --from 2026-06-06 --to 2026-06-06 --project research --tag urgent
python -m lifetxt agenda life.txt --from 2026-06-06 --to 2026-06-06 --assignee alice
python -m lifetxt agenda life.txt --from 2026-06-06 --to 2026-06-06 --detail priority=A --text report
python -m lifetxt agenda life.txt --from 2026-06-06 --to 2026-06-06 --person alice
python -m lifetxt agenda life.txt --from 2026-06-06 --to 2026-06-06 --blocked
python -m lifetxt agenda life.txt --from 2026-06-06 --to 2026-06-06 --blocked hide
```

`--detail key` は key の存在を確認します。`--detail key=value` は detail value の完全一致です。
複数の `--detail` は AND 条件です。

### 9.3 出力オプション

| Option | 意味 |
|---|---|
| `--format text` | 表で表示 |
| `--format life` | 一致した元の life.txt item 行を表示 |
| `--format json` | JSON 配列で表示 |
| `--format jsonl` | JSONL で表示 |
| `-o`, `--output` | 出力ファイル。省略時は標準出力 |
| `--pretty` | JSON を整形して出力 |
| `--width N` | text 出力を指定した terminal width 向けに整形 |

agenda の JSON / JSONL record は、open item が open な `depends_on:` または
`blocks:` 関係で block されている場合に `blocked: true` と `blocked_by` 配列を
含めます。repeat から生成された occurrence には、可能な場合 `source_id`、
`occurrence_start`、`occurrence_end`、`occurrence_index`、`repeat_rule` も含めます。
text 出力では短い `blocked` 列で同じ状態を表示します。`--format life` は保存されている元の item 行をそのまま出力します。

例:

```sh
python -m lifetxt agenda life.txt --from 2026-06-06 --to 2026-06-06 --format life
python -m lifetxt agenda life.txt --from 2026-06-06 --to 2026-06-06 --format json --pretty
python -m lifetxt agenda life.txt --around now --window 1w --format life -o agenda.life.txt
python -m lifetxt agenda life.txt --around now --window 1d --width 70
```

## 10. `assist`

フラグまたは対話入力で life.txt item を作成・更新します。

```sh
python -m lifetxt assist [options]
```

### 10.1 非対話で作成

```sh
python -m lifetxt assist --type task --title "Write Report" --due 2026-06-12 --project university
python -m lifetxt assist --type status --title "Working" --from 2026-06-06T14:00 --state busy --person self
python -m lifetxt assist --type message --title "Review Slides" --sender self --recipient alice --notify-at 2026-06-06T09:00
python -m lifetxt assist --type journal --title "Research day" --on 2026-06-23 --body-file notes.md
python -m lifetxt assist --type habit --title "Review" --rrule "FREQ=WEEKLY;BYDAY=MO;COUNT=4"
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
| `--body-file FILE` | UTF-8 text file から複数行 `body:` を読み込む |
| `--body-stdin` | 標準入力から複数行 `body:` を読み込む |
| `--rrule VALUE` | `repeat:RRULE:...` を設定する。`RRULE:` prefix は省略可能 |

known detail key には直接フラグもあります。各フラグは複数回指定できます。

```txt
--id --parent --ref --depends_on --blocks --related --created --updated --done --due --do --from --to
--state --user --person --owner --assignee --attendee --sender --recipient --team --group --service --channel
--visibility --notify_at --notify_from --notify_to --ack --snooze_until --on --at --repeat
--interval --until --count
--project --context --loc --priority --est --elapsed --tag --note --body --mood --weather --url
--reason --moved_to
```

underscore を含む detail key には hyphen alias も使えます。例:
`--notify-at`、`--notify-from`、`--snooze-until`。

### 10.2 対話で作成

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
| `body<<` | 複数行 `body:` 入力を開始。`.` だけの行で終了 |

対応 terminal では、Tab で type、status、detail-key 候補を補完できます。
Up/Down で入力履歴を呼び出せます。`--no-completion` で補完と line editing を無効化できます。

### 10.3 既存 item の更新

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

## 11. `serve`

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
| `--read-only` | `/api/check-line` 以外の write endpoint を無効化。公開用・常時表示用に便利 |
| `--mcp` | FastAPI HTTP server の代わりに stdio MCP server を起動 |

REST API は `/api/items`、`/api/agenda`、`/api/status`、`/api/health` を提供します。
詳細は [web.md](./web.md) を参照してください。

Browser GUI には header Workspace、中央の record modal、URL/config 由来の
view preset、Review filter と Markdown copy、設定可能な Dashboard card と
theme token、`Ctrl+K` fuzzy Command Palette、recently opened records、
undo history、browser notifications、Graph、display mode、kiosk mode があります。
複数 file を読み込む場合は `path ...` と `--write-file FILE` を併用すると、
generated/read-only file を表示しつつ、編集は hand-maintained file だけに限定できます。

### 11.1 `mcp`

MCP-compatible AI client から life.txt を操作するための JSON-RPC stdio server を起動します。
core package だけで動作し、FastAPI / uvicorn は不要です。

```sh
python -m lifetxt mcp life.txt
python -m lifetxt mcp life.txt .generated/google_calendar.life.txt --write-file life.txt
python -m lifetxt serve life.txt --mcp
python -m lifetxt mcp "projects/**/*.life.txt" --write-file life.txt --read-only
```

主な tool は `list_items`、`get_item`、`check_line`、`parse_item`、
`create_item`、`update_item`、`mark_done`、`delete_item`、`get_agenda`、
`get_review`(`review --format json` / `GET /api/review` と同形の週次・月次
review report)、`get_graph`、`get_blockers`、`list_links`、`list_status`、
`list_notifications`、および type `M` message 操作です。複数 file を読み込んだ場合、read tool は全 file を走査し、
write tool は `--write-file` のみを変更します。`--read-only` を付けると write tool を無効化します。

## 12. `config`

外部 JSON config を作成または表示します。

```sh
python -m lifetxt config init -o .lifetxt.json
python -m lifetxt --config .lifetxt.json config show
```

| Option | 意味 |
|---|---|
| `config init -o FILE` | starter config を FILE に作成。省略時は `.lifetxt.json` |
| `config init --force` | 既存 config file を上書き |
| `config show` | 読み込まれた config を JSON として表示 |

主な config key:

| Key | 意味 |
|---|---|
| `paths` | life.txt 読み込み系 command の default input files |
| `write_file` | `serve` の default writable file |
| `user.name` | 自身の標準ユーザ名 |
| `users`, `teams`, `tags` | user alias、team membership、tag alias/group |
| `message.default_sender` | type `M` 作成時の default `sender:` |
| `timer.state_file` | `timer` の常駐状態を保存する JSON ファイル |
| `tui.*` | TUI の既定値。`theme`、`keymap`、`limit`、`agenda_window` |
| `notifications.*` | `notify` と Web 通知の既定値 |
| `ids.auto`, `ids.key`, `ids.prefixes` | 自動IDと ID key の設定 |
| `api.id_key` | Web API / id-based operation が使う ID key |
| `web.*` | `serve` と Web UI の既定値。`web.theme.*` と `web.dashboard.*` で見た目と Dashboard を調整 |
| `sync_ics.*` | `sync-ics` の default source / output / cache |

top-level `generated_paths` または `sync_ics.generated_paths` に含まれる file は、
通常の変更系 command (`assist`, `done`, `archive`, `assign`, `tag`, `batch`,
`migrate`, `encrypt`, `decrypt`) では generated/read-only として扱われ、
変更を拒否します。`sync-ics` は generated file を出力するための例外ですが、
OS 上で read-only の file は拒否します。

### 12.1 設定値の解決順序

同じ設定項目(例: `self` として使う名前や、`quick` で新規項目に付与する
project)は、最大4つのレベルで指定できます。複数レベルで値が指定された場合、
lifetxt は優先度の高い順に次のように解決します。

1. **CLI フラグ** — 実行するコマンドに直接渡すフラグ。
   例: `lifetxt quick "牛乳を買う" --project errands`、
   `lifetxt agenda --person alice`
2. **Config JSON の defaults** — 読み込んだ `.lifetxt.json` の `defaults`
   (および `user`、`message` など関連セクション)の値。
   例: `"defaults": {"person": "self", "timezone": "Asia/Tokyo"}`
3. **`#!` file-level directive** — life.txt file 先頭の directive 行。
   例: `#! self: alice`、`#! project: research`、`#! timezone: UTC`。
   その file 内でのみ有効です。
4. **組み込みの既定値** — 他のどのレベルにも値がない場合に使われる
   ハードコードされた fallback。例: person `"self"`、timezone `"UTC"`。

例: life.txt file 先頭が `#! project: research` でも、
`lifetxt quick "アウトライン作成" --project writing` を実行すると、
CLI フラグが優先されるため item は `writing` に分類されます。
`--project` を省略し、config file に `"defaults": {"project": "misc"}` が
あり file 側に `#! project:` directive が無い場合は `misc` に分類されます。
上位3レベルのいずれにも project の指定が無ければ、その item に project は
付きません。

`lifetxt config init` は config file 書き込み後にこの解決順序を
リマインダーとして表示します。`lifetxt init` は starter life.txt
(`#! self:` / `#! timezone:` / `#! project:` directive 付き)と対応する
`.lifetxt.json` (`defaults.person` / `defaults.timezone` 付き)を同時に
作成するため、新規ユーザーは3つの設定レベルを並べて確認できます。

## 13. CUI 拡張

### 13.1 `tui`

`tui` は未完了 task、現在時刻付近の agenda、active な `S` status を端末上で表示する dashboard です。

```sh
python -m lifetxt tui [path ...]
python -m lifetxt tui life.txt --theme dark --keymap vim --limit 15
python -m lifetxt tui life.txt --theme light --keymap arrows --agenda-window 1d
```

`textual` が利用可能な場合は最小限の Textual UI を使い、未導入の場合は依存なしの端末表示に fallback します。
`?` または `H` で help を表示します。`--theme auto|dark|light|mono` で curses 色を指定し、
`--keymap vim|arrows` で help/footer の keymap preset を指定できます。既定値は config の
`tui.theme`、`tui.keymap`、`tui.limit`、`tui.agenda_window` でも設定できます。

選択行は `*` で表示されます。既定 keymap は Vim 風です。
`h` / `l` または Left/Right で section focus 移動、`j` / `k` または
Down/Up で選択行移動、`Ctrl-D` / `Ctrl-U` と PageDown/PageUp で半ページ移動、
`g` で先頭、`G` で末尾、`r` で reload、`q` で終了します。
`Enter` / `o` で選択行の action menu を開きます。`s` は詳細表示、`d` は `id:` と source を持つ
task-like 行の完了、`e` は `$EDITOR` で source を開く、`f` は選択行の最初の `project:` で filter します。
`Tab` / `n` と `p` も非 Vim 風の section 移動 alias として使えます。
curses の色表示が利用できる場合は、focus section、選択行、active task、完了 item、
status 行、error、footer を色付きで表示します。plain text fallback は色なしのままです。
入力 file が変更されると自動 reload します。`watchdog` が利用可能な場合は file event を使い、
未導入の場合は mtime を定期確認する fallback で動作します。

### 13.2 `fzf`

`fzf` は通常の item filter を適用した後、`fzf` または `peco` で item を選択し、action を実行します。

```sh
python -m lifetxt fzf life.txt --open --type task --action done
python -m lifetxt fzf life.txt --project research --action show
python -m lifetxt fzf "projects/**/*.life.txt" --tool peco --action edit
```

| Option | 意味 |
|---|---|
| `--action done|edit|delete|show` | 選択 item に実行する action。省略時は prompt |
| `--tool fzf|peco` | 選択 tool。既定では `fzf`、次に `peco` を探索 |
| `--preview` / `--no-preview` | `fzf` preview の有効/無効 |
| `--print-query` | `fzf` の query 行だけを出力 |

`done` と `delete` は item ID を必要とします。必要なら先に `ids --assign` で ID を付与してください。
`delete` は source file、line、title を表示したうえで `DELETE` の入力を要求します。
`fzf` preview では source location、複数行 `body:`、生成された life.txt 行を表示します。

### 13.3 `timer`

`timer` は 1 つの running timer を JSON state file に保存し、停止時に合計時間を `elapsed:` として item に書き戻します。

```sh
python -m lifetxt timer start life.txt --id task_report
python -m lifetxt timer status life.txt
python -m lifetxt timer pause
python -m lifetxt timer resume
python -m lifetxt timer stop
python -m lifetxt timer summary life.txt --project research
```

| Subcommand | 意味 |
|---|---|
| `start path --id ID` | `id:ID` の item の計測を開始。`[ ]` は `[/]` に変更 |
| `pause` | item は変更せず、単一の running timer を一時停止 |
| `resume` | 一時停止中の timer を再開 |
| `stop [path] [--id ID]` | running timer を停止し `elapsed:` を更新 |
| `status [path ...]` | running timer と経過時間を表示 |
| `summary path ...` | `elapsed:` を item / project ごとに集計 |
| `cancel` | item を変更せず state file だけ削除 |

同時に動かせる timer は 1 つだけです。`pause` は累積分数を state file に保存し、
`stop` は timer が一時停止中でも累積合計を item に書き戻します。`elapsed:` は
`25m`、`1h`、`1h30m` のように記録されます。state file の既定値は
`~/.lifetxt_timer.json` で、config の `timer.state_file` で変更できます。

### 13.4 `stats`

`stats` は task 完了率、期限超過、habit streak、mood、project 別進捗を表示します。

```sh
python -m lifetxt stats life.txt
python -m lifetxt stats life.txt --from 2026-06-01 --to 2026-06-30
python -m lifetxt stats life.txt --project research --format json
python -m lifetxt stats life.txt --tag focus --assignee alice --format json
python -m lifetxt stats "projects/**/*.life.txt" --group weekly
python -m lifetxt stats life.txt --width 60
```

| Option | 意味 |
|---|---|
| `--from DATE` | 開始日。省略時は `--to` の 29 日前 |
| `--to DATE` | 終了日。省略時は今日 |
| `filter options` | `filter` と同じ item filter。status、type、project、tag、user、team、people、detail、text、time filter を含む |
| `--group daily|weekly|monthly` | mood trend の集計単位 |
| `--format text|json` | 出力形式 |
| `--width N` | 狭い terminal 向けの compact text 出力 |

`weekly` / `monthly` では task bucket ごとの done / total / overdue と、
bucket ごとの habit sparkline も表示します。

### 13.5 report / chart / batch / encryption

`review` は JSON、JSONL、Markdown、単体 HTML report を出力できます。

```sh
python -m lifetxt review life.txt --week --format html > weekly_review.html
```

`plot` は既定では terminal bar chart を表示します。`--format svg` は追加依存なし、
`--format png` は `matplotlib` がある場合に利用できます。

```sh
python -m lifetxt plot life.txt --chart deadlines --from 2026-06-01 --to 2026-06-30
python -m lifetxt plot life.txt --chart tasks --format svg -o tasks.svg
python -m lifetxt plot life.txt --chart habits --format png -o habits.png
```

`export-heatmap` は task / habit activity を SVG heatmap として出力します。

```sh
python -m lifetxt export-heatmap life.txt --from 2026-01-01 --to 2026-12-31 -o activity.svg
python -m lifetxt export-heatmap "projects/**/*.life.txt" --type habit --project research -o habits.svg
```

`batch` は複数ファイルに対して既存の `done` / `assign` 処理を反復実行します。

```sh
python -m lifetxt batch done "projects/**/*.life.txt" --id task_report
python -m lifetxt batch assign life.txt team_life.txt --text Review --to alice --dry-run
```

`encrypt` / `decrypt` は環境変数または UTF-8 text file から passphrase を読み取れます。

```sh
python -m lifetxt encrypt life.txt --field body --type journal --key-file .secrets/lifetxt.key
python -m lifetxt decrypt life.txt --field body --key-file .secrets/lifetxt.key
```

`inbox --fzf` は未分類 inbox item を `fzf` または `peco` に渡し、選択された行を出力します。

### 13.6 `git-hook`

`git-hook` は現在の repository に local Git hook を導入します。生成される `pre-commit`
hook は `lifetxt check` を実行し、`commit-msg` hook は利用可能な場合に完了 task の要約を commit message に追記します。

```sh
python -m lifetxt git-hook status
python -m lifetxt git-hook install --files life.txt examples/*.txt
python -m lifetxt git-hook uninstall
```

既存の非 lifetxt hook は `--force` なしでは上書きしません。検証だけが必要なら `--no-commit-msg` を指定します。

### 13.7 `completion`

`completion` は shell completion script を生成します。

```sh
python -m lifetxt completion bash
python -m lifetxt completion zsh -o ~/.zfunc/_lifetxt
python -m lifetxt completion fish -o ~/.config/fish/completions/lifetxt.fish
python -m lifetxt completion install --shell bash
```

`completion install` は導入手順を表示するだけで、shell startup file は自動変更しません。

### 13.8 `deps`

`deps` は宣言済みまたは未解決の dependency chain を indented tree として表示します。
`agenda` や `health` と同じ blocker semantics を使い、`depends_on:` target は現在の
item を block し、`blocks:ID` を持つ item は target `ID` を block します。

```sh
python -m lifetxt deps life.txt
python -m lifetxt deps life.txt --blocked
python -m lifetxt deps life.txt --root task_report
python -m lifetxt deps life.txt --root task_report --format json --pretty
python -m lifetxt deps life.txt --root task_report --format mermaid --depth 2
python -m lifetxt deps life.txt --blocked --format dot
```

| Option | 意味 |
|---|---|
| `--blocked` | open blocker を持つ open item のみ表示 |
| `--root ID` | 1つの item ID から blocker chain を辿る |
| `--format text|json|mermaid|dot` | 出力形式 |
| `--depth N` | 表示する dependency depth の上限。`0` は root のみ |
| `--pretty` | JSON を整形して出力 |

## 14. alias

status alias:

| Alias | Status |
|---|---|
| `todo`, `open`, `not_completed`, `queued`, `scheduled` | `[ ]` |
| `progress`, `doing`, `in_progress`, `active`, `sending` | `[/]` |
| `done`, `complete`, `completed`, `sent`, `delivered` | `[x]` |
| `cancel`, `canceled`, `cancelled` | `[-]` |
| `defer`, `deferred`, `moved` | `[>]` |
| `pending`, `unknown` | `[?]` |
| `note`, `n` | `[N]` |
| `x`, `/`, `-`, `>`, `?` | 対応する記号 status |

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
| `message`, `msg`, `mail`, `notification` | `M` |
| `journal`, `diary`, `log`, `entry` | `J` |

## 15. 実用例

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

## 16. `init` と `doctor`

この2つの command は新規ユーザー向けの推奨エントリーポイントです。

```sh
python -m lifetxt init
python -m lifetxt init --yes
python -m lifetxt doctor
```

`init` は starter life.txt と対応する `.lifetxt.json` を作成します。

| Option | 意味 |
|---|---|
| `--file PATH` | 作成する life.txt file。省略時は `life.txt` |
| `--config-output PATH` | 作成する config file。省略時は `.lifetxt.json` |
| `--force` | 確認なしで既存 file を上書き |
| `--name NAME` | 自分の名前。`#! self:` と `defaults.person` に書き込まれる |
| `--timezone TZ` | timezone。`#! timezone:` と `defaults.timezone` に書き込まれる |
| `--project NAME` | default project。`#! project:` と `defaults.project` に書き込まれる |
| `--yes` | すべて既定値 (`self`、`UTC`、project なし) で非対話実行。`--force` と併用した場合の上書き確認プロンプトも省略される。script や CI 向け |

`--yes` を付けない場合、`init` は名前・timezone・default project を尋ね、
既存の `life.txt` や config file を上書きする前に確認します
(`--force` 指定時を除く)。`--yes` を付けると3つのプロンプトはすべて
スキップされ、`--name`/`--timezone`/`--project` で指定されなかった値は
組み込みの既定値になります。

`doctor` は pass/warn/fail の check を表示し、file は一切変更しません。

| Check | 検査内容 |
|---|---|
| `python` | Python 3.10+ (未満は FAIL) |
| `life.txt` | 設定または既定の life.txt file が存在し読み取り可能か |
| `config` | `.lifetxt.json` (または `--config` の path) が存在するか (無ければ WARN) |
| `fzf`, `peco` | optional selector tool が `PATH` にあるか (無ければ WARN) |
| `textual`, `watchdog`, `matplotlib`, `cryptography` | optional Python package が導入済みか (無ければ WARN) |
| `check` | life.txt file を解析し error/warning 件数を報告 |
| `ids` | `id:` が無い item を報告 |

`doctor` は `FAIL` レベルの check がある場合のみ非ゼロで終了します
(Python version が古い、または file が存在しない/読み取れない場合)。
optional dependency の不足は `WARN` であり、終了コードには影響しません。
機械可読な出力には `--format json` を使用してください。

## 17. `encrypt` と `decrypt`

標準ライブラリのみを使った field 単位の暗号化 (journal の body、message の
本文など機密性の高い値向け)。追加 dependency は不要です。

```sh
LIFETXT_KEY="correct horse battery staple" python -m lifetxt encrypt life.txt --field body --type J
LIFETXT_KEY="correct horse battery staple" python -m lifetxt decrypt life.txt --field body
```

**アルゴリズム。** 値は in-place で `enc:XSK:BASE64` の形式にタグ付けされます
(例: `body:"enc:XSK:AbCd..."`)。XSK ("XOR stream cipher, keyed") は
PBKDF2-HMAC-SHA256 (100,000 iteration) と値ごとにランダムな 16 byte の
salt から 32 byte の key を導出し、SHA-256 の繰り返し
(`SHA256(key ‖ counter)`) で keystream を生成して UTF-8 平文と XOR します。
`salt ‖ ciphertext` に対する HMAC-SHA256 (同じ導出 key を使用) を先頭に
付与して整合性を保証しており、MAC が一致しない値は `decrypt` が復号を
拒否します ("wrong passphrase or tampered data")。そのため passphrase の
typo は文字化けではなく明確なエラーになります。これは `hashlib`/`hmac`/
`secrets` のみで組んだ独自実装であり、リポジトリを信頼している前提での
私的な journal など「カジュアルにローカルの秘密を隠す」用途には十分ですが、
監査は受けておらず、レビュー済みの暗号 library の代替にはなりません。

**Passphrase の強度。** key は passphrase のみから導出されるため、
passphrase の強度がデータを守る唯一の要素です。辞書に載っている単語では
なく、長く一意な passphrase (複数単語のフレーズや password manager の
出力) を使ってください。passphrase 自体を repository に commit しては
いけません。

**Key の管理方法。**

| 方法 | Flag | 備考 |
|---|---|---|
| 環境変数 | `--key-env NAME` (既定 `LIFETXT_KEY`) | ローカル shell や CI の secret に便利。shell の history に残さないよう注意 |
| Key file | `--key-file PATH` | `--key-env` より優先。file は repository の外に置くか `.gitignore` に追加する |

**Rotation workflow。** passphrase を rotate するには、影響するすべての
file を古い passphrase で `decrypt` し、新しい passphrase で再度
`encrypt` してから古い passphrase を破棄します。in-place の re-key
操作は無いため、rotation 中は両方の passphrase が必要です。

**部分的に暗号化された file の check。** `check` と `filter` は
`enc:XSK:...` の値を不透明な文字列として扱い、復号を試みません。
そのため暗号化済みの値と平文の値が混在する file でも、構文検証や他 field
による filter は通常どおり動作します。暗号化された field の平文内容で
filter するには、事前に復号する必要があります。

**Upgrade path。** optional package の `cryptography` が導入されていれば
(`pip install cryptography`)、組み込みの XSK 方式の代わりに標準的で
レビュー済みの AES-GCM 実装を検討してください。`doctor` は
`cryptography` の有無を報告します。ただし `encrypt`/`decrypt` は現時点で
自動検出して使用することはありません — これは今後の方向性であり、
現在の挙動ではありません。

Current encryption and watch additions:

```sh
python -m lifetxt batch tag-rename "projects/**/*.life.txt" --old inbox --new triage --dry-run
python -m lifetxt batch tag-merge team.life.txt archive.life.txt --old urgent_old --new urgent
python -m lifetxt batch migrate "projects/**/*.life.txt" --migration normalize-status --backup
python -m lifetxt watch life.txt --run agenda --timestamp
python -m lifetxt watch life.txt --run "agenda --around now --window 2h" --notify
python -m lifetxt encrypt life.txt --field body --algorithm aesgcm --key-file .secrets/lifetxt.key
```

`batch` now supports `done`, `assign`, `tag-rename`, `tag-merge`, and
`migrate`. `watch --timestamp` prints run headers, and `watch --notify`
notifies when the child command exit status changes. `encrypt --algorithm
aesgcm` uses the optional `cryptography` package and writes `enc:GCM:` values;
`decrypt` auto-detects both `enc:XSK:` and `enc:GCM:`.

## 18. `share`、`digest`、`template`

### `share`

server を起動せずに、filter した item・bar chart・table をまとめた
自己完結型の HTML または Markdown report を出力します。

```sh
python -m lifetxt share life.txt --open --type task -o open_tasks.html
python -m lifetxt share life.txt --week --format markdown -o weekly.md
python -m lifetxt share life.txt --project research --title "Research report"
```

`share` は `filter`/`agenda` と同じ filter option (2章参照) に加え、
以下を受け付けます。

| Option | 意味 |
|---|---|
| `--week` | report の見出しに現在の ISO week (月曜日〜今日) を表示 |
| `--month YYYY-MM` | report の見出しに特定の calendar month を表示 |
| `--format html\|markdown` | 出力形式。省略時は `html` |
| `-o, --output PATH` | 出力先 file。省略時は `share.html` または `share.md` |
| `--title TEXT` | report title。省略時は "lifetxt share report" |

`--week`/`--month` は report 見出しの表示のみを変更します。日付で
含める item を絞り込みたい場合は `--after`/`--before` を併用してください。
HTML 出力は外部依存が無く (inline CSS、inline SVG chart)、ブラウザで
直接開いたり email に添付したりできます。

### `digest`

`review` 相当の期間サマリーを Slack、email、または local file へ配信します。

```sh
python -m lifetxt digest life.txt --week --format slack-webhook --url-env SLACK_WEBHOOK_URL
python -m lifetxt digest life.txt --month 2026-06 --format email --to team@example.com
python -m lifetxt digest life.txt --week --format file --path digest-log.md
```

| Option | 意味 |
|---|---|
| `--week` / `--month YYYY-MM` | `review` と同じ期間選択 |
| `--project NAME` | 特定 project に限定 |
| `--format slack-webhook\|email\|file` | 配信 channel (必須) |
| `--url-env ENVVAR` | Slack incoming webhook URL を格納した環境変数 (`slack-webhook`) |
| `--to ADDRESS` | 送信先 email address (`email`) |
| `--smtp-host-env`, `--smtp-user-env`, `--smtp-pass-env` | SMTP host/username/password を格納した環境変数 (`email`)。既定は `LIFETXT_SMTP_HOST`/`_USER`/`_PASS` |
| `--path PATH` | Markdown を追記する local file (`file`) |
| `--dry-run` | message を組み立てて表示するのみで、network request も書き込みも行わない |

各 channel は、network request や書き込みを行う **前に** 必要な環境変数
(または `--to`/`--path`) を検証します。そのため secret が不足している
場合は配信途中でなく即座に明確なエラーで失敗します。

### `template`

config `templates` に定義した再利用可能な named item template を
list / apply します。

```sh
python -m lifetxt template list
python -m lifetxt template apply weekly_review --append life.txt
python -m lifetxt template apply weekly_review --append life.txt --dry-run
```

`.lifetxt.json` で template を定義します。

```json
{
  "templates": {
    "weekly_review": {
      "lines": [
        "[ ] T Weekly_Review due:{next_monday} project:reflection",
        "[ ] T Plan_Next_Week due:{next_monday} project:reflection"
      ]
    }
  }
}
```

日付 placeholder は template 定義時ではなく apply 実行時に解決されます:
`{today}`、`{next_monday}` (直近の未来の月曜日)、`{next_week}`
(今日 + 7日)。`H` habit と異なり、template の内容は自動で
再スケジュールされません — `apply` を再実行すると、新しく解決された
日付で同じ行がもう一度追記されます。
