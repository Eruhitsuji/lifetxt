# AI Reference Patterns — Relationships / 参照・階層

Code blocks copy canonical fixtures. Both languages retain identical source input and code. Author-run Core checks are separate from meaning comparison; independent review takes place on the PR.

[Format 1.0](../life_txt_format_spec.md) / [Profile](../../../prompts/lifetxt-assistant.md) / [Fixture maintenance](../../../examples/ai-patterns/README.md)

<a id="pat-rel-001"></a>

## PAT-REL-001 — id一意性と既存ID文脈

**Input (original language retained):** ユーザー提供の既存ID task_draftで草案を書く。IDはこの文脈内で一意。

**Context:** Fictional example. Fixed baseline: 2030-10-11T12:00:00+09:00; user timezone: Asia/Tokyo. Use only supplied dates, IDs, people, and metadata. Referenced existing records are included for independent validation, not to be appended again to a live workspace.

**Reason:** Use the supplied ID and check uniqueness across all loaded files.

**Pitfall:** Duplicate IDs produce W213 rather than necessarily a parse error.

Counterexample class: **B (validator warning)**. Meaning/capability requires source comparison by a person.

**Recommended** ([canonical fixture](../../../examples/ai-patterns/PAT-REL-001/recommended.life.txt))

<!-- fixture:PAT-REL-001/recommended -->
````lifetxt
[ ] T "草案を書く" id:task_draft
````

**counterexample** ([canonical fixture](../../../examples/ai-patterns/PAT-REL-001/counterexample.life.txt))

<!-- fixture:PAT-REL-001/counterexample -->
````lifetxt
[ ] T "草案を書く" id:task_draft
[ ] T "別の草案" id:task_draft
````

**Validation:** Core 1.0.3; engine source commit `97aa9b52c231f9aad5ba1403e8ed230d69f4d2a3`. Executed; independent review pending. CLI acceptance is not semantic proof.

| Fixture | Class | Exit | Diagnostics (severity/code/line) |
| --- | --- | ---: | --- |
| recommended | recommended | 0 | none |
| counterexample | B | 0 | warning/W213/L2 |

Full diagnostic messages, input SHA-256, and commands are in the [manifest](../../../examples/ai-patterns/manifest.json). Meaning review is the author's source comparison, not independent approval.

**Sources:** [Format 1.0](../life_txt_format_spec.md) §5.1, §7.1–7.2; [Profile](../../../prompts/lifetxt-assistant.md). [source 1](../../../examples/linked_life.txt) / [source 2](../../../examples/hierarchy_life.txt)

<a id="pat-rel-002"></a>

## PAT-REL-002 — parentとインデント推論

**Input (original language retained):** 研究計画(root)、その下に文献調査(lit)、調査の下にメモ。括弧内IDはユーザー提供。

**Context:** Fictional example. Fixed baseline: 2030-10-11T12:00:00+09:00; user timezone: Asia/Tokyo. Use only supplied dates, IDs, people, and metadata. Referenced existing records are included for independent validation, not to be appended again to a live workspace.

**Reason:** Use two-space hierarchy with supplied parent IDs so the parser can infer parent links.

**Pitfall:** A description calling flat records hierarchical does not create a hierarchy.

**Recommended** ([canonical fixture](../../../examples/ai-patterns/PAT-REL-002/recommended.life.txt))

<!-- fixture:PAT-REL-002/recommended -->
````lifetxt
[ ] T "研究計画" id:root
  [ ] T "文献調査" id:lit
    [N] N "文献メモ"
    | 関連研究を要約する。
````

**Validation:** Core 1.0.3; engine source commit `97aa9b52c231f9aad5ba1403e8ed230d69f4d2a3`. Executed; independent review pending. CLI acceptance is not semantic proof.

| Fixture | Class | Exit | Diagnostics (severity/code/line) |
| --- | --- | ---: | --- |
| recommended | recommended | 0 | none |

Full diagnostic messages, input SHA-256, and commands are in the [manifest](../../../examples/ai-patterns/manifest.json). Meaning review is the author's source comparison, not independent approval.

**Sources:** [Format 1.0](../life_txt_format_spec.md) §5.1, §7.1–7.2; [Profile](../../../prompts/lifetxt-assistant.md). [source 1](../../../examples/linked_life.txt) / [source 2](../../../examples/hierarchy_life.txt)

