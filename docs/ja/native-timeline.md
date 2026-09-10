# Native Temporal Timeline

`lifetxt timeline ID [PATH ...]` は、現在の life.txt input に保存された bounded
semantic history を表示します。共有 adapter を通じて `record:item_event`、
`record:progress_event`、`record:ticket_event`、`record:time_entry` を読みます。
Git history は読み込まず、自動で混在させません。

```bash
lifetxt timeline task-1 life.txt
lifetxt timeline task-1 life.txt --limit 25
lifetxt timeline task-1 life.txt --json
```

既定 limit は有効な event 100件、許容範囲は0～500です。event は正規化時刻、
record-kind rank、親内 sequence、安定 record ID の順で決定的に並びます。
元の record kind、record ID、意味、時刻、sequence、transaction、revision
provenance、payload、validity を保持します。

malformed record は主 `events` から除外し、diagnostic とともに
`invalid_events` へ分離します。gap、identity 重複、時刻逆行、不連続、現在
state との不一致、truncation がある場合は complete と表示しません。
creation evidence がなくても有効な partial Timeline として読めますが、履歴を
推測しません。completeness は item、progress、ticket、time-entry domain ごとに
表示します。

JSON result は
[`temporal-timeline-v1.schema.json`](../../dist/schemas/temporal-timeline-v1.schema.json)
に従います。Git の exact revision には引き続き `thread --revision`、
`thread --as-of`、`thread --diff` を使用でき、これらの意味は変更しません。
