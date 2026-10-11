# AI Reference Patterns — Composite / 複合例

Code blocks copy canonical fixtures. Both languages retain identical source input and code. Author-run Core checks are separate from meaning comparison; independent review takes place on the PR.

[Format 1.0](../life_txt_format_spec.md) / [Profile](../../../prompts/lifetxt-assistant.md) / [Fixture maintenance](../../../examples/ai-patterns/README.md)

<a id="pat-com-001"></a>

## PAT-COM-001 — Task+Deadline+Reminder

**Input (original language retained):** ユーザー指定ID writeで10月14日に報告書を書き、20日17時締切(deadline)。20日9時に思い出す(reminder)。年2030。

**Context:** Fictional example. Fixed baseline: 2030-10-11T12:00:00+09:00; user timezone: Asia/Tokyo. Use only supplied dates, IDs, people, and metadata. Referenced existing records are included for independent validation, not to be appended again to a live workspace.

**Reason:** Separate work, cutoff, and attention cue; add D only when an independent deadline concept is useful.

**Pitfall:** Do not add a redundant D merely to multiply records.

**Recommended** ([canonical fixture](../../../examples/ai-patterns/PAT-COM-001/recommended.life.txt))

<!-- fixture:PAT-COM-001/recommended -->
````lifetxt
[ ] T "報告書を書く" id:write do:2030-10-14 due:2030-10-20T17:00+09:00
[ ] D "報告書締切" id:deadline due:2030-10-20T17:00+09:00 ref:write
[ ] R "報告書提出を思い出す" id:reminder at:2030-10-20T09:00+09:00 ref:write
````

**Validation:** Core 1.0.3; engine source commit `97aa9b52c231f9aad5ba1403e8ed230d69f4d2a3`. Executed; independent review pending. CLI acceptance is not semantic proof.

| Fixture | Class | Exit | Diagnostics (severity/code/line) |
| --- | --- | ---: | --- |
| recommended | recommended | 0 | none |

Full diagnostic messages, input SHA-256, and commands are in the [manifest](../../../examples/ai-patterns/manifest.json). Meaning review is the author's source comparison, not independent approval.

**Sources:** [Format 1.0](../life_txt_format_spec.md) §7–14 + owning feature docs; [Profile](../../../prompts/lifetxt-assistant.md). [source 1](../../../examples/minimal_life.txt) / [source 2](../../../examples/team_status_life.txt) / [source 3](../../../examples/diary_life.txt) / [source 4](../../../examples/hierarchy_life.txt)

<a id="pat-com-002"></a>

## PAT-COM-002 — 反復ハイブリッド会議と準備

**Input (original language retained):** 毎週月曜14〜15時に会議室3とTeamsで定例。初回2030年10月14日。自分の進捗まとめは同日12時締切。11時に思い出す。

**Context:** Fictional example. Fixed baseline: 2030-10-11T12:00:00+09:00; user timezone: Asia/Tokyo. Use only supplied dates, IDs, people, and metadata. Referenced existing records are included for independent validation, not to be appended again to a live workspace.

**Reason:** Separate meeting interval, preparation deadline, and the explicitly supplied reminder time.

**Pitfall:** The Teams note is not a contract for creating a meeting or sending messages.

**Recommended** ([canonical fixture](../../../examples/ai-patterns/PAT-COM-002/recommended.life.txt))

<!-- fixture:PAT-COM-002/recommended -->
````lifetxt
[ ] E "進捗定例" from:2030-10-14T14:00+09:00 to:2030-10-14T15:00+09:00 repeat:weekly loc:"会議室3" note:"Teams併用"
[ ] T "進捗をまとめる" due:2030-10-14T12:00+09:00 repeat:weekly assignee:self
[ ] R "進捗まとめを思い出す" on:2030-10-14 at:11:00+09:00 repeat:weekly
````

**Validation:** Core 1.0.3; engine source commit `97aa9b52c231f9aad5ba1403e8ed230d69f4d2a3`. Executed; independent review pending. CLI acceptance is not semantic proof.

| Fixture | Class | Exit | Diagnostics (severity/code/line) |
| --- | --- | ---: | --- |
| recommended | recommended | 0 | none |

Full diagnostic messages, input SHA-256, and commands are in the [manifest](../../../examples/ai-patterns/manifest.json). Meaning review is the author's source comparison, not independent approval.

