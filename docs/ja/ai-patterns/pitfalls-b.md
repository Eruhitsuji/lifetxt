# AI Reference Patterns — Semantic pitfalls / 意味の誤変換

このページのコードはcanonical fixtureのコピー。日英で同じ原文・コードを使う。著者のCore検証と人手の意味照合を区別し、独立reviewはPRで行う。 #1164の失敗類型を基に構成した架空の教育用入力と対照例であり、元の試験prompt/model出力の逐語転載や新たなLLM試験ではない。

[Format 1.0](../life_txt_format_spec.md) / [Profile](../../../prompts/lifetxt-assistant.md) / [Fixture maintenance](../../../examples/ai-patterns/README.md)

<a id="pat-pit-006"></a>

## PAT-PIT-006 — ID・担当・priority等の非創作

**入力（原文保持）:** 牛乳を買う。担当者、priority、project、通知日時は指定しない。

**前提:** 架空例。基準日時は2030-10-11T12:00:00+09:00、利用者TZはAsia/Tokyo。日時は明示されたものだけ使用。ID/人物/metadataは入力に指定したものだけ。例の参照recordも検査文脈として同梱し、既存recordを再追加する手順とはしない。

**理由:** 最小限の行を返す。追加metadataを推測しない。

**注意・反例:** 反例の追加情報は構文的に妥当でも原入力にない。

反例分類: **C (wrong source meaning)**。意味/能力は人が原文と照合する。

**推奨例** ([canonical fixture](../../../examples/ai-patterns/PAT-PIT-006/recommended.life.txt))

<!-- fixture:PAT-PIT-006/recommended -->
````lifetxt
[ ] T "牛乳を買う"
````

**counterexample** ([canonical fixture](../../../examples/ai-patterns/PAT-PIT-006/counterexample.life.txt))

<!-- fixture:PAT-PIT-006/counterexample -->
````lifetxt
[ ] T "牛乳を買う" id:milk project:life priority:A assignee:self
````

**検証:** Core 1.0.3; engine source commit `97aa9b52c231f9aad5ba1403e8ed230d69f4d2a3`. 実測済み。独立reviewは未完了。CLI受理は意味保証ではない。

| Fixture | Class | Exit | Diagnostics (severity/code/line) |
| --- | --- | ---: | --- |
| recommended | recommended | 0 | none |
| counterexample | C | 0 | none |

全診断メッセージ・入力SHA-256・コマンドは[manifest](../../../examples/ai-patterns/manifest.json)に記録。意味レビューは著者による原入力との照合（独立承認ではない）。

**出典:** [Format 1.0](../life_txt_format_spec.md) Profile; AI guide §9; #1164; [Profile](../../../prompts/lifetxt-assistant.md). [source 1](https://github.com/Eruhitsuji/lifetxt/issues/1164#issuecomment-6078516662) / [source 2](https://github.com/Eruhitsuji/lifetxt/issues/1164#issuecomment-6078553354) / [source 3](https://github.com/Eruhitsuji/lifetxt/issues/1164#issuecomment-6079794954) / [source 4](https://github.com/Eruhitsuji/lifetxt/issues/1164#issuecomment-6080057300) / [source 5](../ai-integration.md#9-without-mcp)

<a id="pat-pit-007"></a>

## PAT-PIT-007 — 未知key≠公式候補日・検索機能

**入力（原文保持）:** 会議は2030年10月20日か22日。公式候補日機能を使えるか説明してから下書きを作る。

**前提:** 架空例。基準日時は2030-10-11T12:00:00+09:00、利用者TZはAsia/Tokyo。日時は明示されたものだけ使用。ID/人物/metadataは入力に指定したものだけ。例の参照recordも検査文脈として同梱し、既存recordを再追加する手順とはしない。

**理由:** 既存Formatで候補をnoteへ保持する。custom keyは保持できても標準機能ではない。

**注意・反例:** candidate_onのW106を消すだけでは意味や機能保証は改善しない。

反例分類: **B (validator warning)**。意味/能力は人が原文と照合する。

**推奨例** ([canonical fixture](../../../examples/ai-patterns/PAT-PIT-007/recommended.life.txt))

<!-- fixture:PAT-PIT-007/recommended -->
````lifetxt
[?] E "会議" note:"候補日は2030-10-20または2030-10-22、未確定"
````

**counterexample** ([canonical fixture](../../../examples/ai-patterns/PAT-PIT-007/counterexample.life.txt))

<!-- fixture:PAT-PIT-007/counterexample -->
````lifetxt
[?] E "会議" candidate_on:2030-10-20 candidate_on:2030-10-22
````

