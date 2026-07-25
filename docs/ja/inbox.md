# 統合インボックスと提案（Proposals）

クイックキャプチャや AI の提案は、life.txt に直接書き込まれません。まず操作用ストアに
レビュー可能な**提案（proposal）**として staged されます。人が1件ずつ確認し、承認・
編集・却下・保留・一括適用します。承認された時だけ、他のすべての権威的な変更と同じ
検証付き・アトミックなライターを通じてワークスペースの書き込み先に追記されます。

ストアは操作用であり権威ではありません。保留中の意図を保持するだけで、life.txt の真実
は保持しません。承認こそが、意図がレコードになる唯一の地点です。

## 提案の作成（staging）

```console
$ lifetxt proposal add "Buy milk" --project home --due 2026-08-01
$ lifetxt proposal add "Call Bob" --assignee bob --source mcp
```

AI クライアントは MCP の `stage_proposal` ツールで提案を staged します。書き込み先は
提案ストアのみで、life.txt には書き込みません。

## レビュー

```console
$ lifetxt proposal list                 # 行プレビュー付きで一覧
$ lifetxt proposal list --status pending
$ lifetxt proposal show P-1a2b3c4d
```

## 承認前の編集

```console
$ lifetxt proposal edit P-1a2b3c4d --title "Buy oat milk" --project home
```

編集できるのは pending の提案のみです。

## 承認・却下・保留

```console
$ lifetxt proposal accept P-1a2b3c4d              # 書き込み先へ追記
$ lifetxt proposal accept P-1 P-2 P-3             # 一括適用
$ lifetxt proposal reject P-9
$ lifetxt proposal defer P-8
```

承認は提案のアイテムをワークスペースの書き込み先（または `--to`）へ追記し、`accepted`
にマークします。一括適用は提案ごとの結果を報告し、個別の失敗があっても続行します。

## 設定

```json
{ "inbox": { "proposals_file": ".cache/lifetxt/proposals.json" } }
```

## MCP

- `list_proposals`（読み取り専用）— staged 提案の確認
- `stage_proposal` — レビュー用に create 提案を staged（提案ストアのみ。人が後で承認）

提案は `inbox-proposal-v1.schema.json`（`proposal-v1` の拡張）に従います。
