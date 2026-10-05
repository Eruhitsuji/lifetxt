# Web通信のセキュリティ

この方針は、添付ファイルのアップロードや今後のprivate resourceアクセスを含む、
書き込み可能なWeb UI/APIの通信に適用します。read-onlyサーバーの機密情報の読み出しも
対象です。Bearer認証はアクセスを認可しますが、**平文HTTPの盗聴・改ざんを防ぎません**。
添付ファイルの内容、API認証情報、private metadata、変更要求、持っているだけでアクセス
できるcapability/share URLや署名付きURLを保護してください。opaque IDはパスの開示を
抑える識別子であり、内容の暗号化や安全な通信の代わりにはなりません。

## 配置と保護範囲

| 配置 | 必要な保護・脅威モデル |
| --- | --- |
| loopback上のHTTP | ホスト・ローカルユーザー・プロセスを信頼できる場合に許可します。悪意あるローカルプロセスやブラウザ要求からの分離ではないため、認証・upload CSRF検証は引き続き必要です。 |
| private LAN | private addressやfirewallだけでは暗号化できません。侵害された端末や盗聴を想定し、HTTPSまたは認証付き暗号化トンネルを使用します。 |
| VPN / SSH / private overlay | 接続先を認証し、信頼できないネットワーク区間をすべて暗号化し、アクセスを制限し、復号後のbackend通信をloopbackまたは同等に保護されたホスト内に限定する場合に許可します。overlayの名称だけでは十分ではありません。 |
| public / 一般のnon-loopback | 有効な証明書を持つHTTPSを標準構成とします。信頼できるreverse proxyでTLSを終端し、backendへの接続をそのproxyに限定します。信頼できない区間を通るupstream通信も暗号化します。 |

`lifetxt serve` / `lifetxt web`の既定は`127.0.0.1`です。直接のUvicornはHTTPを使い、
TLS証明書管理はproxyの責務です。書き込み可能なnon-loopback bindでは、Bearer tokenや
`--insecure-public`の有無にかかわらず、通信保護が必要な旨を起動時に警告します。
認証のない書き込み可能なpublic bindを拒否する既存の動作は継続します。
`--insecure-public`が緩和するのは認証の起動条件だけで、平文通信の承認にはなりません。

bindやHTTP schemeだけでは、外側のVPN/SSHトンネルやTLS proxyによる保護を判定できません。
通常のWebサーバーでは新しい平文overrideや一律拒否を追加せず、警告を出します。
警告が出たまま起動できることは、方針を満たした証拠ではありません。機密情報を送る前に
通信経路全体を確認してください。HTTPですでに送った認証情報・bodyはアプリの拒否では
保護できません。Remote Safe Mode独自のHTTPS必須判定と`remote.allow_loopback_http`は
継続し、private VPN経由のHTTP接続元がそれを回避することはできません。
read-onlyは情報秘匿の境界ではありません。

## Proxyの信頼とsame-origin upload

`serve`と`web`は、`FORWARDED_ALLOW_IPS`にかかわらずUvicornの自動proxy header処理を
無効化し、socketの直接接続元を既存の`remote.trusted_proxies`判定に使用します。
Remote Safe Modeが無効でもuploadのOrigin検証に適用します。新しい設定項目はありません。

同一ホストのIPv4 loopback proxyの場合、既存の設定に以下を追加してください。

```json
{
  "remote": {
    "trusted_proxies": ["127.0.0.1/32"]
  }
}
```

実際のproxy接続元がIPv6の場合のみ`::1/128`を追加します。信頼するアドレスは最小限とし、
全ネットワークやLAN全体を指定しないでください。proxyの信頼は、Remote有効時の既存の
principal assertion権限も与えます。backendを信頼できないclientやローカルプロセスに
開放しないでください。

proxyはpublic Hostを設定済みのhostname・portと照合し、`Host`、`X-Forwarded-Host`、
`X-Forwarded-Proto`を検証した外部authority・schemeで上書きします。clientが送った
`Forwarded`や`X-Lifetxt-Principal`は削除し、Remote identityを検証して意図的に渡す場合だけ
principal headerを設定します。clientのforwarding headerをそのまま中継しないでください。
外部portが`:8443`などの場合、Hostとforwarded hostにそのportを保持してください。
[nginx例](../../contrib/nginx/lifetxt.conf.example)はHTTPS listenerの外部hostnameを固定し、
別portを使う場合は両authority headerを変更します。未知のHostはfront-endのdefault serverで
拒否してください。

設定した直接接続元のscheme・hostのみ信頼します。信頼しない接続元のforwarding headerと
標準の`Forwarded`は無視します。uploadとRemote browserのsame-origin計算はこの境界を
共有します。信頼する`X-Forwarded-Proto` / `X-Forwarded-Host`はそれぞれ単一値とし、重複・
空値・カンマ区切り・不正形式・HTTP以外のoriginは拒否します。多段proxyでは最後の信頼する
hopで単一値にしてください。Originはscheme・hostname・実効portを比較し、既定の80/443は
省略時と同じです。upload marker、Fetch Metadata検証、CORSを追加しない方針は継続します。
Remoteの`allowed_origins`はuploadの許可範囲を広げません。

独自ASGI hostingでもproxy headerの自動書き換えを無効にし、socket接続元を保持してください
（`uvicorn ... --no-proxy-headers`）。保持しない構成はこの信頼方式のサポート対象外です。
HTTPSのsame-origin upload成功、cross-origin拒否、信頼しない接続元からのforwarding偽装の
拒否を確認してください。trusted proxies変更後はサービスを再起動します。旧版はUvicornの
proxy headerを独立して処理していたため、upgrade後はその暗黙の信頼に依存しないでください。
downgrade前もproxyの動作確認が必要です。

## 機密URL・ログ・キャッシュ

capability・署名付きURLのアクセス先もHTTPSを使用し、API tokenをquery stringに入れないで
ください。所持によりアクセスを許すURLは一時的な認証情報として、最小権限・短い有効期限を
設定します。life.txt、通常のlocator、平文設定、analytics、access log、例外レポート、
support bundleに残さず、ログには機密でない安定した識別子を使用します。proxyやproviderの
境界でURLのquery・認証情報をredactし、第三者への遷移・referrer流出を避けます
（private responseに`Referrer-Policy: no-referrer`を設定）。

uploadのreceipt/errorは既に`Cache-Control: no-store`を使用します。今後のprivate resource
responseやgrant発行endpointにもno-storeを設定し、shared/proxy/CDN/service-worker cacheを
避け、payloadやgrant URL全体をログに残さず、内容に適したdownload headerを使用してください。
有効期限が切れてもログやキャッシュのコピーは消えません。URL発行・download・provider adapterは
別課題であり、この方針はresource resolverを追加しません。

[Web](web.md)、[Remote Safe Mode](remote.md)、
[Ubuntu配置手順](../deployment/ubuntu-server.md)も参照してください。
proxyの機構は公式の[Uvicorn設定](https://www.uvicorn.org/settings/)と
[nginx header設定](https://nginx.org/en/docs/http/ngx_http_proxy_module.html#proxy_set_header)を参照します。
