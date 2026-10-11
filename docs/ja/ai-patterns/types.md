# AI Reference Patterns — Types / 型

このページのコードはcanonical fixtureのコピー。日英で同じ原文・コードを使う。著者のCore検証と人手の意味照合を区別し、独立reviewはPRで行う。

[Format 1.0](../life_txt_format_spec.md) / [Profile](../../../prompts/lifetxt-assistant.md) / [Fixture maintenance](../../../examples/ai-patterns/README.md)

<a id="pat-type-001"></a>

## PAT-TYPE-001 — Taskの実行

**入力（原文保持）:** 牛乳を買う。日時はまだ決めていない。

**前提:** 架空例。基準日時は2030-10-11T12:00:00+09:00、利用者TZはAsia/Tokyo。日時は明示されたものだけ使用。ID/人物/metadataは入力に指定したものだけ。例の参照recordも検査文脈として同梱し、既存recordを再追加する手順とはしない。

**理由:** 具体的な行動をTで記録し、未指定の期限・予定日・IDを加えない。

**注意・反例:** 日時がないことは誤りではない。

**推奨例** ([canonical fixture](../../../examples/ai-patterns/PAT-TYPE-001/recommended.life.txt))

<!-- fixture:PAT-TYPE-001/recommended -->
````lifetxt
[ ] T "牛乳を買う"
````

**検証:** Core 1.0.3; engine source commit `97aa9b52c231f9aad5ba1403e8ed230d69f4d2a3`. 実測済み。独立reviewは未完了。CLI受理は意味保証ではない。

| Fixture | Class | Exit | Diagnostics (severity/code/line) |
| --- | --- | ---: | --- |
| recommended | recommended | 0 | none |

全診断メッセージ・入力SHA-256・コマンドは[manifest](../../../examples/ai-patterns/manifest.json)に記録。意味レビューは著者による原入力との照合（独立承認ではない）。

**出典:** [Format 1.0](../life_txt_format_spec.md) §2–3, §9, §13–14; [Profile](../../../prompts/lifetxt-assistant.md). [source 1](../../../examples/tasks_life.txt) / [source 2](../../../examples/events_life.txt) / [source 3](../../../examples/habits_reminders_life.txt) / [source 4](../../../examples/messages_life.txt) / [source 5](../../../examples/diary_life.txt) / [source 6](../../../examples/status_presence.txt)

<a id="pat-type-002"></a>

## PAT-TYPE-002 — Eventの開催

**入力（原文保持）:** 2030年10月14日10時に会議がある。

**前提:** 架空例。基準日時は2030-10-11T12:00:00+09:00、利用者TZはAsia/Tokyo。日時は明示されたものだけ使用。ID/人物/metadataは入力に指定したものだけ。例の参照recordも検査文脈として同梱し、既存recordを再追加する手順とはしない。

**理由:** 開催される出来事をEで記録する。終了時刻を推測しない。

**注意・反例:** Tの作業とEの予定は同じ意味ではない。

**推奨例** ([canonical fixture](../../../examples/ai-patterns/PAT-TYPE-002/recommended.life.txt))

<!-- fixture:PAT-TYPE-002/recommended -->
````lifetxt
[ ] E "会議" at:2030-10-14T10:00+09:00
````

**検証:** Core 1.0.3; engine source commit `97aa9b52c231f9aad5ba1403e8ed230d69f4d2a3`. 実測済み。独立reviewは未完了。CLI受理は意味保証ではない。

| Fixture | Class | Exit | Diagnostics (severity/code/line) |
| --- | --- | ---: | --- |
| recommended | recommended | 0 | none |

全診断メッセージ・入力SHA-256・コマンドは[manifest](../../../examples/ai-patterns/manifest.json)に記録。意味レビューは著者による原入力との照合（独立承認ではない）。

**出典:** [Format 1.0](../life_txt_format_spec.md) §2–3, §9, §13–14; [Profile](../../../prompts/lifetxt-assistant.md). [source 1](../../../examples/tasks_life.txt) / [source 2](../../../examples/events_life.txt) / [source 3](../../../examples/habits_reminders_life.txt) / [source 4](../../../examples/messages_life.txt) / [source 5](../../../examples/diary_life.txt) / [source 6](../../../examples/status_presence.txt)

<a id="pat-type-003"></a>

## PAT-TYPE-003 — Deadlineの締切

**入力（原文保持）:** 申請の受付締切は2030年10月20日17時。