**Sources:** [Format 1.0](../life_txt_format_spec.md) §7–14 + owning feature docs; [Profile](../../../prompts/lifetxt-assistant.md). [source 1](../../../examples/minimal_life.txt) / [source 2](../../../examples/team_status_life.txt) / [source 3](../../../examples/diary_life.txt) / [source 4](../../../examples/hierarchy_life.txt)

<a id="pat-com-003"></a>

## PAT-COM-003 — 研究計画・実験・メモの階層

**Input (original language retained):** 研究計画researchの子に文献調査lit、次に実験exp。lit完了が実験の前提。メモも研究計画の子。IDはユーザー提供。

**Context:** Fictional example. Fixed baseline: 2030-10-11T12:00:00+09:00; user timezone: Asia/Tokyo. Use only supplied dates, IDs, people, and metadata. Referenced existing records are included for independent validation, not to be appended again to a live workspace.

**Reason:** Parent inclusion and prerequisite order are distinct relationships.

**Pitfall:** Indentation alone does not define dependency order.

**Recommended** ([canonical fixture](../../../examples/ai-patterns/PAT-COM-003/recommended.life.txt))

<!-- fixture:PAT-COM-003/recommended -->
````lifetxt
[ ] T "研究計画" id:research
  [ ] T "文献調査" id:lit
  [ ] T "実験" id:exp depends_on:lit
  [N] N "研究メモ"
  | 実験条件を確認する。
````

**Validation:** Core 1.0.3; engine source commit `97aa9b52c231f9aad5ba1403e8ed230d69f4d2a3`. Executed; independent review pending. CLI acceptance is not semantic proof.

| Fixture | Class | Exit | Diagnostics (severity/code/line) |
| --- | --- | ---: | --- |
| recommended | recommended | 0 | none |

Full diagnostic messages, input SHA-256, and commands are in the [manifest](../../../examples/ai-patterns/manifest.json). Meaning review is the author's source comparison, not independent approval.

**Sources:** [Format 1.0](../life_txt_format_spec.md) §7–14 + owning feature docs; [Profile](../../../prompts/lifetxt-assistant.md). [source 1](../../../examples/minimal_life.txt) / [source 2](../../../examples/team_status_life.txt) / [source 3](../../../examples/diary_life.txt) / [source 4](../../../examples/hierarchy_life.txt)

<a id="pat-com-004"></a>

## PAT-COM-004 — 日誌から別Taskへ

**Input (original language retained):** 2030年10月11日の日誌logに『文献を読んだ』。別に翌日『要約を書く』Taskをlog参照で追加。ID logはユーザー提供。日誌のmoodはcalm、weatherはsunny、場所labと明示する。

**Context:** Fictional example. Fixed baseline: 2030-10-11T12:00:00+09:00; user timezone: Asia/Tokyo. Use only supplied dates, IDs, people, and metadata. Referenced existing records are included for independent validation, not to be appended again to a live workspace.

**Reason:** Separate the past journal from the future task and preserve the requested link via ref.

**Pitfall:** Do not squeeze the whole diary into a task title.

**Recommended** ([canonical fixture](../../../examples/ai-patterns/PAT-COM-004/recommended.life.txt))

<!-- fixture:PAT-COM-004/recommended -->
````lifetxt
[N] J "研究日誌" id:log on:2030-10-11 mood:calm weather:sunny loc:lab
| 文献を読んだ。
[ ] T "要約を書く" do:2030-10-12 ref:log
````

**Validation:** Core 1.0.3; engine source commit `97aa9b52c231f9aad5ba1403e8ed230d69f4d2a3`. Executed; independent review pending. CLI acceptance is not semantic proof.

| Fixture | Class | Exit | Diagnostics (severity/code/line) |
| --- | --- | ---: | --- |
| recommended | recommended | 0 | none |

Full diagnostic messages, input SHA-256, and commands are in the [manifest](../../../examples/ai-patterns/manifest.json). Meaning review is the author's source comparison, not independent approval.

**Sources:** [Format 1.0](../life_txt_format_spec.md) §7–14 + owning feature docs; [Profile](../../../prompts/lifetxt-assistant.md). [source 1](../../../examples/minimal_life.txt) / [source 2](../../../examples/team_status_life.txt) / [source 3](../../../examples/diary_life.txt) / [source 4](../../../examples/hierarchy_life.txt)

