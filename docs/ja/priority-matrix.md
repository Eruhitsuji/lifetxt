# 重要度と優先順位マトリクス

タスクには任意で `importance:high`、`importance:normal`、`importance:low` を指定できます。これは利用者の判断として `life.txt` に保存されます。既存の `priority:` は別の項目で、重要度としては扱いません。

```text
[ ] T "Submit report" importance:high due:2026-09-27
```

`lifetxt list --matrix life.txt`（または `python -m lifetxt list --matrix life.txt`）で表示します。`--quadrant Q1` で絞り込み、`--json` で構造化された結果を取得できます。対象は未完了 `[ ]` と進行中 `[/]` のタスク `T` のみです。完了、キャンセル、延期、保留、タスク以外は表示しません。

緊急度は実行するたびに、設定されたワークスペースのタイムゾーンで `due:` から算出します。期限超過は critical、24時間以内は high、7日以内は normal、それ以降または期限なしは low です。日付のみの期限はその日の終わりまで有効です。ちょうど24時間・7日の境界は近い側に含めます。明示された時差は尊重します。critical、high、normal を「緊急」、`importance:high` だけを「重要」とし、両方なら Q1、重要のみなら Q2、緊急のみなら Q3、どちらでもなければ Q4 に分類します。重要度の欠落・不正・重複、期限の不正は `unclassified` に表示します。不正・重複した重要度には `check` が警告します。各グループ内は元の順序を維持します。算出結果はファイルに保存しません。
