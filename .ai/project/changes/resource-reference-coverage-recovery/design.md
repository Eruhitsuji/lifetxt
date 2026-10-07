# Resource-reference coverage recovery

Main CI run 37538428323 on bd8fca5a passed the unit/compatibility jobs but
failed the dev-only coverage floor: branch coverage 58.78% < 59.00%.
Its 5214 tests passed (375 skips). Latest main run 37547631196 on f69639c6
repeats the same coverage failure and additionally fails the Python 3.12 Web
suite's concurrent binding-allocation test with one BindingBusy refusal.

The store intentionally bounds lock admission to 0.1 seconds. The old test
incorrectly required every concurrent caller to enter immediately, although
loaded CI runners can legitimately refuse one. Keep that deadline unchanged:
retry only BindingBusy for at most 32 attempts per caller, still requiring
all eight distinct references and no unexpected errors. A separate held-lock
test confirms refusal, no partial binding, and successful admission after
release. Controlled 0.12-second transaction latency reproduces the original
failure and allows the repaired concurrent-allocation test to pass under the
identical condition.

The new HTTP tests require Starlette and are correctly skipped without Web
extras. Their transport module remains measured, however, and its pure input
validation and the policy/store error paths lacked dependency-free evidence.
The remedy is additional tests, preserving both the HTTP suite and its skips.

One dependency-free test module checks normal/exact envelope round trips,
malformed and duplicate JSON, unsupported versions, opaque namespaces,
required revisions, integer bounds, isolated single-worker policy, strict
selectors/limits, principal credential isolation and binding/token lifecycle.
Real temporary SQLite stores test quotas, failed-allocation integrity,
token retirement and foreign sidecar/database replacement refusal. POSIX store
cases retain a platform guard; pure validation cases run on every host.

The test filename uses the existing tests/test_coverage prefix so existing PR
path routing selects dev-only coverage as well as the no-Web suite. No routing
or workflow changes are needed. Runtime behavior and public configuration are
unchanged, so user documentation and migration changes are not applicable.

Review covers observable error codes and data integrity rather than measured
line counts. No live credentials, external resource fetching or production
files are involved. Shared registry edits add only task-specific evidence.
Rollback, if approved by the human maintainer, reverts the recovery PR without
altering runtime state; it would reopen the coverage gap.
