# Decisions

| Date | Decision | Owner | Alternatives | Reason | Follow-up |
| --- | --- | --- | --- | --- | --- |
| 2026-10-27 | Require `--syntax todo`; retain Quick as the default | Eruhitsuji | Automatic detection | Prevent ordinary text and `@` shorthand from being reinterpreted | Web/TUI use explicit selectors in #1442/#1443 |
| 2026-10-27 | Reject semantic override flags in todo mode | Eruhitsuji | Merge flags with todo metadata | Avoid another precedence contract and keep the source task reviewable | Put metadata in the todo task |
| 2026-10-27 | Treat decoder diagnostics as capture errors | Eruhitsuji | Write with warnings | A one-item write has no preview step and must not persist malformed dates | Web/TUI may preview diagnostics before confirmation |
