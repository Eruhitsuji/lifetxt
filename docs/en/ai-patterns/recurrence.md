# AI Reference Patterns — Recurrence / 繰り返し

Code blocks copy canonical fixtures. Both languages retain identical source input and code. Author-run Core checks are separate from meaning comparison; independent review takes place on the PR.

[Format 1.0](../life_txt_format_spec.md) / [Profile](../../../prompts/lifetxt-assistant.md) / [Fixture maintenance](../../../examples/ai-patterns/README.md)

<a id="pat-rec-001"></a>

## PAT-REC-001 — daily/weekdays

**Input (original language retained):** 2030年10月14日から平日だけ9時に朝の確認をする。

**Context:** Fictional example. Fixed baseline: 2030-10-11T12:00:00+09:00; user timezone: Asia/Tokyo. Use only supplied dates, IDs, people, and metadata. Referenced existing records are included for independent validation, not to be appended again to a live workspace.

**Reason:** weekdays selects Monday through Friday rather than every day.

**Pitfall:** This does not automatically exclude public holidays. Use full at datetimes for offset-aware recurrence; #1218 tracks the split on/offset-time anchor discrepancy.

**Recommended** ([canonical fixture](../../../examples/ai-patterns/PAT-REC-001/recommended.life.txt))

<!-- fixture:PAT-REC-001/recommended -->
````lifetxt
[ ] H "朝の確認" at:2030-10-14T09:00+09:00 repeat:weekdays
````

**Validation:** Core 1.0.3; engine source commit `97aa9b52c231f9aad5ba1403e8ed230d69f4d2a3`. Executed; independent review pending. CLI acceptance is not semantic proof.

| Fixture | Class | Exit | Diagnostics (severity/code/line) |
| --- | --- | ---: | --- |
| recommended | recommended | 0 | none |

Fixed-range agenda also executed in UTC; see each manifest agenda field for range, command, and actual output. Storage, expansion, and external execution are separate judgments.

Full diagnostic messages, input SHA-256, and commands are in the [manifest](../../../examples/ai-patterns/manifest.json). Meaning review is the author's source comparison, not independent approval.

**Sources:** [Format 1.0](../life_txt_format_spec.md) §7.6, §8.1; [Profile](../../../prompts/lifetxt-assistant.md). [source 1](../../../examples/recurrence_time_life.txt) / [source 2](../../../examples/habits_reminders_life.txt)

<a id="pat-rec-002"></a>

## PAT-REC-002 — weeklyと起点

**Input (original language retained):** 2030年10月14日（月）10時から11時の会議を毎週開催する。

**Context:** Fictional example. Fixed baseline: 2030-10-11T12:00:00+09:00; user timezone: Asia/Tokyo. Use only supplied dates, IDs, people, and metadata. Referenced existing records are included for independent validation, not to be appended again to a live workspace.

**Reason:** The timed interval anchors weekly expansion.

**Pitfall:** Check that the anchor weekday matches the source request.

**Recommended** ([canonical fixture](../../../examples/ai-patterns/PAT-REC-002/recommended.life.txt))

<!-- fixture:PAT-REC-002/recommended -->
````lifetxt
[ ] E "定例会議" from:2030-10-14T10:00+09:00 to:2030-10-14T11:00+09:00 repeat:weekly
````

**Validation:** Core 1.0.3; engine source commit `97aa9b52c231f9aad5ba1403e8ed230d69f4d2a3`. Executed; independent review pending. CLI acceptance is not semantic proof.

| Fixture | Class | Exit | Diagnostics (severity/code/line) |
| --- | --- | ---: | --- |
| recommended | recommended | 0 | none |

Fixed-range agenda also executed in UTC; see each manifest agenda field for range, command, and actual output. Storage, expansion, and external execution are separate judgments.

Full diagnostic messages, input SHA-256, and commands are in the [manifest](../../../examples/ai-patterns/manifest.json). Meaning review is the author's source comparison, not independent approval.

**Sources:** [Format 1.0](../life_txt_format_spec.md) §7.6, §8.1; [Profile](../../../prompts/lifetxt-assistant.md). [source 1](../../../examples/recurrence_time_life.txt) / [source 2](../../../examples/habits_reminders_life.txt)