**前提:** 架空例。基準日時は2030-10-11T12:00:00+09:00、利用者TZはAsia/Tokyo。日時は明示されたものだけ使用。ID/人物/metadataは入力に指定したものだけ。例の参照recordも検査文脈として同梱し、既存recordを再追加する手順とはしない。

**理由:** Dは作業そのものではなく受付の限界時刻を表す。

**注意・反例:** この記録だけで提出作業が作られるわけではない。

**推奨例** ([canonical fixture](../../../examples/ai-patterns/PAT-TYPE-003/recommended.life.txt))

<!-- fixture:PAT-TYPE-003/recommended -->
````lifetxt
[ ] D "申請受付締切" due:2030-10-20T17:00+09:00
````

**検証:** Core 1.0.3; engine source commit `97aa9b52c231f9aad5ba1403e8ed230d69f4d2a3`. 実測済み。独立reviewは未完了。CLI受理は意味保証ではない。

| Fixture | Class | Exit | Diagnostics (severity/code/line) |
| --- | --- | ---: | --- |
| recommended | recommended | 0 | none |

全診断メッセージ・入力SHA-256・コマンドは[manifest](../../../examples/ai-patterns/manifest.json)に記録。意味レビューは著者による原入力との照合（独立承認ではない）。

**出典:** [Format 1.0](../life_txt_format_spec.md) §2–3, §9, §13–14; [Profile](../../../prompts/lifetxt-assistant.md). [source 1](../../../examples/tasks_life.txt) / [source 2](../../../examples/events_life.txt) / [source 3](../../../examples/habits_reminders_life.txt) / [source 4](../../../examples/messages_life.txt) / [source 5](../../../examples/diary_life.txt) / [source 6](../../../examples/status_presence.txt)

<a id="pat-type-004"></a>

## PAT-TYPE-004 — Reminderの注意喚起

**入力（原文保持）:** 2030年10月14日18時に図書館への電話を思い出すための記録を作る。

**前提:** 架空例。基準日時は2030-10-11T12:00:00+09:00、利用者TZはAsia/Tokyo。日時は明示されたものだけ使用。ID/人物/metadataは入力に指定したものだけ。例の参照recordも検査文脈として同梱し、既存recordを再追加する手順とはしない。

**理由:** 注意喚起の意図をRで表す。

**注意・反例:** 生成した行だけでは実機通知を設定しない。

**推奨例** ([canonical fixture](../../../examples/ai-patterns/PAT-TYPE-004/recommended.life.txt))

<!-- fixture:PAT-TYPE-004/recommended -->
````lifetxt
[ ] R "図書館への電話を思い出す" at:2030-10-14T18:00+09:00
````

**検証:** Core 1.0.3; engine source commit `97aa9b52c231f9aad5ba1403e8ed230d69f4d2a3`. 実測済み。独立reviewは未完了。CLI受理は意味保証ではない。

| Fixture | Class | Exit | Diagnostics (severity/code/line) |
| --- | --- | ---: | --- |
| recommended | recommended | 0 | none |

全診断メッセージ・入力SHA-256・コマンドは[manifest](../../../examples/ai-patterns/manifest.json)に記録。意味レビューは著者による原入力との照合（独立承認ではない）。

**出典:** [Format 1.0](../life_txt_format_spec.md) §2–3, §9, §13–14; [Profile](../../../prompts/lifetxt-assistant.md). [source 1](../../../examples/tasks_life.txt) / [source 2](../../../examples/events_life.txt) / [source 3](../../../examples/habits_reminders_life.txt) / [source 4](../../../examples/messages_life.txt) / [source 5](../../../examples/diary_life.txt) / [source 6](../../../examples/status_presence.txt)

<a id="pat-type-005"></a>

## PAT-TYPE-005 — Habitの習慣

**入力（原文保持）:** 毎日18時に英語を学習する習慣を記録する。

**前提:** 架空例。基準日時は2030-10-11T12:00:00+09:00、利用者TZはAsia/Tokyo。日時は明示されたものだけ使用。ID/人物/metadataは入力に指定したものだけ。例の参照recordも検査文脈として同梱し、既存recordを再追加する手順とはしない。

**理由:** 繰り返す実践をHで表す。起点日は未指定なので時刻だけを保持する。

**注意・反例:** 起点なし時刻の展開には有界範囲が必要。

**推奨例** ([canonical fixture](../../../examples/ai-patterns/PAT-TYPE-005/recommended.life.txt))

