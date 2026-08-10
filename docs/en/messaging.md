# Groups, Messaging, and Delivery State

lifetxt turns a flat list of people into resolvable groups, composes messages to
mixed people/teams/groups, and tracks per-recipient acknowledgement — all from
life.txt records and configuration, with no separate store to drift. A message
is an ordinary `M`-type item; "sending" only ever means appending a validated
`[ ] M ...` line through the same atomic writer every other authoritative
mutation uses.

## Groups

Define groups under the `groups` configuration section. Members may be people,
teams (`team:name`), or other groups, so groups nest:

```json
{
  "teams":  { "platform": { "members": ["carol", "dave"] } },
  "groups": {
    "oncall": { "members": ["alice", "bob"], "disabled_members": ["bob"] },
    "eng":    { "members": ["oncall", "team:platform"], "aliases": ["engineering"] }
  }
}
```

`teams` is a separate config section (`lifetxt/config.py`'s `config_team_members`);
a team's members are always people, never groups, and a team can also be built
implicitly from `user.teams` / `users.<name>.teams` without a `teams` entry at
all — see [people.md](people.md#aliases) for how per-person config sections work.

Expansion is deterministic: duplicates and disabled members are removed, cycles
are detected (not looped), and unknown members are reported. Inspect groups:

```console
$ lifetxt group list
oncall               1 member(s), 1 disabled
eng                  3 member(s), 0 disabled

$ lifetxt group show eng
eng (3 resolved member(s)):
  - alice
  - carol
  - dave

$ lifetxt group validate
All groups are valid.
```

`group list`/`group show`/`group validate` all accept `--json` for the same
data as a structured document — `group show --json` also includes the group's
raw `definition` and any diagnostics.

### Diagnostics

| Code | Severity | Meaning |
| --- | --- | --- |
| `G001` | error | Reference names a group that is not defined. |
| `G002` | error | A group includes itself, directly or through nesting. |
| `G003` | warning | A group (or a reference to one) resolves to zero recipients — every member is unknown, disabled, or the group is empty. |

```console
$ lifetxt group show loop      # groups: {"loop": {"members": ["loop"]}}
loop (0 resolved member(s)):
  [ERROR] G002: Group cycle detected: loop -> loop.

$ lifetxt group validate       # groups: {"silent": {"members": ["alice"], "disabled_members": ["alice"]}}
[WARNING] G003: Group 'silent' is empty.
```

A cycle or an unknown-group reference stops expansion at that point rather than
looping or guessing; `expand_group` returns an empty list and records the
diagnostic instead (`lifetxt/groups.py`).

## Recipient resolution

Preview exactly who a set of references expands to before sending:

```console
$ lifetxt message recipients "group:eng,erin"
Resolved 4 recipient(s) from group:eng, erin:
  - alice
  - carol
  - dave
  - erin
```

The result keeps both the original references and the resolved recipient set
(`references`, `recipients`, `expansion`, `diagnostics` in `--json` output), so
an audit trail records what was targeted while the message stays readable. A
bare name with no `group:`/`team:`/`user:`/`person:` prefix is resolved
against the group directory and team directory first — a name that happens to
collide with a group or team name resolves as that group/team, not as a
literal person, unless it is explicitly prefixed (`person:name`).

Resolving a reference to an unknown group fails the same way `group show`
does:

```console
$ lifetxt message recipients "group:nosuch"
Resolved 0 recipient(s) from group:nosuch:
  [ERROR] G001: Unknown group 'nosuch'.
```

(`message recipients` exits 1 whenever any diagnostic is an error.)

## Composing messages

```console
$ lifetxt message send "Deploy tonight" --to "eng,erin" --ack-policy all
Appended message to life.txt (4 recipient(s)):
  [ ] M Deploy_tonight sender:self recipient:alice recipient:carol recipient:dave recipient:erin group:eng ack_policy:all

$ lifetxt message send "Ping" --to "oncall" --sender alice --dry-run
[ ] M Ping sender:alice recipient:alice group:oncall
```

The written Message item lists resolved people as `recipient:` (one `recipient:`
per person, deduplicated) and preserves the original group/team references as
`group:` for audit — only when a reference actually expanded to something other
than its own literal name; a plain person reference in `--to` produces no
`group:` detail. `--ack-policy` accepts `any` (default), `all`, or an explicit
count, and is only written as `ack_policy:` when it differs from `any`.
`--sender` defaults to the configured user (`user.name`, then
`defaults.person`, then `message.default_sender`, then the literal `self`).
`--body` appends `body:` with the same whitespace-to-underscore treatment as
the title. `--dry-run` prints the exact line without writing it; `--output`
appends to a specific file instead of the resolved write target.

`message send` refuses to write when recipient resolution fails or resolves
to nobody:

```console
$ lifetxt message send "Test" --to "group:nosuch" --dry-run
ERROR: G001 Unknown group 'nosuch'.

$ lifetxt message send "x" --to "group:silent"    # silent's only member is disabled
ERROR: No recipients resolved.
```

(Both exit 1 and never write to life.txt.)

### Writing Message items directly

`message send` is not the only way to create a Message item.
`lifetxt quick`/`lifetxt assist` (and `lifetxt new`, its alias) also accept
`--kind M` for a hand-authored item; in that path there is no group/team
expansion, but `apply_config_defaults_to_item` (`lifetxt/cli.py`) fills in
`sender:`, `channel:`, and `service:` from the `message` config section
(`message.default_sender`, `message.default_channel`, `message.default_service`)
when those details are not already present. Use `message send` when the
recipient set should come from groups/teams; use `quick`/`assist` when you are
writing out `recipient:` values by hand or attaching notification-timing
details (`notify_at:`, `notify_from:`/`notify_to:`) that `message send` has no
flags for.

### Validation

`lifetxt check` validates every `M` item independently of how it was written:

- `E205` — a Message item with no `sender:` (error; blocks a clean check).
- `E206` — a Message item with no `recipient:` (error). Repeat `recipient:` for
  multiple recipients; a single `recipient:` detail line never holds a
  comma-separated list.
- `W210` — only one of `notify_from:`/`notify_to:` is present.
- `W211` — `notify_to:` is earlier than `notify_from:`.
- `W212` — status `[N]` used on a Message item (workflow statuses are
  recommended instead).

```console
$ printf '[ ] M NoSenderOrRecipient\n' | lifetxt check
1: ERROR E205: Message items require sender:PERSON.
1: ERROR E206: Message items require recipient:PERSON. Repeat recipient: for multiple recipients.
```

## Delivery state

Delivery state is derived from the message record itself: `ack:` marks
acknowledgement, `read:` marks read, `skip:` marks skipped. Each recipient maps
to a `delivery-state-v1` record (pending / read / acknowledged / skipped) —
`delivered` and `failed` are also part of the schema's state enum but nothing
in this feature currently writes them; they are reserved for a future
delivery-transport integration.

```console
$ lifetxt message status
$ lifetxt message status --id M-9 --policy all
```

`message status` (like every command that reads items) accepts one or more
input paths and reads stdin when none are given. `--id` restricts to one
message's `id:` detail; `--policy` overrides the message's own `ack_policy:`
detail for that one report, without rewriting the file. `--json` emits the
full per-message summary (`message_id`, `title`, `recipient_count`, `counts`
by state, `acknowledgement`, `states`).

```console
$ lifetxt message status
Deploy_tonight [M-9] recipients=4 ack=2/3 (all) open
    alice            acknowledged
    carol            acknowledged
    dave             read
    erin             skipped
```

(for `... ack:alice ack:carol read:dave skip:erin ack_policy:all` on a
4-recipient message)

Acknowledgement policy decides completion: `any` completes when one recipient
acknowledges, `all` requires every non-skipped recipient, and a count requires
that many (capped at the non-skipped recipient count). One recipient
acknowledging never completes an `all` message on its own — skipped recipients
are excluded from both the numerator and denominator, so an `all` message can
still complete if every *non-skipped* recipient acknowledges.

### A caveat: `ack:` looks like a date/time key to `lifetxt check`

`ack` is one of the shared `DATE_OR_DATETIME_KEYS` (`lifetxt/model.py`), a list
used by every item kind, not only `M`. That rule predates delivery state and
exists for other uses of `ack:` (e.g. acknowledging a reminder). As a result,
`lifetxt check` emits `W203` for every `ack:PERSON` value on a Message item,
even though `delivery.py` deliberately reads `ack:` as a list of recipient
names for this feature:

```console
$ lifetxt check life.txt
life.txt:6: WARNING W203: ack: should use YYYY-MM-DD or YYYY-MM-DDTHH:MM, optionally with :SS, fractional seconds, and timezone.
```

Likewise `read:`, `skip:`, and `ack_policy:` are not in `KNOWN_KEYS` /
`MESSAGE_RECOMMENDED_KEYS` at all, so `check` reports them as `W106` ("custom"
key, preserved unchanged) rather than as unrecognized. None of these warnings
block `check`'s exit status (both are warnings, not errors) and delivery
tracking is unaffected either way — the item is still valid and
`message status` still reads it correctly — but do not expect a Message item
using `ack:`/`read:`/`skip:` to `check` completely clean.

## MCP

AI clients use read-only `list_groups`, `resolve_recipients`, and
`get_delivery_state`, reusing the same expansion and delivery logic as the CLI
(`lifetxt/mcp.py`). `resolve_recipients` accepts `to` as either a comma-joined
string or a list of references. `get_delivery_state` accepts the same `id`/
`policy` filters as `message status --id`/`--policy` and returns
`{"count": N, "messages": [...]}`. There is currently no MCP tool that sends a
message or mutates `ack:`/`read:`/`skip:` — composing and acknowledging stay
CLI/TUI/Web operations; see [inbox.md](inbox.md#mcp) for the Unified Inbox
tools AI clients use to *propose* new items (including Message items) for
human review instead of writing them directly.

See also [people.md](people.md) for the person/group overview that rolls
messages sent/received into a per-person and per-group summary.
