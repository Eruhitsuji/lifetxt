# Design

## Summary

`record:item_event` is a normal Note with a closed common envelope and one of
eight typed payloads. Validation is separated into per-record shape checks and
per-parent stream checks. Existing specialized records are adapted only in the
read model and are never rewritten.

## Interfaces and Contracts

- ADDED: `lifetxt.native_history` builders, validators, completeness report,
  iterators, and normalized adapters.
- ADDED: `item-event-v1.schema.json` and bilingual format documentation.
- MODIFIED: `lifetxt check` includes item-event stream diagnostics.
- MODIFIED: Remote Safe Mode applies parent access inheritance to item events.
- PRESERVED: progress, ticket-event, time-entry, Git history, and ordinary
  life.txt storage contracts.

## Risks

Malformed manual events could look authoritative. Closed payload validation,
sequence/chronology/continuity checks, current-state agreement, and explicit
partial coverage prevent that promotion.

## Compatibility Impact

Additive only. Existing files require no events, migration, or byte changes.
