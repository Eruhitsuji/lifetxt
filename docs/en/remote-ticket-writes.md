# Remote ticket mutations

Remote protocol version 2 can expose a deliberately narrow, history-preserving ticket mutation endpoint. The endpoint is disabled by default and only writes to the server's configured writable `life.txt` source.

## Enable the adapter

```json
{
  "remote": {
    "enabled": true,
    "ticket_writes_enabled": true,
    "principals": [
      {
        "id": "alice",
        "role": "editor",
        "token_env": "LIFETXT_REMOTE_ALICE_TOKEN",
        "projects": ["web"],
        "visibilities": ["public", "shared"]
      }
    ]
  }
}
```

`remote.ticket_writes_enabled` requires a server restart. It does not enable general Web, MCP, attachment, planning, relation, watcher, or multi-file writes.
The CLI client reports the effective write policy with:

```sh
lifetxt remote permissions PROFILE
```

That report combines the authenticated principal's scopes with the server's
`mutation_policy.ticket_mutations_enabled`, advertised operations, and denial
reasons. A profile can read tickets and still be unable to write them.

## Endpoint and required headers

Send all supported operations to:

```text
POST /api/remote/v1/ticket-mutations
```

Every request requires:

- Remote protocol 2 through `X-Lifetxt-Remote-Version: 2`;
- authenticated `write` scope;
- the current Remote snapshot/resource revision in `If-Match`;
- a caller-generated stable `transaction_id` in the JSON body;
- `X-Lifetxt-Client-Time` when `clock.require_remote_write_time` is enabled;
- the browser-session CSRF token and an allowed `Origin` when cookie authentication is used.

Read the current aggregate revision from `GET /api/remote/v1/snapshot`, `GET /api/remote/v1/resources`, or another Remote read response. The server also performs an exact SHA-256 CAS against the writable ticket file while holding the normal sidecar mutation lock.
The CLI write client obtains the snapshot revision immediately before posting
and sends it as `If-Match`; it does not automatically retry a conflict. On a
conflict it returns a structured `REMOTE_MUTATION_CONFLICT` with the attempted
change and next actions: refresh, abandon, or submit a new transaction.

Every operation also accepts `dry_run: true`. Dry-run requests still perform the
normal protocol, authentication, authorization, capability, and revision
admission checks. If the server has ticket writes disabled, a dry-run is
rejected the same way a real write is rejected. When admission succeeds, the
authoritative file remains byte-identical and the response reports the proposed
result.

## Supported operations

### Create

Remote creation requires an explicit stable ticket ID so a lost response can be retried safely.

```json
{
  "operation": "create",
  "transaction_id": "remote-create-WEB-42",
  "ticket_id": "WEB-42",
  "subject": "Fix remote login",
  "tracker": "bug",
  "project": "web",
  "priority": "high",
  "visibility": "shared"
}
```

The ticket and its `record:ticket_event event:created` record are appended in one exact-revision file replacement.

### Edit fields

```json
{
  "operation": "edit",
  "transaction_id": "remote-edit-WEB-42-priority",
  "ticket_id": "WEB-42",
  "set": {
    "priority": "urgent",
    "assignee": "alice"
  },
  "unset": ["milestone"],
  "comment": "Reprioritized after incident review"
}
```

The first contract accepts only conservative scalar planning and assignment fields. It does not accept project, visibility, owner, reporter, watcher, relation, attachment, arbitrary custom-field, or raw status changes.

### Transition

```json
{
  "operation": "transition",
  "transaction_id": "remote-transition-WEB-42-review",
  "ticket_id": "WEB-42",
  "target_status": "review",
  "comment": "Implementation and tests are ready"
}
```

The authenticated Remote role is evaluated against `ticketing.workflow`. The authenticated principal becomes the event author; clients cannot impersonate another actor.

### Comment

```json
{
  "operation": "comment",
  "transaction_id": "remote-comment-WEB-42-root-cause",
  "ticket_id": "WEB-42",
  "body": "The session cookie path excluded the API prefix."
}
```

### Log time

```json
{
  "operation": "log_time",
  "transaction_id": "remote-time-WEB-42-20260726-01",
  "ticket_id": "WEB-42",
  "duration": "90m",
  "activity": "development",
  "date": "2026-07-26",
  "comment": "Implemented and tested the fix"
}
```

A `record:ticket_event event:time_entry` and a `record:time_entry` are appended with the ticket operation. Corrections may reference an earlier time entry through `corrects`.

## Retry and conflict behavior

Each committed event stores the Remote operation and a hash of the normalized request. Repeating the same `transaction_id` with the same body returns the existing result with `replayed: true`, even when the caller did not receive the first response. Reusing the ID for a different body fails with `REMOTE_TRANSACTION_REUSED`.

Missing or stale `If-Match` values fail before mutation. A target-file race is also rejected by the per-file CAS. Validation, workflow, history, custom-field, timestamp, and time-entry failures leave the authoritative bytes unchanged.

## Current boundaries

This first writable Remote contract is intentionally limited:

- exactly one configured writable `life.txt` source;
- no cross-file ticket/event/time/planning transactions;
- no Remote version or sprint mutations;
- no bulk ticket mutation;
- no relation, watcher, attachment, timer-side-effect, or provider-side-effect mutation;
- no MCP write tools;
- no claim of multi-worker browser-session sharing or production readiness.

Use capability discovery before writing. Protocol-v2 capabilities publish `mutation_policy.ticket_mutations_enabled`, the exact operation list, and all remaining limitations.

## CLI and interactive client

The dependency-free CLI client wraps the same endpoint:

```sh
lifetxt remote ticket-create PROFILE WEB-42 "Fix remote login" --project web --dry-run
lifetxt remote ticket-edit PROFILE WEB-42 --set priority=urgent --comment "Incident review"
lifetxt remote ticket-transition PROFILE WEB-42 review --comment "Ready for review"
lifetxt remote ticket-comment PROFILE WEB-42 "Root cause identified"
lifetxt remote ticket-log-time PROFILE WEB-42 90m --activity development --date 2026-07-26
```

`lifetxt remote tui PROFILE --interactive` is a simple text-mode remote ticket
review and proposal loop. It lists visible tickets, shows detail, and asks for
an explicit `y/N` confirmation before submitting a write. It is separate from
the curses-based local `lifetxt tui` app.
