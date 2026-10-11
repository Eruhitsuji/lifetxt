# AI Reference Patterns — Composite / 複合例

このページのコードはcanonical fixtureのコピー。日英で同じ原文・コードを使う。著者のCore検証と人手の意味照合を区別し、独立reviewはPRで行う。

[Format 1.0](../life_txt_format_spec.md) / [Profile](../../../prompts/lifetxt-assistant.md) / [Fixture maintenance](../../../examples/ai-patterns/README.md)

<a id="pat-com-001"></a>

## PAT-COM-001 — Task+Deadline+Reminder

**入力（原文保持）:** ユーザー指定ID writeで10月14日に報告書を書き、20日17時締切(deadline)。20日9時に思い出す(reminder)。年2030。

**前提:** 架空例。基準日時は2030-10-11T12:00:00+09:00、利用者TZはAsia/Tokyo。日時は明示されたものだけ使用。ID/人物/metadataは入力に指定したものだけ。例の参照recordも検査文脈として同梱し、既存recordを再追加する手順とはしない。

**理由:** 作業・受付期限・注意喚起を区別する。Dは必要な独立締切概念がある場合だけ追加する。

**注意・反例:** TのdueとDを無意味に重複追加しない。

**推奨例** ([canonical fixture](../../../examples/ai-patterns/PAT-COM-001/recommended.life.txt))

<!-- fixture:PAT-COM-001/recommended -->
````lifetxt
[ ] T "報告書を書く" id:write do:2030-10-14 due:2030-10-20T17:00+09:00
[ ] D "報告書締切" id:deadline due:2030-10-20T17:00+09:00 ref:write
[ ] R "報告書提出を思い出す" id:reminder at:2030-10-20T09:00+09:00 ref:write
````

**検証:** Core 1.0.3; engine source commit `97aa9b52c231f9aad5ba1403e8ed230d69f4d2a3`. 実測済み。独立reviewは未完了。CLI受理は意味保証ではない。

| Fixture | Class | Exit | Diagnostics (severity/code/line) |
| --- | --- | ---: | --- |
| recommended | recommended | 0 | none |

全診断メッセージ・入力SHA-256・コマンドは[manifest](../../../examples/ai-patterns/manifest.json)に記録。意味レビューは著者による原入力との照合（独立承認ではない）。

**出典:** [Format 1.0](../life_txt_format_spec.md) §7–14 + owning feature docs; [Profile](../../../prompts/lifetxt-assistant.md). [source 1](../../../examples/minimal_life.txt) / [source 2](../../../examples/team_status_life.txt) / [source 3](../../../examples/diary_life.txt) / [source 4](../../../examples/hierarchy_life.txt)

<a id="pat-com-002"></a>

## PAT-COM-002 — 反復ハイブリッド会議と準備

**入力（原文保持）:** 毎週月曜14〜15時に会議室3とTeamsで定例。初回2030年10月14日。自分の進捗まとめは同日12時締切。11時に思い出す。

**前提:** 架空例。基準日時は2030-10-11T12:00:00+09:00、利用者TZはAsia/Tokyo。日時は明示されたものだけ使用。ID/人物/metadataは入力に指定したものだけ。例の参照recordも検査文脈として同梱し、既存recordを再追加する手順とはしない。

**理由:** 開催区間・準備期限・明示された通知時刻を別recordにする。

**注意・反例:** Teams併用noteは外部会議作成・送信の実行契約ではない。

**推奨例** ([canonical fixture](../../../examples/ai-patterns/PAT-COM-002/recommended.life.txt))

<!-- fixture:PAT-COM-002/recommended -->
````lifetxt
[ ] E "進捗定例" from:2030-10-14T14:00+09:00 to:2030-10-14T15:00+09:00 repeat:weekly loc:"会議室3" note:"Teams併用"
[ ] T "進捗をまとめる" due:2030-10-14T12:00+09:00 repeat:weekly assignee:self
[ ] R "進捗まとめを思い出す" on:2030-10-14 at:11:00+09:00 repeat:weekly
````

**検証:** Core 1.0.3; engine source commit `97aa9b52c231f9aad5ba1403e8ed230d69f4d2a3`. 実測済み。独立reviewは未完了。CLI受理は意味保証ではない。

| Fixture | Class | Exit | Diagnostics (severity/code/line) |
| --- | --- | ---: | --- |
| recommended | recommended | 0 | none |

全診断メッセージ・入力SHA-256・コマンドは[manifest](../../../examples/ai-patterns/manifest.json)に記録。意味レビューは著者による原入力との照合（独立承認ではない）。

