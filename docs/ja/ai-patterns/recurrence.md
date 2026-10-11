# AI Reference Patterns — Recurrence / 繰り返し

このページのコードはcanonical fixtureのコピー。日英で同じ原文・コードを使う。著者のCore検証と人手の意味照合を区別し、独立reviewはPRで行う。

[Format 1.0](../life_txt_format_spec.md) / [Profile](../../../prompts/lifetxt-assistant.md) / [Fixture maintenance](../../../examples/ai-patterns/README.md)

<a id="pat-rec-001"></a>

## PAT-REC-001 — daily/weekdays

**入力（原文保持）:** 2030年10月14日から平日だけ9時に朝の確認をする。

**前提:** 架空例。基準日時は2030-10-11T12:00:00+09:00、利用者TZはAsia/Tokyo。日時は明示されたものだけ使用。ID/人物/metadataは入力に指定したものだけ。例の参照recordも検査文脈として同梱し、既存recordを再追加する手順とはしない。

**理由:** weekdaysは月〜金。dailyとの違いを明示する。

**注意・反例:** 祝日カレンダーの自動除外は意味しない。offset付き繰り返しは完全なat日時で記録する。on+offset付き時刻の起点差は#1218で追跡。

**推奨例** ([canonical fixture](../../../examples/ai-patterns/PAT-REC-001/recommended.life.txt))

<!-- fixture:PAT-REC-001/recommended -->
````lifetxt
[ ] H "朝の確認" at:2030-10-14T09:00+09:00 repeat:weekdays
````

**検証:** Core 1.0.3; engine source commit `97aa9b52c231f9aad5ba1403e8ed230d69f4d2a3`. 実測済み。独立reviewは未完了。CLI受理は意味保証ではない。

| Fixture | Class | Exit | Diagnostics (severity/code/line) |
| --- | --- | ---: | --- |
| recommended | recommended | 0 | none |

固定範囲のagendaも実行（UTC）。範囲・コマンド・実出力はmanifestのagenda欄を参照。保存・展開・外部実行は別の判断。

全診断メッセージ・入力SHA-256・コマンドは[manifest](../../../examples/ai-patterns/manifest.json)に記録。意味レビューは著者による原入力との照合（独立承認ではない）。

**出典:** [Format 1.0](../life_txt_format_spec.md) §7.6, §8.1; [Profile](../../../prompts/lifetxt-assistant.md). [source 1](../../../examples/recurrence_time_life.txt) / [source 2](../../../examples/habits_reminders_life.txt)

<a id="pat-rec-002"></a>

## PAT-REC-002 — weeklyと起点

**入力（原文保持）:** 2030年10月14日（月）10時から11時の会議を毎週開催する。

**前提:** 架空例。基準日時は2030-10-11T12:00:00+09:00、利用者TZはAsia/Tokyo。日時は明示されたものだけ使用。ID/人物/metadataは入力に指定したものだけ。例の参照recordも検査文脈として同梱し、既存recordを再追加する手順とはしない。

**理由:** 開始/終了区間を起点として毎週展開する。

**注意・反例:** 希望曜日と起点日の曜日が一致するか確認する。

**推奨例** ([canonical fixture](../../../examples/ai-patterns/PAT-REC-002/recommended.life.txt))

<!-- fixture:PAT-REC-002/recommended -->
````lifetxt
[ ] E "定例会議" from:2030-10-14T10:00+09:00 to:2030-10-14T11:00+09:00 repeat:weekly
````

**検証:** Core 1.0.3; engine source commit `97aa9b52c231f9aad5ba1403e8ed230d69f4d2a3`. 実測済み。独立reviewは未完了。CLI受理は意味保証ではない。

| Fixture | Class | Exit | Diagnostics (severity/code/line) |
| --- | --- | ---: | --- |
| recommended | recommended | 0 | none |

固定範囲のagendaも実行（UTC）。範囲・コマンド・実出力はmanifestのagenda欄を参照。保存・展開・外部実行は別の判断。

全診断メッセージ・入力SHA-256・コマンドは[manifest](../../../examples/ai-patterns/manifest.json)に記録。意味レビューは著者による原入力との照合（独立承認ではない）。

**出典:** [Format 1.0](../life_txt_format_spec.md) §7.6, §8.1; [Profile](../../../prompts/lifetxt-assistant.md). [source 1](../../../examples/recurrence_time_life.txt) / [source 2](../../../examples/habits_reminders_life.txt)

