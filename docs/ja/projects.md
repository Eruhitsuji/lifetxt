# プロジェクトとポートフォリオ

プロジェクトは `project:` 詳細に使われる値です。lifetxt は同じプロジェクトを共有する
アイテムを集約し、設定レジストリの静的メタデータを任意で統合して、進捗・健全性・
負荷・マイルストーン・リスク・意思決定・会議を報告します。新しいアイテム型は導入
しません。

## レコード

`record:` を付けた通常のアイテムでプロジェクトと成果物を記述します。

| レコード           | 型   | 主なキー                                       |
| ------------------ | ---- | ---------------------------------------------- |
| `record:project`   | N    | `project:`・`owner:`・`area:`・`state:`・`due:`・`do:`（開始）・`visibility:` |
| `record:milestone` | D    | `project:`・`due:`・`owner:`                    |
| `record:risk`      | N    | `project:`・`severity:`・`state:`・`owner:`     |
| `record:issue`     | N    | `project:`・`severity:`・`state:`               |
| `record:decision`  | N/J  | `project:`・`on:`（決定日）                     |
| `record:meeting`   | E    | `project:`・`on:`・`at:`                        |

`project:` を持つ通常のタスク・締切はプロジェクト作業として数えます。タスクは
`depends_on:` の対象が未完了なら**ブロック中**、`due:` が今日より前なら**期限超過**
です。

## レジストリ

変化の少ない静的メタデータは設定の `projects` に置きます。

```json
{
  "projects": {
    "web": {
      "display_name": "Website Revamp",
      "aliases": ["website"],
      "default_assignee": "alice",
      "default_area": "work",
      "visibility": "shared"
    }
  }
}
```

エイリアスは全コマンドで正式名に解決されます。進捗・リスク・意思決定などの変化する
データは設定ではなく life.txt レコードに残します。

## コマンド

```console
$ lifetxt project list                 # プロジェクトごとの進捗と健全性
$ lifetxt project show web             # 1プロジェクトの集約ハブ
$ lifetxt project health --all         # 健全性ラベルと算出式
$ lifetxt project timeline web         # 日付順のアイテム
$ lifetxt project workload web         # 担当者ごとの open/done/overdue
$ lifetxt project risks web            # 重大度順のリスク
$ lifetxt portfolio                    # 全プロジェクトの比較
```

レコードの作成（ワークスペースの書き込み先へ追記）:

```console
$ lifetxt project new payments --owner carol --area finance --due 2026-12-01
$ lifetxt project add milestone web "Launch MVP" --due 2026-08-15
$ lifetxt project add risk web "Latency spike" --severity high --owner bob
$ lifetxt project add decision web "Use Postgres" --on 2026-06-20
$ lifetxt project add meeting web "Kickoff" --on 2026-06-01
```

`--dry-run` で書き込まずに行内容だけを表示します。

## アーカイブ

`lifetxt project archive NAME` は、1つのプロジェクトのdone/canceledレコード（および
`parent:`でdoneなticketに紐づく`record:ticket_event`/`record:time_entry`の履歴）を、
ワークスペースの設定済み`role: archive`ソースへ、genericな`archive`と同じ
atomicなmulti-fileトランザクションエンジンで移動します。

```console
$ lifetxt project archive web --dry-run   # プレビューのみ、変更なし
$ lifetxt project archive web             # スキャンした各sourceとarchive先の
                                           # revisionが必要（下記参照）
```

live実行のproject archiveはauthoritative fileへ書き込むため、スキャンした
各sourceとarchive先について厳密な`--revision PATH=SHA256`が必要です。
`--dry-run`はコピーして使える正確なrevision setを表示します。この事前条件と、
同一invocation内でのzero-byte拒否・parse error拒否は、本番incident（#183）—
live archive実行後にその安全性を確認できなかった事例—を受けて追加されました。

### レビュー可能なarchive plan（`--emit-plan` / `--apply-plan`）

「何がarchiveされるか」と「実際にarchiveする」の間にレビュー工程を挟むため、
`--dry-run --emit-plan PATH`はテキスト出力の代わりに`archive-plan-v1`形式の
JSONドキュメントを書き出します。解決済みのworkspace/config identity、
sourceとdestinationの厳密なrevision、選択済みitem IDの固定リスト、
archive対象への外部参照、writer/processのprovenanceを含みます。
`--emit-plan`自体はlife.txtに何も書き込みません。

