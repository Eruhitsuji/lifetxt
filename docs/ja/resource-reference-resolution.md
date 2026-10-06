# 制限付きresource-reference consumer v1（承認案）

[English](../en/resource-reference-resolution.md)

## 1. 状態と採択ゲート

#1110は、ownerが採択した#1101の勧告と採択済みの
[projection契約](resource-reference-projection.md)を具体化します。この契約は
**ownerのセキュリティ・設計承認を求める提案**です。新しいroute、設定、schema、
capability、resolver、binding store、byte操作はまだ実装していません。
承認記録が残るまでは要件・設計具体化の段階です。Issueへの対応依頼を、
今回新しく定義したenvelopeへの承認として記録しません。

最初のconsumerは、明示的に登録したlocal regular fileを扱う専用の
**restricted Remote protocol 2、bearer専用client**です。既存のRemote認証、
workspace/source/item visibility、transactionを再利用し、byte取得には別の
`attachment:read` grantを要求します。通常の`read`、owner/editor role、upload receipt、
history権限からの自動付与はありません。browser session、local CLI/TUI/MCP、
legacy attachment v1、raw Web、directory、provider/fetchの変更は含みません。
Browser対応には、session mode分離、CSRF、Origin、Fetch-Metadata guardを備えた
別のconsumer設計・reviewが必要です。

最初の実装候補platformはLinuxです。kernel/helper/filesystem/rootの実証と
bounded supervisionが必要で、Linuxというだけでは対応済みになりません。
他platformや前提不足ではfail closedとし、featureを広告しません。
#1111/#1113/#1114が永続化・resolver・deliveryを個別実装します。それらが安全な読取りを
主張する前に、#1112/#1115のevidenceのreviewが必要です。

## 2. 認可設定と分離

将来のoperator policyとして、次の明示的な決定を提案します。これらは契約上の概念で、
**現在lifetxtが受け付ける設定keyではありません**。設定の実装時にはregistryの
既定値・型・provenance・restart・secret・version情報、`config explain`、日英docs、
fixture、migration/downgrade testを同時に更新します。

| Policy概念 | 初期設定の要件 |
| --- | --- |
| Consumer有効化 | 既定で無効。resource-reference-v1への明示opt-in、selected workspace、単一binding owner、健全なroot/helperを要求。 |
| Principal disclosure mode | restricted-resource modeを明示指定。request headerで切替不可。mode変更では旧credential/sessionを失効。 |
| Principal identity | trusted generic Web、legacy Remote、proxy、browser identityと異なる専用principalとbearer credential。shared-token alias不可。 |
| Metadata authority | 現在の既存read、selected-workspaceの明示read membership、source role/item visibilityに加え、enrollmentとmetadata policy。 |
| Byte authority | 全metadata/association gateに加え、principal scopesの明示attachment:read。roleから自動付与しない。 |
| 任意情報の開示 | size/MIME/authored labelは現在のmetadata policyで個別制御。full digestは別の明示opt-inで、既定では省略。 |
| Legacy/raw分離 | anonymous/shared-tokenで到達できるraw workspace APIを残さない。trusted generic Web/legacy credentialとnetwork exposureを分離・検証。不明なら有効化拒否。 |
| Browser/trusted proxy | 初期consumerでは受付不可。restricted bearerを別modeへloginさせたりbrowser sessionへ交換したりしない。 |

Restricted credentialが呼べるのは第3節の三つの正確な操作と、将来のallowlist付き
capability handshakeだけです。generic Web item/source/raw/export、legacy attachment/
path/open-plan/upload、Remote snapshot/search/history/audit/mutation、MCP/tool wrapper、
未分類の別routeは拒否します。legacy error/redirect/payload生成前に拒否します。
全method、alias、mounted route、middleware errorを対象にします。version header変更で
通常principal modeを取り戻すことはできません。

将来有効化するcapability handshakeはprotocol 2、feature resource-reference-v1、kind file、
この操作名と有効な上限だけを返します。raw manifest/command catalogを再利用しません。
広告前にrestricted identityで全enabled operation/errorを試験し、generic raw exposureも
検査します。部分対応、未対応platform、schemaだけでは広告しません。
Schema公開はconsumerの有効化を意味しません。

## 3. Negotiationと正確な操作分類

