# Remote CLI／TUIからの参照・編集

Remote protocol version 2では、server上のvisible dataをCLIから参照し、権限があるprincipalだけが限定的なticket更新を実行できます。client profileにはsecret本体を保存せず、Bearer tokenを格納した環境変数名だけを保存します。

本ドキュメントは`lifetxt remote` CLI client（`lifetxt/remote_client_writes.py`と`lifetxt/remote_client_writes_compat_v25.py`）とそのinteractive TUIを扱います。基盤となるread-only resource catalogについては[remote.md](remote.md)、このclientが話すwire-levelの`POST /api/remote/v1/ticket-mutations`契約については[remote-ticket-writes.md](remote-ticket-writes.md)、`lifetxt remote test`が報告するcapability negotiationについては[remote-compatibility.md](remote-compatibility.md)を参照してください。

## 権限の確認

```console
lifetxt remote permissions home
```

このコマンドは、認証中principalのID、role、scope、project／group／visibility grant、serverのread-only状態、ticket mutation可否、拒否理由、negotiated protocol、capability revision、serverが許可しているoperationを表示します。実際に稼働中のserverで確認したJSON形状は次のとおりです（抜粋）。

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

`editable_fields`と`create_fields`は、server側が実際に強制するリストと完全に同一です（`lifetxt/remote_ticket_write_core.py`の`EDIT_FIELDS`と、`remote_ticket_capability_v26.py`にハードコードされたcreate field一覧）。clientは`edit` operationがどのfieldを受け付けるか推測する代わりに、このresponseからformを構築したりlocalで検証したりできます。`field_contract_version`は、このfield集合が将来変更された場合にのみ変わります。

標準roleの想定は次のとおりです。

- `reader`: server上の許可されたdataを参照できます。
- `editor`: `read`と`write` scopeを持ち、server設定で有効なticket operationを実行できます。
- `auditor`: audit surfaceを参照できますが、write scopeがなければ編集できません。
- `owner`: read、write、admin、auditを持ちます。

最終的な許可はroleだけでなく、principalのscope、project、group、visibility制約、`remote.ticket_writes_enabled`、serverのread-only設定によって決まります。書き込みできない場合は、`principal_missing_write_scope`、`ticket_mutations_disabled`、`no_ticket_operations_advertised`などの機械可読な理由を返します。実機で確認したとおり、`write` scopeを持たない`reader` roleのprincipalが`permissions`を要求すると、`can_read`は`true`のままで`"can_write": false`かつ`"denial_reasons": ["principal_missing_write_scope"]`が返ります -- readとwriteは1つの結合したgrantではなく、独立して評価されます。

## CLIから参照する

```console
lifetxt remote snapshot home
lifetxt remote resources home
lifetxt remote get home tickets --param project=web --param status=review
lifetxt remote ticket-show home WEB-42
lifetxt remote diagnose home
```

`ticket-show`はRemote更新時と同じ権限フィルター済みsnapshotからticketを検索し、aggregate revisionとvisible ticketを返します。project、group、visibility、principal制約で除外されたticketを表示することはありません。

`lifetxt remote diagnose home`は固定されたcheck一覧（`remote-enabled`、`https-policy`、`principal-registry`、`source-count`、`browser-session`、`authoritative-remote-writes`）とfree-textの`warnings`を返します。`remote.ticket_writes_enabled: true`かつticket mutationが実際に成功しているserverに対して確認したところ、`authoritative-remote-writes` checkは常に`{"ok": false, "admission_only": true}`を返し続けており、routeの集約`ok`計算自身がこのcheckだけを名前で除外しています（`lifetxt/remote_web.py`）。このcheckは`remote.ticket_writes_enabled`を参照しておらず、ticket writeが有効かどうかの確認には使えません -- 代わりに`lifetxt remote permissions PROFILE`の`ticket_mutations_enabled`か、`lifetxt remote test PROFILE`の`capabilities.mutation_policy.ticket_mutations_enabled`を使用してください。

## CLIからticketを編集する

すべての更新は、更新直前に取得したRemote aggregate revisionを`If-Match`へ設定します。競合時にclientが自動上書きすることはありません。`--transaction-id`はすべてのmutation subcommandでoptionalです。省略した場合、client側でランダムなUUID4が生成されます（`mutate_ticket()`内の`uuid.uuid4()`）。安定した意味のあるIDを自分で指定し、response lostが疑われる同一requestを再試行するときだけ再利用してください -- 呼び出しのたびにランダムなIDを生成すると、このparameterが本来提供する再試行安全性が失われます。

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

