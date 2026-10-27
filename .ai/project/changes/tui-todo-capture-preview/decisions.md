# Decisions

| Date | Decision | Owner | Alternatives | Reason | Follow-up |
| --- | --- | --- | --- | --- | --- |
| 2026-10-27 | Add `/todo TASK` while keeping `/add` as default Quick input | Eruhitsuji | Automatic detection or an `/add` mode toggle | Makes syntax intent explicit without changing existing capture | None |
| 2026-10-27 | Use a modal Enter/Escape review | Eruhitsuji | Immediate write or extra confirmation commands | Matches keyboard-only TUI behavior and makes the mutation boundary visible | None |
| 2026-10-27 | Remote confirmation uses structured create with the previewed revision | Eruhitsuji | Depend on unmerged Web todo-preview API changes | Preserves parallel issue independence and existing server authority | None |
