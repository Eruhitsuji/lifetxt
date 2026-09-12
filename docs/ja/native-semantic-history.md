# Native Semantic History

Status: Investigation #712で承認された設計を段階的に実装済みです。Native historyは
意図的にpartialであり、document済みのmutation経路だけがeventを記録します。既存fileや
手動編集したfileへのbackfillは行いません。

## 決定

人間にとって意味のある履歴をlifetxtのcore conceptとします。semantic operationが
起きたことのprimary evidenceは、人間可読なappend-only recordとして`life.txt`
内に置くべきです。Gitはexact tracked bytes、revision audit、recoveryの独立した
evidenceとして維持し、どちらか一方で他方を置き換えません。

history recordはvalid fileの必須条件ではなく、任意のevidenceです。既存file、
直接のtext edit、current stateだけを持つfileは引き続きvalidです。lifetxtが
captureしていない変更のeventを推測またはbackfillしません。

## Contractの選択

3つの表現を比較しました。

| model | 長所 | 問題 | 決定 |
| --- | --- | --- | --- |
| operationごとのrecord kind | payloadが明示的 | fieldごとにrecord kindとreaderが増殖する | 通常itemのlifecycle eventには拡張しない |
| generic key/value change record | 初期実装が小さい | 意味が曖昧でcustom field無制限のraw diffになる | 不採用 |
| common envelope + typed payload | 共通のordering/provenanceと明示的なdomain意味を両立できる | event registryとdiscriminated validationの維持が必要 | 採用 |

新しいnon-ticket lifecycle historyには`record:item_event`を使用します。共通
envelopeは`id`、`parent`、`event`、`at`、`sequence`、`transaction`、
`source_revision`です。`event`はclosedかつversionedなpayload shapeを選択し、
任意の`field`/`before`/`after`記録を許可しません。任意の`actor`とboundedな
`source`はeventの意味を変えずにprovenanceを追加できます。

概念例（contract実装Issueが完了するまでは専用validatorの受理対象ではありません）:

```txt
[N] N Task_TASK-1_status_changed record:item_event id:IE-TASK-1-000002 parent:TASK-1 event:status_changed at:2026-09-10T00:00:00Z sequence:2 transaction:ITX-TASK-1-000002 source_revision:<sha256> before_status:todo after_status:doing

[N] N Task_TASK-1_relation_added record:item_event id:IE-TASK-1-000003 parent:TASK-1 event:relation_added at:2026-09-10T00:10:00Z sequence:3 transaction:ITX-TASK-1-000003 source_revision:<sha256> relation:follows target:TASK-0

[N] N Task_TASK-1_schedule_changed record:item_event id:IE-TASK-1-000004 parent:TASK-1 event:schedule_changed at:2026-09-10T00:20:00Z sequence:4 transaction:ITX-TASK-1-000004 source_revision:<sha256> field:due before:2026-09-15 after:2026-09-20
```

generic parserではなくtyped payload registryがfieldを制限します。

| event | 必須semantic payload |
| --- | --- |
| `created` | item kind、title、初期lifecycle status |
| `status_changed` | `before_status`、`after_status` |
| `completed`、`reopened`、`canceled` | 変更前後のlifecycle status。operationが書く場合はcompletion time |
| `relation_added`、`relation_removed` | `follows`、`realizes`、`replaced_by`のいずれかの`relation`と1つの`target` |
| `schedule_changed` | `on`、`due`、`from`、`to`、`at`のいずれかの`field`と、両側それぞれの明示的なmissing markerまたはvalue |

`completed`、`reopened`、`canceled` operationは、それぞれ固有のeventをemitし、同じstatus
transitionに対する2件目の`status_changed` eventはemitしません。
`schedule_changed`では、`before`または`before_missing:true`のちょうど一方と、
`after`または`after_missing:true`のちょうど一方が必要です。allowlist済みの`field`が、
このgenericなvalue slotにboundedな意味を与えます。

titleとitem typeの変更も意味のある変更ですが、first capture sliceからは延期します。
安全に表現するにはrename/identityとtype conversionのruleが先に必要です。任意の
custom detail、formatting、ordering、comment、whitespace、raw line changeは
semantic eventではありません。

## 既存historyとの互換性

`record:progress_event`はfield-specificなpublic contractのまま維持します。rawな
percentage/fraction value、`set`/`delta` operation、continuity rule、
authoritative-chain behaviorは変更しません。migrationやduplicate writeではなく、
normalization adapterを通して将来のtimelineに表示します。

