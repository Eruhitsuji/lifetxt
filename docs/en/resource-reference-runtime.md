# Restricted resource discovery and downloads

The dedicated HTTP consumer uses the existing optional Web transport dependencies; install `pip install "lifetxt[web]"` before serving. The binding/resolver modules add no mandatory dependency.

[日本語](../ja/resource-reference-runtime.md) · [Wire contract](resource-reference-resolution.md)

This experimental consumer implements #1111/#1113/#1114 with dedicated bearer-only
Remote protocol 2 operations. It is disabled by default. Enabling it replaces the
entire Web application with a dedicated ASGI application: no GUI, OpenAPI, generic
Web, legacy Remote, browser login, proxy identity, MCP, search, history, mutation or
capability-manifest routes are mounted. The generic Web application must not be
served on another reachable listener for the same workspace. Network exposure and
immediate-peer proxy configuration are deployment responsibilities; automated local
tests cannot certify a deployed host. There is no automatic capability advertisement
or legacy-client fallback. Other platforms retain ordinary local features, but this
consumer requires the reviewed Linux x86_64/glibc helper and its root/kernel/local
filesystem conditions. Missing prerequisites refuse startup or service.

## Operator setup

1. Build/install the [optional confined snapshot helper](attachment-snapshot-helper.md).
   Use concrete local regular-file sources (at most 100); no glob/directory source,
   symlink, hardlink, writable-by-other-user root or unsupported filesystem fallback.
2. Create a private state directory owned by the server user, mode 0700. Explicitly
   provision a fresh index; startup never creates/replaces a missing/corrupt DB:

   ```python
   from lifetxt.resource_reference_store import BindingStore
   BindingStore.provision("/srv/lifetxt-private/bindings.sqlite")
   ```

   Paths here are operator examples, never request fields. DB and owner lock are
   0600. SQLite DELETE journaling with synchronous FULL is selected for one owner;
   foreign/restored WAL, SHM or journal state is refused, never adopted/replayed.
   SQLite is not encryption; the existing at-rest policy and trusted local writer
   assumptions remain applicable. DB identity/epoch/root permissions are rechecked
   for transactions. State is bounded at 10,000 active bindings/50,000 total bindings
   and token records, including tombstones; no automatic deletion, eviction or reuse.
3. Configure a named workspace with **explicit collaboration membership**. A global
   reader/owner role alone is insufficient. Configure dedicated principal credentials
   via distinct `token_env` references; never reuse generic Web, legacy, proxy/browser
   credentials. Every active principal on the dedicated application must have
   `disclosure_mode: "restricted-resource"`. Add `attachment:read` explicitly to
   principals permitted to download; a role does not imply this scope.
4. Set `remote.resource_references.enabled` true, selected `workspace_id`, absolute
   `store_path` and owner-approved `enrolled_items`. Each selector contains exactly
   `source_id`, canonical authored `item_id`, and the exact existing `file:` detail
   value in `attachment`. It selects an existing association, never creates source
   IDs or adds files. Provision workspace/source handles to clients out of band.
   The example [configuration](../../examples/config/resource-references.lifetxt.json)
   remains disabled until customized. On startup the first active principal must be
   authorized to verify all selected associations; otherwise startup fails. Client
   discovery cannot enroll, repair state or supply paths.
5. Launch a **single** server with the selected config, for example
   `lifetxt --config lifetxt.config.json serve --read-only`. TLS is required even on
   loopback; serve behind a correctly isolated TLS terminator with an explicitly
   trusted immediate peer, or use a TLS ASGI server. Preserve the actual ASGI peer:
   disable Uvicorn proxy-header rewriting. Spoofed forwarding from untrusted peers
   does not satisfy TLS. Never cohost a generic/raw listener as an alternate route.

## Configuration metadata and changes

All new values come from protected operator JSON configuration, not HTTP or an
environment override (except the existing credential `token_env`). They are non-secret,
introduced in 1.0.3 with resource contract version `"1"`; none is deprecated and none
has a replacement. The authoritative config-v1 schema and `config explain` registry
contain their types/defaults. Metadata and grants reload for every operation;
consumer/storage/selectors/limits and principal identity/mode require restart.
Unsupported future contract versions and unknown/malformed resource settings fail
validation and startup. Changing modes requires new credentials and restart; the
running dedicated app pins credential digests and cannot upgrade an old bearer into
a trusted identity. Do not roll credentials back when reverting configuration.

