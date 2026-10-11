# AI Reference Patterns — Types / 型

Code blocks copy canonical fixtures. Both languages retain identical source input and code. Author-run Core checks are separate from meaning comparison; independent review takes place on the PR.

[Format 1.0](../life_txt_format_spec.md) / [Profile](../../../prompts/lifetxt-assistant.md) / [Fixture maintenance](../../../examples/ai-patterns/README.md)

<a id="pat-type-001"></a>

## PAT-TYPE-001 — Taskの実行

**Input (original language retained):** 牛乳を買う。日時はまだ決めていない。

**Context:** Fictional example. Fixed baseline: 2030-10-11T12:00:00+09:00; user timezone: Asia/Tokyo. Use only supplied dates, IDs, people, and metadata. Referenced existing records are included for independent validation, not to be appended again to a live workspace.

**Reason:** Use T for an actionable item; no time, deadline, or ID was supplied.

**Pitfall:** Missing time is intentional, not an error.

**Recommended** ([canonical fixture](../../../examples/ai-patterns/PAT-TYPE-001/recommended.life.txt))

<!-- fixture:PAT-TYPE-001/recommended -->
````lifetxt
[ ] T "牛乳を買う"
````

**Validation:** Core 1.0.3; engine source commit `97aa9b52c231f9aad5ba1403e8ed230d69f4d2a3`. Executed; independent review pending. CLI acceptance is not semantic proof.

| Fixture | Class | Exit | Diagnostics (severity/code/line) |
| --- | --- | ---: | --- |
| recommended | recommended | 0 | none |

Full diagnostic messages, input SHA-256, and commands are in the [manifest](../../../examples/ai-patterns/manifest.json). Meaning review is the author's source comparison, not independent approval.

**Sources:** [Format 1.0](../life_txt_format_spec.md) §2–3, §9, §13–14; [Profile](../../../prompts/lifetxt-assistant.md). [source 1](../../../examples/tasks_life.txt) / [source 2](../../../examples/events_life.txt) / [source 3](../../../examples/habits_reminders_life.txt) / [source 4](../../../examples/messages_life.txt) / [source 5](../../../examples/diary_life.txt) / [source 6](../../../examples/status_presence.txt)

<a id="pat-type-002"></a>

## PAT-TYPE-002 — Eventの開催

**Input (original language retained):** 2030年10月14日10時に会議がある。

**Context:** Fictional example. Fixed baseline: 2030-10-11T12:00:00+09:00; user timezone: Asia/Tokyo. Use only supplied dates, IDs, people, and metadata. Referenced existing records are included for independent validation, not to be appended again to a live workspace.

**Reason:** Use E for an occurrence; preserve the known start without inventing an end.

**Pitfall:** An action task and a calendar occurrence express different intentions.

**Recommended** ([canonical fixture](../../../examples/ai-patterns/PAT-TYPE-002/recommended.life.txt))

<!-- fixture:PAT-TYPE-002/recommended -->
````lifetxt
[ ] E "会議" at:2030-10-14T10:00+09:00
````

**Validation:** Core 1.0.3; engine source commit `97aa9b52c231f9aad5ba1403e8ed230d69f4d2a3`. Executed; independent review pending. CLI acceptance is not semantic proof.

| Fixture | Class | Exit | Diagnostics (severity/code/line) |
| --- | --- | ---: | --- |
| recommended | recommended | 0 | none |

Full diagnostic messages, input SHA-256, and commands are in the [manifest](../../../examples/ai-patterns/manifest.json). Meaning review is the author's source comparison, not independent approval.

**Sources:** [Format 1.0](../life_txt_format_spec.md) §2–3, §9, §13–14; [Profile](../../../prompts/lifetxt-assistant.md). [source 1](../../../examples/tasks_life.txt) / [source 2](../../../examples/events_life.txt) / [source 3](../../../examples/habits_reminders_life.txt) / [source 4](../../../examples/messages_life.txt) / [source 5](../../../examples/diary_life.txt) / [source 6](../../../examples/status_presence.txt)

<a id="pat-type-003"></a>

## PAT-TYPE-003 — Deadlineの締切

**Input (original language retained):** 申請の受付締切は2030年10月20日17時。

