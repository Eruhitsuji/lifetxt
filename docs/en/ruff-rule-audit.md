# Incremental Ruff Rule Audit

Issue #347 measured candidate Ruff rule families in read-only mode against
`lifetxt`, `tests`, and `scripts`. The reproducible command is:

```console
python scripts/audit_ruff_rules.py --output docs/en/ruff-rule-audit.json
```

The committed JSON record contains the audit date, rule groups, counts by code,
recommendation, and limitations. The script never applies automatic fixes.

## Snapshot and recommendation

The current snapshot found:

- `E4,E7,E9`: 61 findings, including `E741`: 9 and `E731`: 4;
- `F`: 320 findings, while the existing gate's `F63`, `F7`, and `F82` remain clean;
- `UP`: 2,409 findings;
- `SIM`: 185 findings;
- `B`: 189 findings;
- `RUF`: 377 findings.

The recommended first batch for #348 is `E741` only. It is nine ambiguous-
variable findings with a bounded review surface. `E4`, `E731`, and the larger
modernization, simplification, bugbear, and Ruff-specific groups remain audit
results rather than enabled gates: their current volume or import/behavior risk
would create broad stabilization churn.

## Guardrails

This is a point-in-time inventory, not a claim that every finding is a defect.
#348 must review each E741 location, fix only behavior-preserving cases, and
record any narrow ignore with rationale. It must not format the whole repository
or enable the deferred groups.
