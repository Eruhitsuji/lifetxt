# Person and Group Overviews

lifetxt collects everything about a person into one view — assigned work,
authored and received messages, meetings, presence, projects, waiting items, and
team/group memberships — by reusing the project, group, delivery, and status
logic rather than duplicating records (`lifetxt/people.py`). Names resolve
through the configured user aliases, so `me` and `self` (or any declared
alias) refer to the same person. `person_overview`, `people_list`, and
`group_overview` are read-only, deterministic functions of the item set,
config, and a reference date — the CLI, MCP, and
[search.md](search.md)'s `find --type person` all call the same functions, so
they can never disagree about who is who.

## Commands

```console
$ lifetxt person list          # everyone seen, with counts
alice                open=1 messages=1 meetings=1
bob                  open=1 messages=0 meetings=1
carol                open=0 messages=1 meetings=0
dave                 open=0 messages=1 meetings=0
erin                 open=0 messages=1 meetings=0
self                 open=0 messages=1 meetings=0

$ lifetxt person show alice    # one person's full overview
alice (al)
  presence: active 2026-08-10T08:00
  open=1 waiting=0 overdue=1 sent=0 received=1 meetings=1
  teams: -  groups: eng, oncall
  Assigned (open) (1):
    - [ ] Fix_login_bug @web due:2026-08-05
  Overdue (1):
    - [ ] Fix_login_bug @web due:2026-08-05
  Meetings (1):
    - [ ] Standup
  projects:
    - web (member, 1 task(s))

$ lifetxt person group eng     # a group's members and their workload
eng (3 member(s)) open=1 overdue=1
  alice                open=1 overdue=1 received=1
  carol                open=0 overdue=0 received=1
  dave                 open=0 overdue=0 received=1
```

All three subcommands accept input paths (or read stdin when none are given)
and `--json` for the full structured document.

`person show` reports, for the resolved person:

- **presence** — latest active status record (`S`-kind item whose `person:`
  matches; see [life_txt_format_spec.md](life_txt_format_spec.md) for the `S`
  kind)
- **assigned / waiting / overdue** — open `T` (Task) and `D` (Deadline) items
  where `assignee:` or `owner:` matches. **Only Task and Deadline count** — a
  Reminder, Habit, or Event assigned via `assignee:`/`owner:` is not counted
  here, even though those keys are technically valid on any kind. "Open" means
  status `[ ]`, `[/]`, or `[?]`; **waiting** is the `[?]` subset of assigned;
  **overdue** is the subset of assigned whose `due:` is before the reference
  date (today, unless the caller passes a different date)
- **messages sent / received** — `M`-kind items matched by `sender:` /
  `recipient:` respectively; see [messaging.md](messaging.md)
- **meetings** — `E`-kind items whose `attendee:` matches
- **projects** — projects (from [projects.md](projects.md)'s
  `collect_projects`) the person owns, or has at least one assigned task in;
  each row reports `owner` (bool) and `assigned_tasks` (count in that project)
- **memberships** — teams (`teams` config section, `user.teams`,
  `users.<name>.teams`) and groups (from [messaging.md](messaging.md#groups))
  that resolve to include them

A name that has never appeared anywhere still produces a valid, all-zero
overview rather than an error — `person show` does not validate that the name
exists:

```console
$ lifetxt person show nosuchperson life.txt
nosuchperson
  open=0 waiting=0 overdue=0 sent=0 received=0 meetings=0
```

`person group` expands the group deterministically and shows each member's
open work, overdue count, and received messages, plus group totals
(`total_assigned_open`, `total_overdue`). Unlike `person show`, `person group`
*does* validate the group name and fails loudly on an unknown one:

```console
$ lifetxt person group nosuch life.txt
ERROR: Unknown group 'nosuch'. Known: oncall, eng
```

(exit 1; the same `G001`-style failure `group show` and `message recipients`
report for an unknown group, though `person group` raises it as a plain
`ValueError` rather than a typed diagnostic.)

### `person list` also picks up presence-only people

`person list` counts everyone seen as `assignee:`/`owner:` on an open Task or
Deadline, `sender:`/`recipient:` on a Message, `attendee:` on an Event, **or**
`person:` on an `S` (status/presence) item — even with zero of the other
activity types:

```console
$ printf '[ ] S ghost_status person:ghost state:away from:2026-08-10T08:00\n' | lifetxt person list
ghost                open=0 messages=0 meetings=0
```

`person show`/`--json`'s `counts` object mirrors this same set of fields:
`assigned_open`, `waiting`, `overdue`, `messages_sent`, `messages_received`,
`meetings` — plus the top-level `presence`, `projects`, and `memberships`
fields that `person list`'s one-line-per-person summary does not include.

## Aliases

A person can have more than one name they're referred to by. The configured
user gets aliases from `user.aliases`; anyone else gets them from `users`:

```json
{
  "user": { "name": "self", "aliases": ["me"] },
  "users": { "alice": { "aliases": ["al"] } }
}
```

```console
$ lifetxt person show me
self (me)
  open=0 waiting=0 overdue=0 sent=1 received=0 meetings=0

$ lifetxt person show self
self (me)
  open=0 waiting=0 overdue=0 sent=1 received=0 meetings=0
```

`lifetxt person show me` and `lifetxt person show self` produce the same
overview (`resolve_person` maps every alias to its canonical name before
aggregating), and work assigned to `me` folds into `self` in `person list`.
This is the same canonical-name resolution `person show alice`/`person show
al` would both use for `alice` above — `person show alice` reports `alice
(al)` in its header, showing the other known alias.

`users.<name>.teams` (alongside the top-level `teams` config section and
`user.teams`) is one of the ways a person ends up as a team member without an
explicit `teams.<team>.members` entry — see
[messaging.md](messaging.md#groups) for how `teams` and `groups` compose.

## MCP

AI clients use read-only `list_people`, `get_person`, and `get_group_overview`,
reusing the same aggregation as the CLI (`lifetxt/mcp.py`; `get_person` and
`get_group_overview` raise `ValueError` on a missing `name` argument, and
`get_group_overview` on an unknown group name, matching the CLI's own error
behavior). The person overview follows `person-overview-v1.schema.json`.
