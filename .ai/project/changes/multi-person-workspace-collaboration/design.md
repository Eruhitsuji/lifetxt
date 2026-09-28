# Design

## Authorization boundary

`lifetxt.collaboration.resolve_membership` resolves one selected named
workspace. A collaboration-enabled definition maps stable `remote.principals`
IDs to exactly one of `owner`, `editor`, or `viewer`. The effective operation
set is the intersection of the workspace role and the authenticated principal's
Remote scopes. Item visibility and source/write-target policy stay downstream
checks. Workspace owner does not imply any backup, recovery, or server-security
scope.

Configuration validation rejects malformed membership, unknown principal IDs,
unsupported roles, and a workspace without an active owner. A workspace without
`collaboration` keeps the existing behavior. Membership never enters ordinary
life.txt records.

## Remote enforcement and snapshots

Remote middleware resolves membership on each workspace read and on ordinary
item/ticket write routes. The selected workspace name is checked against the
server's active workspace to prevent query/path confusion. Snapshot and
capability responses expose only the current principal's role and bounded
effective permissions. Existing exact-revision, item visibility, per-file CAS,
idempotency, and actor-aware Native History mutation implementations remain in
place.

## Member management API and CLI

Protocol v2 advertises the list/add/role/remove member API only when the current
principal is a workspace owner with `admin` scope and persistent config writing
is available. Listing returns principal ID/display name/role/disabled state and
the exact config file revision. Each mutation sends that revision to
`write_config(require_revision=True)`. A stale revision is returned as a
conflict; no automatic retry occurs. Candidate validation prevents an ownerless
workspace. The CLI calls this same API and stores no new credentials.

Each attempt appends bounded Remote audit metadata (actor, action, known target,
outcome, request ID, opaque workspace identity, and revisions); it does not
record credential material or full config text. Member changes do not append
ordinary item history.

## Web UX

The authenticated `/remote` page reads role and member-management availability
from server responses. It supports roster refresh and add/change/remove using
the negotiated Remote API and browser CSRF token. Removal and owner demotion
require confirmation. A stale conflict refreshes the list for user review but
does not resubmit the mutation. Recent Activity renders the authenticated actor
IDs already present in Native History with `textContent` and no actor inference.
The controls use responsive wrapping, explicit labels, visible focus, and
English/Japanese copy chosen from the browser language.

## Compatibility and scope

Protocol v1 and workspaces without collaboration remain compatible. Existing
principal scopes remain authoritative, no life.txt or schema migration is
required, and all new config keys are optional. Invitations, account creation,
project/item ACLs, realtime collaboration, and offline reconciliation remain
out of scope.

## Security and verification risks

- Owner lockout and stale config races are guarded by validation and exact CAS.
- A changed role is applied to server memory immediately and is re-evaluated on
  the next request.
- Historical actor IDs remain unchanged when a member is removed.
- Browser layout is covered by responsive/DOM tests and script syntax checks;
  physical iOS/Android verification is not available in this environment.
