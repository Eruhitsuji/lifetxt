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

## Runtime Evaluation Scenarios

Runtime evaluation scenarios live under `standards/evals/runtime/`.

Each runtime scenario records:

- runtime_scenario
- input
- expected.must
- expected.must_not
- deterministic_checks
- semantic_checks
- privacy_requirements
- applicable_rules
- assurance_level

Minimum runtime scenarios:

- process
- ai-human
- issue-workflow
- security
- efficiency

Runtime scenarios evaluate evidence from real or synthetic AI development
history. They must distinguish project execution findings from upstream
standard findings and preserve privacy by default.

## Runner

`scripts/run-standard-evals.py` validates scenario structure. It is intentionally
model-neutral so future work can run the same scenarios and runtime findings
against multiple AI tools or models.

Runtime tooling uses:

- `scripts/export-ai-history.py`
- `scripts/analyze-ai-history.py`
- `scripts/report-ai-findings.py`

These scripts are preview tools. They must not create or update GitHub Issues
without a reviewed reporting workflow and explicit human approval for privacy
settings.
