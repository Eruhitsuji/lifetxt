# Restricted resource-reference consumer v1 (approved schema contract)

[日本語](../ja/resource-reference-resolution.md)

## 1. Status and adoption gate

#1110 refines the owner-accepted #1101 recommendation and the adopted
[projection contract](resource-reference-projection.md). This concrete contract was
**approved by the owner on 2026-10-06** ([approval record](https://github.com/Eruhitsuji/lifetxt/issues/1110#issuecomment-6015909957)).
This task publishes six new schemas through the existing extension pipeline. No new
route, configuration setting, advertised runtime capability, resolver, binding store
or byte operation is implemented here. Independent integration/security review and
merge approval of the delivered schemas remain required.

The first consumer is a dedicated **restricted Remote protocol 2, bearer-only client**
for explicitly enrolled local regular files. It uses existing Remote authentication,
workspace/source/item visibility and transactions, plus a separate `attachment:read`
byte grant. Ordinary `read`, owner/editor status, upload receipts and history access
never imply that grant. No browser session, local CLI/TUI/MCP, legacy attachment v1,
raw Web, directory or provider/fetch change is included. Browser support needs a later
reviewed consumer with isolated session mode, CSRF, Origin and Fetch-Metadata guards.

Linux is the first candidate implementation platform. Kernel/helper/filesystem/root
proof and bounded supervision are required; Linux alone does not establish support.
Other platforms or missing prerequisites fail closed without advertising the feature.
#1111/#1113/#1114 implement persistence, resolver and delivery separately; #1112 and
#1115 evidence must be reviewed before those implementations claim safe reads.

## 2. Authorization configuration and isolation

The approved policy for future operator configuration consists of these explicit decisions. These are
contract concepts, **not currently accepted lifetxt configuration keys**. Configuration
implementation must later update registry/default/type/provenance/restart/secret/version
metadata, `config explain`, EN/JA docs, fixtures and migration/downgrade tests together.

| Policy concept | Required initial setting |
| --- | --- |
| Consumer enablement | Disabled by default; explicit resource-reference-v1 opt-in, selected workspace, single binding owner and healthy root/helper. |
| Principal disclosure mode | Explicit restricted-resource mode; cannot switch mode by changing a request header. Mode change revokes old credentials/sessions. |
| Principal identity | Dedicated principal and bearer credential distinct from trusted generic Web, legacy Remote, proxy and browser identities; no shared-token alias. |
| Metadata authority | Existing current `read`, explicit selected-workspace read membership, source role/item visibility plus enrollment and metadata policy. |
| Byte authority | All metadata/association gates AND explicit `attachment:read` in principal scopes. No automatic role grant. |
| Optional disclosure | Size, MIME and authored label controlled separately by current metadata policy; full digest separately opt-in, omitted by default. |
| Legacy/raw isolation | No anonymous/shared-token reachable raw workspace API; trusted generic Web/legacy credentials and network exposure separated and verified. Refuse enablement if separation is uncertain. |
| Browser/trusted proxy | Not accepted for this initial consumer; restricted bearer cannot log in to another mode or exchange for a browser session. |

Restricted credentials may invoke only the three exact operations in section 3 and a
future allowlisted capability handshake. Deny generic Web item/source/raw/export,
legacy attachment/path/open-plan/upload, Remote snapshot/search/history/audit/mutation,
MCP/tool wrappers and all unclassified alternate routes. Deny before producing legacy
errors, redirects or payloads. All methods, aliases, mounted routes and middleware
errors are covered. Changing a version header does not regain ordinary principal mode.

A capability handshake, if enabled later, emits only protocol 2, feature
resource-reference-v1, kind file, these operation names and effective bounded limits.
It must not reuse a raw manifest/command catalog. All enabled operations and errors
must be tested under the restricted identity and generic raw exposure inspected before
advertising. No advertisement for partial coverage, unsupported platform or schemas
alone. Schema publication will not enable the consumer.

## 3. Negotiation and exact operation classification

Reuse the existing `/api/remote/v1` route namespace; its path version does not select
Remote protocol 1. Every operation requires exactly `X-Lifetxt-Remote-Version: 2` and
`X-Lifetxt-Resource-Contract: resource-reference-v1`, and returns both headers on safe
success. Missing/unsupported/duplicate/comma-combined negotiation values fail with
406 `UNSUPPORTED_CONTRACT`; there is no automatic downgrade. Revalidate principal
mode, selected workspace and policy for every request, even with matching headers.

| Method and contract route | Operation | Membership | Write-clock/read-only classification |
| --- | --- | --- | --- |
| POST /api/remote/v1/resource-references/discover | Item-scoped descriptor discovery | Explicit read | Read-only, exempt from mutation clock only for this exact pair |
| POST /api/remote/v1/resource-references/full | Exact-revision full bytes | Explicit read + attachment:read | Read-only, same narrowly scoped exemption |
| POST /api/remote/v1/resource-references/chunk | Exact-revision bounded slice | Explicit read + attachment:read | Read-only, same narrowly scoped exemption |

Only these pairs are read-classified; trailing-slash aliases and other methods are
not exemptions. GET/HEAD on byte/discovery routes return 405 `OPERATION_UNSUPPORTED`.
Read-only workspace/server operation is permitted if all read gates succeed. Enrollment,
login, replacement, delete and actual mutations keep their original authentication,
CSRF, write membership, read-only and write-clock guards. No blanket POST exemption.

TLS is mandatory, including loopback for this consumer; reuse #1097's immediate-peer
trusted-proxy effective-origin policy, never trust arbitrary forwarding headers. Tokens,
resource refs and revisions stay out of URL/query/fragment and redirects. Authentication
uses `Authorization: Bearer` only; query tokens, ambient cookies and identity proxy
headers cannot supplement/override it. Reject any query parameters and credentials in
URL userinfo. Do not log authorization or request bodies. Pre-auth bounds precede parsing;
transport/authentication gates precede lookup. Malformed envelope never triggers lookup.

## 4. Typed envelopes and descriptor grammar

All JSON requests are UTF-8 objects with `Content-Type: application/json`; reject
compression, duplicate keys, unknown fields, nulls, booleans in integer fields,
nonfinite/fractional numbers, invalid UTF-8, BOM and trailing input. Maximum wire
body is 2,048 bytes, including whitespace. A syntactically well-formed bounded non-v1 att/rev version is 406
UNSUPPORTED_CONTRACT, not a legacy/path request; inspect no more than 64 bytes per
reference/token. Other malformed values are 400 without echo. Parse once; no unescape/normalization
into an accepted identifier. Reject ambiguous duplicate headers and oversize numbers.
`contract_version` is exactly the string `"1"` in each request/descriptor/result.

| Field / envelope | Type and bound |
| --- | --- |
| workspace_id, source_id | Exact 64 lowercase ASCII hex characters; reuse selected-workspace/source handles from #933, never interpret as path or byte digest. Workspace comparison always includes current membership. |
| item_id (discovery only) | Existing authored canonical id, 1..128 Unicode scalar values, <=512 UTF-8 bytes; no controls, bidi controls or surrogate codepoints; exact match, no title/line/ordinal/generated-id fallback. Unsupported existing ids are unavailable without rewriting source. |
| Discovery request | Exactly contract_version, workspace_id, source_id, item_id. No caller revisions on discovery. |
| Discovery success | Exactly contract_version, resources; resources is 0..16 authorized descriptors, no hidden count, reason, locator, cursor or raw item fields. If more than 16 visible eligible resources exist, reject whole operation with fixed RESOURCE_LIMIT; no silent truncation. |
| Full request | Exactly contract_version, workspace_id, resource_ref, source_revision, resource_revision. |
| Chunk request | Full fields plus offset (integer 0..10485760) and length (integer 1..65536); no clamping. |
| resource_ref | Exactly att:v1: + 32 lowercase ASCII hex digits, 39 bytes; random 128-bit identity, never decoded into a path. |
| source_revision, resource_revision | Exactly rev:v1: + 32 lowercase ASCII hex digits, separate random namespaces bound to exact source bytes / resource snapshot and policy generation. Required on full/chunk; no wildcard or latest. |
| Descriptor required fields | contract_version, resource_ref, kind="file", display_name, source_revision, resource_revision. |
| display_name | 1..128 Unicode scalar values and <=512 UTF-8 bytes, no controls/bidi/surrogates/locator/credential/provider detail; safe authored label only, default Attachment. Inert plain text. |
| size_bytes | Optional exact nonboolean integer 0..10485760 after metadata authority. Omit unknown/disallowed, never fake zero. |
| media_type | Optional finite enum: application/octet-stream, text/plain, application/pdf, image/png, image/jpeg, image/gif. Only verified policy-approved value; no parameters/sniffing/inline rendering. |
| content_digest | Optional object with only algorithm="sha256" and value=64 lowercase hex from exact full snapshot; separate explicit disclosure permission, default omitted. No 16-hex stored hash, ETag or provider version substitution. |

Unknown fields are forbidden recursively, including wrappers and digest objects.
Schema cannot prove UTF-8 byte counts, safe label classification, duplicate JSON keys,
random issuance, authority, association continuity or exact revision binding; those
remain semantic validation requirements with separate runtime tests. Workspace/source
handles do not permit deterministic resource/revision IDs or raw source hashes.

Discovery validates one consistent current authorized item/association snapshot again
before serialization. A visible id-less/duplicate/ambiguous item selector fails with
uniform 404; there is no invented id. For an authorized uniquely identified item,
only eligible visible enrolled resources enter resources. Hidden/unavailable associations
contribute no placeholders/counts; zero resources is safe. No discovery mints byte grants.

For this initial consumer, the operator explicitly provisions only the authorized
workspace_id/source_id/item_id selector to the restricted client out of band over a
protected channel. Do not copy a raw snapshot/manifest or use trusted credentials in
that client to bootstrap discovery. This contract adds no item/source inventory route;
a future safe inventory requires its own typed projection contract. Handles convey
identity only and are reauthorized at discovery.

## 5. Exact bytes, fixed bounds and response headers

Full/chunk resolve only after current principal, explicit workspace read membership,
source/item/resource authority, unique live generation and both expected tokens validate.
Open a confined regular-file handle and obtain one bounded immutable snapshot; verify
its exact bytes and recheck source, association and authority before emission. Path
checks followed by another open, pre/post hashes of different opens, mtime and short
hashes are insufficient. Removed/recreated association is unavailable before considering
staleness. Changed source bytes stale the source token even when resource bytes match.

| Resource / cost | Hard ceiling (lower existing policy wins) |
| --- | --- |
| File/full snapshot | min(10 MiB = 10485760 bytes, existing max_file_bytes) |
| Chunk | min(64 KiB = 65536 bytes, existing chunk and file policy); validate full snapshot each request |
| Source parsing | 1 MiB/source, 5,000 items/source, 10,000 items/selected workspace; detect cap+1 and fail closed |
| Discovery serialization | 16 visible descriptors; 32 KiB encoded JSON response |
| Active work | 2/process, 1/principal, no waiting work queue; slot held through receive, validation, worker stop and send |
| Rate | 30/min/principal, 120/min/process; also existing lower principal limits; pre-auth global 120/min/process |
| Absolute deadline | 30 seconds including receive, prepare and delivery; disconnect/cancel retains slot until worker stopped; reject filesystems without bounded supervision |
| Binding quota | 10,000 active and 50,000 total records including tombstones; no silent live eviction or retired-id reuse |

Bounds are not increased by request fields, role, headers or configured higher limits.
Full/chunk verification is O(file bytes) time and O(file cap) memory per active operation;
small slices still incur bounded full verification. Rate/pre-auth/slot controls also apply
to failures. Oversize source/file is generic RESOURCE_UNAVAILABLE; discovery cardinality
or serialization bound is fixed RESOURCE_LIMIT only after authorized item validation.

Successful byte responses are 200 binary, not base64 JSON, not 206. Required headers:
`Content-Type: application/octet-stream`, `Content-Disposition: attachment; filename="download.bin"`,
`Content-Length` exact emitted bytes, `X-Content-Type-Options: nosniff`,
`Cache-Control: private, no-store`, `Referrer-Policy: no-referrer`,
`Cross-Origin-Resource-Policy: same-origin`, `X-Frame-Options: DENY`,
`Content-Security-Policy: default-src 'none'; frame-ancestors 'none'; sandbox`,
both negotiated headers, `X-Lifetxt-Source-Revision` and `X-Lifetxt-Resource-Revision`
echoing only validated expected tokens. Chunk additionally returns decimal
`X-Lifetxt-Next-Offset` (offset + returned bytes) and `X-Lifetxt-EOF: true|false`.
No digest ETag, Last-Modified, Content-Range, Location, source hash or local basename.
No CORS grants, content compression or inline preview. JSON discovery/errors share
no-store/referrer/CORP/nosniff/frame/CSP protections and safe JSON content type.

Reject Range/If-Range headers with 400 INVALID_REQUEST; never convert to HTTP latest
fallback. At offset==size return empty 200, Content-Length: 0, EOF true; offset>size is
fixed INVALID_REQUEST only after authorization and revision validation. Chunk client
keeps both tokens unchanged, validates headers/length/next offset, and discards all
accumulated chunks on stale/unavailable/abort before authorized rediscovery. Full client
also discards incomplete transfer; zero bytes is valid only with Content-Length: 0.

Recheck authority/association/revisions before first byte and each <=64 KiB emission.
Before headers, return a safe error; after headers, abort without appending JSON.
Length consistency alone does not prove completion: clients require normal transport
completion too. Already delivered bytes/user-saved copies cannot be revoked. Byte
recipients necessarily observe lengths; metadata denial cannot hide bytes they receive.

## 6. Fixed safe outcomes and alternate-route denial

Error envelope is exactly {"error":{"code":...,"message":...}}. Code and message
pairs come from this static catalog, never raw exceptions or caller input. No details,
current tokens, labels, size, path, diagnostics or request-body echoes.

| HTTP | Code | Exact message |
| --- | --- | --- |
| 401 | AUTHENTICATION_REQUIRED | Authentication required. |
| 400 | INVALID_REFERENCE | Invalid resource reference. |
| 400 | REVISION_REQUIRED | Expected revisions required. |
| 400 | INVALID_REQUEST | Invalid request. |
| 404 | RESOURCE_UNAVAILABLE | Resource unavailable. |
| 409 | STALE_REVISION | Refresh the resource descriptor. |
| 406 | UNSUPPORTED_CONTRACT | Contract unavailable. |
| 405 | OPERATION_UNSUPPORTED | Operation unavailable. |
| 429 | RESOURCE_LIMIT | Resource limit reached. |
| 503 | RESOURCE_BUSY | Resource service unavailable. |

Authenticate before lookup. Envelope errors may be reported without existence lookup;
valid full/chunk with a missing revision uses REVISION_REQUIRED without returning current
values. Unknown/denied/wrong-workspace/id-less/duplicate/removed/missing/corrupt/uncertain
bindings and missing byte grant use the identical RESOURCE_UNAVAILABLE body and no
lookup-derived timing distinction. Restricted requests to alternate routes get that same
safe 404 after authentication. Return STALE_REVISION only after current authorized live
association validates; never leak that a forbidden resource has changed. Negotiation or
platform/service-wide unsupported conditions use 406 without resource-specific lookup.
Rate/slot/deadline errors reveal no resource state; post-header failures abort.

Audit only to the existing protected sink: safe principal/workspace identity, operation,
fixed outcome and server-created correlation. Scoped refs/revisions require explicit audit
policy; label/path/digest/provider URL/raw exception/body/Authorization are excluded.
Capabilities, HTTP middleware, logs and reverse-proxy access/error logging need the same
review; safe new route output is insufficient when raw alternate access remains reachable.

## 7. Synthetic envelope examples and acceptance scenarios

In order: discovery request/result, full request, chunk request, empty authorized
discovery, uniform unavailable, stale, unsupported. These are review fixtures, **not
executable endpoints**. Metadata label is allowed; optional digest/size/MIME are omitted.

```json
{
  "contract_version": "1",
  "workspace_id": "dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd",
  "source_id": "eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee",
  "item_id": "task-1"
}
```

```json
{
  "contract_version": "1",
  "resources": [
    {
      "contract_version": "1",
      "resource_ref": "att:v1:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
      "kind": "file",
      "display_name": "Attachment",
      "source_revision": "rev:v1:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
      "resource_revision": "rev:v1:cccccccccccccccccccccccccccccccc"
    }
  ]
}
```

```json
{
  "contract_version": "1",
  "workspace_id": "dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd",
  "resource_ref": "att:v1:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "source_revision": "rev:v1:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
  "resource_revision": "rev:v1:cccccccccccccccccccccccccccccccc"
}
```

```json
{
  "contract_version": "1",
  "workspace_id": "dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd",
  "resource_ref": "att:v1:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "source_revision": "rev:v1:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
  "resource_revision": "rev:v1:cccccccccccccccccccccccccccccccc",
  "offset": 0,
  "length": 65536
}
```

```json
{
  "contract_version": "1",
  "resources": []
}
```

```json
{
  "error": {
    "code": "RESOURCE_UNAVAILABLE",
    "message": "Resource unavailable."
  }
}
```

```json
{
  "error": {
    "code": "STALE_REVISION",
    "message": "Refresh the resource descriptor."
  }
}
```

```json
{
  "error": {
    "code": "UNSUPPORTED_CONTRACT",
    "message": "Contract unavailable."
  }
}
```

| Scenario | Required result |
| --- | --- |
| Id-less item; duplicate canonical id; ambiguous repeated association | Uniform 404 for unusable selector; no source rewrite/ordinal fallback. Eligible-item discovery never enumerates hidden/unavailable associations. |
| Removed then same id/path/bytes recreated | Old ref remains 404; fresh enrollment has a new random ref. |
| Ref stolen into another workspace or credential | 404; matching content or syntactically matching revisions do not authorize. |
| Current authorized source changed, same file bytes | 409; no automatic latest read. |
| Byte/presentation/metadata policy changed | 409 after current authority; old resource token cannot recover old bytes/labels. |
| Viewer/owner has read but no attachment:read | Discovery permitted by metadata policy; full/chunk 404. |
| Read-only source/server with healthy binding and read membership | Discovery/full/chunk may pass; enrollment cannot mutate life.txt. |
| Unsupported OS/kernel/helper/root or continuity proof | 406, no advertised capability, no path/legacy fallback. |
| Unknown field; bool offset; short digest; percent/uppercase/suffixed ref | 400; unknown fields cannot smuggle a path or extra disclosure. |
| Range/If-Range; wrong method; missing contract header | 400 / 405 / 406 respectively; no downgrade. |
| Revoke/change between chunks or during full send | 404/409 before headers, abort after headers; discard partial bytes. |
| Generic Web anonymous or same credential exposes raw workspace | Refuse safe-consumer enablement, even if these three responses are safe. |

## 8. Published schemas, usage and verification boundary

Following owner approval and Ready refinement, `lifetxt/schema_extensions_v33.py`
publishes these six contracts through the existing schema-extension bootstrap and
generator/sample pipeline. New outputs use resource-reference-* names and preserve
attachment legacy v1:

- resource-reference-descriptor-v1.schema.json
- resource-reference-discovery-request-v1.schema.json
- resource-reference-discovery-result-v1.schema.json
- resource-reference-full-request-v1.schema.json
- resource-reference-chunk-request-v1.schema.json
- resource-reference-error-v1.schema.json

Schemas are draft 2020-12, closed objects, fixed string contract version, exact anchored
identifier grammar, explicit required fields, bounded integers, finite MIME and fixed
code/message pair alternatives. The discovery result embeds/reuses the same descriptor
shape. Binary 200 bodies are governed by section 5, not misrepresented as JSON schemas.
Matching tests cover positive/negative schema validation, unknown nested fields,
digest grammar, nonboolean bounds, samples/generator parity and EN/JA examples. Keep
every existing attachment v1 generated schema byte-for-byte unchanged. Tests must also
state which semantic gates JSON Schema does not prove; no runtime claim from round trips.

Generate the bundle with `python -m lifetxt format schemas DIRECTORY`. The six files already
exist under `dist/schemas/`; their samples are registered in the existing release
sample pipeline. Run `python -m unittest tests.test_resource_reference_contract`
with the existing optional jsonschema validator installed to validate examples,
negative cases and generator parity. A validator-free run checks publication and
legacy artifacts but skips JSON Schema validation explicitly. This task adds no
mandatory dependency. Example use with an independently prepared JSON request:

```python
import json
from jsonschema import Draft202012Validator

with open("dist/schemas/resource-reference-full-request-v1.schema.json", encoding="utf-8") as handle:
    schema = json.load(handle)
with open("request.json", encoding="utf-8") as handle:
    Draft202012Validator(schema).validate(json.load(handle))
```

This validates the envelope shape; it does not send a request or authorize bytes.
HTTP/transport/member/action checks, request wire limit/duplicate JSON keys, policy,
randomness, enrollment/revision continuity, platform proof and transfer bounds remain
requirements for #1111/#1113/#1114. Full/chunk operations still are not executable.

Verification covers EN/JA JSON/schema round trips, grammar/unknown-field/digest/bound
negatives, generator/sample parity, legacy attachment v1 byte hashes, package and
traceability checks. Integration/security review of the final head remains independent
and pending. Rollback reverts only these docs/schemas/test/bootstrap registration and
task-specific package/registry additions; no data migration or deployment is involved.