<a id="pat-rel-003"></a>

## PAT-REL-003 — ref/relatedの役割

**Input (original language retained):** ユーザー提供Task draftへのメモmemo。参照ref、参考資料readingとの緩い関連relatedを使う。

**Context:** Fictional example. Fixed baseline: 2030-10-11T12:00:00+09:00; user timezone: Asia/Tokyo. Use only supplied dates, IDs, people, and metadata. Referenced existing records are included for independent validation, not to be appended again to a live workspace.

**Reason:** ref is a generic reference and related a loose association; neither is a prerequisite.

**Pitfall:** Do not silently treat a person's name as an item ID.

**Recommended** ([canonical fixture](../../../examples/ai-patterns/PAT-REL-003/recommended.life.txt))

<!-- fixture:PAT-REL-003/recommended -->
````lifetxt
[ ] T "草案" id:draft
[N] N "参考資料" id:reading
[N] N "草案メモ" id:memo ref:draft related:reading
````

**Validation:** Core 1.0.3; engine source commit `97aa9b52c231f9aad5ba1403e8ed230d69f4d2a3`. Executed; independent review pending. CLI acceptance is not semantic proof.

| Fixture | Class | Exit | Diagnostics (severity/code/line) |
| --- | --- | ---: | --- |
| recommended | recommended | 0 | none |

Full diagnostic messages, input SHA-256, and commands are in the [manifest](../../../examples/ai-patterns/manifest.json). Meaning review is the author's source comparison, not independent approval.

**Sources:** [Format 1.0](../life_txt_format_spec.md) §5.1, §7.1–7.2; [Profile](../../../prompts/lifetxt-assistant.md). [source 1](../../../examples/linked_life.txt) / [source 2](../../../examples/hierarchy_life.txt)

<a id="pat-rel-004"></a>

## PAT-REL-004 — depends_on/blocksの方向と解決状態

**Input (original language retained):** ユーザー提供ID reviewのレビューが終わるまで、submitの提出をしない。

**Context:** Fictional example. Fixed baseline: 2030-10-11T12:00:00+09:00; user timezone: Asia/Tokyo. Use only supplied dates, IDs, people, and metadata. Referenced existing records are included for independent validation, not to be appended again to a live workspace.

**Reason:** depends_on points to the prerequisite; blocks points to the blocked item. Mirrored assertions are optional.

**Pitfall:** Core also resolves canceled prerequisites; successful approval needs separate meaning review.

**Recommended** ([canonical fixture](../../../examples/ai-patterns/PAT-REL-004/recommended.life.txt))

<!-- fixture:PAT-REL-004/recommended -->
````lifetxt
[ ] T "レビューを完了する" id:review blocks:submit
[ ] T "提出する" id:submit depends_on:review
````

**Validation:** Core 1.0.3; engine source commit `97aa9b52c231f9aad5ba1403e8ed230d69f4d2a3`. Executed; independent review pending. CLI acceptance is not semantic proof.

| Fixture | Class | Exit | Diagnostics (severity/code/line) |
| --- | --- | ---: | --- |
| recommended | recommended | 0 | none |

Full diagnostic messages, input SHA-256, and commands are in the [manifest](../../../examples/ai-patterns/manifest.json). Meaning review is the author's source comparison, not independent approval.

**Sources:** [Format 1.0](../life_txt_format_spec.md) §5.1, §7.1–7.2; [Profile](../../../prompts/lifetxt-assistant.md). [source 1](../../../examples/linked_life.txt) / [source 2](../../../examples/hierarchy_life.txt)

<a id="pat-rel-005"></a>

## PAT-REL-005 — duplicate_of/replaced_by

**Input (original language retained):** oldをnewに置き換え、copyはnewの重複。3つのIDはユーザー指定。

**Context:** Fictional example. Fixed baseline: 2030-10-11T12:00:00+09:00; user timezone: Asia/Tokyo. Use only supplied dates, IDs, people, and metadata. Referenced existing records are included for independent validation, not to be appended again to a live workspace.

**Reason:** Store one-direction replacement and duplication relations; these are distinct from a moved_to date. Current Core also emits type-specific custom-key W106 for these link keys. Preserve their specified reference meaning rather than replacing them merely to silence the warning.

**Pitfall:** Do not claim automatic inverse relations or status updates.

