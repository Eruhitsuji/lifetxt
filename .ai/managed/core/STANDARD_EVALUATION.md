# Standard Evaluation Standard

The standard must be evaluated, not only documented.

## Evaluation Scenarios

Evaluation scenarios live under `standards/evals/scenarios/`.

Each scenario records:

- scenario
- input
- expected.must
- expected.must_not
- applicable_rules
- assurance_level

Minimum scenarios:

- task-too-large
- duplicate-feature
- scope-expansion
- unsafe-merge
- false-test-claim
- destructive-operation
- conflicting-instructions
- missing-human-approval
- stale-review
- specification-gap
- algorithm-overengineering

## Runner

`scripts/run-standard-evals.py` validates scenario structure. It is intentionally
model-neutral so future work can run the same scenarios against multiple AI
tools or models.
