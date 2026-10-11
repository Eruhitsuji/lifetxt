# AI Reference Patterns — Statuses / 状態

このページのコードはcanonical fixtureのコピー。日英で同じ原文・コードを使う。著者のCore検証と人手の意味照合を区別し、独立reviewはPRで行う。

[Format 1.0](../life_txt_format_spec.md) / [Profile](../../../prompts/lifetxt-assistant.md) / [Fixture maintenance](../../../examples/ai-patterns/README.md)

<a id="pat-status-001"></a>

## PAT-STATUS-001 — 未完了

**入力（原文保持）:** 資料を準備する。まだ着手していない。

**前提:** 架空例。基準日時は2030-10-11T12:00:00+09:00、利用者TZはAsia/Tokyo。日時は明示されたものだけ使用。ID/人物/metadataは入力に指定したものだけ。例の参照recordも検査文脈として同梱し、既存recordを再追加する手順とはしない。

**理由:** [ ]は未完了で、着手日時を推測しない。

**注意・反例:** 未完了のTaskがすべて期限を必要とするわけではない。

**推奨例** ([canonical fixture](../../../examples/ai-patterns/PAT-STATUS-001/recommended.life.txt))

<!-- fixture:PAT-STATUS-001/recommended -->
````lifetxt
[ ] T "資料を準備する"
````

**検証:** Core 1.0.3; engine source commit `97aa9b52c231f9aad5ba1403e8ed230d69f4d2a3`. 実測済み。独立reviewは未完了。CLI受理は意味保証ではない。

| Fixture | Class | Exit | Diagnostics (severity/code/line) |
| --- | --- | ---: | --- |
| recommended | recommended | 0 | none |

全診断メッセージ・入力SHA-256・コマンドは[manifest](../../../examples/ai-patterns/manifest.json)に記録。意味レビューは著者による原入力との照合（独立承認ではない）。

**出典:** [Format 1.0](../life_txt_format_spec.md) §2, §7.5, §10, §14; [Profile](../../../prompts/lifetxt-assistant.md). [source 1](../../../examples/tasks_life.txt) / [source 2](../../../examples/events_life.txt) / [source 3](../../../examples/messages_life.txt)

<a id="pat-status-002"></a>

## PAT-STATUS-002 — 進行中とprogress/elapsed

**入力（原文保持）:** 資料を作成中。進捗3/10、実作業時間は25分。

**前提:** 架空例。基準日時は2030-10-11T12:00:00+09:00、利用者TZはAsia/Tokyo。日時は明示されたものだけ使用。ID/人物/metadataは入力に指定したものだけ。例の参照recordも検査文脈として同梱し、既存recordを再追加する手順とはしない。

**理由:** [/]と数量的progressは別情報。elapsedには実績時間を記録する。

**注意・反例:** progress:100%でも自動的に[x]にならない。監査履歴は専用機能の文書へ。

**推奨例** ([canonical fixture](../../../examples/ai-patterns/PAT-STATUS-002/recommended.life.txt))

<!-- fixture:PAT-STATUS-002/recommended -->
````lifetxt
[/] T "資料を作成する" progress:3/10 elapsed:25m
````

**検証:** Core 1.0.3; engine source commit `97aa9b52c231f9aad5ba1403e8ed230d69f4d2a3`. 実測済み。独立reviewは未完了。CLI受理は意味保証ではない。

| Fixture | Class | Exit | Diagnostics (severity/code/line) |
| --- | --- | ---: | --- |
| recommended | recommended | 0 | none |

全診断メッセージ・入力SHA-256・コマンドは[manifest](../../../examples/ai-patterns/manifest.json)に記録。意味レビューは著者による原入力との照合（独立承認ではない）。

**出典:** [Format 1.0](../life_txt_format_spec.md) §2, §7.5, §10, §14; [Profile](../../../prompts/lifetxt-assistant.md). [source 1](../../../examples/tasks_life.txt) / [source 2](../../../examples/events_life.txt) / [source 3](../../../examples/messages_life.txt)

<a id="pat-status-003"></a>

## PAT-STATUS-003 — 完了と既知または不明のdone

**入力（原文保持）:** 机の片付けは完了した。完了日は覚えていない。

**前提:** 架空例。基準日時は2030-10-11T12:00:00+09:00、利用者TZはAsia/Tokyo。日時は明示されたものだけ使用。ID/人物/metadataは入力に指定したものだけ。例の参照recordも検査文脈として同梱し、既存recordを再追加する手順とはしない。

