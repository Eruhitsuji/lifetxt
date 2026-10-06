# 外部資源の明示的な取得・取り込みポリシー

[English](../en/external-resource-fetch-policy.md)

## 1. 状態と承認境界

これは #1129、[owner採択済み #1103 調査](https://github.com/Eruhitsuji/lifetxt/issues/1103#issuecomment-6027182964)のTask Aとして整備するドキュメントのみの契約です。
MUST/MUST NOT相当の「必須」「禁止」は将来の適合consumerへの要求であり、
利用可能なコマンド、endpoint、設定、scope、schemaを表しません。具体的なconsumer、
接続先、provider、accountは未選定です。採用・merge前に独立したhumanの設計・security
reviewとlatest-head integration reviewが必要です。実装者の自己レビューは参考情報で、最終承認ではありません。

初期候補は承認済みHTTPS originから公開fileを明示取り込みする、既定無効の機能です。
現行 [resource-reference runtime](resource-reference-runtime.md) は登録済みlocal file専用で、
任意URLやcloud objectを取得しません。そのrestricted bearer権限を拡張しません。
Format、item linkage用 `ref:`、local `file:` / `dir:`、保存されるinertな未知custom keysを維持します。

## 2. 操作の分離と現認可

| 操作 | 必須境界 |
| --- | --- |
| 参照の作成・表示・projection | inert。DNS、HEAD、HTTP、favicon、preview、remote存在確認を発生させない |
| 明示的なpublic browser open | 意図的にpublicでsecret-freeかつpolicy承認済みURLのみ。safe plain DOM、noopener/noreferrer、referrer抑止。server fetchなし |
| Provider mediation | #1102のexact object/profile/account bindingを持つ別承認consumer。任意URLへのfallbackではない |
| Explicit fetch | 現authentication、workspace/source/item/resource/action認可、明示network-reach grant、owner承認destinationと強制egress policy |
| Local copyのimport | 全fetch gateに加え現source/item write membership、writable/non-generated source、supported Format、read-only/write-clock guards、exact source revision |
| Render/OS open/archive展開/sync | 別capability。fetch成功だけで許可しない |

role、`read`、`attachment:read`、upload receipt、cached descriptor、object possession、
Mailbox storage credentials、request `origin`、`attachment_refs` はnetwork reach/importを付与しません。
権限・profile選択はserver側で固定し操作ごとに再確認します。未分類入力・不足policyは
**DNS前**に拒否します。実際のscope名、routes、wire versionは別のapproved consumer契約が必要で、今回は登録しません。

各connection/redirect、cancellation checkpoint、bytes delivery/commit前に現permissionとprofile generationを
再検証します。revocationやcontinuity不明時は停止します。既に配信したbytesは回収できません。

## 3. 概念上のtyped profileとintent

以下は概念フィールドで、利用可能なlifetxt設定ではありません。operator-owned profileは
immutable identity/generationをinstall/workspace、承認authority、egress mode、有効上限へ束縛します。
aliasは選択名であってauthorityではありません。再bindingで既存操作の接続先を黙って変えてはいけません。

| 概念フィールド | 型と検証 |
| --- | --- |
| `profile_alias` | bounded ASCII選択string、完全一致。operatorがimmutable profile identity/generationへ解決 |
| `approved_origins` | boundedかつ空でないexact HTTPS host/443 origin集合。substring/wildcard不可 |
| `path_policy` / `query_policy` | typed承認path/query parameters。任意service proxy/URL転送request不可 |
| `egress_mode` | 初期direct接続のみ。proxy採用には別review済みdestination enforcementが必要 |
| `operation_id` | bounded non-secret操作identity。principal/workspaceとintentに束縛し、bearer grantではない |
| `source_selector` / `item_selector` | serverが一意の現source/itemへ解決。client local target path不可 |
| `expected_source_revision` | 現whole-source CASのexact validator。wildcard/implicit latest不可 |
| `public_url` | bounded strict URL、policyで明示public・secret-free。unknown/authenticated/capability/signedは拒否 |
| `expected_content_digest` | optional typed full SHA-256、exact bytes用。provider ETag/短縮保存hashではない。disclosure-controlled |

