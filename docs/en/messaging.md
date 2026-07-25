# Groups, Messaging, and Delivery State

lifetxt turns a flat list of people into resolvable groups, composes messages to
mixed people/teams/groups, and tracks per-recipient acknowledgement — all from
life.txt records and configuration, with no separate store to drift.

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

Expansion is deterministic: duplicates and disabled members are removed, cycles
are detected (not looped), and unknown members are reported. Inspect groups:

```console
$ lifetxt group list
$ lifetxt group show eng
$ lifetxt group validate
```

Diagnostics: `G001` unknown group, `G002` cycle, `G003` empty/no recipients.

## Recipient resolution

Preview exactly who a set of references expands to before sending:

```console
$ lifetxt message recipients "group:eng,erin"
```

The result keeps both the original references and the resolved recipient set, so
an audit trail records what was targeted while the message stays readable.

## Composing messages

```console
$ lifetxt message send "Deploy tonight" --to "eng,erin" --ack-policy all
$ lifetxt message send "Ping" --to "oncall" --sender alice --dry-run
```

The written Message item lists resolved people as `recipient:` and preserves the
original group/team references as `group:` for audit. `--ack-policy` accepts
`any` (default), `all`, or an explicit count.

## Delivery state

Delivery state is derived from the message record itself: `ack:` marks
acknowledgement, `read:` marks read, `skip:` marks skipped. Each recipient maps
to a `delivery-state-v1` record (pending / read / acknowledged / skipped).

```console
$ lifetxt message status
$ lifetxt message status --id M-9 --policy all
```

Acknowledgement policy decides completion: `any` completes when one recipient
acknowledges, `all` requires every non-skipped recipient, and a count requires
that many. One recipient acknowledging never completes an `all` message on its
own.

## MCP

AI clients use read-only `list_groups`, `resolve_recipients`, and
`get_delivery_state`, reusing the same expansion and delivery logic as the CLI.
