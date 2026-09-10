# Native Temporal Timeline

`lifetxt timeline ID [PATH ...]` は、現在の life.txt input に保存された bounded
semantic history を表示します。共有 adapter を通じて `record:item_event`、
`record:progress_event`、`record:ticket_event`、`record:time_entry` を読みます。
Git history は読み込まず、自動で混在させません。

```bash
lifetxt timeline task-1 life.txt
lifetxt timeline task-1 life.txt --limit 25
lifetxt timeline task-1 life.txt --since 2026-09-01T00:00:00Z --until 2026-09-30T23:59:59Z
lifetxt timeline task-1 life.txt --event relation_added --limit 10
lifetxt timeline task-1 life.txt --json
```

既定 limit は有効な event 100件、許容範囲は0～500です。event は正規化時刻、
record-kind rank、親内 sequence、安定 record ID の順で決定的に並びます。
元の record kind、record ID、意味、時刻、sequence、transaction、revision
provenance、payload、validity を保持します。

`--since` と `--until` は UTC offset を含む ISO 8601 timestamp を受け取り、境界を
含みます。`--event` は normalized native event type を1つ受け取ります。複数指定時は
AND条件です。filter は有効 event を並べた後、`--limit` より先に適用されるため、
`bounds.total_valid_events` は filter に一致した件数です。invalid evidence、diagnostic、
limitation、domain別 completeness はinput history全体を表します。offsetのないtimestamp、
未知のevent type、`--since` が `--until` より後の場合は決定的に拒否します。filterを
省略した場合の結果は従来どおりです。

malformed record は主 `events` から除外し、diagnostic とともに
`invalid_events` へ分離します。gap、identity 重複、時刻逆行、不連続、現在
state との不一致、truncation がある場合は complete と表示しません。
creation evidence がなくても有効な partial Timeline として読めますが、履歴を
推測しません。completeness は item、progress、ticket、time-entry domain ごとに
表示します。

JSON result は
[`temporal-timeline-v1.schema.json`](../../dist/schemas/temporal-timeline-v1.schema.json)
に従います。MCP client はread-onlyの`get_native_timeline` toolを使い、同じ`id`、
`limit`、`since`、`until`、`event` contractで取得できます。resultは共有Timeline document
に標準のsource-set `revision`を加えたもので、fileを書き換えずGitも要求しません。
Git の exact revision には引き続き `thread --revision`、
`thread --as-of`、`thread --diff` を使用でき、これらの意味は変更しません。
