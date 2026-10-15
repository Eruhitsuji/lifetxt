# Release preflight proof contract

This is the offline evidence layer for #1315, under #1310 and the approved
#1309 design. It does not build or publish packages, check GitHub approval,
validate CI signatures, or authorize release operations. Existing publication
workflows are unchanged. Component workflows and the controller will be added
in #1316–#1321; canonical public checksums belong to #1305.

## Candidate identity

Run from the repository root, using the trusted controller checkout:

```sh
python scripts/release_preflight_proof.py candidate \
  --repository Eruhitsuji/lifetxt --version 1.0.4.2 \
  --source-sha <40-lowercase-hex> --controller-sha <40-lowercase-hex> \
  --run-id <positive-integer> --run-attempt 1 --output candidate.json
```

The source SHA identifies the distribution code. The controller SHA identifies
the reviewed workflow/policy code. These are syntactic checks, not proof that
either SHA is trusted or has passed main CI. The future controller must verify
repository, branch, merged version PR, CI, actual runner checkout and approvals
against GitHub's trusted API context, never against an untrusted report alone.

The helper reuses `lifetxt.versioning`: `1.0.4` and `1.0.4.0` produce the same
canonical identity; `1.0.4.2` keeps its explicit correction number and maps to
`1.0.4+2` only for Cargo/Tauri metadata. Number selection does not grant approval.
No version is inferred or incremented on failure.

Schema 1 fixes all 13 targets in `TARGETS` in the helper: Core, five Standalone,
three Desktop, two Mini and two OCI targets. A candidate cannot remove a target
to hide a failure. Every component binds to the candidate digest, source and
controller SHA, run ID and attempt. A rebuilt candidate at a new attempt needs
fresh evidence for the entire target set. Publication retries that reuse the
original bytes belong to the later controller, not this evidence creator.

## Component report

The build workflow uploads **only its payload directory** and obtains the
Actions artifact ID, name and archive SHA-256 from the upload action. It then
creates a component spec outside that directory. Example Core spec:

```json
{
  "target": "core-any",
  "artifact": {"id": 123, "name": "core-payload", "sha256": "<64-lowercase-hex>"},
  "observed_version": "1.0.4.2",
  "toolchain": {"python": "3.12.3", "build": "1.3.0", "runner": "ubuntu-24.04"},
  "checks": {"metadata": "passed", "clean-install": "passed", "cli": "passed"},
  "oci_digest": null,
  "files": [
    {"path": "lifetxt-1.0.4.2-py3-none-any.whl", "role": "wheel"},
    {"path": "lifetxt-1.0.4.2.tar.gz", "role": "sdist"},
    {"path": "sbom.cdx.json", "role": "sbom"},
    {"path": "provenance.json", "role": "provenance"}
  ]
}
```

```sh
python scripts/release_preflight_proof.py component \
  --candidate candidate.json --spec core-spec.json \
  --root payloads/core-any --output core-proof.json
```

All payload files must be listed; no unlisted payloads are accepted. Payload
paths are normalized relative POSIX paths with portable ASCII components.
Traversal, absolute paths, backslashes, case aliases and symlinks are rejected.
CI must use private, quiescent directories; the helper is not a sandbox against
concurrent filesystem mutation. Each file must be nonempty. Role names declare
purpose; the helper does not infer contents from a filename or inspect binaries.
Actual semantic validation belongs to each producer's smoke tests.

| Family | Required roles | Required passed checks |
| --- | --- | --- |
| Core | wheel, sdist, sbom, provenance | metadata, clean-install, cli |
| Standalone | binary, checksum | version, check, init-doctor, unicode-path, timezone |
| Desktop | installer, bundled-core | version, bundle, bundled-core |
| Mini | binary, checksum, build-info, notes | version, native, static, conformance, cli |
| OCI | oci-layout | version, native, cli, web, non-root |

Roles are unique except `installer`, which may appear for multiple Desktop
formats. Desktop's `bundled-core` is a private proof payload, not an extra public
Standalone asset. Producers must deliberately select packaging/evidence files
rather than uploading incidental files from their working directory. OCI has
a required `sha256:<hex>` image/index digest and an `oci-layout` archive payload;
OCI producers must validate that digest against the layout contents and later
provide the final multiarch index. This helper only validates its syntax.

