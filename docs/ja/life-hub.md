# Life Hub: Daily Command Center, Areas, Backlinks, Temporal Context

Life Hub commands は life.txt workspace を、今日 attention が必要なもの、area ごとの work organization、items 同士の connection、時間的な relation を見る command center にします。すべての command は shared aggregation を読むため、CLI、MCP、future Web surfaces が同じ picture を見ます。

## Daily command center

`today` は 1 日分を deterministic に aggregate する、1 日の起点となる command
です: 何か capture したら `today` を実行し、attention が必要なものを確認し、
detail な確認や mutation が必要なものだけ専門 command（`agenda`、`next`、
`project`、`proposal`、...）に進みます。`today` 自身は "actionable"、
"blocked"、"overdue"、"today" の第二の定義を発明しません — 以下の各 bucket
は対応する専門 command が既に使っている engine をそのまま再利用します。

```console
$ lifetxt today
$ lifetxt today --mode morning --horizon 5
$ lifetxt today --person self --json
$ lifetxt today --area home
$ lifetxt today --saved-view urgent
```

`--mode` は presentation emphasis を変えるだけで、underlying records は変えません。morning planning、midday re-check、evening review に使っても、JSON と MCP clients に渡る deterministic buckets は同じです。

`--saved-view NAME`/`--area NAME` は aggregate する前に、1 つの configured
saved view（[query.md](query.md) 参照）または 1 つの `area:` へ scope を
絞ります。`view run`/`area show` が既に使っている選択機構をそのまま再利用する
personalization であり、Today 専用の configuration language ではありません。
両者は同時に指定できません。

Buckets:

- **now**: 現在 active な Status/Presence records（`from:` を持ち `to:` を持たない `S` items）。`lifetxt status`/`lifetxt start` が既に使っている open-status の定義をそのまま再利用します
- **today events**: occurrence が today に該当する `E`/`R` items。`agenda` 自身の occurrence/recurrence/timezone 解決を 1 日分に bound して再利用します。today due の tasks/deadlines は下記の **due today** に既に現れるため、ここでは重複させません
- **overdue**: `due:` が today より前の tasks/deadlines
- **due today**: `due:` が today
- **upcoming**: horizon 内の `due:`。default は 3 days
- **blocked**: `depends_on:` target がまだ done ではない
- **waiting**: status `[?]`
- **next actions**: `next`、TUI `/next`、MCP `get_next_actions` と同じ open/unblocked/non-someday actions。ここで再定義せず再利用しています（[new-cli-workflows.md](new-cli-workflows.md) 参照）
- **habits**: open `H` items
- **messages**: acknowledge 済みでなく、有効な `snooze_until:` の対象でもない open `M` items。`--person` で scope 可能
- **captures**: `project:`、`due:`、`assignee:` がない open tasks（未整理の quick capture。下記の Unified Inbox とは別物）
- **inbox**: bounded な Unified Inbox summary。`total`/`pending_count`/`deferred_count`/`counts` と、pending proposal の一部（`id`、`source`、`created`、`summary`）まで。完全な operational proposal store は `proposal list` / MCP `list_proposals` のままで、ここでは複製しません
- **project attention**: non-green projects と health reasons
- **ticket attention**: `review` status、high severity、または stale な open `record:ticket` items。該当した理由をそれぞれ記録します。`ticket project` report や `temporal` と同じ `severity`/staleness rule を再利用し、別定義は作りません
- **safety**: configuration-validity の quick signal