既存の`/api/remote/v1` route namespaceを再利用します。pathのversionでRemote protocol 1を
選ぶわけではありません。各操作で正確な`X-Lifetxt-Remote-Version: 2`と
`X-Lifetxt-Resource-Contract: resource-reference-v1`を要求し、安全な成功応答で両headerを
返します。欠落・未対応・重複・comma結合されたnegotiation値は406
`UNSUPPORTED_CONTRACT`とし、自動downgradeしません。headerが一致しても毎requestで
principal mode、selected workspace、policyを再検証します。

| Methodと提案route | 操作 | Membership | Write-clock/read-only分類 |
| --- | --- | --- | --- |
| POST /api/remote/v1/resource-references/discover | Item単位descriptor discovery | 明示read | Read-only。この正確な組合せだけmutation clock免除 |
| POST /api/remote/v1/resource-references/full | Exact-revision full bytes | 明示read + attachment:read | Read-only。同じ限定的免除 |
| POST /api/remote/v1/resource-references/chunk | Exact-revision bounded slice | 明示read + attachment:read | Read-only。同じ限定的免除 |

この組合せだけをreadとして分類し、末尾slash aliasや別methodは免除しません。
Byte/discovery routeのGET/HEADは405 `OPERATION_UNSUPPORTED`です。
Read gateを全部満たせばread-only workspace/serverでも操作できます。Enrollment、login、
replacement、delete、実際のmutationでは既存の認証、CSRF、write membership、read-only、
write-clock guardを維持します。POST全般の免除は禁止です。

このconsumerではloopbackも含めてTLS必須です。#1097のimmediate-peer trusted-proxy
有効origin policyを再利用し、任意のforwarding headerを信用しません。
Token、resource ref、revisionはURL/query/fragment/redirectへ入れません。
認証は`Authorization: Bearer`だけです。query token、ambient cookie、identity proxy header
から権限を補充・上書きしません。全query parameterとURL userinfo credentialを拒否します。
Authorization/request bodyをlogに記録しません。parse前にpre-auth boundを適用し、
lookup前にtransport/authenticationを確認します。不正envelopeではlookupしません。

## 4. 型付きenvelopeとdescriptor文法

全JSON requestはUTF-8 object、`Content-Type: application/json`です。compression、
重複key、未知field、null、integer fieldのbool、非有限数・小数、不正UTF-8、BOM、
末尾余剰inputを拒否します。wire bodyは空白を含め2,048 bytes以下です。
文法上正しいbounded non-v1 att/rev versionは406 UNSUPPORTED_CONTRACTとし、
legacy/path requestへ変換しません。reference/tokenごとの検査は64 bytesまでです。
それ以外の不正値はechoなしの400です。一度だけparseし、unescape/normalizeで別の受理可能identifierへ変換しません。
曖昧な重複headerと過大桁数も拒否します。`contract_version`はrequest/descriptor/result
すべてで文字列`"1"`固定です。

| Field / envelope | 型と上限 |
| --- | --- |
| workspace_id, source_id | 正確な64桁lowercase ASCII hex。#933のselected workspace/source handleを再利用し、pathやbyte digestと解釈しない。workspace照合は必ず現在membershipも確認。 |
| item_id（discoveryのみ） | 既存の著者指定canonical id。1..128 Unicode scalar、UTF-8で512 bytes以下。control/bidi control/surrogateを除外。完全一致。title/line/ordinal/generated-id fallback不可。範囲外の既存idはsourceを書き換えずunavailable。 |
| Discovery request | contract_version, workspace_id, source_id, item_idのみ。discoveryにcaller revisionなし。 |
| Discovery success | contract_version, resourcesのみ。resourcesは認可済みdescriptor 0..16件。hidden count/reason/locator/cursor/raw item fieldなし。可視で適格なresourceが16件を超える場合、全体を固定RESOURCE_LIMITで拒否し、黙って切り詰めない。 |
| Full request | contract_version, workspace_id, resource_ref, source_revision, resource_revisionのみ。 |
| Chunk request | Full fieldにoffset（integer 0..10485760）、length（integer 1..65536）を追加。clamp不可。 |
| resource_ref | att:v1: + 32桁lowercase ASCII hex、39 bytes固定。random 128-bit identityでありpathへdecodeしない。 |
| source_revision, resource_revision | rev:v1: + 32桁lowercase ASCII hex固定。別random namespaceでexact source bytes/resource snapshotとpolicy generationへbinding。full/chunk必須、wildcard/latest不可。 |
| Descriptor必須field | contract_version, resource_ref, kind="file", display_name, source_revision, resource_revision。 |
| display_name | 1..128 Unicode scalar、UTF-8で512 bytes以下。control/bidi/surrogate/locator/credential/provider detailなし。安全なauthored labelのみ、既定Attachment。plain textで扱う。 |
| size_bytes | Metadata authority確認後の任意のexact nonboolean integer 0..10485760。不明/非開示なら省略し、0で代用しない。 |
| media_type | 任意の有限enum: application/octet-stream, text/plain, application/pdf, image/png, image/jpeg, image/gif。検証・policy承認済みのみ。parameter/sniffing/inline renderingなし。 |
| content_digest | algorithm="sha256", value=exact full snapshotの64桁lowercase hexだけを持つ任意object。別の明示開示権限が必要、既定省略。16桁stored hash/ETag/provider versionで代用不可。 |