**Context:** Fictional example. Fixed baseline: 2030-10-11T12:00:00+09:00; user timezone: Asia/Tokyo. Use only supplied dates, IDs, people, and metadata. Referenced existing records are included for independent validation, not to be appended again to a live workspace.

**Reason:** D records a cutoff rather than the work needed to meet it.

**Pitfall:** The deadline does not create or execute a submission task.

**Recommended** ([canonical fixture](../../../examples/ai-patterns/PAT-TYPE-003/recommended.life.txt))

<!-- fixture:PAT-TYPE-003/recommended -->
````lifetxt
[ ] D "申請受付締切" due:2030-10-20T17:00+09:00
````

**Validation:** Core 1.0.3; engine source commit `97aa9b52c231f9aad5ba1403e8ed230d69f4d2a3`. Executed; independent review pending. CLI acceptance is not semantic proof.

| Fixture | Class | Exit | Diagnostics (severity/code/line) |
| --- | --- | ---: | --- |
| recommended | recommended | 0 | none |

Full diagnostic messages, input SHA-256, and commands are in the [manifest](../../../examples/ai-patterns/manifest.json). Meaning review is the author's source comparison, not independent approval.

**Sources:** [Format 1.0](../life_txt_format_spec.md) §2–3, §9, §13–14; [Profile](../../../prompts/lifetxt-assistant.md). [source 1](../../../examples/tasks_life.txt) / [source 2](../../../examples/events_life.txt) / [source 3](../../../examples/habits_reminders_life.txt) / [source 4](../../../examples/messages_life.txt) / [source 5](../../../examples/diary_life.txt) / [source 6](../../../examples/status_presence.txt)

<a id="pat-type-004"></a>

## PAT-TYPE-004 — Reminderの注意喚起

**Input (original language retained):** 2030年10月14日18時に図書館への電話を思い出すための記録を作る。

**Context:** Fictional example. Fixed baseline: 2030-10-11T12:00:00+09:00; user timezone: Asia/Tokyo. Use only supplied dates, IDs, people, and metadata. Referenced existing records are included for independent validation, not to be appended again to a live workspace.

**Reason:** Use R for an attention cue.

**Pitfall:** A generated record alone does not schedule device delivery.

**Recommended** ([canonical fixture](../../../examples/ai-patterns/PAT-TYPE-004/recommended.life.txt))

<!-- fixture:PAT-TYPE-004/recommended -->
````lifetxt
[ ] R "図書館への電話を思い出す" at:2030-10-14T18:00+09:00
````

**Validation:** Core 1.0.3; engine source commit `97aa9b52c231f9aad5ba1403e8ed230d69f4d2a3`. Executed; independent review pending. CLI acceptance is not semantic proof.

| Fixture | Class | Exit | Diagnostics (severity/code/line) |
| --- | --- | ---: | --- |
| recommended | recommended | 0 | none |

Full diagnostic messages, input SHA-256, and commands are in the [manifest](../../../examples/ai-patterns/manifest.json). Meaning review is the author's source comparison, not independent approval.

**Sources:** [Format 1.0](../life_txt_format_spec.md) §2–3, §9, §13–14; [Profile](../../../prompts/lifetxt-assistant.md). [source 1](../../../examples/tasks_life.txt) / [source 2](../../../examples/events_life.txt) / [source 3](../../../examples/habits_reminders_life.txt) / [source 4](../../../examples/messages_life.txt) / [source 5](../../../examples/diary_life.txt) / [source 6](../../../examples/status_presence.txt)

<a id="pat-type-005"></a>

## PAT-TYPE-005 — Habitの習慣

**Input (original language retained):** 毎日18時に英語を学習する習慣を記録する。

**Context:** Fictional example. Fixed baseline: 2030-10-11T12:00:00+09:00; user timezone: Asia/Tokyo. Use only supplied dates, IDs, people, and metadata. Referenced existing records are included for independent validation, not to be appended again to a live workspace.

**Reason:** H describes repeated practice; retain the floating time because no start date was supplied.

**Pitfall:** Floating-time expansion needs a bounded requested range.

**Recommended** ([canonical fixture](../../../examples/ai-patterns/PAT-TYPE-005/recommended.life.txt))

<!-- fixture:PAT-TYPE-005/recommended -->
````lifetxt
[ ] H "英語を学習する" repeat:daily at:18:00
````