due date が判別できる **overdue**/**due today** の各 row は、deterministic な
`reason`（例: `"3 days overdue"`、`"due today"`）も持ちます。これは
[temporal context](#temporal-context) が既に計算している `overdue_by`/`due_in`
の fact から導出される、固定で inspectable な "why" であり、生成された
説明ではありません。

attention/next-action/upcoming の各 row は record の生の `progress:` 値も
そのまま保持します（無ければ `null`）。CLI の text renderer は値がある場合、
row の隣に `progress:75%` や `progress:3/10 (30%)` のように表示し、
無い場合は何も追加表示しません。

CLI の text renderer はこれらの bucket を `NOW`、`ATTENTION`、`TODAY`、
`NEXT ACTIONS`、`BLOCKED`、`HABITS`、`INBOX` という documented な daily-hub
見出しの下にまとめ、既に前の見出しで表示された row は skip します（overdue な
task は `NEXT ACTIONS` で重複表示されず、Habit は `HABITS` の下で一度だけ
表示されます）ので、同じ record が二重に提示されることはありません。
`--json` 出力はこの grouping の影響を受けず、すべての bucket をそのまま返し
ます。空の bucket は rename や削除ではなく単に空の list になります。

同じ aggregation は MCP tool `get_command_center`（`saved_view`/`area` も
受け付け、`revision` field も持ちます。[ai-integration.md](ai-integration.md#context-revision)
参照）と、TUI `/today` view、Web の Today dashboard からも使えます —
4 つの surface すべてが同じ `command_center()` の結果を読むため、
「today」の意味はどこでも同じです。

## Areas

`area:` は `project:` の上に置ける optional organizing dimension です。item の area は item 自身の `area:` detail から、project の area は project record または registry の `default_area` から決まります。areas は data に現れる values であり、`work`、`research`、`health`、`home`、`finance`、`family`、`learning` は examples であって required taxonomy ではありません。

```console
$ lifetxt area list
$ lifetxt area show work
```

MCP: `get_areas`.

areas は data-derived です。area を rename するには、relevant `area:` details または project registry records を変更します。hidden area database はありません。

## Backlinks

`backlinks` は「この item を何が指しているか」を答えます。link graph の incoming half を、relation (`parent`, `ref`, `depends_on`, `blocks`, `related`, `duplicate_of`, `replaced_by`) ごとに group します。

```console
$ lifetxt backlinks T-1
$ lifetxt backlinks T-1 --json
```

MCP: `get_backlinks`.

backlinks は read-only です。source item を edit する前に、incoming relationships を見て change が safe か判断するための report です。

## Temporal context

`temporal` は「この item の周りで時間的に何が relevant か」を 1 item ずつ答えます。`backlinks`/`links` が扱う明示的な relation graph とは別の、bounded かつ説明可能な derived facts です。

```console
$ lifetxt temporal T-1
$ lifetxt temporal T-1 --window 14 --limit 5
$ lifetxt temporal T-1 --json
```

`rule`/`source_field`/`reference_time` を必ず伴う 2 種類の fact:

- **facts**（item 自身について）: `due:` から得る `overdue_by`/`due_in`、および `stale_since`（`--stale-after` 日数、default 14、以上 activity がない -- `ticket project` report が tickets 用に既に使っている threshold-based rule を、`updated:`/`created:` などを持つ任意の item に一般化したもの）。
- **related** items: この item 自身の日付から `--window` 日以内（default 7）にある他の dated items への `same_day`/`before`/`after` edge。近い順、`--limit`（default 20）まで。

life.txt へ書き戻すものは何もなく、`depends_on:`/`blocks:` などの再計算もしません（それらは `backlinks`/`links` のままです）。比較可能な日付がない item は単に fact を返しません。`temporal` は relation を推測しません。結果は常に 1 item の近傍に bounded され、workspace 全体の全件走査にはなりません。

MCP: `get_temporal_context`（`id`、`window`、`limit`、`stale_after`）。read-only
で、同じ engine に完全に委譲します。`lifetxt temporal --json` と同一の
`temporal-context-v1` object に加えて `revision` field を返します
（[ai-integration.md](ai-integration.md#context-revision) を参照）。

## Projects over MCP

project と portfolio aggregations は read-only tools として AI clients に公開されます。`get_projects`、`get_project`、`get_portfolio` です。CLI の `project`/`portfolio` commands と同じ `lifetxt/projects.py` logic を再利用するため、model は transparent progress/health formulas を含めて human と同じ view を見ます。
