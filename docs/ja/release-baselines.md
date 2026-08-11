# Reviewed release baselines

Release baselines は existing technical debt を明示し、その debt が silent に増えることを防ぎます。blanket suppressions ではありません。

## Translation baseline

`config/release/web-ja-translation-baseline-v1.json` は、baseline version 1 時点で `UI_STRINGS.ja` に存在しないことが review 済みの English Web chrome strings を記録します。

release manifest は次の 4 lists を report します。

- `all_missing`: 現在 untranslated の chrome strings すべて
- `known_missing`: reviewed baseline と一致する current missing strings
- `new_missing`: baseline にない untranslated strings
- `resolved_baseline_entries`: もう missing ではなくなった baseline entries

CI を fail させるのは `new_missing` だけです。`known_missing` は visible debt として残り、時間とともに減らす必要があります。entry を translate した場合は、同じ pull request で対応する resolved entry を baseline から削除してください。

normal UI work では `UI_STRINGS.ja` を更新します。documented migration または design reason なしに、新しい string を translate せず baseline に追加してはいけません。record content は baseline material ではありません。`data-no-i18n` と known record-content classes は scanner から excluded され、`excluded_record_nodes` として別に count されます。

## Direct-write baseline

`config/release/write-route-baseline-v1.json` は、AST audit が検出した pre-existing direct writes の reviewed `(path, call)` pairs を記録します。

各 allowance は reason を持ちます。current categories は次の通りです。

- authoritative `life.txt` data ではない undo/backup/configuration cache output
- generated JSON Schema publication output
- `os.replace` による durable transaction-journal publication

quick capture、journal append、digest/template append、fzf/peco actions、archive、tag merge、TUI edits、attachments、compound work sessions は semantic CAS または journal-backed transactions に移行済みで、direct-write allowances は不要です。

baseline は line numbers を含みません。refactoring だけでは false failure にならず、別 module への direct write 追加や新しい call shape は gate を fail させます。

baseline update には次が必要です。

1. target を authoritative data、operational state、configuration、cache、export、generated output のどれかに classify する。
2. shared mutation path をまだ使えない理由を説明する。
3. allowance が technical debt なら roadmap item を追加する。
4. authoritative data path が conflict-aware であることを証明する test を保持または追加する。

## Golden corpus baseline

`tests/golden/policy-v1.json` は minimum corpus、required fields、required case names、corpus version を定義します。難しい compatibility cases が accidental に削除されることを防ぎます。

canonical output change には corpus version bump と explicit migration note が必要です。test を通すためだけに expected output を書き換えることは policy violation です。

## Reviewing evidence

GitHub Actions は `release-policy-evidence` artifact を upload します。

- `release-gate.log`
- `.cache/release-policy-manifest.json`

job が成功した場合でも manifest を review してください。successful result に known debt や、policy files から削除すべき newly resolved baseline entries が含まれることがあります。

## Baseline review checklist

- baseline entry は scanner が見つけた事実だけでなく、その exception が review 済みである理由を説明する。
- ordinary UI text は translation baseline ではなく `UI_STRINGS.ja` に追加する。
- resolved baseline entry は、それを解決した change と同じ change で削除する。
