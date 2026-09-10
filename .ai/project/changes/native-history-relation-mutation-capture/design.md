# Design

The existing exact-revision ticket relation transform gains event augmentation
for the three native lifecycle fields. When no revision is supplied, it first
captures the exact source hash and uses it as the CAS precondition and event
provenance. The event is appended only when the relation text actually changes.