<!-- fixture:PAT-TYPE-005/recommended -->
````lifetxt
[ ] H "英語を学習する" repeat:daily at:18:00
````

**検証:** Core 1.0.3; engine source commit `97aa9b52c231f9aad5ba1403e8ed230d69f4d2a3`. 実測済み。独立reviewは未完了。CLI受理は意味保証ではない。

| Fixture | Class | Exit | Diagnostics (severity/code/line) |
| --- | --- | ---: | --- |
| recommended | recommended | 0 | none |

全診断メッセージ・入力SHA-256・コマンドは[manifest](../../../examples/ai-patterns/manifest.json)に記録。意味レビューは著者による原入力との照合（独立承認ではない）。

**出典:** [Format 1.0](../life_txt_format_spec.md) §2–3, §9, §13–14; [Profile](../../../prompts/lifetxt-assistant.md). [source 1](../../../examples/tasks_life.txt) / [source 2](../../../examples/events_life.txt) / [source 3](../../../examples/habits_reminders_life.txt) / [source 4](../../../examples/messages_life.txt) / [source 5](../../../examples/diary_life.txt) / [source 6](../../../examples/status_presence.txt)

<a id="pat-type-006"></a>

## PAT-TYPE-006 — Noteの持続的情報

**入力（原文保持）:** 資料には図を増やすというメモを残す。

**前提:** 架空例。基準日時は2030-10-11T12:00:00+09:00、利用者TZはAsia/Tokyo。日時は明示されたものだけ使用。ID/人物/metadataは入力に指定したものだけ。例の参照recordも検査文脈として同梱し、既存recordを再追加する手順とはしない。

**理由:** 継続的に参照する情報はN、状態は[N]にする。

**注意・反例:** メモを勝手に未完了Taskへ変えない。

**推奨例** ([canonical fixture](../../../examples/ai-patterns/PAT-TYPE-006/recommended.life.txt))

<!-- fixture:PAT-TYPE-006/recommended -->
````lifetxt
[N] N "資料には図を増やす"
````

**検証:** Core 1.0.3; engine source commit `97aa9b52c231f9aad5ba1403e8ed230d69f4d2a3`. 実測済み。独立reviewは未完了。CLI受理は意味保証ではない。

| Fixture | Class | Exit | Diagnostics (severity/code/line) |
| --- | --- | ---: | --- |
| recommended | recommended | 0 | none |

全診断メッセージ・入力SHA-256・コマンドは[manifest](../../../examples/ai-patterns/manifest.json)に記録。意味レビューは著者による原入力との照合（独立承認ではない）。

**出典:** [Format 1.0](../life_txt_format_spec.md) §2–3, §9, §13–14; [Profile](../../../prompts/lifetxt-assistant.md). [source 1](../../../examples/tasks_life.txt) / [source 2](../../../examples/events_life.txt) / [source 3](../../../examples/habits_reminders_life.txt) / [source 4](../../../examples/messages_life.txt) / [source 5](../../../examples/diary_life.txt) / [source 6](../../../examples/status_presence.txt)

<a id="pat-type-007"></a>

## PAT-TYPE-007 — Statusの在席状態

**入力（原文保持）:** 自分は2030年10月14日9時から集中作業中。

**前提:** 架空例。基準日時は2030-10-11T12:00:00+09:00、利用者TZはAsia/Tokyo。日時は明示されたものだけ使用。ID/人物/metadataは入力に指定したものだけ。例の参照recordも検査文脈として同梱し、既存recordを再追加する手順とはしない。

**理由:** Sは在席状態で、日時とstateを持つ。対象の自分はperson:self。

**注意・反例:** 外部チャットの在席表示を自動更新する主張はしない。

**推奨例** ([canonical fixture](../../../examples/ai-patterns/PAT-TYPE-007/recommended.life.txt))

<!-- fixture:PAT-TYPE-007/recommended -->
````lifetxt
[/] S "集中作業中" from:2030-10-14T09:00+09:00 state:focus person:self
````

**検証:** Core 1.0.3; engine source commit `97aa9b52c231f9aad5ba1403e8ed230d69f4d2a3`. 実測済み。独立reviewは未完了。CLI受理は意味保証ではない。

| Fixture | Class | Exit | Diagnostics (severity/code/line) |
| --- | --- | ---: | --- |
| recommended | recommended | 0 | none |

全診断メッセージ・入力SHA-256・コマンドは[manifest](../../../examples/ai-patterns/manifest.json)に記録。意味レビューは著者による原入力との照合（独立承認ではない）。

