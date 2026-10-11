# AI Reference Patterns — Relationships / 参照・階層

このページのコードはcanonical fixtureのコピー。日英で同じ原文・コードを使う。著者のCore検証と人手の意味照合を区別し、独立reviewはPRで行う。

[Format 1.0](../life_txt_format_spec.md) / [Profile](../../../prompts/lifetxt-assistant.md) / [Fixture maintenance](../../../examples/ai-patterns/README.md)

<a id="pat-rel-001"></a>

## PAT-REL-001 — id一意性と既存ID文脈

**入力（原文保持）:** ユーザー提供の既存ID task_draftで草案を書く。IDはこの文脈内で一意。

**前提:** 架空例。基準日時は2030-10-11T12:00:00+09:00、利用者TZはAsia/Tokyo。日時は明示されたものだけ使用。ID/人物/metadataは入力に指定したものだけ。例の参照recordも検査文脈として同梱し、既存recordを再追加する手順とはしない。

**理由:** 明示されたIDだけを使い、loaded files全体で一意性を確認する。

**注意・反例:** 同じIDの重複はW213であり必ずしもparse errorではない。

反例分類: **B (validator warning)**。意味/能力は人が原文と照合する。

**推奨例** ([canonical fixture](../../../examples/ai-patterns/PAT-REL-001/recommended.life.txt))

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

**検証:** Core 1.0.3; engine source commit `97aa9b52c231f9aad5ba1403e8ed230d69f4d2a3`. 実測済み。独立reviewは未完了。CLI受理は意味保証ではない。

| Fixture | Class | Exit | Diagnostics (severity/code/line) |
| --- | --- | ---: | --- |
| recommended | recommended | 0 | none |
| counterexample | B | 0 | warning/W213/L2 |

全診断メッセージ・入力SHA-256・コマンドは[manifest](../../../examples/ai-patterns/manifest.json)に記録。意味レビューは著者による原入力との照合（独立承認ではない）。

**出典:** [Format 1.0](../life_txt_format_spec.md) §5.1, §7.1–7.2; [Profile](../../../prompts/lifetxt-assistant.md). [source 1](../../../examples/linked_life.txt) / [source 2](../../../examples/hierarchy_life.txt)

<a id="pat-rel-002"></a>

## PAT-REL-002 — parentとインデント推論

**入力（原文保持）:** 研究計画(root)、その下に文献調査(lit)、調査の下にメモ。括弧内IDはユーザー提供。

**前提:** 架空例。基準日時は2030-10-11T12:00:00+09:00、利用者TZはAsia/Tokyo。日時は明示されたものだけ使用。ID/人物/metadataは入力に指定したものだけ。例の参照recordも検査文脈として同梱し、既存recordを再追加する手順とはしない。

**理由:** 2スペース階層を使い、parserのparent推論が可能な既存IDを持たせる。

**注意・反例:** フラットなレコードを説明だけで階層と呼ばない。

**推奨例** ([canonical fixture](../../../examples/ai-patterns/PAT-REL-002/recommended.life.txt))

<!-- fixture:PAT-REL-002/recommended -->
````lifetxt
[ ] T "研究計画" id:root
  [ ] T "文献調査" id:lit
    [N] N "文献メモ"
    | 関連研究を要約する。
````

**検証:** Core 1.0.3; engine source commit `97aa9b52c231f9aad5ba1403e8ed230d69f4d2a3`. 実測済み。独立reviewは未完了。CLI受理は意味保証ではない。

| Fixture | Class | Exit | Diagnostics (severity/code/line) |
| --- | --- | ---: | --- |
| recommended | recommended | 0 | none |

全診断メッセージ・入力SHA-256・コマンドは[manifest](../../../examples/ai-patterns/manifest.json)に記録。意味レビューは著者による原入力との照合（独立承認ではない）。

**出典:** [Format 1.0](../life_txt_format_spec.md) §5.1, §7.1–7.2; [Profile](../../../prompts/lifetxt-assistant.md). [source 1](../../../examples/linked_life.txt) / [source 2](../../../examples/hierarchy_life.txt)

