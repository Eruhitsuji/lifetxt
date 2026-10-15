# リリースpreflight証跡の共通契約

#1309で承認された設計に基づく、#1310配下のoffline基盤（#1315）・配布物別producer
（#1316〜#1320）・read-only集約controller（#1321）の契約です。preflightは公開・
人間承認確認・CI署名検証・公開権限付与を行いません。既存の公開workflowは変更せず、
公開canonical checksumは#1305が担当します。

## 候補の固定

信頼済みcontrollerのcheckoutを使い、リポジトリrootで実行します。

```sh
python scripts/release_preflight_proof.py candidate \
  --repository Eruhitsuji/lifetxt --version 1.0.4.2 \
  --source-sha <40桁の小文字hex> --controller-sha <40桁の小文字hex> \
  --run-id <正整数> --run-attempt 1 --output candidate.json
```

source SHAは配布コード、controller SHAはレビュー済みworkflow・policyコードです。
この段階の確認は形式検査です。信頼済みSHAやCI合格を証明しません。
後続controllerはGitHub APIと実jobの信頼済みcontextからrepository・branch・
merge済みversion PR・CI結果・実checkout・人間承認を照合する必要があります。
入力reportだけでそれらを認定してはいけません。

既存の`lifetxt.versioning`を再利用し、`1.0.4`と`1.0.4.0`は同一候補に正規化します。
人間が明示した`1.0.4.2`は維持し、Cargo/Tauri内部表現だけ`1.0.4+2`とします。
番号指定は公開承認を意味せず、失敗時に自動採番もしません。

schema 1の対象はhelper内`TARGETS`の全13対象です。Core、Standalone5対象、
Desktop3対象、Mini2対象、OCI2対象を省略できません。各componentを候補digest・
source/controller SHA・run ID/attemptに束縛します。新attemptでbuildし直す場合は
全対象の新たな証跡が必要です。元の公開bytesを使う限定retryは後続controllerの役割です。

## 配布物別のreport

build workflowは**payload専用directoryだけ**をActions artifactへuploadします。
upload actionが返したartifact ID・name・archive SHA-256を取得した後、directoryの
外側にcomponent specを作ります。Coreのspec例は次のとおりです。

```json
{
  "target": "core-any",
  "artifact": {"id": 123, "name": "core-payload", "sha256": "<64桁の小文字hex>"},
  "observed_version": "1.0.4.2",
  "toolchain": {"python": "3.12.3", "build": "1.3.0", "runner": "ubuntu-24.04"},
  "checks": {"metadata": "passed", "clean-install": "passed", "cli": "passed"},
  "oci_digest": null,
  "files": [
    {"path": "lifetxt-1.0.4.2-py3-none-any.whl", "role": "wheel"},
    {"path": "lifetxt-1.0.4.2.tar.gz", "role": "sdist"},
    {"path": "sbom.cdx.json", "role": "sbom"},
    {"path": "provenance.json", "role": "provenance"}
  ]
}
```

```sh
python scripts/release_preflight_proof.py component \
  --candidate candidate.json --spec core-spec.json \
  --root payloads/core-any --output core-proof.json
```

全payload fileを列挙します。未記載file・空file・不正path・絶対path・親directory参照・
backslash・大文字小文字の衝突・symlinkを拒否します。pathは相対POSIX形式、各要素は
portable ASCIIです。CIは外部から同時変更されない専用directoryを使う必要があります。
helperは競合するfilesystem変更に対するsandboxではありません。roleは用途の宣言であり、
file名から実内容を推定せず、実binaryの意味検証も行いません。

| 配布物 | 必須role | 全てpassedが必要なcheck |
| --- | --- | --- |
| Core | wheel, sdist, sbom, provenance | metadata, clean-install, cli |
| Standalone | binary, checksum | version, check, init-doctor, unicode-path, timezone |
| Desktop | installer, bundled-core | version, bundle, bundled-core |
| Mini | binary, checksum, build-info, notes | version, native, static, conformance, cli |
| OCI | oci-layout | version, native, cli, web, non-root |

roleは原則一意で、Desktopの`installer`だけ複数形式を許容します。Desktopの
`bundled-core`は非公開証跡用payloadであり、公開Standalone assetを追加する意味では
ありません。作業directoryの偶発的なfileを丸ごとuploadしないよう意図して選別します。
OCIはlayout archiveと`sha256:<hex>`のimage/index digestを必須とします。後続OCI
producerがlayout実内容との照合・最終multiarch indexの生成を担当し、本helperは
OCI digestの形式のみを検査します。

