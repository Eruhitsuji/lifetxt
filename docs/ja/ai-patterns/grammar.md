# AI Reference Patterns — Grammar / 文法・本文

このページのコードはcanonical fixtureのコピー。日英で同じ原文・コードを使う。著者のCore検証と人手の意味照合を区別し、独立reviewはPRで行う。

[Format 1.0](../life_txt_format_spec.md) / [Profile](../../../prompts/lifetxt-assistant.md) / [Fixture maintenance](../../../examples/ai-patterns/README.md)

<a id="pat-gram-001"></a>

## PAT-GRAM-001 — bare/quoted titleとkey:value

**入力（原文保持）:** スペースを含む『Write Report』というTask。場所はRoom A、日付2030年10月14日に実施。

**前提:** 架空例。基準日時は2030-10-11T12:00:00+09:00、利用者TZはAsia/Tokyo。日時は明示されたものだけ使用。ID/人物/metadataは入力に指定したものだけ。例の参照recordも検査文脈として同梱し、既存recordを再追加する手順とはしない。

**理由:** スペースを含むtitle/valueを引用し、ファイルではkey:valueを使う。bare titleは空白なしの場合に使える。

**注意・反例:** CLI helperのkey=value便利入力とファイル文法を混同しない。

反例分類: **A (syntax error)**。意味/能力は人が原文と照合する。

**推奨例** ([canonical fixture](../../../examples/ai-patterns/PAT-GRAM-001/recommended.life.txt))

<!-- fixture:PAT-GRAM-001/recommended -->
````lifetxt
[ ] T "Write Report" do:2030-10-14 loc:"Room A"
````

**counterexample** ([canonical fixture](../../../examples/ai-patterns/PAT-GRAM-001/counterexample.life.txt))

<!-- fixture:PAT-GRAM-001/counterexample -->
````lifetxt
[ ] T "Write Report" do=2030-10-14
````

**検証:** Core 1.0.3; engine source commit `97aa9b52c231f9aad5ba1403e8ed230d69f4d2a3`. 実測済み。独立reviewは未完了。CLI受理は意味保証ではない。

| Fixture | Class | Exit | Diagnostics (severity/code/line) |
| --- | --- | ---: | --- |
| recommended | recommended | 0 | none |
| counterexample | A | 1 | error/E010/L1 |

全診断メッセージ・入力SHA-256・コマンドは[manifest](../../../examples/ai-patterns/manifest.json)に記録。意味レビューは著者による原入力との照合（独立承認ではない）。

**出典:** [Format 1.0](../life_txt_format_spec.md) §1.1, §4–7, §11–12, §15–16; [Profile](../../../prompts/lifetxt-assistant.md). [source 1](../../../examples/json_roundtrip_life.txt) / [source 2](../../../examples/markdown_life.txt) / [source 3](../../../examples/attachments_life.txt)

<a id="pat-gram-002"></a>

## PAT-GRAM-002 — 引用符・backslashのescape

**入力（原文保持）:** メモのtitleは『"life.txt"を読む』、noteは文字列『C:\docs』。

**前提:** 架空例。基準日時は2030-10-11T12:00:00+09:00、利用者TZはAsia/Tokyo。日時は明示されたものだけ使用。ID/人物/metadataは入力に指定したものだけ。例の参照recordも検査文脈として同梱し、既存recordを再追加する手順とはしない。

**理由:** 引用文字列内でdouble quoteとbackslashをescapeする。

**注意・反例:** JSONのescape層とlife.txtのescape層を区別する。

**推奨例** ([canonical fixture](../../../examples/ai-patterns/PAT-GRAM-002/recommended.life.txt))

<!-- fixture:PAT-GRAM-002/recommended -->
````lifetxt
[N] N "\"life.txt\"を読む" note:"C:\\docs"
````

**検証:** Core 1.0.3; engine source commit `97aa9b52c231f9aad5ba1403e8ed230d69f4d2a3`. 実測済み。独立reviewは未完了。CLI受理は意味保証ではない。

| Fixture | Class | Exit | Diagnostics (severity/code/line) |
| --- | --- | ---: | --- |
| recommended | recommended | 0 | none |

