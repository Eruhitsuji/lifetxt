# Life Hub: Daily Command Center, Areas, and Backlinks

Life Hub commands は life.txt workspace を、今日 attention が必要なもの、area ごとの work organization、items 同士の connection を見る command center にします。すべての command は shared aggregation を読むため、CLI、MCP、future Web surfaces が同じ picture を見ます。

## Daily command center

`today` は 1 日分を deterministic に aggregate します。

```console
$ lifetxt today
$ lifetxt today --mode morning --horizon 5
$ lifetxt today --person self --json
```

`--mode` は presentation emphasis を変えるだけで、underlying records は変えません。morning planning、midday re-check、evening review に使っても、JSON と MCP clients に渡る deterministic buckets は同じです。

Buckets:

- **overdue**: `due:` が today より前の tasks/deadlines
- **due today**: `due:` が today
- **upcoming**: horizon 内の `due:`。default は 3 days
- **blocked**: `depends_on:` target がまだ done ではない
- **waiting**: status `[?]`
- **next actions**: `next`、TUI `/next`、MCP `get_next_actions` と同じ open/unblocked/non-someday actions。ここで再定義せず再利用しています（[new-cli-workflows.md](new-cli-workflows.md) 参照）
- **habits**: open `H` items
- **messages**: open `M` items。`--person` で scope 可能
- **captures**: `project:`、`due:`、`assignee:` がない open tasks（未整理の quick capture。下記の Unified Inbox とは別物）
- **inbox**: bounded な Unified Inbox summary。`total`/`pending_count`/`deferred_count`/`counts` と、pending proposal の一部（`id`、`source`、`created`、`summary`）まで。完全な operational proposal store は `proposal list` / MCP `list_proposals` のままで、ここでは複製しません
- **project attention**: non-green projects と health reasons
- **safety**: configuration-validity の quick signal

同じ aggregation は MCP tool `get_command_center` からも使えます。

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

## Projects over MCP

project と portfolio aggregations は read-only tools として AI clients に公開されます。`get_projects`、`get_project`、`get_portfolio` です。CLI の `project`/`portfolio` commands と同じ `lifetxt/projects.py` logic を再利用するため、model は transparent progress/health formulas を含めて human と同じ view を見ます。
