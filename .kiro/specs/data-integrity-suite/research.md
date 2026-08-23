# Research Log

## Summary

This is an extension of existing lifetxt integrity, validation, revision, workspace, ticket, attachment, and recovery behavior. Discovery found that the first implementation should reuse existing checks and aggregate their output before adding any repair or write behavior.

## Existing Capabilities

- `lifetxt check` already validates syntax, duplicate IDs, references, dependencies, recurrence values, event ranges, message/status rules, and optional `file:` / `dir:` attachment verification.
- `lifetxt ids` and link-related code already expose ID and relationship behavior.
- `lifetxt workspace validate` and `workspace doctor` already diagnose workspace manifests, duplicate physical sources, unsafe write targets, timezone metadata, and revision telemetry.
- `lifetxt ticket validate` and `ticket validate-history` already cover ticket state and event-history consistency.
- `lifetxt.write_operations`, `surface_runtime`, `transaction_journal`, and `transaction_policy` already provide revision-aware writes, transaction journals, backup integrity manifests, and recovery checks.
- Import/sync code already records `source:` and `uid:` conventions for generated records.

## Design Decisions

| Decision | Rationale | Revisit When |
| --- | --- | --- |
| Start with a read-only aggregator | The project rules prefer fail-loud diagnostics and proposal-first mutation. Aggregation has low data risk and unlocks evidence for later repair tasks. | Aggregator output cannot express a needed repair or workflow state. |
| Keep repair planning separate from repair application | Plans can be reviewed, staged, and revision-checked without modifying authoritative data. | A later Ready issue defines `integrity apply` with explicit approval and rollback behavior. |
| Reuse existing diagnostic code namespaces where possible | Avoids another parallel validation vocabulary and keeps CLI/Web/MCP/schema alignment easier. | Existing codes cannot distinguish new cross-file or reconciliation states. |
| Keep strict profiles opt-in | Unknown custom keys are a product-level parser guarantee. Strictness is useful for automation but must not make ordinary editing brittle. | A separate approved issue changes the base parser or `check` contract. |

## Risks

- The full suite is too broad for one implementation PR. It must be split into issue-sized slices.
- Repair application would become a data-changing capability and likely needs higher assurance than read-only reporting.
- Import/sync reconciliation must avoid contacting external services; it should inspect only local lifetxt records and generated files.
- Cross-file archive/generated-file roles may require configuration conventions to avoid guessing.
