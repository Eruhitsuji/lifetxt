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

`ticket link`/`ticket unlink` accept any of the six relation keys: `parent`,
`depends_on`, `blocks`, `related`, `duplicate_of`, and `replaced_by`. Reciprocal
edges are never auto-generated -- setting `duplicate_of` on one ticket does not
write `replaced_by` on the other, matching how `depends_on`/`blocks` already work
as independent assertions:

```console
$ lifetxt ticket link BUG-3 duplicate_of BUG-1
$ lifetxt ticket link BUG-4 blocks BUG-1
```

`lifetxt check` (with or without `--config`) reports reference and cycle
diagnostics for every relation key on a ticket the same as it would for any
other item: missing references (`W215`), self references (`W216`), `parent:`
cycles (`W217`), ambiguous references (`W218`), combined `depends_on:`/`blocks:`
cycles (`W227`), `duplicate_of:` cycles (`W228`), and `replaced_by:` cycles
(`W229`). See docs/en/cli.md's `links` section (3.2) for the complete
reference/cycle-diagnostic catalog. `ticket validate` does not duplicate this
check; run plain `check` (or `links`) alongside `ticket validate` to catch a
relation cycle among tickets.

Typed custom fields (see below) are validated only by `ticket validate`
(`TK006`-`TK010`), not by the generic parser/validator: a ticket with a
configured `ticketing.custom_fields` entry still reports `W106` ("Detail key
... is custom for type T; it will be preserved.") under plain `lifetxt check`,
even when the same `--config` is passed to both commands. Use `ticket validate`
to get typed enforcement (range, enum, pattern, required/repeatable) for custom
fields; use `check`/`ticket validate` together for the complete picture on a
ticket file.

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


## Workflow, append-only history, and time

The audit-safe workflow commands use `ticket-workflow-v1`. The built-in graph
supports triage, assignment, work, review, testing, information/block states,
terminal resolution states, and reopening. Override or replace transitions under
`ticketing.workflow.transitions`; each transition can declare allowed source
states, roles, required fields, a required comment or resolution, fixed
set/unset side effects, and the event type to append.

```json
{
  "ticketing": {
    "activities": ["development", "review", "testing"],
    "workflow": {
      "local_role": "administrator",
      "transitions": {
        "review": {
          "from": ["in_progress", "testing"],
          "roles": ["developer", "manager"],
          "required_fields": ["pr"],
          "comment_required": true
        },
        "resolved": {
          "from": ["review", "testing"],
          "roles": ["manager"],
          "resolution_required": true,
          "event": "closed"
        }
      }
    }
  }
}
```

Inspect the effective graph before changing a ticket:

```console
$ lifetxt ticket workflow --role manager --format json --pretty
```

Audit-safe writes always require the exact revision of the file that owns the
ticket. They update the current ticket and append the required
`record:ticket_event` Note in one sidecar lock and one atomic replacement:

```console
$ REV=$(lifetxt ticket revision BUG-1)
$ lifetxt ticket transition BUG-1 in_progress \
    --revision "$REV" --actor alice --comment "Started" \
    --at 2026-07-25T10:00:00+09:00

$ REV=$(lifetxt ticket revision BUG-1)
$ lifetxt ticket comment BUG-1 "Root cause identified" \
    --revision "$REV" --author alice

$ REV=$(lifetxt ticket revision BUG-1)
$ lifetxt ticket reassign BUG-1 bob --revision "$REV" --actor alice
$ lifetxt ticket change BUG-1 --revision "$REV" --actor alice \
    --set severity=critical --unset milestone
$ lifetxt ticket watch BUG-1 carol --revision "$REV" --actor alice
$ lifetxt ticket unwatch BUG-1 carol --revision "$REV" --actor alice
```

Use `--dry-run` to calculate the generated event and post-write revision without
changing the file. `--transaction-id` supplies a stable retry/audit identifier;
a duplicate transaction is rejected. Event IDs and sequences are allocated
while the lock is held, so equal timestamps still have deterministic ordering.
A stale revision leaves both the ticket and history unchanged.

`ticket transition` also accepts `--role` (checked against the transition's
configured `roles`), `--resolution` (required by transitions with
`resolution_required`), and `--set`/`--unset`, so a status change and its
accompanying field updates commit in the same atomic write and the same
`field_change`-shaped event, instead of needing a separate `ticket change`
call:

```console
$ lifetxt ticket transition BUG-1 resolved \
    --revision "$REV" --actor alice --role manager \
    --resolution "fixed in v2" --set component=auth --unset milestone
```

Events use one of `EVENT_TYPES`:

```text
created, comment, transition, assignment, field_change, time_entry,
relation_added, relation_removed, commit_linked, pr_linked, build_failed,
build_passed, version_assigned, sprint_assigned, watch_added, watch_removed,
closed, reopened
```

`transition`, `comment`, `reassign`, `change`, `watch`/`unwatch`, and `plan`
(see below) emit `transition`/`closed`/`reopened` (via the default or
configured `event`), `comment`, `assignment`, `field_change`,
`watch_added`/`watch_removed`, and `version_assigned`/`sprint_assigned`
respectively. `commit_linked`, `pr_linked`, `build_failed`, and `build_passed`
are declared for use as a custom transition's `event` value (for future Git/CI
integration) but are not emitted by any built-in command today.