**出典:** [Format 1.0](../life_txt_format_spec.md) §7–14 + owning feature docs; [Profile](../../../prompts/lifetxt-assistant.md). [source 1](../../../examples/minimal_life.txt) / [source 2](../../../examples/team_status_life.txt) / [source 3](../../../examples/diary_life.txt) / [source 4](../../../examples/hierarchy_life.txt)

<a id="pat-com-003"></a>

## PAT-COM-003 — 研究計画・実験・メモの階層

**入力（原文保持）:** 研究計画researchの子に文献調査lit、次に実験exp。lit完了が実験の前提。メモも研究計画の子。IDはユーザー提供。

**前提:** 架空例。基準日時は2030-10-11T12:00:00+09:00、利用者TZはAsia/Tokyo。日時は明示されたものだけ使用。ID/人物/metadataは入力に指定したものだけ。例の参照recordも検査文脈として同梱し、既存recordを再追加する手順とはしない。

**理由:** 包含parentと作業順depends_onを別々に表す。

**注意・反例:** インデントだけで依存順は決まらない。

**推奨例** ([canonical fixture](../../../examples/ai-patterns/PAT-COM-003/recommended.life.txt))

<!-- fixture:PAT-COM-003/recommended -->
````lifetxt
[ ] T "研究計画" id:research
  [ ] T "文献調査" id:lit
  [ ] T "実験" id:exp depends_on:lit
  [N] N "研究メモ"
  | 実験条件を確認する。
````

**検証:** Core 1.0.3; engine source commit `97aa9b52c231f9aad5ba1403e8ed230d69f4d2a3`. 実測済み。独立reviewは未完了。CLI受理は意味保証ではない。

| Fixture | Class | Exit | Diagnostics (severity/code/line) |
| --- | --- | ---: | --- |
| recommended | recommended | 0 | none |

全診断メッセージ・入力SHA-256・コマンドは[manifest](../../../examples/ai-patterns/manifest.json)に記録。意味レビューは著者による原入力との照合（独立承認ではない）。

**出典:** [Format 1.0](../life_txt_format_spec.md) §7–14 + owning feature docs; [Profile](../../../prompts/lifetxt-assistant.md). [source 1](../../../examples/minimal_life.txt) / [source 2](../../../examples/team_status_life.txt) / [source 3](../../../examples/diary_life.txt) / [source 4](../../../examples/hierarchy_life.txt)

<a id="pat-com-004"></a>

## PAT-COM-004 — 日誌から別Taskへ

**入力（原文保持）:** 2030年10月11日の日誌logに『文献を読んだ』。別に翌日『要約を書く』Taskをlog参照で追加。ID logはユーザー提供。日誌のmoodはcalm、weatherはsunny、場所labと明示する。

**前提:** 架空例。基準日時は2030-10-11T12:00:00+09:00、利用者TZはAsia/Tokyo。日時は明示されたものだけ使用。ID/人物/metadataは入力に指定したものだけ。例の参照recordも検査文脈として同梱し、既存recordを再追加する手順とはしない。

**理由:** 過去記録Jと未来行動Tを分け、ユーザー指定の関連をrefで保つ。

**注意・反例:** 日誌全文をTaskのtitleへ押し込まない。

**推奨例** ([canonical fixture](../../../examples/ai-patterns/PAT-COM-004/recommended.life.txt))

<!-- fixture:PAT-COM-004/recommended -->
````lifetxt
[N] J "研究日誌" id:log on:2030-10-11 mood:calm weather:sunny loc:lab
| 文献を読んだ。
[ ] T "要約を書く" do:2030-10-12 ref:log
````

**検証:** Core 1.0.3; engine source commit `97aa9b52c231f9aad5ba1403e8ed230d69f4d2a3`. 実測済み。独立reviewは未完了。CLI受理は意味保証ではない。

| Fixture | Class | Exit | Diagnostics (severity/code/line) |
| --- | --- | ---: | --- |
| recommended | recommended | 0 | none |

全診断メッセージ・入力SHA-256・コマンドは[manifest](../../../examples/ai-patterns/manifest.json)に記録。意味レビューは著者による原入力との照合（独立承認ではない）。

**出典:** [Format 1.0](../life_txt_format_spec.md) §7–14 + owning feature docs; [Profile](../../../prompts/lifetxt-assistant.md). [source 1](../../../examples/minimal_life.txt) / [source 2](../../../examples/team_status_life.txt) / [source 3](../../../examples/diary_life.txt) / [source 4](../../../examples/hierarchy_life.txt)