<a id="pat-com-005"></a>

## PAT-COM-005 — チーム在席と人物・期間

**Input (original language retained):** ユーザー提供の状態スナップショット：aliceの2030年10月14日9〜10時の集中期間は終了済み。bobは同日9時30分から会議中で終了時刻不明。2人のteamはresearch、groupはlab_group、serviceはteams、visibilityはteam。

**Context:** Fictional example. Fixed baseline: 2030-10-11T12:00:00+09:00; user timezone: Asia/Tokyo. Use only supplied dates, IDs, people, and metadata. Referenced existing records are included for independent validation, not to be appended again to a live workspace.

**Reason:** In the supplied snapshot, use [x] for the closed interval and [/] for the interval whose end is unknown. These are supplied records, not claims of observed live service state.

**Pitfall:** person and assignee have different roles; do not promise external synchronization.

**Recommended** ([canonical fixture](../../../examples/ai-patterns/PAT-COM-005/recommended.life.txt))

<!-- fixture:PAT-COM-005/recommended -->
````lifetxt
[x] S "集中" from:2030-10-14T09:00+09:00 to:2030-10-14T10:00+09:00 person:alice state:focus team:research group:lab_group service:teams visibility:team
[/] S "会議中" from:2030-10-14T09:30+09:00 person:bob state:meeting team:research group:lab_group service:teams visibility:team
````

**Validation:** Core 1.0.3; engine source commit `97aa9b52c231f9aad5ba1403e8ed230d69f4d2a3`. Executed; independent review pending. CLI acceptance is not semantic proof.

| Fixture | Class | Exit | Diagnostics (severity/code/line) |
| --- | --- | ---: | --- |
| recommended | recommended | 0 | none |

Full diagnostic messages, input SHA-256, and commands are in the [manifest](../../../examples/ai-patterns/manifest.json). Meaning review is the author's source comparison, not independent approval.

**Sources:** [Format 1.0](../life_txt_format_spec.md) §7–14 + owning feature docs; [Profile](../../../prompts/lifetxt-assistant.md). [source 1](../../../examples/minimal_life.txt) / [source 2](../../../examples/team_status_life.txt) / [source 3](../../../examples/diary_life.txt) / [source 4](../../../examples/hierarchy_life.txt)

<a id="pat-com-006"></a>

## PAT-COM-006 — Message threadと通知期間・確認

**Input (original language retained):** ユーザー提供threadのレビュー依頼は自分→alice、2030年10月14日9時送信済み。replyはalice→自分の確認済み返信、9時5分。

**Context:** Fictional example. Fixed baseline: 2030-10-11T12:00:00+09:00; user timezone: Asia/Tokyo. Use only supplied dates, IDs, people, and metadata. Referenced existing records are included for independent validation, not to be appended again to a live workspace.

**Reason:** parent represents a message thread; sent or acknowledged messages do not prove review completion.

**Pitfall:** Do not turn the reply time into a successful review date.

**Recommended** ([canonical fixture](../../../examples/ai-patterns/PAT-COM-006/recommended.life.txt))

<!-- fixture:PAT-COM-006/recommended -->
````lifetxt
[x] M "レビュー依頼" id:thread sender:self recipient:alice done:2030-10-14T09:00+09:00
[x] M "依頼を確認した返信" id:reply parent:thread sender:alice recipient:self done:2030-10-14T09:05+09:00 ack:2030-10-14T09:05+09:00
````

**Validation:** Core 1.0.3; engine source commit `97aa9b52c231f9aad5ba1403e8ed230d69f4d2a3`. Executed; independent review pending. CLI acceptance is not semantic proof.

| Fixture | Class | Exit | Diagnostics (severity/code/line) |
| --- | --- | ---: | --- |
| recommended | recommended | 0 | none |

Full diagnostic messages, input SHA-256, and commands are in the [manifest](../../../examples/ai-patterns/manifest.json). Meaning review is the author's source comparison, not independent approval.

**Sources:** [Format 1.0](../life_txt_format_spec.md) §7–14 + owning feature docs; [Profile](../../../prompts/lifetxt-assistant.md). [source 1](../../../examples/minimal_life.txt) / [source 2](../../../examples/team_status_life.txt) / [source 3](../../../examples/diary_life.txt) / [source 4](../../../examples/hierarchy_life.txt)

<a id="pat-com-007"></a>