| Setting | Type/default | Change policy |
| --- | --- | --- |
| remote.resource_references | object, defaults below | Protected operator-only configuration |
| enabled | bool false | Restart; explicit opt-in |
| contract_version | string "1" only | Restart; no downgrade |
| workspace_id | canonical 64-hex string/null, null | Restart; explicit selected workspace |
| store_path | absolute string/null, null | Restart; pre-provisioned private index |
| enrolled_items | array, [] | Restart; exact source_id/item_id/attachment selectors |
| metadata.label | bool false | Current policy; initial implementation always uses Attachment |
| metadata.size | bool false | Current opt-in for verified size_bytes |
| metadata.mime | bool false | Current opt-in; verified initial MIME is application/octet-stream |
| metadata.digest | bool false | Current separate opt-in; full snapshot SHA-256 only |
| limits.file_bytes | integer 10485760 | Restart; only lower; existing file policy also applies |
| limits.chunk_bytes | integer 65536 | Restart; only lower; existing chunk policy also applies |
| limits.active_process | integer 2 | Restart; only lower; includes pre-auth preparation/send |
| limits.active_principal | integer 1 | Restart; fixed ceiling 1 |
| limits.rate_principal | integer 30/min | Restart; only lower; lower existing principal rate wins |
| limits.rate_process | integer 120/min | Restart; only lower; pre-auth global ceiling 120/min |
| limits.deadline_seconds | integer 30 | Restart; only lower; receive/verify/hash/send included |
| remote.principals.*.disclosure_mode | trusted/restricted-resource, trusted | New credentials + restart; no request-selected mode |

File and source reads use immutable verified snapshots; source cap 1MiB and 5,000
items/source, 10,000 items/workspace. Discovery is at most 16 descriptors and 32KiB.
Full hashing repeats during bounded emission to verify current association/revisions;
small slices also require full verification. CPU/I/O cost can grow with the number
of emissions/sources; all work shares the absolute deadline. Failures count toward
admission/rates. Disconnect/cancellation retains slots until physical workers stop,
even if OS cleanup stalls. The optional audit uses only principal/workspace handles,
operation, static outcome and generated request ID; no bodies/refs/tokens/paths/digests.

## Client operations

All three exact endpoints use POST JSON, with no query parameters:

- `/api/remote/v1/resource-references/discover`: contract_version/workspace_id/source_id/item_id.
- `/api/remote/v1/resource-references/full`: contract_version/workspace_id/resource_ref/source_revision/resource_revision.
- `/api/remote/v1/resource-references/chunk`: full fields plus nonboolean integer offset and length (1..65536).

Send `Authorization: Bearer` with dedicated credentials, `Content-Type: application/json`,
`X-Lifetxt-Remote-Version: 2`, and
`X-Lifetxt-Resource-Contract: resource-reference-v1`. Maximum body is 2048 bytes;
duplicate keys, unknown fields, booleans in integers, BOM, compression, cookies,
Origin/browser Fetch-Metadata and proxy principal identities are rejected. Unsupported
negotiation never falls back. Keep both returned revision tokens exactly unchanged
for full/every chunk. See the [published envelope schemas](resource-reference-resolution.md).

Successful full/chunk returns binary 200, application/octet-stream, fixed
`attachment; filename="download.bin"`, exact emitted Content-Length and validated
revision headers. No inline preview, digest ETag, redirect, provider fetch or CORS.
Chunk includes next-offset/EOF; offset==size yields empty 200, offset>size is invalid
after authorization. Range/If-Range are rejected, not converted to latest/full reads.

Validate returned tokens, content type, length, next-offset and normal transport
completion. Discard the **entire accumulated result** on stale/unavailable, abort,
incomplete transport or header mismatch; rediscover under current authority.
An empty file is complete only with Content-Length 0 and normal completion.
A change/revocation before headers returns a static safe error; after headers the
connection aborts, without JSON appended to the binary stream. Delivered/saved bytes
cannot be recalled. Authorized stale returns STALE_REVISION; hidden, wrong-workspace,
missing, ambiguous, revoked or retired bindings share RESOURCE_UNAVAILABLE.

## Identity lifecycle and recovery

Every process start/recovery creates a new random public-reference epoch. Old IDs
and tokens never survive a clean restart, copied DB or backup restoration. Enrollment
revalidates current sources without writing them. Duplicate/id-less items never get
invented IDs. Source bytes/identity changes invalidate all observed associations;
missing/link/identity uncertainty retires the affected reference. Detach/recreate gets
a new ID, even for the same path/bytes. Verified rename continuity and stable restart
reuse are not implemented. A same-uid malicious writer or privileged compromise is
outside the helper/index guarantee; inode checks do not establish hostile-writer ABA
proof. Store failure/quota exhaustion refuses service; owner-directed retirement is
a separate operation, never automatic cleanup.

To roll back, stop/disable the consumer and workers before reverting code/settings.
Do not restore an old public epoch or old credential, and do not delete the index
without a separately approved owner action. Tests verify local helper/domain/ASGI and
real HTTP behavior; they do not certify every Linux filesystem, actual proxy topology,
privileged host isolation or disk/D-state cancellation. Independent latest-head human
security/integration review remains required before merge.

Audit storage must be pre-created 0600 in a server-owned 0700 directory and must
not alias a source, enrolled resource, configuration, index or index sidecar.
Audit validation is repeated before writing; unsafe/missing sinks refuse service.

Each index transaction also checks and advances a persisted sequence against the
current in-memory sequence. Restoring an older same-epoch DB in place is detected,
so a previously detached reference cannot be revived within a running process.