Checks and toolchain versions are producer assertions. Their presence alone
cannot prove tests ran, an artifact came from Actions, or an OCI digest is
correct. The trusted controller must reconcile artifact IDs/names/digests with
Actions metadata and the successful producer jobs. Archive SHA-256 is distinct
from the individual extracted payload SHA-256 values this helper recomputes.
All component references must identify distinct artifact IDs. Proof JSON is
uploaded separately after the payload reference exists, avoiding self-reference.

## Aggregate and rejection

Download each selected payload into `payloads/<target>/`, preserving the target
namespace. Never merge files from all targets into a flat directory.

```sh
python scripts/release_preflight_proof.py aggregate \
  --candidate candidate.json --root payloads \
  --component core-proof.json --component <each-of-the-other-12-proofs.json> \
  --output preflight-proof.json
```

The helper requires exactly the full target set, validates every report and
rehashes the actual payloads. It rejects missing/duplicate targets or artifact
IDs, unexpected roles, failed/skipped/missing checks, inconsistent identity,
changed bytes, unknown fields, duplicate JSON keys and malformed evidence.
The resulting bundle has `status: preflight_verified` and
`publication_authorized: false`. Its digest is SHA-256 of sorted-key compact
UTF-8 JSON (no trailing newline), excluding only the top-level `digest` field.
Nested digests are retained. The same rule seals candidates and components.
This is content integrity, not an authentication signature.

Each CLI command requires a new output path and exits nonzero on rejection.
Controllers must check exit status, never consume an old output from a failed
attempt, and must not run the helper from mutable/untrusted source code with
publish privileges. Output directories and input files are caller-owned.
No tag, API call, approval, checksum finalization, registry write or Latest
update occurs. Proof retention, expiry, trusted transport and human approval
remain mandatory integration work, not implicit promises of this offline layer.

An explicit correction version follows the normal PR/CI/preflight/approval
flow. Before tag/publication, a corrected SHA may reuse the proposed number.
After tag creation that number is reserved for its SHA. Partial publication may
retry only identical source/bytes; source defects require a new correction
number chosen/approved by the human. Lost artifacts or conflicting bytes stop
recovery. Existing public tags and bytes must never be replaced.

## Core producer (#1316)

`release-preflight-core.yml` is a read-only `workflow_call` producer. It has no
push, release or manual publication trigger, no environment, no publish token
and no stored checkout credentials. The future controller calls it from the
same repository/controller revision, passing the sealed `candidate_json` string.
There is no user-facing dispatch command yet; #1321 owns end-to-end integration.

The job first checks repository/run/attempt and the controller checkout, then
checks out only the validated source SHA into a separate directory. The Core
helper also rejects tracked edits and checks the source's actual declared
version. Both source and controller identity are rechecked after build/smoke.
These are local/run identity checks: the parent still must verify trusted main
CI, version PR and approvals against GitHub, as described above.

The helper runs the existing release-policy and safety release gates, reuses
`release_evidence.generate` for a single wheel/sdist build, verifies archive
Name/Version, SBOM identity and provenance/source/run/file hashes, and runs twine.
It installs **both** the exact wheel and the exact sdist into separate fresh
virtual environments. From a temporary directory outside source, it checks that
imports resolve inside that venv and tests module/console version, help and the
minimal example. PYTHONPATH/PYTHONHOME are removed from smoke subprocesses.
The sdist install builds its own installation wheel; that smoke output is never
substituted for a preflight payload file. It does not run full source unit tests
again. Build backend dependencies may require package-index access.

The four public-payload roles are wheel/sdist/SBOM/provenance. The existing
builder's intermediate SHA256SUMS stays out of the uploaded payload: it cannot
compete with #1305's later canonical manifest. Complete file hashes remain in
the build report/proof, and build/gate diagnostics are in the Actions job log.
A report is emitted only after all gates/smokes pass. A failed job may leave
local files, but cannot reach the upload step or emit a successful component.

The immutable payload is uploaded first. Its `artifact-id`, `artifact-digest`
and deterministic `core-payload-<run>-<attempt>` name are then bound to the build
report after rechecking archive metadata, provenance and unchanged bytes.
The resulting `core-component.json` is uploaded separately together with
candidate/build report as `core-proof-<run>-<attempt>`. Reusable outputs expose
payload ID/name/digest and component artifact ID/digest. Both artifacts request
30-day retention (subject to repository limits). Expired evidence is a stop,
not permission to rebuild under an old approval. No public release/tag/registry
or Latest is changed by this producer. Actual Actions transport and complete
13-target orchestration remain integration acceptance in #1321.

