# AI Reference Patterns — Time / 日時

Code blocks copy canonical fixtures. Both languages retain identical source input and code. Author-run Core checks are separate from meaning comparison; independent review takes place on the PR.

[Format 1.0](../life_txt_format_spec.md) / [Profile](../../../prompts/lifetxt-assistant.md) / [Fixture maintenance](../../../examples/ai-patterns/README.md)

<a id="pat-time-001"></a>

## PAT-TIME-001 — doの実行予定

**Input (original language retained):** 2030年10月14日に草案を書く。締切は指定しない。

**Context:** Fictional example. Fixed baseline: 2030-10-11T12:00:00+09:00; user timezone: Asia/Tokyo. Use only supplied dates, IDs, people, and metadata. Referenced existing records are included for independent validation, not to be appended again to a live workspace.

**Reason:** do is the intended execution date.

**Pitfall:** due would change the meaning to a latest acceptable completion date.

Counterexample class: **C (wrong source meaning)**. Meaning/capability requires source comparison by a person.

**Recommended** ([canonical fixture](../../../examples/ai-patterns/PAT-TIME-001/recommended.life.txt))

<!-- fixture:PAT-TIME-001/recommended -->
````lifetxt
[ ] T "草案を書く" do:2030-10-14
````

**counterexample** ([canonical fixture](../../../examples/ai-patterns/PAT-TIME-001/counterexample.life.txt))

<!-- fixture:PAT-TIME-001/counterexample -->
````lifetxt
[ ] T "草案を書く" due:2030-10-14
````

**Validation:** Core 1.0.3; engine source commit `97aa9b52c231f9aad5ba1403e8ed230d69f4d2a3`. Executed; independent review pending. CLI acceptance is not semantic proof.

| Fixture | Class | Exit | Diagnostics (severity/code/line) |
| --- | --- | ---: | --- |
| recommended | recommended | 0 | none |
| counterexample | C | 0 | none |

Full diagnostic messages, input SHA-256, and commands are in the [manifest](../../../examples/ai-patterns/manifest.json). Meaning review is the author's source comparison, not independent approval.

**Sources:** [Format 1.0](../life_txt_format_spec.md) §7.4, §8, §9.8–9.9; [Profile](../../../prompts/lifetxt-assistant.md). [source 1](../../../examples/recurrence_time_life.txt) / [source 2](../../../examples/messages_life.txt) / [source 3](../../../examples/lifetxt_ai_prompt_conformance.json)

<a id="pat-time-002"></a>

## PAT-TIME-002 — dueの期限

**Input (original language retained):** 草案は2030年10月20日17時までに完成させる。

**Context:** Fictional example. Fixed baseline: 2030-10-11T12:00:00+09:00; user timezone: Asia/Tokyo. Use only supplied dates, IDs, people, and metadata. Referenced existing records are included for independent validation, not to be appended again to a live workspace.

**Reason:** Use due for the cutoff; do not infer the day the work will be performed.

**Pitfall:** Do not automatically duplicate a deadline into do.

**Recommended** ([canonical fixture](../../../examples/ai-patterns/PAT-TIME-002/recommended.life.txt))

<!-- fixture:PAT-TIME-002/recommended -->
````lifetxt
[ ] T "草案を完成させる" due:2030-10-20T17:00+09:00
````

**Validation:** Core 1.0.3; engine source commit `97aa9b52c231f9aad5ba1403e8ed230d69f4d2a3`. Executed; independent review pending. CLI acceptance is not semantic proof.

| Fixture | Class | Exit | Diagnostics (severity/code/line) |
| --- | --- | ---: | --- |
| recommended | recommended | 0 | none |

Full diagnostic messages, input SHA-256, and commands are in the [manifest](../../../examples/ai-patterns/manifest.json). Meaning review is the author's source comparison, not independent approval.

**Sources:** [Format 1.0](../life_txt_format_spec.md) §7.4, §8, §9.8–9.9; [Profile](../../../prompts/lifetxt-assistant.md). [source 1](../../../examples/recurrence_time_life.txt) / [source 2](../../../examples/messages_life.txt) / [source 3](../../../examples/lifetxt_ai_prompt_conformance.json)

<a id="pat-time-003"></a>

## PAT-TIME-003 — onの終日予定

**Input (original language retained):** 2030年10月20日は終日、展示会に参加する。

**Context:** Fictional example. Fixed baseline: 2030-10-11T12:00:00+09:00; user timezone: Asia/Tokyo. Use only supplied dates, IDs, people, and metadata. Referenced existing records are included for independent validation, not to be appended again to a live workspace.

**Reason:** on is an all-day occurrence; no hourly interval is invented.

