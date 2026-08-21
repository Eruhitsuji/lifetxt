# lifetxt 1.0.0 リリースノート

[#454](https://github.com/Eruhitsuji/lifetxt/issues/454)のrelease-candidate-
and-promotion手順に基づき、repository ownerが初回Stable releaseの
バージョンとして**`1.0.0`**を選定しました。release candidate tagは
`v1.0.0rc1`、最終tagは`v1.0.0`です。この文書はそのリリースのrelease notes
内容であり、RCがbounded checkを完了しcandidateがpromoteされた時点で
確定します（下記「Release status」を参照）。

[#454](https://github.com/Eruhitsuji/lifetxt/issues/454)は、残りのStable 1.0
gateを最小限まで縮小します: Format 1.0のcompatibility baseline、core
parse/read/write/canonicalizationの回帰保護、既知のrelease-blockingな
data-loss defectがないこと、clean-artifactのinstall/smokeが動作すること、
そして既知の制限を(網羅的な事前検証ではなく)文書化することです。#454は、
この文書が以前release前提として記述していた網羅的な実機検証の前提を
supersedeします。#283および#339のもとで既に記録済みの実環境証跡を撤回・
無効化するものではなく、それらは引き続き有効な過去のstabilization証跡
として残り、Stable 1.0後のquality workとして再開できます。

## Highlights

`1.0.0`はlifetxt初回のstable releaseです。以下を提供します:

- `life.txt`のplain-text record（tasks、events、habits、status/presence、
  messages、notes、journal entries）をparse・validate・filter・convert・
  atomicにmutateする、依存関係のないCLI
- 明示的でversion管理されたcompatibility contractとしてのFormat 1.0
  （詳細は下記「Stable境界」を参照）
- 同じrecord群の上に構築されたticket・project・portfolio management
  （workflow history、time tracking、dependencies、custom fields）
- read accessとrevision-checkされた範囲でのwriteのための、optional Web
  UI/API（`web` extra）、TUI（`tui` extra）、MCP server、Remote Safe Mode
- durableなmulti-file writeのためのtransaction・backup・recovery tooling
- git clone installに向けたCLI self-update（`lifetxt update`）と
  guardedなproduction deployment tooling
  （`lifetxt server-init`/`server-update`）

これらの各領域には個別のdocumentation（[readme.md](../../readme.md)から
リンク）があり、本セクションはその要約であって代替ではありません。どの
surfaceがstable compatibility promiseに含まれ、どれがexperimentalまたは
deferredかは、下記「既知の制限」、[compatibility policy](release-compatibility-policy.md)、
`.ai/project/STABLE_RELEASE.yml`のsupport matrixで定義されます。

## Stable境界

stable coreは、依存関係の少ないCLIとローカルのlife.txtワークフローです。
stableな書き込み移行は、無版入力からFormat 1.0への移行だけです。既存の
Format 1.0はno-opです。legacy、unknown、future、downgradeの変換は
inspection-onlyまたはwrite前拒否です。詳細は
[Format migration](format-migration.md)、
[compatibility matrix](format-compatibility-matrix.md)、および
`docs/en/format-1.0-finalization-review.md`を参照してください。

## 検証状況

必須CIでは、対応Python範囲、release policy、clean wheel smoke、Windows/macOS
core CLI smokeを検証します。#454が定義する最小限のclean-artifact検証
(wheel/sdistのbuild、対応Python環境のfreshな環境へのinstall、両entry
pointの起動確認、代表的なcore smoke)は`docs/en/stable-release-artifact-verification.md`
に記録します。

対応するすべてのshell・terminal・browser・filesystem class・SMTP
provider・optional client・OS/Python組み合わせについての網羅的な実機検証は、
Stable 1.0の前提条件では**ありません**（#454より）。網羅的な証跡が
ないこと自体はrelease blockerではありません。代表的なcore workflowの確定的な失敗、
Format 1.0 compatibility違反、data-loss/corruption defect、
build/install/startパスの破損、またはcritical security vulnerabilityが
blockerです。

## 既知の制限

Stable 1.0 gateから#454により繰り延べられる項目(具体的なcritical/
data-loss defectが見つからない限りrelease blockerではない、Stable 1.0後の
follow-up work):

- Web revisionの実機deployment証跡(#288-#292)
- remote attachmentのfailure/restartの網羅的な証跡(#297-#299)
- cloud-sync/removable/network filesystemの検証(#304)
- 実機terminalとselectorのmatrix検証(#312-#314)
- 実SMTP providerの検証(#315-#316)
- 実browser-engineの検証(#317-#318)
- 網羅的なexternal-host検証とそれを支えるrelease-harnessの強化(例: #437/#453)
- 通常CIとminimal clean-install smokeを超える網羅的な実機OS/Python matrix証跡

以下の制限は、#454による再scopeとは独立に引き続き適用されます:

- Web writeはstrict revisionの実環境証跡とdeployment gateに従います。
  read-only Web schemaの対応は、対象routeに限定されます。
- MCP write、Remote write、SMTP deliveryは専用の証跡がない限りstable promiseではありません。
- TUI、browser-engine、fzf/peco、cloud-sync、removable、network filesystemは、release証跡に記録された環境に限定されます。
- diagnostic spanは対応issueで対象化されたparser familyのみ完全対応です。

## アップグレード

`1.0.0`はlifetxt初回のreleaseであり、アップグレード元となる過去の公開
releaseはありません。そのため以下のmigrationはこのrelease自体には適用
されませんが、将来のreleaseが使うことになる仕組みであること、また
`1.0.0`のinstallが`1.0.0`より前のdataを黙って変更してはならないことから
ここに記載します:

- **Format**: `#! format_version:`directiveのない既存のlife.txt fileは、
  無版入力として引き続き有効であり、`1.0.0`のinstallやrunによって変更
  されません。`format_version: 1`への唯一のサポートされた明示的な
  revision-checked migrationについては[Format migration](format-migration.md)
  を、inspection-onlyのまま残る範囲については
  [compatibility matrix](format-compatibility-matrix.md)を参照してください。
- **Configuration**: `.lifetxt.json` fileは`1.0.0`のinstallによる影響を
  受けません。将来のconfiguration schema変更に向けて`lifetxt config
  migrate`は引き続き利用可能です。[config.md](config.md)を参照してください。
- **Policy/journal（transactionとrecovery）**: 既存のtransaction journal
  とrecovery evidenceは、
  [Transaction recovery and strict timers](transaction-recovery-and-strict-timers.md)
  に記載されているのと同じversion-awareなinspection pathで読み込まれます。
  将来のreleaseが書き込むより新しいjournalは、`1.0.0`の下ではinspect/
  export-onlyのままであり、`1.0.0`が完全に理解できないjournalを
  mutateすることはありません。
- **Web revision**: Web UIのoptimistic-concurrencyなrevision contractは
  このreleaseによって変更されません。現在の保証については
  [Public surface revisions](public-surface-revisions.md)を参照してください。

将来のreleaseから`1.0.0`へのdowngrade pathは、このreleaseでは定義され
ていません。それが関連する状況になった際に適用される一般的な
deprecationとmigrationのlifecycleについては
[compatibility policy](release-compatibility-policy.md)を参照してください。

## Release status

以下は#454の縮小されたrelease-candidate手順に基づきます:

- **`v1.0.0rc1`**: 2026-08-22に、commit
  `ca1894b6f5571b3862138d84bfe9dc542ebc2551`（PR #467のmerge commit）で
  cutされ、buildしたwheel（`lifetxt-1.0.0rc1-py3-none-any.whl`、sha256
  `fba241ab14bea43eb74281ec106a76f7a9c89aab5318e5dc7f837e1955b12c88`）と
  sdist（`lifetxt-1.0.0rc1.tar.gz`、sha256
  `73ffca299840d4268578d782a3caa2dac416b8e9b115fe03901d694e6eba3cf0`）を
  添付した[GitHub prerelease](https://github.com/Eruhitsuji/lifetxt/releases/tag/v1.0.0rc1)
  として公開されました。`twine check`は両方ともpassし、target commitで
  必須CIがpassし、minimal installed-artifact smokeはfresh virtual
  environmentへinstallした実際のwheelに対して実行されました: parse/read
  （`check`）、create（`quick`）、mutate（`complete`）、serialize/write
  （`format canon`、`format migrate --write`、いずれもrevision-checkedな
  atomic-write contract経由）、re-read、recovery-safeな書き込みpath。
  完全な証跡記録は
  [Stable Release Artifact Verification](stable-release-artifact-verification.md)
  を参照してください。
- **`v1.0.0`**: repository ownerによりpromotionが承認されました。#463の
  open-issue reviewでRC期間中にrelease-blockingなdefectは見つからなかった
  ため、この変更は検証済みの`v1.0.0rc1`candidateのコードに対して
  release-metadata-onlyなversion bump（`1.0.0rc1` -> `1.0.0`）のみを適用し、
  他のproduct behaviorの変更はありません。tag・最終artifact・その証跡は
  この変更がmergeされtagがcutされた時点で記録されます。実際のcommit・
  artifact hash・release URLは、このセクション（またはその履歴）の
  後続の記録を参照してください。

## インストールsmoke

release検証ではeditable checkoutではなく、clean wheelまたはsdistをfresh
virtual environmentへインストールします。

```text
python -m lifetxt --help
lifetxt --help
python -m lifetxt check examples/minimal_life.txt
```

この smoke に対する release-critical な最小要件は、#454により
[Stable Release Artifact Verification](stable-release-artifact-verification.md)
に記録されたminimal clean-artifact検証です。より網羅的な外部環境検証手順は、
追加の（release blockerではない）実機証跡として引き続き利用できます。