Wrapper/digest objectを含め未知fieldは再帰的に禁止です。SchemaではUTF-8 byte数、
safe label分類、重複JSON key、random issuance、authority、association continuity、
exact revision bindingを証明できません。これらにはsemantic validationと別runtime testが
必要です。workspace/source handleからresource/revisionの決定的IDやraw source hashを
作ってよいわけではありません。

Discoveryは現在認可されたitem/associationの一貫snapshotをserialization前に再検証します。
可視でもid-less/duplicate/ambiguous item selectorは一様404です。idは捏造しません。
認可済みの一意itemでは、適格・可視・登録済みresourceだけをresourcesへ入れます。
Hidden/unavailable associationはplaceholder/countに加えず、0件も安全な結果です。
Discoveryはbyte grantを発行しません。

初期consumerではoperatorが認可済みworkspace_id/source_id/item_id selectorだけを
protected channelでclientへ明示的に別途提供します。discoveryの準備としてraw snapshot/
manifestをコピーしたり、このclientでtrusted credentialを使ったりしません。
この契約にitem/source inventory routeはなく、将来のsafe inventoryには別の型付きprojection
契約が必要です。handleはidentityだけを表し、discovery時に改めて認可します。

## 5. Exact bytes、固定上限、response header

Full/chunkは現在principal、明示workspace read membership、source/item/resource authority、
一意なlive generation、両expected token確認後にだけresolveします。
Confined regular-file handleでbounded immutable snapshotを取り、exact bytesを検証し、
emission前にsource/association/authorityを再確認します。path確認後の別open、別openの
前後hash、mtime、short hashでは不十分です。removed/recreated associationはstale判定の前に
unavailableです。resource bytesが同じでもsource bytesの変更でsource tokenはstaleです。

| Resource / cost | Hard ceiling（既存policyが低ければそちらを優先） |
| --- | --- |
| File/full snapshot | min(10 MiB = 10485760 bytes, existing max_file_bytes) |
| Chunk | min(64 KiB = 65536 bytes, existing chunk/file policy)。毎requestでfull snapshotを検証 |
| Source parse | 1 MiB/source、5,000 items/source、10,000 items/selected workspace。cap+1を検出しfail closed |
| Discovery serialization | 可視descriptor 16件、encoded JSON response 32 KiB |
| Active work | 2/process、1/principal、waiting work queueなし。receive/validation/worker stop/sendまでslot維持 |
| Rate | 30/min/principal、120/min/process。既存principal limitが低ければ優先。pre-auth global 120/min/process |
| Absolute deadline | receive/prepare/delivery込み30秒。disconnect/cancelでもworker停止までslot保持。bounded supervisionできないfilesystemは拒否 |
| Binding quota | active 10,000、tombstone込みtotal 50,000 records。liveのsilent eviction/retired-id再利用不可 |

Request field、role、header、高い設定値で上限を増やしません。full/chunk検証はactive
operationごとにO(file bytes)時間、O(file cap)memoryで、小さいsliceもfull verificationの
bounded costを要します。failureもrate/pre-auth/slot対象です。source/file oversizeは一般の
RESOURCE_UNAVAILABLE、discovery件数/serialization上限は認可済みitem確認後のみ固定
RESOURCE_LIMITです。

