# v1.0.5

v1.0.5 は N=0 の通常版（1.0.5.0 と同一のリリース識別子）です。v1.0.4.3 からの主な変更をまとめます。

## 主な変更

- **Web UI:** 初心者向けの作成導線、タイトル優先のフォーム、用途別 More、ヘルプの基本操作ガイドと表示設定、Items の用語・操作案内、キーボードとモバイル操作を改善しました。([#1551](https://github.com/Eruhitsuji/lifetxt/pull/1551), [#1587](https://github.com/Eruhitsuji/lifetxt/pull/1587), [#1591](https://github.com/Eruhitsuji/lifetxt/pull/1591), [#1655](https://github.com/Eruhitsuji/lifetxt/pull/1655), [#1667](https://github.com/Eruhitsuji/lifetxt/pull/1667))
- **タスクボード:** Items の状態別ボードからカード移動・編集・追加ができます。既存のリビジョン付き更新を使用し、競合や結果不明時に自動再送しません。URL からの復帰、モバイルの列移動、ドラッグ中の案内、カレンダー直接操作も改善しました。列内の手動順序や任意のカスタム列は対象外です。([#1613](https://github.com/Eruhitsuji/lifetxt/pull/1613), [#1615](https://github.com/Eruhitsuji/lifetxt/pull/1615), [#1629](https://github.com/Eruhitsuji/lifetxt/pull/1629), [#1651](https://github.com/Eruhitsuji/lifetxt/pull/1651))
- **日々の計画と振り返り:** Agenda/Calendar の連続操作、月送り、再取得、Stats の内訳・期間表示、Graph の関係一覧、詳細 Drawer、一括完了日時と Undo を改善しました。習慣のきっかけ・最小版・休みの記録にも対応します。([#1481](https://github.com/Eruhitsuji/lifetxt/pull/1481), [#1483](https://github.com/Eruhitsuji/lifetxt/pull/1483), [#1557](https://github.com/Eruhitsuji/lifetxt/pull/1557), [#1559](https://github.com/Eruhitsuji/lifetxt/pull/1559), [#1570](https://github.com/Eruhitsuji/lifetxt/pull/1570), [#1576](https://github.com/Eruhitsuji/lifetxt/pull/1576), [#1579](https://github.com/Eruhitsuji/lifetxt/pull/1579), [#1585](https://github.com/Eruhitsuji/lifetxt/pull/1585))
- **入力とデータ表現:** CLI/Web/TUI の明示的な todo.txt 入力とプレビュー、型付き JSON detail と状態に基づく requires に対応します。JSON の最上位配列は各キーの値リストとなり、配列そのものを一値にするには入れ子にします。従来の depends_on/blocks と json:true リテラルは維持します。([#1445](https://github.com/Eruhitsuji/lifetxt/pull/1445), [#1446](https://github.com/Eruhitsuji/lifetxt/pull/1446), [#1447](https://github.com/Eruhitsuji/lifetxt/pull/1447), [#1595](https://github.com/Eruhitsuji/lifetxt/pull/1595), [#1597](https://github.com/Eruhitsuji/lifetxt/pull/1597), [#1599](https://github.com/Eruhitsuji/lifetxt/pull/1599))
- **Desktop と通知:** ネイティブ通知を強化し、`lifetxt_desktop --server-url https://example.com/` で既存サーバの Web UI を開けます。リモートウィンドウはローカル runtime を起動せず、ローカル通知用 IPC を付与しません。([#1593](https://github.com/Eruhitsuji/lifetxt/pull/1593), [#1653](https://github.com/Eruhitsuji/lifetxt/pull/1653))
- **複数人運用:** 通常 Web UI の workspace role に応じた起動・セッション・書込制御と、リビジョン競合の統合テストを追加しました。実 VPN・ブラウザ環境での受入は別途必要であり、任意の公開ネットワークでの運用を保証しません。([#1640](https://github.com/Eruhitsuji/lifetxt/pull/1640), [#1644](https://github.com/Eruhitsuji/lifetxt/pull/1644), [#1647](https://github.com/Eruhitsuji/lifetxt/pull/1647))
- **公式サイト:** 日英の JavaScript 書式チェッカー、サンプル・初心者向け練習の導線を追加しました。ブラウザだけで試せる候補であり、Core の全検証と同一ではありません。別の Pages 公開手順を使用します。([#1535](https://github.com/Eruhitsuji/lifetxt/pull/1535), [#1538](https://github.com/Eruhitsuji/lifetxt/pull/1538), [#1601](https://github.com/Eruhitsuji/lifetxt/pull/1601), [#1603](https://github.com/Eruhitsuji/lifetxt/pull/1603))

## 更新と互換性

Core と Mini の版数は 1.0.5、Desktop は既存の packaging 手順で同期します。Editor の独立版数は変更しません。Mini は引き続き厳密な機能部分集合です。今回の版数更新自体は既存 life.txt の移行を要求しません。型付き JSON・requires など新機能に依存するデータは旧版での処理を前提にしないでください。

更新前にデータと設定をバックアップし、[配布ガイド](distribution.md) に従って利用中のチャネルを更新してください。サーバ運用ではまず検証環境で書込、認証、バックアップと復元を確認してください。

## 残課題・検証境界

- Web UI の継続改善と実環境受入は [#1386](https://github.com/Eruhitsuji/lifetxt/issues/1386)、ブラウザ試験は [#318](https://github.com/Eruhitsuji/lifetxt/issues/318) で追跡します。
- workspace/VPN・Desktop の全 OS GUI、Remote attachment および revision 運用の未解決受入を完了済みとは扱いません。
- 全14ターゲットの preflight、承認、配布物の検証は [#1668](https://github.com/Eruhitsuji/lifetxt/issues/1668) に記録します。外部 winget/Scoop/conda 登録と生成を区別します。

[全変更（v1.0.4.3...v1.0.5）](https://github.com/Eruhitsuji/lifetxt/compare/v1.0.4.3...v1.0.5)