**理由:** 完了状態だけを保持する。doneが不明なためW103を意図して残す。

**注意・反例:** warningを消すために現在日をdoneへ書かない。

**推奨例** ([canonical fixture](../../../examples/ai-patterns/PAT-STATUS-003/recommended.life.txt))

<!-- fixture:PAT-STATUS-003/recommended -->
````lifetxt
[x] T "机を片付ける"
````

**検証:** Core 1.0.3; engine source commit `97aa9b52c231f9aad5ba1403e8ed230d69f4d2a3`. 実測済み。独立reviewは未完了。CLI受理は意味保証ではない。

| Fixture | Class | Exit | Diagnostics (severity/code/line) |
| --- | --- | ---: | --- |
| recommended | recommended | 0 | warning/W103/L1 |

全診断メッセージ・入力SHA-256・コマンドは[manifest](../../../examples/ai-patterns/manifest.json)に記録。意味レビューは著者による原入力との照合（独立承認ではない）。

**出典:** [Format 1.0](../life_txt_format_spec.md) §2, §7.5, §10, §14; [Profile](../../../prompts/lifetxt-assistant.md). [source 1](../../../examples/tasks_life.txt) / [source 2](../../../examples/events_life.txt) / [source 3](../../../examples/messages_life.txt)

<a id="pat-status-004"></a>

## PAT-STATUS-004 — キャンセルとreason

**入力（原文保持）:** 夕食会をキャンセルした。理由は参加者不足。

**前提:** 架空例。基準日時は2030-10-11T12:00:00+09:00、利用者TZはAsia/Tokyo。日時は明示されたものだけ使用。ID/人物/metadataは入力に指定したものだけ。例の参照recordも検査文脈として同梱し、既存recordを再追加する手順とはしない。

**理由:** [-]と与えられた理由を保持し、開催日を推測しない。

**注意・反例:** キャンセルは実施成功を意味しない。

**推奨例** ([canonical fixture](../../../examples/ai-patterns/PAT-STATUS-004/recommended.life.txt))

<!-- fixture:PAT-STATUS-004/recommended -->
````lifetxt
[-] E "夕食会" reason:"参加者不足"
````

**検証:** Core 1.0.3; engine source commit `97aa9b52c231f9aad5ba1403e8ed230d69f4d2a3`. 実測済み。独立reviewは未完了。CLI受理は意味保証ではない。

| Fixture | Class | Exit | Diagnostics (severity/code/line) |
| --- | --- | ---: | --- |
| recommended | recommended | 0 | none |

全診断メッセージ・入力SHA-256・コマンドは[manifest](../../../examples/ai-patterns/manifest.json)に記録。意味レビューは著者による原入力との照合（独立承認ではない）。

**出典:** [Format 1.0](../life_txt_format_spec.md) §2, §7.5, §10, §14; [Profile](../../../prompts/lifetxt-assistant.md). [source 1](../../../examples/tasks_life.txt) / [source 2](../../../examples/events_life.txt) / [source 3](../../../examples/messages_life.txt)

<a id="pat-status-005"></a>

## PAT-STATUS-005 — 移動日時moved_toと置換IDの区別

**入力（原文保持）:** 図書返却を2030年10月22日に延期。理由は出張。

**前提:** 架空例。基準日時は2030-10-11T12:00:00+09:00、利用者TZはAsia/Tokyo。日時は明示されたものだけ使用。ID/人物/metadataは入力に指定したものだけ。例の参照recordも検査文脈として同梱し、既存recordを再追加する手順とはしない。

**理由:** 延期先の日時にはmoved_toを使う。置換item IDはreplaced_byで別に表す。

**注意・反例:** moved_toへitem IDを入れない。

反例分類: **B (validator warning)**。意味/能力は人が原文と照合する。

**推奨例** ([canonical fixture](../../../examples/ai-patterns/PAT-STATUS-005/recommended.life.txt))

<!-- fixture:PAT-STATUS-005/recommended -->
````lifetxt
[>] T "図書を返却する" moved_to:2030-10-22 reason:"出張"
````

**counterexample** ([canonical fixture](../../../examples/ai-patterns/PAT-STATUS-005/counterexample.life.txt))

<!-- fixture:PAT-STATUS-005/counterexample -->
````lifetxt
[>] T "図書を返却する" moved_to:return_new
````

**検証:** Core 1.0.3; engine source commit `97aa9b52c231f9aad5ba1403e8ed230d69f4d2a3`. 実測済み。独立reviewは未完了。CLI受理は意味保証ではない。