**検証:** Core 1.0.3; engine source commit `97aa9b52c231f9aad5ba1403e8ed230d69f4d2a3`. 実測済み。独立reviewは未完了。CLI受理は意味保証ではない。

| Fixture | Class | Exit | Diagnostics (severity/code/line) |
| --- | --- | ---: | --- |
| recommended | recommended | 0 | none |
| counterexample | B | 0 | warning/W106/L1 |

全診断メッセージ・入力SHA-256・コマンドは[manifest](../../../examples/ai-patterns/manifest.json)に記録。意味レビューは著者による原入力との照合（独立承認ではない）。

**出典:** [Format 1.0](../life_txt_format_spec.md) Profile; AI guide §9; #1164; [Profile](../../../prompts/lifetxt-assistant.md). [source 1](https://github.com/Eruhitsuji/lifetxt/issues/1164#issuecomment-6078516662) / [source 2](https://github.com/Eruhitsuji/lifetxt/issues/1164#issuecomment-6078553354) / [source 3](https://github.com/Eruhitsuji/lifetxt/issues/1164#issuecomment-6079794954) / [source 4](https://github.com/Eruhitsuji/lifetxt/issues/1164#issuecomment-6080057300) / [source 5](../ai-integration.md#9-without-mcp)

<a id="pat-pit-008"></a>

## PAT-PIT-008 — 記録≠Teams送信・条件自動実行

**入力（原文保持）:** 2030年10月14日9時にaliceへTeamsで返答依頼を送る記録。回答済みならキャンセルしたいが、その自動処理は設定していない。

**前提:** 架空例。基準日時は2030-10-11T12:00:00+09:00、利用者TZはAsia/Tokyo。日時は明示されたものだけ使用。ID/人物/metadataは入力に指定したものだけ。例の参照recordも検査文脈として同梱し、既存recordを再追加する手順とはしない。

**理由:** 送信要求と条件を記録するだけ。文面や外部接続を創作しない。

**注意・反例:** 反例について『この行で必ずTeams送信と回答時自動取消を行う』という能力主張が誤り。行の構文では検出できない。

反例分類: **D (unsupported prose claim)**。意味/能力は人が原文と照合する。

**推奨例** ([canonical fixture](../../../examples/ai-patterns/PAT-PIT-008/recommended.life.txt))

<!-- fixture:PAT-PIT-008/recommended -->
````lifetxt
[ ] M "返答依頼" sender:self recipient:alice notify_at:2030-10-14T09:00+09:00 channel:teams note:"回答済みの場合の扱いは手動確認。自動送信/自動キャンセルは未設定"
````

**counterexample** ([canonical fixture](../../../examples/ai-patterns/PAT-PIT-008/counterexample.life.txt))

<!-- fixture:PAT-PIT-008/counterexample -->
````lifetxt
[ ] M "返答依頼" sender:self recipient:alice notify_at:2030-10-14T09:00+09:00 channel:teams
````

**検証:** Core 1.0.3; engine source commit `97aa9b52c231f9aad5ba1403e8ed230d69f4d2a3`. 実測済み。独立reviewは未完了。CLI受理は意味保証ではない。

| Fixture | Class | Exit | Diagnostics (severity/code/line) |
| --- | --- | ---: | --- |
| recommended | recommended | 0 | none |
| counterexample | D | 0 | none |

全診断メッセージ・入力SHA-256・コマンドは[manifest](../../../examples/ai-patterns/manifest.json)に記録。意味レビューは著者による原入力との照合（独立承認ではない）。

**出典:** [Format 1.0](../life_txt_format_spec.md) Profile; AI guide §9; #1164; [Profile](../../../prompts/lifetxt-assistant.md). [source 1](https://github.com/Eruhitsuji/lifetxt/issues/1164#issuecomment-6078516662) / [source 2](https://github.com/Eruhitsuji/lifetxt/issues/1164#issuecomment-6078553354) / [source 3](https://github.com/Eruhitsuji/lifetxt/issues/1164#issuecomment-6079794954) / [source 4](https://github.com/Eruhitsuji/lifetxt/issues/1164#issuecomment-6080057300) / [source 5](../ai-integration.md#9-without-mcp)

<a id="pat-pit-009"></a>

## PAT-PIT-009 — 実取得≠URL提示・自己申告・check≠意味

**入力（原文保持）:** 資料URLを提示したが、AIは取得できなかった。構文検査も未実行。入力『2030年10月14日に散歩する』の下書きだけ作る。

**前提:** 架空例。基準日時は2030-10-11T12:00:00+09:00、利用者TZはAsia/Tokyo。日時は明示されたものだけ使用。ID/人物/metadataは入力に指定したものだけ。例の参照recordも検査文脈として同梱し、既存recordを再追加する手順とはしない。

