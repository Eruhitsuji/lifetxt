# AI Integration

lifetxt ships an MCP (Model Context Protocol) server over stdio, so an AI client
can read and edit your `life.txt` through typed tools instead of guessing at the
file format. This document covers setup, the tool surface, the safety model, and
the local-first patterns that keep your data yours.

- [1. Quick Start](#1-quick-start)
- [2. Client Configuration](#2-client-configuration)
- [3. Tool Reference](#3-tool-reference)
- [4. Write Safety](#4-write-safety)
- [5. Prompts](#5-prompts)
- [6. Read-Only And Privacy](#6-read-only-and-privacy)
- [7. Without MCP](#7-without-mcp)

---

## 1. Quick Start

```sh
python -m lifetxt mcp life.txt
```

The server speaks JSON-RPC over stdin/stdout. It never opens a network port and
never sends your file anywhere; the client you connect it to decides what
reaches a model.

Verify it by hand:

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

Point a model at your data without letting it write:

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

`.cursor/mcp.json` or the editor's MCP settings:

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

### Multiple files

Pass several paths; the first is the default write target unless `write_file`
is configured:

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

Use absolute paths: the client usually launches the server from an unrelated
working directory, and `.lifetxt.json` is only found relative to the current
directory.

---

## 3. Tool Reference

Every tool carries MCP annotations (`readOnlyHint`, `destructiveHint`) so a
client can decide what needs confirmation.

### Reading

| Tool | Purpose |
| --- | --- |
| `list_items` | Filtered item list, same filters as `GET /api/items` |
| `get_item` | One item by `id:` |
| `search_items` | Fuzzy search over titles, ids, and detail values |
| `get_next_actions` | Open, unblocked, non-parked work by priority then due date |
| `get_agenda` | Items in a datetime range |
| `get_review` | Completions and elapsed time for a period |
| `get_stats` | Task, habit, mood, and project statistics |
| `get_habit_streaks` | Per-habit completion counts and streaks |
| `get_workload` | Open, actionable, due-soon, overdue counts per assignee |
| `get_graph` | Dependency graph nodes and edges |
| `get_blockers` | What is blocking an item |
| `list_links` | `parent:`, `ref:`, `depends_on:`, `blocks:`, `related:` |
| `get_status` | Presence records and which one is open |
| `list_notifications` | Due message notifications |
| `list_messages` | `M` records |
| `check_line` / `parse_item` | Validate or parse a line without writing |
| `parse_shorthand` | Preview sigil and date-token expansion |
| `complete` | Values the file already uses for a kind, so you reuse rather than reinvent |
| `get_file_state` | Paths, write target, read-only flag, content hashes |
| `check_files` | Verify `file:`/`dir:` attachments: existence, type, hash, portability |
| `timer_status` | The running timer, if any |

### Writing

| Tool | Purpose |
| --- | --- |
| `capture_item` | Create a task from plain text with `@project #tag !priority ^due` |
| `create_item` | Create a record from explicit fields |
| `update_item` | Change fields on an existing record |
| `mark_done` | Close a task and write `done:` |
| `complete_item` | Complete a repeat instance and materialize the next |
| `delete_item` | Remove a record |
| `set_status` | Record presence, closing the previously open status |
| `attach_file` | Associate a file or directory with an item and record its hash |
| `timer_start` / `timer_stop` / `timer_cancel` | Drive the shared timer |
| `start_work` / `stop_work` | Bracket a work session in one call |
| `create_message` / `reply_message` / `ack_message` / `snooze_message` | `M` record flow |

### Shorthand parity

The same shorthand the CLI and TUI accept works here:

```json
{"name": "capture_item", "arguments": {"text": "Buy milk @home #errand !high ^tomorrow"}}
```

produces `[ ] T "Buy milk" project:home tag:errand priority:high due:2026-07-20
source:mcp id:task_...`. Call `parse_shorthand` with no arguments to get the
full token list, which is useful to include in a system prompt.

### Reusing existing values

The most common way an agent degrades a file is by inventing a near-duplicate:
`project:reserach` beside `project:research`, or a fresh `assignee:` spelling
for someone already recorded. `complete` lists what the file already uses:

```json
{"name": "complete", "arguments": {"kind": "project", "prefix": "re"}}
```

```json
{"kind": "project", "prefix": "re", "count": 1, "values": ["research"]}
```

Call it with no `kind` to list the supported kinds: `state`, `project`, `tag`,
`person`, `id`, `type`, `status`, `context`, `priority`, `key`, `team`,
`service`, and `channel`. `person` spans every people-shaped key at once, and
`state` and `priority` list the documented values before the file's own.

Prefer checking `complete` before writing a detail whose value is a name you
did not read from this file in the current session.

---

## 4. Write Safety

The server assumes the model is a capable but fallible collaborator, so the
dangerous parts are structural rather than advisory.

### Proposal mode

Every write tool accepts `dry_run: true` and returns a unified diff instead of
writing:

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

The file is byte-identical afterwards. Have the model propose first and apply
only after you confirm; the `inbox_triage` prompt is built around this.

### Conflict detection

Reads return a content hash and writes accept it back:

1. `get_file_state` → `file_hash`
2. write tool with `expected_file_hash: "<that hash>"`
3. if the file changed in between, the write is rejected with a conflict error

Every successful write returns the new `file_hash`, so a chain of edits can pass
it forward. Omitting the hash skips the check, which is fine for a single-user
session but not when a Web UI or another agent may be writing concurrently.

### Server-generated ids

`create_item` and `capture_item` refuse a client-supplied `id:` and generate one
themselves. A model that invents ids will eventually reuse one, which silently
merges two unrelated records on the next update. Read the id out of the
response and use it for follow-up calls.

This holds regardless of config `ids.auto`, which governs hand-written capture
rather than API writes.

### Provenance

Records created through MCP carry `source:mcp` so you can always tell what a
model wrote:

```sh
lifetxt filter life.txt --detail source=mcp
```

Disable with `{"mcp": {"source_metadata": false}}`.

### Presence integrity

`set_status` performs the whole transition — close the open record, open the new
one — in a single write, so it cannot leave two records that both look current.
Repeating a state that is already open writes nothing, because that would split
one long block into a stub plus a new record and lose the real start time.

### Completion time

`mark_done` follows the same `done.precision` config as the CLI, and accepts
`now: true` for a timestamp. Habit logs stay date-only.

---

## 5. Prompts

The server exposes reusable workflows through the MCP prompts capability, so a
client can offer them as slash commands:

| Prompt | Purpose |
| --- | --- |
| `daily_review` | What is due, what is actionable, what slipped |
| `weekly_review` | Completions, time, habits, and stalled work |
| `standup` | Done / Today / Blocked in under 120 words |
| `inbox_triage` | Propose project, due, and priority for untriaged captures |
| `start_focus` | Pick the best next action and start a work session |

Each one names the tools to call and, where it matters, instructs the model to
propose with `dry_run` before writing.

---

## 6. Read-Only And Privacy

`--read-only` refuses every write tool with a clear error while leaving all read
tools working. Read tools still work, so a model can summarise and plan without
being able to change anything.

The server is local and stdio-only:

- no network listener, no telemetry, no outbound calls
- the file never leaves the machine unless your MCP client sends it to a model
- a local model (Ollama, LM Studio, llama.cpp) with an MCP-capable client keeps
  the whole loop offline

Because `life.txt` is plain text, you can always audit exactly what changed:

```sh
git diff life.txt
lifetxt undo life.txt
```

Keep secrets out of the file. Anything in it is visible to whatever model your
client is talking to; use `--url-env` and `--key-env` patterns instead of
literal tokens.

---

## 7. Without MCP

MCP is not required. The CLI composes well with any model that can run commands:

```sh
# hand a filtered slice to a model
lifetxt filter life.txt --open --project work --format json | llm "what should I do first?"

# review as JSON
lifetxt review life.txt --week --format json | llm "summarise my week in 5 bullets"

# let a model draft, then validate before writing
llm "3 tasks for launching the docs site, one per line" \
  | while read -r line; do lifetxt q "$line @docs"; done
```

`lifetxt check` validates anything before it lands, and `lifetxt q` goes through
the same safe append path the MCP server uses.

For CI, `lifetxt review --format markdown` produces a summary suitable for a job
summary or a pull request comment.
