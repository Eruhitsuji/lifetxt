# ワークスペース Life Timeline

`lifetxt timeline --workspace-timeline [path ...]` は、選択したワークスペース内の
全アイテムに記録された Native History を、上限付きの時系列ストリームとして
読み取ります。既存のアイテム単位 `temporal-timeline-v1` を合成するだけで、Gitを
参照したり、現在のフィールドから履歴を推測したりしません。

`--since`、`--until`、`--event`、`--project`、`--limit` で範囲を限定できます。
JSON は `workspace-life-timeline-v1` を返し、対象・source provenance、上限による
切り詰め、診断、制約、ワークスペース全体の完全性を含みます。部分的な履歴や手動
編集を含むsourceを、完全な履歴として表示することはありません。
