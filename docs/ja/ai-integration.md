# AI 連携

lifetxt は stdio 上の MCP (Model Context Protocol) server を同梱しています。AI client は file format を推測するのではなく、型付き tool を通じて `life.txt` を読み書きできます。この文書では setup、tool surface、安全 model、data を local-first に保つ使い方を説明します。

- [1. Quick Start](#1-quick-start)
- [2. Client Configuration](#2-client-configuration)
- [3. Tool Reference](#3-tool-reference)
- [4. Write Safety](#4-write-safety)
- [5. Prompts](#5-prompts)
- [6. Read-Only And Privacy](#6-read-only-and-privacy)
- [7. Remote Safe Mode Client Tools](#7-remote-safe-mode-client-tools)
- [8. Without MCP](#8-without-mcp)

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

### Read-only variant

model に data は見せるが書き込みは許可しない設定です。

```json
{
  "mcpServers": {
    "lifetxt-readonly": {
      "command": "python",
      "args": ["-m", "lifetxt", "mcp", "--read-only", "/absolute/path/to/life.txt"]
    }
  }
}
```

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

## 6. Read-Only And Privacy

`--read-only` はすべての write tool を明確な error で拒否し、read tool は動作させます。model は要約や計画を作れますが、変更はできません。

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

## 7. Remote Safe Mode Client Tools

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

## 8. Without MCP

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
