# Design: semantic Temporal Diff

Both revisions pass through the exact-revision Historical Temporal Thread seam.
The diff module normalizes stable item fields, explicit edge identities,
consistency warning identities, and stable derived facts/edges before set
comparison. Source locations and serialization order do not create changes.

A missing target is an explicit availability state and compares against an
empty lifecycle. Any historical, traversal, consistency, or possible derived
limit is carried into limitations and prevents complete from being true.

The new temporal-diff-v1 schema is additive and read-only. Rollback is a normal
PR revert with no data migration.
