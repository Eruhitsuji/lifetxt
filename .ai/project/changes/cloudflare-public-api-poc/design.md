# Design

The PoC is a bounded adapter under `contrib/cloudflare_public_api/`:

`Cloudflare Worker -> existing lifetxt Core`

The worker exposes only non-contractual health/info/check routes. The evidence
harness calls the same shared functions in memory for conversion, quick input,
and priority classification. No Core code is changed and no request content is
persisted or logged.

The current `lifetxt/__init__.py` remains the package-root comparison subject;
the PoC does not add a Cloudflare-specific import workaround. If Pyodide shows
root eager initialization is unsuitable while pure semantic modules work, the
decision is a platform-neutral Core-import refactor follow-up.