全診断メッセージ・入力SHA-256・コマンドは[manifest](../../../examples/ai-patterns/manifest.json)に記録。意味レビューは著者による原入力との照合（独立承認ではない）。

**出典:** [Format 1.0](../life_txt_format_spec.md) §1.1, §4–7, §11–12, §15–16; [Profile](../../../prompts/lifetxt-assistant.md). [source 1](../../../examples/json_roundtrip_life.txt) / [source 2](../../../examples/markdown_life.txt) / [source 3](../../../examples/attachments_life.txt)

<a id="pat-gram-003"></a>

## PAT-GRAM-003 — 反復keyと人物役割・tag

**入力（原文保持）:** 資料Taskの責任者alice、担当bob、tagは重要と研究。会議参加者はaliceとbob。

**前提:** 架空例。基準日時は2030-10-11T12:00:00+09:00、利用者TZはAsia/Tokyo。日時は明示されたものだけ使用。ID/人物/metadataは入力に指定したものだけ。例の参照recordも検査文脈として同梱し、既存recordを再追加する手順とはしない。

**理由:** 反復keyで複数値を表し、人物の役割はowner/assignee/attendeeで区別する。

**注意・反例:** カンマ連結を人物2人の構造として勝手に解釈しない。

**推奨例** ([canonical fixture](../../../examples/ai-patterns/PAT-GRAM-003/recommended.life.txt))

<!-- fixture:PAT-GRAM-003/recommended -->
````lifetxt
[ ] T "資料を作る" owner:alice assignee:bob tag:重要 tag:研究
[ ] E "会議" on:2030-10-14 attendee:alice attendee:bob
````

**検証:** Core 1.0.3; engine source commit `97aa9b52c231f9aad5ba1403e8ed230d69f4d2a3`. 実測済み。独立reviewは未完了。CLI受理は意味保証ではない。

| Fixture | Class | Exit | Diagnostics (severity/code/line) |
| --- | --- | ---: | --- |
| recommended | recommended | 0 | none |

全診断メッセージ・入力SHA-256・コマンドは[manifest](../../../examples/ai-patterns/manifest.json)に記録。意味レビューは著者による原入力との照合（独立承認ではない）。

**出典:** [Format 1.0](../life_txt_format_spec.md) §1.1, §4–7, §11–12, §15–16; [Profile](../../../prompts/lifetxt-assistant.md). [source 1](../../../examples/json_roundtrip_life.txt) / [source 2](../../../examples/markdown_life.txt) / [source 3](../../../examples/attachments_life.txt)

<a id="pat-gram-004"></a>

## PAT-GRAM-004 — custom keyの保持と意味の限界

**入力（原文保持）:** 候補日は2030年10月20日。candidate_onというユーザー指定custom keyで保存したい。

**前提:** 架空例。基準日時は2030-10-11T12:00:00+09:00、利用者TZはAsia/Tokyo。日時は明示されたものだけ使用。ID/人物/metadataは入力に指定したものだけ。例の参照recordも検査文脈として同梱し、既存recordを再追加する手順とはしない。

**理由:** custom keyを保持する。W106は意図した診断で、公式候補日機能を示さない。

**注意・反例:** 日時検索やスケジュール展開の保証をしない。

**推奨例** ([canonical fixture](../../../examples/ai-patterns/PAT-GRAM-004/recommended.life.txt))

<!-- fixture:PAT-GRAM-004/recommended -->
````lifetxt
[?] E "候補の会議" candidate_on:2030-10-20
````

**検証:** Core 1.0.3; engine source commit `97aa9b52c231f9aad5ba1403e8ed230d69f4d2a3`. 実測済み。独立reviewは未完了。CLI受理は意味保証ではない。

| Fixture | Class | Exit | Diagnostics (severity/code/line) |
| --- | --- | ---: | --- |
| recommended | recommended | 0 | warning/W106/L1 |

全診断メッセージ・入力SHA-256・コマンドは[manifest](../../../examples/ai-patterns/manifest.json)に記録。意味レビューは著者による原入力との照合（独立承認ではない）。

