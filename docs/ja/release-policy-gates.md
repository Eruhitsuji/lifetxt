# Release policy gates

lifetxt releases は undocumented CI commands の集合ではなく、versioned executable policy で validate されます。

## Required GitHub Actions job

CI workflow には required job `Required release policy and clean wheel` があります。disposable virtual environment で `release` profile を実行し、`release-gate.log` と `.cache/release-policy-manifest.json` を artifact `release-policy-evidence` として upload します。

local では同じ profile を実行できます。

```bash
python scripts/run_ci_like.py --profile release --python python3.12
```

named profiles には `cli`、`web`、`mcp`、`core` もあります。

## Release checks

executable policy は、stale CAS rejection、offset-aware datetime round-trip、package metadata、console script entry point、optional dependency groups、golden corpus policy、schema bundle validity、representative documents、Web Japanese chrome coverage、direct-write baseline、example files、sdist/wheel build、Twine metadata、clean wheel install、outside-repo smoke tests を independently report します。

manifest は deterministic SHA-256 fingerprint を持ちます。check output、policy versions、compatibility versions が変わると fingerprint も変わります。

## Direct command

policy checks だけを実行して manifest を書けます。

```bash
python scripts/check_release_policy.py \
  --root . \
  --pretty \
  --output .cache/release-policy-manifest.json \
  examples/minimal_life.txt \
  examples/status_presence.txt \
  examples/messages_life.txt
```

normal CLI route は同じ implementation を使います。

```bash
lifetxt safety release-gate \
  --root . \
  examples/minimal_life.txt \
  examples/status_presence.txt \
  examples/messages_life.txt
```

`jsonschema` は release-development dependency であり runtime dependency ではありません。`--allow-missing-jsonschema` は partial report 用で、publication evidence には不十分です。

## Translation and write-route coverage

new button、label、placeholder、title、help string、explicit `t()` literal を追加する場合は、同じ change で `UI_STRINGS.ja` に English source text を追加してください。record content は UI chrome として扱いません。

`config/release/write-route-baseline-v1.json` は reviewed direct writes を記録します。new direct `open(..., "w"|"a"|"x")`、`os.replace(...)`、`atomic_write_bytes(...)` は baseline にない限り release gate を fail します。baseline を更新する前に、authoritative write か export/generated/cache かを classify してください。

## Clean-wheel verification

release profile は sdist/wheel を build し、Twine metadata を check し、別 virtual environment に wheel だけを install し、repository 外から module、console script、parser smoke tests を実行します。editable checkout が missing package files を隠すことを防ぎます。

## Legacy Web revision migration telemetry

`GET /api/revision-metrics` は fallback enabled state、total fallback writes、endpoint counts、latest fallback time、removal condition を report します。fallback write は warning/deprecation headers を返します。revision-aware writes は counter を増やしません。strict sessions は missing revision を HTTP 428 で reject します。

## Local evidence checklist

release-policy result を報告する前に、command output と manifest を一緒に保持してください。manifest fingerprint は、どの root、examples、policy versions、optional dependency state で作られたかを reviewer が確認できる場合にだけ有用です。
