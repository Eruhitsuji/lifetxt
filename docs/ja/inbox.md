# 統合インボックスと提案（Proposals）

クイックキャプチャや AI の提案は、life.txt に直接書き込まれません。まず操作用ストア
（`lifetxt/inbox.py`）にレビュー可能な**提案（proposal）**として staged されます。
人が1件ずつ確認し、承認・編集・却下・保留・一括適用します。承認された時だけ、
他のすべての権威的な変更と同じ検証付き・アトミックなライター
（`append_life_records`）を通じてワークスペースの書き込み先に追記されます。

ストアは操作用であり権威ではありません。保留中の意図を保持するだけで、life.txt の真実
は保持しません。承認こそが、意図がレコードになる唯一の地点です。

> **`lifetxt inbox` とは無関係です。** CLI には `project:`・`due:`・`assignee:`
> のいずれも持たない未完了タスクを一覧する、無関係な `lifetxt inbox` コマンドも
> あります（既に権威的なアイテムに対する GTD 式のトリアージで、対話式の
> `--process` プロンプトも選べます。`lifetxt inbox --help` 参照）。この機能とは
> 偶然「inbox」という名前が重複しているだけで、このページで説明する提案ストアとは
> 無関係です。project/due/assignee なしで承認された提案は、life.txt に反映された
> 時点で実際にそちらに現れます — この違いはまさにその挙動を再現して確認しました。

## 提案の作成（staging）

```console
$ lifetxt proposal add "Buy milk" --project home --due 2026-08-01
Staged proposal P-12471d4d

$ lifetxt proposal add "Call Bob" --assignee bob --source mcp
Staged proposal P-e123f000
```

生成される ID は `P-` に続く16進数8桁です（`new_proposal_id`、
`uuid4().hex[:8]`）— 連番ではないため、異なるセッションやマシンで生成された
提案 ID が衝突することはありません。`proposal add` は常に **create** 提案を
staged します（`--kind` の既定は `T`）。`--project`・`--due`・`--assignee`・
`--priority`・繰り返し可能な `--tag` はアイテムの詳細になり、`quick`/`assist`
が書き込むのと全く同じ詳細キーです。`--source` は自由記述のラベルです
（既定は `manual`）。固定リストに対する検証はありません。

AI クライアントは MCP の `stage_proposal` ツール（`lifetxt/mcp.py`）で提案を
staged します。書き込み先は提案ストアのみで、life.txt には書き込みません。
`source` の既定値は `manual` ではなく `mcp` です。どちらの経路も同じ
`stage_create` 関数を呼ぶため、AI クライアントが staged した提案と
`proposal add` で staged した提案は、いったん保存されると区別が付きません
— 同じ ID 方式、同じスキーマ、同じレビューフローです。

`create` は、現時点でどちらの経路も生成する唯一の提案 `operation` です。
保存されるスキーマの `operation` フィールドは自由記述の文字列です
（`inbox-proposal-v1` は `proposal-v1` から継承します）が、このコードベースで
`create` 以外の提案を staged したり承認したりする処理は現時点で存在しません
— `apply_proposal` は `"op": "create"` を持つ `changes` エントリを探し、
見つからなければ例外を送出します。

## レビュー

```console
$ lifetxt proposal list                 # 行プレビュー付きで一覧
P-12471d4d   [pending ] manual   [ ] T "Buy milk" project:home due:2026-08-01
P-e123f000   [pending ] mcp      [ ] T "Call Bob" assignee:bob
(2 total: pending=2)

$ lifetxt proposal list --status pending
$ lifetxt proposal show P-12471d4d
{
  "proposal_version": "1",
  "id": "P-12471d4d",
  "operation": "create",
  "source": "manual",
  "expected_revision": "",
  "changes": [
    {
      "op": "create",
      "kind": "T",
      "status": "[ ]",
      "title": "Buy milk",
      "details": { "project": ["home"], "due": ["2026-08-01"] }
    }
  ],
  "warnings": [],
  "status": "pending",
  "provenance": {},
  "created": "2026-08-10T10:30:19"
}
```

`proposal show` は常に完全な JSON レコードを表示します。プレーンテキスト形式は
ありません。`proposal list` の `--status` は `pending`・`accepted`・`rejected`・
`deferred` を受け付けます。末尾のサマリー行（`(N total: ...)`）は常にストア内の
全提案を反映し、その上のリストにかかる `--status` フィルタとは独立しています。
`proposal list --json` はサマリー行やプレビューテキストを含まない、生の提案配列を
返します。

提案は — どのステータスであっても — [search.md](search.md) のグローバル検索にも
現れ、レンダリング済みの行プレビューと `source` の両方に対してマッチします。

```console
$ lifetxt find "milk" --type proposal
1 match(es) for 'milk':
proposal (1):
  P-12471d4d           [accepted] [ ] T "Buy oat milk" project:home due:2026-08-01
```

## 承認前の編集

```console
$ lifetxt proposal edit P-12471d4d --title "Buy oat milk" --project home
Edited proposal P-12471d4d
```

編集できるのは pending の提案のみです — 既に承認・却下・保留済みの提案を編集
しようとすると明確に失敗します。