`record:ticket_event`と`record:time_entry`もticket domainのaudit/activity contract
として維持します。それぞれのevent vocabulary、author、revision field、validation、
privacy inheritanceを保持したままtimeline entryへnormalizeできます。

eventのstable identityは`(record kind, id)`です。共通の`transaction`は1つのmutation
で作られたrecordを関連付けますが、duplicateにはしません。Git evidenceとnative
eventを暗黙にdeduplicateしません。Gitはrevision stateを、native recordはsemantic
operationを示し、証明対象が異なるためです。

## Authorityと不一致

| 問い | primary evidence | 境界 |
| --- | --- | --- |
| 現在何が真か | current `life.txt` | historyはcurrent stateを上書きしない |
| どのsemantic operationがcaptureされたか | validなnative event | typed operationとpayloadだけを証明する |
| capture済みhistoryが完全か | validated native chainとcoverage result | completenessはitem/domainごとであり、暗黙にglobalとはしない |
| revision時点のtracked file内容 | exact Git tree/blob | domain changeの理由は証明しない |
| raw textやformattingの変更 | Git diff | semantic event sourceではない |
| 何が計画されているか | currentのfuture-facing fieldとlifecycle relation | current planは過去にも存在した証拠ではない |

current state、native event、Git evidenceが一致しない場合、readerは各sourceと
limitationを保持します。hidden winnerを選ばず、自動修復もしません。current
`life.txt`は現在についてauthoritative、valid native recordはoperationが記録された
evidence、Gitはexact tracked bytesのevidenceのままです。

## Ordering、append-only、completeness

- event timeはoffset-aware instantをUTCへnormalizeします。parentごとの正の
  `sequence`がrecord-kind stream内のsemantic orderであり、timestampは同一でもよい
  一方、逆行できません。
- IDはrecord kind内でstableかつuniqueです。sequenceはrecord-kind streamごとに
  1から連続します。transaction IDは、1つのcurrent-state mutationとatomicに書かれた
  recordを関連付けます。
- supported writerはvalidated、exact-revision、atomicな1つのmutation pathでcurrent
  stateを更新し必要eventをappendします。過去eventのupdate/deleteは行いません。
- sequence 1の`created` eventがgeneric item-event streamのfrom-creation coverageを
  確立します。既存itemの途中から始まるstreamもvalidですが、明示的にpartialです。
- completenessはsemantic domainごとに評価します。valid structure、before/after
  projectionのcontinuity、contiguous ordering、最後のcapture値とcurrent stateの一致が
  必要です。全byteや全custom detailの変更をcaptureしたという意味にはしません。
- malformed、duplicate、gap、discontinuous、backwards eventはplain textとして残り
  読めますが、authoritative projectionから除外し、対象streamをincompleteにします。
  timelineはdiagnostic付きで別表示できますが、semantic as-of reconstructionには
  使用できません。
- direct text editingはfirst-classのままです。uncaptured editにより対象domainがpartial
  またはinconsistentになり得ますが、file自体をinvalidにせず、推測eventへ変換しません。

specialized streamをまたぐnormalized timelineは、UTC event time、公開された固定の
record-kind rank、stream sequence、stable IDの順にsortします。このtie-breakは
deterministicな表示順であり、causalityを推測しません。first sliceでstream間の関連を
主張するのは共通transactionだけです。

## Read modelとCLIの方針

最初のnative read modelはboundedな**Temporal Timeline**です。

```text
record:item_event -----+
record:progress_event -+--> normalized native timeline
record:ticket_event ---+       + provenance, validation, completeness
record:time_entry -----+
```

予定commandは`lifetxt timeline ID [--json]`です。native semantic eventを読み、
deterministicに並べ、record kindとstable IDを保持し、source/domainごとのcompletenessを
報告します。`history`ではなく`timeline`を選ぶのは、exact revision logを想起させず、
semanticな時系列viewであることを明示するためです。

`lifetxt thread ID --revision/--as-of`はGit-backed exact-state reconstructionのまま
維持します。native eventによるsemantic as-of reconstruction、
`--source native|git|all`、native/Gitの自動compositionは、timeline contractに実際の
completeness/provenance evidenceが揃うまで延期します。first timelineは完全な過去item
stateを復元できると主張してはいけません。

Gitなしでは、current stateとnative eventを直接読め、native timelineを利用できます。
exact historical revisionとGit diffは利用できません。Gitありでも同じnative behaviorを
historical thread/diff commandと並行して利用します。repositoryの有無によってcommandが
暗黙にsourceを変えることはありません。

