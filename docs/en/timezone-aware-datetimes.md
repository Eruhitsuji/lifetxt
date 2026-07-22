# Timezone-aware datetime handling

This document defines the offset-preservation behavior implemented by the shared datetime utilities. It covers explicit offsets on full datetime values. The precedence rules for naive values, file directives, configuration, and CLI overrides remain a separate roadmap item.

## Parsing

A datetime with an explicit offset remains timezone-aware after parsing:

```python
from lifetxt.timeutil import parse_datetime

value = parse_datetime("2026-07-22T09:30:15.25+09:00")
assert value.utcoffset().total_seconds() == 9 * 60 * 60
```

`Z` is parsed as UTC. A compact offset such as `+0900` is accepted and is formatted canonically as `+09:00`. A datetime without an offset remains naive.

## Formatting

`format_datetime` preserves the offset, seconds, and fractional seconds:

```python
from lifetxt.timeutil import format_datetime, parse_datetime

value = parse_datetime("2026-07-22T09:30:15.25+09:00")
assert format_datetime(value) == "2026-07-22T09:30:15.25+09:00"
```

Formatting a parsed `Z` value produces the equivalent canonical `+00:00` suffix. The original life.txt detail string is not rewritten merely by reading or converting it.

## JSON, JSONL, and CSV

Datetime details remain strings in the item model and interchange formats. Therefore an authored value such as:

```text
from:2026-07-22T09:30:15.25+09:00
```

survives JSON, JSONL, and CSV round trips unchanged. Parsing a datetime for filtering, validation, agenda calculation, timer arithmetic, or recurrence no longer requires discarding the offset.

## Comparison compatibility

Older lifetxt versions converted aware datetimes to the host's local timezone and removed `tzinfo` immediately. The new implementation keeps the aware value and performs that local-naive conversion only at a comparison or subtraction boundary.

`comparison_datetime(value)` exposes the comparison-only representation explicitly. Display and serialization code must use the original value instead.

```python
from lifetxt.timeutil import comparison_datetime, parse_datetime

aware = parse_datetime("2026-07-22T09:30+09:00")
local_comparison_value = comparison_datetime(aware)
assert aware.utcoffset() is not None
assert local_comparison_value.tzinfo is None
```

Mixed aware/naive ordering and subtraction remain supported for existing agenda, validation, and timer code. This compatibility behavior does not decide what a naive value *means*. That policy will be defined together with `#! timezone:`, `defaults.timezone`, CLI overrides, display conversion, filters, and completion-date boundaries.

## Time-only values

This batch is intentionally scoped to full datetime values. Time-only values such as `at:09:30+09:00` retain the existing local-comparison behavior until the broader timezone-precedence policy is finalized.
