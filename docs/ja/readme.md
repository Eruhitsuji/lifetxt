# lifetxt ドキュメント

[English](../en/readme.md) · [文書全体の入口](../README.md) · [公式サイト](https://eruhitsuji.github.io/lifetxt/ja/)

`life.txt` はタスク、予定、メモ、日記などをプレーンテキストで記録する形式です。
最初のファイルは [入門ガイド](getting-started.md) を見ながら作成できます。
実際の記述例は [examples/](../../examples/) にあります。

## はじめる

- [5分で基本の書き方を学ぶ](getting-started.md)
- [CLI・デスクトップアプリ・コンテナを導入する](distribution.md)
- [lifetxt-mini を導入する](lifetxt-mini-distribution.md)
- [テキストエディターを設定する](editor.md)
- [テキストエディターだけで週次運用する](text-editor-only-workflow.md)
- [用途に合う構成を選ぶ](use-cases.md)
- [設計思想を読む](philosophy.md)

## 日常の操作

- [CLI コマンドリファレンス](cli.md)
- [Web UI・REST API](web.md)
- [クイック入力・todo.txt 入力](quick-capture.md)
- [CLI の操作例](new-cli-workflows.md)
- [今日の一覧・領域・被リンク](life-hub.md)
- [クエリ・保存済みビュー](query.md)
- [検索・あいまい検索](search.md)
- [重要度・優先度マトリクス](priority-matrix.md)
- [通常のメモ](ordinary-notes.md)
- [レコード間のリンク](item-links.md)
- [受信箱・提案](inbox.md)
- [プロジェクト・ポートフォリオ](projects.md)
- [開発チケット](tickets.md)
- [チケット・プロジェクトの集計](ticket-projects.md)
- [人物・グループ](people.md)
- [メッセージ・配信状態](messaging.md)
- [定期 Markdown レポート](reports.md)
- [手順ガイド](procedure-guidance.md)
- [ワークスペースのライフタイムライン](workspace-life-timeline.md)
- [ネイティブ時系列タイムライン](native-timeline.md)
- [時間軸を使った振り返り](temporal-review-reads.md)
- [レコードのライフサイクル分析](lifecycle-analytics.md)
- [将来の予定・意図のスナップショット](future-intent-snapshot.md)

## AI・パーソナルコンテキスト

- [AI で下書き・手動共有・MCP 接続](ai-integration.md)
- [AI 向けのレコード記述例](ai-patterns.md)
- [パーソナルコンテキストを作る・使う](personal-context.md)
- [パーソナルコンテキストのツール群](personal-context-toolkit.md)

## 形式・動作の仕様

- [Format 1.0 仕様](life_txt_format_spec.md)
- [往復変換・複数行本文](roundtrip-and-body.md)
- [タイムゾーン付き日時](timezone-aware-datetimes.md)
- [レコードの変更イベント](item-events.md)
- [ネイティブ意味履歴](native-semantic-history.md)
- [指定時点の履歴の意味](historical-as-of-semantics.md)
- [ネイティブ履歴と Git 履歴の整合性](native-git-history-consistency.md)
- [Git 履歴の証跡仕様](git-historical-evidence-contract.md)
- [MCP からの指定時点参照](mcp-semantic-as-of.md)
- [公開インターフェースのリビジョン仕様](public-surface-revisions.md)
- [共通の書き込み経路](shared-mutation-routing.md)
- [リソース参照の抽出・表示](resource-reference-projection.md)
- [制限付きリソース参照解決のスキーマ](resource-reference-resolution.md)
- [TUI の Unicode 表示幅](tui-unicode-width.md)
- [明示的に有効化する仮想マシン](vm.md)

## 設定・運用

- [設定・ワークスペース](config.md)
- [リモートセーフモード](remote.md)
- [リモート CLI・TUI からの書き込み](remote-client-writes.md)
- [リモートのチケット更新](remote-ticket-writes.md)
- [リモート接続の互換性](remote-compatibility.md)
- [Web 通信のセキュリティ](web-transport-security.md)
- [安全な書き込み・添付・作業セッション](safe-writes-attachments-and-work-sessions.md)
- [委任書き込み・リモート添付の復旧](delegated-remote-attachments-and-recovery.md)
- [添付の範囲を制限した読み取り](attachment-snapshot-helper.md)
- [プロセス境界・トランザクション管理](process-boundaries-attachments-and-transaction-admin.md)
- [トランザクション復旧・厳格タイマー](transaction-recovery-and-strict-timers.md)
- [ワークスペースの安全性・リビジョン・タイムゾーン](timezone-revision-workspace-safety.md)
- [ストレージ検査・保守](storage-health.md)
- [添付・復旧データの保存時の機密性](at-rest-confidentiality.md)
- [外部リソース取得の方針](external-resource-fetch-policy.md)
- [制限付きリソースの検索・ダウンロード](resource-reference-runtime.md)
- [オプション依存関係の互換性](optional-dependency-compatibility.md)
- [Ubuntu Server 本番環境の導入手順（英語）](../deployment/ubuntu-server.md)

## 開発・リリース

- [CI の役割](ci-responsibilities.md)
- [外部環境での検証](external-environment-verification.md)
- [確認済みのリリース基準](release-baselines.md)
- [リリース互換性の方針](release-compatibility-policy.md)
- [リリース前の判定基準](release-policy-gates.md)
- [リリースの安全性・Format 1.0](release-safety-foundations.md)
- [リリース事前検証の証跡](release-preflight.md)
- [承認済みリリースの公開](release-publication.md)
- [リリース成果物の証跡](release-artifact-evidence.md)
- [技術仕様・検証記録の索引（英語）](../development/README.md)

## リリースノート・設計案・調査

- [v1.0.5 リリースノート](release-notes-v1.0.5.md)
- [v1.0.4.3 リリースノート](release-notes-v1.0.4.3.md)
- [v1.0.4.2 リリースノート](release-notes-v1.0.4.2.md)
- [v1.0.4.1 リリースノート](release-notes-v1.0.4.1.md)
- [v1.0.2 リリースノート](release-notes-v1.0.2.md)
- [v1.0.0 リリースノート草案](stable-release-notes-draft.md)
- [Daily Flow Lite の設計案](daily-flow-lite-contract.md)
- [手順ガイドの設計案](procedure-guidance-design.md)
- [Git 履歴の開示に関する調査](git-historical-disclosure-policy.md)
- [ロードマップと過去のスナップショット（英語）](../roadmap/README.md)