各更新コマンドは`--dry-run`を受け付けます。dry runでもserver側の認証、権限、入力、revision preconditionを通過する必要がありますが、authoritative dataは変更しません。実機で確認したところ、`--dry-run`のeditに対するresponseには計算済みの完全な結果（書き込まれるはずだったticket状態とeventが`"dry_run": true`とともに）が含まれますが、最上位の`revision_before`と`revision_after`は同一のままです -- aggregate revisionは実際に動いておらず、dry run前後で`life.txt`をbyte比較しても変化がないことを確認しました。

### 実際に書き込まれる内容

承認されたmutationはすべて1件の`record:ticket_event`行を追記し、`log_time`はさらに`record:time_entry`行を、ticket行の変更と同じexact-revisionファイル置換の中で追記します。実際のworkspaceで確認したところ、editのeventには通常のticket-event形状に加えて、Remote由来であることを示す3つのfieldが含まれます。

```text
[N] N Ticket_WEB-42_field_change record:ticket_event id:EV-WEB-42-000001 parent:WEB-42
  event:field_change author:alice at:2026-08-10T10:18:10Z transaction:remote-edit-WEB-42-priority
  change:"{\"field\":\"priority\",\"before\":[\"high\"],\"after\":[\"urgent\"]}"
  remote_operation:edit remote_request_hash:6e4e222e73d92c6c... remote_role:editor
```

`author`は常に認証済みprincipalです（`request_scope`／`require_scope`は呼び出し元が別のactorを詐称することを一切許しません -- 詳細は[remote-ticket-writes.md](remote-ticket-writes.md)参照）。`remote_operation`と`remote_role`により、履歴を読むだけでRemote由来の変更をlocal CLI／Web／MCPの変更と区別できます。`remote_request_hash`は、後述するreplay検出にserverが使うのと同じ正規化済みrequest hashです。

`--visibility`や明示的なownerを指定せずに`ticket-create`でticketを作成した場合の既定値も確認済みです。serverは`visibility: shared`を設定し、`owner`／`reporter`は認証済みprincipal自身のIDになります（`lifetxt/remote_ticket_write_operations.py`）。`role`が`owner`のprincipalだけが他人をownerとするticketを作成でき、それ以外のroleは`REMOTE_TICKET_FIELD_FORBIDDEN`になります。

### Replayとtransaction ID再利用

まったく同じ`--transaction-id`とまったく同じ引数を繰り返すと、既にcommit済みの結果が`"replayed": true`とともに返され、`life.txt`へ再度書き込まれることはありません -- 同一の`ticket-edit`を2回実行して確認したところ、2回目のresponseでは`revision_before`と`revision_after`が一致（新しいcommitなし）していたのに対し、1回目は両者が異なっていました。

同じ`--transaction-id`を**異なる**引数で再利用すると、それとは別の、確認済みの失敗パターンになります。serverは`REMOTE_TRANSACTION_REUSED`（HTTP 409）で正しく拒否しますが、このcodeは後述する4つのconflict codeに含まれないため、CLIには捕捉されません。結果として、構造化されたJSONをstderrへ出力してexit code `3`を返すのではなく、Pythonの完全なtracebackがstderrへ出力され、通常のexit code `1`になります。exit code `3`だけを確認するscriptはこのケースを検出できません。stderrに`REMOTE_TRANSACTION_REUSED`が含まれていないかも確認するか、変更後のrequestでtransaction IDを再利用しないようにしてください。

この「未処理の`RuntimeError`、exit code `1`、stderrへの完全なtraceback」という形は、conflict以外のserver拒否すべてに当てはまります。`reader` roleのprincipalによる書き込み試行（`FORBIDDEN`）、`editable_fields`に含まれないfieldを指定した`ticket-edit --set project=...`（`REMOTE_TICKET_FIELD_FORBIDDEN`）、既定の`ticketing.workflow`で`in_progress`を経由しないと許可されない`new -> review`のような不正なworkflow transition（`REMOTE_TICKET_INVALID`、`lifetxt ticket workflow`の既定値に対して確認済み）などです。これらはいずれもconflictではなく、下記「Revision競合」で説明する丁寧な表示にはなりません。

### Revision競合

serverが`REVISION_CONFLICT`、`STALE_REVISION`、`PRECONDITION_FAILED`、`REVISION_REQUIRED`を返した場合、clientは次の処理を行います。

1. mutationを自動再試行しません。
2. 権限フィルター済みsnapshotを再取得します。
3. request時と現在のaggregate revisionを表示します。
4. request fieldと現在visibleなticketとのbounded comparisonを表示します。
5. 次の操作として`refresh`、`abandon`、`submit_new_transaction`を提示します。

non-interactive CLIは構造化された競合情報をstandard errorへ出力し、exit code `3`を返します。内容を変更して再送する場合は新しいtransaction IDを使用してください。古いtransaction IDを再利用できるのは、responseが失われた可能性がある完全に同一のrequestだけです。

