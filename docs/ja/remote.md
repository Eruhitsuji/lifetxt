# Remote Safe Mode

Remote Safe Modeは、life.txt workspaceを認証付きで参照するための小さなread surfaceです。既定では無効であり、authoritative fileはローカルに保持されます。authoritativeなremote mutationはまだ有効化されません。

## セキュリティモデル

`remote.enabled: true`でRemote APIを公開します。すべてのAPI requestは設定済みprincipalとして認証されます。標準roleは`owner`、`editor`、`reader`、`auditor`で、`read`、`write`、`admin`、`audit` scopeへ展開されます。scopeに加えてproject、group、owner、visibilityも検査されます。

Bearer secretは設定ファイルやclient profileへ保存しません。principalの`token_env`で環境変数名を参照します。trusted reverse proxyが`X-Lifetxt-Principal`を伝達できるのは、直接接続元が`remote.trusted_proxies`に含まれる場合だけです。forwarded protocol／host headerもtrusted peerから届いた場合だけ信頼します。

loopback以外ではHTTPSが必須です。`remote.allow_loopback_http`はローカル開発専用です。absolute local path、credentialに見えるfield、raw source text、詳細なparser diagnosticsはRemote responseから削除またはredactされます。

`remote.audit_log`はauthoritativeなlife.txt input／writable fileと同じpathにできません。同一pathの場合はRemote serverの起動を拒否します。

### Single-worker deployment

Remote Safe Modeのprincipal単位rate limitingとopaqueなbrowser sessionストアは、いずれもprocess-localなin-memory stateで、共有backendを持ちません。`lifetxt serve`自体には`--workers`optionがなく、単一processでしか起動できません。ASGI applicationを外部のmulti-worker manager（gunicorn、`uvicorn --workers N`、あるいはPaaSの既定multi-worker mode）から直接起動した場合、認証やrate limitを行ったworkerとは別のworkerがrequestを受け取ると、そのworkerは別のcounter・別のsession tableを参照することになり、login throttlingが静かに弱まり、session挙動も不整合になります。

`remote.enabled`がtrueのとき、サーバーは`WEB_CONCURRENCY`環境変数（複数のplatform・process managerがこの目的で設定するde facto標準）が`1`を超えて検出された場合、起動を拒否します。この検出はbest-effortであり、すべてのmulti-worker deployment構成を網羅するものではなく、検出されないことがsingle-worker deploymentの保証にはなりません。`remote.allow_multi_worker: true`を設定すると、worker間でのthrottling・session整合性の低下を許容した上でそのまま起動します。

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
- `tickets`: project、status、assigneeで絞り込んだvisible ticket。上限付きのデフォルトpage sizeとcursor pagination付き（後述）
- `ticket-detail`: `id`で指定した1件のvisible ticketの全detail（field、relation、incoming link、時間集計）。存在しないIDとvisibleでない既存IDは同一の`REMOTE_TICKET_NOT_FOUND`エラーを返す
- `projects`:同じvisible item集合から生成したproject summary
- `ticket-report`:共有ticket/project aggregation contract
- `links`: ID、direction、relationで絞り込んだrelation record
- `status`:最新のvisible status record
- `agenda`:指定期間内のvisible record
- `search`:visible item、project、personだけを対象にしたsafe search
- `next`: `lifetxt next`・TUIの`/next`・MCPの`get_next_actions`と同じ共有定義によるactionable item。`project`・`assignee`・上限付き`limit`（既定は無制限、最大1000）で絞り込み可能。principalから見えないdependencyでblockされているitemはactionableに昇格せず除外されたままになる

未知resourceや未対応parameterはfail closedで拒否されます。すべてのresourceは同一のprincipal filteringとsource revisionを使用します。diagnosticsはseverity／codeの集計と運用checkだけを返し、record text、source path、parser messageは返しません。

```http
GET /api/remote/v1/resources/tickets?project=web&status=review&limit=50
Authorization: Bearer <token>
X-Lifetxt-Remote-Version: 2
```

### ticketsのpagination

`limit`を指定しない`tickets`requestは、visible tickets全件ではなく最大200件を返します。明示的な`limit`は従来どおり動作し、既存の上限5000件はそのままです。responseの`data`には`next_cursor`（返却した最後のticketのID。このpageでvisible setの末尾に達した場合は`null`）と`has_more`が追加されます。`next_cursor`を`cursor`として次のrequestに渡すと、既存の決定的なID順で、そのIDより後のticketだけが返されます。

複数requestにまたがってpaginationするclientは、任意で`since_revision`（以前のpageの`revision`値）を渡せます。前回以降にworkspaceが変化していた場合、異なるrevisionのpageを黙って混在させて返す代わりに`REMOTE_RESOURCE_REVISION_CHANGED`で失敗します。clientは最初のpageからpaginationをやり直してください。`since_revision`を省略した場合の挙動は今までと完全に同じです：各pageは自身の`revision`を独立して報告し、整合性checkは行われません。

```http
GET /api/remote/v1/resources/tickets?limit=50&cursor=TK-0050
Authorization: Bearer <token>
X-Lifetxt-Remote-Version: 2
```

このpagination契約は現時点で`tickets`のみに適用されます。他のresourceは上記のとおり、`limit`未指定時は無制限のままです。

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