**Pitfall:** from/to are datetime intervals, not a list of candidate dates.

**Recommended** ([canonical fixture](../../../examples/ai-patterns/PAT-TIME-003/recommended.life.txt))

<!-- fixture:PAT-TIME-003/recommended -->
````lifetxt
[ ] E "展示会" on:2030-10-20
````

**Validation:** Core 1.0.3; engine source commit `97aa9b52c231f9aad5ba1403e8ed230d69f4d2a3`. Executed; independent review pending. CLI acceptance is not semantic proof.

| Fixture | Class | Exit | Diagnostics (severity/code/line) |
| --- | --- | ---: | --- |
| recommended | recommended | 0 | none |

Full diagnostic messages, input SHA-256, and commands are in the [manifest](../../../examples/ai-patterns/manifest.json). Meaning review is the author's source comparison, not independent approval.

**Sources:** [Format 1.0](../life_txt_format_spec.md) §7.4, §8, §9.8–9.9; [Profile](../../../prompts/lifetxt-assistant.md). [source 1](../../../examples/recurrence_time_life.txt) / [source 2](../../../examples/messages_life.txt) / [source 3](../../../examples/lifetxt_ai_prompt_conformance.json)

<a id="pat-time-004"></a>

## PAT-TIME-004 — atの単独日時とon+時刻

**Input (original language retained):** 2030年10月14日の18時に図書を返却することを思い出す。

**Context:** Fictional example. Fixed baseline: 2030-10-11T12:00:00+09:00; user timezone: Asia/Tokyo. Use only supplied dates, IDs, people, and metadata. Referenced existing records are included for independent validation, not to be appended again to a live workspace.

**Reason:** Separate on and at preserve the supplied date and clock time; an at datetime can express the same occurrence.

**Pitfall:** A bare at:18:00 would drop the supplied date.

**Recommended** ([canonical fixture](../../../examples/ai-patterns/PAT-TIME-004/recommended.life.txt))

<!-- fixture:PAT-TIME-004/recommended -->
````lifetxt
[ ] R "図書返却を思い出す" on:2030-10-14 at:18:00+09:00
````

**Validation:** Core 1.0.3; engine source commit `97aa9b52c231f9aad5ba1403e8ed230d69f4d2a3`. Executed; independent review pending. CLI acceptance is not semantic proof.

| Fixture | Class | Exit | Diagnostics (severity/code/line) |
| --- | --- | ---: | --- |
| recommended | recommended | 0 | none |

Full diagnostic messages, input SHA-256, and commands are in the [manifest](../../../examples/ai-patterns/manifest.json). Meaning review is the author's source comparison, not independent approval.

**Sources:** [Format 1.0](../life_txt_format_spec.md) §7.4, §8, §9.8–9.9; [Profile](../../../prompts/lifetxt-assistant.md). [source 1](../../../examples/recurrence_time_life.txt) / [source 2](../../../examples/messages_life.txt) / [source 3](../../../examples/lifetxt_ai_prompt_conformance.json)

<a id="pat-time-005"></a>

## PAT-TIME-005 — from/toの区間

**Input (original language retained):** 2030年10月14日14時から15時30分まで研究会。

**Context:** Fictional example. Fixed baseline: 2030-10-11T12:00:00+09:00; user timezone: Asia/Tokyo. Use only supplied dates, IDs, people, and metadata. Referenced existing records are included for independent validation, not to be appended again to a live workspace.

**Reason:** from/to describe the start and end of one occurrence.

**Pitfall:** Exclusive candidate dates must not be converted into a continuous interval.

**Recommended** ([canonical fixture](../../../examples/ai-patterns/PAT-TIME-005/recommended.life.txt))

<!-- fixture:PAT-TIME-005/recommended -->
````lifetxt
[ ] E "研究会" from:2030-10-14T14:00+09:00 to:2030-10-14T15:30+09:00
````

**Validation:** Core 1.0.3; engine source commit `97aa9b52c231f9aad5ba1403e8ed230d69f4d2a3`. Executed; independent review pending. CLI acceptance is not semantic proof.

| Fixture | Class | Exit | Diagnostics (severity/code/line) |
| --- | --- | ---: | --- |
| recommended | recommended | 0 | none |

Full diagnostic messages, input SHA-256, and commands are in the [manifest](../../../examples/ai-patterns/manifest.json). Meaning review is the author's source comparison, not independent approval.

**Sources:** [Format 1.0](../life_txt_format_spec.md) §7.4, §8, §9.8–9.9; [Profile](../../../prompts/lifetxt-assistant.md). [source 1](../../../examples/recurrence_time_life.txt) / [source 2](../../../examples/messages_life.txt) / [source 3](../../../examples/lifetxt_ai_prompt_conformance.json)

