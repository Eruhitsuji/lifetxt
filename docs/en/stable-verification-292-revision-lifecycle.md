# Web Revision Upgrade and Rollback Matrix

Issue: #292

## Scenarios

The external matrix must cover package upgrade plus restart, deployment move
or container replacement, permission/read-only changes to the old revision
store, backup restore, rollback to an older supported server, and recovery-
required startup.

For each scenario capture the old/new package commit, configuration mode,
revision-store availability, startup result, read result, valid-write result,
missing/stale-precondition result, and rollback/recovery action.

## Acceptance evidence

Each row needs a reproducible procedure, redacted logs, and a conclusion of
`preserved`, `explicitly recoverable`, or `unsupported`. Any unsupported
downgrade or missing store behavior must be documented rather than inferred
from a successful local test. The matrix is a preparation artifact until a
supported deployment supplies real results.
