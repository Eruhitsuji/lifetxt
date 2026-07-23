# Release policy gate

lifetxtのreleaseは、暗黙的なCI commandの集合ではなく、version管理された実行可能policyで検証します。

## 必須GitHub Actions job

CI workflowには次の必須jobがあります。

```text
Required release policy and clean wheel
```

このjobは使い捨てvirtual environmentで`release` profileを実行し、`release-gate.log`と`.cache/release-policy-manifest.json`を生成して、`release-policy-evidence` artifactとして保存します。

同じprofileをlocalで実行できます。

```bash
python scripts/run_ci_like.py --profile release --python python3.12
```

他のnamed profileは次のとおりです。

```bash
python scripts/run_ci_like.py --profile cli
python scripts/run_ci_like.py --profile web
python scripts/run_ci_like.py --profile mcp
python scripts/run_ci_like.py --profile core
```

## Release check

実行可能policyは、現在次の契約を個別に検証・報告します。

1. shared CASがstale writerを拒否すること
2. offset-aware datetimeのround-tripが情報を失わないこと
3. `pyproject.toml`のpackage名が`lifetxt`であること
4. package versionが`lifetxt.__version__`と一致すること
5. `lifetxt` console scriptが`lifetxt.entrypoint:main`を指すこと
6. `web` optional dependency groupが存在すること
7. `tui` optional dependency groupが存在すること
8. golden corpusにversioned policyがあること
9. required golden caseが残り、nameが一意であること
10. golden canonical outputがcanonical normalization済みであること
11. generated/published schemaがDraft 2020-12 JSON Schemaとして妥当であること
12. published schemaが`schema_bundle()`と完全一致すること
13. item・diagnostic・capability・conflictの代表documentがschemaに適合すること
14. Web日本語chromeと明示的な`t()`文字列がdictionaryで網羅され、`data-no-i18n` record contentが別集計されること
15. reviewed baselineにないdirect write path/call pairを拒否すること
16. 指定example fileがstable format diagnosticsを通過すること
17. sdistとwheelをbuildできること
18. Twine metadata checkを通過すること
19. wheelを2つ目のclean virtual environmentへinstallできること
20. repository外のdirectoryから`python -m lifetxt`とinstalled `lifetxt` console scriptを実行できること

manifestには決定的なSHA-256 fingerprintが含まれます。check結果・policy version・compatibility versionが変わるとfingerprintも変わります。

## 直接実行

Policy checkだけを実行し、manifestを保存します。

```bash
python scripts/check_release_policy.py \
  --root . \
  --pretty \
  --output .cache/release-policy-manifest.json \
  examples/minimal_life.txt \
  examples/status_presence.txt \
  examples/messages_life.txt
```

通常CLIも同じ実装を使用します。

```bash
lifetxt safety release-gate \
  --root . \
  examples/minimal_life.txt \
  examples/status_presence.txt \
  examples/messages_life.txt
```

`jsonschema`はruntime dependencyではなくrelease開発dependencyです。dependency-free packageでは次のpartial reportを確認できます。

```bash
python scripts/check_release_policy.py --allow-missing-jsonschema
```

このmodeだけではreleaseできません。

## Translation coverage

scannerは`HTML_PAGE`内の`UI_STRINGS.ja` dictionaryを読み、表示されるstatic text、利用者が読むattribute、`t()`へ渡されるquoted stringを収集します。

`data-no-i18n`または既知のrecord-content classで示されたcontainerは除外し、別件数として報告します。利用者が入力した`Done`というtitleをUI buttonとして翻訳してはいけません。

button、label、placeholder、title、help string、明示的`t()` literalを追加する場合、同じ変更で英語source textを`UI_STRINGS.ja`へ追加してください。

## Write-route baseline

`config/release/write-route-baseline-v1.json`にはreview済みの既存path/call pairを記録します。line numberはkeyに含めないため、通常の編集では不要なbaseline変更が発生しません。

次のような新規direct callはrelease gateを失敗させます。

```text
open(..., "w"|"a"|"x")
os.replace(...)
atomic_write_bytes(...)
```

CIを通すだけの目的でbaselineへ追加してはいけません。最初にauthoritative life.txt/state write、export、generated artifact、cacheのどれかを判断してください。authoritative writeはshared mutation boundaryを使用する必要があります。baseline変更には、direct writeを残す理由と安全性の説明が必要です。

## Golden policy

`tests/golden/policy-v1.json`はcorpus version、minimum case数、required field、required case nameを固定します。

canonical outputを変更する場合やrequired caseを削除する場合は、次が必要です。

1. corpus versionの更新
2. 明示的なmigration note
3. compatibility expectationの更新
4. downgradeおよび旧client動作のreview

## Clean-wheel verification

release profileはsdistとwheelをbuildし、Twine metadata checkを実行し、別のvirtual environmentを作成してwheelだけをinstallします。その後repository外へ移動し、module、console script、parserのsmoke testを実行します。editable checkoutによってpackage file不足やentry point破損が隠れることを防ぎます。

## Legacy Web revision migration telemetry

一時的なWeb revision fallbackを削除する前に、利用状況を測定できる必要があります。

```http
GET /api/revision-metrics
```

responseには次が含まれます。

- fallbackが有効か
- fallback writeの合計
- endpoint path別件数
- 最後にfallbackが使われたUTC時刻
- 文書化された削除条件

fallback writeは次のheaderも返します。

```http
Warning: 299 lifetxt "Legacy write without client revision; fetch /api/revision and send If-Match."
Deprecation: true
X-Lifetxt-Legacy-Revision-Fallback: used
```

revision-aware writeはcounterを増やしません。strict sessionではrevision不足を引き続きHTTP 428で拒否します。
