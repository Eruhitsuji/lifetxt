# Decisions

## D1: Treat the public result extension as High assurance

Issue #706 is S-sized and read-only, but it changes the published
`temporal-thread-v1` contract. The public-contract escalation rule therefore
selects High assurance and retains a change package, review ledger, compatibility
evidence, and rollback plan.

## D2: Use W244

W232-W243 are already assigned to progress-history diagnostics. W244 is the
next unused warning code and is categorized as `time`, because the relation is
valid but its current comparable dates contradict its lifecycle ordering.

## D3: Preserve date granularity

The existing temporal-context comparison reduces date-times to calendar dates.
The consistency check reuses that exact behavior, so same-day values never imply
an order. Richer within-day ordering requires a separate reviewed contract.
