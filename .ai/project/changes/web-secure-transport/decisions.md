# Decisions

- HTTPS or an authenticated encrypted tunnel is required for writable non-loopback traffic and sensitive reads. Normal TLS termination is external.
- Use a startup warning, not a new insecure-transport setting or blanket HTTP refusal, because encryption in a VPN/SSH tunnel cannot be reliably inferred from a bind or HTTP backend request. Existing Remote HTTPS refusal is unchanged.
- One proxy trust list: preserve the immediate peer, disable Uvicorn automatic rewriting, and reuse remote.trusted_proxies, including for uploads without Remote enabled.
- Reject duplicate/empty/list-valued trusted scheme/host before body receive or Remote browser login. Explicit Remote allowed_origins cannot bypass malformed proxy origin refusal.
- No configuration setting is added/changed. Existing trusted_proxies explanation/schema/default and config explain are unchanged; English/Japanese deployment examples document its expanded upload use and restart requirement.
- Final security/integration approval and merge belong to the human maintainer. No deployment was performed.
