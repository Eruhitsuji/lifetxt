# Resource-reference projection v1

[English](../en/resource-reference-projection.md)

## 1. 状態・権限・範囲

これは、オーナー承認済みの
[#1099の決定](https://github.com/Eruhitsuji/lifetxt/issues/1099#issuecomment-6012655572)
に基づく#1100の共有**設計契約**です。「必須」「禁止」は将来の準拠consumerへの要件であり、
現在のendpointが実装済みという意味ではありません。契約の採択にはPRの独立した人間による
設計・security・integrationレビューが必要です。実行コード、lookup DB、endpoint、schema、
Format key、provider adapter、byte syncをこのタスクでは追加しません。

最初の対象はmanaged attachmentと明示的に登録した既存local **file**です。
directoryの閲覧・download、cloud profile、fetchは別判断（#1101、#1102、#1103）です。
ローカルの`file:` / `dir:`と項目リンクの`ref:`の意味を維持します。
Locator、Integrity、Access、Presentationを分離します。opaque referenceは識別のみで、
所持だけでmetadata、open、bytesの認可を与えることは禁止です。

現在のupload receiptの`attachment_id`（#1095/#1096）は受領証でありresolver IDではありません。
Webの`api_item`はdetails/source/text/Markdownを公開します。Remote snapshotは
source/text/Markdownを除去しstructured valuesを再帰的にredactしますが、いずれもこの契約全体の
達成を意味しません。今回新しいcapabilityをruntimeで広告しません。

## 2. 識別子の文法・上限

resource referenceは`att:v1:`の後に32桁の小文字ASCII hexを置いた文字列だけです。

```text
^att:v1:[0-9a-f]{32}$
```

全体39 ASCII bytesです。32桁は暗号学的に安全な乱数16 bytes（128 bits）を表します。
version bitが固定されたUUID、path、digest、item ID、provider ID、それらの決定的hashからは
生成しません。将来のissuerは安全な乱数を使い、lookup store内の一意性を確認し、衝突時は
再生成することが必須です。referenceをdecodeしてpathを得ることは禁止です。

全体を一度だけ厳密にparseします。空白、大文字、escape、percent encoding、Unicode類似文字、
query/fragment、追加separator・bytesは拒否し、別の許容値への正規化をしません。
不正文法は`INVALID_REFERENCE`です。上限内の整形式version tagが`v1`以外なら
`UNSUPPORTED_CONTRACT`とし、pathやlegacy v1へ読み替えません。
構文検査は64 bytesまでとし、それを超える入力はechoせず拒否します。
識別子はcase-sensitiveで有効期限を内包せず、URLではありません。

同じbytes/path/itemでもworkspaceやserver installationが違えば独立したIDを発行することが
必須です。clientはIDをglobal content identityとして比較しません。
同一workspace内では認可されたprincipal間でIDを共有できますが、認可はprincipalごとに行います。
IDとmetadata自体もdisclosure policyの対象です。

## 3. Binding・登録・lifecycle

非公開lookupはIDをserver/install namespace、workspace identity、source identity、
一意なcanonical item、一つのresource-association generationへ結び付けます。
locatorはserver内に留めます。既存source/item/attachmentの権威を再利用し、別の認可engineや
writerを作りません。basename、出現順、行番号、bytes digest、OS pathだけをkeyにしません。

| 状況 | 必須の挙動 |
| --- | --- |
| Managed upload | commit済みで曖昧さのないassociationだけを登録する。失敗transactionから使用可能なbindingを発行しない。receipt喪失は再uploadの許可ではない。 |
| 既存local file | 一意なitem/associationとroot/typeの確認後、server/operatorが明示登録する。自動import/copy/life.txt書換えは禁止。 |
| Read-only source | policyが許せば書込み可能なserver管理binding stateへ登録できる。source編集やcanonical item IDの捏造は禁止。bindingの永続化・検証ができなければunavailable。 |
| Id-less・重複ID item | 使用可能なreferenceなし。unavailableとし、自動ID付与や行番号fallbackは禁止。 |
| 区別不能な重複association | ownerが曖昧さを解消するまでunavailable。出現indexで権威を決定しない。 |
| 同一の検証済みassociationのbytes置換 | resource IDを維持しresource revisionを変更する。旧revisionはstale。 |
| Rename/move | 同じsource/item/associationの連続性を明示検証できる場合だけID維持。path一致やbytes一致だけでは不十分。それ以外は無効化して再登録。 |
| Detach/delete・item/source削除 | association generationを永久に無効化する。同じpath/item ID/bytesでも再添付・再作成は新ID。 |
| Permission revoke | 直ちにprojection/resolutionを拒否。他principalの共有IDまでrotateする必要はないが、再grant後も現在の全確認が必須。 |
| Workspace copy・source rebind・新server | 新workspace/installのIDを発行。source aliasが別originへrebindされたら影響するbindingを無効化。 |
| Restart | 永続bindingが健全で権威あるassociation stateを検証できる場合だけID維持。永続化なしなら旧IDはunavailable。pathから再構成しない。 |
| Restore/rollback | 新binding epochで無効化・再発行。backupからdetach済みIDや旧revision grantを復活させない。 |
| Store喪失・破損・連続性不明 | Fail closed。ownerによる照合後に新規発行し、推測path fallbackをしない。 |

bindingはsecret credential storeではありません。storage layout、atomic enrollment、
concurrency、tombstone retention実装は#1101で具体化します。
consumerは操作ごとに現在のassociationの連続性を検証することが必須です。
外部編集で曖昧になれば無効化し、cached lookupだけで連続性を証明しません。
固定の有効期限は約束しません。unavailable/stale時はclientがrefreshします。

## 4. Identity・revision・integrity

| 概念 | 現在の意味／将来のprojection規則 |
| --- | --- |
| 保存`#sha256=` | 通常`HASH_LENGTH=16`で16 hex桁、SHA-256の64-bit prefix。互換性を維持し、full digest・認可と扱わない。 |
| Full byte digest | 正確なfile bytesの64桁小文字hex。現在の`attachment_revision`はこれを使用する。明示型のoptional `content_digest`はpolicyで許可した場合のみ公開。 |
| Source revision | 現在のtransaction `item_revision`は**source life.txt全体**のhashであり、個別itemではない。無関係なsource編集でもstaleになり得る。 |
| Projected `source_revision` | 必須。workspace/source/epoch内のrandom equality tokenで、server側で既存の正確なsource revisionにbindingする。権威あるsource revision変更で旧tokenを無効化。 |
| Projected `resource_revision` | 必須。workspace/association/epoch内の独立したrandom equality tokenで、正確なbyte revisionとbinding/presentation-policy generationへ結び付け、それらの変更で更新。 |
| Provider version | Adapter固有のobject/version/ETag。暗号学的digestとして解釈しない。このv1では非公開provider versionを直接公開しない。 |
| Directory hash | 現行のtree manifest/hashの意味。単一file digestではなく、最初のfile projection対象外。 |

projected revision tokenは`rev:v1:` + 32桁のrandom小文字hex（39 bytes）とし、
resource IDと同じ厳密なparse・生成制約を使います。構文が同じでもsource/resourceのnamespaceを
分離します。validatorであってcredentialや順序値ではありません。
既存の正確なhashにmappingすることで、private sourceの照合可能なhashを公開せずCASの意味を
維持します。mtime、短縮保存hash、provider ETagで正確なapplicable revisionを代用しません。
成功descriptorやresolving requestで`<missing>`、wildcard、暗黙のlatestは禁止です。

resolverは両方の正確なexpected tokenと現在のbindingを要求します。将来のwriteも既存の
mutation/attachment revision guardを使います。fileがmissingでも暗黙createにはしません。
bytesが不変でもstale source tokenは有効になりません。metadata/policy変更でresource tokenを
無効化し、不適切なcached label/MIMEを再使用させません。別workspace/source/resourceのtokenは
hashが同じでも一致しません。optional digest公開は既知文書の照合が可能なため別許可が必要で、
既定で拒否します。

## 5. File descriptorのallowlist

新DTOを組み立て、transaction/item/providerのdictを転送しません。
将来のconsumerのcontract validatorは未知fieldを拒否することが必須です。

| Field | v1規則 |
| --- | --- |
| `contract_version` | 必須string `"1"`。referenceの`v1`やlegacy attachment v1とは別。 |
| `resource_ref` | 2節の必須識別子。 |
| `kind` | 必須literal `"file"`。未対応kindはunavailable。 |
| `display_name` | 必須の安全な作成済みlabel。1–128 Unicode scalar valuesかつUTF-8で512 bytes以内。既定`Attachment`。local/provider basenameから自動生成しない。 |
| `size_bytes` | Optional。policyが許可した観測済みの正確な非負整数、9007199254740991以下。不明・不許可なら省略し、0で代用しない。 |
| `media_type` | Optional。具体consumerの有限allowlistで許可された観測済みtype。127 ASCII bytes以内、小文字`type/subtype`、parametersなし。不明・unsafe・spoofedなら省略。内容の安全証明ではない。 |
| `source_revision` | 4節の必須projected source token。 |
| `resource_revision` | 4節の必須projected resource token。 |
| `content_digest` | Optional object。`algorithm: "sha256"`と`value: <64 lowercase hex>`のみ。明示的digest公開許可と検証済みfull bytesが必須。既定省略。 |

labelからcontrol、bidi override、locator、credential、private provider detailsを除外することが
必須です。分類不確実なら`Attachment`にします。plain textとして表示し、HTML、Markdown link、
実行入力として扱いません。command、clickable URL、filenameをlabelから生成しません。
sanitizeだけで公開可能にはなりません。size/MIMEにも現在のmetadata権限が必要で、metadata不明は
外部network fetchを誘発しません。media typeだけでsniff/inline表示せず、download/openには別policyが必要です。

常に除外するもの: path/stored_path/value/source/source_text/text/raw/markdown、configured root、
journal/temp/lock path、internal transaction targets、OS command、provider account/tenant/profile/object ID、
credentials、share/capability/signed URL。汎用`extra` bagは禁止です。
objectのwrapperも同じallowlist原則に従います。

## 6. 認可・解決・安全なoutcome

**毎回**のmetadata・将来のbyte/open requestで次を行います。

初回descriptor discoveryにはcaller revisionがまだありません。正確で認可済みの
source/resource snapshotを取得し、serialize直前にbinding/revisions/policyを再検証します。
一貫したsnapshotを確立できなければ拒否します。4のcaller expected tokenはresolving/action
requestで要求します。discoveryはbyte/open/write requestに暗黙latestの例外を与えません。

1. 現在のprincipalを認証し、そのcontextにnegotiated contractをbindingする。
2. 現在のworkspace/source/item/resourceと**action**の権限を確認する。
3. 認可workspace内だけで解決し、一意な現在のmembership、canonical item、resource association
   generationを検証する。callerがpathを上書きすることは禁止。
4. Resolving/action requestでは両方の正確なexpected revisionを現在の権威あるstateと比較する。
   Discoveryでは取得した正確なsnapshotを検証する。
5. configured root/type/symlink/content boundsを適用し、raceによるopened objectの差替えを防ぎ、
   bytes返却・commit前にrevision/authorityを再確認する。
6. 別途認可されたbounded operationだけを行い、Remote OS open planを実行しない。
   連続性やrace-safeなexact-version readを証明できなければ拒否する。

opaque ID、mailbox origin、upload成功、cached metadata、tokenだけでは通過できません。
snapshot/historyの認可はbytes権限を与えません。

| Outcome | 契約response／情報境界 |
| --- | --- |
| 未認証 | `AUTHENTICATION_REQUIRED`（将来HTTP 401）。lookup情報なし。 |
| 不正文法／未対応version | `INVALID_REFERENCE`（400）／`UNSUPPORTED_CONTRACT`（406）。入力echoなし。 |
| Unknown、forbidden、別workspace、removed、missing、ambiguous、id-less、binding破損 | 一律`RESOURCE_UNAVAILABLE`（404）。同じ安全なbodyで、存在理由・locator・lookup由来のtiming差を公開しない。 |
| 認可済みrequestのexpected revision欠落 | `REVISION_REQUIRED`（400）。暗黙latest・current token公開なし。 |
| 現在の認可とassociation検証後のexact revision不一致 | `STALE_REVISION`（409）。認可されたdescriptor経路でrefresh。errorにraw/current revisionを含めない。 |
| 操作・契約が未実装 | `UNSUPPORTED_CONTRACT`（406）／`OPERATION_UNSUPPORTED`（405）。raw path fallbackなし。 |

code/mappingは将来の挙動であり、新routeではありません。messageは上限付きの固定catalogとし、
exception string、label、path、provider responseを返しません。missing/denied/removedを区別しません。
itemがvisibleならassociationに対して一つの汎用unavailable stateを表示できますが、
resource_ref/revisions/metadataとhidden-resource countは省略することが必須です。
id-less item自体はそのpolicyで表示できますが、使用可能なrefは付与しません。
responseは`Cache-Control: no-store`とし、clientはlogout/workspace変更/revokeで保持projectionを
消去し、URLや通常logへ保存しません。

## 7. Disclosure coverage一覧

将来のconsumerは有効な全operationについてこの一覧を完成・検証することが必須です。
安全に再構成できないsurfaceは省略するかoperationを拒否します。
正規表現のpath/secret redactionは補助であり、完全なprojection境界ではありません。

| Surface／既存seam | Restricted clientへの必須representation |
| --- | --- |
| Item list/detail/edit refresh（`webapp.api_item`） | Typed item DTOとdescriptor。raw locator fields省略。現行raw Web routesを安全な代替と扱わない。 |
| Details/title/note/custom fields | Allowlistと分類済みsafe text。`file`/`dir` locator、credential-like/unknown URLを**どのfieldでも**除去。edit formにraw copyを隠して残さない。 |
| Raw source text/plain-text export/clipboard | Raw sourceなし。再構成display textは非canonicalと明示し、write/export可能なlife.txtの代替にしない。安全な再構成不可ならraw export拒否。 |
| Markdown/HTML/link preview | Projected fieldsから生成。元anchor/image/tooltip/DOM attributeにlocator/capability URLを残さない。 |
| Search/snippet/autocomplete/counts | 認可projected dataだけをquery。unsafe queryをechoせず、隠れたlocatorへの一致で存在・countを漏らさない。 |
| Errors/validation/diagnostics | 固定safe codes/messages。raw snippet、exception path、internal/provider details、secret query parameters除去。 |
| Capabilities/command catalog/OpenAPI/examples | Version/kinds/action limitsのみ。configured roots、raw path例、provider credentials、restricted clientへのlegacy raw-path案内を含めない。 |
| History/revisions/diffs/recovery evidence | Current **かつ**historical disclosure permission。before/afterをprojectしjournal/artifacts/raw source除去。不確実なら拒否。historyからbyte権限を継承しない。 |
| Audit/logs/support evidence | 最小限の許可principal/workspace識別子、operation/code、policy許可のscoped reference/revision token。label/digest/path/URLは既定除外。保護された内部照合はpublic exportではない。 |
| Workspace/sync/package manifests | Opaque scoped workspace/source identity、許可roles/revisions、descriptorのみ。path/relative path/package entry names/download URL/bytesなし。 |
| Upload receiptと続くUI refresh | 現行receipt IDを別物として維持。新consumerが別途登録・projectし、全refresh/edit/search routesでnegotiated boundaryを適用。 |
| MCP tools/resources、Remote、Cloud Mailbox wrappers | Nested resultも統一projection。wrapper/origin/message所持は権限にならない。resourceだけを隠して同じrestricted principalのtool raw結果を残さない。 |
| Browser cache/offline state/copy/share/redirects | Storage、address/referrer、console、action payloadにlocal/provider locatorやcredential URLなし。opaque refはnavigation URLではない。offline replicationは対象外。 |

HTTPSやqueryなしはpublicの証明ではありません。capability secretはpathにもあります。
意図的にpublicとされたsecret-freeかつpolicy許可のURLだけ、他のprojected item fieldsに残せます。
unknown/private/capability/signed URLは全体を非公開にし、queryだけ削除するfallbackは禁止です。
既存source/historyのsecretは別途ownerがremediationし、この契約で履歴を消去しません。
metadata保存・表示はinertで、server fetch/provider login/importをしません。

## 8. Negotiation・互換性

Opt-inの`resource-reference-v1` featureとdescriptor contract `"1"`を選びます。
将来のattachment operation v2がこれを運ぶことも可能です。
consumerはprotocol/versionとrestricted disclosure policyを認証session、workspace、
**全**有効surfaceへ明示bindingすることが必須です。request headerだけではpolicy境界になりません。

serverはcoverageとoperation tests合格後だけ広告できます。restricted clientはこの契約を必須とし、
未広告、未対応version、部分coverage、無効operationは明示失敗します。
client/serverとも同じrestricted credentialsでlegacy attachment v1やgeneric raw Web routesへ
retryすることは禁止です。既存認可でrestricted principalの代替raw routesを拒否する必要があり、
できなければ新responseが安全でもdeploymentは準拠を名乗れません。version discoveryも安全にします。

`attachment-remote-operation-v1.schema.json`、`attachment-chunk-v1.schema.json`、
他のattachment v1 schemasとpath-based legacy behaviorを維持します。
信頼されたpath-aware legacy clientはoperatorの明示選択を必要とします。
operator選択sourceへのlocal CLI/TUI/MCPはreadable raw accessを維持します。
MCPのread/assist/full tool profileだけではexternal-safe disclosure modeになりません。
Remote MCP consumerはserver policyに従います。

#933のworkspace/source identity、authorization、redaction、revisionをseamとして再利用しますが、
既存opaque identityは決定的resource IDやdigest照合可能なrevision公開の許可ではありません。
#1097 TLSと#1098 at-rest protectionは別境界として引き続き必要です。
具体consumerとnegotiation/envelopeの承認までschemaを追加しません。
現行`dist/schemas`が以下の提案例を検証すると説明してはいけません。

## 9. Serialized review例・acceptance scenarios

以下は合成fixtureであり、reference/revisionはいずれもcredentialではありません。
設計例であって実行可能なAPI callではありません。この例ではMIME/size/label公開を許可し、
digest公開は許可していません。

```json
{
  "contract_version": "1",
  "resource_ref": "att:v1:8cb4d9e603a71f25b6c082de49f135a7",
  "kind": "file",
  "display_name": "Quarterly report",
  "size_bytes": 2048,
  "media_type": "application/pdf",
  "source_revision": "rev:v1:4d10b7926ac83f05e914d0cba672853f",
  "resource_revision": "rev:v1:721ba4d085cf639a10e7b82d954f6c30"
}
```

denied/unknown/removed/別workspace/missing/ambiguous/id-lessのresolutionは同じbodyです
（将来HTTP 404）。

```json
{"error":{"code":"RESOURCE_UNAVAILABLE","message":"Resource unavailable."}}
```

認可済みでsource **または**resource revisionがstale（将来HTTP 409）:

```json
{"error":{"code":"STALE_REVISION","message":"Refresh the resource descriptor."}}
```

visible itemのid-less/ambiguous associationで使用可能なreferenceなし:

```json
{"resource_state":"unavailable"}
```

| Review input | 期待するcontract確認 |
| --- | --- |
| 裸ID・大文字・31/33桁・空白・percent encoding・suffix | 厳密文法で拒否。64 bytes超は追加検査前に拒否。 |
| 別principal/workspaceで盗用・replayするvalid ID | 現在の全認可を要求。path/content一致でもunavailable。 |
| 両revision一致でもrelation削除・再作成 | 旧associationはunavailable。新登録は新ID。 |
| 同じfile bytesで別のsource item編集 | Source tokenがstale。source全体のCAS semanticsを維持。 |
| Source不変でもbytes/presentation policy変更 | Resource tokenがstale。旧content/不適切metadata fallbackなし。 |
| Read-only sourceで安全なdurable server bindingなし | Unavailable。source write・一時path由来IDなし。 |
| Full digest公開許可あり | Optional typed content_digestだけ、64桁hex。短縮保存hash・provider ETagで代用不可。 |
| Title/note/Markdown/search/history/manifestにlocator/capability URL | Serialize前に省略・拒否。成功receiptだけでは不十分。 |
| Negotiation欠落・unsafeな代替route有効 | Unsupported／非準拠。downgradeなし。 |

将来のacceptanceは実際の全有効surfaceでTOCTOU、revoke、restart/restore、hidden count、
workspaceを越えたdigest照合を含めて検証します。現在のcompatibility testsは旧挙動維持だけの証拠です。
証拠と未実施human reviewは
[change package](../../.ai/project/changes/resource-reference-projection/design.md)
を参照してください。resolver/byte operationsは引き続き#1101です。
