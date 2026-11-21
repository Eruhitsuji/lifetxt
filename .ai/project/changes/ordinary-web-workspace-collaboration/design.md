# Design

## Approved deployment and identity boundary

The Owner approved private-network-only use, including VPN access, with no
direct public Internet exposure; a one-time exchange of an existing configured
principal token for an opaque browser session; and one server-selected named
workspace. VPN membership is enforced by the network/firewall or trusted
deployment boundary. The application does not infer VPN identity from arbitrary
headers. Writable non-loopback traffic requires HTTPS or an authenticated
encrypted tunnel.

## Authentication and session boundary

`lifetxt.web_collaboration` installs only when the selected workspace has
collaboration configured and `remote.enabled` supplies the existing principal
registry. The ordinary Web login uses the existing `authenticate_token`,
`BrowserSessionStore`, session expiry, and CSRF/Origin helpers. It uses a
separate `lifetxt_web_session` cookie with `HttpOnly`, `Secure` when applicable,
`SameSite=Strict`, root path, and no-store responses; the existing Remote cookie
continues to use its narrower path. The submitted token is cleared by the login
page and never saved in browser storage.

Each protected request resolves the current principal from the registry and
re-resolves selected-workspace membership. The browser cookie is CSRF protected
for every unsafe request. Direct API callers may use an existing principal
Bearer token; the shared `api.token` and proxy identity headers never identify
the caller for this feature. Session state is process-local, so the existing
single-worker Remote deployment guard applies.

## Route and role matrix

| Route class | Read / viewer | Write / editor | Additional authority |
| --- | --- | --- | --- |
| Standard pages, manifests, icons, ordinary data APIs | Workspace `read` scope and active membership | — | Private/no-store headers |
| Shared item, status, attachment and workspace data mutations | Denied | Workspace `write` permission plus existing exact revision/source guards | Cookie requests also require CSRF + Origin |
| Parse, preview, check and resolve POST APIs | Workspace `read` permission | Not applicable | CSRF + Origin for cookie sessions |
| `/api/config`, health, backup status, transaction preflight, Git and procedures | Requires workspace membership | Requires workspace write permission for unsafe methods | Existing principal `admin` scope; existing subsystem restrictions remain |
| Personal Context, notifications, messages, timer and work-session APIs | Denied | Denied | No per-user data partition exists yet |
| `/remote` and `/api/remote/v1/**` | Existing Remote implementation | Existing Remote implementation | Existing Remote checks unchanged |
| Login page and login endpoint | Public login shell only | Token exchange only | HTTPS, rate limit, exact Origin; endpoint reveals no workspace data |
| Unknown paths | Require authenticated workspace membership before returning route result | Unsafe methods require write permission | No implicit public bypass in collaboration mode |

Member roles only narrow existing principal scopes. A workspace owner does not
gain server administration. Collaboration grants access to the selected shared
life.txt sources; no per-item ACL is added. `person:` and `assignee:` remain
record semantics.

## Actor attribution

The ordinary Web mutation helpers already append supported Native History
events but did not accept an actor. A request-scoped `ContextVar` is set only
after authentication and membership checks, then read by the existing
`transform_items_text_with_native_history` path. Client payload actor fields
are not read. Other transports keep their existing explicit actor behavior.

## Rollback

Revert this PR to restore the prior ordinary Web behavior. No data migration is
required. Existing workspace collaboration configuration and Remote sessions
remain valid; the separate Web sessions are process-local and disappear on
restart. If reverting while collaboration remains configured, operators should
restrict the ordinary Web listener to the same trusted audience as before the
integration and keep direct Internet exposure disabled.
