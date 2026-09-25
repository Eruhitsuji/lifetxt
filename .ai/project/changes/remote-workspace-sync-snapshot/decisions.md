# Decisions

| Date | Decision | Owner | Alternatives | Reason | Follow-up |
| --- | --- | --- | --- | --- | --- |
| 2026-09-25 | Extend only protocol v2 while preserving v1 shape | Codex, approved architecture by Eruhitsuji | Replace the v1 snapshot schema | Existing clients keep compatibility and must negotiate the richer contract | #931 consumes the v2 contract |
| 2026-09-25 | Use opaque logical IDs instead of paths or path hashes | Codex, approved architecture by Eruhitsuji | Return paths; hash absolute paths | Paths disclose deployment details and path hashes change on relocation | None |
| 2026-09-25 | Reject a mid-read revision change | Codex, approved architecture by Eruhitsuji | Retry internally; return best effort | Explicit conflict is bounded and prevents a mixed-revision response | Clients retry the whole snapshot |
| 2026-09-25 | Keep item `editable` false in this issue | Codex, approved architecture by Eruhitsuji | Advertise mutation readiness now | #933 is read-only; #931 owns guarded mutation capability | #931 |