```console
$ lifetxt proposal edit P-12471d4d --title x
ERROR: Only pending proposals can be edited.
```

（終了コード1。提案は変更されません。）`edit` は `--project`/`--due`/
`--assignee`/`--priority` を既存の詳細に**マージ**します（詳細集合全体を
置き換えるわけではないため）、指定しなかったフラグは以前の値を保ちます。
`--title` と `--kind` は対応するフィールドをそのまま置き換えます。`edit` に
（`add` と異なり）`--tag` フラグはありません。

## 承認・却下・保留

```console
$ lifetxt proposal accept P-12471d4d              # 書き込み先へ追記
Accepted P-12471d4d -> life.txt
  [ ] T "Buy oat milk" project:home due:2026-08-01

$ lifetxt proposal accept P-1 P-2 P-3             # 一括適用
$ lifetxt proposal reject P-9
$ lifetxt proposal defer P-8
```

承認は提案のアイテムをワークスペースの書き込み先（または `--to`）へ追記し、
`accepted` にマークします。承認されたアイテムのタイトルは通常のアイテム
シリアライザーによって**引用符付き**（`"Buy oat milk"`）で書き込まれます。
`quick`/`assist`/`message send` がタイトルをアンダースコアで結合するのとは
異なりますが、どちらも有効な life.txt 構文であり `lifetxt check` はどちらの
形式も受理します。

既に承認済みの提案・未知の ID・承認後の編集/再承認は、すべて黙って無視される
のではなくエラーとして報告されます。

```console
$ lifetxt proposal accept P-12471d4d              # 既に承認済み
ERROR: P-12471d4d: Proposal 'P-12471d4d' is already accepted.
Applied 0/1.

$ lifetxt proposal reject P-nosuch
ERROR: Unknown proposal 'P-nosuch'.
```

一括適用は提案ごとの結果を報告し、個別の失敗があっても続行します — バッチ内の
1つの不正な ID が他の適用を止めることはありません。

```console
$ lifetxt proposal accept P-b627dcd8 P-nosuch
ERROR: P-nosuch: Unknown proposal 'P-nosuch'.
Accepted P-b627dcd8 -> life.txt
  [ ] T "Untyped item"
Applied 1/2.
```

（終了コードは、バッチ内の全 ID が適用された場合のみ0になります。ここでは
有効な ID が成功したにもかかわらず1です。）`batch_apply` はバッチ全体に対する
任意の `expected_revision` を受け付け、最初の成功した追記の後にそれをクリアします
（その時点でファイルのリビジョンは既に変わっているため）— ただし CLI の
`proposal accept` はそもそも `expected_revision` を渡さないため、CLI からの
承認は一括であろうとなかろうと常にリビジョンの前提条件なしで追記します。
それでも各承認は他のあらゆる場所で使われるのと同じ検証済み・アトミックな
ライターである `append_life_records` を通るため、対象ファイルへの外部からの
同時編集は書き込み自体で検知されます — ただしバッチ開始前に観測したリビジョンへ
固定しているわけではありません。

## 設定

```json
{ "inbox": { "proposals_file": ".cache/lifetxt/proposals.json" } }
```

`inbox.proposals_file` はこの機能の唯一の設定キーです。`~` 展開に対応し、初回
書き込み時に（親ディレクトリを含めて）作成されます。ストアが存在しない、または
読み取り不能/壊れている場合はエラーではなく空として扱われます（`load_proposals`
は `OSError`/`ValueError` を捕捉して `[]` を返します）。

## MCP

- `list_proposals`（読み取り専用）— staged 提案の確認。`status` で任意に絞り込み
  可能。`{"proposals": [...], "counts": {...}, "total": N}` を返します —
  `proposal list` の末尾サマリー行と同じステータス別カウントです。
- `stage_proposal` — レビュー用に create 提案を staged（提案ストアのみ。人が
  後で承認）。`title` は必須。`kind`（既定 `T`）・`details`（オブジェクト —
  `tag` のような繰り返し可能な詳細も JSON 配列で指定）・`source`（既定 `mcp`）
  を受け付けます。`title` が欠けている場合は `ValueError` を送出します。

`accept`/`reject`/`defer`/`edit` に対応する MCP ツールはありません — これらは
人間専用の操作のままで、現時点では CLI だけがこれらを実装しています
（`lifetxt/tui.py`/`lifetxt/tui_app.py` にも `lifetxt/webapp.py` にも、提案を
レビューする画面は現状ありません）。これは「承認こそが、意図がレコードになる
唯一の地点である」という設計意図に沿っており、提案を作る側と同じクラスの
クライアントが自動化すべきではないという考え方です。メッセージング機能まわりの
読み取り専用 MCP ツールについては、life.txt に直接書き込む代わりに「AI が提案し、
人が承認する」という同じ分離に従っている [messaging.md](messaging.md#mcp) を
参照してください。

提案は `inbox-proposal-v1.schema.json`（`proposal-v1` の拡張）に従います。
`status` の列挙値は `pending`/`accepted`/`rejected`/`deferred` です。