check/toolchainはproducerの申告です。項目があるだけで実行済み・Actions由来・正しい
OCI digestとは認定できません。controllerがartifact参照をActions metadataと実際に
成功したproducer jobへ照合します。archive SHA-256と展開後fileごとのSHA-256は別です。
各componentのartifact IDは独立させます。component proofはpayload参照の取得後に別の
artifactとして保存し、自己参照を避けます。

## 集約と失敗

payloadを`payloads/<target>/`へ対象別にdownloadし、全対象をflat directoryへ
混在させないでください。

```sh
python scripts/release_preflight_proof.py aggregate \
  --candidate candidate.json --root payloads \
  --component core-proof.json --component <残り12件のproof.jsonを各々指定> \
  --output preflight-proof.json
```

全13対象を必須とし、各reportと実payloadを再hashします。対象/artifact IDの欠測・重複、
role不正、失敗/skip/欠測check、identity相違、bytes改変、未知field、JSON key重複を
拒否します。正常結果も`status: preflight_verified`、`publication_authorized: false`です。
公開承認receiptとして使えません。

candidate/component/bundleのdigestは、最上位の`digest`のみを除外したJSONのSHA-256です。
keyをsortし、compact UTF-8、末尾改行なし、非ASCIIをescapeしない形式です。内側のdigestは
保持します。これは内容の整合性であり、真正性の署名ではありません。

各CLIは新しい出力pathを要求し、拒否時は非zero終了します。controllerは終了codeを確認し、
失敗したattemptの古い出力を使ってはいけません。入力コードを信頼できるcheckoutから
実行し、公開権限を付けないでください。入力file・出力directoryは呼出側が管理します。
保存期限・信頼済み転送・承認・公開checksum確定・tag・registry・Latestは本helperの
対象外で、後続実装で必ず保証する事項です。

人間指定の補正版も通常PR/CI/preflight/承認を通します。未公開・tag未確定なら修正後の
SHAで同じ候補番号を再利用できます。tag確定後は番号をそのSHAへ予約します。部分公開は
同じsource/bytesのみretryでき、ソース不具合の修正は人間が新補正版番号を指定/承認します。
元artifact消失・bytes衝突では停止し、公開済みtagやbytesを差し替えません。

## Core producer（#1316）

`release-preflight-core.yml`はread-onlyの`workflow_call`専用producerです。
push/release/manual公開trigger・environment・公開tokenはなく、checkout認証情報も
保持しません。同じrepository/controller revisionの呼出元から、封印済み
`candidate_json`を渡します。ユーザー向けdispatch操作はまだなく、全体の接続は
#1321が担当します。

repository/run/attemptとcontroller checkoutを照合してから、検証済みsource SHAだけを
別directoryへcheckoutします。helperはtracked変更とソースの実versionを検査し、
build/smoke後にもsource/controller identityを再確認します。これらはlocal/runの
照合であり、信頼済みmain CI・version PR・人間承認のAPI照合は呼出元の責務です。

既存release-policy/safety release gateを実行し、`release_evidence.generate`で
wheel/sdistを一度生成します。両archiveのName/Version、SBOM、provenanceの
source/run/file hash、twineを検証します。さらに**wheelとsdistの両方**を個別の
新規venvへインストールし、ソース外の一時directoryからimport先がvenv内であること、
module/consoleのversion/help/最小exampleを実行検証します。smoke subprocessへ
PYTHONPATH/PYTHONHOMEを引き継ぎません。sdist installで生成するインストール用wheelを
公開payloadへ差し替えることもありません。通常のfull unittestは重複実行しません。
backend依存の取得にはpackage indexへの接続が必要な場合があります。

upload payloadはwheel/sdist/SBOM/provenanceの4roleです。既存builderの中間
SHA256SUMSはpayloadに入れず、#1305のcanonicalと競合させません。fileごとの
hashはbuild report/proof、gate/build診断はActions job logに記録します。
全検証の成功後のみreportを生成します。失敗時にlocal fileが残っても、そのjobは
uploadへ進まず成功componentも生成しません。

先に不変payloadをuploadし、返されたartifact-id/digestと
`core-payload-<run>-<attempt>`という名前を、再検証した同一bytesのreportへ束縛します。
`core-component.json`とcandidate/build reportは別artifact
`core-proof-<run>-<attempt>`へ保存します。reusable outputsはpayloadのID/name/digestと
component artifactのID/digestです。保持期間は30日を要求しますがrepositoryの制限に
従います。期限切れは停止条件であり、古い承認で再buildしてよいという意味ではありません。
公開Release/tag/registry/Latestは変更しません。Actions上の実転送と全13対象の
orchestrationは#1321で統合受入を行います。

