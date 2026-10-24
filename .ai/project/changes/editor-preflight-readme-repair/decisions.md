# Decisions

| Date | Decision | Owner | Alternatives | Reason | Follow-up |
| --- | --- | --- | --- | --- | --- |
| 2026-10-24 | Rewrite the two documentation links only in the disposable VSIX staging README, using the candidate source SHA. | Implementer; Owner review pending | Change the tracked README, use mutable main URLs, or disable vsce link checks. | Preserve source documentation and immutable provenance without weakening packaging validation. | Validate the actual VSIX in a new non-public preflight after merge. |
| 2026-10-24 | Require both packaged README links and reject unresolved parent-relative links. | Implementer; Owner review pending | Trust staging output without checking archive bytes. | Verify the delivered archive independently and fail closed on missing or mismatched documentation provenance. | Independent implementation and integration review of the final head. |
| 2026-10-24 | Complete this package with its required decision record; retain the existing closeout test unchanged. | Implementer; Owner review pending | Weaken the package completeness gate. | CI run 40078158539 failed in both Python suites because this file was absent. The existing test reproduces the failure locally. | Run package closeout and Editor regression checks, then confirm CI on the updated PR. |

These are implementation decisions within #1394 and PR #1395, not merge or
Release Authority approvals. Real VSIX generation and the new 14-target
non-public preflight remain outstanding; public release requires separate
human approval.
