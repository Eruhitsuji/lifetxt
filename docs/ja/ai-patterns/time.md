# AI Reference Patterns — Time / 日時

このページのコードはcanonical fixtureのコピー。日英で同じ原文・コードを使う。著者のCore検証と人手の意味照合を区別し、独立reviewはPRで行う。

[Format 1.0](../life_txt_format_spec.md) / [Profile](../../../prompts/lifetxt-assistant.md) / [Fixture maintenance](../../../examples/ai-patterns/README.md)

<a id="pat-time-001"></a>

## PAT-TIME-001 — doの実行予定

**入力（原文保持）:** 2030年10月14日に草案を書く。締切は指定しない。

**前提:** 架空例。基準日時は2030-10-11T12:00:00+09:00、利用者TZはAsia/Tokyo。日時は明示されたものだけ使用。ID/人物/metadataは入力に指定したものだけ。例の参照recordも検査文脈として同梱し、既存recordを再追加する手順とはしない。

**理由:** 実行予定日にはdoを使う。

**注意・反例:** dueならその日までに終えるという別の意味になる。

反例分類: **C (wrong source meaning)**。意味/能力は人が原文と照合する。

**推奨例** ([canonical fixture](../../../examples/ai-patterns/PAT-TIME-001/recommended.life.txt))

<!-- fixture:PAT-TIME-001/recommended -->
````lifetxt
[ ] T "草案を書く" do:2030-10-14
````

**counterexample** ([canonical fixture](../../../examples/ai-patterns/PAT-TIME-001/counterexample.life.txt))

<!-- fixture:PAT-TIME-001/counterexample -->
````lifetxt
[ ] T "草案を書く" due:2030-10-14
````

**検証:** Core 1.0.3; engine source commit `97aa9b52c231f9aad5ba1403e8ed230d69f4d2a3`. 実測済み。独立reviewは未完了。CLI受理は意味保証ではない。

| Fixture | Class | Exit | Diagnostics (severity/code/line) |
| --- | --- | ---: | --- |
| recommended | recommended | 0 | none |
| counterexample | C | 0 | none |

全診断メッセージ・入力SHA-256・コマンドは[manifest](../../../examples/ai-patterns/manifest.json)に記録。意味レビューは著者による原入力との照合（独立承認ではない）。

**出典:** [Format 1.0](../life_txt_format_spec.md) §7.4, §8, §9.8–9.9; [Profile](../../../prompts/lifetxt-assistant.md). [source 1](../../../examples/recurrence_time_life.txt) / [source 2](../../../examples/messages_life.txt) / [source 3](../../../examples/lifetxt_ai_prompt_conformance.json)

<a id="pat-time-002"></a>

## PAT-TIME-002 — dueの期限

**入力（原文保持）:** 草案は2030年10月20日17時までに完成させる。

**前提:** 架空例。基準日時は2030-10-11T12:00:00+09:00、利用者TZはAsia/Tokyo。日時は明示されたものだけ使用。ID/人物/metadataは入力に指定したものだけ。例の参照recordも検査文脈として同梱し、既存recordを再追加する手順とはしない。

**理由:** 期限の日時にはdueを使い、実行予定日は別途指定がなければ書かない。

**注意・反例:** doとdueの両方を自動で同じ値にしない。

**推奨例** ([canonical fixture](../../../examples/ai-patterns/PAT-TIME-002/recommended.life.txt))

<!-- fixture:PAT-TIME-002/recommended -->
````lifetxt
[ ] T "草案を完成させる" due:2030-10-20T17:00+09:00
````

**検証:** Core 1.0.3; engine source commit `97aa9b52c231f9aad5ba1403e8ed230d69f4d2a3`. 実測済み。独立reviewは未完了。CLI受理は意味保証ではない。

| Fixture | Class | Exit | Diagnostics (severity/code/line) |
| --- | --- | ---: | --- |
| recommended | recommended | 0 | none |

