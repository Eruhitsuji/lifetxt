# Reviewed release baselines

Release baselines make existing technical debt explicit without allowing the debt to grow silently. They are not blanket suppressions.

## Translation baseline

`config/release/web-ja-translation-baseline-v1.json` contains the English Web chrome strings that are known to be missing from `UI_STRINGS.ja` at baseline version 1.

The release manifest reports four separate lists:

- `all_missing`: every currently untranslated chrome string;
- `known_missing`: current strings that match the reviewed baseline;
- `new_missing`: untranslated strings not present in the baseline;
- `resolved_baseline_entries`: baseline entries that are no longer missing.

Only `new_missing` fails CI. `known_missing` remains visible and must shrink over time. When an entry is translated, remove the corresponding resolved entry from the baseline in the same pull request.

Do not add a new string to the baseline instead of translating it unless there is a documented migration or design reason. Normal UI work must update `UI_STRINGS.ja`.

Record content is never baseline material. Elements marked `data-no-i18n` and known record-content classes are excluded by the scanner and counted through `excluded_record_nodes`.

## Direct-write baseline

`config/release/write-route-baseline-v1.json` contains reviewed `(path, call)` pairs for pre-existing direct writes found by the AST audit.

Each allowance contains a reason. Current categories include:

- undo/backup cache output;
- explicit digest/template append output;
- the legacy fzf helper writer that is replaced at runtime by `compat_writes`;
- generated JSON Schema publication output.

The baseline does not contain line numbers. Refactoring a file therefore does not create false failures, while introducing a new call shape or a direct write in another module fails the gate.

A baseline update requires all of the following:

1. classify the target as authoritative data, operational state, configuration, cache, export, or generated output;
2. explain why the shared mutation path cannot be used yet;
3. add a roadmap item when the allowance represents technical debt;
4. retain or add a test proving the authoritative data path remains conflict-aware.

## Golden corpus baseline

`tests/golden/policy-v1.json` defines the minimum corpus, required fields, required case names, and corpus version. It prevents accidental deletion of difficult compatibility cases.

A canonical-output change requires a corpus version bump and an explicit migration note. Merely changing expected output to make a test pass violates the policy.

## Reviewing evidence

GitHub Actions uploads `release-policy-evidence`, containing:

- `release-gate.log`;
- `.cache/release-policy-manifest.json`.

Review the manifest even when the job succeeds. A successful result can still contain known debt or newly resolved baseline entries that should be removed from policy files.