For offline/local validation, standard pip settings such as `PIP_FIND_LINKS`
and `PIP_NO_INDEX` can point smoke installs at a pre-fetched build-dependency
wheelhouse. This changes dependency transport, not payload bytes or the clean
venv/import checks.

## Standalone producer (#1317)

`release-preflight-standalone.yml` is a read-only `workflow_call` matrix for
Windows x86_64, Linux x86_64/arm64 and macOS arm64/x86_64. It preserves the
existing native runners and PyInstaller spec; the old publication workflow is
unchanged. Pass the same sealed `candidate_json` used by the Core producer.
The controller/source/run/version checks reuse the Core helper. The producer
also checks the real OS, normalized host architecture and 64-bit interpreter
before building, and rejects cross-target execution.

The source's web/tui extras and PyInstaller are installed for the build. The
frozen executable, not `python -m lifetxt`, runs outside source. Version must
match the candidate exactly. `check`, `init --yes`, `doctor`, workspace checks,
paths containing spaces/Japanese characters and Asia/Tokyo `check`/`today`
smoke are retained. HOME and config/data/cache directories point at temporary
smoke-only locations; PYTHONHOME/PYTHONPATH are removed. Failed builds/smokes
produce no successful report or upload. Full source unit tests are not rerun.

Each payload contains only its platform-qualified binary and LF-only `.sha256`
file, preserving the existing public filenames. The sealed report records the
source/controller/candidate/run/target, toolchain versions, successful checks,
and both file hashes/sizes. After payload upload, the helper verifies the exact
two-file inventory, checksum text and unchanged report/file digests before
emitting a schema-1 Standalone component. A fresh checksum alone cannot certify
a binary changed after smoke. Neither the component nor checksum authorizes
publication or writes the future canonical SHA256SUMS.

Payload artifacts use `<target>-payload-<run>-<attempt>`, and separate proof
artifacts use `<target>-proof-<run>-<attempt>`. Each proof archive contains
candidate/build report/component; the component references its payload archive
ID/name/digest. Both request 30-day retention. Matrix outputs are deliberately
not exposed as a five-target inventory: GitHub matrix outputs can select one
completed job's values. #1321 must collect all five target-named proofs, verify
their trusted API/run metadata and payload IDs/digests, and reject missing or
duplicate targets. Keep downloaded payloads under their target namespaces.
On Unix, restore execute permission on a downloaded binary before running a
new smoke; artifact transport may normalize file modes. This does not change
the file bytes/digest and is not a rebuild or payload replacement.

The helper's `build` and `component` CLI arguments follow the Core producer,
with an explicit `--target standalone-linux-x86_64` (or one of the other four
supported targets). The upload reference is supplied only to `component`.
See the reusable workflow for exact commands. There is no standalone public
dispatch action. Local Linux smoke does not claim Windows/macOS/ARM native
coverage; those and actual Actions artifact transport remain #1321 acceptance.

## Desktop producer (#1318)

`release-preflight-desktop.yml` is a read-only `workflow_call` matrix for Windows
x86_64, macOS arm64 and Linux x86_64. Pass the same sealed `candidate_json`.
It reuses Core context/source checks and Standalone native-host and frozen
smoke checks. It has no publish event, environment or secret. The old Desktop
workflow and packaging scripts are unchanged.

The helper's `stage` command creates a fresh local shared Git checkout at the
exact source SHA. Only this generated checkout is used for the existing runtime
builder and version setter. The original source/controller remain tracked-clean
and are checked before/after the work. The generated bundled Core is actually
executed outside source with the full Standalone smoke set. The version setter
then applies the existing three/four-part transport mapping and precise Apple
release plist. Configuration version, plist identity and the resource mapping
`resources/bin/* -> bin/` are checked. Unexpected tracked edits (including a
Cargo.lock change) or extra runtime resources fail closed. A successful stage
report certifies the Core staging only, not an installer or a release.