<a id="pat-rec-003"></a>

## PAT-REC-003 — monthly/yearlyと暦境界

**Input (original language retained):** 2030年1月31日9時から毎月、棚卸しをする。年次版も示す。年次版は2032年2月29日9時起点で毎年確認する。

**Context:** Fictional example. Fixed baseline: 2030-10-11T12:00:00+09:00; user timezone: Asia/Tokyo. Use only supplied dates, IDs, people, and metadata. Referenced existing records are included for independent validation, not to be appended again to a live workspace.

**Reason:** Monthly and yearly rules depend on the calendar; verify month-end and leap-day expansion with Core. Observed monthly dates are Jan 31 → Feb 28 → Mar 28; yearly Feb 29, 2032 clamps to Feb 28 in 2033 and remains Feb 28 in 2036. Returning to the original month-end/leap-day is not guaranteed.

**Pitfall:** Do not guess how a month without day 31 is handled. Use full at datetimes for offset-aware recurrence; #1218 tracks the split on/offset-time anchor discrepancy.

**Recommended** ([canonical fixture](../../../examples/ai-patterns/PAT-REC-003/recommended.life.txt))

<!-- fixture:PAT-REC-003/recommended -->
````lifetxt
[ ] T "棚卸しをする" do:2030-01-31T09:00+09:00 repeat:monthly
````

**yearly** ([canonical fixture](../../../examples/ai-patterns/PAT-REC-003/yearly.life.txt))

<!-- fixture:PAT-REC-003/yearly -->
````lifetxt
[ ] H "年次確認" at:2032-02-29T09:00+09:00 repeat:yearly
````

**Validation:** Core 1.0.3; engine source commit `97aa9b52c231f9aad5ba1403e8ed230d69f4d2a3`. Executed; independent review pending. CLI acceptance is not semantic proof.

| Fixture | Class | Exit | Diagnostics (severity/code/line) |
| --- | --- | ---: | --- |
| recommended | recommended | 0 | none |
| yearly | recommended | 0 | none |

Fixed-range agenda also executed in UTC; see each manifest agenda field for range, command, and actual output. Storage, expansion, and external execution are separate judgments.

Full diagnostic messages, input SHA-256, and commands are in the [manifest](../../../examples/ai-patterns/manifest.json). Meaning review is the author's source comparison, not independent approval.

**Sources:** [Format 1.0](../life_txt_format_spec.md) §7.6, §8.1; [Profile](../../../prompts/lifetxt-assistant.md). [source 1](../../../examples/recurrence_time_life.txt) / [source 2](../../../examples/habits_reminders_life.txt)

<a id="pat-rec-004"></a>

## PAT-REC-004 — interval

**Input (original language retained):** 2030年10月14日から2週間ごとに振り返る。

**Context:** Fictional example. Fixed baseline: 2030-10-11T12:00:00+09:00; user timezone: Asia/Tokyo. Use only supplied dates, IDs, people, and metadata. Referenced existing records are included for independent validation, not to be appended again to a live workspace.

**Reason:** interval:2 means every two units of the selected weekly rule.

**Pitfall:** count:2 limits occurrences rather than setting the interval.

**Recommended** ([canonical fixture](../../../examples/ai-patterns/PAT-REC-004/recommended.life.txt))

<!-- fixture:PAT-REC-004/recommended -->
````lifetxt
[ ] H "振り返る" on:2030-10-14 repeat:weekly interval:2
````

**Validation:** Core 1.0.3; engine source commit `97aa9b52c231f9aad5ba1403e8ed230d69f4d2a3`. Executed; independent review pending. CLI acceptance is not semantic proof.

| Fixture | Class | Exit | Diagnostics (severity/code/line) |
| --- | --- | ---: | --- |
| recommended | recommended | 0 | none |

Fixed-range agenda also executed in UTC; see each manifest agenda field for range, command, and actual output. Storage, expansion, and external execution are separate judgments.

Full diagnostic messages, input SHA-256, and commands are in the [manifest](../../../examples/ai-patterns/manifest.json). Meaning review is the author's source comparison, not independent approval.