local/offline検証では、標準のpip設定`PIP_FIND_LINKS`と`PIP_NO_INDEX`により、
事前取得したbuild依存wheelhouseを使えます。依存の取得経路だけを変更し、payload
bytesや新規venv・import先の検証は変えません。

## Standalone producer（#1317）

`release-preflight-standalone.yml`はWindows x86_64、Linux x86_64/arm64、
macOS arm64/x86_64の5対象を扱うread-onlyの`workflow_call`です。既存native
runner・PyInstaller specを維持し、旧公開workflowは変更しません。Coreと同じ
封印済み`candidate_json`を渡します。controller/source/run/versionの照合は
Core helperを再利用し、実OS・正規化host arch・64bit interpreterも照合して
cross-target buildを拒否します。

ソースのweb/tui extrasとPyInstallerをbuild環境へ入れ、ソース外でfrozen実行物
そのものを起動します。versionは候補と完全一致を要求します。check、init --yes、
doctor、workspace確認、空白・日本語を含むpath、Asia/Tokyoのcheck/today検証を
維持します。HOME/config/data/cacheはsmoke専用一時directoryとし、
PYTHONHOME/PYTHONPATHを除去します。build/smoke失敗時は成功reportやuploadへ
進みません。通常のfull unittestは重複実行しません。

payloadは既存のplatform別binary名とLF-onlyの.sha256だけです。封印reportに
source/controller/candidate/run/target・toolchain・成功check・両fileのhash/sizeを
記録します。payload upload後にも、厳密な2file inventory・checksum本文・
report/file digestの不変性を確認して共通schemaのcomponentを生成します。
binaryとchecksumを両方変更しても、smoke済みbytesとしては通りません。
component/checksumは公開承認でもcanonical SHA256SUMSの更新でもありません。

payload名は`<target>-payload-<run>-<attempt>`、別proof名は
`<target>-proof-<run>-<attempt>`です。proofはcandidate/build report/componentを
含み、componentがpayload archiveのID/name/digestを参照します。両方30日保持を
要求します。matrix outputの最後の1件を全5対象の一覧とみなしてはいけません。
そのため一覧outputは設けず、#1321が対象別proofを全件収集し、信頼済みAPI/run情報と
payload ID/digestを照合して欠測・重複を拒否します。download先も対象別namespaceを
維持してください。
Unixでdownloadしたbinaryを再検証するときは実行権限を復元してください。artifact転送で
file modeが正規化される場合があります。chmodはbytes/digestを変えず、再buildや
payloadの差替えではありません。

helperのbuild/component CLIはCore同様の引数に加え、
`--target standalone-linux-x86_64`等の対応対象を明示します。upload参照はcomponent
時だけ指定します。正確なコマンドはreusable workflowに記載し、単独の公開dispatchは
設けません。local Linuxの成功をWindows/macOS/ARMのnative検証済みとは扱わず、
それらとActions実転送は#1321の統合受入へ残します。

## Desktop producer（#1318）

`release-preflight-desktop.yml`はWindows x86_64・macOS arm64・Linux x86_64の
read-only `workflow_call`です。同じ封印済み`candidate_json`を渡します。
Coreのcontext/source照合とStandaloneのnative host/frozen smokeを再利用し、
公開event・environment・secretは持ちません。旧Desktop workflowとpackaging
scriptは変更しません。

stageコマンドは正確なsource SHAで新しいlocal shared Git checkoutを作り、その
生成用checkout内だけで既存runtime builderとversion setterを実行します。元の
source/controllerは前後でtracked cleanを確認します。bundled Coreそのものを
ソース外で起動してStandalone同等のsmokeを行い、既存の3/4要素version変換・
Appleの正確なrelease plist・resource mappingを検査します。生成用checkoutの
予期しないtracked編集（Cargo.lock変更を含む）や余分なruntime resourceは拒否します。
stage成功はCoreの準備完了であり、installer完成や公開承認ではありません。

bundleはstage identityとruntime hashを再照合してcargo tauri buildを実行し、
完了後にも再検証します。native Rust buildには30分のtimeoutを設けます。installerが
実際に生成され、非空・形式signature・元file名の一意性を満たすことを確認します。
全形式の深い構造検証やインストールを意味しません。Rust/tauri-cliのversionも記録します。
GUI install/upgrade/uninstall、全形式からの内包Core抽出は明示的にnot_verifiedとし、
後続の公開後検証でも実download物の確認が必要です。