`bundle` revalidates stage identity and runtime hash, invokes `cargo tauri build`
with a bounded 30-minute timeout, then rechecks the generated checkout/runtime.
It requires native installer outputs, validates nonempty files and format
signatures, and rejects duplicate public basenames. This is not deep validation
or installation of every MSI/NSIS/DMG/deb/AppImage/rpm format. Rust and tauri-cli
versions are recorded alongside Python/PyInstaller. GUI install/upgrade/uninstall
and extraction of embedded Core from every format remain explicitly not_verified.
The later publication verification must still inspect actual downloaded bytes.

Desktop public names can contain spaces. Keep them unchanged: internal payloads
use safe aliases such as `installer-001.deb`. The sealed bundle report's
`installers` records each alias `path`, original `public_name`, and `format`.
The separate proof artifact contains candidate, stage report, bundle report and
common component. Before publishing, #1305/#1311/#1321 must verify that proof
archive's trusted Actions digest and bind each mapping to the matching component
file hash; then use the original public_name, never the internal alias. Public
names reject separators/control characters and duplicates. They are metadata,
not paths to concatenate into a local directory or interpolate into a shell.

The payload's single `bundled-core` (or `.exe`) role is private evidence. It must
not be uploaded as an extra release asset or added to the public canonical
inventory. Only installer-role files map to public Desktop assets. This preserves
schema 1 and public filenames without adding a new canonical checksum writer.
After payload upload, `component` validates the installer mapping/signatures,
runtime hash and exact file hashes against the report before emitting proof.

Artifacts follow `<target>-payload-<run>-<attempt>` and
`<target>-proof-<run>-<attempt>` with 30-day retention requested; the parent must
collect all three targets rather than treat a matrix output as an inventory.
See the reusable workflow for the `stage -> bundle -> upload -> component`
commands. Native installer builds/Actions transport require the appropriate
Rust/WebKit/OS runner; local runtime staging is not proof they already ran.

## Mini producer (#1319)

`release-preflight-mini.yml` is a read-only `workflow_call` for native Linux
x86_64 and AArch64, using the existing musl Rust targets and Zig 0.13.0 setup.
Pass the same sealed `candidate_json`. It reuses actual Core context/source
checks, native host validation and the common proof schema. The existing Mini
publication workflow/crate/version/conformance scripts are unchanged.

The helper first checks existing Core/Cargo/lock/tag version consistency, runs
`cargo test --locked`, then `cargo zigbuild --locked --release` with the selected
musl target. Test/build target directories are fresh temporary directories;
old workspace target caches are not mistaken for new outputs. The resulting
binary must be ELF64 little-endian for the expected machine (x86_64=62,
AArch64=183), with bounded program headers, a load segment, no PT_INTERP and
no DT_NEEDED/filter/auxiliary library dependency. Static PIE with a dynamic
metadata table but no loader/dependencies is allowed. This replaces the old
locale-dependent ldd-message classification; it is not a binary safety sandbox.

Before checks are marked passed, the actual native Mini runs version/help/check/
today and the existing binary-version and Core/Mini conformance scripts. The
explicit test date and strict-subset Mini Runtime Profile identity are retained.
The existing conformance script's `python` alias must resolve to the current
supported interpreter. Failed/skip/missing checks cannot emit success proof.

The payload preserves `lifetxt-mini-<tag>-linux-<arch>`, `.sha256`, `.build-info`
and `RELEASE-NOTES.md`. Checksums and notes are LF-only. Build info records
rustc -Vv; the report adds Cargo/cargo-zigbuild/Zig/Python versions, static ELF
evidence and file hashes/sizes. Notes are byte-identical on both arches and
retain the strict-subset boundary: the later public canonical inventory must
deduplicate RELEASE-NOTES.md only if hashes match, and stop on a conflict.
There is no per-producer canonical SHA256SUMS writer.

Payload/proof artifacts use the same target/run/attempt naming and 30-day
retention request as the other producers. After upload, `component` rechecks
ELF/arch, exact inventory, checksum/notes and unchanged report hashes. The parent
must collect both target proofs and verify trusted Actions IDs/digests; matrix
outputs are not an inventory. See the workflow for build/upload/component CLI.
Without Cargo/Zig, local ELF/fixture tests do not certify a real Mini build,
native AArch64 execution, conformance success or Actions artifact transport.
Those remain required integration evidence in #1321 before publication enablement.
