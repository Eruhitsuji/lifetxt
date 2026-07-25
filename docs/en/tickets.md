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

Configured typed custom fields are stored as ordinary detail keys, so the
life.txt line remains readable and tools that do not know the registry continue
to preserve them.

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
    "defaults": { "tracker": "task", "priority": "normal" },
    "write": { "require_revision": true },
    "custom_fields": {
      "risk_score": {
        "type": "integer",
        "required": true,
        "default": 3,
        "minimum": 0,
        "maximum": 10,
        "filterable": true,
        "searchable": true,
        "privacy": "internal",
        "trackers": ["bug", "security"]
      },
      "customer_tier": {
        "type": "enum",
        "enum": ["free", "standard", "enterprise"],
        "default": "standard",
        "filterable": true,
        "privacy": "private",
        "editable_roles": ["manager"],
        "visible_roles": ["manager", "viewer"]
      },
      "security_label": {
        "type": "string",
        "repeatable": true,
        "pattern": "^[a-z0-9_-]+$",
        "privacy": "secret"
      }
    }
  }
}
```

`ticketing.write.require_revision` makes the exact source-file revision mandatory
for every existing ticket mutation. It is optional by default for backward-
compatible local use, but enabling it is recommended for scripts and any future
remote adapter.

## Typed custom fields

`ticketing.custom_fields` is a versioned, ticket-only registry. It does **not**
make unknown life.txt keys invalid globally. An unconfigured detail key is still
preserved and ignored by custom-field validation.

Supported types are `string`, `integer`, `number`, `boolean`, `date`, `datetime`,
`duration`, and `enum`. Definitions can also declare:

- `required`, `default`, and `repeatable`
- `enum`/`values`, numeric `minimum`/`maximum`, string `min_length`/`max_length`,
  and a regular-expression `pattern`
- tracker/project applicability through `trackers` and `projects`
- `filterable` and `searchable` metadata
- `privacy` as `public`, `internal`, `private`, or `secret`
- future role policy through `editable_roles` and `visible_roles`

Canonical, relation, and system ticket keys cannot be redefined as custom fields.
Defaults are applied when `ticket new` creates an applicable ticket. Existing
exact-revision mutations validate the resulting custom-field values while the
shared lock is held, so an invalid edit is rejected before replacement.

Inspect the effective registry and its diagnostics:

```console
$ lifetxt ticket fields
$ lifetxt ticket fields --tracker bug --project web --role manager --format json --pretty
```

Set fields while creating a ticket. Repeat `--field` for a repeatable definition:

```console
$ lifetxt ticket new "Login fails" --tracker bug --project web \
    --field risk_score=7 \
    --field customer_tier=enterprise \
    --field security_label=auth \
    --field security_label=cve
```

Existing tickets use normal `--set`/`--unset` operations and therefore retain the
same revision contract:

```console
$ lifetxt ticket edit BUG-1 --revision SHA256 --set risk_score=8
```

A custom field can be used by the dedicated list filter only when its definition
has `filterable: true`:

```console
$ lifetxt ticket list --field risk_score=8 --has-field customer_tier
```

`searchable` is published for future shared-query, Web, TUI, saved-view, and
remote adapters; it does not silently add a field to unrelated global-search
results. Privacy and role metadata are also published through capability
discovery, but remote ticket writes remain disabled until server-side permission,
history, clock, and recovery enforcement is complete.

## Commands

```console
$ lifetxt ticket new "Login fails" --tracker bug --priority high --assignee alice --project web
$ lifetxt ticket list --tracker bug --open
$ lifetxt ticket show BUG-1
$ lifetxt ticket revision BUG-1
$ lifetxt ticket assign BUG-1 carol
$ lifetxt ticket edit BUG-1 --set severity=critical --set component=auth --unset milestone
$ lifetxt ticket link BUG-2 depends_on BUG-1
$ lifetxt ticket unlink BUG-2 depends_on BUG-1
$ lifetxt ticket close BUG-1 --status resolved --resolution "fixed in v2"
$ lifetxt ticket reopen BUG-1
$ lifetxt ticket validate
```

`ticket new` generates the next id from `id_prefix`. `ticket show` aggregates the
current record, its configured custom fields, relations, and incoming links
without modifying anything. Transitions patch the ticket in one rewrite: `close`
sets the terminal status, `closed_by`, and any `--resolution`; `reopen` clears
them.

## Exact-revision writes

`ticket revision ID` prints the lowercase SHA-256 of the exact authoritative
source-file bytes containing the ticket. Pass that token to `edit`, `assign`,
`close`, `reopen`, `link`, or `unlink`:

```console
$ lifetxt ticket revision BUG-1
f28c83d4c0f17a3f...
$ lifetxt ticket edit BUG-1 --revision f28c83d4c0f17a3f... --set priority=urgent
Edited BUG-1 in life.txt
  revision: f28c83d4c0f17a3f... -> 74108639317b8870...
```

`--expected-revision` is an alias for `--revision`. A weak or quoted HTTP ETag is
also normalized to the same token. If the file changed after the token was read,
the command reports a conflict and leaves the newer bytes untouched. The check,
ticket lookup, semantic transform, validation, and replacement all use the
shared sidecar-lock/CAS mutation contract.

Use `--require-revision` to require a token for one command, or enable
`ticketing.write.require_revision` for all six mutation commands. `--dry-run`
still validates a supplied revision and prints the predicted post-write revision
without changing the file:

```console
$ lifetxt ticket link BUG-2 depends_on BUG-1 \
    --revision f28c83d4c0f17a3f... --dry-run
```

For machine-readable discovery, use:

```console
$ lifetxt ticket revision BUG-1 --json --pretty
```

The JSON object includes the ticket id, owning path, hash algorithm, and revision.

## Validation

`ticket validate` reports:

- `TK001` ticket with no id
- `TK002` unknown `ticket_status`
- `TK003` `ticket_status` contradicts the coarse life.txt status
- `TK004` value not in a configured registry (tracker/priority/severity/component)
- `TK005` a configured required field is missing
- `TK006` invalid custom-field registry metadata
- `TK007` a required applicable custom field is missing
- `TK008` a non-repeatable custom field has repeated values
- `TK009` a custom value violates its type or constraints
- `TK010` a custom field is present outside its configured tracker/project scope

## MCP

Read-only tools: `list_tickets`, `get_ticket`, `validate_tickets`. Ticket
writes go through the CLI (workflow-enforced remote writes are a later track).
Capability discovery publishes the local ticket revision and typed custom-field
contracts, but it does not advertise remote ticket writes as enabled. Tickets
follow `ticket-v1.schema.json`; the built-in field registry follows
`ticket-field-registry-v1.schema.json`; custom definitions follow
`ticket-custom-field-registry-v1.schema.json`.
