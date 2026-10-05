# Web transport security

This policy applies to writable Web UI/API traffic, including attachment uploads
and future private-resource access. It also applies to sensitive reads even on a
read-only server. Bearer authentication authorizes requests; **it does not protect
plaintext HTTP from eavesdropping or tampering**. Protect attachment bytes, API
credentials, private metadata, mutation bodies, and capability/share or
signed/presigned URLs that grant access by possession. Opaque resource IDs reduce
path disclosure; they do not encrypt content or replace secure transport.

## Deployment boundary

| Deployment | Required protection / threat model |
| --- | --- |
| HTTP on loopback | Permitted when the host, local users and processes are trusted. Loopback does not isolate hostile local processes or browser requests; authentication and upload CSRF checks still apply. |
| Private LAN | A private address or firewall alone is not encryption. Use HTTPS or an authenticated encrypted tunnel; account for compromised peers and network interception. |
| VPN / SSH / private overlay | Permitted only when peers are authenticated, every untrusted network hop is encrypted, access is restricted, and decrypted backend traffic stays on loopback or an equivalently protected host boundary. An overlay name alone is not sufficient. |
| Public / general non-loopback | HTTPS with a valid certificate is the normal production model. Terminate TLS at a trusted reverse proxy, restrict the backend to that proxy, and encrypt upstream hops that cross untrusted networks. |

`lifetxt serve` / `lifetxt web` default to `127.0.0.1`. Direct Uvicorn remains
HTTP-only; TLS certificate management belongs to the proxy. Writable non-loopback
binds print an actionable transport warning even with a Bearer token or
`--insecure-public`. The existing refusal of unauthenticated writable public
binds remains. `--insecure-public` relaxes that authentication gate only; it does
not approve plaintext network exposure.

The bind and HTTP scheme cannot establish whether an external VPN/SSH tunnel or
TLS proxy protects the connection. Therefore the ordinary Web server warns,
rather than adding a new plaintext override or refusing valid tunnel deployments.
This warning is **not proof of compliance**. Operators must verify the complete
route before sending sensitive material. Application rejection cannot protect a
credential/body already sent over HTTP. Remote Safe Mode retains its separate
HTTPS enforcement and `remote.allow_loopback_http` behavior; an HTTP private VPN
peer does not bypass that enforcement. Read-only mode is not a privacy boundary.

## Proxy trust and same-origin uploads

`serve` and `web` disable Uvicorn's automatic proxy-header middleware, irrespective
of `FORWARDED_ALLOW_IPS`. This preserves the immediate socket peer for the existing
`remote.trusted_proxies` check. It applies to upload Origin checks even when
Remote Safe Mode is disabled. There is no new configuration setting.

For a same-host proxy using IPv4 loopback, add this to your existing config:

```json
{
  "remote": {
    "trusted_proxies": ["127.0.0.1/32"]
  }
}
```

Add `::1/128` only if that is the proxy's actual upstream peer. Use the narrowest
addresses, never all networks or an entire LAN. Trusting a proxy also grants the
existing Remote principal-assertion authority when Remote is enabled; keep the
backend inaccessible to untrusted clients and local processes.

The proxy must validate the public Host against configured hostnames and ports,
overwrite `Host`, `X-Forwarded-Host` and `X-Forwarded-Proto` with the validated
external authority/scheme, and strip client-supplied `Forwarded` and
`X-Lifetxt-Principal` unless deliberately providing a verified Remote identity.
Do not relay arbitrary client forwarding headers. Preserve the external port
(e.g. `:8443`) in Host/forwarded host. The supplied
[nginx example](../../contrib/nginx/lifetxt.conf.example) uses a fixed external
hostname for its HTTPS listener; adjust both authority headers if using another
port. Reject unknown hosts in the front-end default server.

Only the configured immediate peer may supply effective scheme/host. Untrusted
forwarding headers and the standard `Forwarded` header are ignored. Upload and
Remote browser same-origin calculations share this boundary. Trusted
`X-Forwarded-Proto` / `X-Forwarded-Host` must contain one value each; duplicate,
empty, comma-separated, malformed or non-HTTP origins fail closed. Multi-hop
proxies must collapse these values at the last trusted hop. Origin comparisons
include scheme, hostname and effective port; default 80/443 are equivalent to
omitted ports. The upload marker, Fetch Metadata checks and no-CORS policy remain;
Remote `allowed_origins` does not extend the upload allowlist.

Custom ASGI hosting must also disable automatic proxy-header rewriting and
preserve the socket peer (`uvicorn ... --no-proxy-headers`). Otherwise it is outside
this supported trust architecture. Check a genuine HTTPS same-origin upload
succeeds, a cross-origin upload fails, and direct spoofed forwarding from an
untrusted peer fails. Restart the service after changing trusted proxies. Older
versions handled Uvicorn proxy headers independently; do not rely on that implicit
trust after upgrading, and review proxy behavior before downgrading.

## Sensitive URLs, logs and caches

Use HTTPS for a capability or signed URL's destination too; do not put API tokens
in query strings. Treat possession-granting URLs as temporary credentials, with
minimum scope and short expiry. Keep them out of life.txt, ordinary locators,
plaintext configuration, analytics, access logs, exception reports and support
bundles. Log a stable non-secret identifier instead; redact URL query/credential
material at the proxy and provider boundary. Avoid third-party navigation and
referrer disclosure (`Referrer-Policy: no-referrer` on private responses).

Upload receipts/errors already use `Cache-Control: no-store`. Future private
resource responses and grant-issuing endpoints must also use no-store, bypass
shared/proxy/CDN/service-worker caches, avoid logging payloads or full grant URLs,
and use download headers appropriate to the content. Expiration does not erase
logged or cached copies. URL issuance/download/provider adapters remain separate
work; this policy does not introduce a resource resolver.

See [Web](web.md), [Remote Safe Mode](remote.md), and
[Ubuntu deployment](../deployment/ubuntu-server.md). Proxy mechanics are described
in the official [Uvicorn settings](https://www.uvicorn.org/settings/) and
[nginx proxy header documentation](https://nginx.org/en/docs/http/ngx_http_proxy_module.html#proxy_set_header).
