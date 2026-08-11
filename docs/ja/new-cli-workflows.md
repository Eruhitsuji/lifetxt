# New CLI Workflows

この guide は 2026-07-20 roadmap implementation batch で追加された workflow commands を扱います。すべての commands は既存 CLI と同じように `--config FILE` を受け付けます。file-reading commands は paths が省略された場合、configured `paths` または `life.txt` を default にします。

## Actionable work

```sh
lifetxt next life.txt
lifetxt next life.txt --project research --limit 10
lifetxt next life.txt --format json
lifetxt next life.txt --rank
```

`next` は open な Task、Deferred、Recurring、Habit records から、`someday`、`maybe`、`waiting` tags が付いておらず、unfinished または unresolvable な `depends_on` reference に block されていないものを選びます。TUI `/next` view と MCP `get_next_actions` tool と同じ definition です。blocking は command に渡されたすべての files を横断して解決されるため、別 file にある dependency でも item は parked されます。results は priority、due date、age で ordered されます。

`--rank` を追加すると overdue items を priority より先に置きます。ties は通常の priority、due date、age ordering に戻ります。`--rank` なしの output は変わりません。

`--rank` は selected item の `due` value が valid date であることを要求します。`due:not-a-date` のように parse できない value がある場合、silent に no due date 扱いせず item 名を含む error で失敗します。`--rank` なしの `next` は従来通り unparseable `due` を許容します。

## Inspect and edit one item

```sh
lifetxt show task_report life.txt
lifetxt show task_report life.txt --format json
lifetxt edit task_report life.txt --editor "code --wait"
lifetxt edit task_report life.txt --dry-run
```

`show` は source location、hierarchy context、incoming references を含めます。`edit` は `--editor`、top-level `editor` config key、`VISUAL`、`EDITOR` の順に editor を解決します。

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