<a id="pat-rec-003"></a>

## PAT-REC-003 — monthly/yearlyと暦境界

**入力（原文保持）:** 2030年1月31日9時から毎月、棚卸しをする。年次版も示す。年次版は2032年2月29日9時起点で毎年確認する。

**前提:** 架空例。基準日時は2030-10-11T12:00:00+09:00、利用者TZはAsia/Tokyo。日時は明示されたものだけ使用。ID/人物/metadataは入力に指定したものだけ。例の参照recordも検査文脈として同梱し、既存recordを再追加する手順とはしない。

**理由:** monthly/yearlyは暦に依存する。月末・閏日はCoreの展開結果を確認する。実測では月次が1/31→2/28→3/28、年次が2032/2/29→2033/2/28→2036/2/28。元の月末/閏日へ戻るとは保証しない。

**注意・反例:** 31日を持たない月の処理を自然言語だけで推測しない。offset付き繰り返しは完全なat日時で記録する。on+offset付き時刻の起点差は#1218で追跡。

**推奨例** ([canonical fixture](../../../examples/ai-patterns/PAT-REC-003/recommended.life.txt))

<!-- fixture:PAT-REC-003/recommended -->
````lifetxt
[ ] T "棚卸しをする" do:2030-01-31T09:00+09:00 repeat:monthly
````

**yearly** ([canonical fixture](../../../examples/ai-patterns/PAT-REC-003/yearly.life.txt))

<!-- fixture:PAT-REC-003/yearly -->
````lifetxt
[ ] H "年次確認" at:2032-02-29T09:00+09:00 repeat:yearly
````

**検証:** Core 1.0.3; engine source commit `97aa9b52c231f9aad5ba1403e8ed230d69f4d2a3`. 実測済み。独立reviewは未完了。CLI受理は意味保証ではない。

| Fixture | Class | Exit | Diagnostics (severity/code/line) |
| --- | --- | ---: | --- |
| recommended | recommended | 0 | none |
| yearly | recommended | 0 | none |

固定範囲のagendaも実行（UTC）。範囲・コマンド・実出力はmanifestのagenda欄を参照。保存・展開・外部実行は別の判断。

全診断メッセージ・入力SHA-256・コマンドは[manifest](../../../examples/ai-patterns/manifest.json)に記録。意味レビューは著者による原入力との照合（独立承認ではない）。

**出典:** [Format 1.0](../life_txt_format_spec.md) §7.6, §8.1; [Profile](../../../prompts/lifetxt-assistant.md). [source 1](../../../examples/recurrence_time_life.txt) / [source 2](../../../examples/habits_reminders_life.txt)

<a id="pat-rec-004"></a>

## PAT-REC-004 — interval

**入力（原文保持）:** 2030年10月14日から2週間ごとに振り返る。

**前提:** 架空例。基準日時は2030-10-11T12:00:00+09:00、利用者TZはAsia/Tokyo。日時は明示されたものだけ使用。ID/人物/metadataは入力に指定したものだけ。例の参照recordも検査文脈として同梱し、既存recordを再追加する手順とはしない。

**理由:** interval:2はrepeatの単位で2週間ごと。

**注意・反例:** count:2は回数上限であり間隔ではない。

**推奨例** ([canonical fixture](../../../examples/ai-patterns/PAT-REC-004/recommended.life.txt))

<!-- fixture:PAT-REC-004/recommended -->
````lifetxt
[ ] H "振り返る" on:2030-10-14 repeat:weekly interval:2
````

**検証:** Core 1.0.3; engine source commit `97aa9b52c231f9aad5ba1403e8ed230d69f4d2a3`. 実測済み。独立reviewは未完了。CLI受理は意味保証ではない。

| Fixture | Class | Exit | Diagnostics (severity/code/line) |
| --- | --- | ---: | --- |
| recommended | recommended | 0 | none |

固定範囲のagendaも実行（UTC）。範囲・コマンド・実出力はmanifestのagenda欄を参照。保存・展開・外部実行は別の判断。

全診断メッセージ・入力SHA-256・コマンドは[manifest](../../../examples/ai-patterns/manifest.json)に記録。意味レビューは著者による原入力との照合（独立承認ではない）。