全診断メッセージ・入力SHA-256・コマンドは[manifest](../../../examples/ai-patterns/manifest.json)に記録。意味レビューは著者による原入力との照合（独立承認ではない）。

**出典:** [Format 1.0](../life_txt_format_spec.md) §7.4, §8, §9.8–9.9; [Profile](../../../prompts/lifetxt-assistant.md). [source 1](../../../examples/recurrence_time_life.txt) / [source 2](../../../examples/messages_life.txt) / [source 3](../../../examples/lifetxt_ai_prompt_conformance.json)

<a id="pat-time-003"></a>

## PAT-TIME-003 — onの終日予定

**入力（原文保持）:** 2030年10月20日は終日、展示会に参加する。

**前提:** 架空例。基準日時は2030-10-11T12:00:00+09:00、利用者TZはAsia/Tokyo。日時は明示されたものだけ使用。ID/人物/metadataは入力に指定したものだけ。例の参照recordも検査文脈として同梱し、既存recordを再追加する手順とはしない。

**理由:** 終日の日付はon。開始/終了時刻を捏造しない。

**注意・反例:** from/toは日時区間なので日付だけの候補一覧には使わない。

**推奨例** ([canonical fixture](../../../examples/ai-patterns/PAT-TIME-003/recommended.life.txt))

<!-- fixture:PAT-TIME-003/recommended -->
````lifetxt
[ ] E "展示会" on:2030-10-20
````

**検証:** Core 1.0.3; engine source commit `97aa9b52c231f9aad5ba1403e8ed230d69f4d2a3`. 実測済み。独立reviewは未完了。CLI受理は意味保証ではない。

| Fixture | Class | Exit | Diagnostics (severity/code/line) |
| --- | --- | ---: | --- |
| recommended | recommended | 0 | none |

全診断メッセージ・入力SHA-256・コマンドは[manifest](../../../examples/ai-patterns/manifest.json)に記録。意味レビューは著者による原入力との照合（独立承認ではない）。

**出典:** [Format 1.0](../life_txt_format_spec.md) §7.4, §8, §9.8–9.9; [Profile](../../../prompts/lifetxt-assistant.md). [source 1](../../../examples/recurrence_time_life.txt) / [source 2](../../../examples/messages_life.txt) / [source 3](../../../examples/lifetxt_ai_prompt_conformance.json)

<a id="pat-time-004"></a>

## PAT-TIME-004 — atの単独日時とon+時刻

**入力（原文保持）:** 2030年10月14日の18時に図書を返却することを思い出す。

**前提:** 架空例。基準日時は2030-10-11T12:00:00+09:00、利用者TZはAsia/Tokyo。日時は明示されたものだけ使用。ID/人物/metadataは入力に指定したものだけ。例の参照recordも検査文脈として同梱し、既存recordを再追加する手順とはしない。

**理由:** onで日付、atで時刻を分けて保持する。単一のat日時でも同じ意図を表せる。

**注意・反例:** at:18:00だけにすると日付文脈が失われる。

**推奨例** ([canonical fixture](../../../examples/ai-patterns/PAT-TIME-004/recommended.life.txt))

<!-- fixture:PAT-TIME-004/recommended -->
````lifetxt
[ ] R "図書返却を思い出す" on:2030-10-14 at:18:00+09:00
````

**検証:** Core 1.0.3; engine source commit `97aa9b52c231f9aad5ba1403e8ed230d69f4d2a3`. 実測済み。独立reviewは未完了。CLI受理は意味保証ではない。

| Fixture | Class | Exit | Diagnostics (severity/code/line) |
| --- | --- | ---: | --- |
| recommended | recommended | 0 | none |

全診断メッセージ・入力SHA-256・コマンドは[manifest](../../../examples/ai-patterns/manifest.json)に記録。意味レビューは著者による原入力との照合（独立承認ではない）。

