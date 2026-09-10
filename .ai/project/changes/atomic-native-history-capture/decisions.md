# Decisions

| Date | Decision | Owner | Alternatives | Reason | Follow-up |
| --- | --- | --- | --- | --- | --- |
| 2026-09-10 | Derive payload from before/after state | Eruhitsuji | Trust caller payload | Prevent evidence/state disagreement | #715 |
| 2026-09-10 | Preserve ID-less legacy writes | Eruhitsuji | Require IDs globally | Avoid an unrelated breaking migration | Document partial coverage |
| 2026-09-10 | Keep ticket/progress specialized writers | Eruhitsuji | Emit duplicate item events | Preserve established authority and compatibility | Adapter via #713 |
