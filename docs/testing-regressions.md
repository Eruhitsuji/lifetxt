# Historical regression test policy

A fixed defect should add a deterministic regression test when its essential
failure mode can be reproduced without a browser, shell, host, network, or
mutable external service. The test should include a `Regression: #NNN` comment
and assert the corrected observable behavior. Existing tests should be extended
when they already cover the same boundary.

Environment-specific defects remain in their appropriate integration or
external-verification layer. A bug issue that cannot be made deterministic is
recorded as evidence there rather than represented by a fragile unit test.

## Initial historical review

The first bounded review used two representative defects:

| Origin | Protected behavior | Test evidence |
| --- | --- | --- |
| #850 | Drawer edit actions remain scoped to the selected record and do not regress to a global action | `tests/test_web_drawer_edit_js.py` |
| #880 | Remote revision-classification routes retain explicit read/write safety classification | `tests/test_remote_backup_operations.py` |

These tests are deterministic and remain in the normal unittest suite. Browser
rendering and real-host-only failures remain outside this policy and continue to
use their existing integration or external-verification evidence.