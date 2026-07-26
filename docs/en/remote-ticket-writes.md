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
