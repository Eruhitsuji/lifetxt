# Remote Safe Mode

Remote Safe Modeは、life.txtデータの参照とrevision-aware writeの検証に限定した、認証必須の小さなHTTP surfaceです。既定では無効です。

## セキュリティモデル

`remote.enabled: true`で有効化します。すべてのremote requestは設定済みprincipalとして認証される必要があります。roleは`owner`、`editor`、`reader`、`auditor`で、`read`、`write`、`admin`、`audit`のscopeへ展開されます。scopeに加えてprojectとvisibilityのgrantも検証されます。

Bearer secretは設定ファイルへ直接保存しません。principalに`token_env`を設定し、その環境変数へsecretを保存します。trusted reverse proxyは、直接接続元が`remote.trusted_proxies`のIP/CIDRに含まれ、assertされたIDがprincipal registryに存在する場合だけ`X-Lifetxt-Principal`を使用できます。

loopback以外ではHTTPS必須です。`remote.allow_loopback_http`はローカル開発専用です。remote browser UIは`remote.browser_ui`を明示的に有効化しない限り無効です。

すべてのremote writeは正確な`If-Match` revisionを要求します。revisionがない場合は`REVISION_REQUIRED`、古い場合は`REVISION_CONFLICT`を返します。remote routeはrequest ID、principal単位rate limit、絶対local pathのredaction、上限付きJSONL audit logに対応します。

## 設定例

```json
{
  "remote": {
    "enabled": true,
    "allow_loopback_http": false,
    "rate_limit_per_minute": 120,
    "audit_log": ".cache/lifetxt/remote-audit.jsonl",
    "principals": [
      {
        "id": "alice",
        "role": "editor",
        "token_env": "LIFETXT_REMOTE_ALICE_TOKEN",
        "projects": ["web"],
        "visibilities": ["public", "shared"]
      }
    ],
    "trusted_proxies": ["10.0.0.0/8"]
  }
}
```

## Remote HTTP route

- `GET /api/remote/v1/capabilities`
- `GET /api/remote/v1/session`
- `GET /api/remote/v1/snapshot`
- `GET /api/remote/v1/tickets`
- `GET /api/remote/v1/projects`
- `GET /api/remote/v1/audit`
- `POST /api/remote/v1/write-check`

write-check routeはauthoritative dataを変更せず、認証済みwrite scopeとexact revisionを検証します。ticket mutationは既存のexact-revision ticket contractを使用します。

## 依存ライブラリ不要のclient

```console
lifetxt remote profile-set home https://life.example.test --token-env LIFETXT_REMOTE_TOKEN
lifetxt remote profile-list
lifetxt remote test home
lifetxt remote snapshot home
lifetxt remote export home snapshot.json
lifetxt remote tui home
```

profileにはserver URL、TLS設定、tokenを保持する環境変数名だけを保存します。read-only remote TUIはWeb依存を追加せずsnapshotを表示します。