**Recommended** ([canonical fixture](../../../examples/ai-patterns/PAT-REL-005/recommended.life.txt))

<!-- fixture:PAT-REL-005/recommended -->
````lifetxt
[>] T "旧手順" id:old replaced_by:new
[ ] T "新手順" id:new
[-] T "重複手順" id:copy duplicate_of:new reason:"重複"
````

**Validation:** Core 1.0.3; engine source commit `97aa9b52c231f9aad5ba1403e8ed230d69f4d2a3`. Executed; independent review pending. CLI acceptance is not semantic proof.

| Fixture | Class | Exit | Diagnostics (severity/code/line) |
| --- | --- | ---: | --- |
| recommended | recommended | 0 | warning/W106/L1; warning/W106/L3 |

Full diagnostic messages, input SHA-256, and commands are in the [manifest](../../../examples/ai-patterns/manifest.json). Meaning review is the author's source comparison, not independent approval.

**Sources:** [Format 1.0](../life_txt_format_spec.md) §5.1, §7.1–7.2; [Profile](../../../prompts/lifetxt-assistant.md). [source 1](../../../examples/linked_life.txt) / [source 2](../../../examples/hierarchy_life.txt)

<a id="pat-rel-006"></a>

## PAT-REL-006 — follows/realizesと非自動推論

**Input (original language retained):** 計画planを実績actualが実現。実績actualはpreviousの次の訪問。IDと日付はユーザー提供。

**Context:** Fictional example. Fixed baseline: 2030-10-11T12:00:00+09:00; user timezone: Asia/Tokyo. Use only supplied dates, IDs, people, and metadata. Referenced existing records are included for independent validation, not to be appended again to a live workspace.

**Reason:** Store actual-to-plan realizes and current-to-previous follows explicitly. Current Core also emits type-specific custom-key W106 for these link keys. Preserve their specified reference meaning rather than replacing them merely to silence the warning.

**Pitfall:** Do not infer edges from nearby dates or persist derived inverse relations.

**Recommended** ([canonical fixture](../../../examples/ai-patterns/PAT-REL-006/recommended.life.txt))

<!-- fixture:PAT-REL-006/recommended -->
````lifetxt
[ ] E "訪問計画" id:plan on:2030-10-14
[x] E "前回訪問" id:previous on:2030-10-07 done:2030-10-07
[x] E "今回訪問" id:actual on:2030-10-14 done:2030-10-14 realizes:plan follows:previous
````

**Validation:** Core 1.0.3; engine source commit `97aa9b52c231f9aad5ba1403e8ed230d69f4d2a3`. Executed; independent review pending. CLI acceptance is not semantic proof.

| Fixture | Class | Exit | Diagnostics (severity/code/line) |
| --- | --- | ---: | --- |
| recommended | recommended | 0 | warning/W106/L3; warning/W106/L3 |

Full diagnostic messages, input SHA-256, and commands are in the [manifest](../../../examples/ai-patterns/manifest.json). Meaning review is the author's source comparison, not independent approval.

**Sources:** [Format 1.0](../life_txt_format_spec.md) §5.1, §7.1–7.2; [Profile](../../../prompts/lifetxt-assistant.md). [source 1](../../../examples/linked_life.txt) / [source 2](../../../examples/hierarchy_life.txt)

<a id="pat-rel-007"></a>

## PAT-REL-007 — 欠落・自己参照・曖昧ID・循環の境界

**Input (original language retained):** 欠落ID、自己参照、曖昧ID、循環を検査する方法を示す。まず独立した正常例aとbを使う。

**Context:** Fictional example. Fixed baseline: 2030-10-11T12:00:00+09:00; user timezone: Asia/Tokyo. Use only supplied dates, IDs, people, and metadata. Referenced existing records are included for independent validation, not to be appended again to a live workspace.

**Reason:** Resolve references within loaded input; check each failure class in a separate fixture.

**Pitfall:** Reference warnings are not parse errors.

Counterexample class: **B (validator warning)**. Meaning/capability requires source comparison by a person.

**Recommended** ([canonical fixture](../../../examples/ai-patterns/PAT-REL-007/recommended.life.txt))

<!-- fixture:PAT-REL-007/recommended -->
````lifetxt
[ ] T "前提" id:a
[ ] T "後続" id:b depends_on:a
````

