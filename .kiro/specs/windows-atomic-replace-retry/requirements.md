# Requirements Document

> **Authoritative copy lives in the change package, not here.**
>
> For non-trivial work, and for anything at High or Regulated assurance, this content is distilled
> into `.ai/project/changes/<change-id>/requirements.yml`, which is what reviewers and the other
> executors read. See `.ai/project/changes/README.md` for when a change package is required at
> all — below that threshold, the issue and pull request carry the reasoning and no package is
> needed.
>
> The formats differ on purpose: this file is Markdown for drafting, the change package is YAML
> for the standard's traceability records. Distilling is a manual step, so this file and the
> package can drift. The package wins.
>
> See #101 for the decision behind this.

## Project Description (Input)

Windows で `os.replace` が `WinError 5`（PermissionError）で一時的に失敗する問題。

- `lifetxt/atomic.py:73` の `os.replace(temp_path, path)` は無保護（リトライなし）。
  実際に #96 で `tests.test_mutation` 実行中に一度発生し、直後の単体再実行では成功した
  （一時的なハンドル競合と推定）。
- `lifetxt/config_writer.py:96` と `lifetxt/config_writer.py:125` の
  `os.replace(older, newer)`（バックアップ／rejected 候補のローテーション）も無保護。
- `lifetxt/transaction_journal.py:962` の `_replace_file()` のみ、Windows 限定の
  バウンデッドリトライ（初回試行 + 0.01/0.05/0.1/0.25 秒間隔で最大4回リトライ、
  予算枯渇時は `PermissionError` を再送出）で保護済み（#86 / #94、PR #94）。

決めるべきこと（本要件定義で確定）:
- どの書き込み経路を同種の保護対象にすべきか → **3経路すべて**（下記参照）。
- 保護方式は既存パターンを再利用するか → **`transaction_journal.py` の既存バウンデッド
  リトライを流用する**。
- リトライ予算が枯渇した場合の挙動 → **経路の性質ごとに異なる**（下記参照）。

## Introduction

本機能は、Windows 上でファイル置換（`os.replace`）が一時的なファイルハンドル競合により
`PermissionError`（`WinError 5`）で失敗する既知の事象に対して、`transaction_journal.py` の
`_replace_file()`（#86 / #94）で既に確立済みのバウンデッドリトライパターンを、現時点で無保護
な残り2モジュール・3呼び出し箇所に適用する。

対象となる書き込み経路は次の3つで、いずれも直接 `os.replace` を呼び出しているコード全体の
検索により確定している（`transaction_journal.py:962` を除く残り全て）。

1. **共有アトミック書き込みコミット原始関数**（`lifetxt/atomic.py:73`）— CLI・TUI・Web・MCP・
   タイマー・通知など、プロジェクト内のほぼ全ての永続化書き込みが最終的に経由する、単一の
   低レベル置換ステップ。
2. **設定バックアップローテーション**（`lifetxt/config_writer.py:96`）— `config set` /
   `config unset` / `config migrate` 実行時の `.bak` 世代ローテーション。既存実装は
   `except OSError: pass` により失敗を完全に黙って無視するベストエフォート処理。
3. **設定 rejected 候補ローテーション**（`lifetxt/config_writer.py:125`）— compare-and-set
   拒否時に呼び出し元の編集内容を回復可能に保持する `.rejectedN` 世代ローテーション。同じく
   `except OSError: pass` によるベストエフォート処理。

## Boundary Context (Optional)

- **In scope**:
  - 上記3箇所の `os.replace` 呼び出しに対する、Windows 限定のバウンデッドリトライの追加。
  - リトライ予算（試行回数・待機間隔）は `transaction_journal.py` の既存バウンデッドリトライ
    と同一の値を3箇所すべてで再利用し、経路間で一貫させる。
  - リトライ予算枯渇時の挙動は経路の性質ごとに次の通り分岐させる：
    - 経路1（共有コミット原始関数）: 現在と同じくアクセス拒否エラーを呼び出し元へそのまま
      伝播させる（fail loudly を維持）。
    - 経路2・3（設定ローテーション）: 現在と同じく完全にサイレントに継続する（新しいログ・
      警告・診断出力は追加しない）。