公開installer名には空白が入り得るため、元の公開名は維持し、CI payload内だけ
installer-001.deb等の安全な別名を使います。封印bundle reportのinstallers配列に
path/public_name/formatの対応を保存します。別proof artifactにはcandidate・stage・
bundle report・共通componentを保存します。#1305/#1311/#1321は信頼済みActionsの
proof archive digestを照合し、対応表をcomponentのfile hashへ結び付けてから、
元public_nameで公開してください。aliasを公開名にしてはいけません。public_nameは
separator/control文字と重複を拒否しますが、local path連結やshellへの直接展開にも
使わないでください。

payload内のbundled-core（Windowsは.exe）は非公開証跡です。追加のRelease assetや
public canonical inventoryには入れません。公開Desktop assetはinstaller roleのみです。
これにより既存schemaと公開名を維持し、canonical checksum writerも増やしません。
payload upload後のcomponentでは対応表・形式signature・runtime/file hashの不変性を
再検証します。

artifact名は他producerと同じtarget別payload/proof形式、30日保持要求です。
呼出元はmatrix outputを一覧とみなさず3対象を全件収集します。正確な
stage→bundle→upload→componentコマンドはreusable workflowに記載しています。
Rust/WebKit/各OS runnerが必要な実installer buildとActions転送は、local Core準備の
成功とは区別して記録します。

## Mini producer（#1319）

`release-preflight-mini.yml`はLinux x86_64/AArch64 native runnerと既存musl
Rust target・Zig 0.13.0を使うread-only `workflow_call`です。同じ封印済み
candidate_jsonを渡し、Coreの実context/source照合・host照合・共通proofを再利用します。
旧Mini公開workflow/crate/version/conformance scriptは変更しません。

既存のCore/Cargo/lock/tag整合検査、cargo test --locked、選択musl targetへの
cargo zigbuild --locked --releaseを実行します。test/build出力先は新しい一時
directoryとし、古いtarget出力を候補の成果物と取り違えません。実binaryは対象archの
little-endian ELF64（x86_64=62、AArch64=183）を要求し、program-header境界・
load segment・PT_INTERP不在・DT_NEEDED/filter/auxiliary依存不在を検査します。
loader/外部依存を持たないstatic PIEのdynamic metadataは許容します。旧ldd文言への
依存をなくしますが、binary自体を安全なsandboxへ認定する検査ではありません。

実Miniのversion/help/check/today、既存binary-version検査とCore/Mini conformanceを
実行してからcheckをpassedとします。固定試験日とstrict-subsetのMini Runtime Profile
表示を維持します。conformance内のpython aliasは現在の対応interpreterと同一である
ことを確認し、失敗・skip・欠測を成功proofへ変換しません。

payload名は従来どおりlifetxt-mini-<tag>-linux-<arch>、.sha256、.build-info、
RELEASE-NOTES.mdです。checksum/notesはLFとし、build-infoはrustc -Vvを保存します。
reportにはCargo/cargo-zigbuild/Zig/Python・ELF証跡・各file hash/sizeも記録します。
notesは両archで同一bytesとしstrict-subset境界を残します。公開canonicalへの集約は
同名RELEASE-NOTES.mdを同hashの場合だけ1件へまとめ、異hashなら停止してください。
producer固有のcanonical SHA256SUMSは生成しません。

artifactは他producerと同じtarget/run/attempt別payload/proof・30日保持要求です。
upload後のcomponentでELF/arch・厳密inventory・checksum/notes・report hashを
再照合します。呼出元は両target proofを全件集め、信頼済みActions ID/digestを
検査します。matrix outputを一覧とみなしてはいけません。具体的なbuild→upload→
componentコマンドはworkflowに記載しています。Cargo/ZigがないlocalのELF/fixture
試験は、実Mini build・native AArch64・conformance・Actions転送の成功証拠では
ありません。公開有効化前に必要なそれらの統合証拠は#1321へ残します。

## OCI producer（非公開）

