# Remote CLI／TUIからの参照・編集

Remote protocol version 2では、server上のvisible dataをCLIから参照し、権限があるprincipalだけが限定的なticket更新を実行できます。client profileにはsecret本体を保存せず、Bearer tokenを格納した環境変数名だけを保存します。

## 権限の確認

```console
lifetxt remote permissions home
```

このコマンドは、認証中principalのID、role、scope、project／group／visibility grant、serverのread-only状態、ticket mutation可否、拒否理由、negotiated protocol、capability revision、serverが許可しているoperationを表示します。

標準roleの想定は次のとおりです。

- `reader`: server上の許可されたdataを参照できます。
- `editor`: `read`と`write` scopeを持ち、server設定で有効なticket operationを実行できます。
- `auditor`: audit surfaceを参照できますが、write scopeがなければ編集できません。
- `owner`: read、write、admin、auditを持ちます。

最終的な許可はroleだけでなく、principalのscope、project、group、visibility制約、`remote.ticket_writes_enabled`、serverのread-only設定によって決まります。書き込みできない場合は、`principal_missing_write_scope`、`ticket_mutations_disabled`、`no_ticket_operations_advertised`などの機械可読な理由を返します。

## CLIから参照する

```console
lifetxt remote snapshot home
lifetxt remote resources home
lifetxt remote get home tickets --param project=web --param status=review
lifetxt remote ticket-show home WEB-42
lifetxt remote diagnose home
```

`ticket-show`はRemote更新時と同じ権限フィルター済みsnapshotからticketを検索し、aggregate revisionとvisible ticketを返します。project、group、visibility、principal制約で除外されたticketを表示することはありません。

## CLIからticketを編集する

すべての更新は、更新直前に取得したRemote aggregate revisionを`If-Match`へ設定し、stableな`transaction_id`を送信します。競合時にclientが自動上書きすることはありません。response lostが疑われる同一requestを再試行するときだけ、同じ`--transaction-id`を再利用してください。

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

各更新コマンドは`--dry-run`を受け付けます。dry runでもserver側の認証、権限、入力、revision preconditionを通過する必要がありますが、authoritative dataは変更しません。

### Revision競合

serverが`REVISION_CONFLICT`、`STALE_REVISION`、`PRECONDITION_FAILED`、`REVISION_REQUIRED`を返した場合、clientは次の処理を行います。

1. mutationを自動再試行しません。
2. 権限フィルター済みsnapshotを再取得します。
3. request時と現在のaggregate revisionを表示します。
4. request fieldと現在visibleなticketとのbounded comparisonを表示します。
5. 次の操作として`refresh`、`abandon`、`submit_new_transaction`を提示します。

non-interactive CLIは構造化された競合情報をstandard errorへ出力し、exit code `3`を返します。内容を変更して再送する場合は新しいtransaction IDを使用してください。古いtransaction IDを再利用できるのは、responseが失われた可能性がある完全に同一のrequestだけです。

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

`alice`は許可されたproject／visibility範囲のticketを参照・更新できます。`bob`は同じ範囲を参照できますが、write scopeがないため更新は拒否されます。

## 現在の境界

Remoteから直接更新できるのは、serverが公開するsingle-source ticket mutation contractの`create`、`edit`、`transition`、`comment`、`log_time`だけです。任意file編集、raw source置換、relation、watcher、attachment、version／sprint、bulk、multi-file transactionはこのclientから有効化しません。
