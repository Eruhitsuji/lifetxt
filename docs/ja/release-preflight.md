# リリースpreflight証跡の共通契約

#1309で承認された設計に基づく、#1310配下の#1315のoffline基盤です。
本helperはbuild・公開・GitHub承認確認を実行せず、公開権限も付与しません。
既存の公開workflowは変更していません。配布物別buildと統合workflowは
#1316〜#1321、公開canonical checksumは#1305が担当します。

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
