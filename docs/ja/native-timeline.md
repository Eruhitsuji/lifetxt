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

## Semantic as-of reconstruction

`--as-of TIMESTAMP` は、offset 付き RFC3339 timestamp における各 field の
known/partial/unavailable state を再構築し、bounded event list に加えて
（置き換えではなく）表示します。

```bash
lifetxt timeline task-1 life.txt --as-of 2026-09-10T11:00:00Z
lifetxt timeline task-1 life.txt --as-of 2026-09-10T11:00:00Z --json
```

`--as-of` は `show --as-of`/`query --as-of` と同じ offset 付き RFC3339
cutoff parser を使い、naive または malformed な timestamp を同じ message で
拒否します。`--summary`、analysis flag、`--compare-window`/`--to-window`
とは併用できません。

各 field は次の3状態のいずれかを報告します。

- `known` -- creation から欠落のない item-event chain から再構築できた。
- `partial` -- 適用可能な event から再構築できたが、item の event chain が
  creation から完全であると検証されていないため、未知の gap が答えを
  変える可能性がある。
- `unavailable` -- cutoff 以前に適用可能な event が存在しない、または
  この field には今日時点で atomic capture route がない。**現在の item
  state へのフォールバックは一切行いません。**

対象 field は `status`（lifecycle status）、`due`（`due:` schedule field、
今日 atomic capture route を持つ唯一の schedule field）、
`follows`/`realizes`/`replaced_by`（`relation_added`/`relation_removed`
event から再現する lifecycle relation）、および `on`/`from`/`to`/`at`
（常に `unavailable` -- これらの schedule field はまだ capture route が
ありません）です。

これは既存の `native_timeline()`/`normalize_native_events()` reader と
`item_event_completeness()` をそのまま再利用しており、現在の life.txt
state へフォールバックせず、Git も合成しません。

JSON result の `semantic_as_of` field は
[`semantic-as-of-v1.schema.json`](../../dist/schemas/semantic-as-of-v1.schema.json)
に従います。これは `temporal-timeline-v1` の event list や、Git-backed の
`historical`/`as of` revision snapshot を返す `temporal-thread-v1` とは
別の bounded contract です。Git は一切読み込まず、cutoff 以前に capture
された `record:item_event` stream が実際に裏付ける以上の field state は
主張しません。

## ワークスペース Life Timeline

`lifetxt timeline --workspace-timeline [path ...]` は、上記の bounded な
per-item Native Timeline を、選択したワークスペース内の全アイテムに対する
1つの決定的な read-only 時系列ストリームへ合成します。
[workspace-life-timeline.md](workspace-life-timeline.md) を参照してください。
