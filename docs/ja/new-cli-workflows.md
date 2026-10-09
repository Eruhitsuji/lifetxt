# New CLI Workflows

この guide は 2026-07-20 roadmap implementation batch で追加された workflow commands を扱います。すべての commands は既存 CLI と同じように `--config FILE` を受け付けます。file-reading commands は paths が省略された場合、configured `paths` または `life.txt` を default にします。

## Actionable work

### 次の1件だけを取得（読み取り専用）

```sh
lifetxt next life.txt --one
lifetxt next life.txt --one --json
lifetxt next life.txt --one --rank --project research
# 作業後、返されたレコードの id を明示して完了する:
lifetxt done task_report life.txt
lifetxt next life.txt --one
```

`--one` は先頭1件を完全な正規life.txtレコードとして出力し、表の見出しや
説明を付けません。`--json`（`--one` 専用）、または `--one --format json` は
`{"item":"[ ] T Report id:task_report","source":"/path/life.txt","line":1}`
を返します。`item` は完全な `id:` を含む正規レコード文字列です。
`source` と1始まりの `line` により、IDがないレコードも特定できます。
標準入力（`-`）の `source` は `-` です。`--pretty` はJSONの整形のみ行います。

候補がない場合はテキストが空、JSONが `null` となり、終了コードは **0** です。
入力や設定の不正・読み取り失敗は終了コード **1** のエラーとなり、候補なしとは
区別されます。不正なオプションの組合せは **2** です。`--one` は `--limit`、
`--why`、`-o`/`--output` と併用できません。元ファイル、設定、タイムスタンプ、
メタデータ、アーカイブ、出力ファイルへの書き込みは行いません。

入力パス、設定済み・既定のworkspace、`--user`、`--project`、`--context`、
タイムゾーン解決は既存の `next` と共通です。選択された入力だけを読み、
workspaceのアーカイブや別workspaceを暗黙に追加しません。明示的に指定した
パスはその指定通りに扱います。

候補判定・同順位の処理は既存CLIの `command_next` をそのまま利用します。
全入力間の依存関係を解決し、priority、due、created、元の行番号で並べます。
それでも同順位なら入力順を維持します。`--rank` は解決済みタイムゾーンで
既存の期限超過優先 `_rank_key` を利用します。時間配置を行う機能ではなく、
未来の日付を持つレコードも既存ルールに従って候補になります。
`today` の `next_actions` は `nextaction.next_action_items` を使い、priorityの
別名やdue/do/行番号の順序が異なります。Daily Flowは `_rank_key` に加え、
見積り・ID・開始可能時刻・空き時間を確認します。これらを混ぜずCLIの判定を
維持します。通常の `next` は従来の複数件の表、`--one` なしの
`--format json` は従来の配列を返します。

### 従来の候補一覧

```sh
lifetxt next life.txt
lifetxt next life.txt --project research --limit 10
lifetxt next life.txt --format json
lifetxt next life.txt --rank
lifetxt next life.txt --why
```

`next` は open な Task、Deferred、Recurring、Habit records から、`someday`、`maybe`、`waiting` tags が付いておらず、unfinished または unresolvable な `depends_on` reference に block されていないものを選びます。TUI `/next` view と MCP `get_next_actions` tool と同じ definition です。blocking は command に渡されたすべての files を横断して解決されるため、別 file にある dependency でも item は parked されます。results は priority、due date、age で ordered されます。

`--rank` を追加すると overdue items を priority より先に置きます。ties は通常の priority、due date、age ordering に戻ります。`--rank` なしの output は変わりません。

`--rank` は selected item の `due` value が valid date であることを要求します。`due:not-a-date` のように parse できない value がある場合、silent に no due date 扱いせず item 名を含む error で失敗します。`--rank` なしの `next` は従来通り unparseable `due` を許容します。

`--why` を追加すると、返された各itemについて、actionableなstatus/type、
parked tagとdependencyの確認結果、および結果順に使ったordering fieldを表示します。
JSON outputでは各itemに `why` object が追加され、text/life outputでは人向けの
`Why:` 行が追加されます。`--why` なしの出力は変わりません。

