# Decisions

| Date | Decision | Owner | Alternatives | Reason | Follow-up |
| --- | --- | --- | --- | --- | --- |
| 2026-09-08 | Add `follows:` and `realizes:` to the shared graph | Eruhitsuji | Date inference or a second graph | Explicit semantics are authoritative and date proximity is not causality | None |
| 2026-09-08 | Reuse `old replaced_by:new` | Eruhitsuji | Add `supersedes:` | Existing vocabulary already expresses replacement | None |
| 2026-09-08 | Compose a separate `temporal-thread-v1` | Codex | Break `temporal-context-v1` compatibility | Composition preserves the stable derived contract and provenance boundary | Keep both schema markers explicit |
| 2026-09-08 | Expose one shared model on all primary surfaces | Eruhitsuji | Surface-specific logic | Prevent semantic drift across CLI/TUI/Web/MCP | Thin adapters only |
| 2026-09-08 | Defer general `as-of` | Codex | Infer history from current dates | Current domain dates do not prove record existence at a past cutoff | Define a dedicated evidence/provenance contract before implementation |