<a id="pat-com-005"></a>

## PAT-COM-005 — チーム在席と人物・期間

**入力（原文保持）:** ユーザー提供の状態スナップショット：aliceの2030年10月14日9〜10時の集中期間は終了済み。bobは同日9時30分から会議中で終了時刻不明。2人のteamはresearch、groupはlab_group、serviceはteams、visibilityはteam。

**前提:** 架空例。基準日時は2030-10-11T12:00:00+09:00、利用者TZはAsia/Tokyo。日時は明示されたものだけ使用。ID/人物/metadataは入力に指定したものだけ。例の参照recordも検査文脈として同梱し、既存recordを再追加する手順とはしない。

**理由:** 提供済みスナップショットの閉じた期間は[x]、終了不明の期間は[/]で別recordにする。外部サービスで現在観測した状態とは主張しない。

**注意・反例:** personとassigneeは役割が異なる。外部サービスへの同期を約束しない。

**推奨例** ([canonical fixture](../../../examples/ai-patterns/PAT-COM-005/recommended.life.txt))

<!-- fixture:PAT-COM-005/recommended -->
````lifetxt
[x] S "集中" from:2030-10-14T09:00+09:00 to:2030-10-14T10:00+09:00 person:alice state:focus team:research group:lab_group service:teams visibility:team
[/] S "会議中" from:2030-10-14T09:30+09:00 person:bob state:meeting team:research group:lab_group service:teams visibility:team
````

**検証:** Core 1.0.3; engine source commit `97aa9b52c231f9aad5ba1403e8ed230d69f4d2a3`. 実測済み。独立reviewは未完了。CLI受理は意味保証ではない。

| Fixture | Class | Exit | Diagnostics (severity/code/line) |
| --- | --- | ---: | --- |
| recommended | recommended | 0 | none |

全診断メッセージ・入力SHA-256・コマンドは[manifest](../../../examples/ai-patterns/manifest.json)に記録。意味レビューは著者による原入力との照合（独立承認ではない）。

**出典:** [Format 1.0](../life_txt_format_spec.md) §7–14 + owning feature docs; [Profile](../../../prompts/lifetxt-assistant.md). [source 1](../../../examples/minimal_life.txt) / [source 2](../../../examples/team_status_life.txt) / [source 3](../../../examples/diary_life.txt) / [source 4](../../../examples/hierarchy_life.txt)

<a id="pat-com-006"></a>

## PAT-COM-006 — Message threadと通知期間・確認

**入力（原文保持）:** ユーザー提供threadのレビュー依頼は自分→alice、2030年10月14日9時送信済み。replyはalice→自分の確認済み返信、9時5分。

**前提:** 架空例。基準日時は2030-10-11T12:00:00+09:00、利用者TZはAsia/Tokyo。日時は明示されたものだけ使用。ID/人物/metadataは入力に指定したものだけ。例の参照recordも検査文脈として同梱し、既存recordを再追加する手順とはしない。

**理由:** parentはthread関係。メッセージ送信/確認とレビュー作業完了を混同しない。

**注意・反例:** 返信の受信時刻をレビュー成功日へ転記しない。

**推奨例** ([canonical fixture](../../../examples/ai-patterns/PAT-COM-006/recommended.life.txt))

<!-- fixture:PAT-COM-006/recommended -->
````lifetxt
[x] M "レビュー依頼" id:thread sender:self recipient:alice done:2030-10-14T09:00+09:00
[x] M "依頼を確認した返信" id:reply parent:thread sender:alice recipient:self done:2030-10-14T09:05+09:00 ack:2030-10-14T09:05+09:00
````

**検証:** Core 1.0.3; engine source commit `97aa9b52c231f9aad5ba1403e8ed230d69f4d2a3`. 実測済み。独立reviewは未完了。CLI受理は意味保証ではない。

| Fixture | Class | Exit | Diagnostics (severity/code/line) |
| --- | --- | ---: | --- |
| recommended | recommended | 0 | none |

全診断メッセージ・入力SHA-256・コマンドは[manifest](../../../examples/ai-patterns/manifest.json)に記録。意味レビューは著者による原入力との照合（独立承認ではない）。

**出典:** [Format 1.0](../life_txt_format_spec.md) §7–14 + owning feature docs; [Profile](../../../prompts/lifetxt-assistant.md). [source 1](../../../examples/minimal_life.txt) / [source 2](../../../examples/team_status_life.txt) / [source 3](../../../examples/diary_life.txt) / [source 4](../../../examples/hierarchy_life.txt)

<a id="pat-com-007"></a>