**出典:** [Format 1.0](../life_txt_format_spec.md) §2–3, §9, §13–14; [Profile](../../../prompts/lifetxt-assistant.md). [source 1](../../../examples/tasks_life.txt) / [source 2](../../../examples/events_life.txt) / [source 3](../../../examples/habits_reminders_life.txt) / [source 4](../../../examples/messages_life.txt) / [source 5](../../../examples/diary_life.txt) / [source 6](../../../examples/status_presence.txt)

<a id="pat-type-008"></a>

## PAT-TYPE-008 — Messageの伝達依頼

**入力（原文保持）:** 2030年10月14日9時に自分からaliceへ資料レビュー依頼を送るための記録。

**前提:** 架空例。基準日時は2030-10-11T12:00:00+09:00、利用者TZはAsia/Tokyo。日時は明示されたものだけ使用。ID/人物/metadataは入力に指定したものだけ。例の参照recordも検査文脈として同梱し、既存recordを再追加する手順とはしない。

**理由:** Mで送信者・受信者・通知日時を記録する。本文は依頼されていないので創作しない。

**注意・反例:** 送信済みと未送信の依頼を区別する。

**推奨例** ([canonical fixture](../../../examples/ai-patterns/PAT-TYPE-008/recommended.life.txt))

<!-- fixture:PAT-TYPE-008/recommended -->
````lifetxt
[ ] M "資料レビュー依頼" sender:self recipient:alice notify_at:2030-10-14T09:00+09:00
````

**検証:** Core 1.0.3; engine source commit `97aa9b52c231f9aad5ba1403e8ed230d69f4d2a3`. 実測済み。独立reviewは未完了。CLI受理は意味保証ではない。

| Fixture | Class | Exit | Diagnostics (severity/code/line) |
| --- | --- | ---: | --- |
| recommended | recommended | 0 | none |

全診断メッセージ・入力SHA-256・コマンドは[manifest](../../../examples/ai-patterns/manifest.json)に記録。意味レビューは著者による原入力との照合（独立承認ではない）。

**出典:** [Format 1.0](../life_txt_format_spec.md) §2–3, §9, §13–14; [Profile](../../../prompts/lifetxt-assistant.md). [source 1](../../../examples/tasks_life.txt) / [source 2](../../../examples/events_life.txt) / [source 3](../../../examples/habits_reminders_life.txt) / [source 4](../../../examples/messages_life.txt) / [source 5](../../../examples/diary_life.txt) / [source 6](../../../examples/status_presence.txt)

<a id="pat-type-009"></a>

## PAT-TYPE-009 — Journalの日時付き記録

**入力（原文保持）:** 2030年10月11日の研究日誌。今日は関連文献を読んだ。

**前提:** 架空例。基準日時は2030-10-11T12:00:00+09:00、利用者TZはAsia/Tokyo。日時は明示されたものだけ使用。ID/人物/metadataは入力に指定したものだけ。例の参照recordも検査文脈として同梱し、既存recordを再追加する手順とはしない。

**理由:** 日付のある振り返りはJにし、長い内容はbody継続行へ置く。

**注意・反例:** Jにも[N]を使い、体験からTaskを自動生成しない。

**推奨例** ([canonical fixture](../../../examples/ai-patterns/PAT-TYPE-009/recommended.life.txt))

<!-- fixture:PAT-TYPE-009/recommended -->
````lifetxt
[N] J "研究日誌" on:2030-10-11
| 今日は関連文献を読んだ。
````

**検証:** Core 1.0.3; engine source commit `97aa9b52c231f9aad5ba1403e8ed230d69f4d2a3`. 実測済み。独立reviewは未完了。CLI受理は意味保証ではない。

| Fixture | Class | Exit | Diagnostics (severity/code/line) |
| --- | --- | ---: | --- |
| recommended | recommended | 0 | none |

全診断メッセージ・入力SHA-256・コマンドは[manifest](../../../examples/ai-patterns/manifest.json)に記録。意味レビューは著者による原入力との照合（独立承認ではない）。

**出典:** [Format 1.0](../life_txt_format_spec.md) §2–3, §9, §13–14; [Profile](../../../prompts/lifetxt-assistant.md). [source 1](../../../examples/tasks_life.txt) / [source 2](../../../examples/events_life.txt) / [source 3](../../../examples/habits_reminders_life.txt) / [source 4](../../../examples/messages_life.txt) / [source 5](../../../examples/diary_life.txt) / [source 6](../../../examples/status_presence.txt)