<a id="pat-rel-003"></a>

## PAT-REL-003 — ref/relatedの役割

**入力（原文保持）:** ユーザー提供Task draftへのメモmemo。参照ref、参考資料readingとの緩い関連relatedを使う。

**前提:** 架空例。基準日時は2030-10-11T12:00:00+09:00、利用者TZはAsia/Tokyo。日時は明示されたものだけ使用。ID/人物/metadataは入力に指定したものだけ。例の参照recordも検査文脈として同梱し、既存recordを再追加する手順とはしない。

**理由:** refは一般参照、relatedは緩い関連で、作業の前提条件とは異なる。

**注意・反例:** 人名をitem IDとして勝手に参照しない。

**推奨例** ([canonical fixture](../../../examples/ai-patterns/PAT-REL-003/recommended.life.txt))

<!-- fixture:PAT-REL-003/recommended -->
````lifetxt
[ ] T "草案" id:draft
[N] N "参考資料" id:reading
[N] N "草案メモ" id:memo ref:draft related:reading
````

**検証:** Core 1.0.3; engine source commit `97aa9b52c231f9aad5ba1403e8ed230d69f4d2a3`. 実測済み。独立reviewは未完了。CLI受理は意味保証ではない。

| Fixture | Class | Exit | Diagnostics (severity/code/line) |
| --- | --- | ---: | --- |
| recommended | recommended | 0 | none |

全診断メッセージ・入力SHA-256・コマンドは[manifest](../../../examples/ai-patterns/manifest.json)に記録。意味レビューは著者による原入力との照合（独立承認ではない）。

**出典:** [Format 1.0](../life_txt_format_spec.md) §5.1, §7.1–7.2; [Profile](../../../prompts/lifetxt-assistant.md). [source 1](../../../examples/linked_life.txt) / [source 2](../../../examples/hierarchy_life.txt)

<a id="pat-rel-004"></a>

## PAT-REL-004 — depends_on/blocksの方向と解決状態

**入力（原文保持）:** ユーザー提供ID reviewのレビューが終わるまで、submitの提出をしない。

**前提:** 架空例。基準日時は2030-10-11T12:00:00+09:00、利用者TZはAsia/Tokyo。日時は明示されたものだけ使用。ID/人物/metadataは入力に指定したものだけ。例の参照recordも検査文脈として同梱し、既存recordを再追加する手順とはしない。

**理由:** depends_onは待つ側→前提、blocksは前提→待つ側。両方の記録は必須ではない。

**注意・反例:** Coreはキャンセル済み前提も解決扱いにする。成功承認は別に意味確認する。

**推奨例** ([canonical fixture](../../../examples/ai-patterns/PAT-REL-004/recommended.life.txt))

<!-- fixture:PAT-REL-004/recommended -->
````lifetxt
[ ] T "レビューを完了する" id:review blocks:submit
[ ] T "提出する" id:submit depends_on:review
````

**検証:** Core 1.0.3; engine source commit `97aa9b52c231f9aad5ba1403e8ed230d69f4d2a3`. 実測済み。独立reviewは未完了。CLI受理は意味保証ではない。

| Fixture | Class | Exit | Diagnostics (severity/code/line) |
| --- | --- | ---: | --- |
| recommended | recommended | 0 | none |

全診断メッセージ・入力SHA-256・コマンドは[manifest](../../../examples/ai-patterns/manifest.json)に記録。意味レビューは著者による原入力との照合（独立承認ではない）。

**出典:** [Format 1.0](../life_txt_format_spec.md) §5.1, §7.1–7.2; [Profile](../../../prompts/lifetxt-assistant.md). [source 1](../../../examples/linked_life.txt) / [source 2](../../../examples/hierarchy_life.txt)

<a id="pat-rel-005"></a>

## PAT-REL-005 — duplicate_of/replaced_by

