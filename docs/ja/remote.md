# Remote Safe Mode

Remote Safe Modeは、life.txt workspaceを認証付きで参照するための小さなread surfaceです。既定では無効であり、authoritative fileはローカルに保持されます。authoritativeなremote mutationはまだ有効化されません。

## セキュリティモデル

`remote.enabled: true`でRemote APIを公開します。すべてのAPI requestは設定済みprincipalとして認証されます。標準roleは`owner`、`editor`、`reader`、`auditor`で、`read`、`write`、`admin`、`audit` scopeへ展開されます。scopeに加えてproject、group、owner、visibilityも検査されます。

Bearer secretは設定ファイルやclient profileへ保存しません。principalの`token_env`で環境変数名を参照します。trusted reverse proxyが`X-Lifetxt-Principal`を伝達できるのは、直接接続元が`remote.trusted_proxies`に含まれる場合だけです。forwarded protocol／host headerもtrusted peerから届いた場合だけ信頼します。

loopback以外ではHTTPSが必須です。`remote.allow_loopback_http`はローカル開発専用です。absolute local path、credentialに見えるfield、raw source text、詳細なparser diagnosticsはRemote responseから削除またはredactされます。

`remote.audit_log`はauthoritativeなlife.txt input／writable fileと同じpathにできません。同一pathの場合はRemote serverの起動を拒否します。

## Protocol negotiation

version headerを送らない既存clientには、互換性のためRemote protocol version 1を使用します。新しいclientはversion 2を要求してください。

```http
X-Lifetxt-Remote-Version: 2
```

すべてのAPI responseには次のheaderが付与されます。

```text
X-Lifetxt-Remote-Version
X-Lifetxt-Remote-Min-Version
X-Lifetxt-Remote-Capability-Revision
X-Request-ID
```

未対応versionは`REMOTE_VERSION_UNSUPPORTED`、HTTP 426で拒否されます。version 2ではbrowser session、CSRF／Origin検証、resource catalog、aggregate diagnostics、capability revision negotiationを利用できます。

## 設定例

```json
{
  "remote": {
    "enabled": true,
    "browser_ui": true,
    "allow_loopback_http": false,
    "rate_limit_per_minute": 120,
    "browser_login_rate_limit_per_minute": 10,
    "browser_session_ttl_seconds": 28800,
    "browser_session_idle_seconds": 1800,
    "browser_session_max": 256,
    "session_cookie_name": "lifetxt_remote_session",
    "csrf_header": "X-CSRF-Token",
    "allowed_origins": ["https://life.example.test"],
    "audit_log": ".cache/lifetxt/remote-audit.jsonl",
    "audit_max_bytes": 5242880,
    "principals": [
      {
        "id": "alice",
        "role": "editor",
        "token_env": "LIFETXT_REMOTE_ALICE_TOKEN",
        "projects": ["web"],
        "groups": ["engineering"],
        "visibilities": ["public", "shared", "team"]
      }
    ],
    "trusted_proxies": ["10.0.0.0/8"]
  }
}
```

secretは設定ファイルの外で指定します。

```console
export LIFETXT_REMOTE_ALICE_TOKEN='replace-with-a-random-secret'
```

`allowed_origins`にはpathを含まないHTTP(S) originだけを指定できます。cookie名とCSRF header名は有効なHTTP tokenである必要があり、不正なsession設定はserver起動時に拒否されます。

## Browser session

`remote.browser_ui`を有効化して`/remote`を開きます。browserはBearer tokenを一度だけ送信し、opaqueなserver-side sessionへ交換します。login後にtoken inputは消去され、local storage、session storage、cookie、profile、response、audit detailへ保存されません。

session cookieの性質は次のとおりです。

- opaqueかつserver-side管理
- `HttpOnly`
- `SameSite=Strict`
- 明示したloopback開発例外を除いて`Secure`
- pathは`/api/remote/`に限定
- logout、principal削除／無効化、expiry、eviction、server restartで無効化

browser-sessionによるunsafe requestには、設定済みCSRF headerと完全一致する許可済み`Origin`の両方が必要です。loginにもexact Originが必要で、通常requestとは別のlogin rate limitが適用されます。再login時はcookieをrotationし、旧sessionをrevokeします。

Browser session endpointはprotocol version 2専用です。

```text
POST /api/remote/v1/browser/login
GET  /api/remote/v1/browser/session
POST /api/remote/v1/browser/logout
```

## HTTP read surface

互換route:

```text
GET  /api/remote/v1/capabilities
GET  /api/remote/v1/session
GET  /api/remote/v1/snapshot
GET  /api/remote/v1/tickets
GET  /api/remote/v1/projects
GET  /api/remote/v1/audit
POST /api/remote/v1/write-check
```

protocol version 2 route:

```text
GET /api/remote/v1/resources
GET /api/remote/v1/resources/{resource}
GET /api/remote/v1/diagnostics
```

共通read backendは現在次のresourceを公開します。

- `items`: text、type、project、open-only、limitで絞り込んだvisible item
- `tickets`: project、status、assigneeで絞り込んだvisible ticket
- `projects`:同じvisible item集合から生成したproject summary
- `ticket-report`:共有ticket/project aggregation contract
- `links`: ID、direction、relationで絞り込んだrelation record
- `status`:最新のvisible status record
- `agenda`:指定期間内のvisible record
- `search`:visible item、project、personだけを対象にしたsafe search

未知resourceや未対応parameterはfail closedで拒否されます。すべてのresourceは同一のprincipal filteringとsource revisionを使用します。diagnosticsはseverity／codeの集計と運用checkだけを返し、record text、source path、parser messageは返しません。

```http
GET /api/remote/v1/resources/tickets?project=web&status=review&limit=50
Authorization: Bearer <token>
X-Lifetxt-Remote-Version: 2
```

## Dependency-free client

profile storeは`remote-profile-v3`です。version 2 profileは、TLS verificationとprotocol versionのdefaultを補ってmemory上でversion 3へmigrationします。保存する値はURL、TLS preference、protocol version、token環境変数名だけです。

```console
lifetxt remote profile-set home https://life.example.test \
  --token-env LIFETXT_REMOTE_TOKEN \
  --protocol-version 2

lifetxt remote profile-list
lifetxt remote profile-show home
lifetxt remote test home
lifetxt remote resources home
lifetxt remote get home tickets --param project=web --param status=review
lifetxt remote diagnose home
lifetxt remote snapshot home
lifetxt remote export home snapshot.json
lifetxt remote tui home
lifetxt remote profile-remove home
```

clientはrequest ID、offset-aware client time、選択したprotocol versionを送信します。protocol 2でnegotiation headerを返さないserverや、要求と異なるversionを返すserverは拒否します。

## Write境界

admissionされるremote writeにはexactな`If-Match` revisionが必要です。revisionがなければ`REVISION_REQUIRED`、staleなら`REVISION_CONFLICT`になります。

`POST /api/remote/v1/write-check`は認証、write scope、browser-session CSRF／Origin、exact revisionを検証しますが、常に`authoritative_mutation: false`です。permission、privacy、event history、clock、idempotency、multi-target transaction、recoveryを完全に公開・強制できるoperationだけが、将来authoritative Remote mutationの対象になります。