| Fixture | Class | Exit | Diagnostics (severity/code/line) |
| --- | --- | ---: | --- |
| recommended | recommended | 0 | none |
| counterexample | B | 0 | warning/W203/L1 |

全診断メッセージ・入力SHA-256・コマンドは[manifest](../../../examples/ai-patterns/manifest.json)に記録。意味レビューは著者による原入力との照合（独立承認ではない）。

**出典:** [Format 1.0](../life_txt_format_spec.md) §2, §7.5, §10, §14; [Profile](../../../prompts/lifetxt-assistant.md). [source 1](../../../examples/tasks_life.txt) / [source 2](../../../examples/events_life.txt) / [source 3](../../../examples/messages_life.txt)

<a id="pat-status-006"></a>

## PAT-STATUS-006 — 保留・未確定

**入力（原文保持）:** 顧客との会議は未確定。返答待ち。

**前提:** 架空例。基準日時は2030-10-11T12:00:00+09:00、利用者TZはAsia/Tokyo。日時は明示されたものだけ使用。ID/人物/metadataは入力に指定したものだけ。例の参照recordも検査文脈として同梱し、既存recordを再追加する手順とはしない。

**理由:** [?]で未確定のまま記録する。日時未指定なら省略する。

**注意・反例:** 未確定という理由だけで候補日を作らない。

**推奨例** ([canonical fixture](../../../examples/ai-patterns/PAT-STATUS-006/recommended.life.txt))

<!-- fixture:PAT-STATUS-006/recommended -->
````lifetxt
[?] E "顧客との会議" reason:"返答待ち"
````

**検証:** Core 1.0.3; engine source commit `97aa9b52c231f9aad5ba1403e8ed230d69f4d2a3`. 実測済み。独立reviewは未完了。CLI受理は意味保証ではない。

| Fixture | Class | Exit | Diagnostics (severity/code/line) |
| --- | --- | ---: | --- |
| recommended | recommended | 0 | none |

全診断メッセージ・入力SHA-256・コマンドは[manifest](../../../examples/ai-patterns/manifest.json)に記録。意味レビューは著者による原入力との照合（独立承認ではない）。

**出典:** [Format 1.0](../life_txt_format_spec.md) §2, §7.5, §10, §14; [Profile](../../../prompts/lifetxt-assistant.md). [source 1](../../../examples/tasks_life.txt) / [source 2](../../../examples/events_life.txt) / [source 3](../../../examples/messages_life.txt)

<a id="pat-status-007"></a>

## PAT-STATUS-007 — Note/Journal専用の[N]

**入力（原文保持）:** 設計のメモを残す。Noteを完了Taskとは扱わない。

**前提:** 架空例。基準日時は2030-10-11T12:00:00+09:00、利用者TZはAsia/Tokyo。日時は明示されたものだけ使用。ID/人物/metadataは入力に指定したものだけ。例の参照recordも検査文脈として同梱し、既存recordを再追加する手順とはしない。

**理由:** N/Jの状態は[N]。一般Taskの完了とは異なる。

**注意・反例:** [N] Tは型と状態の不整合を診断される。

反例分類: **B (validator warning)**。意味/能力は人が原文と照合する。

**推奨例** ([canonical fixture](../../../examples/ai-patterns/PAT-STATUS-007/recommended.life.txt))

<!-- fixture:PAT-STATUS-007/recommended -->
````lifetxt
[N] N "設計メモ"
````

**counterexample** ([canonical fixture](../../../examples/ai-patterns/PAT-STATUS-007/counterexample.life.txt))

<!-- fixture:PAT-STATUS-007/counterexample -->
````lifetxt
[N] T "設計メモ"
````

**検証:** Core 1.0.3; engine source commit `97aa9b52c231f9aad5ba1403e8ed230d69f4d2a3`. 実測済み。独立reviewは未完了。CLI受理は意味保証ではない。

| Fixture | Class | Exit | Diagnostics (severity/code/line) |
| --- | --- | ---: | --- |
| recommended | recommended | 0 | none |
| counterexample | B | 0 | warning/W101/L1 |

全診断メッセージ・入力SHA-256・コマンドは[manifest](../../../examples/ai-patterns/manifest.json)に記録。意味レビューは著者による原入力との照合（独立承認ではない）。

**出典:** [Format 1.0](../life_txt_format_spec.md) §2, §7.5, §10, §14; [Profile](../../../prompts/lifetxt-assistant.md). [source 1](../../../examples/tasks_life.txt) / [source 2](../../../examples/events_life.txt) / [source 3](../../../examples/messages_life.txt)

