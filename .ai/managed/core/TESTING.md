# Testing Standard

## Required Behavior

Behavioral changes require tests unless an approved exception explains why.

Bug fixes should include a regression test that fails before the fix and passes
after the fix whenever practical.

## Test Levels

- unit tests: isolated behavior of functions, classes, and modules
- integration tests: contracts between components or external adapters
- end-to-end tests: user-visible workflows and deployment-critical paths

## Test Viewpoints

Use these viewpoints when deciding what to test:

- acceptance criteria: each condition can be demonstrated
- normal path: expected usage succeeds
- edge cases: boundaries, empty input, maximum/minimum values, repeated actions
- error cases: invalid input, missing dependency, timeout, unavailable service
- compatibility: existing public behavior still works
- security: authorization, validation, and secret handling remain safe
- data integrity: no unintended loss, duplication, corruption, or migration error
- concurrency: parallel actions and retries behave safely when relevant
- observability: logs and error messages help diagnosis without leaking secrets
- performance: critical paths stay within project expectations

## W-Model Test Mapping

| Source | Test or Check |
| --- | --- |
| Requirements | acceptance tests, manual acceptance checks |
| Architecture | integration tests, dependency checks |
| Interface contracts | contract tests, schema compatibility checks |
| Implementation | unit tests, static analysis |
| Release plan | smoke tests, migration tests, rollback checks |

## Test Design Rules

- Test externally observable behavior.
- Avoid tests that only lock implementation details.
- Prefer deterministic test data.
- Keep fixtures small and meaningful.
- Add regression tests for confirmed defects when practical.
- Do not delete or weaken tests to make CI pass without explicit approval.

## Verification Reporting

Pull requests must report:

- commands executed
- pass/fail result
- tests not run
- reason tests were not run
- residual risk

Never mark an unchecked item as complete.

If a check cannot be run, record:

- the exact check
- why it could not be run
- what was done instead
- the risk left for reviewers