将来validatorはduplicate keys、unknown fields、不正encoding、controls、過長入力を
echoせず拒否します。bounds・正式wire field名はconcrete consumer承認後にだけ公開します。
後続mediationがprovider object ID/revisionを扱う場合は #1102 のexact opaque stringsを維持し、
URL normalizationを適用しません。credential値、caller headers、proxy選択、filesystem
destinationはintent fieldsに含めず、secret referencesはprotected server metadataに留めます。

予約されたexample dataによる**内部intent例のみ**です。HTTP requestや実環境へ貼る設定ではありません。

```json
{
  "profile_alias": "approved-public-docs",
  "operation_id": "example-operation-001",
  "source_selector": "example-source",
  "item_selector": "example-item",
  "expected_source_revision": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "public_url": "https://downloads.example.com/report.pdf"
}
```

このexample originを本契約で許可していません。フィールドを渡しただけで通信、profile登録、認可の省略を行ってはいけません。

## 4. URLとredirect

初期はHTTPS、443、GETのみです。HTTP/file/FTP/gopher/data/javascript/Unix socket、
別port、caller method/body overrideはscope外です。single strict parserで一度解析し、
接続・request構築まで同じ検証済み解釈を維持します。

hostはbounded ASCII（必要時は事前承認A-labelのみ）。userinfo、fragment、controls/CRLF/NUL、
backslash、malformed percent、percent-encoded/ambiguous authority、trailing-dot host、
IPv6 zone ID、decimal/octal/hex等のalternate IP表現を拒否します。初期はIP literal不可です。
明記したURL canonicalization後のscheme/host/portをapproved originへ完全照合し、path/query
policyも満たす必要があります。知らないquery名だけでpublicとは判断しません。
signed/capabilityの証拠をpublic宣言より優先し、不確かな入力は拒否します。

automatic redirectは無効、初期限度は **0** です。別承認profileで将来許可しても最大 **3** hops、
cycle検出と各hopで全URL/permission/classification/DNS/IP/peer/egress検証が必要です。
relative Locationは同じparserで現URLに対し解決し、request前に検証します。
downgrade・未承認originは拒否。same-originでもheadersを再構成し、cross-originへ
Authorization/Cookie/Referer/origin固有credentialsを転送しません。別credential bindingには別明示権限が必要です。

HTML meta-refresh、JS/CSS/images、favicon、Link preload、Content-Location、Alt-Svc、
service discovery、HTTP/2 origin coalescing、HTTP/3 address migrationによるrouting変更は禁止です。
初期transportは1つのapproved originと検証済みconnection destinationを維持します。

## 5. DNS・実peer・egress

origin許可だけでresolved addressを許可しません。DNS前gateの後、operator-controlled resolverを
使用し、duration/answer count/CNAME処理をboundedにします。最終A/AAAAの全候補を検証し、
permitted/deniedのmixed set、過多、不明分類は拒否します。

loopback、private/ULA、link-local、unspecified、multicast、shared/CGNAT、documentation/reserved、
special-purpose ranges、operator internal/service networks、IPv4/IPv6の明示metadata endpoints/namesをdenyします。
denyはorigin許可より優先。maintained explicit address分類を使用し、runtimeの `is_private` のみには依存しません。
IPv4-mapped IPv6はembedded IPv4も検証します。transition/tunnel/NAT64 destinationは初期deny、
translation後にもegress側で同等制限を適用します。global番号のinternal serviceもoperator denylistへ含めます。

選択済みvalidated IPへだけ接続し、二度目のunchecked DNSを禁止します。承認hostnameを
Host/SNI/TLS証明書検証に維持し、証明書検証を無効にしません。実direct peerが選択addressと一致するか確認します。
retry、fallback/Happy Eyeballs、redirect、pool/new connectionも同じgateを通します。
poolはprofile/authority/validated address/policy generationにscopedとし、不確かな再利用は拒否します。

application peer確認だけではNAT/routing/proxyの最終destinationを保証できません。
translated/internal destinationsを含む強制egress rulesが必要です。未対応ならserviceを拒否し、
generic URL clientへfallbackしません。outbound proxy trustは #1097 のinbound
`remote.trusted_proxies` / TLS-origin処理と別です。

## 6. Headers・proxy・credentials

connectorはfresh allowlist requestを構築します。approved Host/SNI、固定User-Agent、Accept、
`Accept-Encoding: identity`のみを基本とし、caller headers、Authorization/Cookie/Proxy-Authorization/Referer/Range、
任意method/body、provider/session credentialsを受け付けません。environmentの
HTTP(S)_PROXY/ALL_PROXY/NO_PROXY、netrc、browser/OS session、persistent cookiesを自動利用しません。