**counterexample** ([canonical fixture](../../../examples/ai-patterns/PAT-REL-007/counterexample.life.txt))

<!-- fixture:PAT-REL-007/counterexample -->
````lifetxt
[ ] T "前提" id:a depends_on:b
[ ] T "後続" id:b depends_on:a
````

**missing** ([canonical fixture](../../../examples/ai-patterns/PAT-REL-007/missing.life.txt))

<!-- fixture:PAT-REL-007/missing -->
````lifetxt
[ ] T "後続" id:b depends_on:missing
````

**self** ([canonical fixture](../../../examples/ai-patterns/PAT-REL-007/self.life.txt))

<!-- fixture:PAT-REL-007/self -->
````lifetxt
[ ] T "前提" id:a depends_on:a
````

**ambiguous** ([canonical fixture](../../../examples/ai-patterns/PAT-REL-007/ambiguous.life.txt))

<!-- fixture:PAT-REL-007/ambiguous -->
````lifetxt
[ ] T "前提1" id:a
[ ] T "前提2" id:a
[ ] T "後続" id:b depends_on:a
````

**Validation:** Core 1.0.3; engine source commit `97aa9b52c231f9aad5ba1403e8ed230d69f4d2a3`. Executed; independent review pending. CLI acceptance is not semantic proof.

| Fixture | Class | Exit | Diagnostics (severity/code/line) |
| --- | --- | ---: | --- |
| recommended | recommended | 0 | none |
| counterexample | B | 0 | warning/W227/L1 |
| missing | B | 0 | warning/W215/L1 |
| self | B | 0 | warning/W216/L1; warning/W227/L1 |
| ambiguous | B | 0 | warning/W213/L2; warning/W218/L3 |

Full diagnostic messages, input SHA-256, and commands are in the [manifest](../../../examples/ai-patterns/manifest.json). Meaning review is the author's source comparison, not independent approval.

**Sources:** [Format 1.0](../life_txt_format_spec.md) §5.1, §7.1–7.2; [Profile](../../../prompts/lifetxt-assistant.md). [source 1](../../../examples/linked_life.txt) / [source 2](../../../examples/hierarchy_life.txt)

<a id="pat-rel-008"></a>

## PAT-REL-008 — 複数ファイル参照と部分共有

**Input (original language retained):** 別ファイルにある完了済みID review_doneを参照して提出する。既存の完了記録も検査へ同梱する。

**Context:** Fictional example. Fixed baseline: 2030-10-11T12:00:00+09:00; user timezone: Asia/Tokyo. Use only supplied dates, IDs, people, and metadata. Referenced existing records are included for independent validation, not to be appended again to a live workspace.

**Reason:** The standalone fixture includes existing reference context; only the submission line is a new-workspace proposal.

**Pitfall:** An unshared target's state must not be guessed.

Counterexample class: **B (validator warning)**. Meaning/capability requires source comparison by a person.

**Recommended** ([canonical fixture](../../../examples/ai-patterns/PAT-REL-008/recommended.life.txt))

<!-- fixture:PAT-REL-008/recommended -->
````lifetxt
[x] T "レビュー完了" id:review_done done:2030-10-11
[ ] T "提出する" depends_on:review_done
````

**counterexample** ([canonical fixture](../../../examples/ai-patterns/PAT-REL-008/counterexample.life.txt))

<!-- fixture:PAT-REL-008/counterexample -->
````lifetxt
[ ] T "提出する" depends_on:review_done
````

**Validation:** Core 1.0.3; engine source commit `97aa9b52c231f9aad5ba1403e8ed230d69f4d2a3`. Executed; independent review pending. CLI acceptance is not semantic proof.

| Fixture | Class | Exit | Diagnostics (severity/code/line) |
| --- | --- | ---: | --- |
| recommended | recommended | 0 | none |
| counterexample | B | 0 | warning/W215/L1 |

Full diagnostic messages, input SHA-256, and commands are in the [manifest](../../../examples/ai-patterns/manifest.json). Meaning review is the author's source comparison, not independent approval.

**Sources:** [Format 1.0](../life_txt_format_spec.md) §5.1, §7.1–7.2; [Profile](../../../prompts/lifetxt-assistant.md). [source 1](../../../examples/linked_life.txt) / [source 2](../../../examples/hierarchy_life.txt)

