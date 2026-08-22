# Life Hub: Daily Command Center, Areas, and Backlinks

The Life Hub commands turn a life.txt workspace into a single place to see what
needs attention today, how work is organized by area, and how items connect.
Every command reads from one shared aggregation so the CLI, MCP, and future Web
surfaces agree on the same picture.

## Daily command center

`today` builds one deterministic aggregation of the day:

```console
$ lifetxt today
$ lifetxt today --mode morning --horizon 5
$ lifetxt today --person self --json
```

`--mode` changes presentation emphasis, not the underlying records. Use it for
morning planning, midday re-checks, or evening review while keeping the same
deterministic buckets available to JSON and MCP clients.

Buckets:

- **overdue** — tasks/deadlines with a `due:` before today
- **due today** — `due:` equal to today
- **upcoming** — `due:` within the horizon (default 3 days)
- **blocked** — a `depends_on:` target is not yet done
- **waiting** — status `[?]`
- **next actions** — the same open/unblocked/non-someday actions `next`, the
  TUI `/next` view, and MCP `get_next_actions` already agree on, reused here
  rather than redefined (see [new-cli-workflows.md](new-cli-workflows.md))
- **habits** — open `H` items
- **messages** — open `M` items (optionally scoped to `--person`)
- **captures** — open tasks with no `project:`, `due:`, or `assignee:`
  (untriaged quick captures, distinct from the Unified Inbox below)
- **inbox** — a bounded Unified Inbox summary: `total`/`pending_count`/
  `deferred_count`/`counts` plus up to a handful of pending proposals
  (`id`, `source`, `created`, `summary`); the full operational proposal store
  stays in `proposal list` / MCP `list_proposals`, never duplicated here
- **project attention** — non-green projects with their health reasons
- **safety** — a quick configuration-validity signal

The same aggregation is available to AI clients through the MCP tool
`get_command_center`.

## Areas

`area:` is an optional organizing dimension above `project:`. An item's area
comes from its own `area:` detail; a project's area comes from its record or the
registry's `default_area`. Areas are whatever appears in the data — presets like
`work`, `research`, `health`, `home`, `finance`, `family`, `learning` are
examples, never a required taxonomy.

```console
$ lifetxt area list
$ lifetxt area show work
```

MCP: `get_areas`.
Because areas are data-derived, renaming an area means changing the relevant
`area:` details or project registry records; there is no hidden area database.

## Backlinks

`backlinks` answers "what points at this item?" — the incoming half of the link
graph, grouped by relation (`parent`, `ref`, `depends_on`, `blocks`, `related`,
`duplicate_of`, `replaced_by`):

```console
$ lifetxt backlinks T-1
$ lifetxt backlinks T-1 --json
```

MCP: `get_backlinks`.
Backlinks are read-only. They report incoming relationships so you can decide
whether a change is safe before editing the source item.

## Projects over MCP

The project and portfolio aggregations are exposed to AI clients as read-only
tools: `get_projects`, `get_project`, `get_portfolio`. They reuse the same
`lifetxt/projects.py` logic as the CLI `project`/`portfolio` commands, so a model
sees exactly what a person sees, including the transparent progress and health
formulas.
