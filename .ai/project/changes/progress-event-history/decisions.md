# Decisions

| Date | Decision | Owner | Alternatives | Reason | Follow-up |
| --- | --- | --- | --- | --- | --- |
| 2026-09-08 | Use append-only `record:progress_event` Notes | Eruhitsuji | Reconstruct from undo, snapshots, VCS, or current values | Investigation #696 found no existing source that preserves complete ordered boundaries; the owner approved the explicit record contract | Keep #695 blocked until #697 merges |
| 2026-09-08 | Preserve exact raw before/after values | Codex | Store only normalized ratios | Denominator and representation changes are meaningful to future aggregation and audit consumers | Reuse `parse_progress` only for validity |
| 2026-09-08 | Couple the item update and event append in one exact-revision mutation | Codex | Two writes or best-effort event capture | A successful supported write must never publish a current value without matching evidence | Reject stale snapshots before replacement |
| 2026-09-08 | Treat incomplete chains as unavailable | Codex | Guess missing boundaries or block all later CLI writes | Fail-loud diagnostics preserve evidence quality while allowing users to continue recording new explicit writes after a manual edit | #695 must exclude unavailable chains |
| 2026-09-08 | Inherit parent access policy on Remote reads | Codex | Copy privacy fields into each event | Read-time inheritance stays current when parent policy changes and avoids a second driftable privacy copy | Independent security review required |

## Assurance note

This is High assurance because it introduces durable public data used as future
authoritative evidence and touches a remote permission-filtering path. Human
implementation, integration, security, rollback, and merge approvals remain
required.