`next` の default（table）output は `ID` 列に完全な `id:` value ではなく
**Short ID** を表示します -- loaded workspace 内の全 `id:` の中で、その item を
一意に識別できる最短の prefix（最低6文字）です。呼び出しのたびに derive される
だけで別の short-ID registry は存在せず、常に同じ item へ解決されることが
保証されています: `done`、`start`、`complete`、`assist --update --match-id`
（いずれも一意な ID prefix を受け付けます。[cli.md](cli.md#103-既存-item-の更新)
参照）にそのまま渡せます。`--format json`/`--format life` は影響を受けず、
常に完全な `id:` value を表示します。

CLI・TUI・Web の human-readable な date field には、`due:2026-09-07 (in 2 days)`
や `done:2026-09-04 (yesterday)` のような relative label が補助表示されます。
canonical な保存値と machine-readable output は変更されません。

## Recently changed items

```sh
lifetxt recent life.txt
lifetxt recent life.txt --updated
lifetxt recent life.txt --created
lifetxt recent life.txt --limit 10
lifetxt recent life.txt --format json
```

`recent` は、最近作成・更新された item を newest-first で表示する
read-only な view です -- 新しい indexing/cache subsystem ではなく、既存の
parsing、short ID、relative-time 表示を薄く組み合わせたものです。
default では `updated:` を基準にし、`updated:` を持たない item は
`created:` に fallback します。`--updated`/`--created` はどちらか一方の
基準を明示的に選択し、fallback なしになります —— その detail を持たない
item は推測せず除外されます。選択した基準の下でタイムスタンプを全く
持たない item や、parse できない item は、command を crash させず
silent に除外されます。

`--limit N` は行数を制限します（default 20、正の整数のみ）。text output
では `next`（上記参照）と同じ short unique ID に加えて relative-time
label（`today`、`2 days ago` など）を表示します。`--format json` は
代わりに各 item の完全な `id:` と、実際に使われた raw な絶対タイムスタンプ
を保持します —— locale に依存する表示用文字列ではありません。

## Inspect and edit one item

```sh
lifetxt show task_report life.txt
lifetxt show task_report life.txt --format json
lifetxt edit task_report life.txt --editor "code --wait"
lifetxt edit task_report life.txt --dry-run
```

`show` は source location、hierarchy context、incoming references を含めます。`edit` は `--editor`、top-level `editor` config key、`VISUAL`、`EDITOR` の順に editor を解決します。

### Historical item inspection (#726/#729)

```sh
lifetxt show task_report life.txt --revision a1b2c3d
lifetxt show task_report life.txt --as-of 2026-09-01T12:00:00+09:00 --ref main
```

`--revision`/`--as-of` は共有の
[Git historical evidence contract](git-historical-evidence-contract.md) を
再利用し、その commit 時点に存在した item をそのまま表示します。current
working tree は決して混入しません。選択した revision にその item が存在
しない場合、`show` は current item へフォールバックせず失敗します。
`--revision` と `--as-of` は互いに排他で、`--ref`（既定 `HEAD`）は `--as-of`
と併用する場合のみ有効です。selector を指定しない `show` は無変更です。

## Resolved paths

```sh
lifetxt path
lifetxt path --format json
```

`path` は loaded config、input files、write target、timer state、notification state、cache directory を report します。

## Review selectors and stale someday items

```sh
lifetxt review life.txt --last-week
lifetxt review life.txt --last-month
lifetxt review life.txt --year
lifetxt review life.txt --year 2025
lifetxt review life.txt --someday --older-than 90
```

year selector は current calendar year を default にします。convenience selectors は `--week`、`--month`、`--from`、`--to` と mutually exclusive です。

## Aggregation and team workload

```sh
lifetxt count life.txt --by status
lifetxt count life.txt --by project --format csv
lifetxt who life.txt --workload --due-soon 7
```

`count` は `status`、`type`、`tag`、`person`、`project`、`context`、`assignee` を support します。workload output は open、in-progress、due-soon、overdue work を assignee または owner ごとに group します。

## Standup and invoice reports

```sh
lifetxt standup life.txt --user self
lifetxt standup life.txt --format markdown
lifetxt invoice life.txt --from 2026-07-01 --to 2026-07-31 --rate 5000 --currency JPY
lifetxt invoice life.txt --rate research=6000 --rate consulting=8000 --round 15 --format csv
```

`standup` は yesterday に completed した work、today の planned work、blocked tasks を report します。`invoice` は project ごとの `elapsed:` を total し、optional project-specific rates と minute rounding を適用し、text、Markdown、CSV、JSON を出力します。

## Attachments

```sh
lifetxt files life.txt --open task_report --dry-run
lifetxt files life.txt --open task_report
lifetxt files life.txt --open task_report --allow-outside
```

opener は recorded `file:` と `dir:` targets だけを受け付けます。URLs、executable extensions、source file directory の外の paths は、明示的に許可しない限り reject されます。他人から受け取った data を open する前に `--dry-run` を使ってください。

## Calendar and text interchange

```sh
lifetxt to-ics life.txt -o calendar.ics
lifetxt from-todo todo.txt -o imported.life.txt
lifetxt import-ics todo.txt --preset todo -o imported.life.txt
lifetxt from-markdown issues.md --preset github -o issues.life.txt
```

`to-ics` は all-day/timed event records、timezone offsets、attendees、recurrence、stable UID metadata を export します。todo.txt importer は completion、priority、projects、contexts、dates を map します。GitHub Markdown preset は task-list state、issue references、assignee mentions、nested task relationships を map します。

## Journal capture

```sh
lifetxt quick --journal --append life.txt
lifetxt quick --journal --title "Research notes" --mood focused --project thesis
lifetxt quick --journal --body-file notes.md --date 2026-07-20 --dry-run
```

editor flow は temporary Markdown file を開き、non-empty content が保存された場合だけ `J` record を append します。write 自体は existing validated quick-capture path を通ります。

## PowerShell completion

```powershell
lifetxt completion powershell -o $HOME\Documents\PowerShell\lifetxt-completion.ps1
. $HOME\Documents\PowerShell\lifetxt-completion.ps1
```

native command-name completion を有効にするには、dot-source line を PowerShell profile に追加します。

## CI-like local testing

push 前には repository helper を使います。

```sh
python scripts/run_ci_like.py
python scripts/run_ci_like.py --python python3.12 --no-web
python scripts/run_ci_like.py --skip-smoke
```

launcher commands は明示的に渡してください。Windows では `--python "py -3.12"`、Unix-like systems では `--python python3.12` などです。各 selected interpreter は clean virtual environment で実行されます。