- **Out of scope**:
  - `transaction_journal.py:962` の既存保護そのものの変更（#86 / #94 で完了済み、対象外）。
  - リトライの試行回数・待機間隔の値そのものを変更・再設計すること（既存値をそのまま流用）。
  - 経路2・3のローテーション失敗を新たに可観測にすること（ログ出力、`lifetxt doctor` 診断、
    戻り値の変更、その他の新しい報告手段）。
  - `os.replace` を直接呼び出す、上記3箇所・既保護1箇所以外の経路の保護
    （コードベース全体を検索した結果、該当箇所は存在しないことを確認済み）。
  - Windows 以外のプラットフォームでの挙動変更（リトライは適用されず、現状のまま即座に失敗
    または即座に成功する）。
- **Adjacent expectations**:
  - 本機能は設定の compare-and-set（リビジョン照合）書き込み契約（`cap-config-safe-writes`）
    を変更しない。リビジョン不一致による書き込み拒否と、拒否された候補の保持・doctor での
    情報報告は、本機能と独立した既存の仕組みのまま維持される。
  - 本機能は `lifetxt/mutation.py` の共有ロック・競合検出・書き込み後検証の契約を変更しない。
    リトライは置換ステップの内部でのみ発生し、呼び出し元から見える契約は変わらない。

## Requirements

### Requirement 1: 共有アトミック書き込みコミット原始関数の一時的アクセス拒否に対するリトライ保護

**Objective:** As a Windows 上で lifetxt のいずれかの書き込み経路（CLI・TUI・Web・MCP・タイマー
等）を利用するユーザー, I want ファイル置換時の一時的なアクセス拒否エラーが自動的にリトライさ
れること, so that 短命なファイルハンドル競合だけを理由に通常の書き込みが失敗しない。

#### Acceptance Criteria

1. While the runtime platform is Windows, when the shared atomic write commit step encounters a
   temporary access-denied error while replacing the target file, the Atomic Write Module shall
   retry the replacement using the same bounded retry timing already used for durable transaction
   journal writes (an initial attempt plus up to four retries spaced at increasing short
   intervals, totaling no more than roughly half a second).
2. When a retried replacement succeeds within the retry budget, the Atomic Write Module shall
   complete the write with the same observable outcome as a write that succeeded on the first
   attempt.
3. If the retry budget is exhausted without a successful replacement, then the Atomic Write
   Module shall propagate the access-denied error to the caller, unchanged from current behavior.
4. Where the runtime platform is not Windows, the Atomic Write Module shall not apply retry to an
   access-denied error during replacement, matching current behavior.

### Requirement 2: 設定バックアップ／rejected 候補ローテーションの一時的アクセス拒否に対するリトライ保護

**Objective:** As an 設定ファイルのバックアップおよび拒否候補による復旧に依存する運用者,
I want ローテーションステップで一時的なアクセス拒否エラーが発生した場合にリトライされること,
so that 短命な Windows のファイルハンドル競合だけを理由に、復旧用コピーの作成が不必要にスキ
ップされない。

#### Acceptance Criteria

1. While the runtime platform is Windows, when the configuration backup rotation step encounters
   a temporary access-denied error while replacing a backup generation file, the Configuration
   Writer shall retry the replacement using the same bounded retry timing as Requirement 1.
2. While the runtime platform is Windows, when the configuration rejected-candidate rotation step
   encounters a temporary access-denied error while replacing a rejected-candidate generation
   file, the Configuration Writer shall retry the replacement using the same bounded retry timing
   as Requirement 1.
3. If the retry budget for either rotation step is exhausted without a successful replacement,
   then the Configuration Writer shall continue exactly as it does today: it shall not raise the
   error and shall not fail or block the configuration write operation that triggered the
   rotation.
4. The Configuration Writer shall not introduce any new user-visible message, log entry, or
   diagnostic report as a result of a rotation replacement failure, whether or not retries
   occurred, preserving current silent best-effort behavior.

### Requirement 3: 保護経路間で一貫したリトライポリシー

**Objective:** As a lifetxt のリライアビリティを保守する担当者, I want 新たに保護される全ての
経路が同一のリトライポリシーに従うこと, so that リトライ挙動の追加が経路ごとに異なる、予測しに
くい遅延や振る舞いを生まない。

#### Acceptance Criteria

1. The system shall apply an identical bounded retry policy (attempt count and delay intervals)
   to every replacement call site covered by Requirement 1 and Requirement 2.
2. The system shall bound the total additional wait time introduced by retry at any single
   covered call site to the same budget already used by the existing durable transaction journal
   retry (initial attempt plus four delays of 0.01, 0.05, 0.1, and 0.25 seconds, approximately
   0.41 seconds total).
3. Where a covered call site is not running on Windows, the system shall behave exactly as it
   does today, with no retry applied and no added delay.
