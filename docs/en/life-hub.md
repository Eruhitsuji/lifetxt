# Life Hub: Daily Command Center, Areas, Backlinks, and Temporal Context

The Life Hub commands turn a life.txt workspace into a single place to see what
needs attention today, how work is organized by area, how items connect, and
how they relate in time. Every command reads from one shared aggregation so
the CLI, MCP, and future Web surfaces agree on the same picture.

## Daily command center

`today` builds one deterministic aggregation of the day and is the intended
starting point of the day: capture something, run `today`, see what needs
attention, then move to the specialized command (`agenda`, `next`, `project`,
`proposal`, ...) for anything that needs deeper inspection or a mutation.
`today` itself never invents a second definition of "actionable", "blocked",
"overdue", or "today" — every bucket below reuses the exact engine the
matching specialized command already uses.

```console
$ lifetxt today
$ lifetxt today --mode morning --horizon 5
$ lifetxt today --person self --json
$ lifetxt today --area home
$ lifetxt today --saved-view urgent
```

`--mode` changes presentation emphasis, not the underlying records. Use it for
morning planning, midday re-checks, or evening review while keeping the same
deterministic buckets available to JSON and MCP clients.

`--saved-view NAME`/`--area NAME` scope the whole aggregation to one
configured saved view (see [query.md](query.md)) or one `area:` before
building it — personalization through the same existing selection
mechanisms `view run`/`area show` already use, not a Today-only
configuration language. The two are mutually exclusive.

Buckets:

- **now** — currently active Status/Presence records (`S` items with a
  `from:` and no `to:`), reusing the same open-status definition
  `lifetxt status`/`lifetxt start` already use
- **today events** — `E`/`R` items whose occurrence falls today, reusing
  `agenda`'s own occurrence/recurrence/timezone resolution bounded to a
  single day; tasks/deadlines due today already appear in **due today**
  below, so they are not repeated here
- **overdue** — tasks/deadlines with a `due:` before today
- **due today** — `due:` equal to today
- **upcoming** — `due:` within the horizon (default 3 days)
- **blocked** — a `depends_on:` target is not yet done
- **waiting** — status `[?]`
- **next actions** — the same open/unblocked/non-someday actions `next`, the
  TUI `/next` view, and MCP `get_next_actions` already agree on, reused here
  rather than redefined (see [new-cli-workflows.md](new-cli-workflows.md))
- **habits** — open `H` items
- **messages** — open `M` items not yet acknowledged and not under an active
  `snooze_until:` (optionally scoped to `--person`)
- **captures** — open tasks with no `project:`, `due:`, or `assignee:`
  (untriaged quick captures, distinct from the Unified Inbox below)
- **inbox** — a bounded Unified Inbox summary: `total`/`pending_count`/
  `deferred_count`/`counts` plus up to a handful of pending proposals
  (`id`, `source`, `created`, `summary`); the full operational proposal store
  stays in `proposal list` / MCP `list_proposals`, never duplicated here
- **project attention** — non-green projects with their health reasons
- **ticket attention** — open `record:ticket` items in `review` status,
  high severity, or stale, each tagged with which reason(s) applied; reuses
  the same `severity`/staleness rules `ticket project` reports and `temporal`
  already use, never a second definition of either
- **safety** — a quick configuration-validity signal

Every `overdue`/`due today` row that has a determinable due date also carries
a deterministic `reason` (e.g. `"3 days overdue"`, `"due today"`), derived
from the same `overdue_by`/`due_in` facts [temporal context](#temporal-context)
already computes — a fixed, inspectable "why", not a generated explanation.

The CLI text renderer groups these buckets under the documented daily-hub
headings — `NOW`, `ATTENTION`, `TODAY`, `NEXT ACTIONS`, `BLOCKED`, `HABITS`,
`INBOX` — and skips a row already shown under an earlier heading (an overdue
task is not repeated under `NEXT ACTIONS`; a Habit is shown once, under
`HABITS`) so the same record is never presented twice. `--json` output is
unaffected by this grouping and returns every bucket unchanged; empty
buckets are simply empty lists rather than being renamed or removed.

The same aggregation is available to AI clients through the MCP tool
`get_command_center` (which also accepts `saved_view`/`area` and carries a
`revision` field, see [ai-integration.md](ai-integration.md#context-revision))
and to the TUI `/today` view and the Web Today dashboard — all four surfaces
read the identical `command_center()` result, so "today" means the same thing
everywhere.

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

## Temporal context

`temporal` answers "what is relevant around this item, in time?" for one item
at a time — a bounded, explainable set of derived date-based facts, distinct
from the explicit relation graph `backlinks`/`links` report:

```console
$ lifetxt temporal T-1
$ lifetxt temporal T-1 --window 14 --limit 5
$ lifetxt temporal T-1 --json
```

Two kinds of fact, both carrying `rule`/`source_field`/`reference_time` so
you can see why each one exists:

- **facts** about the item alone: `overdue_by`/`due_in` (from `due:`) and
  `stale_since` (no activity in more than `--stale-after` days, default 14 —
  the same threshold-based rule `ticket project` reports already use for
  tickets, generalized here to any item with an `updated:`/`created:`/similar
  timestamp).
- **related** items: `same_day`/`before`/`after` edges to other dated items
  within `--window` days (default 7) of this item's own date, nearest first,
  capped at `--limit` (default 20).

Nothing here is written back to life.txt, and nothing here recomputes
`depends_on:`/`blocks:`/... — those stay with `backlinks`/`links`. An item
with no comparable date simply reports no fact for it; `temporal` never
guesses a relation. The result is always bounded to one item's neighborhood,
never an all-item scan of the workspace.

MCP: `get_temporal_context` (`id`, `window`, `limit`, `stale_after`), read-only
and delegating entirely to the same engine; it returns the identical
`temporal-context-v1` object `lifetxt temporal --json` prints, plus a
`revision` field (see [ai-integration.md](ai-integration.md#context-revision)).

## Projects over MCP

The project and portfolio aggregations are exposed to AI clients as read-only
tools: `get_projects`, `get_project`, `get_portfolio`. They reuse the same
`lifetxt/projects.py` logic as the CLI `project`/`portfolio` commands, so a model
sees exactly what a person sees, including the transparent progress and health
formulas.
