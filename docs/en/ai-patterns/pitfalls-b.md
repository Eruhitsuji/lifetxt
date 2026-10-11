# AI Reference Patterns — Semantic pitfalls / 意味の誤変換

Code blocks copy canonical fixtures. Both languages retain identical source input and code. Author-run Core checks are separate from meaning comparison; independent review takes place on the PR. These are fictional teaching inputs and contrasts built from #1164 failure classes, not verbatim original prompts/model outputs or new LLM observations.

[Format 1.0](../life_txt_format_spec.md) / [Profile](../../../prompts/lifetxt-assistant.md) / [Fixture maintenance](../../../examples/ai-patterns/README.md)

<a id="pat-pit-006"></a>

## PAT-PIT-006 — ID・担当・priority等の非創作

**Input (original language retained):** 牛乳を買う。担当者、priority、project、通知日時は指定しない。

**Context:** Fictional example. Fixed baseline: 2030-10-11T12:00:00+09:00; user timezone: Asia/Tokyo. Use only supplied dates, IDs, people, and metadata. Referenced existing records are included for independent validation, not to be appended again to a live workspace.

**Reason:** Return the minimal line without inferring metadata.

**Pitfall:** The counterexample's added metadata can be valid syntax while absent from the source.

Counterexample class: **C (wrong source meaning)**. Meaning/capability requires source comparison by a person.

**Recommended** ([canonical fixture](../../../examples/ai-patterns/PAT-PIT-006/recommended.life.txt))

<!-- fixture:PAT-PIT-006/recommended -->
````lifetxt
[ ] T "牛乳を買う"
````

**counterexample** ([canonical fixture](../../../examples/ai-patterns/PAT-PIT-006/counterexample.life.txt))

<!-- fixture:PAT-PIT-006/counterexample -->
````lifetxt
[ ] T "牛乳を買う" id:milk project:life priority:A assignee:self
````

**Validation:** Core 1.0.3; engine source commit `97aa9b52c231f9aad5ba1403e8ed230d69f4d2a3`. Executed; independent review pending. CLI acceptance is not semantic proof.

| Fixture | Class | Exit | Diagnostics (severity/code/line) |
| --- | --- | ---: | --- |
| recommended | recommended | 0 | none |
| counterexample | C | 0 | none |

Full diagnostic messages, input SHA-256, and commands are in the [manifest](../../../examples/ai-patterns/manifest.json). Meaning review is the author's source comparison, not independent approval.

**Sources:** [Format 1.0](../life_txt_format_spec.md) Profile; AI guide §9; #1164; [Profile](../../../prompts/lifetxt-assistant.md). [source 1](https://github.com/Eruhitsuji/lifetxt/issues/1164#issuecomment-6078516662) / [source 2](https://github.com/Eruhitsuji/lifetxt/issues/1164#issuecomment-6078553354) / [source 3](https://github.com/Eruhitsuji/lifetxt/issues/1164#issuecomment-6079794954) / [source 4](https://github.com/Eruhitsuji/lifetxt/issues/1164#issuecomment-6080057300) / [source 5](../ai-integration.md#9-without-mcp)

<a id="pat-pit-007"></a>

## PAT-PIT-007 — 未知key≠公式候補日・検索機能

**Input (original language retained):** 会議は2030年10月20日か22日。公式候補日機能を使えるか説明してから下書きを作る。

**Context:** Fictional example. Fixed baseline: 2030-10-11T12:00:00+09:00; user timezone: Asia/Tokyo. Use only supplied dates, IDs, people, and metadata. Referenced existing records are included for independent validation, not to be appended again to a live workspace.

**Reason:** Use note to preserve candidates in existing Format; custom-key preservation is not a standard candidate feature.

**Pitfall:** Removing W106 alone does not establish semantics or feature support.

Counterexample class: **B (validator warning)**. Meaning/capability requires source comparison by a person.

**Recommended** ([canonical fixture](../../../examples/ai-patterns/PAT-PIT-007/recommended.life.txt))

<!-- fixture:PAT-PIT-007/recommended -->
````lifetxt
[?] E "会議" note:"候補日は2030-10-20または2030-10-22、未確定"
````

**counterexample** ([canonical fixture](../../../examples/ai-patterns/PAT-PIT-007/counterexample.life.txt))

<!-- fixture:PAT-PIT-007/counterexample -->
````lifetxt
[?] E "会議" candidate_on:2030-10-20 candidate_on:2030-10-22
````

**Validation:** Core 1.0.3; engine source commit `97aa9b52c231f9aad5ba1403e8ed230d69f4d2a3`. Executed; independent review pending. CLI acceptance is not semantic proof.

