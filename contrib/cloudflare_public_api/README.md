# Cloudflare Python Worker feasibility PoC (#827)

This is an experimental, stateless feasibility probe. It is not the Public
Utility API and does not add a production `lifetxt` endpoint.

The adapter calls the existing Python Core directly. It does not invoke the
CLI, a subprocess, a server-local workspace, Remote, or a persistent store.

## Local reproduction

Prerequisites are Python 3.12+ for repository tooling, Node.js 18+, and `uv`.
Cloudflare's current Python Worker tooling is `pywrangler` from `workers-py`.
The commands below intentionally preserve the checked-in Worker entrypoint and
Wrangler configuration; do not run `pywrangler init` in this existing PoC.

From the repository root, build the authoritative package wheel used by the
PoC, then synchronize the PoC environment:

```text
uv build --wheel --out-dir .cache/wheels
cd contrib/cloudflare_public_api
uv sync
npm ci
npx wrangler --version
```

## Manual Cloudflare reproduction

An active Cloudflare account with Workers & Pages access is required for the
remote step. The local `pywrangler dev` step does not require an account.

For the approved manual PoC flow, authenticate interactively with Wrangler:

```text
npx wrangler login --device --use-keyring
npx wrangler whoami
```

Complete the browser/device approval when prompted. On Windows, the keyring
option uses the OS credential store/Credential Manager where supported. Do not
copy credentials, OAuth values, or tokens into the repository or evidence.
An API Token was not needed for this manual OAuth PoC flow.

Run the local Worker from this directory:

```text
uv run pywrangler dev
```

The intended current-default runtime is selected by
`compatibility_date = "2026-10-03"` and `python_workers` (Python 3.14 / Pyodide
314). With the default local port, verify the native handler using any HTTP
client:

```text
GET  http://127.0.0.1:8787/health
GET  http://127.0.0.1:8787/v1/info
POST http://127.0.0.1:8787/v1/check
     {"text":"[ ] T \"Read paper\""}
```

The `/v1/info` response uses `engine_base_revision` for the authoritative
engine revision. It is not the complete adapter source revision. The already
deployed temporary Worker version used the earlier legacy field
`source_revision`; this historical difference is retained in `RESULTS.md`.

The local port may be changed by Wrangler; use the URL it prints. The
`deployed_smoke.mjs` script is a convenient bounded client for a deployed or
local URL:

```text
node deployed_smoke.mjs https://<workers-dev-url>
```

Routes are deliberately non-contractual:

* `GET /health`
* `GET /v1/info`
* `POST /v1/check` with `{"text": "..."}`

The in-process `smoke_native.py` script exercises conversion, quick input
resolution, and priority classification without exposing those as HTTP
endpoints. The already-deployed historical Worker also had a temporary
`/__poc/smoke` route; the checked-in adapter removes that route and does not
claim it as part of the intended HTTP surface.

## Deployment approval boundary

After local verification, a human must approve any deployment. The exact
command is `uv run pywrangler deploy` from this directory. It would
create/update only the named Worker and its `workers.dev` endpoint; no D1, KV,
R2, Durable Object, custom domain, or user-content storage is configured.

The deployed PoC endpoint is:

`https://lifetxt-cloudflare-public-api-poc.leo10070021.workers.dev`

To remove the temporary PoC Worker after review, use the authenticated account
context and explicitly confirm the target name:

```text
npx wrangler delete lifetxt-cloudflare-public-api-poc
```

Deletion is a separate human cleanup decision and is not part of local setup.

Future release automation must use `CLOUDFLARE_ACCOUNT_ID` and a least-
privilege `CLOUDFLARE_API_TOKEN` in a protected GitHub Environment, deploy the
exact verified stable tag, reject prereleases by default, and remain a separate
responsibility from `.github/workflows/release.yml`.