`selected_item_ids`は明示的な`id:`（または設定済みの`id_key`）を持つitemのみを
列挙します。IDを持たないitemも正しくarchiveされますが、このfieldには反映されません。
自動ID割り当てを有効にしていないworkspaceでは、`selected_item_ids`だけでなく
dry-runのテキスト出力もあわせてレビューしてください。これは`--apply-plan`の
安全性を弱めるものではありません──安全性の根拠はsource/destinationのrevision
チェック（同一バイト列の入力は決定的に同じ選択を再現する）にあり、
`selected_item_ids`自体には依存していません。

```console
$ lifetxt project archive web --dry-run --emit-plan plan.json
Archive plan written to plan.json.
$ cat plan.json   # 適用前にレビューできる
$ lifetxt project archive web --apply-plan plan.json
Archive plan verified against current state (reserved_transaction_id=...).
No changes made.
Re-run the same command with --yes to apply it.
$ lifetxt project archive web --apply-plan plan.json --yes
Applying archive plan (reserved_transaction_id=...).
Archived 3 item(s) to ...
```

`--apply-plan`は書き込みを行う前に、planが記録した内容をすべて現在の状態と
再照合し、以下の場合はファイルを一切変更せずに拒否します:

| 拒否理由 | 意味 | 推奨される対応 |
| --- | --- | --- |
| 未対応の`plan_version` | このlifetxtが理解できないversionでplanが作成されている | 対応するversionでplanを再emitする |
| consistency check失敗（`plan_hash`不一致） | planファイルが自身の記録済みhashと一致しない──`--emit-plan`が書き出した後に手編集または破損した | planを再emitしてレビューし直す。planファイルを手編集しない |
| sourceまたはdestinationのrevisionが古い | emit後にスキャン対象sourceまたはarchive先が変更された | `--dry-run --emit-plan`を再実行して最新のplanを作成する |
| workspace/configのdrift | emit後にactive workspaceの設定が変更された | `--dry-run --emit-plan`を再実行する |
| selectionのdrift | 現在の状態から再導出した候補集合が、planで固定されたitem IDリストと一致しない | `--dry-run --emit-plan`を再実行し、選択が変化した原因（status変更、someday tag追加など）を確認する |
| recovery evidenceに到達不能 | transaction journal/backupディレクトリが存在しないか書き込み不可 | 適用前にstorageへのアクセスを修正する |

**`plan_hash`は自己一貫性のためのchecksumであり、署名ではありません。**
planファイル自身から計算されファイル内に保存されるため、意図しない手編集や
破損は検知できますが、planの出自を認証したり、意図的にファイルを編集する者
（変更後に一致するhashを再計算できる）を防ぐものではありません。
`plan.json`は他のこのコマンドへのlocal入力と同様に信頼してください──
信頼できない仲介者を経由させてconsistency checkが改ざんを検知することを
期待するのではなく、`--emit-plan`から`--apply-plan`までの間、未署名の
設定ファイルと同じように自分の管理下に置いてください。

`--apply-plan`は`--revision`・明示的なsource path・`--dest`と併用できません
（planがこれら3つをすべて固定しているため）。`--yes`なしで適用すると検証と
reserved transaction IDの報告のみを行い、何も書き込みません。

`--revision`を使う経路と同様、拒否時はすべてのsource/destinationファイルが
バイト単位で不変のまま保たれ、backup世代も消費しません。archive完了後の
recoveryは、他のmulti-file書き込みと同じbackup/journalの契約を使います
（[Safe Writes, Attachments, and Work Sessions](safe-writes-attachments-and-work-sessions.md)参照）。
`--emit-plan`/`--apply-plan`を信頼できない、または手編集された可能性のある
planパスの周りでscriptingする場合、`set -o noclobber`のようなshell側の
追加防御も妥当な選択です。

## 算出の透明性

導出値はすべて算出方法を明示します。

- **進捗** = `done_tasks / non_cancelled_tasks * 100`。非キャンセル作業が無い場合は
  理由付きで `null`。
- **健全性** = 未対応の critical/high リスク、または進捗50%未満での期限超過があれば
  `red`、期限超過・ブロック・未対応の medium/low リスクがあれば `yellow`、それ以外は
  `green`。各レポートは理由と、データ不足による限界（例:「基準日が無いため期限超過は
  未評価」）を列挙します。
