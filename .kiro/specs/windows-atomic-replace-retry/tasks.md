# Implementation Plan

> **This file is working material, not the task source of truth.**
>
> In this repository, actionable work lives in GitHub Issues.
> `.ai/managed/core/TASK_MANAGEMENT.md` makes Issues the source of truth, and
> `.ai/managed/core/INDEX.md` lists "no implementation without a reviewable task source"
> in the non-overridable baseline. A checklist here would compete with both.
>
> Use this breakdown to decide what the issues should be, then file them. Each must meet
> `.ai/managed/core/DEFINITION_OF_READY.md` before implementation starts, and an issue that is
> `status:inbox` or `status:blocked` may not be started. Writing this file does not open that gate.
>
> Recording the resulting issue numbers beside each task here is encouraged; inventing progress
> here without them is not.
>
> See #101 for the decision behind this.

## Tasks

- [x] 1. Foundation: 共有リプレイスリトライプリミティブ
- [x] 1.1 依存を持たない最下層モジュールに、Windows限定のバウンデッドリトライでファイル置換を
      行う共有ヘルパーとそのリトライポリシー（対象OS・試行回数・待機間隔）を追加する
  - 既存のトランザクションジャーナルのリトライ実装（#86 / #94）と完全に同一の値（Windows限
    定、初回+最大4回、待機間隔0.01/0.05/0.1/0.25秒）でポリシーを定義する
  - `PermissionError` 以外の例外はリトライせず即座に伝播させる
  - リトライ予算を使い切った場合、最後に発生した例外をそのまま再送出する（新しい例外でラップ
    しない）
  - 追加したヘルパーと定数がモジュール外からインポート可能になっている（インポートが成功す
    る）
  - _Requirements: 1.1, 1.2, 1.4, 3.1, 3.2, 3.3_
  - _Boundary: Replace Retry Primitive_

- [x] 1.2 共有リプレイスリトライプリミティブの単体テストを追加する
  - 失敗が発生しない場合は追加の待機なしで即座に成功することを検証する
  - Windows環境を模擬し、一時的な失敗が2回発生した後に成功するケースで、規定の待機間隔を挟ん
    で3回目に成功することを検証する
  - Windows環境を模擬し、失敗が継続するケースで、初回+4回の合計5回試行した後に同じ例外が再送
    出されることを検証する
  - 非Windows環境を模擬した場合、待機なしで即座に例外が伝播し、リトライが発生しないことを検証
    する
  - リトライ対象外の例外（`PermissionError` 以外の `OSError`）はWindows環境でも即座に伝播し、
    リトライされないことを検証する
  - `python -m unittest` を実行すると、上記5件の新規テストを含めてすべて成功する（既存テスト
    は非退行）
  - _Requirements: 1.1, 1.2, 1.4, 3.1, 3.2, 3.3_
  - _Boundary: Replace Retry Primitive_

- [x] 2. Core: 各書き込み経路をリトライプリミティブへ委譲
- [x] 2.1 (P) 共有アトミック書き込みコミット原始関数の置換ステップを、新しいリトライプリミティ
      ブに委譲する
  - 既存の一時ファイル作成・fsync・パーミッション引き継ぎ・クリーンアップの責務は変更しない
  - 一時的な失敗の後に置換が成功するケースで、最終的に新しい内容がファイルへ反映され、一時フ
    ァイルが残らないことを結合テストで検証する
  - リトライ予算を使い切った場合、既存通り例外が呼び出し元へ伝播し、元のファイル内容が変更さ
    れず、一時ファイルが後始末されることを結合テストで検証する
  - _Requirements: 1.1, 1.2, 1.3_
  - _Boundary: Atomic Write Commit Primitive_

- [x] 2.2 (P) 設定のバックアップ／rejected候補ローテーションの置換ステップを、新しいリトライプ
      リミティブに委譲する
  - 既存のベストエフォート例外処理（置換失敗を黙って継続する既存方針）は変更しない
  - 一時的な失敗の後に、バックアップ世代ローテーションとrejected候補ローテーションの両方が最
    終的に完了するケースを結合テストで検証する
  - リトライ予算を使い切った場合でも、例外が発生せず設定書き込み操作全体が正常に完了し、既存
    の世代数上限（バックアップ・rejected候補とも）が維持されることを結合テストで検証する
  - リトライ予算枯渇時に、新しいログ出力・診断・戻り値など、これまでになかった可観測な差異が
    一切追加されていないことをテストで確認する
  - _Requirements: 2.1, 2.2, 2.3, 2.4_
  - _Boundary: Configuration Backup and Rejected Rotation_

- [x] 3. Validation: 全体の回帰確認とリトライポリシーの一貫性検証
  - プロジェクトの単体テストスイート全体（既存 + 本機能で追加した新規テスト）を実行し、全件成
    功することを確認する
  - 変更した4ファイル（実装2・テスト2）に対してフォーマット・リントチェックを実行し、成功する
    ことを確認する
  - 共有コミット原始関数と設定ローテーションの両方が同一のリトライポリシー（試行回数・待機間
    隔・対象OS）を使用していることを、それぞれの結合テストの検証結果を突き合わせて確認する
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 2.1, 2.2, 2.3, 2.4, 3.1, 3.2, 3.3_
  - _Depends: 2.1, 2.2_