**Sources:** [Format 1.0](../life_txt_format_spec.md) §7.6, §8.1; [Profile](../../../prompts/lifetxt-assistant.md). [source 1](../../../examples/recurrence_time_life.txt) / [source 2](../../../examples/habits_reminders_life.txt)

<a id="pat-rec-005"></a>

## PAT-REC-005 — count/untilの終端

**Input (original language retained):** 2030年10月14日から毎日、最大3回、10月16日まで測定する。

**Context:** Fictional example. Fixed baseline: 2030-10-11T12:00:00+09:00; user timezone: Asia/Tokyo. Use only supplied dates, IDs, people, and metadata. Referenced existing records are included for independent validation, not to be appended again to a live workspace.

**Reason:** count limits occurrences from the anchor; until is inclusive. Verify both bounds.

**Pitfall:** Do not confuse a query end boundary with recurrence until.

**Recommended** ([canonical fixture](../../../examples/ai-patterns/PAT-REC-005/recommended.life.txt))

<!-- fixture:PAT-REC-005/recommended -->
````lifetxt
[ ] H "測定する" on:2030-10-14 repeat:daily count:3 until:2030-10-16
````

**Validation:** Core 1.0.3; engine source commit `97aa9b52c231f9aad5ba1403e8ed230d69f4d2a3`. Executed; independent review pending. CLI acceptance is not semantic proof.

| Fixture | Class | Exit | Diagnostics (severity/code/line) |
| --- | --- | ---: | --- |
| recommended | recommended | 0 | none |

Fixed-range agenda also executed in UTC; see each manifest agenda field for range, command, and actual output. Storage, expansion, and external execution are separate judgments.

Full diagnostic messages, input SHA-256, and commands are in the [manifest](../../../examples/ai-patterns/manifest.json). Meaning review is the author's source comparison, not independent approval.

**Sources:** [Format 1.0](../life_txt_format_spec.md) §7.6, §8.1; [Profile](../../../prompts/lifetxt-assistant.md). [source 1](../../../examples/recurrence_time_life.txt) / [source 2](../../../examples/habits_reminders_life.txt)

<a id="pat-rec-006"></a>

## PAT-REC-006 — RRULEのdaily/weekly BYDAY

**Input (original language retained):** 2030年10月14日から月曜と水曜の7時に学習する。最大6回。

**Context:** Fictional example. Fixed baseline: 2030-10-11T12:00:00+09:00; user timezone: Asia/Tokyo. Use only supplied dates, IDs, people, and metadata. Referenced existing records are included for independent validation, not to be appended again to a live workspace.

**Reason:** Use weekly BYDAY in the dependency-free subset; daily BYDAY is also supported.

**Pitfall:** This does not imply support for the full RRULE standard. Use full at datetimes for offset-aware recurrence; #1218 tracks the split on/offset-time anchor discrepancy. In this RRULE observation, expanded agenda times lose the offset. The stored authored value is preserved; instant-comparison fidelity is under investigation in #1218.

**Recommended** ([canonical fixture](../../../examples/ai-patterns/PAT-REC-006/recommended.life.txt))

<!-- fixture:PAT-REC-006/recommended -->
````lifetxt
[ ] H "学習する" at:2030-10-14T07:00+09:00 repeat:RRULE:FREQ=WEEKLY;BYDAY=MO,WE;COUNT=6
````

**Validation:** Core 1.0.3; engine source commit `97aa9b52c231f9aad5ba1403e8ed230d69f4d2a3`. Executed; independent review pending. CLI acceptance is not semantic proof.

| Fixture | Class | Exit | Diagnostics (severity/code/line) |
| --- | --- | ---: | --- |
| recommended | recommended | 0 | none |

Fixed-range agenda also executed in UTC; see each manifest agenda field for range, command, and actual output. Storage, expansion, and external execution are separate judgments.

Full diagnostic messages, input SHA-256, and commands are in the [manifest](../../../examples/ai-patterns/manifest.json). Meaning review is the author's source comparison, not independent approval.

**Sources:** [Format 1.0](../life_txt_format_spec.md) §7.6, §8.1; [Profile](../../../prompts/lifetxt-assistant.md). [source 1](../../../examples/recurrence_time_life.txt) / [source 2](../../../examples/habits_reminders_life.txt)

