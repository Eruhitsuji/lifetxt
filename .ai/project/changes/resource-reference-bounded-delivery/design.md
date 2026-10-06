> Concrete owner approval received 2026-10-07 for the active-session proposal.
> Original proposal-stage gate notes below are superseded for approved scoped runtime
> work; independent latest-head human security/integration and merge review remain pending.

# Restricted bounded HTTP delivery — approved implementation design

## Authority, phase and dependencies

This is a concrete design proposal, not owner approval or executable behavior.
The owner's request authorizes refinement and a reviewable Draft PR. The issue's
explicit Inbox/concrete-design gate remains effective until owner approval.
Method: adaptive-default + W-model. Change type: Security. Assurance: High.
Accountable owner and Merge Authority: Eruhitsuji; implementer: Codex.
Independent human design/security and final integration review remain required.

Latest inspected main includes #1110 / PR #1124's approved bearer-only schemas,
#1112's investigation and #1115 / PR #1123's confined reader integration.
Reuse docs/en/resource-reference-resolution.md as the normative wire contract,
remote_access, collaboration membership, remote_backend item visibility,
attachment policies and attachment_snapshot.read_snapshot. No replacement writer,
provider fetching, Format changes, mandatory dependency or .ai/managed edits.

Owner decisions requested together: accept these concrete persistence/resolution/
delivery designs, proposed configuration boundary, sequential subunits and High
risk treatment. Until accepted, no runtime/schema/config edits and no capability
advertisement. Approval authorizes implementation, not merge/release/deployment.

## Decomposition before Ready

The original thin-adapter scope does not include all configuration and isolation
work. Treat #1114 as two sequential S units, not one oversized runtime patch:
(A) default-disabled policy registration and all-route authentication isolation,
(B) three-operation delivery/admission adapter. Before runtime implementation,
record separately tracked child contracts with scores <=6 and exact extension
selection/write scope. Both remain in this one integration branch/final PR.
No additional network feature, browser consumer or deployment is authorized.

## Proposed operator configuration (new, needs owner approval)

Add remote.resource_references with enabled=false (bool), workspace_id=null
(nullable canonical 64-hex handle), store_path=null (nullable private server path),
enrolled_items=[] (bounded source_id/item_id/attachment selector records),
metadata={label:false,size:false,mime:false,digest:false},
limits={file_bytes:10485760,chunk_bytes:65536,active_process:2,
active_principal:1,rate_principal:30,rate_process:120,deadline_seconds:30}.
Only smaller positive configured ceilings accepted (file zero may deny bytes).
This is protected server configuration, not writable through restricted HTTP.
Private enrollment selectors only select existing authored associations; never
create attachment authority or rewrite source IDs. Existing source/attachment
policies are additional gates. No token/digest/secret values in this setting.

Add remote principal disclosure_mode with existing default trusted and explicit
restricted-resource. Mode cannot be selected by a request header. Restricted
principal credentials must be dedicated, unique and separate from trusted Web,
legacy Remote, proxies/browser sessions. attachment:read is an explicit scope;
roles remain unchanged. Changing mode/config revokes old credentials/session
binding; cannot reuse an old token in a newly trusted mode. If the existing auth
model cannot prove rotation/isolation, refuse enablement.

Settings must update authoritative extension/registry types/defaults/provenance,
restart-required metadata (restart true for consumer/storage/identity; existing
current read policy reload for scopes/membership/disclosure), secret=false,
contract version=1, config explain, template, EN/JA docs, fixtures and downgrade
rejection tests together. No mandatory dependency. Reject unknown future versions.
A config option alone never certifies reachable-route isolation.

## Isolation and exact dispatch

Initial consumer is bearer-only as approved in #1110; browser/proxy/session support
is deferred. Install a guard ahead of all generic Web/Remote route/middleware
payload producers, including unknown routes, methods, login, history, search,
capability, tool wrappers and generic error handlers. Recognize restricted credential
before generic version negotiation; missing/changing version never changes mode.
Deny alternate routes with static 404 RESOURCE_UNAVAILABLE. No shared-token,
anonymous raw workspace reachability, trusted credential overlap or browser session
exchange. Require verified isolated generic network exposure; otherwise startup
refuses safe consumer enablement. In-process wrapper tests alone cannot certify
production reverse-proxy/listener exposure; record that as deployment prerequisite.

