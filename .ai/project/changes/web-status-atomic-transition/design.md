# Design

Reuse the existing Status authoring capability and Core `status_transition`.
Use `mutation.write_text(transform=..., create=True)` so the read, parse,
no-op/close/open decision and atomic replacement run under the shared lock.
Choose this entry point over `status_transition_file`, whose `create=False`
would remove the existing Web API's missing-target creation behavior.

The existing Web middleware already captures a source snapshot and rejects
stale client revisions. Observe mode synthesizes a legacy revision; required
mode and revision-discovery clients already require a supplied header. Pass the
active transaction's expected hash to the mutation; never silently use a newer
revision or retry. A later external edit is checked again inside the mutation,
including no-ops. Unlike the old universal-newline read, the shared snapshot
preserves BOM and exact line endings.

The Status handler performs the authoritative commit itself. Acknowledge its
verified snapshot in the existing transaction's `before`, `text` and `result`
fields, leaving `dirty` false. The outer middleware's no-write commit reports
that saved hash. This deliberately avoids staging a stale full replacement or
performing a second write. No shared runtime changes are needed.

Keep response body fields and semantic details unchanged. Return 409 CONFLICT
with the existing conflict payload, 503 LOCK_TIMEOUT, 500 IO_ERROR, and existing
400 parser/input errors. New storage errors omit filesystem diagnostics. Return
JSONResponse for new storage errors because the existing global HTTPException
handler does not forward exception headers. Status success and mutation
conflict/lock/I/O responses carry no-store. Existing middleware failures and
authentication/read-only precedence remain unchanged.

Review viewpoints: acceptance, locked transform, Web CAS, one persistent write,
no-op, failure behavior, compatibility, authorization boundaries, response hash,
and preservation of unrelated data. Test viewpoints map each requirement to
real FastAPI requests and deterministic concurrent/external-edit tests.

The shared lock serializes cooperating CLI/Web/mutation writers. Raw editors
that ignore it are detected by hash checks before replacement and after writing;
the existing check-to-replace race against arbitrary non-cooperating editors
is not eliminated by this scoped fix. A post-write I/O/verification failure can
have an uncertain outcome; clients must reload before explicit retry.

Rollback: maintainer-approved revert of this PR. No migration is required;
already-written S records retain the existing Format. #1379 remains dependent
on merge of this PR. No deployment or live file mutation is included.