## PAT-COM-007 — 予定→実績→延期・置換workflow

**入力（原文保持）:** 旧訪問oldは延期しnewへ置換、2030年10月22日が新予定。actualはnewを実現した実績。IDと実績日もユーザー提供。

**前提:** 架空例。基準日時は2030-10-11T12:00:00+09:00、利用者TZはAsia/Tokyo。日時は明示されたものだけ使用。ID/人物/metadataは入力に指定したものだけ。例の参照recordも検査文脈として同梱し、既存recordを再追加する手順とはしない。

**理由:** 延期先日時・計画置換・実績が実現する計画を分離する。現Coreのtype別custom警告W106は保持し、置換/実現の公式意味を別keyへ改変しない。

**注意・反例:** 予定があるだけで実績を生成しない。この入力は実績も明示している。

**推奨例** ([canonical fixture](../../../examples/ai-patterns/PAT-COM-007/recommended.life.txt))

<!-- fixture:PAT-COM-007/recommended -->
````lifetxt
[>] E "旧訪問" id:old on:2030-10-14 moved_to:2030-10-22 replaced_by:new
[ ] E "新訪問計画" id:new on:2030-10-22
[x] E "訪問実績" id:actual on:2030-10-22 done:2030-10-22 realizes:new
````

**検証:** Core 1.0.3; engine source commit `97aa9b52c231f9aad5ba1403e8ed230d69f4d2a3`. 実測済み。独立reviewは未完了。CLI受理は意味保証ではない。

| Fixture | Class | Exit | Diagnostics (severity/code/line) |
| --- | --- | ---: | --- |
| recommended | recommended | 0 | warning/W106/L1; warning/W106/L3 |

全診断メッセージ・入力SHA-256・コマンドは[manifest](../../../examples/ai-patterns/manifest.json)に記録。意味レビューは著者による原入力との照合（独立承認ではない）。

**出典:** [Format 1.0](../life_txt_format_spec.md) §7–14 + owning feature docs; [Profile](../../../prompts/lifetxt-assistant.md). [source 1](../../../examples/minimal_life.txt) / [source 2](../../../examples/team_status_life.txt) / [source 3](../../../examples/diary_life.txt) / [source 4](../../../examples/hierarchy_life.txt)

<a id="pat-com-008"></a>

## PAT-COM-008 — 提供済みmetadata・添付参照・record拡張境界

**入力（原文保持）:** project:research、tag:designの会議recordを残す。2030年10月14日。参照資料はFormat仕様。record:meetingを指定。関連ユーザーalice、想定1時間、作成2030年10月10日・更新10月11日、URL https://example.com/designも指定。

**前提:** 架空例。基準日時は2030-10-11T12:00:00+09:00、利用者TZはAsia/Tokyo。日時は明示されたものだけ使用。ID/人物/metadataは入力に指定したものだけ。例の参照recordも検査文脈として同梱し、既存recordを再追加する手順とはしない。

**理由:** 指定されたmetadataを保持する。recordはbase typeを増やさず、機能所有文書の約束に従う。

**注意・反例:** 未知record値が保存可能でも全機能の扱いは保証しない。

**推奨例** ([canonical fixture](../../../examples/ai-patterns/PAT-COM-008/recommended.life.txt))

<!-- fixture:PAT-COM-008/recommended -->
````lifetxt
[ ] E "設計会議" on:2030-10-14 project:research tag:design record:meeting file:../../../docs/en/life_txt_format_spec.md user:alice est:1h created:2030-10-10 updated:2030-10-11 url:https://example.com/design
````

**検証:** Core 1.0.3; engine source commit `97aa9b52c231f9aad5ba1403e8ed230d69f4d2a3`. 実測済み。独立reviewは未完了。CLI受理は意味保証ではない。

| Fixture | Class | Exit | Diagnostics (severity/code/line) |
| --- | --- | ---: | --- |
| recommended | recommended | 0 | none |

全診断メッセージ・入力SHA-256・コマンドは[manifest](../../../examples/ai-patterns/manifest.json)に記録。意味レビューは著者による原入力との照合（独立承認ではない）。

**出典:** [Format 1.0](../life_txt_format_spec.md) §7–14 + owning feature docs; [Profile](../../../prompts/lifetxt-assistant.md). [source 1](../../../examples/minimal_life.txt) / [source 2](../../../examples/team_status_life.txt) / [source 3](../../../examples/diary_life.txt) / [source 4](../../../examples/hierarchy_life.txt)

機能固有recordの詳細は[projects](../projects.md), [tickets](../tickets.md).

