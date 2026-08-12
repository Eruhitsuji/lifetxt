# Stable CI Coverage Baseline

The `coverage-baseline` CI job publishes line and branch coverage for the
existing unittest suite as reviewable artifacts. The job is visibility-only:
it does not fail because the repository-wide percentage is below an arbitrary
threshold.

## Evidence

Each run publishes:

- `coverage-summary.txt` for a human-readable line/branch summary;
- `coverage.json` for machine-readable comparisons;
- `.coverage` for later local inspection;
- `coverage-tests.log` to preserve the test result that produced the numbers.

The baseline is interpreted with the source commit, Python version, test
selection, and coverage tool version from the CI run. Numbers from different
machines or changed test selections are not treated as directly comparable.

## Review focus

Future maintenance reviews should compare the parser and format contracts,
mutation and recovery paths, CLI contracts, and exercised Web/MCP contracts
before considering aggregate percentage changes. A decrease is a review signal,
not an automatic release blocker. Coverage tooling remains a development-only
dependency and is not part of the dependency-free runtime install.

## Local reproduction

```console
python -m pip install -e ".[dev]"
coverage run --branch -m unittest discover
coverage report -m
coverage json -o coverage.json
```
