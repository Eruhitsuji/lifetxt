# AI Reference Patterns — Statuses / 状態

Code blocks copy canonical fixtures. Both languages retain identical source input and code. Author-run Core checks are separate from meaning comparison; independent review takes place on the PR.

[Format 1.0](../life_txt_format_spec.md) / [Profile](../../../prompts/lifetxt-assistant.md) / [Fixture maintenance](../../../examples/ai-patterns/README.md)

<a id="pat-status-001"></a>

## PAT-STATUS-001 — 未完了

**Input (original language retained):** 資料を準備する。まだ着手していない。

**Context:** Fictional example. Fixed baseline: 2030-10-11T12:00:00+09:00; user timezone: Asia/Tokyo. Use only supplied dates, IDs, people, and metadata. Referenced existing records are included for independent validation, not to be appended again to a live workspace.

**Reason:** [ ] means unfinished; no start time is inferred.

**Pitfall:** Not every open task needs a deadline.

**Recommended** ([canonical fixture](../../../examples/ai-patterns/PAT-STATUS-001/recommended.life.txt))

<!-- fixture:PAT-STATUS-001/recommended -->
````lifetxt
[ ] T "資料を準備する"
````

**Validation:** Core 1.0.3; engine source commit `97aa9b52c231f9aad5ba1403e8ed230d69f4d2a3`. Executed; independent review pending. CLI acceptance is not semantic proof.

| Fixture | Class | Exit | Diagnostics (severity/code/line) |
| --- | --- | ---: | --- |
| recommended | recommended | 0 | none |

Full diagnostic messages, input SHA-256, and commands are in the [manifest](../../../examples/ai-patterns/manifest.json). Meaning review is the author's source comparison, not independent approval.

**Sources:** [Format 1.0](../life_txt_format_spec.md) §2, §7.5, §10, §14; [Profile](../../../prompts/lifetxt-assistant.md). [source 1](../../../examples/tasks_life.txt) / [source 2](../../../examples/events_life.txt) / [source 3](../../../examples/messages_life.txt)

<a id="pat-status-002"></a>

## PAT-STATUS-002 — 進行中とprogress/elapsed

**Input (original language retained):** 資料を作成中。進捗3/10、実作業時間は25分。

**Context:** Fictional example. Fixed baseline: 2030-10-11T12:00:00+09:00; user timezone: Asia/Tokyo. Use only supplied dates, IDs, people, and metadata. Referenced existing records are included for independent validation, not to be appended again to a live workspace.

**Reason:** Workflow status, quantitative progress, and actual elapsed time are separate facts.

**Pitfall:** 100% does not automatically complete the item; authoritative history belongs to the progress feature.

**Recommended** ([canonical fixture](../../../examples/ai-patterns/PAT-STATUS-002/recommended.life.txt))

<!-- fixture:PAT-STATUS-002/recommended -->
````lifetxt
[/] T "資料を作成する" progress:3/10 elapsed:25m
````

**Validation:** Core 1.0.3; engine source commit `97aa9b52c231f9aad5ba1403e8ed230d69f4d2a3`. Executed; independent review pending. CLI acceptance is not semantic proof.

| Fixture | Class | Exit | Diagnostics (severity/code/line) |
| --- | --- | ---: | --- |
| recommended | recommended | 0 | none |

Full diagnostic messages, input SHA-256, and commands are in the [manifest](../../../examples/ai-patterns/manifest.json). Meaning review is the author's source comparison, not independent approval.

**Sources:** [Format 1.0](../life_txt_format_spec.md) §2, §7.5, §10, §14; [Profile](../../../prompts/lifetxt-assistant.md). [source 1](../../../examples/tasks_life.txt) / [source 2](../../../examples/events_life.txt) / [source 3](../../../examples/messages_life.txt)

<a id="pat-status-003"></a>

## PAT-STATUS-003 — 完了と既知または不明のdone

**Input (original language retained):** 机の片付けは完了した。完了日は覚えていない。

**Context:** Fictional example. Fixed baseline: 2030-10-11T12:00:00+09:00; user timezone: Asia/Tokyo. Use only supplied dates, IDs, people, and metadata. Referenced existing records are included for independent validation, not to be appended again to a live workspace.

**Reason:** Preserve completion without inventing done; W103 is intentional when the completion date is unknown.

