# Design

## Summary

The Timeline consumes only the #713 normalized adapters. It validates each
present domain, partitions invalid records, applies one deterministic sort and
limit, and emits a single ordered result used by both CLI presentations.

## Interfaces and Contracts

- ADDED: `native_timeline()` and `lifetxt timeline ID [PATH ...] [--limit N] [--json]`.
- ADDED: `temporal-timeline-v1.schema.json` and bilingual documentation.
- PRESERVED: Git-backed thread revision/as-of/diff contracts.

## Risks

Readers could overstate partial or truncated evidence. The result carries
domain coverage, diagnostics, invalid records, explicit limitations, and a
conservative global complete flag.

## Compatibility Impact

Read-only additive command and schema. Stored files and existing commands are unchanged.
