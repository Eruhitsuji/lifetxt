# Historical Git evidence disclosure policy (investigation, #727)

Status: investigation only. No endpoint, MCP tool, or runtime code is
implemented by this document. It defines the Definition-of-Ready acceptance
criteria for a future server/Remote Safe Mode implementation issue (#728).

## Why this cannot reuse current-state read permission unchanged

Git history can retain values a current `life.txt` no longer has: a deleted
private record, an old address, a token-shaped string, or content that was
later marked private. "The caller can read `life.txt` now" does not prove
"the caller may see everything any historical revision ever contained."

## 1. Authorization model (v1 decision)

**Both current effective disclosure policy AND historical-revision content
must independently permit the result; a caller sees a historical record only
when it would also be visible under current policy for an equivalent
current record.** This is the conjunctive ("both current and historical must
permit") option from the issue's own candidate list, not the simpler "reapply
current policy alone" option, because current policy alone cannot detect
content that existed in a revision but has since been deleted from a source
the current policy would otherwise treat as globally readable.

A plain `read` role/scope never implies historical access by itself. A
future implementation must gate historical selectors behind a distinct,
explicit scope (mirroring `cap-mcp-permission-profiles`'s existing
`read`/`assist`/`full` profile precedent of never inferring a broader grant
from a narrower one).

## 2. Allowed v1 selectors

- **Exact revision** (`git_exact_revision`) — allowed.
- **Bounded as-of** (`git_as_of`) — allowed, since #726's
  `select_revision_as_of` is already deterministic and bounded
  (`MAX_HISTORY_COMMITS`).
- **Bounded revision list / history browsing** — **not allowed in v1.**
  #725 already decided no revision-listing helper is needed for the
  currently selected consumers; extending that to a server-exposed listing
  endpoint is new scope requiring its own review, not silently included
  here.
- Arbitrary Git object ID or path input — **never allowed.** The server must
  resolve selectors only against the caller's already-authorized
  workspace/source configuration, exactly as `read_historical_snapshot`
  already requires an explicit `paths` list rather than accepting a raw
  tree path from the caller.

## 3. Path / workspace boundary

- Only the server's own configured workspace/source paths may be read
  historically -- never a caller-supplied path. This reuses
  `resolve_git_inputs`'s existing repository/escape checks
  (`Historical input escapes its Git repository`) unmodified as the lower
  bound, with the server adding its own configured-source allowlist on top.
- Selected-commit tracked-path membership is reported exactly as
  `historical_snapshot` already reports it (`loaded_paths`/`missing_paths`);
  a path missing at the selected commit is never silently substituted with
  a different tracked file.
- Multi-repository workspaces remain unsupported for historical reads, same
  as the existing CLI reader (`resolve_git_inputs` already refuses a mixed
  repository set).

## 4. Reuse of existing Remote Safe Mode policy (no parallel engine)

The following existing Remote Safe Mode mechanisms must be reused verbatim,
not reimplemented for historical data:

- role/scope enforcement (the existing principal/session model)
- `lifetxt.remote_access.redact_remote_value` for any redacted field
- source-revision/provenance reporting shape (`source_revision()`)
- bounded-result-contract precedent (e.g. the tickets resource's
  `limit`/`cursor` pagination)
- audit-log append shape (`append_audit`)

A parallel "historical policy engine" duplicating any of the above is
explicitly rejected by this investigation.

## 5. Audit contract

Must be recorded per historical read:

- requested selector (revision or as-of cutoff/ref)
- resolved full commit SHA
- workspace/source scope actually read
- caller identity/role/scope
- result classification (served / denied / redacted) and denial reason
- redaction/limitation summary (e.g. `missing_at_revision:<path>`)

Must never be recorded: secret values, raw historical content, or any
redacted field's original value -- matching the existing Remote Safe Mode
audit discipline already established for current-state reads.

## 6. Bounds (v1 deterministic limits)

Reuse the existing reader's own limits rather than defining new, looser
ones for the server surface:

- `MAX_HISTORICAL_FILE_BYTES` / `MAX_HISTORICAL_TOTAL_BYTES` (already
  enforced by `historical_snapshot`)
- `MAX_HISTORY_COMMITS` (already enforced by `select_revision_as_of`)
- `GIT_TIMEOUT_SECONDS` per Git subprocess call (already enforced)
- A server-level result-size bound (item count) equivalent to existing
  Remote Safe Mode resource pagination bounds, applied on top.

No new, larger bound may be introduced for the server surface without its
own explicit review.

## 7. Fail-closed rule for policy conflicts

When current disclosure policy and the historical revision's own recorded
`privacy`/visibility metadata disagree, **the more restrictive of the two
wins.** A record that was private at the historical revision stays denied
even if current policy would now allow it; a record that is private under
current policy stays denied even if the historical revision predates that
restriction. This is the direct consequence of the conjunctive "both must
permit" rule in Section 1 and requires no separate mechanism.

## Definition of Ready for #728 (server implementation)

- [x] Authorization model decided (Section 1: conjunctive current+historical).
- [x] Allowed v1 selectors decided (Section 2: exact revision + as-of only).
- [x] Path/workspace boundary decided (Section 3: server-configured sources
      only, no caller-supplied path).
- [x] Reuse plan for existing Remote Safe Mode mechanisms decided
      (Section 4: no parallel policy engine).
- [x] Audit contract decided (Section 5).
- [x] Bounds decided (Section 6: reuse existing reader limits, plus an
      item-count bound).
- [x] Fail-closed conflict rule decided (Section 7).
- [ ] #728 itself remains unimplemented; this document is its Definition of
      Ready input, not its implementation.

## Explicit non-goals carried forward to #728

- No bounded revision-list/history-browsing endpoint.
- No arbitrary Git object/path traversal.
- No Native Semantic History merge.
- No rollback/restore.
- No AI inference over historical content.