**出典:** [Format 1.0](../life_txt_format_spec.md) §1.1, §4–7, §11–12, §15–16; [Profile](../../../prompts/lifetxt-assistant.md). [source 1](../../../examples/json_roundtrip_life.txt) / [source 2](../../../examples/markdown_life.txt) / [source 3](../../../examples/attachments_life.txt)

<a id="pat-gram-005"></a>

## PAT-GRAM-005 — 物理行backslash継続と不正境界

**入力（原文保持）:** 長いTask行を物理行2行で記述する。2030年10月20日締切。

**前提:** 架空例。基準日時は2030-10-11T12:00:00+09:00、利用者TZはAsia/Tokyo。日時は明示されたものだけ使用。ID/人物/metadataは入力に指定したものだけ。例の参照recordも検査文脈として同梱し、既存recordを再追加する手順とはしない。

**理由:** 末尾backslashは次の物理行を結合し、継続行の先頭空白を除く。

**注意・反例:** EOFの裸のbackslashは不正。bodyの|行へ結合しない。

反例分類: **A (syntax error)**。意味/能力は人が原文と照合する。

**推奨例** ([canonical fixture](../../../examples/ai-patterns/PAT-GRAM-005/recommended.life.txt))

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

**検証:** Core 1.0.3; engine source commit `97aa9b52c231f9aad5ba1403e8ed230d69f4d2a3`. 実測済み。独立reviewは未完了。CLI受理は意味保証ではない。

| Fixture | Class | Exit | Diagnostics (severity/code/line) |
| --- | --- | ---: | --- |
| recommended | recommended | 0 | none |
| counterexample | A | 1 | error/E020/L1; warning/W003/L1 |
| joined-body | A | 1 | error/E021/L2; error/E010/L1; error/E010/L1; error/E010/L1 |

全診断メッセージ・入力SHA-256・コマンドは[manifest](../../../examples/ai-patterns/manifest.json)に記録。意味レビューは著者による原入力との照合（独立承認ではない）。

**出典:** [Format 1.0](../life_txt_format_spec.md) §1.1, §4–7, §11–12, §15–16; [Profile](../../../prompts/lifetxt-assistant.md). [source 1](../../../examples/json_roundtrip_life.txt) / [source 2](../../../examples/markdown_life.txt) / [source 3](../../../examples/attachments_life.txt)

<a id="pat-gram-006"></a>

## PAT-GRAM-006 — body継続・空行・孤立継続

**入力（原文保持）:** 設計メモの本文を2段落で残す。第一段落は目的、第二段落は制約。

**前提:** 架空例。基準日時は2030-10-11T12:00:00+09:00、利用者TZはAsia/Tokyo。日時は明示されたものだけ使用。ID/人物/metadataは入力に指定したものだけ。例の参照recordも検査文脈として同梱し、既存recordを再追加する手順とはしない。

**理由:** |行は直前recordのbodyになり、裸の|は空の本文行。

**注意・反例:** 先行recordなしの孤立|は構文エラー。

反例分類: **A (syntax error)**。意味/能力は人が原文と照合する。

**推奨例** ([canonical fixture](../../../examples/ai-patterns/PAT-GRAM-006/recommended.life.txt))

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

**検証:** Core 1.0.3; engine source commit `97aa9b52c231f9aad5ba1403e8ed230d69f4d2a3`. 実測済み。独立reviewは未完了。CLI受理は意味保証ではない。

| Fixture | Class | Exit | Diagnostics (severity/code/line) |
| --- | --- | ---: | --- |
| recommended | recommended | 0 | none |
| counterexample | A | 1 | error/E019/L1 |

全診断メッセージ・入力SHA-256・コマンドは[manifest](../../../examples/ai-patterns/manifest.json)に記録。意味レビューは著者による原入力との照合（独立承認ではない）。

**出典:** [Format 1.0](../life_txt_format_spec.md) §1.1, §4–7, §11–12, §15–16; [Profile](../../../prompts/lifetxt-assistant.md). [source 1](../../../examples/json_roundtrip_life.txt) / [source 2](../../../examples/markdown_life.txt) / [source 3](../../../examples/attachments_life.txt)

<a id="pat-gram-007"></a>

