# Design and review boundary

Approved D1-D3: #1143 / PR #1148. One pure core composes nextaction.blocked_map/
is_actionable, extra_common._rank_key, read_scope/agenda.filter_items,
priority_matrix.classify_item, timezone_policy and freebusy.compute_freebusy.
No existing temporal, priority or mutation engine is changed.

Core orchestrates bounded admission, full-context dependency resolution, candidate
selection, occupancy certification, classification, greedy packing and canonical
serialization. daily_flow_model owns admission/provenance; daily_flow_time owns
workspace normalization, constant-offset certification and interval preflight.
Unknown attendance stops placement but preserves safely derived fixed rows.
No remaining-time inference, split, automatic dependency unlock, stored proposal,
background computation, file discovery or external dependency.

Currentness/admission/retry/auth are caller obligations; their flags can block
without leaking source inventories. Optional real snapshot digests use the
existing mutation hash contract; otherwise parsed_snapshot is explicitly labelled.
This is an internal shared response contract, not a public endpoint/schema.

Security review: no IO/network or writes; explicit certification flags; bounded
records/edges/text/expansion/conflict pairs/slots; generic unavailable result; source
paths hashed, no raw details in output; authorized titles remain visible. Hashes
are pseudonymous references, not authorization grants. No hidden-data lookup.

Temporal review: shared interpreters preserve authored offsets; convert immutable
copies to workspace naive wall time only for certified constant-offset days.
Reject DST windows, incomplete spans and unsupported recurrence. Legacy engines
unchanged. Scopes narrow candidates, never occupancy/dependency context.

Tests cover boundary behavior, byte/input immutability, seeded non-overlap/identity/
capacity invariants, rank compatibility, scale and failure caps. Caller IO and Web
auth integration are not claimed tested. Independent human review remains pending.
