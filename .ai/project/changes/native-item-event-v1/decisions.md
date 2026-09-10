# Decisions

| Date | Decision | Owner | Alternatives | Reason | Follow-up |
| --- | --- | --- | --- | --- | --- |
| 2026-09-10 | Use closed per-event payloads | Eruhitsuji | Generic field-change events | Prevent arbitrary mutations from acquiring semantic authority | #714 |
| 2026-09-10 | Normalize existing records at read time | Eruhitsuji | Stored migration | Preserve byte compatibility and existing authorities | #715 |
| 2026-09-10 | Treat missing creation evidence as partial, not invalid | Eruhitsuji | Reject or infer history | Existing/manual files remain readable without overstating completeness | #715 |