**出典:** [Format 1.0](../life_txt_format_spec.md) §7.6, §8.1; [Profile](../../../prompts/lifetxt-assistant.md). [source 1](../../../examples/recurrence_time_life.txt) / [source 2](../../../examples/habits_reminders_life.txt)

<a id="pat-rec-005"></a>

## PAT-REC-005 — count/untilの終端

**入力（原文保持）:** 2030年10月14日から毎日、最大3回、10月16日まで測定する。

**前提:** 架空例。基準日時は2030-10-11T12:00:00+09:00、利用者TZはAsia/Tokyo。日時は明示されたものだけ使用。ID/人物/metadataは入力に指定したものだけ。例の参照recordも検査文脈として同梱し、既存recordを再追加する手順とはしない。

**理由:** countは起点からの回数、untilは包含する終端。両制約を確認する。

**注意・反例:** 検索範囲の終端とuntilの意味を混同しない。

**推奨例** ([canonical fixture](../../../examples/ai-patterns/PAT-REC-005/recommended.life.txt))

<!-- fixture:PAT-REC-005/recommended -->
````lifetxt
[ ] H "測定する" on:2030-10-14 repeat:daily count:3 until:2030-10-16
````

**検証:** Core 1.0.3; engine source commit `97aa9b52c231f9aad5ba1403e8ed230d69f4d2a3`. 実測済み。独立reviewは未完了。CLI受理は意味保証ではない。

| Fixture | Class | Exit | Diagnostics (severity/code/line) |
| --- | --- | ---: | --- |
| recommended | recommended | 0 | none |

固定範囲のagendaも実行（UTC）。範囲・コマンド・実出力はmanifestのagenda欄を参照。保存・展開・外部実行は別の判断。

全診断メッセージ・入力SHA-256・コマンドは[manifest](../../../examples/ai-patterns/manifest.json)に記録。意味レビューは著者による原入力との照合（独立承認ではない）。

**出典:** [Format 1.0](../life_txt_format_spec.md) §7.6, §8.1; [Profile](../../../prompts/lifetxt-assistant.md). [source 1](../../../examples/recurrence_time_life.txt) / [source 2](../../../examples/habits_reminders_life.txt)

<a id="pat-rec-006"></a>

## PAT-REC-006 — RRULEのdaily/weekly BYDAY

**入力（原文保持）:** 2030年10月14日から月曜と水曜の7時に学習する。最大6回。

**前提:** 架空例。基準日時は2030-10-11T12:00:00+09:00、利用者TZはAsia/Tokyo。日時は明示されたものだけ使用。ID/人物/metadataは入力に指定したものだけ。例の参照recordも検査文脈として同梱し、既存recordを再追加する手順とはしない。

**理由:** dependency-free subsetでweekly BYDAYを使う。daily BYDAYもsubset対象。

**注意・反例:** RRULE全体が実装済みという意味ではない。offset付き繰り返しは完全なat日時で記録する。on+offset付き時刻の起点差は#1218で追跡。このRRULE実測ではagendaの展開時刻からoffsetが落ちた。保存された元値とは別に、実時刻比較の忠実性は#1218で確認する。

**推奨例** ([canonical fixture](../../../examples/ai-patterns/PAT-REC-006/recommended.life.txt))

<!-- fixture:PAT-REC-006/recommended -->
````lifetxt
[ ] H "学習する" at:2030-10-14T07:00+09:00 repeat:RRULE:FREQ=WEEKLY;BYDAY=MO,WE;COUNT=6
````

**検証:** Core 1.0.3; engine source commit `97aa9b52c231f9aad5ba1403e8ed230d69f4d2a3`. 実測済み。独立reviewは未完了。CLI受理は意味保証ではない。

| Fixture | Class | Exit | Diagnostics (severity/code/line) |
| --- | --- | ---: | --- |
| recommended | recommended | 0 | none |

固定範囲のagendaも実行（UTC）。範囲・コマンド・実出力はmanifestのagenda欄を参照。保存・展開・外部実行は別の判断。

全診断メッセージ・入力SHA-256・コマンドは[manifest](../../../examples/ai-patterns/manifest.json)に記録。意味レビューは著者による原入力との照合（独立承認ではない）。

**出典:** [Format 1.0](../life_txt_format_spec.md) §7.6, §8.1; [Profile](../../../prompts/lifetxt-assistant.md). [source 1](../../../examples/recurrence_time_life.txt) / [source 2](../../../examples/habits_reminders_life.txt)