| Fixture | Class | Exit | Diagnostics (severity/code/line) |
| --- | --- | ---: | --- |
| recommended | recommended | 0 | none |
| counterexample | B | 0 | warning/W106/L1 |

Full diagnostic messages, input SHA-256, and commands are in the [manifest](../../../examples/ai-patterns/manifest.json). Meaning review is the author's source comparison, not independent approval.

**Sources:** [Format 1.0](../life_txt_format_spec.md) Profile; AI guide §9; #1164; [Profile](../../../prompts/lifetxt-assistant.md). [source 1](https://github.com/Eruhitsuji/lifetxt/issues/1164#issuecomment-6078516662) / [source 2](https://github.com/Eruhitsuji/lifetxt/issues/1164#issuecomment-6078553354) / [source 3](https://github.com/Eruhitsuji/lifetxt/issues/1164#issuecomment-6079794954) / [source 4](https://github.com/Eruhitsuji/lifetxt/issues/1164#issuecomment-6080057300) / [source 5](../ai-integration.md#9-without-mcp)

<a id="pat-pit-008"></a>

## PAT-PIT-008 — 記録≠Teams送信・条件自動実行

**Input (original language retained):** 2030年10月14日9時にaliceへTeamsで返答依頼を送る記録。回答済みならキャンセルしたいが、その自動処理は設定していない。

**Context:** Fictional example. Fixed baseline: 2030-10-11T12:00:00+09:00; user timezone: Asia/Tokyo. Use only supplied dates, IDs, people, and metadata. Referenced existing records are included for independent validation, not to be appended again to a live workspace.

**Reason:** Record the request and condition only; do not invent message text or external connectivity.

**Pitfall:** The wrong claim is that the counterexample guarantees Teams delivery and automatic cancellation after a reply; check cannot detect that prose claim.

Counterexample class: **D (unsupported prose claim)**. Meaning/capability requires source comparison by a person.

**Recommended** ([canonical fixture](../../../examples/ai-patterns/PAT-PIT-008/recommended.life.txt))

<!-- fixture:PAT-PIT-008/recommended -->
````lifetxt
[ ] M "返答依頼" sender:self recipient:alice notify_at:2030-10-14T09:00+09:00 channel:teams note:"回答済みの場合の扱いは手動確認。自動送信/自動キャンセルは未設定"
````

**counterexample** ([canonical fixture](../../../examples/ai-patterns/PAT-PIT-008/counterexample.life.txt))

<!-- fixture:PAT-PIT-008/counterexample -->
````lifetxt
[ ] M "返答依頼" sender:self recipient:alice notify_at:2030-10-14T09:00+09:00 channel:teams
````

**Validation:** Core 1.0.3; engine source commit `97aa9b52c231f9aad5ba1403e8ed230d69f4d2a3`. Executed; independent review pending. CLI acceptance is not semantic proof.

| Fixture | Class | Exit | Diagnostics (severity/code/line) |
| --- | --- | ---: | --- |
| recommended | recommended | 0 | none |
| counterexample | D | 0 | none |

Full diagnostic messages, input SHA-256, and commands are in the [manifest](../../../examples/ai-patterns/manifest.json). Meaning review is the author's source comparison, not independent approval.

**Sources:** [Format 1.0](../life_txt_format_spec.md) Profile; AI guide §9; #1164; [Profile](../../../prompts/lifetxt-assistant.md). [source 1](https://github.com/Eruhitsuji/lifetxt/issues/1164#issuecomment-6078516662) / [source 2](https://github.com/Eruhitsuji/lifetxt/issues/1164#issuecomment-6078553354) / [source 3](https://github.com/Eruhitsuji/lifetxt/issues/1164#issuecomment-6079794954) / [source 4](https://github.com/Eruhitsuji/lifetxt/issues/1164#issuecomment-6080057300) / [source 5](../ai-integration.md#9-without-mcp)

<a id="pat-pit-009"></a>

## PAT-PIT-009 — 実取得≠URL提示・自己申告・check≠意味

**Input (original language retained):** 資料URLを提示したが、AIは取得できなかった。構文検査も未実行。入力『2030年10月14日に散歩する』の下書きだけ作る。

**Context:** Fictional example. Fixed baseline: 2030-10-11T12:00:00+09:00; user timezone: Asia/Tokyo. Use only supplied dates, IDs, people, and metadata. Referenced existing records are included for independent validation, not to be appended again to a live workspace.