**入力（原文保持）:** oldをnewに置き換え、copyはnewの重複。3つのIDはユーザー指定。

**前提:** 架空例。基準日時は2030-10-11T12:00:00+09:00、利用者TZはAsia/Tokyo。日時は明示されたものだけ使用。ID/人物/metadataは入力に指定したものだけ。例の参照recordも検査文脈として同梱し、既存recordを再追加する手順とはしない。

**理由:** 置換・重複の方向をそれぞれ明記する。moved_toとは異なるID関係。現Coreはこれらのlink keyをtype別のcustomとしてW106も出す。公式の参照意味は保持し、warningを消すために別keyへ変換しない。

**注意・反例:** 逆関係や状態変更が自動生成されるとは言わない。

**推奨例** ([canonical fixture](../../../examples/ai-patterns/PAT-REL-005/recommended.life.txt))

<!-- fixture:PAT-REL-005/recommended -->
````lifetxt
[>] T "旧手順" id:old replaced_by:new
[ ] T "新手順" id:new
[-] T "重複手順" id:copy duplicate_of:new reason:"重複"
````

**検証:** Core 1.0.3; engine source commit `97aa9b52c231f9aad5ba1403e8ed230d69f4d2a3`. 実測済み。独立reviewは未完了。CLI受理は意味保証ではない。

| Fixture | Class | Exit | Diagnostics (severity/code/line) |
| --- | --- | ---: | --- |
| recommended | recommended | 0 | warning/W106/L1; warning/W106/L3 |

全診断メッセージ・入力SHA-256・コマンドは[manifest](../../../examples/ai-patterns/manifest.json)に記録。意味レビューは著者による原入力との照合（独立承認ではない）。

**出典:** [Format 1.0](../life_txt_format_spec.md) §5.1, §7.1–7.2; [Profile](../../../prompts/lifetxt-assistant.md). [source 1](../../../examples/linked_life.txt) / [source 2](../../../examples/hierarchy_life.txt)

<a id="pat-rel-006"></a>

## PAT-REL-006 — follows/realizesと非自動推論

**入力（原文保持）:** 計画planを実績actualが実現。実績actualはpreviousの次の訪問。IDと日付はユーザー提供。

**前提:** 架空例。基準日時は2030-10-11T12:00:00+09:00、利用者TZはAsia/Tokyo。日時は明示されたものだけ使用。ID/人物/metadataは入力に指定したものだけ。例の参照recordも検査文脈として同梱し、既存recordを再追加する手順とはしない。

**理由:** actual→planのrealizes、current→previousのfollowsを明示する。現Coreはこれらのlink keyをtype別のcustomとしてW106も出す。公式の参照意味は保持し、warningを消すために別keyへ変換しない。

**注意・反例:** 日付の近さだけで関係を推測しない。導出逆関係を保存しない。

**推奨例** ([canonical fixture](../../../examples/ai-patterns/PAT-REL-006/recommended.life.txt))

<!-- fixture:PAT-REL-006/recommended -->
````lifetxt
[ ] E "訪問計画" id:plan on:2030-10-14
[x] E "前回訪問" id:previous on:2030-10-07 done:2030-10-07
[x] E "今回訪問" id:actual on:2030-10-14 done:2030-10-14 realizes:plan follows:previous
````

**検証:** Core 1.0.3; engine source commit `97aa9b52c231f9aad5ba1403e8ed230d69f4d2a3`. 実測済み。独立reviewは未完了。CLI受理は意味保証ではない。

| Fixture | Class | Exit | Diagnostics (severity/code/line) |
| --- | --- | ---: | --- |
| recommended | recommended | 0 | warning/W106/L3; warning/W106/L3 |

全診断メッセージ・入力SHA-256・コマンドは[manifest](../../../examples/ai-patterns/manifest.json)に記録。意味レビューは著者による原入力との照合（独立承認ではない）。

