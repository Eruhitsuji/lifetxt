# Core Performance Baseline

`scripts/benchmark_core.py` records a deterministic baseline for representative
dependency-free workflows. It generates small (100), medium (1,000), and large
(5,000) task fixtures and measures `check`, JSON conversion, open-task filtering,
and `summary` in disposable workspaces.

```console
python scripts/benchmark_core.py --output docs/en/core-performance-baseline.json
```

The JSON records Python/platform metadata, wall-clock seconds, output sizes, and
the fixture sizes. It is a trend baseline, not a portable performance promise:
compare runs made with the same command, fixture policy, and comparable
environment. A single slow run should trigger review rather than an automatic
failure. Unexpected non-linear scaling should be split into a focused issue.

The benchmark uses only the standard library and is never part of the normal
runtime path or release gate.