明示採用outbound proxyはidentity/TLS、origin destinationとDNS/IP/translation enforcement、
redirect、最小化したlog/spool retentionを証明する必要があります。proxy peer確認だけでは不十分で、
未対応topologyはunavailableです。authenticated provider mediationは別taskで、verified
tenant/account/object scope、external secret references、public fetch/ambient accountへのfallback禁止が必要です。
capability URLsはexternal secret facilities、signed URLsは明示認可後に生成するoperation-scoped
ephemeral secretsに留めます。いずれも初期public consumerは受け付けません。

## 7. 将来の上限とcontent acceptance

以下はfuture consumer契約のbudgetで、**利用可能な設定ではありません**。ownerはeffective limitsを
下げられます。引き上げ、compression/retry追加は別reviewが必要です。identityでもencoded/decodedをそれぞれ計数します。

| Budget ID | 上限 |
| --- | --- |
| L1 wire/decoded body | 各min(10 MiB = 10485760 bytes, configured attachment max_file_bytes) |
| L2 encoding | identityのみ。unknown/nonidentity Content-Encoding拒否、automatic decompressionなし |
| L3 headers | total 32 KiB = 32768 bytes、最大100 fields |
| L4 network | DNS/connect/TLS/body全体30 s、connect5 s/idle5 sはtotal monotonic deadline内 |
| L5 concurrency | process2 / principal1、unbounded waiting queueなし |
| L6 rate | 30 operations/principal/min、120/process/min。失敗したadmitted attemptsも含む |
| L7 retry | 初期0。将来最大1のpre-body transient GET retryのみ、同じtotal budgetと再gate |
| L8 redirects | 初期0、別承認のfuture ceiling3、automatic followなし |

全resource phaseにCPU/memory/physical-worker lifetimeの上限が必要です。network deadlineは
filesystem commitがblockしない保証ではありません。future import consumerでsupervised
validation/commit budgetを定義し、stuck work時は安全にadmissionを止め、physical termination確認までcapacityを保持します。
client disconnectやlogical timerだけでslotを返しません。budget外の任意queue/cache/spool/large allocationは禁止です。

初期は完全な200 bodyだけ受理します。Content-Lengthによらずstreaming bytesを計数し、
partial206、矛盾/重複framing・encoding、unexpected status、truncation、length mismatch、deadline超過を拒否します。
compression追加には別encoded/decoded size、ratio、layers、CPU制限が必要です。

MIME/provider names/Content-Dispositionはuntrusted。uploadの `content_type` とattachment MIME/executable
policyを弱めず再利用します。観測content、宣言MIME、filename policyを確認し、矛盾/不明typeは
明示承認inert-binary policyがなければ拒否します。magicは無害性・malware不在の証明ではありません。
generated create-only managed pathsとsafe authored labelsを使い、URL/provider basenameをtargetにしません。
active preview/executable launch/macro実行/HTML subresource fetch/automatic archive展開なし。承認archivesもinert bytesとして保持します。

## 8. Disclosure・secrets・local copies

通常diagnosticsからquery/fragment/userinfoを除くことに加え、path capability対策として
**URL全体を出力しません**。fresh DTOは必要なoperation/outcome・認可済みcorrelation handlesのみallowlist化します。
alias/host/account/object/secret handles/labels/digestsは既定非公開。
raw Location、DNS/TLS/provider exception、headers/bodyを漏らしません。

| Surface | 必須最小化 |
| --- | --- |
| Raw/details/note/custom/Markdown/export/edit forms | hidden raw locator/secret copyなし。allowed projected textを構築または拒否 |
| Search/snippets/previews | authorized projected dataのみ。unsafe query echo/implicit HTTPなし |
| History/diffs/audit/support/logs | current AND historical disclosure permission。static outcomeとminimal correlation、raw URL/exception fallbackなし |
| Browser DOM/storage/copy/referrer/redirect | secret/provider locatorなし。no-store、logout/workspace変更でstate消去、frontend signed-URL redirectなし |
| Mailbox/MCP/Remote wrappers | nested resultsも同じprojection。origin/storage possession/attachment refsはauthorityなし |
| Cache/worker arguments/temporary files | shared response cache/cookies/disk spool/command-line secretsなし。external secret facilityのみ |

