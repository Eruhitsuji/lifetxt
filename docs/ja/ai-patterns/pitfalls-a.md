# AI Reference Patterns — Semantic pitfalls / 意味の誤変換

このページのコードはcanonical fixtureのコピー。日英で同じ原文・コードを使う。著者のCore検証と人手の意味照合を区別し、独立reviewはPRで行う。 #1164の失敗類型を基に構成した架空の教育用入力と対照例であり、元の試験prompt/model出力の逐語転載や新たなLLM試験ではない。

[Format 1.0](../life_txt_format_spec.md) / [Profile](../../../prompts/lifetxt-assistant.md) / [Fixture maintenance](../../../examples/ai-patterns/README.md)

<a id="pat-pit-001"></a>

## PAT-PIT-001 — 排他的候補日≠期間・確定日

**入力（原文保持）:** 顧客との会議は2030年10月20日か22日のどちらか1日、希望14〜15時30分。返答待ち。場所未定。

**前提:** 架空例。基準日時は2030-10-11T12:00:00+09:00、利用者TZはAsia/Tokyo。日時は明示されたものだけ使用。ID/人物/metadataは入力に指定したものだけ。例の参照recordも検査文脈として同梱し、既存recordを再追加する手順とはしない。

**理由:** 排他的候補をnoteに保持し、確定on/from/toを創作しない。

**注意・反例:** 反例は構文が通っても2日以上の区間へ意味を変える。

反例分類: **C (wrong source meaning)**。意味/能力は人が原文と照合する。

**推奨例** ([canonical fixture](../../../examples/ai-patterns/PAT-PIT-001/recommended.life.txt))

<!-- fixture:PAT-PIT-001/recommended -->
````lifetxt
[?] E "顧客との会議" note:"2030-10-20または2030-10-22のどちらか1日、希望14:00-15:30、返答待ち、場所未定"
````

**counterexample** ([canonical fixture](../../../examples/ai-patterns/PAT-PIT-001/counterexample.life.txt))

<!-- fixture:PAT-PIT-001/counterexample -->
````lifetxt
[ ] E "顧客との会議" from:2030-10-20T14:00+09:00 to:2030-10-22T15:30+09:00
````

**検証:** Core 1.0.3; engine source commit `97aa9b52c231f9aad5ba1403e8ed230d69f4d2a3`. 実測済み。独立reviewは未完了。CLI受理は意味保証ではない。

| Fixture | Class | Exit | Diagnostics (severity/code/line) |
| --- | --- | ---: | --- |
| recommended | recommended | 0 | none |
| counterexample | C | 0 | none |

全診断メッセージ・入力SHA-256・コマンドは[manifest](../../../examples/ai-patterns/manifest.json)に記録。意味レビューは著者による原入力との照合（独立承認ではない）。

**出典:** [Format 1.0](../life_txt_format_spec.md) Profile; AI guide §9; #1164; [Profile](../../../prompts/lifetxt-assistant.md). [source 1](https://github.com/Eruhitsuji/lifetxt/issues/1164#issuecomment-6078516662) / [source 2](https://github.com/Eruhitsuji/lifetxt/issues/1164#issuecomment-6078553354) / [source 3](https://github.com/Eruhitsuji/lifetxt/issues/1164#issuecomment-6079794954) / [source 4](https://github.com/Eruhitsuji/lifetxt/issues/1164#issuecomment-6080057300) / [source 5](../ai-integration.md#9-without-mcp)

<a id="pat-pit-002"></a>

## PAT-PIT-002 — レビュー依頼≠完了

**入力（原文保持）:** 既存ID requestのレビュー依頼は送信済み（2030年10月11日）。ID completeのレビューはまだ未完了。提出はレビュー完了まで待つ。

**前提:** 架空例。基準日時は2030-10-11T12:00:00+09:00、利用者TZはAsia/Tokyo。日時は明示されたものだけ使用。ID/人物/metadataは入力に指定したものだけ。例の参照recordも検査文脈として同梱し、既存recordを再追加する手順とはしない。

**理由:** 提出の依存先は必要な達成状態を持つcompleteで、依頼requestではない。

**注意・反例:** IDはこの架空workspace入力で提供済み。無指定の変換へ勝手に追加しない。

反例分類: **C (wrong source meaning)**。意味/能力は人が原文と照合する。

**推奨例** ([canonical fixture](../../../examples/ai-patterns/PAT-PIT-002/recommended.life.txt))

<!-- fixture:PAT-PIT-002/recommended -->
````lifetxt
[x] T "レビューを依頼する" id:request done:2030-10-11
[ ] T "レビューを完了する" id:complete
[ ] T "提出する" depends_on:complete
````

**counterexample** ([canonical fixture](../../../examples/ai-patterns/PAT-PIT-002/counterexample.life.txt))

