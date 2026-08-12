# Remote Attachment Crash and Replay Recovery

Issue: #298

## Scenarios

Exercise client crash before acknowledgement, identical retry, conflicting
reuse of a transaction id, resume, compensate, abandoned journal, diverged
journal, and restored-backup recovery. Run each against a disposable workspace
with the transaction state retained across process restart.

## Required observations

Record the transaction state before interruption, after restart, and after the
chosen inspect/resume/compensate action. Identical replay must be idempotent or
return the documented existing state; conflicting replay must be rejected with
structured diagnostics. Redact paths and content, retain stable state/code
references, and confirm no cleanup step erases evidence needed for diagnosis.
Real remote-client execution is still required for completion.
