# Resource-reference projection v1

[日本語](../ja/resource-reference-projection.md)

## 1. Status, authority and scope

This is the shared **design contract** for #1100, based on the owner-approved
[#1099 decision](https://github.com/Eruhitsuji/lifetxt/issues/1099#issuecomment-6012655572).
MUST/MUST NOT specify requirements for a future conforming consumer; they do not
claim current endpoints implement them. Contract acceptance requires independent
human design/security and integration review of the PR. This task adds no runtime,
lookup database, endpoint, schema, Format key, provider adapter or byte sync.

The first consumer scope is managed and explicitly enrolled existing local **files**.
Directory browsing/download, cloud profiles and fetching remain separate decisions
(#1101, #1102, #1103). Local `file:` / `dir:` and item-link `ref:` semantics stay intact.
Locator, integrity, access and presentation are separate concerns. An opaque reference
provides identity only; possession MUST NOT authorize metadata, opening or bytes.

Current upload receipt `attachment_id` (#1095/#1096) is a receipt, not a resolver ID.
Current Web `api_item` exposes details/source/text/Markdown; current Remote snapshot
removes source/text/Markdown and recursively redacts structured values. Neither
establishes this entire projection contract. No new capability is advertised now.

## 2. Identifier grammar and limits

A resource reference is exactly `att:v1:` followed by 32 lowercase ASCII hex digits:

```text
^att:v1:[0-9a-f]{32}$
```

Total length: 39 ASCII bytes. The 32 digits encode 16 independently generated
cryptographically random bytes (128 bits), **not** a UUID with fixed version bits,
path, digest, item ID, provider ID or deterministic hash of those values. A future
issuer MUST use secure randomness and check uniqueness in its lookup store,
regenerating on collision. It MUST NOT obtain a path by decoding the reference.

Parse the entire value exactly once. Reject whitespace, uppercase, escapes,
percent encoding, Unicode lookalikes, appended query/fragment, separators and extra
bytes; do not normalize into another accepted value. Malformed syntax is
`INVALID_REFERENCE`. A bounded well-formed version tag other than `v1` produces
`UNSUPPORTED_CONTRACT`; never reinterpret it as a path or legacy v1 request.
Limit syntax inspection to 64 bytes; larger input is invalid without echoing it.
The identifier is case-sensitive, has no embedded expiry, and is not a URL.

The server MUST issue independent IDs for the same bytes/path/item across different
workspaces and server installations. Clients MUST NOT compare IDs for global
content identity. Within one workspace an ID may be shared by authorized principals;
every principal is authorized separately. IDs and metadata remain disclosure-controlled.

## 3. Binding, enrollment and lifecycle

The private lookup binds the ID to server/install namespace, workspace identity,
source identity, uniquely identified canonical item, and one resource-association
generation. Its locator stays server-side. It reuses existing authoritative source,
item and attachment state; it MUST NOT create another authorization engine or writer.
Do not key only by basename, ordinal, line number, bytes digest or OS path.

| Situation | Required behavior |
| --- | --- |
| Managed upload | Enroll only a committed, unambiguous association; a failed transaction cannot issue a usable binding. A lost receipt is not permission to duplicate an upload. |
| Existing local file | Explicit server/operator enrollment after unique item/association and root/type checks; no automatic import, copy or life.txt rewrite. |
| Read-only source | May enroll in writable server-owned binding state if policy permits; MUST NOT edit the source or invent a canonical item ID. If binding persistence/validation is unavailable, return unavailable. |
| Id-less or duplicate-ID item | No usable reference; unavailable, no automatic ID assignment or line-number fallback. |
| Duplicate indistinguishable associations | Unavailable until the owner disambiguates; occurrence index MUST NOT decide authority. |
| Byte replacement on same verified association | Keep resource ID; replace resource revision. The old revision becomes stale. |
| Rename/move | Retain ID only if the same source/item/association continuity is explicitly verified; path equality or equal bytes alone is insufficient. Otherwise invalidate and re-enroll. |
| Detach, delete, item/source removal | Invalidate association generation permanently. Reattachment/recreation gets a fresh ID even if the path/item ID/bytes recur. |
| Permission revoke | Immediately deny further projection/resolution. Revocation need not rotate other principals' shared ID; re-grant still needs full current checks. |
| Workspace copy, source rebind, new server | Fresh workspace/install-scoped IDs. A source alias rebound to another origin invalidates affected bindings. |
| Restart | Preserve IDs only with intact durable bindings and validated authoritative association state. No persistence means old IDs are unavailable; never reconstruct them from paths. |
| Restore/rollback | Invalidate and reissue in a fresh binding epoch; do not resurrect detached IDs or old revision grants from a backup. |
| Store loss/corruption, uncertain continuity | Fail closed; owner reconciliation and fresh issuance, no best-effort path fallback. |

A binding is not a secret credential store. Storage layout, atomic enrollment,
concurrency and tombstone retention implementation belong to #1101 refinement.
A consumer MUST validate current association continuity on every operation. Ambiguous
out-of-band edits invalidate it; a cached lookup alone cannot prove continuity.
No finite expiry is promised. Clients must refresh after unavailable/stale responses.

## 4. Identity, revisions and integrity

| Concept | Current meaning / future projection rule |
| --- | --- |
| Stored `#sha256=` | Normally `HASH_LENGTH=16`: 16 hex digits, a 64-bit prefix of SHA-256. Keep existing compatibility; not a full digest or authorization. |
| Full byte digest | 64 lowercase hex digits from exact file bytes. Current `attachment_revision` uses this; explicitly typed optional `content_digest` may disclose it only under policy. |
| Source revision | Current transaction `item_revision` is the hash of the **whole source life.txt**, not an individual item. Unrelated source edits can make it stale. |
| Projected `source_revision` | Required workspace/source/epoch-scoped random equality token bound server-side to the exact existing source revision; any authoritative source revision change invalidates the old token. |
| Projected `resource_revision` | Required independent workspace/association/epoch-scoped random equality token bound to exact byte revision and binding/presentation-policy generation; it changes when those change. |
| Provider version | Adapter-specific object/version/ETag, never interpreted as a cryptographic digest. No private raw provider version in this v1. |
| Directory hash | Existing tree-manifest/hash semantics, not a single-file digest. Outside this first file projection. |

Projected revision tokens use `rev:v1:` + 32 random lowercase hex digits (39 bytes),
with the same exact parsing and generation constraints as resource IDs. Separate
source/resource namespaces are required even though token syntax matches. They
are validators, not credentials or ordering values. Mapping them to existing exact
hashes preserves CAS semantics without publishing content-correlatable hashes of
private source files. Do not substitute mtime, truncated stored hash or provider
ETag for an exact applicable revision. No `<missing>`, wildcard or implicit latest
revision is allowed in a successful descriptor or a resolving request.

A resolver requires both exact expected tokens plus the current binding; a future
write additionally uses existing mutation/attachment revision guards. A missing
file never becomes an implicit create operation. Unchanged bytes alone cannot
make a stale source token valid. Metadata or policy changes invalidate the resource
token so cached unsafe labels/MIME cannot be reused. Tokens from another workspace,
source or resource do not match even when hashes do. Optional digest disclosure
can correlate known documents and therefore is separately denied by default.

## 5. Allowlisted file descriptor

Construct a fresh DTO; do not forward transaction/item/provider dictionaries.
Unknown fields MUST be rejected by the future consumer's contract validator.

| Field | v1 rule |
| --- | --- |
| `contract_version` | Required string `"1"`; distinct from the reference's `v1` and legacy attachment v1. |
| `resource_ref` | Required identifier from section 2. |
| `kind` | Required literal `"file"`; unsupported kinds are unavailable. |
| `display_name` | Required safe authored label, 1–128 Unicode scalar values and <=512 UTF-8 bytes. Default `Attachment`; not auto-derived from a local/provider basename. |
| `size_bytes` | Optional policy-approved observed exact nonnegative integer <= 9007199254740991; omit unknown/disallowed sizes, never substitute 0. |
| `media_type` | Optional policy-approved observed type from the concrete consumer's finite allowlist, <=127 ASCII bytes, lowercase `type/subtype`, no parameters. Omit unknown/unsafe/spoofed types; not proof of content safety. |
| `source_revision` | Required projected source token from section 4. |
| `resource_revision` | Required projected resource token from section 4. |
| `content_digest` | Optional object with exactly `algorithm: "sha256"` and `value: <64 lowercase hex>`; explicit digest disclosure permission and verified full bytes required. Default omitted. |

Labels MUST exclude controls, bidi overrides, locators, credentials and private
provider details. Uncertain classification falls back to `Attachment`. Render as
plain text, never HTML, Markdown links or executable input; do not derive a command,
clickable URL or filename from it. Sanitization alone does not make a label public.
Size/MIME need current metadata authority; unavailable metadata does not trigger
external network fetching. A conforming client must not sniff/render inline solely
because a media type is present; download/open behavior needs its own policy.

Always exclude: path/stored_path/value/source/source_text/text/raw/markdown,
configured roots, journal/temp/lock paths, internal transaction targets, OS commands,
provider account/tenant/profile/object IDs, credentials, share/capability/signed URLs.
No generic `extra` bag. Object and wrapper fields follow the same allowlist principle.

## 6. Authorization, resolution and safe outcomes

For **every** metadata or future byte/open request:

Initial descriptor discovery has no caller revision yet: obtain one exact authorized
source/resource snapshot and revalidate its binding, revisions and policy immediately
before serialization. Deny if that consistent snapshot cannot be established.
Only resolving/action requests use caller-supplied expected tokens in step 4;
discovery does not grant an implicit-latest exception for byte/open/write requests.

1. Authenticate current principal; bind the negotiated contract to that context.
2. Check current workspace, source, item and resource **and action** permission.
3. Resolve only in that authorized workspace and verify unique current membership,
   canonical item and resource association generation; no caller-supplied path override.
4. For resolving/action requests, compare both exact expected revisions to current
   authoritative state; discovery instead validates its exact snapshot.
5. Apply configured root/type/symlink and content bounds; constrain the opened object
   against races, and recheck revisions/authority before delivering bytes/committing.
6. Perform only the separately authorized bounded operation; do not execute a remote
   OS open plan. If continuity or race-safe exact-version reads cannot be proved, deny.

An opaque ID, mailbox origin, upload success, cached metadata or token alone never
passes these steps. Snapshot/history authorization does not grant byte access.

| Outcome | Contract response / information boundary |
| --- | --- |
| Unauthenticated | `AUTHENTICATION_REQUIRED` (future HTTP mapping 401). No lookup information. |
| Malformed / unsupported | `INVALID_REFERENCE` (400) / `UNSUPPORTED_CONTRACT` (406); no input echo. |
| Unknown, forbidden, wrong workspace, removed, missing, ambiguous, id-less, corrupt binding | Uniform `RESOURCE_UNAVAILABLE` (404). Same safe body; no existence reason, locator or lookup-derived timing distinction. |
| Missing expected revision for an otherwise authorized request | `REVISION_REQUIRED` (400). No implicit latest or current-token disclosure. |
| Exact revision mismatch after current authorization and association validation | `STALE_REVISION` (409). Refresh via the authorized descriptor route; error does not include raw/current revisions. |
| Operation or contract not implemented | `UNSUPPORTED_CONTRACT` (406) / `OPERATION_UNSUPPORTED` (405). No fallback to raw paths. |

These codes/mappings specify future behavior, not new routes. Messages come from a
bounded static catalog; no exception string, label, path or raw provider response.
Do not distinguish missing/denied/removed to clients. Safe projection may show one
generic unavailable state for a resource association only if its item is visible;
it MUST omit resource_ref/revisions/metadata and hidden-resource counts. ID-less
items can remain visible under their own policy, but cannot receive usable refs.
Responses use `Cache-Control: no-store`; clients must clear retained projections on
logout/workspace change/revocation and must not store them in URLs or ordinary logs.

## 7. Disclosure coverage inventory

A future consumer MUST complete and test this inventory for every enabled operation.
If a surface cannot be safely reconstructed, omit it or deny the operation. Regex
path/secret redaction is defense in depth, not a complete projection boundary.

| Surface / existing seam | Required restricted-client representation |
| --- | --- |
| Item lists/detail/edit refresh (`webapp.api_item`) | Typed item DTO and descriptors; omit raw locator fields. Current raw Web routes are not a safe alternative. |
| Details, title, note, custom fields | Allowlist and classified safe text. Remove `file`/`dir` locator values and credential-like/unknown URLs in **any** field; no hidden raw copy in an edit form. |
| Raw source text, plain-text export/clipboard | No raw source. Reconstructed display text is explicitly noncanonical and not a writable/exportable life.txt substitute. Deny raw export where reconstruction is unsafe. |
| Markdown/HTML/link previews | Build from projected fields; no original anchors/images/tooltips/DOM attributes containing locators or capability URLs. |
| Search, snippets, autocomplete, counts | Query authorized projected data only; do not echo unsafe queries or match hidden locators to reveal existence/counts. |
| Errors, validation, diagnostics | Static safe codes/messages; omit raw snippets, exception paths, internal/provider details and secret query parameters. |
| Capabilities, command catalog, OpenAPI/examples | Version/kinds/action limits only; no configured roots, raw path examples, provider credentials or legacy raw-path suggestion for restricted clients. |
| History, revisions, diffs, recovery evidence | Current AND historical disclosure permission; project before/after, omit journal/artifacts and raw source; uncertainty denies. No byte permission inherited from history. |
| Audit/logs/support evidence | Minimized authorized principal/workspace identifiers, operation, code and policy-approved scoped references/revision tokens; no labels/digests/paths/URLs by default. Protected internal correlation is not a public export. |
| Workspace/sync/package manifests | Opaque scoped workspace/source identities, permitted roles/revisions and descriptors only. No path/relative path/package entry names, download URLs or bytes. |
| Upload receipts and subsequent UI refresh | Existing receipt ID remains distinct. New consumer separately enrolls and projects; all refresh/edit/search routes must obey the negotiated boundary. |
| MCP tools/resources, Remote, Cloud Mailbox wrappers | Project nested results consistently; wrappers/origin/message possession confer no authority. Resource-only hiding cannot leave raw tool results available to the same restricted principal. |
| Browser caches, offline state, copy/share, redirects | No local/provider locator or credential URL in storage, address/referrer, console or action payload; opaque refs are not navigation URLs. Offline replication remains out of scope. |

A URL's HTTPS scheme or absence of a query does not prove public status: capability
secrets can be in the path. Only deliberately public, secret-free, policy-approved
URLs may remain in other projected item fields. Unknown/private/capability/signed
URLs are withheld in full; no query-stripping fallback. Already-authored secrets
in source/history require separate owner remediation; this contract does not erase
history. Saving/displaying metadata is inert: no server fetch, provider login or import.

## 8. Negotiation and compatibility

Choose an opt-in `resource-reference-v1` feature with descriptor contract `"1"`;
a future attachment-operation v2 may carry it. That consumer must explicitly bind
protocol/version and restricted disclosure policy to the authenticated session,
workspace and **all** enabled surfaces. A request header alone is not a policy boundary.

A server MUST advertise it only after coverage and operation tests pass. A restricted
client requires it; absence, unsupported version, partial coverage or disabled operation
fails explicitly. Client and server MUST NOT retry legacy attachment v1 or generic
raw Web routes with the same restricted credentials. Existing auth must deny those
alternate routes to restricted principals; otherwise the deployment cannot claim
conformance, even if its new response is safe. Version discovery must itself be safe.

Keep `attachment-remote-operation-v1.schema.json`, `attachment-chunk-v1.schema.json`,
other attachment v1 schemas and path-based legacy behavior unchanged. Trusted path-aware
legacy clients remain explicitly operator-selected. Local CLI/TUI/MCP on operator-selected
sources retain readable raw access: MCP read/assist/full tool profiles alone are not
external-safe disclosure modes. Remote MCP consumers obey the server policy.

Existing #933 workspace/source identity, authorization, redaction and revision
mechanisms are reused as seams; their existing opaque identities are not a license
to generate deterministic resource IDs or publish digest-correlatable revisions.
#1097 TLS and #1098 at-rest protection remain necessary, separate boundaries.
No schema is added until a concrete consumer and its negotiation/envelope are approved;
do not imply that current `dist/schemas` validates these proposed examples.

## 9. Serialized review examples and acceptance scenarios

The fixtures below are synthetic; neither reference nor revision is a credential.
They are design examples, not executable API calls. MIME/size/label disclosure has
been permitted for this example; digest disclosure has not.

```json
{
  "contract_version": "1",
  "resource_ref": "att:v1:8cb4d9e603a71f25b6c082de49f135a7",
  "kind": "file",
  "display_name": "Quarterly report",
  "size_bytes": 2048,
  "media_type": "application/pdf",
  "source_revision": "rev:v1:4d10b7926ac83f05e914d0cba672853f",
  "resource_revision": "rev:v1:721ba4d085cf639a10e7b82d954f6c30"
}
```

Denied, unknown, removed, wrong-workspace, missing, ambiguous and id-less resolution
all have the same body (future HTTP 404):

```json
{"error":{"code":"RESOURCE_UNAVAILABLE","message":"Resource unavailable."}}
```

Authorized but stale source **or** resource revision (future HTTP 409):

```json
{"error":{"code":"STALE_REVISION","message":"Refresh the resource descriptor."}}
```

Visible item's id-less/ambiguous association with no usable reference:

```json
{"resource_state":"unavailable"}
```

| Review input | Expected contract check |
| --- | --- |
| Bare/uppercase/31 or 33 hex digits, whitespace, percent-encoded reference, extra suffix | Reject exact grammar; over 64 bytes rejected before further inspection. |
| Valid ID stolen or replayed under another principal/workspace | Full current authorization; unavailable even if path/content happen to match. |
| Both revisions match but relation removed/recreated | Old association unavailable; new enrollment has a fresh ID. |
| Same file bytes, another source item edited | Source token stale; full source CAS semantics preserved. |
| Source unchanged, bytes or presentation policy changed | Resource token stale; no old-content or unsafe-metadata fallback. |
| Read-only source, no safe durable server binding | Unavailable; no source write or transient path-derived ID. |
| Approved full digest | Only optional typed content_digest with 64 hex digits; short stored hash/provider ETag cannot fill it. |
| Locator/capability URL in title, note, Markdown, search, history or manifest | Omit/deny before serialization; success receipt alone is insufficient. |
| Negotiation missing or unsafe alternate route enabled | Unsupported/nonconforming; no downgrade. |

Future acceptance must exercise these cases over real enabled surfaces, including
TOCTOU, revocation, restart/restore, hidden-resource counts and cross-workspace digest
correlation. Current compatibility tests establish only that old behavior is intact.
See the [change package](../../.ai/project/changes/resource-reference-projection/design.md)
for evidence and outstanding human review; resolver/byte operations remain #1101.