**出典:** [Format 1.0](../life_txt_format_spec.md) §7.4, §8, §9.8–9.9; [Profile](../../../prompts/lifetxt-assistant.md). [source 1](../../../examples/recurrence_time_life.txt) / [source 2](../../../examples/messages_life.txt) / [source 3](../../../examples/lifetxt_ai_prompt_conformance.json)

<a id="pat-time-005"></a>

## PAT-TIME-005 — from/toの区間

**入力（原文保持）:** 2030年10月14日14時から15時30分まで研究会。

**前提:** 架空例。基準日時は2030-10-11T12:00:00+09:00、利用者TZはAsia/Tokyo。日時は明示されたものだけ使用。ID/人物/metadataは入力に指定したものだけ。例の参照recordも検査文脈として同梱し、既存recordを再追加する手順とはしない。

**理由:** 同一出来事の開始と終了をfrom/toにする。

**注意・反例:** 排他的候補を区間に変えるのは意味ミス。

**推奨例** ([canonical fixture](../../../examples/ai-patterns/PAT-TIME-005/recommended.life.txt))

<!-- fixture:PAT-TIME-005/recommended -->
````lifetxt
[ ] E "研究会" from:2030-10-14T14:00+09:00 to:2030-10-14T15:30+09:00
````

**検証:** Core 1.0.3; engine source commit `97aa9b52c231f9aad5ba1403e8ed230d69f4d2a3`. 実測済み。独立reviewは未完了。CLI受理は意味保証ではない。

| Fixture | Class | Exit | Diagnostics (severity/code/line) |
| --- | --- | ---: | --- |
| recommended | recommended | 0 | none |

全診断メッセージ・入力SHA-256・コマンドは[manifest](../../../examples/ai-patterns/manifest.json)に記録。意味レビューは著者による原入力との照合（独立承認ではない）。

**出典:** [Format 1.0](../life_txt_format_spec.md) §7.4, §8, §9.8–9.9; [Profile](../../../prompts/lifetxt-assistant.md). [source 1](../../../examples/recurrence_time_life.txt) / [source 2](../../../examples/messages_life.txt) / [source 3](../../../examples/lifetxt_ai_prompt_conformance.json)

<a id="pat-time-006"></a>

## PAT-TIME-006 — doneの完了日時

**入力（原文保持）:** 資料提出は2030年10月14日16時に完了。

**前提:** 架空例。基準日時は2030-10-11T12:00:00+09:00、利用者TZはAsia/Tokyo。日時は明示されたものだけ使用。ID/人物/metadataは入力に指定したものだけ。例の参照recordも検査文脈として同梱し、既存recordを再追加する手順とはしない。

**理由:** 既知の実績日時はdone。dueとは異なる。

**注意・反例:** 締切が不明なら完了日時をdueとして追加しない。

**推奨例** ([canonical fixture](../../../examples/ai-patterns/PAT-TIME-006/recommended.life.txt))

<!-- fixture:PAT-TIME-006/recommended -->
````lifetxt
[x] T "資料を提出する" done:2030-10-14T16:00+09:00
````

**検証:** Core 1.0.3; engine source commit `97aa9b52c231f9aad5ba1403e8ed230d69f4d2a3`. 実測済み。独立reviewは未完了。CLI受理は意味保証ではない。

| Fixture | Class | Exit | Diagnostics (severity/code/line) |
| --- | --- | ---: | --- |
| recommended | recommended | 0 | none |

全診断メッセージ・入力SHA-256・コマンドは[manifest](../../../examples/ai-patterns/manifest.json)に記録。意味レビューは著者による原入力との照合（独立承認ではない）。

**出典:** [Format 1.0](../life_txt_format_spec.md) §7.4, §8, §9.8–9.9; [Profile](../../../prompts/lifetxt-assistant.md). [source 1](../../../examples/recurrence_time_life.txt) / [source 2](../../../examples/messages_life.txt) / [source 3](../../../examples/lifetxt_ai_prompt_conformance.json)

