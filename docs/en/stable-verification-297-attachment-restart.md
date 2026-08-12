# Remote Attachment Partial-Send Recovery

Issue: #297

## Test matrix

Use a disposable source tree and supported remote client to exercise a single
and multi-chunk transfer interrupted after each chunk boundary, restart during
delivery, retry with the same transaction identifier, and authoritative data
changed between chunks.

## Required observations

The result must distinguish complete, partial, retryable, rejected, and
changed-source states. Verify that no partial package is accepted as complete,
retries do not mix revisions, and status responses contain bounded diagnostic
state without local secrets or paths. Record chunk index, transaction id
hash/reference, source revision, response code, and cleanup result in redacted
form. This is the test contract; real client execution remains outstanding.
