# 重要度と優先順位マトリクス

タスクには任意で `importance:high`、`importance:normal`、`importance:low` を指定できます。これは利用者の判断として `life.txt` に保存されます。既存の `priority:` は従来の契約に基づく、利用者が明示する実行順・並び順の希望です。マトリクスは `priority:` と `importance:` を相互変換せず、分類にも `priority:` を使いません。

```text
[ ] T "Submit report" importance:high due:2026-09-27
```

各項目は異なる情報を表します。

| 項目 | 意味 | 保存または算出 |
| --- | --- | --- |
| `priority:` | 利用者が明示する実行順・並び順の希望。`next` など、従来から優先度順を使う view が利用 | `life.txt` に保存 |
| `importance:` | タスクがどれほど重要かという利用者の判断 | `life.txt` に保存 |
| 緊急度 | `due:` と評価時刻から算出する時間的な切迫度 | 実行ごとに算出 |
| Q1–Q4 | importance と緊急度から導く注意分類 | 実行ごとに算出し、保存しない |

たとえば `priority:C importance:high` と `priority:A importance:low` はどちらも有効です。`priority:` だけを変更しても、緊急度や象限は変わりません。`importance:` が欠落または不正なら、`priority:A` があっても `unclassified` のままです。既存の view は従来どおり `priority:` を並び替えに使うことがありますが、マトリクス内の項目は元の順序を保ち、`priority:` 順には並べません。

`lifetxt list --matrix life.txt`（または `python -m lifetxt list --matrix life.txt`）で表示します。`--quadrant Q1` で絞り込み、`--json` で構造化された結果を取得できます。対象は未完了 `[ ]` と進行中 `[/]` のタスク `T` のみです。完了、キャンセル、延期、保留、タスク以外は表示しません。

緊急度は実行するたびに、設定されたワークスペースのタイムゾーンで `due:` から算出します。期限超過は critical、24時間以内は high、7日以内は normal、それ以降または期限なしは low です。日付のみの期限はその日の終わりまで有効です。ちょうど24時間・7日の境界は近い側に含めます。明示された時差は尊重します。critical、high、normal を「緊急」、`importance:high` だけを「重要」とし、両方なら Q1、重要のみなら Q2、緊急のみなら Q3、どちらでもなければ Q4 に分類します。重要度の欠落・不正・重複、期限の不正は `unclassified` に表示します。不正・重複した重要度には `check` が警告します。各グループ内は元の順序を維持します。算出結果はファイルに保存しません。

Q1–Q4 は既存の `priority:` 項目の置き換えではありません。マトリクスは総合スコアや推奨実行順を算出しません。