<a id="pat-time-007"></a>

## PAT-TIME-007 — offsetとUTC

**入力（原文保持）:** 2030年10月14日、日本時間9時から10時までのオンライン会議。

**前提:** 架空例。基準日時は2030-10-11T12:00:00+09:00、利用者TZはAsia/Tokyo。日時は明示されたものだけ使用。ID/人物/metadataは入力に指定したものだけ。例の参照recordも検査文脈として同梱し、既存recordを再追加する手順とはしない。

**理由:** 入力で与えられた+09:00の9時はUTCの0時。オフセットなし時刻へ落とさない。

**注意・反例:** Zは日本時間を意味しない。

**推奨例** ([canonical fixture](../../../examples/ai-patterns/PAT-TIME-007/recommended.life.txt))

<!-- fixture:PAT-TIME-007/recommended -->
````lifetxt
[ ] E "オンライン会議" from:2030-10-14T00:00Z to:2030-10-14T01:00Z
````

**検証:** Core 1.0.3; engine source commit `97aa9b52c231f9aad5ba1403e8ed230d69f4d2a3`. 実測済み。独立reviewは未完了。CLI受理は意味保証ではない。

| Fixture | Class | Exit | Diagnostics (severity/code/line) |
| --- | --- | ---: | --- |
| recommended | recommended | 0 | none |

全診断メッセージ・入力SHA-256・コマンドは[manifest](../../../examples/ai-patterns/manifest.json)に記録。意味レビューは著者による原入力との照合（独立承認ではない）。

**出典:** [Format 1.0](../life_txt_format_spec.md) §7.4, §8, §9.8–9.9; [Profile](../../../prompts/lifetxt-assistant.md). [source 1](../../../examples/recurrence_time_life.txt) / [source 2](../../../examples/messages_life.txt) / [source 3](../../../examples/lifetxt_ai_prompt_conformance.json)

<a id="pat-time-008"></a>

## PAT-TIME-008 — 秒・小数秒・時刻のみ

**入力（原文保持）:** 毎日18時00分30.5秒（+09:00）に測定する習慣。

**前提:** 架空例。基準日時は2030-10-11T12:00:00+09:00、利用者TZはAsia/Tokyo。日時は明示されたものだけ使用。ID/人物/metadataは入力に指定したものだけ。例の参照recordも検査文脈として同梱し、既存recordを再追加する手順とはしない。

**理由:** 秒・小数秒・時刻オフセットを保持する。起点なしであり有界範囲内だけ展開する。

**注意・反例:** 小数秒は最大6桁。検証成功だけでは通知実行を意味しない。

**推奨例** ([canonical fixture](../../../examples/ai-patterns/PAT-TIME-008/recommended.life.txt))

<!-- fixture:PAT-TIME-008/recommended -->
````lifetxt
[ ] H "測定する" repeat:daily at:18:00:30.5+09:00
````

**検証:** Core 1.0.3; engine source commit `97aa9b52c231f9aad5ba1403e8ed230d69f4d2a3`. 実測済み。独立reviewは未完了。CLI受理は意味保証ではない。

| Fixture | Class | Exit | Diagnostics (severity/code/line) |
| --- | --- | ---: | --- |
| recommended | recommended | 0 | none |

全診断メッセージ・入力SHA-256・コマンドは[manifest](../../../examples/ai-patterns/manifest.json)に記録。意味レビューは著者による原入力との照合（独立承認ではない）。

**出典:** [Format 1.0](../life_txt_format_spec.md) §7.4, §8, §9.8–9.9; [Profile](../../../prompts/lifetxt-assistant.md). [source 1](../../../examples/recurrence_time_life.txt) / [source 2](../../../examples/messages_life.txt) / [source 3](../../../examples/lifetxt_ai_prompt_conformance.json)

<a id="pat-time-009"></a>

## PAT-TIME-009 — 基準日時付き相対日付と欠測時