`record:ticket_event` records are append-only and include a stable ID, parent
ticket, event type, author, offset-aware UTC timestamp, per-ticket sequence,
transaction ID, source ticket revision, changed-field summaries, comment body,
and optional provider/reference context. Validate them with:

```console
$ lifetxt ticket activity BUG-1
$ lifetxt ticket validate-history --format json --pretty
```

`ticket validate-history` reports:

| Code | Meaning |
| --- | --- |
| `TK020` | event missing a required field (`id`, `parent`, `event`, `author`, `at`, `sequence`, `transaction`, `ticket_revision`) |
| `TK021` | unknown event type (not in `EVENT_TYPES`) |
| `TK022` | event `at` is not an ISO date-time with a UTC offset |
| `TK023` | event `sequence` is not a positive integer |
| `TK024` | event `parent` does not resolve to a known ticket |
| `TK025` | time entry missing a required field (`id`, `parent`, `user`, `activity`, `on`, `elapsed`, `sequence`, `event_id`, `created_at`) |
| `TK026` | time entry `on` is not `YYYY-MM-DD` |
| `TK027` | time entry `elapsed` is not a parseable duration |
| `TK028` | time entry `activity` is not in `ticketing.activities` |
| `TK029` | time entry `parent` does not resolve to a known ticket |
| `TK030`/`TK033` | duplicate `id` on a ticket event / time entry |
| `TK031` | duplicate `(parent, sequence)` pair among ticket events |
| `TK032` | duplicate `transaction` id among ticket events |
| `TK034` | time entry's `event_id` does not resolve to a known event |
| `TK035`/`TK036` | event/time-entry `id` does not match the `parent`+`sequence`-derived id |
| `TK037` | a correction's `--corrects` target is missing, or belongs to a different ticket |
| `TK038` | a correction targets itself, or a correction chain cycles |
| `TK039` | a ticket's event sequence has a gap (not a dense `1..N` run) |

`ticket validate-history` and `ticket validate-planning` (below) resolve their
input the same way as `check`: an explicit path, then configured `paths`, then
stdin. Unlike `ticket new`/`list`/`show`/`edit`/the workflow write commands
(which fall back to `life.txt` in the current directory when neither is given),
these two read-only validators silently read from stdin -- an empty stdin
produces a trivially clean "valid" result rather than an error or a check of
`life.txt`. Always pass an explicit path (or rely on configured `paths`) when
scripting these two commands.

The audit-safe commands are additive. Compatibility commands such as the older
`ticket edit|assign|close|reopen|link|unlink` remain available and do not claim
to append events. Workflows that require an audit trail should use
`ticket transition`, `ticket reassign`, `ticket change`, and the new comment,
watch, planning, and time commands.

Time is stored as append-only `record:time_entry` Notes:

```console
$ REV=$(lifetxt ticket revision BUG-1)
$ lifetxt ticket log-time BUG-1 90m \
    --revision "$REV" --user alice --activity development \
    --date 2026-07-25 --comment "Implemented validation"

$ lifetxt ticket time BUG-1 --format json --pretty
```

A correction is another immutable entry with `--corrects TIME-ID`. The newest
uncorrected entries are counted; referenced entries remain visible but are
superseded in the authoritative total. Legacy ticket `elapsed:` is returned
separately and is never double-counted. Timer/work-session conversion remains a
future proposal/transaction integration and is not performed implicitly.

## Versions, sprints, backlog, and roadmap

Versions and sprints are ordinary Notes marked `record:version` and
`record:sprint`. Their writes also require an exact file revision:

```console
$ REV=$(lifetxt ticket file-revision)
$ lifetxt version new "v1.0" --project web --due 2026-08-15 \
    --revision "$REV"

$ REV=$(lifetxt ticket file-revision)
$ lifetxt sprint new "Sprint 12" --project web \
    --start 2026-07-20 --end 2026-08-02 \
    --version VER-1 --capacity 30 --revision "$REV"

$ REV=$(lifetxt ticket revision BUG-1)
$ lifetxt ticket plan BUG-1 --sprint SPR-1 \
    --revision "$REV" --actor alice

$ lifetxt ticket backlog --project web
$ lifetxt ticket roadmap --project web --format json --pretty
```