<!-- fixture:PAT-PIT-002/counterexample -->
````lifetxt
[x] T "レビューを依頼する" id:request done:2030-10-11
[ ] T "レビューを完了する" id:complete
[ ] T "提出する" depends_on:request
````

**検証:** Core 1.0.3; engine source commit `97aa9b52c231f9aad5ba1403e8ed230d69f4d2a3`. 実測済み。独立reviewは未完了。CLI受理は意味保証ではない。

| Fixture | Class | Exit | Diagnostics (severity/code/line) |
| --- | --- | ---: | --- |
| recommended | recommended | 0 | none |
| counterexample | C | 0 | none |

全診断メッセージ・入力SHA-256・コマンドは[manifest](../../../examples/ai-patterns/manifest.json)に記録。意味レビューは著者による原入力との照合（独立承認ではない）。

**出典:** [Format 1.0](../life_txt_format_spec.md) Profile; AI guide §9; #1164; [Profile](../../../prompts/lifetxt-assistant.md). [source 1](https://github.com/Eruhitsuji/lifetxt/issues/1164#issuecomment-6078516662) / [source 2](https://github.com/Eruhitsuji/lifetxt/issues/1164#issuecomment-6078553354) / [source 3](https://github.com/Eruhitsuji/lifetxt/issues/1164#issuecomment-6079794954) / [source 4](https://github.com/Eruhitsuji/lifetxt/issues/1164#issuecomment-6080057300) / [source 5](../ai-integration.md#9-without-mcp)

<a id="pat-pit-003"></a>

## PAT-PIT-003 — 完了・キャンセル≠成功・承認

**入力（原文保持）:** レビューID reviewはキャンセル済み。提出にはレビュー成功の承認が必要だが、承認record/IDは未提供。

**前提:** 架空例。基準日時は2030-10-11T12:00:00+09:00、利用者TZはAsia/Tokyo。日時は明示されたものだけ使用。ID/人物/metadataは入力に指定したものだけ。例の参照recordも検査文脈として同梱し、既存recordを再追加する手順とはしない。

**理由:** Coreがキャンセル前提を解決扱いにしても成功承認の証拠ではない。不明な依存先を質問する。

**注意・反例:** Coreの依存解決と業務上の成功条件を別に確認する。

反例分類: **C (wrong source meaning)**。意味/能力は人が原文と照合する。

**推奨例** ([canonical fixture](../../../examples/ai-patterns/PAT-PIT-003/recommended.life.txt))

<!-- fixture:PAT-PIT-003/recommended -->
````lifetxt
[?] T "提出する" note:"レビュー成功の承認が必要。承認record/ID未提供のため依存先は未確定"
[-] T "レビューする" id:review reason:"中止"
````

**counterexample** ([canonical fixture](../../../examples/ai-patterns/PAT-PIT-003/counterexample.life.txt))

<!-- fixture:PAT-PIT-003/counterexample -->
````lifetxt
[-] T "レビューする" id:review reason:"中止"
[ ] T "提出する" depends_on:review
````

**検証:** Core 1.0.3; engine source commit `97aa9b52c231f9aad5ba1403e8ed230d69f4d2a3`. 実測済み。独立reviewは未完了。CLI受理は意味保証ではない。

| Fixture | Class | Exit | Diagnostics (severity/code/line) |
| --- | --- | ---: | --- |
| recommended | recommended | 0 | none |
| counterexample | C | 0 | none |

全診断メッセージ・入力SHA-256・コマンドは[manifest](../../../examples/ai-patterns/manifest.json)に記録。意味レビューは著者による原入力との照合（独立承認ではない）。

**出典:** [Format 1.0](../life_txt_format_spec.md) Profile; AI guide §9; #1164; [Profile](../../../prompts/lifetxt-assistant.md). [source 1](https://github.com/Eruhitsuji/lifetxt/issues/1164#issuecomment-6078516662) / [source 2](https://github.com/Eruhitsuji/lifetxt/issues/1164#issuecomment-6078553354) / [source 3](https://github.com/Eruhitsuji/lifetxt/issues/1164#issuecomment-6079794954) / [source 4](https://github.com/Eruhitsuji/lifetxt/issues/1164#issuecomment-6080057300) / [source 5](../ai-integration.md#9-without-mcp)

<a id="pat-pit-004"></a>

## PAT-PIT-004 — do≠due・条件評価日≠期限

**入力（原文保持）:** 2030年10月20日に進捗を確認し、遅れていれば相談する。確認日を締切とは指定しない。

**前提:** 架空例。基準日時は2030-10-11T12:00:00+09:00、利用者TZはAsia/Tokyo。日時は明示されたものだけ使用。ID/人物/metadataは入力に指定したものだけ。例の参照recordも検査文脈として同梱し、既存recordを再追加する手順とはしない。