**Pitfall:** Do not fabricate today's date to silence the warning.

**Recommended** ([canonical fixture](../../../examples/ai-patterns/PAT-STATUS-003/recommended.life.txt))

<!-- fixture:PAT-STATUS-003/recommended -->
````lifetxt
[x] T "机を片付ける"
````

**Validation:** Core 1.0.3; engine source commit `97aa9b52c231f9aad5ba1403e8ed230d69f4d2a3`. Executed; independent review pending. CLI acceptance is not semantic proof.

| Fixture | Class | Exit | Diagnostics (severity/code/line) |
| --- | --- | ---: | --- |
| recommended | recommended | 0 | warning/W103/L1 |

Full diagnostic messages, input SHA-256, and commands are in the [manifest](../../../examples/ai-patterns/manifest.json). Meaning review is the author's source comparison, not independent approval.

**Sources:** [Format 1.0](../life_txt_format_spec.md) §2, §7.5, §10, §14; [Profile](../../../prompts/lifetxt-assistant.md). [source 1](../../../examples/tasks_life.txt) / [source 2](../../../examples/events_life.txt) / [source 3](../../../examples/messages_life.txt)

<a id="pat-status-004"></a>

## PAT-STATUS-004 — キャンセルとreason

**Input (original language retained):** 夕食会をキャンセルした。理由は参加者不足。

**Context:** Fictional example. Fixed baseline: 2030-10-11T12:00:00+09:00; user timezone: Asia/Tokyo. Use only supplied dates, IDs, people, and metadata. Referenced existing records are included for independent validation, not to be appended again to a live workspace.

**Reason:** Retain canceled status and the supplied reason without guessing an event date.

**Pitfall:** Cancellation is not evidence of successful execution.

**Recommended** ([canonical fixture](../../../examples/ai-patterns/PAT-STATUS-004/recommended.life.txt))

<!-- fixture:PAT-STATUS-004/recommended -->
````lifetxt
[-] E "夕食会" reason:"参加者不足"
````

**Validation:** Core 1.0.3; engine source commit `97aa9b52c231f9aad5ba1403e8ed230d69f4d2a3`. Executed; independent review pending. CLI acceptance is not semantic proof.

| Fixture | Class | Exit | Diagnostics (severity/code/line) |
| --- | --- | ---: | --- |
| recommended | recommended | 0 | none |

Full diagnostic messages, input SHA-256, and commands are in the [manifest](../../../examples/ai-patterns/manifest.json). Meaning review is the author's source comparison, not independent approval.

**Sources:** [Format 1.0](../life_txt_format_spec.md) §2, §7.5, §10, §14; [Profile](../../../prompts/lifetxt-assistant.md). [source 1](../../../examples/tasks_life.txt) / [source 2](../../../examples/events_life.txt) / [source 3](../../../examples/messages_life.txt)

<a id="pat-status-005"></a>

## PAT-STATUS-005 — 移動日時moved_toと置換IDの区別

**Input (original language retained):** 図書返却を2030年10月22日に延期。理由は出張。

**Context:** Fictional example. Fixed baseline: 2030-10-11T12:00:00+09:00; user timezone: Asia/Tokyo. Use only supplied dates, IDs, people, and metadata. Referenced existing records are included for independent validation, not to be appended again to a live workspace.

**Reason:** moved_to stores the new date; replaced_by is the separate item-ID replacement relation.

**Pitfall:** Do not put an item ID into moved_to.

Counterexample class: **B (validator warning)**. Meaning/capability requires source comparison by a person.

**Recommended** ([canonical fixture](../../../examples/ai-patterns/PAT-STATUS-005/recommended.life.txt))

<!-- fixture:PAT-STATUS-005/recommended -->
````lifetxt
[>] T "図書を返却する" moved_to:2030-10-22 reason:"出張"
````

**counterexample** ([canonical fixture](../../../examples/ai-patterns/PAT-STATUS-005/counterexample.life.txt))

<!-- fixture:PAT-STATUS-005/counterexample -->
````lifetxt
[>] T "図書を返却する" moved_to:return_new
````

**Validation:** Core 1.0.3; engine source commit `97aa9b52c231f9aad5ba1403e8ed230d69f4d2a3`. Executed; independent review pending. CLI acceptance is not semantic proof.

