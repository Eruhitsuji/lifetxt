# Design

Use a read-only workflow_call producer with separate controller/source checkouts.
Validate the candidate against actual run context before choosing the source ref.
Recheck SHA, tracked clean state and declared version before/after artifact work.
Reuse release policy/safety and release_evidence once, validate the exact output,
and install both payload archives into separate clean venvs outside source.

A sealed build report binds the successful checks to exact bytes. Upload payload
first, then revalidate report and bytes before emitting the common component
proof with the action-provided immutable archive reference. Four Core roles stay
compatible with schema 1; intermediate component SHA256SUMS is not uploaded.

No source full-test duplication, publish token, environment, secrets, tag creation
or old workflow edits. The caller still owns trusted CI/source/approval API
checks. Logs remain in Actions; failed builds never upload success proof. Real
Actions transport integration belongs to #1321. Revert this PR to remove the
producer; no public assets require rollback. See bilingual release-preflight.md.
