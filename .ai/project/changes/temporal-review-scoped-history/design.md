# Design

Reuse authoritative area/Saved View selection over the original snapshot; take
selected non-history targets and append only native history whose sole parent
identifies one selected target uniquely across that snapshot. Unscoped reads
return the original snapshot unchanged. Malformed associated payloads go through
the existing native validators, not prefiltered as valid. Ambiguous selected IDs
or parent values involving a selected ID raise a generic ValueError/HTTP 400
without exposing target IDs, record titles or source paths.

The dedicated helper is used only by GET /api/temporal-review. Generic readers,
Workspace Timeline/native validation, bounds and response schema stay unchanged.
The entire scoped snapshot is passed into the existing builder so current
carry-forward and upcoming rows cannot include unrelated targets.

Alternative: build full review then filter events. Rejected because bounds and
diagnostics/current rows would be composed before scope. Expanding generic
resolve_read_scope would change other consumers unnecessarily.

Risks: ambiguous historical references must fail closed; missing/invalid history
can still make a result incomplete. No life.txt migration or automatic writes.

Horizontal review found pre-existing upcoming composition passing None as an
agenda end bound (#1156). Owner then explicitly requested its repair in the same
PR; that independent S task is recorded in temporal-review-upcoming-range.
