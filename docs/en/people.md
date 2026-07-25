# Person and Group Overviews

lifetxt collects everything about a person into one view — assigned work,
authored and received messages, meetings, presence, projects, waiting items, and
team/group memberships — by reusing the project, group, delivery, and status
logic rather than duplicating records. Names resolve through the configured user
aliases, so `me` and `self` (or any declared alias) refer to the same person.

## Commands

```console
$ lifetxt person list          # everyone seen, with counts
$ lifetxt person show alice    # one person's full overview
$ lifetxt person group eng     # a group's members and their workload
```

`person show` reports, for the resolved person:

- **presence** — latest active status record
- **assigned / waiting / overdue** — open tasks and deadlines they own or are assigned
- **messages sent / received** — as sender or recipient
- **meetings** — events they attend
- **projects** — projects they own or have assigned tasks in
- **memberships** — teams and groups that include them

`person group` expands the group deterministically and shows each member's open
work, overdue count, and received messages, plus group totals.

## Aliases

With

```json
{ "user": { "name": "self", "aliases": ["me"] } }
```

`lifetxt person show me` and `lifetxt person show self` produce the same
overview, and work assigned to `me` folds into `self` in `person list`.

## MCP

AI clients use read-only `list_people`, `get_person`, and `get_group_overview`,
reusing the same aggregation as the CLI. The person overview follows
`person-overview-v1.schema.json`.
