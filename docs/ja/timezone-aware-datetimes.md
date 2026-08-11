# Timezone-aware datetime handling

この文書は shared datetime utilities が実装する offset-preservation behavior を説明します。対象は explicit offset を持つ full datetime values です。naive values、file directives、configuration、CLI overrides の precedence は [timezone-revision-workspace-safety.md](./timezone-revision-workspace-safety.md) で扱います。

## Parsing

explicit offset を持つ datetime は parse 後も timezone-aware のままです。

```python
from lifetxt.timeutil import parse_datetime

value = parse_datetime("2026-07-22T09:30:15.25+09:00")
assert value.utcoffset().total_seconds() == 9 * 60 * 60
```

`Z` は UTC として parse されます。`+0900` のような compact offset も受け付け、canonical output では `+09:00` になります。offset のない datetime は naive のままです。

## Formatting

`format_datetime` は offset、seconds、fractional seconds を保持します。

```python
from lifetxt.timeutil import format_datetime, parse_datetime

value = parse_datetime("2026-07-22T09:30:15.25+09:00")
assert format_datetime(value) == "2026-07-22T09:30:15.25+09:00"
```

parsed `Z` value を format すると equivalent canonical `+00:00` suffix になります。life.txt detail string は、read や interchange conversion だけでは rewrite されません。

## JSON, JSONL, and CSV

datetime details は item model と interchange formats では strings のままです。次の authored value は JSON、JSONL、CSV round trips 後も unchanged です。

```text
from:2026-07-22T09:30:15.25+09:00
```

filtering、validation、agenda calculation、timer arithmetic、recurrence のために datetime を parse しても、authored offset を捨てる必要はありません。

## Comparison compatibility

older lifetxt は aware datetimes を host local timezone に変換し、すぐ `tzinfo` を削除していました。現在は aware value を保持し、comparison/subtraction boundary だけで local-naive representation に変換します。

```python
from lifetxt.timeutil import comparison_datetime, parse_datetime

aware = parse_datetime("2026-07-22T09:30+09:00")
local_comparison_value = comparison_datetime(aware)
assert aware.utcoffset() is not None
assert local_comparison_value.tzinfo is None
```

mixed aware/naive ordering と subtraction は existing agenda、validation、timer code の互換性のため残ります。この behavior は naive value の意味を決めるものではありません。

## Time-only values

今回の実装範囲は full datetime values です。`at:09:30+09:00` のような time-only values は、より広い timezone-precedence policy が確定するまで existing local-comparison behavior を維持します。

## Authoring guidance

machines、services、collaborators の間で共有される real instant を表す datetime には explicit offset を使ってください。workspace timezone policy における wall time を意図する場合だけ naive values を使います。
