# Read and edit server data from the Remote CLI and TUI

Remote protocol version 2 lets a client inspect visible server data and lets only authorized principals execute the deliberately limited ticket mutation contract. Profiles store an environment-variable name for the Bearer token, never the token value itself.

This document covers the `lifetxt remote` CLI client (`lifetxt/remote_client_writes.py` and `lifetxt/remote_client_writes_compat_v25.py`) and its interactive TUI. See [remote.md](remote.md) for the read-only resource catalog it builds on, [remote-ticket-writes.md](remote-ticket-writes.md) for the wire-level `POST /api/remote/v1/ticket-mutations` contract this client speaks, and [remote-compatibility.md](remote-compatibility.md) for the capability negotiation `lifetxt remote test` reports.

## Inspect effective permissions

```console
lifetxt remote permissions home
```

The response includes the authenticated principal, role, scopes, project/group/visibility grants, server read-only state, write admission, denial reasons, negotiated protocol information, capability revision, and the exact operations published by the server. Confirmed against a real running server, the JSON shape includes (trimmed):

```json
{
  "can_read": true,
  "can_write": true,
  "principal": {"id": "alice", "role": "editor", "scopes": ["read", "write"], "projects": ["web"], "visibilities": ["public", "shared"]},
  "grants": {"projects": ["web"], "groups": [], "visibilities": ["public", "shared"]},
  "ticket_mutations_enabled": true,
  "ticket_operations": ["create", "edit", "transition", "comment", "log_time"],
  "editable_fields": ["assignee", "branch", "build", "category", "component", "due", "est", "milestone", "priority", "severity", "sprint", "story_points", "version"],
  "create_fields": ["ticket_id", "subject", "tracker", "project", "priority", "visibility"],
  "field_contract_version": "1",
  "denial_reasons": [],
  "capability_revision": "7ffbde9edd..."
}
```

`editable_fields` and `create_fields` are the exact same lists the server enforces server-side (`lifetxt/remote_ticket_write_core.py`'s `EDIT_FIELDS` and `remote_ticket_capability_v26.py`'s hardcoded create-field list) -- a client can render a form or validate locally from this response instead of guessing which fields the `edit` operation accepts. `field_contract_version` changes only if that field set changes in a future release.

The standard roles are designed as follows:

- `reader` can inspect authorized server data.
- `editor` has `read` and `write` scopes and may execute ticket operations that the server enables.
- `auditor` may inspect audit surfaces but cannot mutate data without `write` scope.
- `owner` has read, write, admin, and audit scopes.

The final decision also applies project, group, visibility, server read-only mode, and `remote.ticket_writes_enabled` restrictions. The client reports machine-readable denial reasons such as `principal_missing_write_scope`, `ticket_mutations_disabled`, and `no_ticket_operations_advertised` rather than treating every denial as the same condition. Verified live: a `reader`-role principal (no `write` scope) requesting `permissions` gets `"can_write": false` and `"denial_reasons": ["principal_missing_write_scope"]` while `can_read` stays `true` -- read and write are evaluated independently, not as one combined grant.

## Read through the CLI

```console
lifetxt remote snapshot home
lifetxt remote resources home
lifetxt remote get home tickets --param project=web --param status=review
lifetxt remote ticket-show home WEB-42
lifetxt remote diagnose home
```

`ticket-show` searches the same permission-filtered snapshot used for Remote writes. It returns the aggregate revision together with the visible ticket. It cannot reveal a ticket excluded by project, group, visibility, or principal filtering.

`lifetxt remote diagnose home` reports a fixed set of named checks (`remote-enabled`, `https-policy`, `principal-registry`, `source-count`, `browser-session`, `authoritative-remote-writes`) plus free-text `warnings`. Verified against a real server with `remote.ticket_writes_enabled: true` and working ticket mutations already succeeding: the `authoritative-remote-writes` check still reports `{"ok": false, "admission_only": true}` unconditionally, and the route's own aggregate `ok` computation explicitly excludes that one check by name (`lifetxt/remote_web.py`). This check does not read `remote.ticket_writes_enabled` and cannot be used to confirm that ticket writes are enabled -- use `lifetxt remote permissions PROFILE`'s `ticket_mutations_enabled` field or `lifetxt remote test PROFILE`'s `capabilities.mutation_policy.ticket_mutations_enabled` instead.

