# Development Tickets

lifetxt adds Redmine-style issue tracking without a database and without
replacing the plain-text Task model. A ticket is a normal `T` record marked
`record:ticket`; existing filters, agenda, and reports still understand it. The
ticket layer adds canonical fields, a detailed `ticket_status` on top of the
coarse `[ ]`/`[x]` status, validation, and aggregation.

Generic project `record:issue` records remain available for operational concerns
that do not need the ticket workflow.

## Fields

A ticket carries any of these canonical fields (registry-backed ones are
validated against configuration):

`tracker`, `ticket_status`, `priority`, `severity`, `reporter`, `assignee`,
repeated `watcher`, `component`, `category`, `version`, `milestone`, `sprint`,
`est`, `elapsed`, `story_points`, `resolution`, `closed_by`, `branch`, repeated
`commit`/`pr`, `build`, plus the shared relation keys `parent`, `depends_on`,
`blocks`, `related`, `duplicate_of`, `replaced_by`.

## Status mapping

`ticket_status` is the detailed state; it maps onto the coarse life.txt status
so existing filters keep working:

| ticket_status                          | life.txt |
| -------------------------------------- | -------- |
| new, triaged, assigned                 | `[ ]`    |
| in_progress, review, testing           | `[/]`    |
| needs_info, blocked                    | `[?]`    |
| deferred                               | `[>]`    |
| resolved, closed                       | `[x]`    |
| rejected, duplicate, wont_fix          | `[-]`    |

A contradictory pair (e.g. `ticket_status:closed` on a `[ ]` line) is reported as
`TK003`. Override or extend the map under `ticketing.statuses`.

## Configuration

```json
{
  "ticketing": {
    "id_prefix": "BUG",
    "trackers": ["bug", "feature", "task", "support"],
    "priorities": ["low", "normal", "high", "urgent"],
    "severities": ["minor", "major", "critical", "blocker"],
    "required_fields": ["assignee"],
    "defaults": { "tracker": "task", "priority": "normal" }
  }
}
```

## Commands

```console
$ lifetxt ticket new "Login fails" --tracker bug --priority high --assignee alice --project web
$ lifetxt ticket list --tracker bug --open
$ lifetxt ticket show BUG-1
$ lifetxt ticket assign BUG-1 carol
$ lifetxt ticket edit BUG-1 --set severity=critical --set component=auth --unset milestone
$ lifetxt ticket link BUG-2 depends_on BUG-1
$ lifetxt ticket unlink BUG-2 depends_on BUG-1
$ lifetxt ticket close BUG-1 --status resolved --resolution "fixed in v2"
$ lifetxt ticket reopen BUG-1
$ lifetxt ticket validate
```

`ticket new` generates the next id from `id_prefix`. `ticket show` aggregates the
current record, its relations, and incoming links without modifying anything.
Transitions patch the ticket in one rewrite: `close` sets the terminal status,
`closed_by`, and any `--resolution`; `reopen` clears them.

## Validation

`ticket validate` reports:

- `TK001` ticket with no id
- `TK002` unknown `ticket_status`
- `TK003` `ticket_status` contradicts the coarse life.txt status
- `TK004` value not in a configured registry (tracker/priority/severity/component)
- `TK005` a configured required field is missing

## MCP

Read-only tools: `list_tickets`, `get_ticket`, `validate_tickets`. Ticket
writes go through the CLI (workflow-enforced remote writes are a later track).
Tickets follow `ticket-v1.schema.json`; the field registry follows
`ticket-field-registry-v1.schema.json`.
