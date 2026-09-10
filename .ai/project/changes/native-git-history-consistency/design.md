# Design

## Summary

The verifier enumerates a bounded set of path-affecting commits, loads tracked
life.txt blobs through the existing historical evidence helpers, projects
supported item semantics from adjacent states, and compares transition sets to
the #713 Native normalization. Exact source-content revisions prefer otherwise
equal matches; timestamp is presentation evidence only.

## Interfaces and Contracts

- ADDED: `verify_history_consistency()` and `lifetxt history-check` text/JSON.
- ADDED: `native-git-history-consistency-v1.schema.json` and bilingual docs.
- REUSED: bounded Git process/blob safety and Native normalized records.
- PRESERVED: all Native/Git write paths, Timeline, and historical thread reads.

## Risks

Rewritten, shallow, missing, or truncated Git history could create false
confidence. These states set explicit limitations and force `complete:false`.
Unsupported ticket/time-entry projections are `unverifiable`, not guessed.

## Compatibility Impact

Read-only additive command/schema. Git remains optional and existing commands
and stored data are unchanged.