## Mutate tickets through the CLI

Each command obtains the current aggregate revision immediately before the request and sends it through `If-Match`. The client never overwrites a conflict automatically. `--transaction-id` is optional on every mutation subcommand; when omitted, the client generates a random UUID4 for you (`uuid.uuid4()` in `mutate_ticket()`). Supply your own stable, meaningful ID and reuse it only when retrying the identical operation after a lost response -- a fresh random ID on every invocation defeats the retry-safety this parameter exists for.

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

All mutation commands accept `--dry-run`. A dry run must still pass authentication, authorization, input validation, and the exact revision precondition, but it does not replace authoritative data. Verified live: the response to a `--dry-run` edit includes the full computed result (the projected ticket state and event that would have been written, with `"dry_run": true`), but the top-level `revision_before` and `revision_after` fields are identical -- the aggregate revision genuinely did not move, and a byte comparison of `life.txt` before and after confirms it is untouched.

### What gets written

Every accepted mutation appends one `record:ticket_event` line, and `log_time` additionally appends a `record:time_entry` line, in the same exact-revision file replacement as the ticket line change. Confirmed against a real workspace, an edit's event carries three fields beyond the normal ticket-event shape that record the Remote origin of the change:

```text
[N] N Ticket_WEB-42_field_change record:ticket_event id:EV-WEB-42-000001 parent:WEB-42
  event:field_change author:alice at:2026-08-10T10:18:10Z transaction:remote-edit-WEB-42-priority
  change:"{\"field\":\"priority\",\"before\":[\"high\"],\"after\":[\"urgent\"]}"
  remote_operation:edit remote_request_hash:6e4e222e73d92c6c... remote_role:editor
```

`author` is always the authenticated principal (`request_scope`/`require_scope` never let a caller impersonate a different actor -- see [remote-ticket-writes.md](remote-ticket-writes.md)). `remote_operation` and `remote_role` make it possible to tell a Remote-originated change apart from a local CLI, Web, or MCP edit just by reading the history, and `remote_request_hash` is the same normalized-request hash the server uses for replay detection below.

Creating a ticket through `ticket-create` without `--visibility` or an explicit owner also has a verified default: the server sets `visibility: shared` and `owner`/`reporter` to the authenticated principal's own ID (`lifetxt/remote_ticket_write_operations.py`). Only a principal whose `role` is `owner` may create a ticket owned by someone else; every other role gets `REMOTE_TICKET_FIELD_FORBIDDEN`.

### Replay and transaction ID reuse

Repeating the exact same `--transaction-id` with the exact same arguments returns the already-committed result with `"replayed": true` and does not write to `life.txt` again -- confirmed live by running an identical `ticket-edit` twice: the second response's `revision_before` and `revision_after` are equal (no new commit) while the first pair differ.

Reusing the same `--transaction-id` with **different** arguments is a distinct, verified failure mode worth calling out: the server correctly rejects it with `REMOTE_TRANSACTION_REUSED` (HTTP 409), but this code is not one of the four conflict codes the CLI catches (see below), so it surfaces as an unhandled `RuntimeError` with a full Python traceback on stderr and plain exit code `1`, not the structured JSON-on-stderr/exit-`3` shape the next section describes. A script that only checks for exit code `3` will not catch this case; check stderr for `REMOTE_TRANSACTION_REUSED` too, or simply never reuse a transaction ID for a changed request.

The same "unhandled `RuntimeError`, exit code `1`, full traceback on stderr" shape also covers every other non-conflict server rejection: a `reader`-role principal attempting a write (`FORBIDDEN`), `ticket-edit --set project=...` naming a field outside `editable_fields` (`REMOTE_TICKET_FIELD_FORBIDDEN`), and an invalid workflow transition such as `new -> review` when the configured workflow requires passing through `in_progress` first (`REMOTE_TICKET_INVALID`, verified against the default `ticketing.workflow` -- see `lifetxt ticket workflow`). None of these are conflicts and none of them get the graceful presentation described in "Revision conflicts" below.

### Revision conflicts

When the server reports `REVISION_CONFLICT`, `STALE_REVISION`, `PRECONDITION_FAILED`, or `REVISION_REQUIRED`, the client:

