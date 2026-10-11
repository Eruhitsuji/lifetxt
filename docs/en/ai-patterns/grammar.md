# AI Reference Patterns — Grammar / 文法・本文

Code blocks copy canonical fixtures. Both languages retain identical source input and code. Author-run Core checks are separate from meaning comparison; independent review takes place on the PR.

[Format 1.0](../life_txt_format_spec.md) / [Profile](../../../prompts/lifetxt-assistant.md) / [Fixture maintenance](../../../examples/ai-patterns/README.md)

<a id="pat-gram-001"></a>

## PAT-GRAM-001 — bare/quoted titleとkey:value

**Input (original language retained):** スペースを含む『Write Report』というTask。場所はRoom A、日付2030年10月14日に実施。

**Context:** Fictional example. Fixed baseline: 2030-10-11T12:00:00+09:00; user timezone: Asia/Tokyo. Use only supplied dates, IDs, people, and metadata. Referenced existing records are included for independent validation, not to be appended again to a live workspace.

**Reason:** Quote titles and values with spaces and use key:value in files; bare titles are allowed without spaces.

**Pitfall:** Do not confuse CLI helper key=value input with file syntax.

Counterexample class: **A (syntax error)**. Meaning/capability requires source comparison by a person.

**Recommended** ([canonical fixture](../../../examples/ai-patterns/PAT-GRAM-001/recommended.life.txt))

<!-- fixture:PAT-GRAM-001/recommended -->
````lifetxt
[ ] T "Write Report" do:2030-10-14 loc:"Room A"
````

**counterexample** ([canonical fixture](../../../examples/ai-patterns/PAT-GRAM-001/counterexample.life.txt))

<!-- fixture:PAT-GRAM-001/counterexample -->
````lifetxt
[ ] T "Write Report" do=2030-10-14
````

**Validation:** Core 1.0.3; engine source commit `97aa9b52c231f9aad5ba1403e8ed230d69f4d2a3`. Executed; independent review pending. CLI acceptance is not semantic proof.

| Fixture | Class | Exit | Diagnostics (severity/code/line) |
| --- | --- | ---: | --- |
| recommended | recommended | 0 | none |
| counterexample | A | 1 | error/E010/L1 |

Full diagnostic messages, input SHA-256, and commands are in the [manifest](../../../examples/ai-patterns/manifest.json). Meaning review is the author's source comparison, not independent approval.

**Sources:** [Format 1.0](../life_txt_format_spec.md) §1.1, §4–7, §11–12, §15–16; [Profile](../../../prompts/lifetxt-assistant.md). [source 1](../../../examples/json_roundtrip_life.txt) / [source 2](../../../examples/markdown_life.txt) / [source 3](../../../examples/attachments_life.txt)

<a id="pat-gram-002"></a>

## PAT-GRAM-002 — 引用符・backslashのescape

**Input (original language retained):** メモのtitleは『"life.txt"を読む』、noteは文字列『C:\docs』。

**Context:** Fictional example. Fixed baseline: 2030-10-11T12:00:00+09:00; user timezone: Asia/Tokyo. Use only supplied dates, IDs, people, and metadata. Referenced existing records are included for independent validation, not to be appended again to a live workspace.

**Reason:** Escape double quotes and backslashes inside quoted strings.

**Pitfall:** JSON escaping and life.txt escaping are separate layers.

**Recommended** ([canonical fixture](../../../examples/ai-patterns/PAT-GRAM-002/recommended.life.txt))

<!-- fixture:PAT-GRAM-002/recommended -->
````lifetxt
[N] N "\"life.txt\"を読む" note:"C:\\docs"
````

**Validation:** Core 1.0.3; engine source commit `97aa9b52c231f9aad5ba1403e8ed230d69f4d2a3`. Executed; independent review pending. CLI acceptance is not semantic proof.

| Fixture | Class | Exit | Diagnostics (severity/code/line) |
| --- | --- | ---: | --- |
| recommended | recommended | 0 | none |

Full diagnostic messages, input SHA-256, and commands are in the [manifest](../../../examples/ai-patterns/manifest.json). Meaning review is the author's source comparison, not independent approval.