`release-preflight-oci.yml`は同じ信頼済み`candidate_json`をworkflow_callだけで
受け取り、Ubuntu amd64/arm64のnative runnerで実行します。contents:read、
credentialを残さないcheckoutを使用し、公開environmentやregistry loginはありません。
`release_preflight_oci.py build`でcontroller/source/run/version/hostを照合し、
既存DockerfileをBuildxで一度だけbuildします。version/revision labelを付け、
OCI形式・attestationなし（unknown-platformの追加manifestなし）でexportします。
保持した出力の同一性を保証する方式で、再現可能buildの認定ではありません。

payloadは元exporter bytesの`lifetxt-<tag>-linux-<arch>.oci.tar`1件
（role: oci-layout）です。index/config/layerの全graphを保持します。
`release_preflight_oci_layout.py`はtarの危険path/link/sparse/重複、外部descriptor、
size/hash不一致、余剰file、複数manifest、arch/version/revision/non-root設定不一致を
拒否します。extractallは使いません。schema/digest検査はsandboxや認証の代替ではありません。

Skopeoの`--preserve-digests`でlayoutからローカルcontainers-storageへだけ転送し、
失敗時に再buildや形式変換へ迂回しません。rootful Podmanのmanifest/config digestと
native platformを照合し、config ID固定・pull=neverで実version/help/check・uid=1000・
read-only Web healthを検証します。Web portはloopbackだけへbindし、CLI smokeの
networkは無効です。Web containerは後処理で削除します。registry transport/push・
QEMU・package公開は使いません。

reportの`oci.manifest_digest`が共通componentの`oci_digest`、
`oci.config_digest`が実行image ID、`oci.index_digest`が保持した単arch indexの
hashです。Actions archive SHA256とは別物です。Buildx/Docker/Skopeo/Podman/Python
versionとtar全体のhash/sizeも保存します。upload後のcomponentでtarを安全に再展開し、
graphとreport全体を照合してartifact参照を封印します。payload/proof名は
target/run/attempt別で30日保持を要求します。

呼出元は両component proofとActions参照を認証した後（#1321）、各archiveをfresh
directoryへ安全に展開し、`release_preflight_oci_layout.assemble(candidate,
{target: layout_path, ...}, out)`を呼びます。両targetを必須とし、graphを再検証、
元blobを変更せずコピーしてamd64→arm64順の決定的OCI indexを生成します。
戻り値は最終multiarch **index** digestです。そのindex bytesと全blobを保持し、
公開時は全digestを維持（Skopeo `--all --preserve-digests`）、remote index digestを
照合し、変換が必要なら停止してください。承認後の再build/index再生成や、単arch
manifest digestのmultiarch digestへの流用は禁止です。関数自体は公開権限を与えず、
最終証跡の結合は#1321、人間承認/公開転送は#1311です。canonical writerは追加しません。

local fixture試験はgraph/archive故障・smokeコマンド失敗・決定的組立を検証しますが、
実containerの成功証拠ではありません。localにDocker/Skopeo/Podmanがないため、
両arch native build・実storage転送・Actions転送は未実行として#1321に残します。

## 全target controllerと統合受入

`Release preflight (non-public)`（release-preflight.yml）は既存の公開workflowと別の
**main限定・手動専用**入口です。push/PR/tag/workflow_runでは起動しません。
今後のrelease.yml中央制御への接続/cutoverは#1311が所有し、ここでは実施しません。

このworkflowのmerge後、Actions → Release preflight (non-public) → Run workflowで
mainを選び、次を入力します。

| 入力 | 必須の意味 |
| --- | --- |
| source_sha | mainへmerge済みの固定40桁小文字hex commit SHA |
| version | そのsourceのpyproject.tomlと一致する明示X.Y.ZまたはX.Y.Z.N |
| main_ci_run_id | 同source SHAのCI push/main成功run（Main compatibility gate成功必須） |

source SHAとは別にcontroller workflow SHAを固定します。別repo/fork・main以外の
ref・別workflow/event・別source CI・main gate失敗/skippedを拒否します。
既存main gateにリンクし、互換性unit suite全体を重複実行しません。番号指定は公開承認
ではなく、bump/tag/version変更もありません。既公開versionを非公開検証に使っても、
そのversionの既存公開bytesは変更しません。

prepare→Core→Standalone→Desktopの順序とし、Mini/OCIはCore成功後に並列起動します。
全5familyとprepareの成功が必須です。collectは失敗後も動き部分成功を拒否しますが、
全成功時だけverified bundleをuploadします。producerはcontents:readのみ、
prepare/collectだけAPI参照用actions:readも付与します。設定済みGITHUB_TOKENをgh経由で
通常使用し、PAT・environment・secret継承・write権限・承認receipt・公開能力は追加しません。