**Validation:** Core 1.0.3; engine source commit `97aa9b52c231f9aad5ba1403e8ed230d69f4d2a3`. Executed; independent review pending. CLI acceptance is not semantic proof.

| Fixture | Class | Exit | Diagnostics (severity/code/line) |
| --- | --- | ---: | --- |
| recommended | recommended | 0 | none |

Full diagnostic messages, input SHA-256, and commands are in the [manifest](../../../examples/ai-patterns/manifest.json). Meaning review is the author's source comparison, not independent approval.

**Sources:** [Format 1.0](../life_txt_format_spec.md) §2–3, §9, §13–14; [Profile](../../../prompts/lifetxt-assistant.md). [source 1](../../../examples/tasks_life.txt) / [source 2](../../../examples/events_life.txt) / [source 3](../../../examples/habits_reminders_life.txt) / [source 4](../../../examples/messages_life.txt) / [source 5](../../../examples/diary_life.txt) / [source 6](../../../examples/status_presence.txt)

<a id="pat-type-006"></a>

## PAT-TYPE-006 — Noteの持続的情報

**Input (original language retained):** 資料には図を増やすというメモを残す。

**Context:** Fictional example. Fixed baseline: 2030-10-11T12:00:00+09:00; user timezone: Asia/Tokyo. Use only supplied dates, IDs, people, and metadata. Referenced existing records are included for independent validation, not to be appended again to a live workspace.

**Reason:** N is enduring information and uses [N].

**Pitfall:** Do not turn a memo into an unfinished action without a request.

**Recommended** ([canonical fixture](../../../examples/ai-patterns/PAT-TYPE-006/recommended.life.txt))

<!-- fixture:PAT-TYPE-006/recommended -->
````lifetxt
[N] N "資料には図を増やす"
````

**Validation:** Core 1.0.3; engine source commit `97aa9b52c231f9aad5ba1403e8ed230d69f4d2a3`. Executed; independent review pending. CLI acceptance is not semantic proof.

| Fixture | Class | Exit | Diagnostics (severity/code/line) |
| --- | --- | ---: | --- |
| recommended | recommended | 0 | none |

Full diagnostic messages, input SHA-256, and commands are in the [manifest](../../../examples/ai-patterns/manifest.json). Meaning review is the author's source comparison, not independent approval.

**Sources:** [Format 1.0](../life_txt_format_spec.md) §2–3, §9, §13–14; [Profile](../../../prompts/lifetxt-assistant.md). [source 1](../../../examples/tasks_life.txt) / [source 2](../../../examples/events_life.txt) / [source 3](../../../examples/habits_reminders_life.txt) / [source 4](../../../examples/messages_life.txt) / [source 5](../../../examples/diary_life.txt) / [source 6](../../../examples/status_presence.txt)

<a id="pat-type-007"></a>

## PAT-TYPE-007 — Statusの在席状態

**Input (original language retained):** 自分は2030年10月14日9時から集中作業中。

**Context:** Fictional example. Fixed baseline: 2030-10-11T12:00:00+09:00; user timezone: Asia/Tokyo. Use only supplied dates, IDs, people, and metadata. Referenced existing records are included for independent validation, not to be appended again to a live workspace.

**Reason:** S records presence with a datetime and state; person:self identifies the supplied target.

**Pitfall:** Do not claim that this updates an external chat presence.

**Recommended** ([canonical fixture](../../../examples/ai-patterns/PAT-TYPE-007/recommended.life.txt))

<!-- fixture:PAT-TYPE-007/recommended -->
````lifetxt
[/] S "集中作業中" from:2030-10-14T09:00+09:00 state:focus person:self
````

**Validation:** Core 1.0.3; engine source commit `97aa9b52c231f9aad5ba1403e8ed230d69f4d2a3`. Executed; independent review pending. CLI acceptance is not semantic proof.

| Fixture | Class | Exit | Diagnostics (severity/code/line) |
| --- | --- | ---: | --- |
| recommended | recommended | 0 | none |

Full diagnostic messages, input SHA-256, and commands are in the [manifest](../../../examples/ai-patterns/manifest.json). Meaning review is the author's source comparison, not independent approval.