**Sources:** [Format 1.0](../life_txt_format_spec.md) §1.1, §4–7, §11–12, §15–16; [Profile](../../../prompts/lifetxt-assistant.md). [source 1](../../../examples/json_roundtrip_life.txt) / [source 2](../../../examples/markdown_life.txt) / [source 3](../../../examples/attachments_life.txt)

<a id="pat-gram-003"></a>

## PAT-GRAM-003 — 反復keyと人物役割・tag

**Input (original language retained):** 資料Taskの責任者alice、担当bob、tagは重要と研究。会議参加者はaliceとbob。

**Context:** Fictional example. Fixed baseline: 2030-10-11T12:00:00+09:00; user timezone: Asia/Tokyo. Use only supplied dates, IDs, people, and metadata. Referenced existing records are included for independent validation, not to be appended again to a live workspace.

**Reason:** Repeat keys for multiple values and distinguish accountable owner, assignee, and attendees.

**Pitfall:** A comma-joined string is not automatically two structured people.

**Recommended** ([canonical fixture](../../../examples/ai-patterns/PAT-GRAM-003/recommended.life.txt))

<!-- fixture:PAT-GRAM-003/recommended -->
````lifetxt
[ ] T "資料を作る" owner:alice assignee:bob tag:重要 tag:研究
[ ] E "会議" on:2030-10-14 attendee:alice attendee:bob
````

**Validation:** Core 1.0.3; engine source commit `97aa9b52c231f9aad5ba1403e8ed230d69f4d2a3`. Executed; independent review pending. CLI acceptance is not semantic proof.

| Fixture | Class | Exit | Diagnostics (severity/code/line) |
| --- | --- | ---: | --- |
| recommended | recommended | 0 | none |

Full diagnostic messages, input SHA-256, and commands are in the [manifest](../../../examples/ai-patterns/manifest.json). Meaning review is the author's source comparison, not independent approval.

**Sources:** [Format 1.0](../life_txt_format_spec.md) §1.1, §4–7, §11–12, §15–16; [Profile](../../../prompts/lifetxt-assistant.md). [source 1](../../../examples/json_roundtrip_life.txt) / [source 2](../../../examples/markdown_life.txt) / [source 3](../../../examples/attachments_life.txt)

<a id="pat-gram-004"></a>

## PAT-GRAM-004 — custom keyの保持と意味の限界

**Input (original language retained):** 候補日は2030年10月20日。candidate_onというユーザー指定custom keyで保存したい。

**Context:** Fictional example. Fixed baseline: 2030-10-11T12:00:00+09:00; user timezone: Asia/Tokyo. Use only supplied dates, IDs, people, and metadata. Referenced existing records are included for independent validation, not to be appended again to a live workspace.

**Reason:** Preserve the requested custom key; intentional W106 does not confer standard candidate-date semantics.

**Pitfall:** Do not promise standard temporal search or scheduling support for this key.

**Recommended** ([canonical fixture](../../../examples/ai-patterns/PAT-GRAM-004/recommended.life.txt))

<!-- fixture:PAT-GRAM-004/recommended -->
````lifetxt
[?] E "候補の会議" candidate_on:2030-10-20
````

**Validation:** Core 1.0.3; engine source commit `97aa9b52c231f9aad5ba1403e8ed230d69f4d2a3`. Executed; independent review pending. CLI acceptance is not semantic proof.

| Fixture | Class | Exit | Diagnostics (severity/code/line) |
| --- | --- | ---: | --- |
| recommended | recommended | 0 | warning/W106/L1 |

Full diagnostic messages, input SHA-256, and commands are in the [manifest](../../../examples/ai-patterns/manifest.json). Meaning review is the author's source comparison, not independent approval.

**Sources:** [Format 1.0](../life_txt_format_spec.md) §1.1, §4–7, §11–12, §15–16; [Profile](../../../prompts/lifetxt-assistant.md). [source 1](../../../examples/json_roundtrip_life.txt) / [source 2](../../../examples/markdown_life.txt) / [source 3](../../../examples/attachments_life.txt)

<a id="pat-gram-005"></a>

## PAT-GRAM-005 — 物理行backslash継続と不正境界

**Input (original language retained):** 長いTask行を物理行2行で記述する。2030年10月20日締切。

**Context:** Fictional example. Fixed baseline: 2030-10-11T12:00:00+09:00; user timezone: Asia/Tokyo. Use only supplied dates, IDs, people, and metadata. Referenced existing records are included for independent validation, not to be appended again to a live workspace.