<a id="pat-time-006"></a>

## PAT-TIME-006 — doneの完了日時

**Input (original language retained):** 資料提出は2030年10月14日16時に完了。

**Context:** Fictional example. Fixed baseline: 2030-10-11T12:00:00+09:00; user timezone: Asia/Tokyo. Use only supplied dates, IDs, people, and metadata. Referenced existing records are included for independent validation, not to be appended again to a live workspace.

**Reason:** done records the known completion instant, not the deadline.

**Pitfall:** Do not add a deadline merely because completion time is known.

**Recommended** ([canonical fixture](../../../examples/ai-patterns/PAT-TIME-006/recommended.life.txt))

<!-- fixture:PAT-TIME-006/recommended -->
````lifetxt
[x] T "資料を提出する" done:2030-10-14T16:00+09:00
````

**Validation:** Core 1.0.3; engine source commit `97aa9b52c231f9aad5ba1403e8ed230d69f4d2a3`. Executed; independent review pending. CLI acceptance is not semantic proof.

| Fixture | Class | Exit | Diagnostics (severity/code/line) |
| --- | --- | ---: | --- |
| recommended | recommended | 0 | none |

Full diagnostic messages, input SHA-256, and commands are in the [manifest](../../../examples/ai-patterns/manifest.json). Meaning review is the author's source comparison, not independent approval.

**Sources:** [Format 1.0](../life_txt_format_spec.md) §7.4, §8, §9.8–9.9; [Profile](../../../prompts/lifetxt-assistant.md). [source 1](../../../examples/recurrence_time_life.txt) / [source 2](../../../examples/messages_life.txt) / [source 3](../../../examples/lifetxt_ai_prompt_conformance.json)

<a id="pat-time-007"></a>

## PAT-TIME-007 — offsetとUTC

**Input (original language retained):** 2030年10月14日、日本時間9時から10時までのオンライン会議。

**Context:** Fictional example. Fixed baseline: 2030-10-11T12:00:00+09:00; user timezone: Asia/Tokyo. Use only supplied dates, IDs, people, and metadata. Referenced existing records are included for independent validation, not to be appended again to a live workspace.

**Reason:** 09:00 at +09:00 is 00:00Z; retain the instant rather than dropping its offset.

**Pitfall:** Z means UTC, not Japan local time.

**Recommended** ([canonical fixture](../../../examples/ai-patterns/PAT-TIME-007/recommended.life.txt))

<!-- fixture:PAT-TIME-007/recommended -->
````lifetxt
[ ] E "オンライン会議" from:2030-10-14T00:00Z to:2030-10-14T01:00Z
````

**Validation:** Core 1.0.3; engine source commit `97aa9b52c231f9aad5ba1403e8ed230d69f4d2a3`. Executed; independent review pending. CLI acceptance is not semantic proof.

| Fixture | Class | Exit | Diagnostics (severity/code/line) |
| --- | --- | ---: | --- |
| recommended | recommended | 0 | none |

Full diagnostic messages, input SHA-256, and commands are in the [manifest](../../../examples/ai-patterns/manifest.json). Meaning review is the author's source comparison, not independent approval.

**Sources:** [Format 1.0](../life_txt_format_spec.md) §7.4, §8, §9.8–9.9; [Profile](../../../prompts/lifetxt-assistant.md). [source 1](../../../examples/recurrence_time_life.txt) / [source 2](../../../examples/messages_life.txt) / [source 3](../../../examples/lifetxt_ai_prompt_conformance.json)

<a id="pat-time-008"></a>

## PAT-TIME-008 — 秒・小数秒・時刻のみ

**Input (original language retained):** 毎日18時00分30.5秒（+09:00）に測定する習慣。

**Context:** Fictional example. Fixed baseline: 2030-10-11T12:00:00+09:00; user timezone: Asia/Tokyo. Use only supplied dates, IDs, people, and metadata. Referenced existing records are included for independent validation, not to be appended again to a live workspace.

**Reason:** Preserve seconds, fractional seconds, and the offset; floating-time expansion is limited to a bounded range.

**Pitfall:** Fractional seconds support up to six digits; validation does not deliver notifications.

**Recommended** ([canonical fixture](../../../examples/ai-patterns/PAT-TIME-008/recommended.life.txt))

<!-- fixture:PAT-TIME-008/recommended -->
````lifetxt
[ ] H "測定する" repeat:daily at:18:00:30.5+09:00
````