**Sources:** [Format 1.0](../life_txt_format_spec.md) §2–3, §9, §13–14; [Profile](../../../prompts/lifetxt-assistant.md). [source 1](../../../examples/tasks_life.txt) / [source 2](../../../examples/events_life.txt) / [source 3](../../../examples/habits_reminders_life.txt) / [source 4](../../../examples/messages_life.txt) / [source 5](../../../examples/diary_life.txt) / [source 6](../../../examples/status_presence.txt)

<a id="pat-type-008"></a>

## PAT-TYPE-008 — Messageの伝達依頼

**Input (original language retained):** 2030年10月14日9時に自分からaliceへ資料レビュー依頼を送るための記録。

**Context:** Fictional example. Fixed baseline: 2030-10-11T12:00:00+09:00; user timezone: Asia/Tokyo. Use only supplied dates, IDs, people, and metadata. Referenced existing records are included for independent validation, not to be appended again to a live workspace.

**Reason:** M records sender, recipient, and notification time; do not compose an unsupplied message body.

**Pitfall:** A request to send is different from a message already sent.

**Recommended** ([canonical fixture](../../../examples/ai-patterns/PAT-TYPE-008/recommended.life.txt))

<!-- fixture:PAT-TYPE-008/recommended -->
````lifetxt
[ ] M "資料レビュー依頼" sender:self recipient:alice notify_at:2030-10-14T09:00+09:00
````

**Validation:** Core 1.0.3; engine source commit `97aa9b52c231f9aad5ba1403e8ed230d69f4d2a3`. Executed; independent review pending. CLI acceptance is not semantic proof.

| Fixture | Class | Exit | Diagnostics (severity/code/line) |
| --- | --- | ---: | --- |
| recommended | recommended | 0 | none |

Full diagnostic messages, input SHA-256, and commands are in the [manifest](../../../examples/ai-patterns/manifest.json). Meaning review is the author's source comparison, not independent approval.

**Sources:** [Format 1.0](../life_txt_format_spec.md) §2–3, §9, §13–14; [Profile](../../../prompts/lifetxt-assistant.md). [source 1](../../../examples/tasks_life.txt) / [source 2](../../../examples/events_life.txt) / [source 3](../../../examples/habits_reminders_life.txt) / [source 4](../../../examples/messages_life.txt) / [source 5](../../../examples/diary_life.txt) / [source 6](../../../examples/status_presence.txt)

<a id="pat-type-009"></a>

## PAT-TYPE-009 — Journalの日時付き記録

**Input (original language retained):** 2030年10月11日の研究日誌。今日は関連文献を読んだ。

**Context:** Fictional example. Fixed baseline: 2030-10-11T12:00:00+09:00; user timezone: Asia/Tokyo. Use only supplied dates, IDs, people, and metadata. Referenced existing records are included for independent validation, not to be appended again to a live workspace.

**Reason:** J is a dated reflection; the continuation line is its body.

**Pitfall:** Use [N] for J; do not automatically synthesize tasks from an experience.

**Recommended** ([canonical fixture](../../../examples/ai-patterns/PAT-TYPE-009/recommended.life.txt))

<!-- fixture:PAT-TYPE-009/recommended -->
````lifetxt
[N] J "研究日誌" on:2030-10-11
| 今日は関連文献を読んだ。
````

**Validation:** Core 1.0.3; engine source commit `97aa9b52c231f9aad5ba1403e8ed230d69f4d2a3`. Executed; independent review pending. CLI acceptance is not semantic proof.

| Fixture | Class | Exit | Diagnostics (severity/code/line) |
| --- | --- | ---: | --- |
| recommended | recommended | 0 | none |

Full diagnostic messages, input SHA-256, and commands are in the [manifest](../../../examples/ai-patterns/manifest.json). Meaning review is the author's source comparison, not independent approval.

**Sources:** [Format 1.0](../life_txt_format_spec.md) §2–3, §9, §13–14; [Profile](../../../prompts/lifetxt-assistant.md). [source 1](../../../examples/tasks_life.txt) / [source 2](../../../examples/events_life.txt) / [source 3](../../../examples/habits_reminders_life.txt) / [source 4](../../../examples/messages_life.txt) / [source 5](../../../examples/diary_life.txt) / [source 6](../../../examples/status_presence.txt)

