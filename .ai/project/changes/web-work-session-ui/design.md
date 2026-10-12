# Work-session drawer design

Use /api/work-session without changing its API. Consistent file reads surround
the current item/session read; compare displayed record contents and exact
timer revision. Stop additionally requires matching record ID, source file
and item revision. Explicit If-Match prevents the global fetch bridge from
upgrading a displayed snapshot. The existing editor retains the same file
precondition. Global pending state spans drawer disposal to prevent duplicates.
Failures stop controls and preserve edit input; only explicit refresh reloads
authoritative state. Operator resume is the existing journal contract, not
automatic browser recovery. Existing /timer slash behavior stays unchanged.
