# ライフサイクル分析

`lifetxt timeline --summary --json --id ITEM` は、追加形式の
`lifecycle-analytics-v1` を返します。正規化された有効イベントを先に
絞り込んでから集計するため、`--limit` は表示件数だけを制限し、分析結果を
暗黙に変えません。不完全な履歴や利用できない証拠は `limitations` と
`complete` に記録されます。

利用できる分析は、所要時間、状態滞在時間、スケジュール変更、関係の変化、
完了・再オープンサイクル、状態遷移、イベント間隔、頻度、状態振動、証跡、
進捗速度、工数、スケジュールから完了までの時間、due差分です。2つの明示的な
期間は `--compare-window START..END --to-window START..END` で比較できます。

`lifecycle-stats --json` は同じreaderでworkspace全体を集計し、期間を指定すれば
所要時間分布も返します。`thread` の各分析と MCP の
`get_lifecycle_analytics` は読み取り専用で、同じ制限情報とprovenanceを保持します。

既存の `temporal-timeline-v1` のフィールドは変更しない追加互換です。分析はGitを
読み取らず、`life.txt`を変更せず、履歴にないdue日を現在の項目から推測しません。