**入力（原文保持）:** 明日、残高を確認する。

**前提:** 架空例。基準日時は2030-10-11T12:00:00+09:00、利用者TZはAsia/Tokyo。日時は明示されたものだけ使用。ID/人物/metadataは入力に指定したものだけ。例の参照recordも検査文脈として同梱し、既存recordを再追加する手順とはしない。

**理由:** この例の基準は2030-10-11/Asia/Tokyoなので明日は10月12日。基準不明なら質問する。

**注意・反例:** 例示日を実際の会話の現在日と取り違えない。

**推奨例** ([canonical fixture](../../../examples/ai-patterns/PAT-TIME-009/recommended.life.txt))

<!-- fixture:PAT-TIME-009/recommended -->
````lifetxt
[ ] T "残高を確認する" do:2030-10-12
````

**検証:** Core 1.0.3; engine source commit `97aa9b52c231f9aad5ba1403e8ed230d69f4d2a3`. 実測済み。独立reviewは未完了。CLI受理は意味保証ではない。

| Fixture | Class | Exit | Diagnostics (severity/code/line) |
| --- | --- | ---: | --- |
| recommended | recommended | 0 | none |

全診断メッセージ・入力SHA-256・コマンドは[manifest](../../../examples/ai-patterns/manifest.json)に記録。意味レビューは著者による原入力との照合（独立承認ではない）。

**出典:** [Format 1.0](../life_txt_format_spec.md) §7.4, §8, §9.8–9.9; [Profile](../../../prompts/lifetxt-assistant.md). [source 1](../../../examples/recurrence_time_life.txt) / [source 2](../../../examples/messages_life.txt) / [source 3](../../../examples/lifetxt_ai_prompt_conformance.json)

<a id="pat-time-010"></a>

## PAT-TIME-010 — notify_at/from/to・ack・snooze_until

**入力（原文保持）:** 自分からaliceへの確認依頼。通知期間は2030年10月14日9時〜17時。9時5分に確認済み、9時30分まで通知抑制。

**前提:** 架空例。基準日時は2030-10-11T12:00:00+09:00、利用者TZはAsia/Tokyo。日時は明示されたものだけ使用。ID/人物/metadataは入力に指定したものだけ。例の参照recordも検査文脈として同梱し、既存recordを再追加する手順とはしない。

**理由:** 通知期間・確認時刻・抑制終了をそれぞれのkeyに保存する。ackはTask完了とは異なる。

**注意・反例:** 期間保存だけで通知経路や配信を設定したことにはならない。

**推奨例** ([canonical fixture](../../../examples/ai-patterns/PAT-TIME-010/recommended.life.txt))

<!-- fixture:PAT-TIME-010/recommended -->
````lifetxt
[ ] M "確認依頼" sender:self recipient:alice notify_from:2030-10-14T09:00+09:00 notify_to:2030-10-14T17:00+09:00 ack:2030-10-14T09:05+09:00 snooze_until:2030-10-14T09:30+09:00
````

**検証:** Core 1.0.3; engine source commit `97aa9b52c231f9aad5ba1403e8ed230d69f4d2a3`. 実測済み。独立reviewは未完了。CLI受理は意味保証ではない。

| Fixture | Class | Exit | Diagnostics (severity/code/line) |
| --- | --- | ---: | --- |
| recommended | recommended | 0 | none |

全診断メッセージ・入力SHA-256・コマンドは[manifest](../../../examples/ai-patterns/manifest.json)に記録。意味レビューは著者による原入力との照合（独立承認ではない）。

**出典:** [Format 1.0](../life_txt_format_spec.md) §7.4, §8, §9.8–9.9; [Profile](../../../prompts/lifetxt-assistant.md). [source 1](../../../examples/recurrence_time_life.txt) / [source 2](../../../examples/messages_life.txt) / [source 3](../../../examples/lifetxt_ai_prompt_conformance.json)