取得bytesは [at-rest policy](at-rest-confidentiality.md) に従う別のlocal confidentiality責任です。
final files、atomic temps、transaction before/after artifacts、backups、proxy spool、swap/hibernation、crash dumpsを含みます。
初期stagingはbounded memoryですが、非永続化保証ではありません。future disk stagingにはapproved
owner directory0700/file0600、link拒否、size/retention上限、cleanup ownershipが必要です。
normal unlinkはsecure erasureではありません。SQLite/reference indexは暗号化ではありません。

既存user-authored secretsには内容をechoしない警告、provider revoke/rotate、owner明示修正、
history/Git/journal/backups/export/browser copyの棚卸しが必要です。silent rewrite/deleteやhistorical erasureを
主張しません。この契約の公開だけで既存generic raw surfacesが安全になるわけではありません。

## 9. Exact import・回復・replay

current authority + exact source precondition → approved fetch → complete content/version/digest検証
→ current write authority/source CAS再確認 → normal attachment transaction → committed receipt → optional enrollment。
network中はsource lockを保持しません。source変更時はconflictとしexpected revisionをlatestへ自動変更しません。

`attachment_transactions.put_attachment` を `require_revisions=True`、exact `item_revision`、
`attachment_expected_revision=MISSING_HASH` で既存domain transactionを通して再利用します。
内部でHTTP upload endpointを呼び出したり第二writerを作りません。owner-controlled create-only managed rootを使い、
fetch前だけでなくmutation境界でもconfinement/link policyを再検証します。expected provider revision/full digestが
ある場合はexact bytesと一致が必要です。provider ETag/version、短縮保存hash、whole-source revisionは別です。
public URL copyは今後の同URL bytesが同一という保証ではありません。

multi-targetはjournal-backed compensated operationsで、無関係file間のportable atomic置換ではありません。
最終commit/recovery stateを確認し、reference/bytes不一致を成功として返しません。
pre-commit failureはowned stagingを破棄しreferenceを追加しません。proven operation-owned empty namespaceのみ
cleanupでき、他operationのfile/journalを削除しません。commit開始後のcancel/disconnectを未適用の証拠にしません。
worker slotを保持しjournalを確認、不明時はsafe recovery-needed outcomeとします。
既存explicit resume/compensateはowner-controlled。automatic journal削除で失敗を隠しません。

future idempotencyはoperation IDをprincipal/workspace、secret-free intent/profile generation、
exact source expectation、validated byte digestに束縛します。同IDで異なるintent/digestは拒否。
replay identity/lookup metadataにraw URLを永続化しません。intentのprivate query/path漏えいがあり得る場合は
protected non-secret locator identityとscoped opaque equality validatorsを使用します。unknown/secret-bearing intentは
初期public consumerで拒否し、hash化してgrantになったように扱いません。
既存transaction_idだけでfetch replay protocolが成立すると扱いません。lost receiptは認可下のcommitted-outcome
lookupが必要で、blind redownload/duplicate attachmentは禁止です。不明commitを解決してからretryし、
request間にURL bytesが変わり得る点を考慮します。enrollment failureはcommitted attachmentを取り消さず、
二重importを起こしません。fetch-onlyはsource writeなし。provider reference/imported local copy/descriptorは別で、background mirror/syncなしです。

## 10. 将来のnegative verification matrix

全行が**未実装・未実行fetch requirements**です。合格済みtest resultsではありません。
後続controlled connector testsと実deployment reviewで確認します。