<a id="pat-rec-007"></a>

## PAT-REC-007 — 未対応RRULE・例外日の保持と非展開

**Input (original language retained):** 毎月第2月曜を外部RRULE（FREQ=MONTHLY;BYDAY=MO;BYSETPOS=2）から記録する。起点2030年10月14日。11月11日は休みとだけメモする。

**Context:** Fictional example. Fixed baseline: 2030-10-11T12:00:00+09:00; user timezone: Asia/Tokyo. Use only supplied dates, IDs, people, and metadata. Referenced existing records are included for independent validation, not to be appended again to a live workspace.

**Reason:** BYSETPOS is unsupported by current Core and gives W223. Storage succeeds but observed expansion is empty; this boundary example is not an executable recurring schedule.

**Pitfall:** The note does not implement a recurrence exception. #1217 tracks current ordinal BYDAY/BYMONTHDAY/BYMONTH/WKST support beyond the narrow specification wording.

**Recommended** ([canonical fixture](../../../examples/ai-patterns/PAT-REC-007/recommended.life.txt))

<!-- fixture:PAT-REC-007/recommended -->
````lifetxt
[ ] E "外部の定例予定" on:2030-10-14 repeat:RRULE:FREQ=MONTHLY;BYDAY=MO;BYSETPOS=2 note:"2030-11-11は休み（例外自動展開は未設定）"
````

**Validation:** Core 1.0.3; engine source commit `97aa9b52c231f9aad5ba1403e8ed230d69f4d2a3`. Executed; independent review pending. CLI acceptance is not semantic proof.

| Fixture | Class | Exit | Diagnostics (severity/code/line) |
| --- | --- | ---: | --- |
| recommended | recommended | 0 | warning/W223/L1 |

Fixed-range agenda also executed in UTC; see each manifest agenda field for range, command, and actual output. Storage, expansion, and external execution are separate judgments.

Full diagnostic messages, input SHA-256, and commands are in the [manifest](../../../examples/ai-patterns/manifest.json). Meaning review is the author's source comparison, not independent approval.

**Sources:** [Format 1.0](../life_txt_format_spec.md) §7.6, §8.1; [Profile](../../../prompts/lifetxt-assistant.md). [source 1](../../../examples/recurrence_time_life.txt) / [source 2](../../../examples/habits_reminders_life.txt)

<a id="pat-rec-008"></a>

## PAT-REC-008 — 日付起点なしatと有界範囲

**Input (original language retained):** 起点日は未定だが毎日18時にストレッチする。

**Context:** Fictional example. Fixed baseline: 2030-10-11T12:00:00+09:00; user timezone: Asia/Tokyo. Use only supplied dates, IDs, people, and metadata. Referenced existing records are included for independent validation, not to be appended again to a live workspace.

**Reason:** at without a date anchor is floating and expands only in a bounded range.

**Pitfall:** One-sided time filters intentionally ignore this unanchored value.

**Recommended** ([canonical fixture](../../../examples/ai-patterns/PAT-REC-008/recommended.life.txt))

<!-- fixture:PAT-REC-008/recommended -->
````lifetxt
[ ] H "ストレッチする" at:18:00+09:00 repeat:daily
````

**Validation:** Core 1.0.3; engine source commit `97aa9b52c231f9aad5ba1403e8ed230d69f4d2a3`. Executed; independent review pending. CLI acceptance is not semantic proof.

| Fixture | Class | Exit | Diagnostics (severity/code/line) |
| --- | --- | ---: | --- |
| recommended | recommended | 0 | none |

Fixed-range agenda also executed in UTC; see each manifest agenda field for range, command, and actual output. Storage, expansion, and external execution are separate judgments.

Full diagnostic messages, input SHA-256, and commands are in the [manifest](../../../examples/ai-patterns/manifest.json). Meaning review is the author's source comparison, not independent approval.

**Sources:** [Format 1.0](../life_txt_format_spec.md) §7.6, §8.1; [Profile](../../../prompts/lifetxt-assistant.md). [source 1](../../../examples/recurrence_time_life.txt) / [source 2](../../../examples/habits_reminders_life.txt)

