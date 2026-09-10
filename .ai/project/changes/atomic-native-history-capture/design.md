# Design

## Summary

The producer accepts a prevalidated replacement, re-parses before and after
states inside an exact-revision write, derives the approved payload, appends the
event, and validates the final life.txt. A pure transformer variant lets the
journal-backed work-session path use the same logic.

## Interfaces and Contracts

- ADDED: `commit_item_mutation_with_event`, compound event commit, and pure
  `augment_item_mutation_with_event`.
- MODIFIED: stable-ID quick, lifecycle, scheduling, and work-session routes.
- PRESERVED: CLI output/dry-run/refusal semantics and specialized ticket and
  progress history.

## Risks

Precomputed replacements could become stale. CAS checks the exact original
revision before the transformer runs; mismatch commits nothing. Payloads are
derived and compared with actual before/after state rather than trusted input.

## Compatibility Impact

Stable-ID typed routes append Note records. ID-less legacy writes remain valid
and explicitly provide only partial history.
