# 制限付きリソース参照・ダウンロード

専用HTTP consumerは既存の任意Web依存を利用します。起動前に`pip install "lifetxt[web]"`で導入してください。binding/resolverに必須依存の追加はありません。

[English](../en/resource-reference-runtime.md) · [通信契約](resource-reference-resolution.md)

#1111/#1113/#1114の実験的な専用Bearer方式のRemote 2 consumerです。既定は無効です。
有効化するとWebアプリ全体が専用ASGIアプリに切り替わります。GUI、OpenAPI、一般Web、
旧Remote、ブラウザログイン、proxy identity、MCP、検索、履歴、更新、通常のcapability
manifestを搭載しません。同じワークスペースの一般Web/raw APIを、別の到達可能なlistener
で公開しないでください。実際のネットワーク分離・proxy構成は運用側で確認します。
自動capability広告や旧クライアントへのフォールバックはありません。Linux x86_64/glibc、
検証済みヘルパー、対応kernel・ローカルfilesystem・root権限が必要です。条件不足は安全側で
起動または読み取りを拒否します。他環境の通常のローカル機能は従来どおりです。

## 設定と起動

1. [任意のsnapshotヘルパー](attachment-snapshot-helper.md)をビルド・設置します。
   sourceは具体的なローカル通常ファイルに限定します（最大100）。glob、directory source、
   symlink、hardlink、他利用者が書き込めるrootや非対応filesystemには対応しません。
2. サーバ利用者が所有する0700の専用ディレクトリに、明示的に新しいindexを作成します。
   起動時に紛失・破損したDBを自動作成・置換しません。

   ```python
   from lifetxt.resource_reference_store import BindingStore
   BindingStore.provision("/srv/lifetxt-private/bindings.sqlite")
   ```

   これは運用用の例示pathで、HTTP入力には使いません。DB・owner lockは0600です。
   単一owner用にSQLiteのDELETE journalとsynchronous FULLを採用します。復元・持込された
   WAL/SHM/journalは採用・再生せず拒否します。SQLiteは暗号化ではなく、既存の保存先保護と
   信頼するlocal writerの前提が必要です。transactionごとにDB identity・epoch・root権限を
   確認します。最大10,000 active／token・tombstone込み50,000 recordsで、自動削除・eviction・
   ID再利用はしません。
3. 名前付きworkspaceと**明示的なcollaboration membership**を設定します。全体のreader／
   ownerだけでは不十分です。専用の異なる`token_env`に認証情報を置き、一般Web・旧Remote・
   proxy・ブラウザのcredentialと共用しません。専用アプリ上の全active principalに
   `disclosure_mode: "restricted-resource"`を設定します。ダウンロード可能なprincipalには
   `attachment:read`を明示指定します。roleから自動付与しません。
4. `remote.resource_references.enabled`をtrueにし、`workspace_id`、絶対pathの`store_path`、
   ownerが認めた`enrolled_items`を指定します。selectorは`source_id`・既存のcanonical
   `item_id`・既存`file:`詳細値と完全一致する`attachment`だけです。sourceにIDやfileを追加
   しません。workspace/source handleは運用側から別途クライアントへ渡します。
   [設定例](../../examples/config/resource-references.lifetxt.json)は編集するまで無効です。
   起動時の最初のactive principalが全selectorを検証できなければ起動を拒否します。
   HTTP discoveryから登録・state修復・path指定はできません。
5. 例：`lifetxt --config lifetxt.config.json serve --read-only`で**1 worker**を起動します。
   loopbackでもTLS必須です。分離したTLS終端proxyと明示的なtrusted immediate peer、または
   TLS対応ASGIサーバを使用します。Uvicornのproxy header書換えを無効にし、実際のASGI peerを
   保持します。未信頼peerの転送headerはTLSの証明になりません。一般/raw listenerを併設
   して迂回経路にしないでください。

## 設定metadataと変更方法

新しい設定は保護された運用JSONから読み、HTTPや環境変数overrideから変更しません。
credentialだけは既存の`token_env`を利用します。全設定は非secret、導入version 1.0.3、
resource contract `"1"`で、deprecated／replacementはありません。型・defaultはconfig-v1
schemaと`config explain`の共通registryに登録しています。metadata・scope・membershipは
操作ごとに再確認し、consumer/storage/selector/limit/identity/mode変更には再起動が必要です。
未知の将来contract version、未知key、型・上限違反は拒否します。mode変更時は認証情報も
変更し、再起動してください。起動中の専用アプリはcredential digestを固定し、旧Bearerを
trusted identityへ昇格させません。設定を戻す際もcredentialを旧値に戻しません。

