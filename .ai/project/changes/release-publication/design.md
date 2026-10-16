# Design and test plan

Implement #1311 → #1305 → #1312 → #1313 sequentially on one user-authorized
integration branch; #1314 supplies the shared pure recovery policy and runbook.
Source origin/main 65162fb8; final PR base main. Owner/Integrator/Release Authority
Eruhitsuji; Executor Codex. Existing cap-distribution-channels and numeric version
parser are extended/reused. No product format/version change. Phase Implementation
and Verification, inherited adaptive-default/W-model; High assurance.

## Trust and authority

The controller checkout is the immutable workflow SHA, main/manual/repository/API
run-bound and tracked-clean. Source is a main ancestor with successful same-source
CI. A completed current preflight run must match all five reusable controller SHAs,
all 13 producer jobs and exact API artifact references/creation/expiry. Verify final
ZIP API size/hash before bounded safe extraction; rehash exact bundle file inventory,
download original payload ZIPs and rerun every offline producer validator. Rebuild
the aggregate and assemble the original OCI index without rebuilding images. Repeat
API/CI/expiry checks. A plan seals source/version/bundle/final artifact/inventory/index
and publication controller/run/attempt; it has no self-granted authority.

Read-only prepare emits a reviewable plan and preserves
the strict source release-policy and CLI safety release-gate with required
jsonschema before approval; former profile build/twine/clean-install checks are
provided by authenticated Core preflight rather than rebuilding a second payload.
A single pypi environment job retains
PyPI's existing release.yml/pypi Trusted Publisher identity. The job authenticates
API approval history for the human Release Authority and exact plan/run/attempt
comment. Missing environment protection cannot silently authorize writes. Repeat
full preparation after approval and compare plans. New dispatch is the retry UX;
Re-run failed jobs cannot reuse an earlier attempt's prepared plan.

## Byte publication and ordering

One globally serialized central workflow has explicit prepare → publish-pypi →
verify → finish job dependencies. Only publish-pypi has the pypi environment and
OIDC permission. Verify runs actual product binaries in a fresh read-only job,
without a publish credential, registry login file, OIDC or Homebrew secret.
Finish uses another fresh runner for controller-only generation/Homebrew/Latest;
it has no OIDC permission and requires the successful same-plan verify receipt.
Each job reauthenticates original preflight bytes/expiry and the same approved
run plan; only the publisher's environment requests human approval. Retire seven old
entry workflows to fail-only read-only workflow_call stubs in the same atomic PR.
This closes tag/manual/release-event bypass and avoids GITHUB_TOKEN event chaining
without adding a PAT. Reusable native producers stay untouched/read-only.

Tag creation is create-only and resolves annotated existing tags without moves;
reject an equivalent .0 alternate. Bind the GitHub Release body to the immutable
inventory. All public names are role-selected, unique/case-safe with identical Mini
notes deduplication. Preserve Desktop public mappings; exclude private bundled
Core and OCI archives. Existing remote objects must match actual downloads and
hash/size before no-op. GitHub uploads omit clobber, thus conflicting concurrent
writers fail. Final SHA256SUMS is one deterministic LF bytes object covering all
payloads plus inventory, excluding itself; publish only after GitHub/PyPI/GHCR
primary confirmation. OCI transport wraps the exact index as a named layout entry
and uses --all --preserve-digests; immutable version tags are never rewritten.

Public GitHub/PyPI URLs and GHCR index/all blob reads are checked independently.
Run downloaded Linux x86_64 Standalone and static Mini CLI/conformance with secrets
removed from their read-only job environment, using immutable source fixtures. Preflight binds
other native targets and Desktop build/bundled runtime metadata. Generate existing
winget/Scoop/conda adapters after verification; compare-and-swap Homebrew file with
its existing token and verify readback. External submissions and exhaustive GUI
remain manual_required/not_verified, never fabricated successes.

A required failed primary/canonical/generator/Homebrew prevents Latest. Before
promotion check receipt identity, current inventories and Homebrew, both GHCR
platforms, expiry, authority and critical variable. Guard current GitHub Latest
and each OCI alias using four-part numeric order, rejecting same-version wrong
bytes. Repair only missing aliases to the original index and promote GitHub Latest
last. Failure receipts override earlier stage success, including external action
failure; retain receipts/generated adapters in a 90-day Actions artifact.

## Review viewpoints and test plan

Requirements: all five issue contracts and human approved #1309 flow. Code: exact
byte reuse, explicit stage dependencies, no hidden dispatch/publish path, simple
stdlib helpers and existing generators. Security: API identity, untrusted archive
bounds, stale approval/attempt/expiry, least privileges, no secret stderr/artifact
exposure. Integration: atomic cutover and direct PyPI identity, 3/4 numeric version
compatibility. Operations: partial state, retry without clobber, Latest repair,
explicit account setup and critical stop. Algorithms are linear in total artifact
bytes and inventory size; checksum name ordering is O(n log n), dozens of assets.
Network reads use time/size bounds; no unbounded automatic retry loops.

Execute tests.test_release_publication plus all existing preflight producer/API/
collector and version/packaging/checksum/generator tests, traceability/closeout,
ruff check/format and validate_release_docs. Faults cover malformed approval,
wrong ref/controller/attempt, expired evidence, ZIP/path/hash tamper, partial
primary, historical 9/23 and missing Desktop sets, duplicate/case/CRLF, reverse
order/idempotent uploads, PyPI partial conflict, exact OCI transport, Homebrew CAS,
required states, alias partial repair/numeric downgrade and manual external state.
Forward-test the runbook read-only via skill-creator's separate-thread procedure.

Live OIDC/registry/Homebrew writes and protected environment settings are not run
by this implementation task. First real release requires separate approval. Real
preflight run 38822634032 is build/transport evidence, not public release evidence.
Independent implementation/integration reviews remain pending. No final self-approval.

## Rollback

Before publication, revert this integration PR as one unit if required; note that
restoring retired triggers restores old unsafe publication semantics and requires
human review. Do not revert a partial workflow subset as a cutover. Once published,
keep tags/public bytes fixed; human chooses a new correction version for source
changes. For critical findings, stop and seek explicit incident/withdrawal authority.