Permit only POST /api/remote/v1/resource-references/{discover,full,chunk} and a
minimal allowlisted handshake after complete coverage. Exact method/path matching;
no trailing-slash aliases. Exact X-Lifetxt-Remote-Version: 2 and
X-Lifetxt-Resource-Contract: resource-reference-v1, no duplicate/comma values.
TLS mandatory even loopback via existing effective-origin trusted immediate-peer
policy. Reject URL userinfo/query, ambient cookies, proxy identity supplementation,
Range/If-Range, compression, malformed Content-Type and ambiguous headers.
No redirect or fallback. OPTIONS/CORS denied; unknown paths use static outcomes.
Only these POST pairs bypass mutation clock/write-read-only classification; they
still require explicit read membership. Actual mutations keep existing guards.

## Parse, admission and send

Apply bounded pre-auth 120/min process rate before body work. Operation admission
reserves two/process and one/principal, no queue, retained through receive,
validation/snapshot, serialization and transport completion/physical worker stop.
Honor lower existing limits. 30/min principal and 120/min process; failures count.
Absolute monotonic deadline 30s includes body receive, hashes, policy rechecks and
send. Propagate remaining time to confined reader; cancel/disconnect cannot release
a slot while a physical worker remains alive. Reuse supervisor's cleanup evidence;
if needed expose minimal reviewed lifecycle acknowledgement seam in a child scope,
never infer cleanup solely from caller timeout.

Read <=2048 wire bytes once. Strict UTF-8 JSON object, no BOM/duplicates/unknown
fields/nonfinite values/bool integers. Exact schemas and semantic byte bounds;
missing action revisions uses REVISION_REQUIRED. No arbitrary paths in envelopes.
Resource cap min(10MiB, existing), chunk 1..min(64KiB, existing), offset bounded;
full exact immutable snapshot verified each request, including chunks.

Recheck current principal/membership/source/association/exact tokens before headers
and every <=64KiB emission, within the same deadline. Revoked/changed before headers
gives fixed unavailable/stale; after headers abort transport with no appended JSON.
Never combine changed bytes. ASGI send timeout bounded; disconnect handling and
normal completion tested with actual sockets, not only TestClient buffering.

Success is 200 application/octet-stream, attachment filename download.bin, exact
Content-Length, nosniff, private/no-store, no-referrer, same-origin CORP, DENY frame,
contract CSP and validated expected token headers. Chunk adds next-offset/EOF only;
no digest/ETag/Last-Modified/Content-Range/Location/CORS/compression/provider redirect.
Discovery/errors use the same protective headers and static #1110 catalog. Audit
allowlist: principal ID, workspace handle, operation, static outcome and request ID;
never request bodies/filenames/paths/URLs/digests or public tokens.

## Coverage and operational limitations

Real HTTP tests: unauthenticated/unknown/IDOR/hidden/removed/stale/symlink swap,
chunk revision mix, body/bool/offset/cardinality bounds, rate/concurrent admission,
slow receive/send, cancellation and stuck-worker slot retention, HTML/SVG inert
attachment, TLS/proxy spoofing, cookie/CSRF-mode refusal, read-only membership,
downgrade and every route/method/wrapper/history/search/capability/error denial.
Legacy/local contracts must stay green. Linux x86_64 glibc/helper/local-root proof
is mandatory; other platforms return unsupported, never portable path fallback.
Capability remains disabled unless all dependencies and full restricted-route
coverage pass. Runtime tests cannot claim real-host isolation or filesystem proof.
Rollback disables consumer and stops workers before reverting; no DB/epoch restore,
credential rollback, automatic deletion, release or deployment included.

## Selected integration details

Policy/isolation is #1125; delivery/completion is #1126. Configuration extension
is schema_extensions_v34.py, with config_registry/config_validation/template and
generated config-v1 metadata. The final bootstrap installer selects a dedicated
ASGI application after all legacy route wrappers, so no generic route is mounted.
No browser/proxy principal or automatic capability advertisement is added. Linux
source continuity includes exact bytes AND inode/size/mtime/ctime/root fingerprint;
observed source changes atomically retire its associations. Dedicated credentials
are pinned in memory and rechecked at every config/authority reload. Initial label
remains Attachment and verified MIME remains octet-stream even when optional flags
are enabled. TLS/proxy/real-host prerequisites remain operator acceptance boundaries.