| 設定 | 型・default | 変更条件 |
| --- | --- | --- |
| remote.resource_references | object、以下のdefault | 保護された運用設定のみ |
| enabled | bool false | 再起動、明示opt-in |
| contract_version | string "1"のみ | 再起動、downgradeなし |
| workspace_id | canonical 64-hex string/null、null | 再起動、対象workspaceを明示 |
| store_path | absolute string/null、null | 再起動、事前作成済みindex |
| enrolled_items | array、[] | 再起動、source_id/item_id/attachmentの完全一致 |
| metadata.label | bool false | 現行policy、初期版は常にAttachment |
| metadata.size | bool false | 検証したsize_bytesの開示opt-in |
| metadata.mime | bool false | 初期の検証済み値はapplication/octet-streamのみ |
| metadata.digest | bool false | 個別opt-in、完全snapshotのSHA-256のみ |
| limits.file_bytes | integer 10485760 | 再起動、減らすのみ、既存file上限も適用 |
| limits.chunk_bytes | integer 65536 | 再起動、減らすのみ、既存chunk上限も適用 |
| limits.active_process | integer 2 | 再起動、減らすのみ、認証前準備・送信も含む |
| limits.active_principal | integer 1 | 再起動、上限1固定 |
| limits.rate_principal | integer 30/分 | 再起動、減らすのみ、既存の低い上限も適用 |
| limits.rate_process | integer 120/分 | 再起動、減らすのみ、認証前全体上限120/分 |
| limits.deadline_seconds | integer 30 | 再起動、減らすのみ、受信・検証・hash・送信を含む |
| remote.principals.*.disclosure_mode | trusted/restricted-resource、trusted | 新credential＋再起動、headerで切替不可 |

sourceは1MiB・5,000 items/source・10,000 items/workspace、discoveryは16 descriptors・
32KiBまでです。送信単位ごとに現行関連付け・revisionを検証するため完全hashを再取得します。
小さいchunkでも完全検証が必要で、source数・送信回数に応じてCPU/I/Oが増えます。全処理に
絶対deadlineが適用され、失敗もrate/admissionに数えます。切断・cancel後も物理workerが
停止するまで枠を保持します。任意auditの項目はprincipal/workspace handle・操作・固定結果・
生成request IDのみで、body・参照ID・token・path・digestは記録しません。

## クライアントからの利用

以下の完全一致endpointにPOST JSONを送り、query parameterは使いません。

- `/api/remote/v1/resource-references/discover`：contract_version/workspace_id/source_id/item_id。
- `/api/remote/v1/resource-references/full`：contract_version/workspace_id/resource_ref/source_revision/resource_revision。
- `/api/remote/v1/resource-references/chunk`：fullの項目＋整数offset・length（1..65536）。boolは不可。

専用`Authorization: Bearer`、`Content-Type: application/json`、
`X-Lifetxt-Remote-Version: 2`、
`X-Lifetxt-Resource-Contract: resource-reference-v1`が必要です。bodyは2048 bytesまでで、
重複key、未知field、bool整数、BOM、圧縮、cookie、Origin/browser Fetch-Metadata、proxy
principalは拒否します。unsupported negotiationからfallbackしません。取得した2つの
revision tokenを変更せず、fullと全chunkに付けます。[公開schema](resource-reference-resolution.md)
で入力形状を確認できます。

full/chunkの成功はbinary 200、application/octet-stream、固定
`attachment; filename="download.bin"`、実際のContent-Length、検証済みrevision headerです。
inline preview・digest ETag・redirect・provider fetch・CORSはありません。chunkにはnext-offset／
EOFが付き、offset==sizeは空の200、offset>sizeは認可後に拒否します。Range/If-Rangeはlatestや
全体取得に変換せず拒否します。

返却token・型・長さ・next-offset・通信の正常完了を確認してください。stale/unavailable、
中断、不完全な通信、header不一致なら**蓄積した結果全体を破棄**し、再discoveryします。
空fileでもContent-Length 0と正常完了の両方が必要です。header送信前の変更・権限取消しは
固定error、送信後はbinaryにJSONを追加せず接続を中断します。既に受領・保存したbytesは
回収できません。認可済みrevision不一致だけがSTALE_REVISIONで、非公開・別workspace・
不存在・曖昧・取消済み・失効済みは同じRESOURCE_UNAVAILABLEです。

## ID・復旧・rollback

全ての起動・復旧で公開参照epochをランダムに新規作成します。clean restart・DB copy・backup
復元でも旧ID/tokenは使用できません。登録時にsourceを再検証し、sourceには書き込みません。
重複・IDなしitemにIDを作りません。観測したsource bytes/identity変更はsourceの関連付けを
失効させます。file不存在・link・identity不確実性も該当参照を失効させます。解除後の再作成は
同じpath/bytesでも新IDです。rename continuity保証・再起動後のID維持は実装しません。
同じUIDの悪意あるwriterや特権侵害は保証対象外で、inode照合は敵対writerに対するABA証明では
ありません。state破損・上限到達では停止し、ownerによるretirementは別の明示操作とします。

rollback時はconsumerとworkerを停止・無効化してからcode/settingsを戻します。旧公開epochや
credentialを復元せず、別途承認されたowner操作なしにindexを削除しません。local helper・domain・
ASGI・実HTTPを検証しますが、全Linux filesystem、実proxy構成、特権host分離、disk/D-stateの
cancelを保証するものではありません。merge前には最新headの独立した人間のsecurity/integration
reviewが必要です。

Audit保存先はサーバ利用者所有の0700ディレクトリに0600で事前作成し、source・登録resource・
設定・index・sidecarと共用しません。書込前にも再検証し、不正・未作成の保存先は拒否します。

各index transactionはDB内の更新番号とメモリ内の番号を照合し、commit時に進めます。
起動中に同じepochの古いDBへ戻しても検出でき、解除済み参照を復活させません。