Byte成功応答は200 binaryであり、base64 JSONや206ではありません。必須headerは
`Content-Type: application/octet-stream`、`Content-Disposition: attachment; filename="download.bin"`、
送信byte数に正確な`Content-Length`、`X-Content-Type-Options: nosniff`、
`Cache-Control: private, no-store`、`Referrer-Policy: no-referrer`、
`Cross-Origin-Resource-Policy: same-origin`、`X-Frame-Options: DENY`、
`Content-Security-Policy: default-src 'none'; frame-ancestors 'none'; sandbox`、
両negotiation header、検証済みexpected tokenだけをechoする
`X-Lifetxt-Source-Revision`と`X-Lifetxt-Resource-Revision`です。
Chunkではdecimal `X-Lifetxt-Next-Offset`（offset + 返却bytes）と
`X-Lifetxt-EOF: true|false`も返します。digest ETag、Last-Modified、Content-Range、Location、
source hash、local basenameは出しません。CORS grant、content compression、inline previewは
ありません。JSON discovery/errorにもno-store/referrer/CORP/nosniff/frame/CSPと安全な
JSON content typeを適用します。

Range/If-Range headerは400 INVALID_REQUESTで拒否し、HTTP latest fallbackに変換しません。
offset==sizeはempty 200、Content-Length: 0、EOF trueです。offset>sizeは認可・revision確認後に
固定INVALID_REQUESTです。chunk clientは両tokenを固定し、header/length/next offsetを検証し、
stale/unavailable/abort時には受信済みchunk全部を破棄して認可付きrediscoveryへ戻ります。
Full clientも不完全transferを破棄します。0 bytesはContent-Length: 0の場合だけ有効です。

最初のbyte前と各64 KiB以下のemission前にauthority/association/revisionを再確認します。
Header前ならsafe error、header後ならJSONを追加せずabortします。length一致だけでは
完了証明にならず、clientはtransport正常完了も要求します。既送信bytes/保存済みcopyは
revokeできません。byte recipientが取得byte数を知ることはmetadata非開示でも防げません。

## 6. 固定のsafe outcomeと別経路拒否

Error envelopeは正確に{"error":{"code":...,"message":...}}です。code/messageの組合せは
次の固定catalogのみとし、raw exception/caller inputは使いません。details、current token、
label、size、path、diagnostic、request body echoなしです。

| HTTP | Code | 正確なmessage |
| --- | --- | --- |
| 401 | AUTHENTICATION_REQUIRED | Authentication required. |
| 400 | INVALID_REFERENCE | Invalid resource reference. |
| 400 | REVISION_REQUIRED | Expected revisions required. |
| 400 | INVALID_REQUEST | Invalid request. |
| 404 | RESOURCE_UNAVAILABLE | Resource unavailable. |
| 409 | STALE_REVISION | Refresh the resource descriptor. |
| 406 | UNSUPPORTED_CONTRACT | Contract unavailable. |
| 405 | OPERATION_UNSUPPORTED | Operation unavailable. |
| 429 | RESOURCE_LIMIT | Resource limit reached. |
| 503 | RESOURCE_BUSY | Resource service unavailable. |

Lookup前に認証します。envelope errorは存在lookupなしで返せます。有効なfull/chunkでrevisionが
欠ける場合はcurrent値を返さずREVISION_REQUIREDです。unknown/denied/wrong-workspace/
id-less/duplicate/removed/missing/corrupt/uncertain bindingとbyte grant欠落は同じ
RESOURCE_UNAVAILABLE bodyで、lookup由来のtiming差を作りません。restricted requestの
別routeも認証後に同じsafe 404です。現在認可済みlive association確認後にだけ
STALE_REVISIONとし、forbidden resourceの変更を漏らしません。negotiation/platform/service全体の
unsupportedはresource個別lookupなしで406です。rate/slot/deadline errorはresource状態を
出さず、header後のfailureはabortです。

Auditは既存protected sinkのみへsafe principal/workspace identity、operation、固定outcome、
server生成correlationを記録します。scoped ref/revisionには明示audit policyが必要です。
label/path/digest/provider URL/raw exception/body/Authorizationは除外します。
Capability、HTTP middleware、log、reverse-proxy access/error logも同じreview対象です。
raw alternate accessが残る場合、安全な新route出力だけでは不十分です。

## 7. 合成envelope例と受入scenario

順にdiscovery request/result、full request、chunk request、認可済みempty discovery、
一様unavailable、stale、unsupportedです。Review fixtureであり、**実行できるendpointでは
ありません**。labelのmetadata開示は許可済み、任意のdigest/size/MIMEは省略しています。

```json
{
  "contract_version": "1",
  "workspace_id": "dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd",
  "source_id": "eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee",
  "item_id": "task-1"
}
```

```json
{
  "contract_version": "1",
  "resources": [
    {
      "contract_version": "1",
      "resource_ref": "att:v1:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
      "kind": "file",
      "display_name": "Attachment",
      "source_revision": "rev:v1:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
      "resource_revision": "rev:v1:cccccccccccccccccccccccccccccccc"
    }
  ]
}
```

