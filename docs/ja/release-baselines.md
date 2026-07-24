# Review済みrelease baseline

Release baselineは、既存のtechnical debtを明示しながら、それが黙って増えることを防ぎます。包括的な無視設定ではありません。

## Translation baseline

`config/release/web-ja-translation-baseline-v1.json`には、baseline version 1の時点で`UI_STRINGS.ja`に存在しないことが確認されたWeb chromeの英語文字列を記録します。

Release manifestは次の4種類を個別に報告します。

- `all_missing`: 現在未翻訳のchrome文字列すべて
- `known_missing`: review済みbaselineと一致する現在の未翻訳文字列
- `new_missing`: baselineにない新規未翻訳文字列
- `resolved_baseline_entries`: すでに未翻訳ではなくなったbaseline項目

CIを失敗させるのは`new_missing`だけです。`known_missing`も常に可視化され、時間とともに減らす必要があります。翻訳を追加した場合、同じpull requestで対応するresolved entryをbaselineから削除してください。

通常のUI変更では`UI_STRINGS.ja`を更新してください。翻訳する代わりに新しい文字列をbaselineへ追加してはいけません。追加を認めるのは、migrationまたはdesign上の理由が文書化されている場合だけです。

Record contentはbaselineの対象ではありません。`data-no-i18n`と既知のrecord-content classはscannerから除外され、`excluded_record_nodes`として別に数えられます。

## Direct-write baseline

`config/release/write-route-baseline-v1.json`には、AST auditが検出した既存direct writeのreview済み`(path, call)` pairを記録します。

各allowanceには理由があります。現在の分類は次のとおりです。

- authoritativeな`life.txt` dataではないundo/backup/configuration cache出力
- generated JSON Schema公開出力
- durable transaction journalを公開する`os.replace`

Quick capture、journal append、digest/template append、fzf/peco action、archive、tag merge、TUI edit、attachment、compound work sessionはsemantic CASまたはjournal-backed transactionへ移行済みで、direct-write allowanceは不要です。

Baselineにはline numberを含めません。そのため通常のrefactoringでは誤検出せず、別moduleへのdirect write追加や新しいcall shapeはgateを失敗させます。

Baseline更新には次のすべてが必要です。

1. targetをauthoritative data、operational state、configuration、cache、export、generated outputのいずれかに分類する
2. shared mutation pathをまだ使えない理由を説明する
3. technical debtの場合はroadmap項目を追加する
4. authoritative data pathがconflict-awareであることを証明するtestを維持または追加する

## Golden corpus baseline

`tests/golden/policy-v1.json`はminimum corpus、required field、required case name、corpus versionを定義します。難しいcompatibility caseが誤って削除されることを防ぎます。

Canonical outputを変更する場合はcorpus version更新と明示的migration noteが必要です。testを通すだけの目的でexpected outputを書き換えることはpolicy違反です。

## Evidenceの確認

GitHub Actionsは次を含む`release-policy-evidence`をuploadします。

- `release-gate.log`
- `.cache/release-policy-manifest.json`

Jobが成功した場合もmanifestを確認してください。成功結果にもknown debtや、baselineから削除すべきresolved entryが含まれる場合があります。