**Reason:** At generation time disclose unverified retrieval and check not run; that is separate from the catalog author's later validation.

**Pitfall:** For the same line, an unexecuted claim of retrieved sources, passed CLI, and guaranteed meaning is wrong.

Counterexample class: **D (unsupported prose claim)**. Meaning/capability requires source comparison by a person.

**Recommended** ([canonical fixture](../../../examples/ai-patterns/PAT-PIT-009/recommended.life.txt))

<!-- fixture:PAT-PIT-009/recommended -->
````lifetxt
[ ] T "散歩する" do:2030-10-14
````

**counterexample** ([canonical fixture](../../../examples/ai-patterns/PAT-PIT-009/counterexample.life.txt))

<!-- fixture:PAT-PIT-009/counterexample -->
````lifetxt
[ ] T "散歩する" do:2030-10-14
````

**Validation:** Core 1.0.3; engine source commit `97aa9b52c231f9aad5ba1403e8ed230d69f4d2a3`. Executed; independent review pending. CLI acceptance is not semantic proof.

| Fixture | Class | Exit | Diagnostics (severity/code/line) |
| --- | --- | ---: | --- |
| recommended | recommended | 0 | none |
| counterexample | D | 0 | none |

Full diagnostic messages, input SHA-256, and commands are in the [manifest](../../../examples/ai-patterns/manifest.json). Meaning review is the author's source comparison, not independent approval.

**Sources:** [Format 1.0](../life_txt_format_spec.md) Profile; AI guide §9; #1164; [Profile](../../../prompts/lifetxt-assistant.md). [source 1](https://github.com/Eruhitsuji/lifetxt/issues/1164#issuecomment-6078516662) / [source 2](https://github.com/Eruhitsuji/lifetxt/issues/1164#issuecomment-6078553354) / [source 3](https://github.com/Eruhitsuji/lifetxt/issues/1164#issuecomment-6079794954) / [source 4](https://github.com/Eruhitsuji/lifetxt/issues/1164#issuecomment-6080057300) / [source 5](../ai-integration.md#9-without-mcp)

<a id="pat-pit-010"></a>

## PAT-PIT-010 — Reviewの原文保持・初回/修正版の分離

**Input (original language retained):** Review対象は『[ ] T 草案 due:2030-10-20』。元の意図は20日に作業する。原文を保持して修正案を別に返す。

**Context:** Fictional example. Fixed baseline: 2030-10-11T12:00:00+09:00; user timezone: Asia/Tokyo. Use only supplied dates, IDs, people, and metadata. Referenced existing records are included for independent validation, not to be appended again to a live workspace.

**Reason:** Keep the original as a separate wrong-meaning fixture and change only the proposed Review version to do.

**Pitfall:** Initial and corrected versions are not a batch to append together.

Counterexample class: **C (wrong source meaning)**. Meaning/capability requires source comparison by a person.

**Recommended** ([canonical fixture](../../../examples/ai-patterns/PAT-PIT-010/recommended.life.txt))

<!-- fixture:PAT-PIT-010/recommended -->
````lifetxt
[ ] T "草案" do:2030-10-20
````

**counterexample** ([canonical fixture](../../../examples/ai-patterns/PAT-PIT-010/counterexample.life.txt))

<!-- fixture:PAT-PIT-010/counterexample -->
````lifetxt
[ ] T "草案" due:2030-10-20
````

**Validation:** Core 1.0.3; engine source commit `97aa9b52c231f9aad5ba1403e8ed230d69f4d2a3`. Executed; independent review pending. CLI acceptance is not semantic proof.

| Fixture | Class | Exit | Diagnostics (severity/code/line) |
| --- | --- | ---: | --- |
| recommended | recommended | 0 | none |
| counterexample | C | 0 | none |

Full diagnostic messages, input SHA-256, and commands are in the [manifest](../../../examples/ai-patterns/manifest.json). Meaning review is the author's source comparison, not independent approval.

**Sources:** [Format 1.0](../life_txt_format_spec.md) Profile; AI guide §9; #1164; [Profile](../../../prompts/lifetxt-assistant.md). [source 1](https://github.com/Eruhitsuji/lifetxt/issues/1164#issuecomment-6078516662) / [source 2](https://github.com/Eruhitsuji/lifetxt/issues/1164#issuecomment-6078553354) / [source 3](https://github.com/Eruhitsuji/lifetxt/issues/1164#issuecomment-6079794954) / [source 4](https://github.com/Eruhitsuji/lifetxt/issues/1164#issuecomment-6080057300) / [source 5](../ai-integration.md#9-without-mcp)