**Validation:** Core 1.0.3; engine source commit `97aa9b52c231f9aad5ba1403e8ed230d69f4d2a3`. Executed; independent review pending. CLI acceptance is not semantic proof.

| Fixture | Class | Exit | Diagnostics (severity/code/line) |
| --- | --- | ---: | --- |
| recommended | recommended | 0 | none |

Full diagnostic messages, input SHA-256, and commands are in the [manifest](../../../examples/ai-patterns/manifest.json). Meaning review is the author's source comparison, not independent approval.

**Sources:** [Format 1.0](../life_txt_format_spec.md) §7.4, §8, §9.8–9.9; [Profile](../../../prompts/lifetxt-assistant.md). [source 1](../../../examples/recurrence_time_life.txt) / [source 2](../../../examples/messages_life.txt) / [source 3](../../../examples/lifetxt_ai_prompt_conformance.json)

<a id="pat-time-009"></a>

## PAT-TIME-009 — 基準日時付き相対日付と欠測時

**Input (original language retained):** 明日、残高を確認する。

**Context:** Fictional example. Fixed baseline: 2030-10-11T12:00:00+09:00; user timezone: Asia/Tokyo. Use only supplied dates, IDs, people, and metadata. Referenced existing records are included for independent validation, not to be appended again to a live workspace.

**Reason:** The fixed example baseline is 2030-10-11 in Asia/Tokyo, so tomorrow is October 12; ask if the baseline is unavailable.

**Pitfall:** Do not treat the illustrative date as the real conversation date.

**Recommended** ([canonical fixture](../../../examples/ai-patterns/PAT-TIME-009/recommended.life.txt))

<!-- fixture:PAT-TIME-009/recommended -->
````lifetxt
[ ] T "残高を確認する" do:2030-10-12
````

**Validation:** Core 1.0.3; engine source commit `97aa9b52c231f9aad5ba1403e8ed230d69f4d2a3`. Executed; independent review pending. CLI acceptance is not semantic proof.

| Fixture | Class | Exit | Diagnostics (severity/code/line) |
| --- | --- | ---: | --- |
| recommended | recommended | 0 | none |

Full diagnostic messages, input SHA-256, and commands are in the [manifest](../../../examples/ai-patterns/manifest.json). Meaning review is the author's source comparison, not independent approval.

**Sources:** [Format 1.0](../life_txt_format_spec.md) §7.4, §8, §9.8–9.9; [Profile](../../../prompts/lifetxt-assistant.md). [source 1](../../../examples/recurrence_time_life.txt) / [source 2](../../../examples/messages_life.txt) / [source 3](../../../examples/lifetxt_ai_prompt_conformance.json)

<a id="pat-time-010"></a>

## PAT-TIME-010 — notify_at/from/to・ack・snooze_until

**Input (original language retained):** 自分からaliceへの確認依頼。通知期間は2030年10月14日9時〜17時。9時5分に確認済み、9時30分まで通知抑制。

**Context:** Fictional example. Fixed baseline: 2030-10-11T12:00:00+09:00; user timezone: Asia/Tokyo. Use only supplied dates, IDs, people, and metadata. Referenced existing records are included for independent validation, not to be appended again to a live workspace.

**Reason:** Record notification window, acknowledgement, and snooze separately; ack is not task completion.

**Pitfall:** Stored timing does not configure a route or prove delivery.

**Recommended** ([canonical fixture](../../../examples/ai-patterns/PAT-TIME-010/recommended.life.txt))

<!-- fixture:PAT-TIME-010/recommended -->
````lifetxt
[ ] M "確認依頼" sender:self recipient:alice notify_from:2030-10-14T09:00+09:00 notify_to:2030-10-14T17:00+09:00 ack:2030-10-14T09:05+09:00 snooze_until:2030-10-14T09:30+09:00
````

**Validation:** Core 1.0.3; engine source commit `97aa9b52c231f9aad5ba1403e8ed230d69f4d2a3`. Executed; independent review pending. CLI acceptance is not semantic proof.

| Fixture | Class | Exit | Diagnostics (severity/code/line) |
| --- | --- | ---: | --- |
| recommended | recommended | 0 | none |

Full diagnostic messages, input SHA-256, and commands are in the [manifest](../../../examples/ai-patterns/manifest.json). Meaning review is the author's source comparison, not independent approval.

**Sources:** [Format 1.0](../life_txt_format_spec.md) §7.4, §8, §9.8–9.9; [Profile](../../../prompts/lifetxt-assistant.md). [source 1](../../../examples/recurrence_time_life.txt) / [source 2](../../../examples/messages_life.txt) / [source 3](../../../examples/lifetxt_ai_prompt_conformance.json)