## PAT-COM-007 — 予定→実績→延期・置換workflow

**Input (original language retained):** 旧訪問oldは延期しnewへ置換、2030年10月22日が新予定。actualはnewを実現した実績。IDと実績日もユーザー提供。

**Context:** Fictional example. Fixed baseline: 2030-10-11T12:00:00+09:00; user timezone: Asia/Tokyo. Use only supplied dates, IDs, people, and metadata. Referenced existing records are included for independent validation, not to be appended again to a live workspace.

**Reason:** Separate the new date, replacement plan, and actual-to-plan realization. Retain current type-specific W106 warnings without rewriting specified replacement/realization semantics into another key.

**Pitfall:** Do not synthesize actuals from a plan; this source explicitly supplies the actual.

**Recommended** ([canonical fixture](../../../examples/ai-patterns/PAT-COM-007/recommended.life.txt))

<!-- fixture:PAT-COM-007/recommended -->
````lifetxt
[>] E "旧訪問" id:old on:2030-10-14 moved_to:2030-10-22 replaced_by:new
[ ] E "新訪問計画" id:new on:2030-10-22
[x] E "訪問実績" id:actual on:2030-10-22 done:2030-10-22 realizes:new
````

**Validation:** Core 1.0.3; engine source commit `97aa9b52c231f9aad5ba1403e8ed230d69f4d2a3`. Executed; independent review pending. CLI acceptance is not semantic proof.

| Fixture | Class | Exit | Diagnostics (severity/code/line) |
| --- | --- | ---: | --- |
| recommended | recommended | 0 | warning/W106/L1; warning/W106/L3 |

Full diagnostic messages, input SHA-256, and commands are in the [manifest](../../../examples/ai-patterns/manifest.json). Meaning review is the author's source comparison, not independent approval.

**Sources:** [Format 1.0](../life_txt_format_spec.md) §7–14 + owning feature docs; [Profile](../../../prompts/lifetxt-assistant.md). [source 1](../../../examples/minimal_life.txt) / [source 2](../../../examples/team_status_life.txt) / [source 3](../../../examples/diary_life.txt) / [source 4](../../../examples/hierarchy_life.txt)

<a id="pat-com-008"></a>

## PAT-COM-008 — 提供済みmetadata・添付参照・record拡張境界

**Input (original language retained):** project:research、tag:designの会議recordを残す。2030年10月14日。参照資料はFormat仕様。record:meetingを指定。関連ユーザーalice、想定1時間、作成2030年10月10日・更新10月11日、URL https://example.com/designも指定。

**Context:** Fictional example. Fixed baseline: 2030-10-11T12:00:00+09:00; user timezone: Asia/Tokyo. Use only supplied dates, IDs, people, and metadata. Referenced existing records are included for independent validation, not to be appended again to a live workspace.

**Reason:** Preserve supplied metadata; record conventions layer on the base type and follow their owning feature documentation.

**Pitfall:** Preserving an unknown record value does not guarantee support by every feature.

**Recommended** ([canonical fixture](../../../examples/ai-patterns/PAT-COM-008/recommended.life.txt))

<!-- fixture:PAT-COM-008/recommended -->
````lifetxt
[ ] E "設計会議" on:2030-10-14 project:research tag:design record:meeting file:../../../docs/en/life_txt_format_spec.md user:alice est:1h created:2030-10-10 updated:2030-10-11 url:https://example.com/design
````

**Validation:** Core 1.0.3; engine source commit `97aa9b52c231f9aad5ba1403e8ed230d69f4d2a3`. Executed; independent review pending. CLI acceptance is not semantic proof.

| Fixture | Class | Exit | Diagnostics (severity/code/line) |
| --- | --- | ---: | --- |
| recommended | recommended | 0 | none |

Full diagnostic messages, input SHA-256, and commands are in the [manifest](../../../examples/ai-patterns/manifest.json). Meaning review is the author's source comparison, not independent approval.

**Sources:** [Format 1.0](../life_txt_format_spec.md) §7–14 + owning feature docs; [Profile](../../../prompts/lifetxt-assistant.md). [source 1](../../../examples/minimal_life.txt) / [source 2](../../../examples/team_status_life.txt) / [source 3](../../../examples/diary_life.txt) / [source 4](../../../examples/hierarchy_life.txt)

Feature-specific record contracts: [projects](../projects.md), [tickets](../tickets.md).