**出典:** [Format 1.0](../life_txt_format_spec.md) §5.1, §7.1–7.2; [Profile](../../../prompts/lifetxt-assistant.md). [source 1](../../../examples/linked_life.txt) / [source 2](../../../examples/hierarchy_life.txt)

<a id="pat-rel-007"></a>

## PAT-REL-007 — 欠落・自己参照・曖昧ID・循環の境界

**入力（原文保持）:** 欠落ID、自己参照、曖昧ID、循環を検査する方法を示す。まず独立した正常例aとbを使う。

**前提:** 架空例。基準日時は2030-10-11T12:00:00+09:00、利用者TZはAsia/Tokyo。日時は明示されたものだけ使用。ID/人物/metadataは入力に指定したものだけ。例の参照recordも検査文脈として同梱し、既存recordを再追加する手順とはしない。

**理由:** 参照はloaded input内で解決する。各異常は別fixtureとして検査する。

**注意・反例:** 参照warningをsyntax errorと呼ばない。

反例分類: **B (validator warning)**。意味/能力は人が原文と照合する。

**推奨例** ([canonical fixture](../../../examples/ai-patterns/PAT-REL-007/recommended.life.txt))

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

**検証:** Core 1.0.3; engine source commit `97aa9b52c231f9aad5ba1403e8ed230d69f4d2a3`. 実測済み。独立reviewは未完了。CLI受理は意味保証ではない。

| Fixture | Class | Exit | Diagnostics (severity/code/line) |
| --- | --- | ---: | --- |
| recommended | recommended | 0 | none |
| counterexample | B | 0 | warning/W227/L1 |
| missing | B | 0 | warning/W215/L1 |
| self | B | 0 | warning/W216/L1; warning/W227/L1 |
| ambiguous | B | 0 | warning/W213/L2; warning/W218/L3 |

全診断メッセージ・入力SHA-256・コマンドは[manifest](../../../examples/ai-patterns/manifest.json)に記録。意味レビューは著者による原入力との照合（独立承認ではない）。

**出典:** [Format 1.0](../life_txt_format_spec.md) §5.1, §7.1–7.2; [Profile](../../../prompts/lifetxt-assistant.md). [source 1](../../../examples/linked_life.txt) / [source 2](../../../examples/hierarchy_life.txt)

<a id="pat-rel-008"></a>

## PAT-REL-008 — 複数ファイル参照と部分共有

**入力（原文保持）:** 別ファイルにある完了済みID review_doneを参照して提出する。既存の完了記録も検査へ同梱する。

**前提:** 架空例。基準日時は2030-10-11T12:00:00+09:00、利用者TZはAsia/Tokyo。日時は明示されたものだけ使用。ID/人物/metadataは入力に指定したものだけ。例の参照recordも検査文脈として同梱し、既存recordを再追加する手順とはしない。

**理由:** 独立検証fixtureには既存参照文脈を含める。実workspaceへの追加提案は提出行だけ。

**注意・反例:** 部分共有で参照先が未共有なら状態を推測しない。

反例分類: **B (validator warning)**。意味/能力は人が原文と照合する。

**推奨例** ([canonical fixture](../../../examples/ai-patterns/PAT-REL-008/recommended.life.txt))

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

**検証:** Core 1.0.3; engine source commit `97aa9b52c231f9aad5ba1403e8ed230d69f4d2a3`. 実測済み。独立reviewは未完了。CLI受理は意味保証ではない。

| Fixture | Class | Exit | Diagnostics (severity/code/line) |
| --- | --- | ---: | --- |
| recommended | recommended | 0 | none |
| counterexample | B | 0 | warning/W215/L1 |

全診断メッセージ・入力SHA-256・コマンドは[manifest](../../../examples/ai-patterns/manifest.json)に記録。意味レビューは著者による原入力との照合（独立承認ではない）。

**出典:** [Format 1.0](../life_txt_format_spec.md) §5.1, §7.1–7.2; [Profile](../../../prompts/lifetxt-assistant.md). [source 1](../../../examples/linked_life.txt) / [source 2](../../../examples/hierarchy_life.txt)