**Reason:** A trailing backslash joins physical lines and strips leading spaces on the continued line.

**Pitfall:** A bare trailing backslash at EOF is invalid; do not join into a | body line.

Counterexample class: **A (syntax error)**. Meaning/capability requires source comparison by a person.

**Recommended** ([canonical fixture](../../../examples/ai-patterns/PAT-GRAM-005/recommended.life.txt))

<!-- fixture:PAT-GRAM-005/recommended -->
````lifetxt
[ ] T "資料を提出する" \
  due:2030-10-20
````

**counterexample** ([canonical fixture](../../../examples/ai-patterns/PAT-GRAM-005/counterexample.life.txt))

<!-- fixture:PAT-GRAM-005/counterexample -->
````lifetxt
[ ] T "資料を提出する" \
````

**joined-body** ([canonical fixture](../../../examples/ai-patterns/PAT-GRAM-005/joined-body.life.txt))

<!-- fixture:PAT-GRAM-005/joined-body -->
````lifetxt
[ ] T "Task" \
| joined body
````

**Validation:** Core 1.0.3; engine source commit `97aa9b52c231f9aad5ba1403e8ed230d69f4d2a3`. Executed; independent review pending. CLI acceptance is not semantic proof.

| Fixture | Class | Exit | Diagnostics (severity/code/line) |
| --- | --- | ---: | --- |
| recommended | recommended | 0 | none |
| counterexample | A | 1 | error/E020/L1; warning/W003/L1 |
| joined-body | A | 1 | error/E021/L2; error/E010/L1; error/E010/L1; error/E010/L1 |

Full diagnostic messages, input SHA-256, and commands are in the [manifest](../../../examples/ai-patterns/manifest.json). Meaning review is the author's source comparison, not independent approval.

**Sources:** [Format 1.0](../life_txt_format_spec.md) §1.1, §4–7, §11–12, §15–16; [Profile](../../../prompts/lifetxt-assistant.md). [source 1](../../../examples/json_roundtrip_life.txt) / [source 2](../../../examples/markdown_life.txt) / [source 3](../../../examples/attachments_life.txt)

<a id="pat-gram-006"></a>

## PAT-GRAM-006 — body継続・空行・孤立継続

**Input (original language retained):** 設計メモの本文を2段落で残す。第一段落は目的、第二段落は制約。

**Context:** Fictional example. Fixed baseline: 2030-10-11T12:00:00+09:00; user timezone: Asia/Tokyo. Use only supplied dates, IDs, people, and metadata. Referenced existing records are included for independent validation, not to be appended again to a live workspace.

**Reason:** | lines attach body to the previous record; a bare | preserves a blank body line.

**Pitfall:** A | line without a preceding record is a syntax error.

Counterexample class: **A (syntax error)**. Meaning/capability requires source comparison by a person.

**Recommended** ([canonical fixture](../../../examples/ai-patterns/PAT-GRAM-006/recommended.life.txt))

<!-- fixture:PAT-GRAM-006/recommended -->
````lifetxt
[N] N "設計メモ"
| 目的を整理する。
|
| 制約を記録する。
````

**counterexample** ([canonical fixture](../../../examples/ai-patterns/PAT-GRAM-006/counterexample.life.txt))

<!-- fixture:PAT-GRAM-006/counterexample -->
````lifetxt
| 孤立した本文
````

**Validation:** Core 1.0.3; engine source commit `97aa9b52c231f9aad5ba1403e8ed230d69f4d2a3`. Executed; independent review pending. CLI acceptance is not semantic proof.

| Fixture | Class | Exit | Diagnostics (severity/code/line) |
| --- | --- | ---: | --- |
| recommended | recommended | 0 | none |
| counterexample | A | 1 | error/E019/L1 |

Full diagnostic messages, input SHA-256, and commands are in the [manifest](../../../examples/ai-patterns/manifest.json). Meaning review is the author's source comparison, not independent approval.

**Sources:** [Format 1.0](../life_txt_format_spec.md) §1.1, §4–7, §11–12, §15–16; [Profile](../../../prompts/lifetxt-assistant.md). [source 1](../../../examples/json_roundtrip_life.txt) / [source 2](../../../examples/markdown_life.txt) / [source 3](../../../examples/attachments_life.txt)

