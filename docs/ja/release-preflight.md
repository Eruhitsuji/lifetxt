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
