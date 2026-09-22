# Historical regression test policy

A fixed defect should add a deterministic regression test when its essential
failure mode can be reproduced without a browser, shell, host, network, or
mutable external service. The test should include a `Regression: #NNN` comment
and assert the corrected observable behavior. Existing tests should be extended
when they already cover the same boundary.

Environment-specific defects remain in their appropriate integration or
external-verification layer. A bug issue that cannot be made deterministic is
recorded as evidence there rather than represented by a fragile unit test.