```json
{
  "contract_version": "1",
  "workspace_id": "dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd",
  "resource_ref": "att:v1:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "source_revision": "rev:v1:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
  "resource_revision": "rev:v1:cccccccccccccccccccccccccccccccc"
}
```

```json
{
  "contract_version": "1",
  "workspace_id": "dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd",
  "resource_ref": "att:v1:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "source_revision": "rev:v1:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
  "resource_revision": "rev:v1:cccccccccccccccccccccccccccccccc",
  "offset": 0,
  "length": 65536
}
```

```json
{
  "contract_version": "1",
  "resources": []
}
```

```json
{
  "error": {
    "code": "RESOURCE_UNAVAILABLE",
    "message": "Resource unavailable."
  }
}
```

```json
{
  "error": {
    "code": "STALE_REVISION",
    "message": "Refresh the resource descriptor."
  }
}
```

```json
{
  "error": {
    "code": "UNSUPPORTED_CONTRACT",
    "message": "Contract unavailable."
  }
}
```

| Scenario | 必須の結果 |
| --- | --- |
| Id-less item、duplicate canonical id、曖昧な重複association | 使用不可selectorは一様404。source書換え/ordinal fallbackなし。適格itemのdiscoveryでもhidden/unavailable associationは列挙しない。 |
| Removed後に同じid/path/bytesで再作成 | 旧refは404のまま。再enrollmentは新random ref。 |
| 別workspace/credentialへrefを持込 | 404。内容やrevision文法の一致は認可ではない。 |
| 現在認可済みsource変更、file bytes同一 | 409。自動latest readなし。 |
| Byte/presentation/metadata policy変更 | 現在authority確認後に409。旧resource tokenで旧bytes/labelを取り戻せない。 |
| Viewer/ownerにreadはあるがattachment:readなし | Metadata policyが許せばdiscovery可。full/chunkは404。 |
| 健全なbinding/read membershipのあるread-only source/server | Discovery/full/chunk可。enrollmentでlife.txtは変更不可。 |
| 未対応OS/kernel/helper/rootまたはcontinuity proof不足 | 406、capability非広告、path/legacy fallbackなし。 |
| Unknown field、bool offset、short digest、percent/uppercase/suffixed ref | 400。未知fieldでpath/追加情報を持込不可。 |
| Range/If-Range、wrong method、contract header欠落 | 順に400/405/406。downgradeなし。 |
| Chunk間/full send中のrevoke/change | Header前は404/409、後はabort。partial bytesを破棄。 |
| Generic Webがanonymous/同じcredentialでraw workspaceを開示 | 三つの応答が安全でもsafe consumer有効化を拒否。 |

## 8. Schema公開計画と検証の境界

第1～7節へのownerの明示承認後、#1110をReadyへ具体化して
`lifetxt/schema_extensions_v33.py`（main更新で使用済みなら次の未使用番号）を既存の
schema-extension bootstrap、generator/sample pipelineへ追加します。新outputはlegacy
attachment v1ではなくresource-reference-*の名前で、次を提案します。

- resource-reference-descriptor-v1.schema.json
- resource-reference-discovery-request-v1.schema.json
- resource-reference-discovery-result-v1.schema.json
- resource-reference-full-request-v1.schema.json
- resource-reference-chunk-request-v1.schema.json
- resource-reference-error-v1.schema.json

Schemaはdraft 2020-12、closed object、固定string contract version、完全anchor付きidentifier
文法、明示required field、bounded integer、有限MIME、固定code/message pair alternativeです。
Discovery resultは同じdescriptor shapeをembed/reuseします。200 binary bodyは第5節の契約で
扱い、JSON schemaと偽りません。Matching testはpositive/negative schema validation、未知nested
field、digest文法、nonboolean bound、sample/generator parity、日英例を対象にします。
既存attachment v1 generated schemaはすべてbyte単位で維持します。JSON Schemaでは証明
できないsemantic gateも明記し、round tripでruntimeを証明したことにはしません。

承認段階の検証は日英JSON parity/round trip、identifier例、local reference、package/registry
parse、scope、legacy schema非変更です。まだschema/contract test実装の許可はありません。
独立した人間による設計・security/integration reviewは未完了です。Rollbackはdocs/package/
task固有registry追加のrevertで、data migration/deployment/releaseはありません。
