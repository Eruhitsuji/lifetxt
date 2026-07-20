# AI 連携

lifetxt は stdio 経由の MCP (Model Context Protocol) server を同梱しています。
AI client は file format を推測することなく、型付きの tool を通じて `life.txt` を
読み書きできます。この文書では設定、tool 一覧、安全性のモデル、
そしてデータを手元に保つための local-first な使い方を説明します。

- [1. クイックスタート](#1-クイックスタート)
- [2. client 設定](#2-client-設定)
- [3. tool 一覧](#3-tool-一覧)
- [4. 書き込みの安全性](#4-書き込みの安全性)
- [5. prompts](#5-prompts)
- [6. read-only とプライバシー](#6-read-only-とプライバシー)
- [7. MCP を使わない場合](#7-mcp-を使わない場合)

---

## 1. クイックスタート

```sh
python -m lifetxt mcp life.txt
```

server は stdin/stdout で JSON-RPC を話します。network port は開かず、
file をどこにも送信しません。model に何が渡るかは接続する client が決めます。

手動での確認:

```sh
printf '%s\n' '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' | python -m lifetxt mcp life.txt
```

---

## 2. client 設定

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

### read-only 構成

書き込みを許可せずに model にデータを見せる場合:

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

`.cursor/mcp.json` または editor の MCP 設定:

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

複数の path を渡せます。`write_file` が設定されていなければ最初の path が
書き込み先になります:

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

path は絶対パスにしてください。client は通常無関係な作業ディレクトリから
server を起動し、`.lifetxt.json` はカレントディレクトリ基準でしか探索されません。

---

## 3. tool 一覧

すべての tool は MCP annotation (`readOnlyHint`、`destructiveHint`) を持つため、
client は確認が必要かどうかを判断できます。

### 読み取り

| tool | 用途 |
| --- | --- |
| `list_items` | filter 付きの item 一覧。`GET /api/items` と同じ filter |
| `get_item` | `id:` で 1 件取得 |
| `search_items` | title、id、detail 値を横断する fuzzy 検索 |
| `get_next_actions` | 未完了・blocked でない・parked でない作業を priority 順に |
| `get_agenda` | 日時範囲の item |
| `get_review` | 期間の完了項目と経過時間 |
| `get_stats` | task、habit、mood、project の統計 |
| `get_habit_streaks` | habit ごとの完了数と streak |
| `get_workload` | assignee ごとの open / actionable / due-soon / overdue 件数 |
| `get_graph` | 依存グラフの node と edge |
| `get_blockers` | item を blocking しているもの |
| `list_links` | `parent:`、`ref:`、`depends_on:`、`blocks:`、`related:` |
| `get_status` | presence record と、現在 open なもの |
| `list_notifications` | 期限が来た message 通知 |
| `list_messages` | `M` record |
| `check_line` / `parse_item` | 書き込まずに行を検証・解析 |
| `parse_shorthand` | 記号と日付トークンの展開を事前確認 |
| `complete` | その kind でファイルが既に使っている値。新語を作らず再利用するため |
| `get_file_state` | path、書き込み先、read-only、content hash |
| `check_files` | `file:`/`dir:` attachment の存在・種別・hash・移植性を検証 |
| `timer_status` | 実行中の timer |

### 書き込み

| tool | 用途 |
| --- | --- |
| `capture_item` | `@project #tag !priority ^due` を含む plain text から task 作成 |
| `create_item` | 明示的な field から record 作成 |
| `update_item` | 既存 record の field を変更 |
| `mark_done` | task を完了して `done:` を書く |
| `complete_item` | 繰り返し instance を完了し次回を生成 |
| `delete_item` | record を削除 |
| `set_status` | 直前の status を閉じて presence を記録 |
| `attach_file` | file やディレクトリを item に関連付け、hash を記録 |
| `timer_start` / `timer_stop` / `timer_cancel` | 共有 timer の操作 |
| `start_work` / `stop_work` | 作業セッションを 1 回の呼び出しで開始・終了 |
| `create_message` / `reply_message` / `ack_message` / `snooze_message` | `M` record の流れ |

### 省略記法の対応

CLI や TUI と同じ省略記法が使えます:

```json
{"name": "capture_item", "arguments": {"text": "Buy milk @home #errand !high ^tomorrow"}}
```

は `[ ] T "Buy milk" project:home tag:errand priority:high due:2026-07-20
source:mcp id:task_...` を生成します。
`parse_shorthand` を引数なしで呼ぶと全トークン一覧が得られるため、
system prompt に含めると有用です。

### 既存の値の再利用

agent がファイルを劣化させる最も多いパターンは、ごく近い別語を作ってしまう
ことです。`project:research` の隣に `project:reserach` を作る、既に記録済みの
人物に別表記の `assignee:` を与える、といった例です。`complete` は
ファイルが既に使っている値を返します:

```json
{"name": "complete", "arguments": {"kind": "project", "prefix": "re"}}
```

```json
{"kind": "project", "prefix": "re", "count": 1, "values": ["research"]}
```

`kind` なしで呼ぶと対応 kind の一覧が得られます: `state`、`project`、`tag`、
`person`、`id`、`type`、`status`、`context`、`priority`、`key`、`team`、
`service`、`channel`。`person` は人物系の key をまとめて対象にし、`state` と
`priority` は文書化された値をファイル固有の値より先に並べます。

そのセッションで実際に読んでいない名前を detail の値として書く場合は、
先に `complete` で確認することを推奨します。

---

## 4. 書き込みの安全性

model は有能だが誤りうる協力者だと想定し、危険な部分は注意書きではなく
構造で防いでいます。

### proposal モード

すべての書き込み tool は `dry_run: true` を受け付け、書き込む代わりに
unified diff を返します:

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

実行後の file は 1 byte も変わりません。
model にはまず提案させ、確認してから適用させてください。
`inbox_triage` prompt はこの流れを前提に書かれています。

### 競合検出

読み取りで content hash を返し、書き込みでそれを受け取ります:

1. `get_file_state` → `file_hash`
2. 書き込み tool に `expected_file_hash: "<その hash>"` を渡す
3. その間に file が変わっていれば conflict error で拒否

成功した書き込みは新しい `file_hash` を返すため、連続した編集で引き継げます。
hash を省略すると検査は行われません。単一利用者の session では問題ありませんが、
Web UI や別の agent が同時に書く場合は渡してください。

### id は server が生成

`create_item` と `capture_item` は client 指定の `id:` を拒否し、server 側で生成します。
id を創作する model はいずれ同じ id を再利用し、次の更新で無関係な 2 件の record が
静かに統合されてしまうためです。
response から id を読み取り、後続の呼び出しに使ってください。

これは config の `ids.auto` に関係なく適用されます。
`ids.auto` は手書きのキャプチャを対象とした設定です。

### 由来の記録

MCP 経由で作成された record は `source:mcp` を持つため、
model が書いたものを常に判別できます:

```sh
lifetxt filter life.txt --detail source=mcp
```

`{"mcp": {"source_metadata": false}}` で無効化できます。

### presence の整合性

`set_status` は「open な record を閉じる」「新しい record を開く」を
1 回の書き込みで行うため、現在有効に見える record が 2 つ残ることはありません。
すでに開いている状態と同じ状態を指定した場合は何も書き込みません。
書き込むと長い 1 区間が切れ端と新 record に分割され、本当の開始時刻が失われるためです。

### 完了時刻

`mark_done` は CLI と同じ `done.precision` 設定に従い、`now: true` で時刻付きになります。
habit のログは日付のみのままです。

---

## 5. prompts

server は MCP の prompts capability で再利用可能なワークフローを公開します。
client 側では slash command として提示できます:

| prompt | 用途 |
| --- | --- |
| `daily_review` | 今日の期限、着手可能なもの、遅れているもの |
| `weekly_review` | 完了、時間、habit、停滞している作業 |
| `standup` | Done / Today / Blocked を 120 語以内で |
| `inbox_triage` | 未整理のキャプチャに project・due・priority を提案 |
| `start_focus` | 最良の next action を選んで作業セッションを開始 |

いずれも呼ぶべき tool を明示し、必要な場面では書き込み前に `dry_run` で
提案するよう model に指示しています。

---

## 6. read-only とプライバシー

`--read-only` はすべての書き込み tool を明確な error で拒否し、
読み取り tool は動作させます。
model は要約や計画はできますが、何も変更できません。

server は local かつ stdio のみです:

- network listener なし、telemetry なし、外部通信なし
- MCP client が model に送らない限り、file は machine から出ません
- local model (Ollama、LM Studio、llama.cpp) と MCP 対応 client を使えば
  全体を offline に保てます

`life.txt` は plain text なので、何が変わったかを常に監査できます:

```sh
git diff life.txt
lifetxt undo life.txt
```

秘密情報は file に入れないでください。
file の内容は client が話している model から見えます。
literal な token ではなく `--url-env` や `--key-env` の方式を使ってください。

---

## 7. MCP を使わない場合

MCP は必須ではありません。CLI は command を実行できる model と組み合わせられます:

```sh
# filter した一部を model に渡す
lifetxt filter life.txt --open --project work --format json | llm "what should I do first?"

# JSON で review
lifetxt review life.txt --week --format json | llm "summarise my week in 5 bullets"

# model に下書きさせ、検証してから書き込む
llm "3 tasks for launching the docs site, one per line" \
  | while read -r line; do lifetxt q "$line @docs"; done
```

`lifetxt check` は書き込み前の検証に使え、`lifetxt q` は MCP server と同じ
安全な追記経路を通ります。

CI では `lifetxt review --format markdown` が job summary や
pull request comment に適した要約を出力します。