**理由:** 条件を評価する予定はdo。条件付きの説明はnoteに保ち、dueへ変えない。

**注意・反例:** 遅延判定や相談Taskの自動発火を約束しない。

反例分類: **C (wrong source meaning)**。意味/能力は人が原文と照合する。

**推奨例** ([canonical fixture](../../../examples/ai-patterns/PAT-PIT-004/recommended.life.txt))

<!-- fixture:PAT-PIT-004/recommended -->
````lifetxt
[ ] T "進捗を確認する" do:2030-10-20 note:"遅れていれば相談する（条件の自動評価は設定していない）"
````

**counterexample** ([canonical fixture](../../../examples/ai-patterns/PAT-PIT-004/counterexample.life.txt))

<!-- fixture:PAT-PIT-004/counterexample -->
````lifetxt
[ ] T "進捗を確認する" due:2030-10-20
````

**検証:** Core 1.0.3; engine source commit `97aa9b52c231f9aad5ba1403e8ed230d69f4d2a3`. 実測済み。独立reviewは未完了。CLI受理は意味保証ではない。

| Fixture | Class | Exit | Diagnostics (severity/code/line) |
| --- | --- | ---: | --- |
| recommended | recommended | 0 | none |
| counterexample | C | 0 | none |

全診断メッセージ・入力SHA-256・コマンドは[manifest](../../../examples/ai-patterns/manifest.json)に記録。意味レビューは著者による原入力との照合（独立承認ではない）。

**出典:** [Format 1.0](../life_txt_format_spec.md) Profile; AI guide §9; #1164; [Profile](../../../prompts/lifetxt-assistant.md). [source 1](https://github.com/Eruhitsuji/lifetxt/issues/1164#issuecomment-6078516662) / [source 2](https://github.com/Eruhitsuji/lifetxt/issues/1164#issuecomment-6078553354) / [source 3](https://github.com/Eruhitsuji/lifetxt/issues/1164#issuecomment-6079794954) / [source 4](https://github.com/Eruhitsuji/lifetxt/issues/1164#issuecomment-6080057300) / [source 5](../ai-integration.md#9-without-mcp)

<a id="pat-pit-005"></a>

## PAT-PIT-005 — 未共有参照・人物名≠ID

**入力（原文保持）:** 佐藤さんのレビューを待って提出する。レビューrecordのIDは共有していない。

**前提:** 架空例。基準日時は2030-10-11T12:00:00+09:00、利用者TZはAsia/Tokyo。日時は明示されたものだけ使用。ID/人物/metadataは入力に指定したものだけ。例の参照recordも検査文脈として同梱し、既存recordを再追加する手順とはしない。

**理由:** 人名はitem IDではない。未共有IDを創作せず条件を保持する。

**注意・反例:** 反例ではID形式と参照欠落がwarningになるが、人手の意図照合も必要。

反例分類: **B (validator warning)**。意味/能力は人が原文と照合する。

**推奨例** ([canonical fixture](../../../examples/ai-patterns/PAT-PIT-005/recommended.life.txt))

<!-- fixture:PAT-PIT-005/recommended -->
````lifetxt
[?] T "提出する" note:"佐藤さんのレビュー完了待ち。依存先IDを確認する"
````

**counterexample** ([canonical fixture](../../../examples/ai-patterns/PAT-PIT-005/counterexample.life.txt))

<!-- fixture:PAT-PIT-005/counterexample -->
````lifetxt
[ ] T "提出する" depends_on:佐藤さん
````

**検証:** Core 1.0.3; engine source commit `97aa9b52c231f9aad5ba1403e8ed230d69f4d2a3`. 実測済み。独立reviewは未完了。CLI受理は意味保証ではない。

| Fixture | Class | Exit | Diagnostics (severity/code/line) |
| --- | --- | ---: | --- |
| recommended | recommended | 0 | none |
| counterexample | B | 0 | warning/W214/L1; warning/W215/L1 |

全診断メッセージ・入力SHA-256・コマンドは[manifest](../../../examples/ai-patterns/manifest.json)に記録。意味レビューは著者による原入力との照合（独立承認ではない）。

**出典:** [Format 1.0](../life_txt_format_spec.md) Profile; AI guide §9; #1164; [Profile](../../../prompts/lifetxt-assistant.md). [source 1](https://github.com/Eruhitsuji/lifetxt/issues/1164#issuecomment-6078516662) / [source 2](https://github.com/Eruhitsuji/lifetxt/issues/1164#issuecomment-6078553354) / [source 3](https://github.com/Eruhitsuji/lifetxt/issues/1164#issuecomment-6079794954) / [source 4](https://github.com/Eruhitsuji/lifetxt/issues/1164#issuecomment-6080057300) / [source 5](../ai-integration.md#9-without-mcp)

