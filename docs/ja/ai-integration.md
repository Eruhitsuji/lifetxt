# AI 連携

lifetxt は stdio 上の MCP (Model Context Protocol) server を同梱しています。AI client は file format を推測するのではなく、型付き tool を通じて `life.txt` を読み書きできます。この文書では setup、tool surface、安全 model、data を local-first に保つ使い方を説明します。

- [1. Quick Start](#1-quick-start)
- [2. Client Configuration](#2-client-configuration)
- [3. Tool Reference](#3-tool-reference)
- [4. Write Safety](#4-write-safety)
- [5. Prompts](#5-prompts)
- [6. Permission Profiles And Privacy](#6-permission-profiles-and-privacy)
- [7. AI-Safe Workspaces](#7-ai-safe-workspaces)
- [8. Remote Safe Mode Client Tools](#8-remote-safe-mode-client-tools)
- [9. Without MCP](#9-without-mcp)

---

## 1. Quick Start

```sh
python -m lifetxt mcp life.txt
```

server は stdin/stdout で JSON-RPC を話します。network port は開かず、file を外部へ送信しません。model に何が届くかは、接続する MCP client が決めます。

手元で確認する例:

```sh
printf '%s\n' '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' | python -m lifetxt mcp life.txt
```

---

## 2. Client Configuration

### 汎用 setup command

```sh
python -m lifetxt ai setup generic life.txt
```

現在の workspace に対する正確な command と、汎用的な `mcpServers` configuration を
表示します -- 解決済みの path と write target を含むので、どちらも手書きする必要は
ありません。file への書き込みは一切行いません。出力される profile は default で
`read` になり、`--profile assist|full` で変更でき、`--format json` で機械可読な
出力も得られます。

client を接続する前に、実際に動作するか確認できます:

```sh
python -m lifetxt ai doctor life.txt
```

各 input file が存在し parse できるか、write target が一意に解決できるか
（できない場合は `lifetxt mcp` 自身が出す `--write-file` 必須の error と同じ内容）、
そして外部/信頼できない client には `read` を default として推奨する旨を表示します。
file への書き込みは一切行いません。

### Claude Desktop

`claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "lifetxt": {
      "command": "python",
      "args": ["-m", "lifetxt", "mcp", "/absolute/path/to/life.txt"]
    }
  }
}
```

### 制限された profile

model に data は見せるが、full な書き込み権限は与えない設定です。各 profile が何を許可するかは
[Section 6](#6-permission-profiles-and-privacy) を参照してください。

```json
{
  "mcpServers": {
    "lifetxt-readonly": {
      "command": "python",
      "args": ["-m", "lifetxt", "mcp", "--profile", "read", "/absolute/path/to/life.txt"]
    },
    "lifetxt-assist": {
      "command": "python",
      "args": ["-m", "lifetxt", "mcp", "--profile", "assist", "/absolute/path/to/life.txt"]
    }
  }
}
```

`--read-only` は引き続き使え、`--profile read` と同じ意味です。

### Cursor / VS Code

`.cursor/mcp.json` または editor の MCP settings:

```json
{
  "mcpServers": {
    "lifetxt": {
      "command": "python",
      "args": ["-m", "lifetxt", "mcp", "--config", "/absolute/path/.lifetxt.json"]
    }
  }
}
```

### 複数 file

複数 path を渡せます。`write_file` が設定されていなければ、最初の path が default write target です。

```json
{
  "mcpServers": {
    "lifetxt": {
      "command": "python",
      "args": [
        "-m", "lifetxt", "mcp",
        "/home/me/life.txt",
        "/home/me/work.life.txt",
        "--write-file", "/home/me/life.txt"
      ]
    }
  }
}
```

path は absolute path にしてください。client は通常、無関係な working directory から server を起動します。`.lifetxt.json` も current directory 基準でしか探索されません。

---

## 3. Tool Reference

すべての tool は MCP annotations (`readOnlyHint`, `destructiveHint`) を持つため、client は確認が必要かを判断できます。

### Reading

| Tool | Purpose |
| --- | --- |
| `list_items` | `GET /api/items` と同じ filters を使う item list |
| `get_item` | `id:` で 1 item を取得 |
| `search_items` | title、id、detail value の fuzzy search |
| `get_next_actions` | open、unblocked、non-parked work を priority と due date 順に返す |
| `get_agenda` | datetime range 内の items |
| `get_review` | period 内の completions と elapsed time |
| `get_stats` | task、habit、mood、project statistics |
| `get_habit_streaks` | habit ごとの completion count と streak |
| `get_workload` | assignee ごとの open/actionable/due-soon/overdue counts |
| `get_graph` | dependency graph の nodes と edges |
| `get_blockers` | item を block しているもの |
| `list_links` | `parent:`、`ref:`、`depends_on:`、`blocks:`、`related:`、`duplicate_of:`、`replaced_by:` |
| `get_status` | presence records と open record |
| `list_notifications` | due message notifications |
| `list_messages` | `M` records |
| `check_line` / `parse_item` | 書き込まずに 1 line を validate/parse |
| `parse_shorthand` | sigil と date-token expansion の preview |
| `complete` | file が既に使っている value を kind ごとに返す |
| `get_file_state` | paths、write target、read-only flag、content hashes |
| `check_files` | `file:`/`dir:` attachment の存在、type、hash、portability を確認 |
| `timer_status` | running timer |
| `remote_list_profiles` | local Remote Safe Mode profile の name と URL。secret は返さない |
| `remote_test_connection` | 1 profile の connectivity と capability negotiation |
| `remote_list_resources` | remote lifetxt server が publish する read-only resources |
| `remote_get_resource` | `next`、`tickets`、`agenda`、`search` などの permission-filtered remote resource |

### Context revision

`get_command_center`、`get_temporal_context`、`get_next_actions`、
`get_backlinks`、`get_ticket`、`get_project` はそれぞれ `revision` field を
持つ。これは全 source file の path と bytes に対する SHA-256 で、Remote Safe
Mode が各 resource read に既に付与している方法をそのまま再利用したもの
(`lifetxt.remote_backend.source_revision()` を無改変で再利用しており、
2 つ目の revision 方式は存在しない)。

これにより、1 つの目的のために複数回これらを呼び出す client -- 例えば
`explain_item` prompt は 1 つの対象 item に対し最大 6 回呼び出す -- が、
呼び出しの途中で workspace が変化したことに気付けるようになる。異なる
時点で読んだ事実を黙って混在させることを防ぐ。現時点では古い revision を
強制的に拒否する仕組みはなく、client が確認できるよう field を公開している
だけである。これは Remote の `tickets` resource が今日 1 つの限定的な場合に
対して行っている `since_revision` と同じ考え方である。`command_center()` や
`temporal_context()` を直接呼び出すライブラリ呼び出し元(CLI `today`/
`temporal`、TUI の Today view、Web の `/api/command-center` route)はこの
field を設定しない -- MCP tool の境界でのみ付与される。

### Writing

| Tool | Purpose |
| --- | --- |
| `capture_item` | `@project #tag !priority ^due` を含む plain text から task を作る |
| `create_item` | explicit fields から record を作る |
| `update_item` | existing record の fields を変更 |
| `mark_done` | task を close し `done:` を書く |
| `complete_item` | repeat instance を complete し next instance を materialize |
| `delete_item` | record を削除 |
| `set_status` | presence を記録し、以前の open status を close |
| `attach_file` | file/directory を item に関連付け hash を記録 |
| `timer_start` / `timer_stop` / `timer_cancel` | shared timer を操作 |
| `start_work` / `stop_work` | work session を 1 call で開始/終了 |
| `create_message` / `reply_message` / `ack_message` / `snooze_message` | `M` record flow |

### Shorthand parity

CLI と TUI が受け付ける shorthand は MCP でも使えます。

```json
{"name": "capture_item", "arguments": {"text": "Buy milk @home #errand !high ^tomorrow"}}
```

これは `[ ] T "Buy milk" project:home tag:errand priority:high due:2026-07-20 source:mcp id:task_...` を生成します。`parse_shorthand` を argument なしで呼ぶと token list が返るため、system prompt に含めると便利です。

### Existing values の再利用

agent が file を劣化させる典型例は、`project:research` の横に `project:reserach` を作るような近似 duplicate です。`complete` は file が既に使っている値を返します。

```json
{"name": "complete", "arguments": {"kind": "project", "prefix": "re"}}
```

```json
{"kind": "project", "prefix": "re", "count": 1, "values": ["research"]}
```

`kind` なしで呼ぶと対応 kind が返ります。`state`、`project`、`tag`、`person`、`id`、`type`、`status`、`context`、`priority`、`key`、`team`、`service`、`channel` です。今の session で読んでいない名前を detail value として書く前に、まず `complete` で確認してください。

---

## 4. Write Safety

server は model を有能だが間違える collaborator として扱うため、危険な部分は助言ではなく構造で守ります。

### Proposal mode

すべての write tool は `dry_run: true` を受け付け、書き込みの代わりに unified diff を返します。

```json
{"name": "mark_done", "arguments": {"id": "t1", "dry_run": true}}
```

```json
{
  "applied": false,
  "proposal": true,
  "summary": "Mark t1 done",
  "diff": ["--- life.txt (current)", "+++ life.txt (proposed)", "-[ ] T Write_Report id:t1", "+[x] T Write_Report id:t1 done:2026-07-19"]
}
```

この後も file は byte-identical です。model にはまず proposal を出させ、確認後だけ apply してください。`inbox_triage` prompt もこの流れを前提にしています。

### Conflict detection

read は content hash を返し、write はそれを受け取れます。

1. `get_file_state` -> `file_hash`
2. write tool に `expected_file_hash: "<that hash>"` を渡す
3. その間に file が変わっていれば conflict error で拒否される

成功した write は新しい `file_hash` を返すため、連続 edit ではそれを引き継げます。hash を省略すると check は行われません。single-user session では問題ない場合もありますが、Web UI や別の agent が同時に書く可能性があるなら渡してください。

### Server-generated ids

`create_item` と `capture_item` は client-supplied `id:` を拒否し、server 側で生成します。model が id を作ると再利用事故を起こし、後続 update で無関係な 2 records を同一視する危険があります。response から id を読み取り、後続 call に使ってください。

これは config の `ids.auto` とは別です。`ids.auto` は hand-written capture を対象にします。

### Provenance

MCP 経由で作られた records は `source:mcp` を持つため、model が書いたものを後から識別できます。

```sh
lifetxt filter life.txt --detail source=mcp
```

`{"mcp": {"source_metadata": false}}` で無効化できます。

### Presence integrity

`set_status` は open record を close し、新しい record を open する transition を 1 write で行います。同じ state が既に open なら何も書きません。長い 1 block を stub と新 record に分けて本当の start time を失うことを避けるためです。

### Completion time

`mark_done` は CLI と同じ `done.precision` config に従い、`now: true` で timestamp を使えます。habit logs は date-only のままです。

---

## 5. Prompts

server は MCP prompts capability で再利用可能な workflows を公開します。client は slash command として表示できます。

| Prompt | Purpose |
| --- | --- |
| `daily_review` | due、actionable、slipped items の確認 |
| `weekly_review` | completions、time、habits、stalled work |
| `standup` | Done / Today / Blocked を 120 words 未満でまとめる |
| `inbox_triage` | untriaged captures に project、due、priority を提案 |
| `start_focus` | best next action を選び work session を開始 |
| `explain_item` | 1 item（`id`、required）が今なぜ relevant かを、`get_temporal_context`、`get_backlinks`、`get_command_center`/`get_next_actions`、`get_ticket`/`get_project` を組み合わせて説明 |

各 prompt は呼ぶべき tool を示し、必要な場面では書き込み前に `dry_run` で proposal を出すよう model に指示します。`explain_item` は完全に read-only です:
proposal を出すことはなく、既存 tool が返す provenance field に基づく explanation のみを行います。`explain_item` の `id` のような required argument が省略された場合は、汎用的な prompt を黙って返すのではなく、明確な error で拒否されます。

---

## 6. Permission Profiles And Privacy

`--profile` は、接続した client が tool surface のどこまで到達できるかを選びます。判定は
2 箇所で行われます -- server が tool 一覧を提示する時 (`tools/list`) と、実際に tool を呼び出す時
(`tools/call`) です。そのため client は一覧に出ていない tool を直接呼び出しても回避できません。

| Profile | Read tool | 書き込み | 備考 |
| --- | --- | --- | --- |
| `read` | すべて | なし | `--read-only` と同じ意味。 |
| `assist` | すべて | `stage_proposal` のみ | Unified Inbox に proposal を stage するだけで、あなたが review して accept するまで `life.txt` に直接書き込まれない。 |
| `full` | すべて | すべて | どちらの flag も指定しない場合の、現在の default。 |

```sh
python -m lifetxt mcp --profile read life.txt
python -m lifetxt mcp --profile assist life.txt
```

read/write のどちらにも明示的に分類されていない tool は、`read` と `assist` では到達不能です --
これは意図的な挙動です: 将来 lifetxt に新しい tool が追加されても、制限された接続が使える範囲が
黙って広がることはありません。`--read-only` は従来どおり動作し、`--profile read` と同じ意味です。
`--read-only` と別の `--profile` を同時に指定すると、矛盾した要求として拒否されます。MCP の tool
annotation (`readOnlyHint` など) はあくまで説明用であり、どの profile が何を許可するかの判断には
使われません。

permission profile が制御するのは到達可能な *tool* だけです。どの workspace source や record が
見えるかという *disclosure* のレイヤーはまだ実装されておらず、別の課題として残っています。

read tool はどの profile でも動作するので、model は自分の profile が許す範囲を超えて変更すること
なく、要約や計画を作れます。

server は local かつ stdio-only です。

- network listener、telemetry、outbound calls はない
- MCP client が model に送らない限り、file は machine から出ない
- local model (Ollama、LM Studio、llama.cpp) と MCP-capable client を使えば loop 全体を offline に保てる

`life.txt` は plain text なので、何が変わったかは常に audit できます。

```sh
git diff life.txt
lifetxt undo life.txt
```

secret は file に入れないでください。file 内のものは client が話している model から見えます。literal token ではなく、`--url-env` や `--key-env` の pattern を使ってください。

---

## 7. AI-Safe Workspaces

`--profile` が制御するのは client が到達できる *tool* です。named workspace が
制御するのは、client が読み書きする *data* です -- 他のすべての lifetxt command
がすでにサポートしている同じ `--workspace` flag を使います。この二つを組み合わ
せることで、client に広い read access を与えつつ、その write を一つの専用 file
に閉じ込めることができます:

```json
{
  "workspaces": {
    "default": {
      "sources": [{"path": "life.txt", "role": "primary"}],
      "write_file": "life.txt"
    },
    "ai": {
      "sources": [
        {"path": "life.txt", "role": "readonly", "writable": false},
        {"path": "ai-inbox.life.txt", "role": "primary", "writable": true}
      ],
      "write_file": "ai-inbox.life.txt"
    }
  }
}
```

```sh
python -m lifetxt --workspace ai mcp --profile assist
python -m lifetxt --workspace ai ai setup generic --profile assist
python -m lifetxt --workspace ai ai doctor
```

この設定では、read tool（`list_items`、`get_agenda` など）は `life.txt` と
`ai-inbox.life.txt` の両方の item を見ますが、`assist` の下での
`stage_proposal` を含むすべての write tool は `ai-inbox.life.txt` に閉じ込め
られ、`life.txt` 自体には一切触れません。`get_file_state` は解決済みの
`writable_path` を報告するので、client（あるいはあなた自身）は、その接続を
信頼する前に、write が実際にどの file に届くのかを確認できます。`--workspace`
に必要なのは [`config.md`](./config.md) にすでに文書化されている
`workspaces` の設定だけであり、ここで動作させるために MCP 固有の設定は
何も必要ありません。

`--profile assist` と組み合わせることで、#500 が説明するpattern -- 広い read
context と、専用の proposal/inbox write path -- が実現します。AI client が
提案したものは、あなたが別途その proposal を accept するまで `life.txt` に
届くことはありません。

---

## 8. Remote Safe Mode Client Tools

MCP server は、Remote Safe Mode で動く別の lifetxt server の read-only client としても使えます。これらの tool は CLI の `lifetxt remote profile-*` commands と同じ profile store を再利用します。

```json
{"name": "remote_list_profiles", "arguments": {}}
```

これは profile name と URL だけを返します。secret は返しません。他の remote tool はその profile name を受け取ります。

```json
{"name": "remote_test_connection", "arguments": {"profile": "home"}}
{"name": "remote_list_resources", "arguments": {"profile": "home"}}
{"name": "remote_get_resource", "arguments": {"profile": "home", "resource": "next", "params": {"project": "web"}}}
```

`remote_get_resource` は query parameters を server resource に渡します。そのため model は CLI remote client と同じ filtered slice を要求できます。permission enforcement は remote server 上の principal に従います。MCP tool は Remote Safe Mode を迂回しません。

これら 4 tools は MCP client から見て read-only です。設定済み remote URL へ HTTP request は行いますが、remote `life.txt` は mutate しません。AI client は local にあり、authoritative workspace が別 machine にある場合に使います。write は MCP ではなく CLI remote write flow で、proposal と explicit confirmation を伴って行ってください。

---

## 9. Without MCP

MCP は必須ではありません。command を実行できる model なら CLI と組み合わせられます。

```sh
# filtered slice を model に渡す
lifetxt filter life.txt --open --project work --format json | llm "what should I do first?"

# JSON で review
lifetxt review life.txt --week --format json | llm "summarise my week in 5 bullets"

# model に draft させ、validate してから書く
llm "3 tasks for launching the docs site, one per line" \
  | while read -r line; do lifetxt q "$line @docs"; done
```

`lifetxt check` は landing 前の validation に使えます。`lifetxt q` は MCP server と同じ safe append path を通ります。

CI では `lifetxt review --format markdown` が job summary や pull request comment に適した summary を出力します。

---

## 10. Personal AI Memory

AI との会話から、好みや目標、恒久的な decision のような永続的な personal
fact を捕捉し、この workspace を読む全ての AI client から再利用できるように
するための convention です。セッションをまたぐたびに再導出したり忘れたり
することを防ぎます。これは新しい Format、Query、schema、MCP contract では
**ありません**。すべて本プロジェクトが既に出荷している仕組みだけで組み立てた
文書化された pattern であり、Personal Context Engine 調査（#503）が最初の
スライスとして選定したものです。

### Convention の内容

- **Kind**: `N`（Note）。Note は既に任意の custom detail key を無検査で
  受け付けます。未知の key は non-blocking な warning を出すだけで保存
  されます。
- **Subject**: workspace 所有者自身についての fact には `person:self`、
  他の誰かについてなら `person:<name>`。`person:` は既に汎用 field であり、
  特定の record kind 専用ではありません。
- **Intent tag**: `preference`、`goal`、`decision` のような素の `tag:` 値で、
  新しい first-class `assertion:`/`category:` 語彙を導入せずに fact の意図を
  可読にします（下記の
  [Query semantics は今回拡張しない](#query-semantics-は今回拡張しない)
  を参照）。
- **Staleness**: `lifetxt temporal <id>` / MCP `get_temporal_context` を
  無改変で再利用します。`updated:` detail を持つ任意の item に対し既に
  「まだ current か?」を答える `stale_since` fact が、personal-context の
  Note に対しても他の item と全く同様に使えます。

### Lifecycle

```text
AI conversation
      |
      v
MCP stage_proposal (kind: "N", details: {person: "self", tag: "preference"})
      |
      v
Unified Inbox（pending、review 可能、まだ authoritative ではない）
      |
      v
lifetxt proposal show / accept   <- human review
      |
      v
通常の life.txt N record
      |
      v
lifetxt search / lifetxt query / MCP list_items / get_item
```

ここに新しいものは何もありません: `stage_proposal` は既に任意の `kind` を
受け付け、Unified Inbox の review flow（`proposal list` / `show` / `accept` /
`reject`）は task や ticket の proposal と全く同じように動作し、accept された
Note は他の item と同じ方法で取得できます。

### 実例

実際の disposable workspace に対して検証済み。以下の command と出力は
例示ではなく実際に得られたものです。

```json
{"name": "stage_proposal", "arguments": {
  "title": "Prefers dark mode in all editors",
  "kind": "N",
  "details": {"person": "self", "tag": "preference"}
}}
```

```console
$ lifetxt proposal list
P-30181d96   [pending ] mcp      [ ] N "Prefers dark mode in all editors" person:self tag:preference
(1 total: pending=1)

$ lifetxt proposal accept P-30181d96
Accepted P-30181d96 -> life.txt
  [ ] N "Prefers dark mode in all editors" person:self tag:preference
Applied 1/1.
```

life.txt に書き込まれる accept 後の行:

```text
[ ] N "Prefers dark mode in all editors" person:self tag:preference
```

`stage_proposal` には `status` 引数がないため、staged された Note は常に
既定の `[ ]` status になります。`lifetxt check` はこれを non-blocking な
W102 hint（Note/Journal には `[N]` を推奨）として報告しますが、record 自体は
有効であり、上記の通り staging/accept されます。status の修正（および、
上記の staleness rule を適用したい場合にのみ必要で何も自動設定しない
`updated:` detail の追加）は通常の `lifetxt proposal edit` や後からの手動編集で
行うものであり、新しい仕組みではありません。

後で、この workspace を読む任意の AI client は新しい tooling なしにそれを
取得できます:

```console
$ lifetxt search "dark mode"
life.txt:1: WARNING W102: Note type N and journal type J are recommended to use status [N].
life.txt:1  [ ] N Prefers dark mode in all editors

$ lifetxt query "kind:N person:self tag:preference"
[ ] N "Prefers dark mode in all editors" person:self tag:preference
```

```json
{"name": "search_items", "arguments": {"query": "dark mode"}}
```

### Query semantics は今回拡張しない

`assertion:`（explicit/observed/inferred/conflicting）、`confidence:`
のような語彙は、この最初のスライスでは Query 許可リスト
（`CUSTOM_DETAIL_FIELDS`）に**意図的に追加しません** -- #503 に記録された
owner 決定です。personal-context の custom key は自由記述のままです:
`lifetxt query` は未知の field を Q001 warning で報告し、単にそれで
filter しないだけで、query 自体を拒否はしません。key を first-class Query
へ昇格させるのは、実際の利用がその継続的な互換性維持コストに見合うと
分かってからにします。これは `area`/`record`/`severity` が既に満たしている
のと同じ基準です。

### これは何ではないか

新しい `subject:` field も、既存の `source:` タグを超える構造化された
provenance モデルも、AI 推論から authoritative な fact への自動昇格も
ありません -- すべての Personal AI Memory 候補は、他の Unified Inbox
proposal と全く同じ human review を通過します。この convention の元になった
調査全体は #503 を参照してください。
