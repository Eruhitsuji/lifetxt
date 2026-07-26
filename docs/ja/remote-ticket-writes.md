# Remoteチケット更新

Remote protocol version 2では、履歴を必ず残す限定的なチケット更新エンドポイントを公開できます。このエンドポイントは既定で無効であり、サーバーに設定された書き込み対象の`life.txt`だけを更新します。

## アダプターの有効化

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

`remote.ticket_writes_enabled`の変更後はサーバーを再起動してください。この設定は、一般Web API、MCP、添付ファイル、計画、関連、watcher、複数ファイルの書き込みを有効にしません。

## エンドポイントと必須ヘッダー

対応する操作はすべて次へ送信します。

```text
POST /api/remote/v1/ticket-mutations
```

各リクエストには次が必要です。

- `X-Lifetxt-Remote-Version: 2`によるRemote protocol 2の選択
- 認証済みprincipalの`write` scope
- 現在のRemote snapshot／resource revisionを指定した`If-Match`
- JSON本文内の、呼び出し側が生成した安定した`transaction_id`
- `clock.require_remote_write_time`有効時の`X-Lifetxt-Client-Time`
- ブラウザセッション認証時のCSRF tokenと許可された`Origin`

現在の集約revisionは`GET /api/remote/v1/snapshot`、`GET /api/remote/v1/resources`、または他のRemote読み取り応答から取得します。サーバーはさらに、通常のsidecar mutation lockを保持した状態で、書き込み対象のチケットファイルに対する正確なSHA-256 CASを実行します。

## 対応操作

### 作成

応答を受信できなかった場合でも安全に再試行できるよう、Remote作成では明示的な安定IDが必要です。

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

チケットと`record:ticket_event event:created`履歴は、1回のexact-revisionファイル置換で同時に追記されます。

### フィールド編集

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

最初の契約で変更できるのは、保守的に選んだ単一値の計画・担当フィールドだけです。project、visibility、owner、reporter、watcher、関連、添付、任意のカスタムフィールド、生のstatus変更は受け付けません。

### ステータス遷移

```json
{
  "operation": "transition",
  "transaction_id": "remote-transition-WEB-42-review",
  "ticket_id": "WEB-42",
  "target_status": "review",
  "comment": "Implementation and tests are ready"
}
```

認証済みRemote roleを`ticketing.workflow`に対して評価します。イベントのauthorには認証済みprincipalを使用し、クライアントによる別actorの指定はできません。

### コメント

```json
{
  "operation": "comment",
  "transaction_id": "remote-comment-WEB-42-root-cause",
  "ticket_id": "WEB-42",
  "body": "The session cookie path excluded the API prefix."
}
```

### 工数入力

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

`record:ticket_event event:time_entry`と`record:time_entry`を同じチケット操作で追記します。`corrects`を使うことで、以前の工数レコードを訂正できます。

## 再試行と競合

コミットされた各イベントにはRemote operationと、正規化したリクエストのハッシュを保存します。同じ本文と同じ`transaction_id`を再送した場合、最初の応答を受信できていなくても、既存結果を`replayed: true`として返します。異なる本文で同じIDを再利用すると`REMOTE_TRANSACTION_REUSED`になります。

`If-Match`がない場合や古い場合は更新前に拒否します。対象ファイルの競合もper-file CASで拒否します。validation、workflow、history、custom-field、timestamp、time-entryの検証に失敗した場合、authoritativeなバイト列は変更されません。

## 現在の境界

最初の書き込み可能Remote契約は意図的に次へ限定しています。

- 設定された書き込み可能な`life.txt`は1ファイルだけ
- チケット・イベント・工数・計画を複数ファイルに分けた更新には未対応
- Remoteからのversion・sprint更新には未対応
- チケット一括更新には未対応
- 関連、watcher、添付、timer side effect、provider side effectの更新には未対応
- MCP書き込みツールには未対応
- 複数worker間のブラウザセッション共有や本番運用の安全性は未主張

書き込み前にcapability discoveryを利用してください。Protocol v2 capabilitiesの`mutation_policy.ticket_mutations_enabled`、対応operation一覧、残っている制限を確認できます。
