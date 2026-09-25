# Design

The existing dependency-free Remote client remains the read path and profile
store. Item commands extend the existing Remote command group and reuse the
reviewed protocol-v2 generic item-mutation endpoint from #931.

Before an item write, the client fetches capabilities and requires both the
`item-mutations` feature and enabled item mutation policy. It then fetches the
current permission-filtered snapshot, uses its aggregate revision as
`If-Match`, and sends one create, update, or delete operation with either the
caller's stable transaction ID or a generated UUID. No local state is mutated.

The existing structured conflict type reports the attempted operation and
server revisions with explicit refresh, abandon, and new-transaction actions.
No conflict is automatically retried. Capability, authentication, connection,
and other non-conflict failures propagate without falling back to cached or
local writes.
