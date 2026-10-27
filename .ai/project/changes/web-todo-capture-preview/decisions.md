# Decisions

| Date | Decision | Owner | Alternatives | Reason | Follow-up |
| --- | --- | --- | --- | --- | --- |
| 2026-10-27 | Keep Quick as the default and require an explicit todo.txt selector | Eruhitsuji | Automatic detection | Prevent ordinary text and `@` shorthand reinterpretation | None |
| 2026-10-27 | Require preview plus a separate confirmation for todo.txt Web capture | Eruhitsuji | Save immediately | Web can expose semantic mapping before mutation | TUI follows its own #1443 review flow |
| 2026-10-27 | Reuse contextual workspace review and the existing capture mutation | Eruhitsuji | New parser or writer | Preserve one grammar and existing security/atomicity contracts | None |
