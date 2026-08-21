# Stableリリースノート草案

この文書は初回stable release向けの草案です。リリースバージョンとtagは
release判断で決定するため、公開済みのリリース告知ではありません。

[#454](https://github.com/Eruhitsuji/lifetxt/issues/454)は、残りのStable 1.0
gateを最小限まで縮小します: Format 1.0のcompatibility baseline、core
parse/read/write/canonicalizationの回帰保護、既知のrelease-blockingな
data-loss defectがないこと、clean-artifactのinstall/smokeが動作すること、
そして既知の制限を(網羅的な事前検証ではなく)文書化することです。#454は、
この文書が以前release前提として記述していた網羅的な実機検証の前提を
supersedeします。#283および#339のもとで既に記録済みの実環境証跡を撤回・
無効化するものではなく、それらは引き続き有効な過去のstabilization証跡
として残り、Stable 1.0後のquality workとして再開できます。

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
#454によりStable 1.0の前提条件では**ありません**。網羅的な証跡がないこと
自体はrelease blockerではありません。代表的なcore workflowの確定的な失敗、
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
- この草案ではversion/tagを意図的に未設定のままにしています。Format 1.0
  baselineの確定とminimal clean-artifact検証の合格後に、release authorityが
  選定します。#454は候補/リリース識別子として`1.0.0rc1`と`1.0.0`を
  指定しています。

## インストールsmoke

release検証ではeditable checkoutではなく、clean wheelまたはsdistをfresh
virtual environmentへインストールします。

```text
python -m lifetxt --help
lifetxt --help
python -m lifetxt check examples/minimal_life.txt
```

stable tagのpromote前に、artifact hash、Python、OS、結果を外部環境検証手順へ記録します。
