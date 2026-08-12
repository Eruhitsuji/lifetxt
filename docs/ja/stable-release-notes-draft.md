# Stableリリースノート草案

この文書は初回stable release向けの草案です。リリースバージョンとtagは
release判断で決定するため、公開済みのリリース告知ではありません。

## Stable境界

stable coreは、依存関係の少ないCLIとローカルのlife.txtワークフローです。
stableな書き込み移行は、無版入力からFormat 1.0への移行だけです。既存の
Format 1.0はno-opです。legacy、unknown、future、downgradeの変換は
inspection-onlyまたはwrite前拒否です。

## 検証状況

CIでは、対応Python範囲、release policy、clean wheel smoke、Windows/macOS
core CLI smokeを検証します。外部環境のsupport判定には
`docs/en/external-environment-verification.md`の実機手順が必要です。
CI通過だけでは4環境の検証済みとはしません。

## 既知の制限

- Web writeはstrict revisionの実環境証跡とdeployment gateに従います。
- MCP write、Remote write、SMTP deliveryは専用の証跡がない限りstable promiseではありません。
- TUI、browser-engine、fzf/peco、cloud-sync、removable、network filesystemは、release証跡に記録された環境に限定されます。
- diagnostic spanは対応issueで対象化されたparser familyのみ完全対応です。

## インストールsmoke

release検証ではeditable checkoutではなく、clean wheelまたはsdistをfresh
virtual environmentへインストールします。

```text
python -m lifetxt --help
lifetxt --help
python -m lifetxt check examples/minimal_life.txt
```

stable tagのpromote前に、artifact hash、Python、OS、結果を外部環境検証手順へ記録します。