Version states are `open`, `locked`, `released`, and `closed`; sprint states are
`planned`, `active`, and `closed`. Releasing/closing a version or closing a
sprint refuses unresolved members unless `--force` is supplied after reviewing
the scope/carry-over. Membership must stay within the ticket's project, sprint
capacity warnings use optional story points, and a sprint-associated version is
inferred during `ticket plan`.

```console
$ REV=$(lifetxt ticket file-revision)
$ lifetxt version release VER-1 --revision "$REV"
$ lifetxt sprint start SPR-1 --revision "$REV"
$ lifetxt sprint close SPR-1 --revision "$REV"
$ lifetxt ticket validate-planning
```

Every state transition is a dedicated subcommand rather than a `--state` flag:
`version close|release|lock|reopen` and `sprint start|close|reopen`. `reopen`
returns a version to `open` or a sprint to `planned`; only closing/releasing a
version and closing a sprint enforce the unresolved-members check above (a
version can be locked or reopened, and a ticket planned into it, without that
check running -- `lock` only signals intent, it does not freeze membership).

`version new` also accepts `--parent-version ID`, recorded as a plain
`parent_version` detail for chaining a version to its predecessor (for example
`v1.1`'s parent is `v1.0`); nothing currently reads it automatically, it is
descriptive metadata for future carry-over tooling.

`ticket plan` clears membership with `--clear-version`/`--clear-sprint` instead
of an empty `--version`/`--sprint` value:

```console
$ REV=$(lifetxt ticket revision BUG-1)
$ lifetxt ticket plan BUG-1 --clear-version --revision "$REV" --actor alice
```

`version list`/`show` and `sprint list`/`show` report each record's resolved
`state`, `due`/`release` or `start`/`end`, `parent_version` (versions) or
`capacity`/`version` (sprints), and the member ticket/open-ticket counts and
ids computed against the same input:

```console
$ lifetxt version show VER-1 life.txt --format json --pretty
$ lifetxt sprint list life.txt --project web
```

`ticket validate-planning` reports:

| Code | Meaning |
| --- | --- |
| `TK040` | version missing `id`/`project`/`state` |
| `TK041` | unknown version state |
| `TK042` | version `due`/`release` is not `YYYY-MM-DD` |
| `TK043` | sprint missing `id`/`project`/`state`/`start`/`end` |
| `TK044` | unknown sprint state |
| `TK045` | sprint `start`/`end` is not `YYYY-MM-DD` |
| `TK046` | sprint `end` is before `start` |
| `TK047` | sprint `capacity` is not a non-negative number |
| `TK048`/`TK049` | duplicate version id / duplicate sprint id |
| `TK050` | sprint references a missing version |
| `TK051`/`TK052` | ticket references a missing version / missing sprint |
| `TK053` | ticket's `version` conflicts with its `sprint`'s own `version` |

`version list`/`show`, `sprint list`/`show`, `ticket backlog`/`roadmap`, and
`ticket validate-planning` share the read-resolution caveat noted above for
`ticket validate-history`: without an explicit path or configured `paths` they
fall back to stdin, not `life.txt`. Verified: `lifetxt version list` run with
no arguments against a directory containing only an unconfigured `life.txt`
prints `No versions.` even when the file has versions, while
`lifetxt version list life.txt` correctly lists them.

The current implementation is atomic for records in the same authoritative
life.txt file. Split ticket/event/time/planning sources require revision sets
and the existing multi-target journal/recovery contract and are therefore not
advertised as writable yet. Remote ticket writes, authenticated role
enforcement, watcher delivery, and timer side effects also remain disabled.

Read-only MCP adds `get_ticket_workflow`, `get_ticket_activity`,
`get_ticket_time`, `get_ticket_planning`, `validate_ticket_history`, and
`validate_ticket_planning`. Capability discovery publishes the seven workflow,
event, time, and planning schemas plus the exact-revision and same-file compound
boundaries.

## Archiving a ticket's history

`lifetxt project archive NAME` (see docs/en/projects.md's Archiving section)
follows a done/canceled ticket's `record:ticket_event` and `record:time_entry`
Notes via their `parent:` reference and moves them to the configured archive
source in the same transaction as the ticket -- unconditionally, since history
records carry no status of their own and would otherwise never match the
archive candidate filter and be left behind as a dangling log. This history
linkage only runs for the project-filtered `project archive` command; the
generic `lifetxt archive` (no `--project`/project filter) does not scan for or
follow `record:ticket_event`/`record:time_entry` parents. Version and sprint
registry entries are not moved by either command; an archived ticket's
`version:`/`sprint:` detail values are left pointing at the still-active
registry record.