**理由:** 生成時は参照未確認・check not runと明示する。本カタログ著者の後日の実測とは別状態。

**注意・反例:** 同じ行でも『公式資料取得済み・CLI合格・意味保証』という未実行の主張は誤り。

反例分類: **D (unsupported prose claim)**。意味/能力は人が原文と照合する。

**推奨例** ([canonical fixture](../../../examples/ai-patterns/PAT-PIT-009/recommended.life.txt))

<!-- fixture:PAT-PIT-009/recommended -->
````lifetxt
[ ] T "散歩する" do:2030-10-14
````

**counterexample** ([canonical fixture](../../../examples/ai-patterns/PAT-PIT-009/counterexample.life.txt))

<!-- fixture:PAT-PIT-009/counterexample -->
````lifetxt
[ ] T "散歩する" do:2030-10-14
````

**検証:** Core 1.0.3; engine source commit `97aa9b52c231f9aad5ba1403e8ed230d69f4d2a3`. 実測済み。独立reviewは未完了。CLI受理は意味保証ではない。

| Fixture | Class | Exit | Diagnostics (severity/code/line) |
| --- | --- | ---: | --- |
| recommended | recommended | 0 | none |
| counterexample | D | 0 | none |

全診断メッセージ・入力SHA-256・コマンドは[manifest](../../../examples/ai-patterns/manifest.json)に記録。意味レビューは著者による原入力との照合（独立承認ではない）。

**出典:** [Format 1.0](../life_txt_format_spec.md) Profile; AI guide §9; #1164; [Profile](../../../prompts/lifetxt-assistant.md). [source 1](https://github.com/Eruhitsuji/lifetxt/issues/1164#issuecomment-6078516662) / [source 2](https://github.com/Eruhitsuji/lifetxt/issues/1164#issuecomment-6078553354) / [source 3](https://github.com/Eruhitsuji/lifetxt/issues/1164#issuecomment-6079794954) / [source 4](https://github.com/Eruhitsuji/lifetxt/issues/1164#issuecomment-6080057300) / [source 5](../ai-integration.md#9-without-mcp)

<a id="pat-pit-010"></a>

## PAT-PIT-010 — Reviewの原文保持・初回/修正版の分離

**入力（原文保持）:** Review対象は『[ ] T 草案 due:2030-10-20』。元の意図は20日に作業する。原文を保持して修正案を別に返す。

**前提:** 架空例。基準日時は2030-10-11T12:00:00+09:00、利用者TZはAsia/Tokyo。日時は明示されたものだけ使用。ID/人物/metadataは入力に指定したものだけ。例の参照recordも検査文脈として同梱し、既存recordを再追加する手順とはしない。

**理由:** 元行は意味反例として別fixtureに保存し、Review提案だけdoへ修正する。

**注意・反例:** 初回と修正版を1つのworkspaceへ一緒に追加する例ではない。

反例分類: **C (wrong source meaning)**。意味/能力は人が原文と照合する。

**推奨例** ([canonical fixture](../../../examples/ai-patterns/PAT-PIT-010/recommended.life.txt))

<!-- fixture:PAT-PIT-010/recommended -->
````lifetxt
[ ] T "草案" do:2030-10-20
````

**counterexample** ([canonical fixture](../../../examples/ai-patterns/PAT-PIT-010/counterexample.life.txt))

<!-- fixture:PAT-PIT-010/counterexample -->
````lifetxt
[ ] T "草案" due:2030-10-20
````

**検証:** Core 1.0.3; engine source commit `97aa9b52c231f9aad5ba1403e8ed230d69f4d2a3`. 実測済み。独立reviewは未完了。CLI受理は意味保証ではない。

| Fixture | Class | Exit | Diagnostics (severity/code/line) |
| --- | --- | ---: | --- |
| recommended | recommended | 0 | none |
| counterexample | C | 0 | none |

全診断メッセージ・入力SHA-256・コマンドは[manifest](../../../examples/ai-patterns/manifest.json)に記録。意味レビューは著者による原入力との照合（独立承認ではない）。

**出典:** [Format 1.0](../life_txt_format_spec.md) Profile; AI guide §9; #1164; [Profile](../../../prompts/lifetxt-assistant.md). [source 1](https://github.com/Eruhitsuji/lifetxt/issues/1164#issuecomment-6078516662) / [source 2](https://github.com/Eruhitsuji/lifetxt/issues/1164#issuecomment-6078553354) / [source 3](https://github.com/Eruhitsuji/lifetxt/issues/1164#issuecomment-6079794954) / [source 4](https://github.com/Eruhitsuji/lifetxt/issues/1164#issuecomment-6080057300) / [source 5](../ai-integration.md#9-without-mcp)