<a id="pat-rec-007"></a>

## PAT-REC-007 — 未対応RRULE・例外日の保持と非展開

**入力（原文保持）:** 毎月第2月曜を外部RRULE（FREQ=MONTHLY;BYDAY=MO;BYSETPOS=2）から記録する。起点2030年10月14日。11月11日は休みとだけメモする。

**前提:** 架空例。基準日時は2030-10-11T12:00:00+09:00、利用者TZはAsia/Tokyo。日時は明示されたものだけ使用。ID/人物/metadataは入力に指定したものだけ。例の参照recordも検査文脈として同梱し、既存recordを再追加する手順とはしない。

**理由:** BYSETPOSは現Core対象外でW223。保存はできても展開結果は空。この例は記録用途の境界例で、実行可能な定例予定とは扱わない。

**注意・反例:** noteの休み指定は自動的な繰り返し例外ではない。現在Coreのordinal BYDAY/BYMONTHDAY/BYMONTH/WKSTも、仕様の狭いsubset説明とのずれとして#1217で追跡。

**推奨例** ([canonical fixture](../../../examples/ai-patterns/PAT-REC-007/recommended.life.txt))

<!-- fixture:PAT-REC-007/recommended -->
````lifetxt
[ ] E "外部の定例予定" on:2030-10-14 repeat:RRULE:FREQ=MONTHLY;BYDAY=MO;BYSETPOS=2 note:"2030-11-11は休み（例外自動展開は未設定）"
````

**検証:** Core 1.0.3; engine source commit `97aa9b52c231f9aad5ba1403e8ed230d69f4d2a3`. 実測済み。独立reviewは未完了。CLI受理は意味保証ではない。

| Fixture | Class | Exit | Diagnostics (severity/code/line) |
| --- | --- | ---: | --- |
| recommended | recommended | 0 | warning/W223/L1 |

固定範囲のagendaも実行（UTC）。範囲・コマンド・実出力はmanifestのagenda欄を参照。保存・展開・外部実行は別の判断。

全診断メッセージ・入力SHA-256・コマンドは[manifest](../../../examples/ai-patterns/manifest.json)に記録。意味レビューは著者による原入力との照合（独立承認ではない）。

**出典:** [Format 1.0](../life_txt_format_spec.md) §7.6, §8.1; [Profile](../../../prompts/lifetxt-assistant.md). [source 1](../../../examples/recurrence_time_life.txt) / [source 2](../../../examples/habits_reminders_life.txt)

<a id="pat-rec-008"></a>

## PAT-REC-008 — 日付起点なしatと有界範囲

**入力（原文保持）:** 起点日は未定だが毎日18時にストレッチする。

**前提:** 架空例。基準日時は2030-10-11T12:00:00+09:00、利用者TZはAsia/Tokyo。日時は明示されたものだけ使用。ID/人物/metadataは入力に指定したものだけ。例の参照recordも検査文脈として同梱し、既存recordを再追加する手順とはしない。

**理由:** 起点なしatは浮動時刻で、有界範囲のみで展開する。

**注意・反例:** 片側だけの時間フィルタでは安定した起点がないため除外される。

**推奨例** ([canonical fixture](../../../examples/ai-patterns/PAT-REC-008/recommended.life.txt))

<!-- fixture:PAT-REC-008/recommended -->
````lifetxt
[ ] H "ストレッチする" at:18:00+09:00 repeat:daily
````

**検証:** Core 1.0.3; engine source commit `97aa9b52c231f9aad5ba1403e8ed230d69f4d2a3`. 実測済み。独立reviewは未完了。CLI受理は意味保証ではない。

| Fixture | Class | Exit | Diagnostics (severity/code/line) |
| --- | --- | ---: | --- |
| recommended | recommended | 0 | none |

固定範囲のagendaも実行（UTC）。範囲・コマンド・実出力はmanifestのagenda欄を参照。保存・展開・外部実行は別の判断。

全診断メッセージ・入力SHA-256・コマンドは[manifest](../../../examples/ai-patterns/manifest.json)に記録。意味レビューは著者による原入力との照合（独立承認ではない）。

**出典:** [Format 1.0](../life_txt_format_spec.md) §7.6, §8.1; [Profile](../../../prompts/lifetxt-assistant.md). [source 1](../../../examples/recurrence_time_life.txt) / [source 2](../../../examples/habits_reminders_life.txt)

