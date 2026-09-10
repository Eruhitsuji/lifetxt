# Decisions

## D1: Native semantic history is a core concept with optional evidence

Semantic operations should be readable from `life.txt`, but event presence is
not required for file validity. This preserves plain-text ownership and manual
editing without inventing history.

## D2: Use a common envelope with typed payloads

`record:item_event` avoids one record kind per item field, while a closed event
and payload registry prevents the contract from becoming a generic raw diff.

## D3: Preserve existing event contracts through adapters

Progress and ticket event records are public, working contracts with different
domain fields. Migration or duplicate emission adds risk without user value.

## D4: Keep authority source-specific

Current state, captured semantic operations, and exact revision bytes are not
competing representations of one fact. Readers retain provenance and disclose
conflicts instead of selecting or repairing a source implicitly.

## D5: Limit the first capture slice

Creation, lifecycle status, completion/reopen/cancel, explicit lifecycle
relations, and meaningful schedule fields are included. Title/type changes and
arbitrary custom details are deferred or excluded because their semantics are
not yet bounded.

## D6: Ship a timeline before semantic as-of reconstruction

Incomplete legacy/manual history cannot safely reconstruct a whole item at an
instant. A bounded event view can expose useful evidence and completeness first
without overclaiming.