既存CLIの`ticket link` / `ticket unlink`経路は、lifecycle fieldの`follows`、
`realizes`、`replaced_by`について`relation_added` / `relation_removed` item eventを
記録します。relation state変更とevent追記は1回のexact-revision mutationで行われます。
重複addはno-op、失敗またはstale writeではorphan eventを残さず、他のrelation fieldは
従来の動作を維持します。他のmutation surfaceはcoverage gapのままで、migrationや
backfillは行いません。

## 実装への影響

follow-up implementationには次を含めます。

- shared envelope、typed registry、validator、normalization adapter、parent access-policy
  inheritance
- 選択したCLI/TUI/Web/API/MCP mutation pathでのexact-revision compound write。
  unsupportedなgeneric/manual mutation pathはcoverage limitationとして開示
- public JSON outputより先に`item-event-v1`と`temporal-timeline-v1` JSON Schema、
  schema compatibility test
- 英語・日本語のformat、CLI、関係surface documentation
- capability/traceability更新とHigh-assuranceのdata-integrity、compatibility、privacy、
  atomicity evidence

migration/backfillは不要です。将来writerをrollbackする場合は、既存recordを削除せず新規
event emissionを停止します。旧parserはpermissive custom-key parsingによりNoteを
引き続き受理します。

## Follow-up Issues

1. [#713](https://github.com/Eruhitsuji/lifetxt/issues/713): shared item-event
   contract、validator、schema、adapterを定義します。
2. [#714](https://github.com/Eruhitsuji/lifetxt/issues/714): #713の後、選択した
   lifecycle mutationをatomicにcaptureします。
3. [#715](https://github.com/Eruhitsuji/lifetxt/issues/715): #713の後、boundedな
   native Temporal Timelineを追加します。#714とは独立して進行できます。

## Surface横断の capture parity（#767）

自動 Native History capture は現在 CLI 限定です。`lifetxt done`、`complete`、
`reopen`、`due` はそれぞれ `native_history_mutation.
commit_item_mutation_with_event`/`augment_item_mutation_with_event` を直接
呼び出すため、対応する CLI mutation は必ず state 変更と同じ atomic write の
中で対応する typed `record:item_event` を生成します。

Web UI/API（`PUT /api/items/id/{id}` -- Remote TUI もこれを authoritative な
write route として使用）、local TUI の row edit
（`lifetxt.tui_backend.LocalTuiBackend.apply_semantic_changes`）、および
Remote TUI 自身の edit は、今日時点でどの Native History producer も呼び出し
ません。これらの surface から status/due/relation を変更しても
`record:item_event` は一切生成されません -- これは設計上の選択ではなく、
#767 の investigation が見つけた実際の gap です。

この gap を安全に閉じられるようにするため、
`lifetxt.native_history_mutation.infer_item_event_specs(before, after)` を
新しく追加しました。これは `augment_item_mutation_with_event` がすでに
発行しているのと全く同じ event vocabulary と field scope（status family、
`due:` schedule field、`follows`/`realizes`/`replaced_by` relation）を、
before/after の `Item` pair から純粋に file I/O なしで分類する pure
classifier です。event 形状のロジックは一切重複させておらず、完全に
unit test されています
（`tests/test_native_history_mutation.py::InferItemEventSpecsTests`）が、
まだどの live write path にも組み込まれていません。

これを安全に組み込むには、Web UI/API の `update_item_in_file`、
（CLI の generic path と local TUI がすでに共有している）
`lifetxt.write_operations.mutate_items`/`mutate_item_files`、Remote TUI の
edit route のそれぞれが、置換 text を組み立て、推論された event を
#714 が CLI の専用コマンドですでに確立した「1回の write」保証と同じ形で
一緒に commit する必要があります。これはこのプロジェクトの共有された、
広く使われている mutation の primitive 自体への変更であり、局所的な修正
ではないため、このプロジェクト自身の
[Task Decomposition Standard](../../.ai/managed/core/TASK_DECOMPOSITION.md)
が示す「独立した write path を安全にまとめてレビューできない場合は task を
分割する」という指針に従い、意図的にこの回では実施していません。これは
黙って落とした requirement ではなく、記録された明示的な follow-up です。

その follow-up が着地するまで、Web UI・local TUI・Remote TUI から item を
編集することは従来どおり有効な workflow です -- ただ、その変更についての
Native History evidence はまだ（今のところ）生成されません。これは
直接の手動 text edit がすでに持っている、推測しない partial-completeness
の挙動と同じです。