matrix outputでなく全pageのActions APIを照合します。実controller run/attempt・
全5reusable workflow SHA・13targetの成功jobと必須build/component/upload stepを確認。
payload/proofは一意のtarget/run/attempt名・ID、同repo/run/controller SHA、producer
job時間内の作成、期限内、archive SHA256/sizeを必須とします。APIにartifact uploaderの
job IDはないため、信頼した固定workflowと一意job/name/時間窓を帰属境界とします。
独立した暗号学的attestationとみなしてはいけません。

ZIPをID指定downloadしhash/sizeを照合後、安全に展開します。現producerのflatでportableな
通常fileだけを許容し、traversal・alias・symlink・暗号化・空entry・CRC故障・展開size超過を
拒否します。各producerのoffline finish検証を再利用し、report/candidate/componentの
厳密inventoryとDesktop stage/公開名対応を照合します。collector上でbinaryは実行せず、
native実行は成功したproducerの責務です。信頼済みで同時改変されないrunner領域を前提とします。

全13componentを共通aggregatorへ通し、検証済み両OCI tarからblobを変えず最終indexを生成。
index digestと正確な全OCI bytes、aggregate digest、元payload/proof参照と有効期限、
main CI証跡、report全体のhash/sizeをpreflight-bundle.jsonへ結合します。自己hashは除外。
download/組立後にもActions/main CI状態を再取得し、attempt/job/metadata/期限が変わったら
成功bundleを出力せず停止します。

出力はpreflight-verified-<run_id>-<attempt>（30日保持要求）で、candidate.json、
components.json、proofs/<target>/*、ociのindex/layout/全blob、preflight-bundle.jsonです。
元13payloadは再複製せず、元artifactを参照します。後続利用前に最終artifact自体のID/
archive digestも認証してください。必要な元artifactが1件でも失効すれば公開再利用不可です。
publication_authorizedは常にfalseで、後続は古い成功JSONだけを信じず、実API最新状態と
人間承認を検証する必要があります。

新build attemptは「Re-run all jobs」を使います。失敗jobだけの再実行では新attemptの
candidateと全13target証跡が揃わず停止します。古い/部分成功artifactによる穴埋めは禁止。
既公開bytesのretryは別操作で、#1311が元の承認済みbytesだけを再利用します。

localの13target fixtureはAPI故障と実offline validatorの統合を検証しますが、実native/
GitHub転送の証拠ではありません。main手動runで全13targetのnative build/smoke、実upload/
download digest、集約成功と最終OCI index artifactを確認するまで#1321/#1310は開いたままです。
run URL/attempt/bundle artifact ID/digestを#1321に記録し、unit CIだけで統合成功を称したり
公開を有効化したりしないでください。

## native producer互換性とcontroller修正後の再試験

Miniのbuilder version証跡は`cargo-zigbuild --version`で取得します。
root CLIはこのflagを受理しますが、`cargo zigbuild --version`ではbuild subcommandへ
渡され、native smoke成功後でも拒否される場合があります。version取得失敗を成功扱いに
せず、toolchain証跡を省略して通すこともしません。

Tauriは生成checkoutのCargo.tomlを変更し、tauri-build文字列依存をversionと
features=[]を持つtableへ正規化することがあります。Desktopはimmutable source SHAの
git blobとTOML全体を比較し、tauri-buildの文字列/table・features未指定/空配列だけを
同値化して表現差を許可します。format/CRLFは意味比較に影響しません。
依存version・非空features・package metadata・その他の意味変更は拒否し、Cargo.lockや
他tracked fileの変更禁止も維持します。元source checkout/manifestは変更しません。
既存のversion/resource/plist/runtime/installer検証もそのまま適用します。

初回実統合run 38814960857ではCore・Standalone5・OCI2が成功しましたが、この2件の
互換性不具合（#1329）で停止しました。final verified bundleも公開物も生成されておらず、
この部分成功だけで全13targetの受入を満たしたとは扱いません。

controller/helper修正merge後は、**mainから新規の手動workflow run**を開始してください。
旧runのrerunは旧controller SHAを使うため修正検証になりません。元の固定source SHA・
version・成功main CI runを同じ非公開配布sourceとして使うことは可能ですが、新controller
SHAと新run/attemptを記録し、全targetを実行し直します。旧部分成功proofの流用・公開tagの
移動・同versionへの別bytes再公開は禁止です。全native成功と最終bundle/API/index証拠が
揃うまで#1321/#1310は開いたままにします。
