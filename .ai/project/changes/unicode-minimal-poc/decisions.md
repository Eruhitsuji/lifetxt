# Decisions

| Date | Decision | Owner | Alternatives | Reason | Follow-up |
| --- | --- | --- | --- | --- | --- |
| 2026-10-26 | Explore a UTF-8-first CPython runtime with only essential internal Unicode codecs, keeping profile2 intact | Eruhitsuji | Existing ICU applicability review alone; only remove GB18030 | Limit unused historical mapping data while preserving life.txt UTF-8 text | #1434 source PoC; #1436 runtime; #1437 integration |
| 2026-10-26 | Submit only source curation and tests in this PR; no WASM or licensing claim | Implementer, subject to Owner review | Change the runtime within the PoC | Separate unverified compatibility and distribution risk from a small inspectable change | Independent High review of PR #1435 |
| 2026-10-26 | Preserve existing blocked distribution and publication gates | Eruhitsuji | Enable public release upon PoC completion | Source absence is not a licence or actual WASM acceptance | #1398 and #1400 remain blocked |