| Fixture | Class | Exit | Diagnostics (severity/code/line) |
| --- | --- | ---: | --- |
| recommended | recommended | 0 | none |
| counterexample | B | 0 | warning/W203/L1 |

Full diagnostic messages, input SHA-256, and commands are in the [manifest](../../../examples/ai-patterns/manifest.json). Meaning review is the author's source comparison, not independent approval.

**Sources:** [Format 1.0](../life_txt_format_spec.md) §2, §7.5, §10, §14; [Profile](../../../prompts/lifetxt-assistant.md). [source 1](../../../examples/tasks_life.txt) / [source 2](../../../examples/events_life.txt) / [source 3](../../../examples/messages_life.txt)

<a id="pat-status-006"></a>

## PAT-STATUS-006 — 保留・未確定

**Input (original language retained):** 顧客との会議は未確定。返答待ち。

**Context:** Fictional example. Fixed baseline: 2030-10-11T12:00:00+09:00; user timezone: Asia/Tokyo. Use only supplied dates, IDs, people, and metadata. Referenced existing records are included for independent validation, not to be appended again to a live workspace.

**Reason:** [?] preserves uncertainty; omit a date that was not supplied.

**Pitfall:** Uncertainty is not permission to invent candidate dates.

**Recommended** ([canonical fixture](../../../examples/ai-patterns/PAT-STATUS-006/recommended.life.txt))

<!-- fixture:PAT-STATUS-006/recommended -->
````lifetxt
[?] E "顧客との会議" reason:"返答待ち"
````

**Validation:** Core 1.0.3; engine source commit `97aa9b52c231f9aad5ba1403e8ed230d69f4d2a3`. Executed; independent review pending. CLI acceptance is not semantic proof.

| Fixture | Class | Exit | Diagnostics (severity/code/line) |
| --- | --- | ---: | --- |
| recommended | recommended | 0 | none |

Full diagnostic messages, input SHA-256, and commands are in the [manifest](../../../examples/ai-patterns/manifest.json). Meaning review is the author's source comparison, not independent approval.

**Sources:** [Format 1.0](../life_txt_format_spec.md) §2, §7.5, §10, §14; [Profile](../../../prompts/lifetxt-assistant.md). [source 1](../../../examples/tasks_life.txt) / [source 2](../../../examples/events_life.txt) / [source 3](../../../examples/messages_life.txt)

<a id="pat-status-007"></a>

## PAT-STATUS-007 — Note/Journal専用の[N]

**Input (original language retained):** 設計のメモを残す。Noteを完了Taskとは扱わない。

**Context:** Fictional example. Fixed baseline: 2030-10-11T12:00:00+09:00; user timezone: Asia/Tokyo. Use only supplied dates, IDs, people, and metadata. Referenced existing records are included for independent validation, not to be appended again to a live workspace.

**Reason:** N and J use [N], not a task completion state.

**Pitfall:** [N] T is diagnosed as an incompatible type/status combination.

Counterexample class: **B (validator warning)**. Meaning/capability requires source comparison by a person.

**Recommended** ([canonical fixture](../../../examples/ai-patterns/PAT-STATUS-007/recommended.life.txt))

<!-- fixture:PAT-STATUS-007/recommended -->
````lifetxt
[N] N "設計メモ"
````

**counterexample** ([canonical fixture](../../../examples/ai-patterns/PAT-STATUS-007/counterexample.life.txt))

<!-- fixture:PAT-STATUS-007/counterexample -->
````lifetxt
[N] T "設計メモ"
````

**Validation:** Core 1.0.3; engine source commit `97aa9b52c231f9aad5ba1403e8ed230d69f4d2a3`. Executed; independent review pending. CLI acceptance is not semantic proof.

| Fixture | Class | Exit | Diagnostics (severity/code/line) |
| --- | --- | ---: | --- |
| recommended | recommended | 0 | none |
| counterexample | B | 0 | warning/W101/L1 |

Full diagnostic messages, input SHA-256, and commands are in the [manifest](../../../examples/ai-patterns/manifest.json). Meaning review is the author's source comparison, not independent approval.

**Sources:** [Format 1.0](../life_txt_format_spec.md) §2, §7.5, §10, §14; [Profile](../../../prompts/lifetxt-assistant.md). [source 1](../../../examples/tasks_life.txt) / [source 2](../../../examples/events_life.txt) / [source 3](../../../examples/messages_life.txt)

