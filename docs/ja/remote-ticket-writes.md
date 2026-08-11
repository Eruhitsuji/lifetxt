# Remote ticket mutations

Remote protocol version 2 は、履歴を保つために範囲を絞った ticket mutation endpoint を公開できます。この endpoint は default では disabled で、server に設定された writable `life.txt` source だけを書き換えます。

## Adapter を有効にする

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

`remote.ticket_writes_enabled` の変更後は server restart が必要です。この設定は general Web、MCP、attachment、planning、relation、watcher、multi-file writes を有効化しません。

CLI client では次の command で effective write policy を確認できます。

```sh
lifetxt remote permissions PROFILE
```

この report は、authenticated principal の scopes、server の `mutation_policy.ticket_mutations_enabled`、advertised operations、denial reasons を組み合わせます。profile が ticket を読めても、書き込めるとは限りません。

## Endpoint と required headers

対応するすべての operation は次に送ります。

```text
POST /api/remote/v1/ticket-mutations
```

各 request には次が必要です。

- `X-Lifetxt-Remote-Version: 2` による Remote protocol 2
- authenticated `write` scope
- current Remote snapshot/resource revision を示す `If-Match`
- JSON body 内の caller-generated stable `transaction_id`
- `clock.require_remote_write_time` が enabled の場合は `X-Lifetxt-Client-Time`
- cookie authentication を使う場合は browser-session CSRF token と allowed `Origin`

current aggregate revision は `GET /api/remote/v1/snapshot`、`GET /api/remote/v1/resources`、または別の Remote read response から読みます。server は通常の sidecar mutation lock を保持した状態で、writable ticket file に対して exact SHA-256 CAS も実行します。

CLI write client は post 直前に snapshot revision を取得し、`If-Match` として送ります。conflict を自動 retry しません。conflict 時は attempted change と next actions (refresh、abandon、submit_new_transaction) を含む structured `REMOTE_MUTATION_CONFLICT` を返します。

すべての operation は `dry_run: true` も受け付けます。dry-run request も通常の protocol、authentication、authorization、capability、revision admission checks を通ります。server 側で ticket writes が disabled なら、dry-run も real write と同じように拒否されます。admission が成功した場合、authoritative file は byte-identical のままで、response は proposed result を返します。

## Supported operations

### Create

Remote creation では、lost response を安全に retry できるよう explicit stable ticket ID が必要です。

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

ticket と `record:ticket_event event:created` record は、1 回の exact-revision file replacement で append されます。

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

最初の contract が受け付けるのは、保守的に選ばれた scalar planning/assignment fields だけです。project、visibility、owner、reporter、watcher、relation、attachment、arbitrary custom-field、raw status changes は受け付けません。

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

authenticated Remote role は `ticketing.workflow` に対して評価されます。event author は authenticated principal です。client は別 actor を impersonate できません。

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

`record:ticket_event event:time_entry` と `record:time_entry` は、ticket operation と一緒に append されます。correction は `corrects` で earlier time entry を参照できます。

## Retry と conflict behavior

committed event は Remote operation と normalized request hash を保存します。同じ `transaction_id` と同じ body を繰り返すと、caller が最初の response を受け取れなかった場合でも existing result を `replayed: true` として返します。同じ ID を別 body に再利用すると `REMOTE_TRANSACTION_REUSED` で失敗します。

missing/stale `If-Match` values は mutation 前に失敗します。target-file race も per-file CAS で拒否されます。validation、workflow、history、custom-field、timestamp、time-entry failures は authoritative bytes を変更しません。

## Current boundaries

この最初の writable Remote contract は意図的に限定されています。

- configured writable `life.txt` source は exactly one
- cross-file ticket/event/time/planning transactions はない
- Remote version/sprint mutations はない
- bulk ticket mutation はない
- relation、watcher、attachment、timer-side-effect、provider-side-effect mutation はない
- MCP write tools はない
- multi-worker browser-session sharing や production readiness は主張しない

write 前には capability discovery を使ってください。protocol-v2 capabilities は `mutation_policy.ticket_mutations_enabled`、exact operation list、remaining limitations を publish します。

## CLI と interactive client

dependency-free CLI client は同じ endpoint を wrap します。

```sh
lifetxt remote ticket-create PROFILE WEB-42 "Fix remote login" --project web --dry-run
lifetxt remote ticket-edit PROFILE WEB-42 --set priority=urgent --comment "Incident review"
lifetxt remote ticket-transition PROFILE WEB-42 review --comment "Ready for review"
lifetxt remote ticket-comment PROFILE WEB-42 "Root cause identified"
lifetxt remote ticket-log-time PROFILE WEB-42 90m --activity development --date 2026-07-26
```

`lifetxt remote tui PROFILE --interactive` は simple text-mode remote ticket review/proposal loop です。visible tickets を list し、detail を表示し、write を submit する前に explicit `y/N` confirmation を求めます。curses-based local `lifetxt tui` app とは別です。
