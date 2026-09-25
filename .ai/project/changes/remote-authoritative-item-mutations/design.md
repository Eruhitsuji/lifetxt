# Design

The route reuses the reviewed ticket-write sequence: authorize, reject duplicate
workspace IDs, compare the aggregate revision, then mutate one configured target
through per-file CAS. Transaction ID and request hash are stored on the Native
History event, so identical retries succeed while changed-payload reuse fails.
Create IDs are authority-assigned and immutable. Delete removes the current item
and appends `deleted` evidence atomically; it is not a replica tombstone.