実機でstale revisionを強制して確認したところ、実際にstderrへ出力される`RemoteMutationConflict.as_dict()`は次の形状です。

```json
{
  "error": "REMOTE_MUTATION_CONFLICT",
  "message": "Remote data changed before the mutation could be committed.",
  "expected_revision": "<clientが送ったstale revision>",
  "current_revision": "<serverの実際の現在aggregate revision>",
  "attempted_change": {"operation": "edit", "ticket_id": "WEB-42", "set": {"priority": "low"}},
  "current_item": {"status": "[/]", "title": "Fix_remote_login", "details": {"priority": ["urgent"], "...": "..."}},
  "automatic_retry": false,
  "next_actions": ["refresh", "abandon", "submit_new_transaction"],
  "server_detail": {"error": "REVISION_CONFLICT", "detail": {"...": "serverのconflict-v1.schema.json形状のpayload"}}
}
```

`attempted_change`はclientがcommitしようとした正規化済みrequestです（serverでの計算方法は[remote-ticket-writes.md](remote-ticket-writes.md)参照）。`current_item`は同じ権限フィルターを通した現在のticketそのものであり、principalがそのticketをまったく参照できなくなった場合（例えば別の誰かが`project`や`visibility`を変更した場合）は`null`になります。`server_detail`には生のserver responseがそのまま入れ子になっているため、clientが自分のfieldへ再構成しても、元の`conflict-v1.schema.json` payloadの情報は失われません。

## TUIから参照・編集する

従来のread-only snapshot表示はそのまま使用できます。

```console
lifetxt remote tui home
```

継続的な対話操作を行う場合は次を使用します。

```console
lifetxt remote tui home --interactive
```

interactive TUIでは、すべての認証済みprincipalが`show`、`refresh`、`quit`を使用できます。`show`はvisible ticketとsnapshot revisionを表示し、`refresh`はdataを変更せずに権限フィルター済みsnapshotを再取得します。

write権限がないprincipalもread-onlyのまま`show`と`refresh`を利用できます。write権限がある場合は、server capabilityに含まれるoperationだけを選択できます。更新前にoperationとpayload全体を表示し、authoritative mutation直前に明示確認を要求します。成功後はsnapshotを再取得します。revision競合時は構造化された競合内容を表示してvisible dataをrefreshし、自動再送せずoperation loopへ戻ります。

scriptedなsession（`show` -> ticket ID -> `quit`、続いて`comment` -> ticket ID -> comment本文 -> `y`）で確認した実際の出力です。

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

このtranscriptだけでは分かりにくい挙動が2つあります。1つ目は、write用のinteractive prompt sequence（`_operation_payload()`）がtransaction IDを一切尋ねないことです。常に新しいランダムなUUID4が生成されるため、interactive TUI自体は以前のwriteをreplayできません -- 失敗したinteractive mutationを再試行すると、必ず新しいtransactionになります。2つ目は、serverが公開していないoperationを入力した場合（例えば`reader`が`comment`と入力した場合）、requestは一切試行されないことです。TUIは`Operation is not allowed by the server: comment`と表示してpromptへ戻るため、拒否されるはずのwriteがnetworkへ届くことはありません。

## Server設定例

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

`alice`は許可されたproject／visibility範囲のticketを参照・更新できます。`bob`は同じ範囲を参照できますが、write scopeがないため更新は拒否されます。まさにこの設定に対して実機で確認したところ、`bob`の`ticket-comment`requestはHTTP 403 `{"error": "FORBIDDEN", "message": "Principal lacks write scope."}`を返し、mutationが評価されることすらありません -- このscope checkはroute handler内の他のどの検証よりも先に行われます（`lifetxt/remote_ticket_writes.py`）。

両principal用のprofileは同じ方法で登録します（一致する`token_env`名は、profile fileではなくCLIを実行する環境の環境変数に設定します）。

```console
lifetxt remote profile-set home http://127.0.0.1:8080 --token-env LIFETXT_REMOTE_ALICE_TOKEN
lifetxt remote profile-set home-readonly http://127.0.0.1:8080 --token-env LIFETXT_REMOTE_BOB_TOKEN
```

## 現在の境界

Remoteから直接更新できるのは、serverが公開するsingle-source ticket mutation contractの`create`、`edit`、`transition`、`comment`、`log_time`だけです。任意file編集、raw source置換、relation、watcher、attachment、version／sprint、bulk、multi-file transactionはこのclientから有効化しません。attachmentには別のRemote契約があります -- [delegated-remote-attachments-and-recovery.md](delegated-remote-attachments-and-recovery.md)を参照してください。
