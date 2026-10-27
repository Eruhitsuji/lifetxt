# Decisions

| Date | Decision | Owner | Alternatives | Reason | Follow-up |
| --- | --- | --- | --- | --- | --- |
| 2026-10-27 | Use strict conversion by default; reject unrepresentable items/fields before writing output | Eruhitsuji | Silent omission; lossy default | Preserve source semantics and make loss visible | Consider explicit lossy mode only with complete field diagnostics |
| 2026-10-27 | Keep the standard Format 1.0 grammar unchanged and extend the existing shared conversion core | Eruhitsuji | Add syntax to life.txt; create another todo parser | Interoperability belongs at the codec boundary | Input UI adapters remain separate follow-up work |