| Case ID | 入力・event | 必須結果 |
| --- | --- | --- |
| N01 | Display/hover/Markdown/metadata refresh | DNS/HTTP callゼロ |
| N02 | Reader/local-resource bearer/Mailbox originのみ | DNS前deny |
| N03 | Alias再binding/account/profile generation変更 | old operation unavailable、authorityすり替えなし |
| N04 | Loopback/private/link-local/ULA/metadata/CGNAT/special/internal | approved hostでもblock |
| N05 | Mapped IPv4/transition/NAT64/translated internal peer | embedded/post-translation policy適用またはunavailable |
| N06 | Encoded/alternate IP/userinfo/backslash/zone ID/CRLF | strict reject、別parserで再解釈なし |
| N07 | Public DNS後private接続/mixed A/AAAA/fallback | validated peerのみ、不明set拒否 |
| N08 | Private/HTTP/未承認host/cycleへのredirect | default拒否、許可hopも毎回確認、ceiling3 |
| N09 | Cross-origin credentials/env proxy/netrc/cookies | forwarding/ambient loadなし |
| N10 | Path capability/signed URL/raw provider exception | persistence/log/export/referrer/frontend redirectなし |
| N11 | Compressed bomb/偽length/slow stream/truncated/206 | bounded abort、importなし |
| N12 | Executable MIME偽装/unsafe filename/HTML/archive | rejectまたは明示inert bytes、execution/展開/fetchなし |
| N13 | Body後source変更/provider version/digest不一致 | exact conflict、latest fallbackなし |
| N14 | Disconnect/partial compensation/unknown commit | journal確認、capacity保持、silent mismatch/blind retryなし |
| N15 | Lost receipt/同ID別intent/enrollment failure | 認可outcome回復、duplicate importなし |
| N16 | Stuck physical worker/unsupported proxy/egress | capacity保持、bounded supervision、service拒否 |
| N17 | Raw alternate route/search/history/Browser/Mailbox wrapper | disclosure bypassなし、current AND historical policy |

## 11. Enablement案と後続gate

具体consumerはadvertise/enable前にすべてのgateを満たす必要があります。

1. ownerがexact surface/public destinations/privacy・運用目的を選定します。本契約はgeneral Internet/provider accountを選定しません。
2. 別Ready XS/S taskでtyped wire/config契約と明示grantsを定義。restricted local-resource credentialにfetch/writeを付けません。
3. independent review済みconnectorがcontrolled fixturesでN04–N09を確認。deploymentのegress/proxy/NAT/TLS topologyを検証します。
4. content/import/recovery/idempotencyでN11–N16と現exact authorityを確認。全budgetがphysical workをカバーしstuck workerを安全に扱います。
5. 全enabled surfacesでN01–N03/N10/N17を確認。raw alternative/unsafe cache/secret error/private locatorを漏らしません。
6. latest-head human design/security・integration review、required CI、operator storage protection、rollback planをenable前に採択します。

| Task | Size / gate |
| --- | --- |
| A (#1129) | S: この英日documentation/package/registry契約のみ |
| B | S: validated-address single-hop public HTTPS connectorとcontrolled fixtures。Aとconsumer/destination選定が必要。public routeなし |
| C | S: transaction import core/recovery/idempotency。A/B依存、既存writer再利用、public APIなし |
| D | S: 1つの明示opt-in consumer、operation認可/disclosure/deployed egress検証。A/B/Cとowner surface選定が必要 |

B–Dは計画で、実装済みcapabilitiesや自動Ready Issuesではありません。credentials/provider mediation、
signed/capability ingress、redirect/proxy、compression、Format、generic syncを初期public-file batchへ混ぜません。
Task Aはendpoint/config/schemaを公開しません。Aのrollbackはdocumentation/package/registry revertのみです。
future consumerにはdisable-before-rollbackとcommitted-data recoveryの独自policyが必要です。

## 12. 証拠と参考資料

[High change package](../../.ai/project/changes/external-resource-fetch-policy/design.md) にacceptance criteriaと両言語、
verification、pending human reviewを対応付けます。既存attachment/upload/transport testsは互換性証拠のみで、
proseやskipped testsからnetwork-reach/SSRF/future fetch consumerの安全性を認定しません。

2026-10-07 JSTに確認した外部primary references:

- [OWASP SSRF Prevention](https://cheatsheetseries.owasp.org/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html): allowlist/redirect control/connection-bound DNS対策。
- [RFC 9110 §15.4](https://www.rfc-editor.org/rfc/rfc9110.html#section-15.4): redirect時のheader再構成とsensitive fields。
- [IANA IPv4 special-purpose registry](https://www.iana.org/assignments/iana-ipv4-special-registry) と [IPv6 registry](https://www.iana.org/assignments/iana-ipv6-special-registry): address分類の入力。

ここでのexact limits、厳格なinitial policy、enablement gatesは承認済み調査からのlifetxt設計判断です。
普遍的保証や外部standardの一律mandateではありません。#1095 transactions、#1097 transport、#1098 at-rest、
#1100 projection、#1102 private authorityはそれぞれ独立した境界です。
