# Design

## Boundary

Protocol v2 extends the existing snapshot response with a `workspace` manifest
and filtered `items`. Protocol v1 remains unchanged. The server remains the only
authority; this is a read contract and creates no local replica.

## Identity and disclosure

Workspace and source IDs are domain-separated SHA-256 values derived from the
logical workspace name and ordered source position. They are stable across a
server path relocation and reveal neither path spelling nor file names. Source
records expose only role, writable/default-visible/existence flags, and opaque
identity. Diagnostics are reduced to severity/code/count tuples.

## Consistency

The server computes the aggregate source revision before parsing, builds every
section from the same parsed item set, and recomputes the revision afterward.
A mismatch returns `REMOTE_SNAPSHOT_REVISION_CHANGED` with the current revision
and no mixed snapshot. The selected writable source is determined by exact
normalized comparison with the server-configured write target and the source's
declared writable role.

## Security review viewpoint

The route retains Remote `read` scope enforcement and visibility filtering.
The new response does not serialize source/config records directly, avoiding
paths, exclusions, generators, privacy metadata, or configuration secrets.
Raw text and attachment bytes remain excluded by the existing item serializer.
