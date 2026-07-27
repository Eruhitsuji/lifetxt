# Read and edit server data from the Remote CLI and TUI

Remote protocol version 2 lets a client inspect visible server data and lets only authorized principals execute the deliberately limited ticket mutation contract. Profiles store an environment-variable name for the Bearer token, never the token value itself.

## Inspect effective permissions

```console
lifetxt remote permissions home
```

The response includes the authenticated principal, role, scopes, project/group/visibility grants, server read-only state, write admission, denial reasons, negotiated protocol information, capability revision, and the exact operations published by the server.

The standard roles are designed as follows:

- `reader` can inspect authorized server data.
- `editor` has `read` and `write` scopes and may execute ticket operations that the server enables.
- `auditor` may inspect audit surfaces but cannot mutate data without `write` scope.
- `owner` has read, write, admin, and audit scopes.

The final decision also applies project, group, visibility, server read-only mode, and `remote.ticket_writes_enabled` restrictions. The client reports machine-readable denial reasons such as `principal_missing_write_scope`, `ticket_mutations_disabled`, and `no_ticket_operations_advertised` rather than treating every denial as the same condition.

## Read through the CLI

```console
lifetxt remote snapshot home
lifetxt remote resources home
lifetxt remote get home tickets --param project=web --param status=review
lifetxt remote ticket-show home WEB-42
lifetxt remote diagnose home
```

`ticket-show` searches the same permission-filtered snapshot used for Remote writes. It returns the aggregate revision together with the visible ticket. It cannot reveal a ticket excluded by project, group, visibility, or principal filtering.

## Mutate tickets through the CLI

Each command obtains the current aggregate revision immediately before the request and sends it through `If-Match`. The client never overwrites a conflict automatically. Supply a stable `--transaction-id` and reuse it only when retrying the identical operation after a lost response.

```console
lifetxt remote ticket-create home WEB-42 "Fix remote login" \
  --project web --tracker bug --priority high \
  --transaction-id remote-create-WEB-42

lifetxt remote ticket-edit home WEB-42 \
  --set priority=urgent --set assignee=alice \
  --unset milestone \
  --comment "Reprioritized after incident review" \
  --transaction-id remote-edit-WEB-42-priority

lifetxt remote ticket-transition home WEB-42 review \
  --comment "Implementation is ready" \
  --transaction-id remote-transition-WEB-42-review

lifetxt remote ticket-comment home WEB-42 "Root cause confirmed" \
  --transaction-id remote-comment-WEB-42-root-cause

lifetxt remote ticket-log-time home WEB-42 90m \
  --activity development --date 2026-07-27 \
  --comment "Implemented the fix" \
  --transaction-id remote-time-WEB-42-01
```

All mutation commands accept `--dry-run`. A dry run must still pass authentication, authorization, input validation, and the exact revision precondition, but it does not replace authoritative data.

### Revision conflicts

When the server reports `REVISION_CONFLICT`, `STALE_REVISION`, `PRECONDITION_FAILED`, or `REVISION_REQUIRED`, the client:

1. does not retry the mutation;
2. fetches a new permission-filtered snapshot;
3. reports the requested and current aggregate revisions;
4. provides a bounded comparison of requested fields with the currently visible ticket;
5. reports the permitted next actions as `refresh`, `abandon`, or `submit_new_transaction`.

The non-interactive CLI writes the structured conflict to standard error and returns exit code `3`. A new mutation should use a new transaction ID. Reuse the old transaction ID only for an identical request whose response may have been lost.

## Use the TUI

The existing snapshot view remains read-only:

```console
lifetxt remote tui home
```

Use the interactive mode for a continuous permission-aware session:

```console
lifetxt remote tui home --interactive
```

The interactive TUI provides `show`, `refresh`, and `quit` for every authenticated principal. `show` displays one visible ticket and the snapshot revision. `refresh` reloads the filtered snapshot without changing data.

A principal without write permission remains read-only but can continue using `show` and `refresh`. An authorized principal can select only operations advertised by the server. Before a write, the TUI displays the complete proposed operation and payload and requires explicit confirmation. After a successful mutation it refreshes the snapshot. After a revision conflict it displays the structured conflict, refreshes visible data, and returns to the operation loop without automatically resubmitting anything.

## Server configuration example

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
      },
      {
        "id": "bob",
        "role": "reader",
        "token_env": "LIFETXT_REMOTE_BOB_TOKEN",
        "projects": ["web"],
        "visibilities": ["public", "shared"]
      }
    ]
  }
}
```

Alice may read and mutate tickets within the permitted project and visibility set. Bob can inspect the same authorized data but the server rejects mutations because the principal lacks `write` scope.

## Current boundary

The client exposes only the server's single-source `create`, `edit`, `transition`, `comment`, and `log_time` ticket operations. It does not enable arbitrary file editing, raw source replacement, relations, watchers, attachments, versions, sprints, bulk changes, or multi-file Remote transactions.