<a id="pat-gram-007"></a>

## PAT-GRAM-007 — Markdown本文・HTML非実行

**Input (original language retained):** メモ本文にMarkdown見出し、太字、リスト、コード例をそのまま保存する。

**Context:** Fictional example. Fixed baseline: 2030-10-11T12:00:00+09:00; user timezone: Asia/Tokyo. Use only supplied dates, IDs, people, and metadata. Referenced existing records are included for independent validation, not to be appended again to a live workspace.

**Reason:** Markdown is display markup in the body; the parser preserves text without changing record grammar.

**Pitfall:** Safe renderers escape raw HTML and do not execute code examples.

**Recommended** ([canonical fixture](../../../examples/ai-patterns/PAT-GRAM-007/recommended.life.txt))

<!-- fixture:PAT-GRAM-007/recommended -->
````lifetxt
[N] N "Markdownメモ"
| ## 方針
| **原文を保存**
| - 後で確認
| ```python
| print("example")
| ```
````

**Validation:** Core 1.0.3; engine source commit `97aa9b52c231f9aad5ba1403e8ed230d69f4d2a3`. Executed; independent review pending. CLI acceptance is not semantic proof.

| Fixture | Class | Exit | Diagnostics (severity/code/line) |
| --- | --- | ---: | --- |
| recommended | recommended | 0 | none |

Full diagnostic messages, input SHA-256, and commands are in the [manifest](../../../examples/ai-patterns/manifest.json). Meaning review is the author's source comparison, not independent approval.

**Sources:** [Format 1.0](../life_txt_format_spec.md) §1.1, §4–7, §11–12, §15–16; [Profile](../../../prompts/lifetxt-assistant.md). [source 1](../../../examples/json_roundtrip_life.txt) / [source 2](../../../examples/markdown_life.txt) / [source 3](../../../examples/attachments_life.txt)

<a id="pat-gram-008"></a>

## PAT-GRAM-008 — コメント・ヘッダー・file/dir・opaque暗号値

**Input (original language retained):** 日本時間のファイルで、資料参照と暗号化済みopaque値をメモする。サンプル暗号文字列は復号可能性を保証しない。外部から取得したイベントのsourceはics、uidとidはevent-2030@example.com、2030年10月14日開催、参照URLはhttps://example.com/event。

**Context:** Fictional example. Fixed baseline: 2030-10-11T12:00:00+09:00; user timezone: Asia/Tokyo. Use only supplied dates, IDs, people, and metadata. Referenced existing records are included for independent validation, not to be appended again to a live workspace.

**Reason:** This is a document-level example with header/comments; attachments resolve from the life.txt location and enc text remains opaque.

**Pitfall:** Ordinary check is separate from file/hash verification and decryption; never embed keys or secrets.

**Recommended** ([canonical fixture](../../../examples/ai-patterns/PAT-GRAM-008/recommended.life.txt))

<!-- fixture:PAT-GRAM-008/recommended -->
````lifetxt
#! timezone: Asia/Tokyo
# 資料は相対パス参照で保持
[N] N "資料メモ" file:../../../docs/en/life_txt_format_spec.md dir:../../../docs/en note:enc:XSK:QUJD
[ ] E "取り込んだ予定" on:2030-10-14 source:ics uid:event-2030@example.com id:event-2030@example.com url:https://example.com/event
````

**Validation:** Core 1.0.3; engine source commit `97aa9b52c231f9aad5ba1403e8ed230d69f4d2a3`. Executed; independent review pending. CLI acceptance is not semantic proof.

| Fixture | Class | Exit | Diagnostics (severity/code/line) |
| --- | --- | ---: | --- |
| recommended | recommended | 0 | none |

Full diagnostic messages, input SHA-256, and commands are in the [manifest](../../../examples/ai-patterns/manifest.json). Meaning review is the author's source comparison, not independent approval.

**Sources:** [Format 1.0](../life_txt_format_spec.md) §1.1, §4–7, §11–12, §15–16; [Profile](../../../prompts/lifetxt-assistant.md). [source 1](../../../examples/json_roundtrip_life.txt) / [source 2](../../../examples/markdown_life.txt) / [source 3](../../../examples/attachments_life.txt)