1. does not retry the mutation;
2. fetches a new permission-filtered snapshot;
3. reports the requested and current aggregate revisions;
4. provides a bounded comparison of requested fields with the currently visible ticket;
5. reports the permitted next actions as `refresh`, `abandon`, or `submit_new_transaction`.

The non-interactive CLI writes the structured conflict to standard error and returns exit code `3`. A new mutation should use a new transaction ID. Reuse the old transaction ID only for an identical request whose response may have been lost.

Verified by forcing a stale revision against a real server, `RemoteMutationConflict.as_dict()` (what actually reaches stderr) has this shape:

```json
{
  "error": "REMOTE_MUTATION_CONFLICT",
  "message": "Remote data changed before the mutation could be committed.",
  "expected_revision": "<the stale revision the client sent>",
  "current_revision": "<the server's actual current aggregate revision>",
  "attempted_change": {"operation": "edit", "ticket_id": "WEB-42", "set": {"priority": "low"}},
  "current_item": {"status": "[/]", "title": "Fix_remote_login", "details": {"priority": ["urgent"], "...": "..."}},
  "automatic_retry": false,
  "next_actions": ["refresh", "abandon", "submit_new_transaction"],
  "server_detail": {"error": "REVISION_CONFLICT", "detail": {"...": "the server's own conflict-v1.schema.json-shaped payload"}}
}
```

`attempted_change` is the normalized request the client tried to commit (see [remote-ticket-writes.md](remote-ticket-writes.md) for how the server computes it), and `current_item` is the ticket exactly as it currently reads through the same permission filter -- it is `null` if the principal can no longer see the ticket at all (for example, someone else changed its `project` or `visibility` out from under the request). `server_detail` nests the raw server response so nothing about the underlying `conflict-v1.schema.json` payload is lost even though the client also reshapes it into its own fields.

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

Verified with a scripted session (`show` -> ticket ID -> `quit`, then a second run doing `comment` -> ticket ID -> comment text -> `y`):

```console
$ lifetxt remote tui home --interactive
lifetxt remote
principal: alice
role: editor
scopes: read, write
ticket writes: allowed
operations: create, edit, transition, comment, log_time
revision: fe6078dc...
[ticket] WEB-42           Fix_remote_login
operation [show/refresh/quit/create/edit/transition/comment/log_time]: show
ticket id: WEB-42
ticket: WEB-42
revision: fe6078dc...
priority: "urgent"
status: "[/]"
ticket_status: "review"
...
```

Two behaviors are not obvious from the transcript and are worth calling out. First, the interactive prompt sequence for a write (`_operation_payload()`) never asks for a transaction ID -- it always generates a fresh random UUID4 per mutation, so the interactive TUI cannot itself replay a previous write; retrying a failed interactive mutation always creates a new transaction. Second, entering an operation the server has not advertised (for example a `reader` typing `comment`) does not attempt the request at all: the TUI prints `Operation is not allowed by the server: comment` and returns to the prompt, so a denied write never reaches the network.

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

Alice may read and mutate tickets within the permitted project and visibility set. Bob can inspect the same authorized data but the server rejects mutations because the principal lacks `write` scope. Verified live against exactly this configuration: `bob`'s `ticket-comment` request returns HTTP 403 `{"error": "FORBIDDEN", "message": "Principal lacks write scope."}` before the mutation is ever evaluated -- the scope check happens ahead of every other validation in the route handler (`lifetxt/remote_ticket_writes.py`).

Register profiles for both principals the same way (each with the matching `token_env` name set in the environment the CLI process runs in, not in the profile file itself):

```console
lifetxt remote profile-set home http://127.0.0.1:8080 --token-env LIFETXT_REMOTE_ALICE_TOKEN
lifetxt remote profile-set home-readonly http://127.0.0.1:8080 --token-env LIFETXT_REMOTE_BOB_TOKEN
```

## Current boundary

The client exposes only the server's single-source `create`, `edit`, `transition`, `comment`, and `log_time` ticket operations. It does not enable arbitrary file editing, raw source replacement, relations, watchers, attachments, versions, sprints, bulk changes, or multi-file Remote transactions. Attachments have their own, separate Remote contract -- see [delegated-remote-attachments-and-recovery.md](delegated-remote-attachments-and-recovery.md).
