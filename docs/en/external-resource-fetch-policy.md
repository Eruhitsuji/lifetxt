# Explicit external resource fetch/import policy

[日本語](../ja/external-resource-fetch-policy.md)

## 1. Status and authority

This is the documentation-only contract for #1129, Task A of the
[owner-accepted #1103 investigation](https://github.com/Eruhitsuji/lifetxt/issues/1103#issuecomment-6027182964).
MUST/MUST NOT describe a future conforming consumer; they do not describe an
available command, endpoint, configuration option, scope or schema. No concrete
consumer, destination, provider or account has been selected. Independent human
design/security and latest-head integration review are required before adoption
and merge. Implementer self-review is informational, not final approval.

The initial candidate is an explicit, default-disabled public-file import from
approved HTTPS origins. The current [resource-reference runtime](resource-reference-runtime.md)
serves enrolled local files, not arbitrary URLs or cloud objects. This contract
does not extend its restricted bearer credentials. Format, `ref:` item linkage,
local `file:` / `dir:` and preserved inert custom keys remain unchanged.

## 2. Separate operations and current permission gates

| Operation | Required boundary |
| --- | --- |
| Author/display/project a reference | Inert: no DNS, HEAD, HTTP, favicon, preview or remote existence check |
| User-triggered public browser open | Deliberately public, secret-free, policy-approved URL; safe plain DOM, noopener/noreferrer and referrer suppression; no server fetch |
| Provider mediation | Separate approved consumer with exact object/profile/account binding from #1102; not an arbitrary URL fallback |
| Explicit fetch | Current authentication and workspace/source/item/resource/action permission, explicit network-reach grant, owner-approved destination and enforced egress policy |
| Import local copy | All fetch gates plus current source/item write membership, writable/non-generated source, supported Format, read-only/write-clock guards and exact source revision |
| Render/OS open/archive expansion/sync | Separate capabilities; fetch success grants none of them |

Role, `read`, `attachment:read`, upload receipt, cached descriptor, object
possession, Mailbox storage credentials, request `origin` or `attachment_refs`
MUST NOT grant network reach or import. Permission and profile selection are
server-controlled and revalidated per operation. Unclassified input or missing
policy MUST be denied **before DNS**. The actual future scope names, routes and
wire versions require a separate approved consumer contract; none is registered here.

Revalidate current permission and profile generation at each connection/redirect,
cancellation checkpoint and before delivering bytes or committing. Revocation or
uncertain continuity stops the operation; already delivered bytes cannot be recalled.

## 3. Conceptual typed profile and intent

These are conceptual fields, not usable lifetxt configuration. Operator-owned
profiles MUST bind immutable identity/generation to the install/workspace,
approved authority, egress mode and effective limits. Aliases are selection names,
never authority; rebinding an alias MUST NOT silently redirect existing operations.

| Conceptual field | Type and validation |
| --- | --- |
| `profile_alias` | Bounded ASCII selection string, exact comparison; operator resolves it to immutable profile identity/generation |
| `approved_origins` | Nonempty bounded set of exact HTTPS host/443 origins; no substring or wildcard match |
| `path_policy` / `query_policy` | Typed approved paths/query parameters; no arbitrary service proxy/URL-forwarding requests |
| `egress_mode` | Initial direct connection only; proxy adoption requires its own reviewed destination enforcement |
| `operation_id` | Bounded non-secret operation identity, bound to principal/workspace and intent; not a bearer grant |
| `source_selector` / `item_selector` | Server-resolved unambiguous current source/item; no client local target path |
| `expected_source_revision` | Exact existing whole-source CAS validator, never wildcard/implicit latest |
| `public_url` | Bounded strict URL, explicitly public and secret-free under policy; unknown, authenticated, capability or signed input is denied |
| `expected_content_digest` | Optional typed full SHA-256 of exact bytes, not provider ETag or short stored hash; disclosure-controlled |

Future validators MUST reject duplicate keys, unknown fields, invalid encoding,
controls and overlong input without echoing it. Bounds and exact wire field names
must be published only after a concrete consumer is approved. Provider object ID
and provider revision, if a later mediation consumer uses them, MUST remain exact
opaque strings under #1102; URL normalization rules MUST NOT be applied to them.
Credential values, caller headers, proxy choices and filesystem destinations are
not intent fields. Secret references remain protected server metadata.

Illustrative **internal intent only**, using reserved example data. It is not an
HTTP request or a configuration file to paste into an installation:

```json
{
  "profile_alias": "approved-public-docs",
  "operation_id": "example-operation-001",
  "source_selector": "example-source",
  "item_selector": "example-item",
  "expected_source_revision": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "public_url": "https://downloads.example.com/report.pdf"
}
```

The example origin is not approved by this document. Merely supplying these fields
MUST NOT cause a connection, enroll a profile or bypass current permissions.

## 4. URL and redirect rules

Initial operations MUST use HTTPS, port 443 and GET only. HTTP, file, FTP, gopher,
data, javascript, Unix sockets, alternate ports and caller method/body overrides
are outside scope. One strict parser MUST parse once and preserve a single
validated interpretation through connection and request construction.

Hosts MUST be bounded ASCII (only preapproved A-labels when needed). Reject
userinfo, fragments, controls/CRLF/NUL, backslashes, malformed percent encoding,
percent-encoded or ambiguous authority, trailing-dot hosts, IPv6 zone IDs and
alternate decimal/octal/hex IP forms. IP literals are not accepted initially.
Scheme/host/port MUST match an approved origin exactly after the explicitly
documented URL canonicalization. Path/query policy MUST also match. Query fields
are not public merely because their names are unfamiliar. Signed/capability
evidence takes precedence over a public declaration; uncertain input is denied.

Automatic redirect following MUST be disabled. The initial redirect limit is
**0**. A separately approved profile may later allow at most **3** hops, with
cycle detection and all URL, permission, classification, DNS/IP/peer and egress
checks repeated at every hop. Relative Location is resolved against the current
URL by the same parser and validated before any request. Reject downgrades and
unapproved origins. Rebuild headers even on same-origin redirects. Never forward
Authorization, Cookie, Referer or origin-specific credentials across origins;
another credential binding requires separate explicit permission.

MUST NOT follow HTML meta-refresh, JS/CSS/images, favicon, Link preload,
Content-Location, Alt-Svc, service discovery, HTTP/2 origin coalescing or HTTP/3
address migration as alternate routing. Initial transport must keep one approved
origin and validated connection destination.

## 5. DNS, actual peer and egress

Origin approval alone MUST NOT authorize its resolved addresses. After the
pre-DNS gates, use an operator-controlled resolver path with bounded duration,
answer count and CNAME handling. Validate every final A/AAAA candidate; reject a
mixed permitted/denied set, excessive answers or uncertain classification.

MUST deny loopback, private/ULA, link-local, unspecified, multicast, shared/CGNAT,
documentation/reserved and special-purpose ranges, plus operator internal/service
networks and explicit IPv4/IPv6 metadata endpoints/names. Deny overrides origin
approval. Use maintained explicit address classification, not only the runtime's
`is_private` flag. IPv4-mapped IPv6 requires embedded IPv4 checks. Transition,
tunnel/NAT64 destinations are denied initially; egress must enforce equivalent
restrictions after translation. Globally numbered internal services also belong
in the operator denylist.

Connect only to a selected validated IP, preventing a second unchecked DNS lookup.
Preserve the approved hostname for Host, SNI and TLS certificate verification;
MUST NOT disable certificate validation. Verify the actual direct peer matches
the selected address. Retries, fallback/Happy Eyeballs, redirects, pooled or new
connections MUST follow the same gates. Pools must be scoped to profile,
authority, validated address and policy generation; uncertain reuse is denied.

Application peer checks alone cannot certify NAT, routing or a proxy's final
destination. Enforced egress rules are required, including translated/internal
destinations. Unsupported enforcement MUST refuse service, not fall back to a
generic URL client. Outbound proxy trust is separate from inbound
`remote.trusted_proxies` and TLS-origin handling in #1097.

## 6. Headers, proxies and credentials

The connector MUST build a fresh allowlisted request: approved Host/SNI, fixed
User-Agent, Accept and `Accept-Encoding: identity`. No caller-controlled headers,
Authorization, Cookie, Proxy-Authorization, Referer, Range, arbitrary method/body
or provider/session credentials. It MUST NOT discover environment
HTTP(S)_PROXY/ALL_PROXY/NO_PROXY, netrc, browser/OS sessions or persistent cookies.

An explicitly adopted outbound proxy must prove identity/TLS, origin destination
and DNS/IP/translation enforcement, redirect behavior and minimized log/spool
retention. Checking only the proxy peer is insufficient. Unsupported proxy
topologies are unavailable. Authenticated provider mediation is a separate task:
verified tenant/account/object scope, external secret references and no public
fetch or ambient-account fallback. Capability URLs stay in external secret
facilities; signed URLs are operation-scoped ephemeral secrets generated only
after explicit authorization. Neither is accepted by the initial public consumer.

## 7. Proposed budgets and content acceptance

These are future-consumer contract budgets, **not available settings**. Owners may
lower effective limits. Raising them or adding compression/retries needs separate
review. Compare encoded and decoded counts even when identity makes them equal.

| Budget ID | Limit |
| --- | --- |
| L1 wire/decoded body | Each min(10 MiB = 10485760 bytes, configured attachment max_file_bytes) |
| L2 encoding | Identity only; reject unknown/nonidentity Content-Encoding; no automatic decompression |
| L3 headers | 32 KiB = 32768 bytes total, at most 100 fields |
| L4 network | Total 30 s for DNS/connect/TLS/body; connect 5 s and idle 5 s within total monotonic deadline |
| L5 concurrency | 2 per process, 1 per principal; no unbounded waiting queue |
| L6 rate | 30 operations/principal/min and 120/process/min; includes failed admitted attempts |
| L7 retry | 0 initially; later at most 1 pre-body transient GET retry within the same total budget and renewed gates |
| L8 redirects | 0 initially; separately approved future ceiling 3, never automatic |

Every resource phase must also have bounded CPU/memory/physical-worker lifetime.
The network deadline is not a claim that filesystem commit cannot block. The
future import consumer MUST define a bounded supervised validation/commit budget,
stop admission safely on stuck work and retain capacity until physical termination.
Do not release a slot merely because a client disconnected or a logical timer fired.
No arbitrary queue, cache, spool or large allocation is allowed outside the budget.

Accept only a complete 200 body initially. Count streaming bytes regardless of
Content-Length. Reject partial 206, inconsistent/duplicate framing or encoding,
unexpected status, truncation, length mismatch or exceeded deadlines. Adding
compression requires separate encoded/decoded size, ratio, layers and CPU limits.

MIME, provider names and Content-Disposition are untrusted. Reuse upload
`content_type` and attachment MIME/executable policy without weakening it. Check
observed content, declared MIME and filename policy; conflicting/unknown types
require an explicitly approved inert-binary policy or rejection. Magic checks
are not proof of harmlessness or absence of malware. Use generated create-only
managed paths and safe authored labels, never a URL/provider basename as a target.
No active preview, executable launch, macro execution, HTML subresource fetch or
automatic archive expansion; approved archives remain inert bytes.

## 8. Disclosure, secrets and local copies

Remove query/fragment/userinfo from ordinary diagnostics **and suppress the whole
URL**, because path components can be capabilities. Fresh DTOs MUST allowlist
only necessary operation/outcome and authorized correlation handles; alias,
host/account/object, secret handles, labels and digests are not public by default.
No raw Location, DNS/TLS/provider exception, headers or bodies may escape.

| Surface | Required minimization |
| --- | --- |
| Raw/details/note/custom/Markdown/export/edit forms | No hidden raw locator/secret copies; construct allowed projected text or deny |
| Search/snippets/previews | Authorized projected data only; no unsafe query echo or implicit HTTP |
| History/diffs/audit/support/logs | Current and historical disclosure permission; static outcomes and minimal correlation, no raw URL/exception fallback |
| Browser DOM/storage/copy/referrer/redirect | No secret/provider locator; no-store, cleared state on logout/workspace change, no frontend signed-URL redirect |
| Mailbox/MCP/Remote wrappers | Project nested results consistently; origin, storage possession and attachment refs confer no authority |
| Cache/worker arguments/temporary files | No shared response cache, cookies, disk spool or secrets in command lines; external secret facility only |

Downloaded bytes become a separate local confidentiality responsibility under
[the at-rest policy](at-rest-confidentiality.md): final files, atomic temps,
transaction before/after artifacts, backups, proxy spool, swap/hibernation and
crash dumps. Bounded memory is the initial staging choice, not a guarantee against
persistence. Future disk staging requires approved owner directories 0700/files
0600, link rejection, size/retention limits and cleanup ownership. Normal unlink
is not secure erasure. SQLite or a reference index is not encryption.

Existing user-authored secrets need non-echoing warnings, provider revoke/rotate,
explicit owner repair and inventory of history/Git/journal/backups/export/browser
copies. Do not silently rewrite/delete them or claim historical erasure. Existing
generic raw surfaces are not made safe by publishing this contract.

## 9. Exact import, recovery and replay

Use: current authority + exact source precondition → approved fetch → complete
content/version/digest validation → recheck current write authority and source CAS
→ ordinary attachment transaction → committed receipt → optional enrollment.
Network work MUST NOT hold a source lock. Source changes yield a conflict, never
automatic replacement of the expected revision with latest.

Reuse `attachment_transactions.put_attachment` with `require_revisions=True`,
the exact `item_revision` and `attachment_expected_revision=MISSING_HASH`, through
the existing domain transaction. Do not call the HTTP upload endpoint internally
or introduce another writer. Use an owner-controlled create-only managed root;
revalidate confinement/link policy at the mutation boundary, not only before fetch.
Existing expected provider revision and full digest, if present, must match exact
bytes. Provider ETag/version, short stored hash and whole-source revision are
distinct. A public URL copy does not promise that future URL bytes remain identical.

Multi-target writes are journal-backed compensated operations, not portable atomic
replacement of unrelated files. A consumer MUST inspect final commit/recovery state
and never report success for mismatched reference/bytes. Pre-commit failure discards
owned staging and adds no reference. Only proven operation-owned empty namespaces
may be cleaned; another operation's files/journal must not be removed. Once commit
starts, cancellation/disconnection is not evidence of non-application. Retain the
worker slot, inspect the journal and expose a safe recovery-needed outcome when
uncertain. Existing explicit resume/compensate procedures remain owner-controlled;
do not hide failures by automatic journal deletion.

Future idempotency MUST bind operation ID to principal/workspace, secret-free
intent/profile generation, exact source expectation and validated byte digest.
Replay identity and lookup metadata MUST NOT persist a raw URL: use protected
non-secret locator identity and scoped opaque equality validators where intent
could disclose private query/path material. Unknown or secret-bearing intent is
rejected by the initial public consumer rather than hashed into an apparent grant.
Same ID with different intent/digest is rejected. Existing transaction_id alone
does not establish a complete fetch replay protocol. A lost receipt requires an
authorized committed-outcome lookup, not blind redownload or duplicate attachment.
Resolve uncertain commit state before retry; URL bytes may change between requests.
Enrollment failure does not undo a committed attachment and must not trigger a
second import. Fetch-only has no source write. Provider reference, imported local
copy and its descriptor are separate; there is no background mirror/sync.

## 10. Future negative verification matrix

All rows are **unimplemented/unrun fetch requirements**, not passing test results.
Controlled connector tests and actual deployment review must establish them later.

| Case ID | Input/event | Required outcome |
| --- | --- | --- |
| N01 | Display/hover/Markdown/metadata refresh | Zero DNS/HTTP calls |
| N02 | Reader/local-resource bearer/Mailbox origin only | Deny before DNS |
| N03 | Alias rebound/account or profile generation changes | Old operation unavailable; no authority substitution |
| N04 | Loopback/private/link-local/ULA/metadata/CGNAT/special/internal | Block even behind approved host |
| N05 | Mapped IPv4, transition/NAT64 or translated internal peer | Embedded/post-translation policy enforced or unavailable |
| N06 | Encoded/alternate IP, userinfo, backslash, zone ID, CRLF | Strict rejection, no second-parser reinterpretation |
| N07 | Public DNS then private connection; mixed A/AAAA/fallback | Only validated peer allowed; uncertain set rejected |
| N08 | Redirect to private/HTTP/unapproved host/cycle | Default rejection; every allowed hop checked, ceiling 3 |
| N09 | Cross-origin credentials, env proxy/netrc/cookies | No forwarding or ambient load |
| N10 | Path capability/signed URL/raw provider exception | No persistence, log/export/referrer or frontend redirect |
| N11 | Compressed bomb/lying length/slow stream/truncated/206 | Bounded abort; no import |
| N12 | Executable MIME spoof, unsafe filename, HTML/archive | Reject or explicitly inert bytes; no execution/expansion/fetch |
| N13 | Source changes after body/provider version or digest mismatch | Exact conflict; no latest fallback |
| N14 | Disconnect/partial compensation/unknown commit | Inspect journal, retain capacity; no silent mismatch/blind retry |
| N15 | Lost receipt/different intent same ID/enrollment failure | Authorized outcome recovery, no duplicate import |
| N16 | Stuck physical worker/unsupported proxy or egress | Capacity retained, bounded supervision, refuse service |
| N17 | Raw alternate route/search/history/Browser/Mailbox wrapper | No disclosure bypass; current and historical policy |

## 11. Proposed enablement and gated follow-ups

A concrete consumer MUST pass all gates before advertisement or enablement:

1. Owner selects the exact surface, public destinations and privacy/operational
   purpose; no general Internet or provider account is selected by this contract.
2. Separate Ready XS/S tasks establish typed wire/config contracts and explicit
   grants; restricted local-resource credentials cannot acquire fetch/write.
3. Independently reviewed connector proves N04–N09 with controlled fixtures;
   approved egress/proxy/NAT/TLS topology is verified at deployment.
4. Content/import/recovery/idempotency prove N11–N16 and exact current authority;
   every budget covers real physical work, with safe stuck-worker handling.
5. All enabled surfaces prove N01–N03/N10/N17; no raw alternative, unsafe cache,
   secret error or private locator is exposed.
6. Latest-head human design/security and integration review, required CI,
   operator storage protection and rollback plan are accepted before enablement.

| Task | Size / gate |
| --- | --- |
| A (#1129) | S: this bilingual documentation/package/registry contract only |
| B | S: validated-address single-hop public HTTPS connector plus controlled fixtures; A and selected consumer/destinations required; no public route |
| C | S: transaction import core, recovery and idempotency; A/B required; reuse existing writer, no public API |
| D | S: one explicit opt-in consumer, operation authorization/disclosure and deployed egress verification; A/B/C and owner surface selection required |

B–D are plans, not implemented capabilities or automatically Ready issues.
Credentials/provider mediation, signed/capability ingress, redirects/proxy,
compression, Format and generic sync are not bundled into the initial public-file
batch. No endpoint/config/schema is published by Task A. Rollback for A is a
documentation/package/registry revert only; a future consumer needs its own
disable-before-rollback and committed-data recovery policy.

## 12. Evidence and references

The [High change package](../../.ai/project/changes/external-resource-fetch-policy/design.md)
maps acceptance criteria to both languages, verification and pending human reviews.
Existing attachment/upload/transport tests establish compatibility only; no
network-reach, SSRF or future fetch consumer is certified by prose or skipped tests.

External primary references checked on 2026-10-07 JST:

- [OWASP SSRF Prevention](https://cheatsheetseries.owasp.org/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html): allowlisting, redirect control and connection-bound DNS defense.
- [RFC 9110 §15.4](https://www.rfc-editor.org/rfc/rfc9110.html#section-15.4): redirect header reconstruction and sensitive fields.
- [IANA IPv4 special-purpose registry](https://www.iana.org/assignments/iana-ipv4-special-registry) and [IPv6 registry](https://www.iana.org/assignments/iana-ipv6-special-registry): address classification inputs.

The exact limits, stricter initial policy and enablement gates here are lifetxt
design choices derived from the approved investigation, not universal guarantees
or external-standard mandates. #1095 transactions, #1097 transport, #1098 at-rest,
#1100 projection and #1102 private authority remain independent boundaries.
