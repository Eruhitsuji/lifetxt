# lifetxt v1.0.4.1 リリースノート

v1.0.4で失敗したPython/CoreとStandaloneの配布経路を修正する補正版です。
既存v1.0.4タグを移動せず、修正を含む新しいv1.0.4.1タグから配布します。
本ファイルは公開前のリリースノートです。公開済み状態は [#1298](https://github.com/Eruhitsuji/lifetxt/issues/1298) のチャネル別受入記録を参照してください。

## v1.0.4からの変更

- [#1301](https://github.com/Eruhitsuji/lifetxt/pull/1301): 新しいPythonプロセスでのスキーマ初期化順序を修正。release gateが完全なスキーマbundleを検証します。
- 同PR: PyInstallerに動的ロードのschema_extensions_v4〜v34を明示し、Standaloneの初回起動でのModuleNotFoundErrorを修正。
- [#1303](https://github.com/Eruhitsuji/lifetxt/pull/1303): 通常のvX.Y.Z表記を維持したまま、補正版vX.Y.Z.Nに対応。省略N=0として更新判定を数値比較します。
- Core/Mini CLIと公開タグは1.0.4.1。Cargo/Tauriの内部SemVerメタデータは1.0.4+1。内部の+1は更新比較に使いません。

## 互換性と制限

life.txt Format 1.0の文法変更・データ移行はありません。v1.0.4に含まれた変更はそのまま保持します。
MiniはPython不要のLinux用strict subsetです。同じバージョンでもPython Coreと機能同等ではありません。
Mini公式対象はLinux x86_64/AArch64。Windows/macOSではCore/Standalone/Desktopの各成果物を使用してください。
DesktopのOS標準メタデータだけではサブバージョン順序を保証しません。実インストール/上書き更新はチャネル別に検証します。
公開前の検証、タグ公開後の成果物到達性、未実施の実機検証を混同せず、#1298/#911に記録します。

## インストール・更新

公開後のPython版: `python -m pip install --upgrade lifetxt==1.0.4.1`。
確認: `lifetxt --version` が `lifetxt 1.0.4.1` を表示。
GitHub配布: [v1.0.4.1 Release](https://github.com/Eruhitsuji/lifetxt/releases/tag/v1.0.4.1) の用途・OS・archに合う成果物を取得し、同Releaseの最終SHA256SUMSで照合してください。
[配布とインストール](distribution.md) に各チャネルとMiniの制限・checksum検証を説明しています。
Homebrew/winget/Scoop/condaは別の後続処理・外部反映を伴うため、#1298の実際の反映状態を参照してください。