## PAT-GRAM-007 — Markdown本文・HTML非実行

**入力（原文保持）:** メモ本文にMarkdown見出し、太字、リスト、コード例をそのまま保存する。

**前提:** 架空例。基準日時は2030-10-11T12:00:00+09:00、利用者TZはAsia/Tokyo。日時は明示されたものだけ使用。ID/人物/metadataは入力に指定したものだけ。例の参照recordも検査文脈として同梱し、既存recordを再追加する手順とはしない。

**理由:** Markdownはbodyの表示用。parserは原文を保持し、record文法は変えない。

**注意・反例:** raw HTMLはsafe rendererでescapeされ、コード例は実行しない。

**推奨例** ([canonical fixture](../../../examples/ai-patterns/PAT-GRAM-007/recommended.life.txt))

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

**検証:** Core 1.0.3; engine source commit `97aa9b52c231f9aad5ba1403e8ed230d69f4d2a3`. 実測済み。独立reviewは未完了。CLI受理は意味保証ではない。

| Fixture | Class | Exit | Diagnostics (severity/code/line) |
| --- | --- | ---: | --- |
| recommended | recommended | 0 | none |

全診断メッセージ・入力SHA-256・コマンドは[manifest](../../../examples/ai-patterns/manifest.json)に記録。意味レビューは著者による原入力との照合（独立承認ではない）。

**出典:** [Format 1.0](../life_txt_format_spec.md) §1.1, §4–7, §11–12, §15–16; [Profile](../../../prompts/lifetxt-assistant.md). [source 1](../../../examples/json_roundtrip_life.txt) / [source 2](../../../examples/markdown_life.txt) / [source 3](../../../examples/attachments_life.txt)

<a id="pat-gram-008"></a>

## PAT-GRAM-008 — コメント・ヘッダー・file/dir・opaque暗号値

**入力（原文保持）:** 日本時間のファイルで、資料参照と暗号化済みopaque値をメモする。サンプル暗号文字列は復号可能性を保証しない。外部から取得したイベントのsourceはics、uidとidはevent-2030@example.com、2030年10月14日開催、参照URLはhttps://example.com/event。

**前提:** 架空例。基準日時は2030-10-11T12:00:00+09:00、利用者TZはAsia/Tokyo。日時は明示されたものだけ使用。ID/人物/metadataは入力に指定したものだけ。例の参照recordも検査文脈として同梱し、既存recordを再追加する手順とはしない。

**理由:** これはheader/commentを含むdocument例。file/dirはlife.txtの場所を基準に解決し、enc値はopaqueに保存する。

**注意・反例:** checkの通常検査は存在/ハッシュ確認や復号検証とは別。鍵や秘密を例へ入れない。

**推奨例** ([canonical fixture](../../../examples/ai-patterns/PAT-GRAM-008/recommended.life.txt))

<!-- fixture:PAT-GRAM-008/recommended -->
````lifetxt
#! timezone: Asia/Tokyo
# 資料は相対パス参照で保持
[N] N "資料メモ" file:../../../docs/en/life_txt_format_spec.md dir:../../../docs/en note:enc:XSK:QUJD
[ ] E "取り込んだ予定" on:2030-10-14 source:ics uid:event-2030@example.com id:event-2030@example.com url:https://example.com/event
````

**検証:** Core 1.0.3; engine source commit `97aa9b52c231f9aad5ba1403e8ed230d69f4d2a3`. 実測済み。独立reviewは未完了。CLI受理は意味保証ではない。

| Fixture | Class | Exit | Diagnostics (severity/code/line) |
| --- | --- | ---: | --- |
| recommended | recommended | 0 | none |

全診断メッセージ・入力SHA-256・コマンドは[manifest](../../../examples/ai-patterns/manifest.json)に記録。意味レビューは著者による原入力との照合（独立承認ではない）。

**出典:** [Format 1.0](../life_txt_format_spec.md) §1.1, §4–7, §11–12, §15–16; [Profile](../../../prompts/lifetxt-assistant.md). [source 1](../../../examples/json_roundtrip_life.txt) / [source 2](../../../examples/markdown_life.txt) / [source 3](../../../examples/attachments_life.txt)

