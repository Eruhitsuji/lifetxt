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
- [6. Permission Profiles And Privacy](#6-permission-profiles-and-privacy)
- [7. Remote Safe Mode Client Tools](#7-remote-safe-mode-client-tools)
- [8. Without MCP](#8-without-mcp)

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

### Generic setup command

```sh
python -m lifetxt ai setup generic life.txt
```

Prints the exact command and a generic `mcpServers` configuration for your
current workspace -- resolved paths and write target included, so you do not
have to hand-write either. It writes nothing to disk. The emitted profile
defaults to `read`; pass `--profile assist|full` to emit a different one, or
`--format json` for a machine-readable version.

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

### Constrained profiles

Point a model at your data without giving it full write access; see
[Section 6](#6-permission-profiles-and-privacy) for what each profile allows:

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

`--read-only` still works and is equivalent to `--profile read`.

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
| `list_links` | `parent:`, `ref:`, `depends_on:`, `blocks:`, `related:`, `duplicate_of:`, `replaced_by:` |
| `get_status` | Presence records and which one is open |
| `list_notifications` | Due message notifications |
| `list_messages` | `M` records |
| `check_line` / `parse_item` | Validate or parse a line without writing |
| `parse_shorthand` | Preview sigil and date-token expansion |
| `complete` | Values the file already uses for a kind, so you reuse rather than reinvent |
| `get_file_state` | Paths, write target, read-only flag, content hashes |
| `check_files` | Verify `file:`/`dir:` attachments: existence, type, hash, portability |
| `timer_status` | The running timer, if any |
| `remote_list_profiles` | Local Remote Safe Mode profile names and URLs, never stored secrets |
| `remote_test_connection` | Connectivity and capability negotiation for one remote profile |
| `remote_list_resources` | The read-only resources published by a remote lifetxt server |
| `remote_get_resource` | One permission-filtered remote resource such as `next`, `tickets`, `agenda`, or `search` |

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
| `explain_item` | Why one item (`id`, required) is relevant now, composed from `get_temporal_context`, `get_backlinks`, `get_command_center`/`get_next_actions`, and `get_ticket`/`get_project` |

Each one names the tools to call and, where it matters, instructs the model to
propose with `dry_run` before writing. `explain_item` is read-only end to end:
it never proposes a write, only an explanation grounded in the provenance
fields the composed tools already return. A required argument that is
omitted, such as `explain_item`'s `id`, is rejected with a clear error rather
than silently producing a generic prompt.

---

## 6. Permission Profiles And Privacy

`--profile` chooses how much of the tool surface a connected client can reach.
It is enforced twice -- once when the server advertises its tool list
(`tools/list`), and again when a tool is actually called (`tools/call`) -- so a
client cannot reach a disallowed tool by calling it directly instead of
listing it first.

| Profile | Read tools | Writes | Notes |
| --- | --- | --- | --- |
| `read` | all | none | Equivalent to `--read-only`. |
| `assist` | all | `stage_proposal` only | Stages a Unified Inbox proposal for you to review and accept; never writes `life.txt` directly. |
| `full` | all | all | Today's default when neither flag is given. |

```sh
python -m lifetxt mcp --profile read life.txt
python -m lifetxt mcp --profile assist life.txt
```

A tool with no explicit read/write classification is unreachable under `read`
and `assist`, not reachable by default -- this is deliberate: adding a new tool
to lifetxt in the future cannot silently widen what a constrained connection
can do. `--read-only` keeps working exactly as before and is equivalent to
`--profile read`; combining `--read-only` with a different `--profile` is
rejected as a conflicting request. MCP tool annotations (`readOnlyHint`, etc.)
are descriptive only and are never used to decide what a profile allows.

Permission profiles control which *tools* are reachable. They do not yet
control which *workspace sources or records* are visible to a client -- that
is a separate, not-yet-implemented workspace/disclosure layer.

Read tools still work under every profile, so a model can summarise and plan
without being able to change anything beyond what its profile allows.

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

## 7. Remote Safe Mode Client Tools

The MCP server can also act as a read-only client for another lifetxt server
running Remote Safe Mode. These tools reuse the same profile store as the CLI
`lifetxt remote profile-*` commands:

```json
{"name": "remote_list_profiles", "arguments": {}}
```

returns profile names and URLs only. Secrets are not returned. The other remote
tools take one of those profile names:

```json
{"name": "remote_test_connection", "arguments": {"profile": "home"}}
{"name": "remote_list_resources", "arguments": {"profile": "home"}}
{"name": "remote_get_resource", "arguments": {"profile": "home", "resource": "next", "params": {"project": "web"}}}
```

`remote_get_resource` passes query parameters through to the server resource,
so a model can ask for the same filtered slices available to the CLI remote
client. The server still enforces the remote principal's permissions; the MCP
tool does not bypass Remote Safe Mode. These four tools are read-only from the
MCP client's point of view: they may perform an HTTP request to the configured
remote URL, but they do not mutate the remote `life.txt`.

Use them when the AI client is local but the authoritative workspace is on a
different machine. For writes, use the CLI remote write flow with an explicit
proposal and confirmation; MCP exposes only the Remote Safe Mode read-client
slice.

---

## 8. Without MCP

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
