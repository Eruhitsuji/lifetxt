# Bounded input coverage

Owner requested continuation after #1422; it is merged at main 78442528.
Operations / High / S / W-model. Branch fix/1423-verification-coverage;
final PR base main. Owner/Integrator/Merge Eruhitsuji, Implementer Codex;
independent implementation/integration review pending.

Reuse prepare_build's locked reconstruction. Compare manifests of regular files
in tools/, cpython/patches/, emsdk/patches/ and the named configs in
BUILD_INPUT_CONFIGS, in addition to the four modified inputs. Exact set comparison
rejects missing/extra files and content changes. Reject symlinked roots, parent
paths and members, as well as nonregular inputs. Generated tools Python caches
are documented exclusions and must be cleared before rebuilding. Empty directories
are irrelevant. Root config names absent on both sides do not add inputs; a
missing expected config or unexpected named config changes the manifest.

Newly generated source/object reports include staging_input_check (file count
and manifest SHA256). Existing retained source-build proofs, runtime locks and
source archives are unchanged. This remains bounded verification: installed SDK,
host tools and generated build outputs are not attested. Existing src, CPython,
dependency, library/object and WASM checks continue separately.

Archive/receipt mismatch remains an error. Report current Python and zlib
build/runtime versions and reproduction guidance without claiming compression is
the cause. Do not accept extracted-content equality or replace pins.

Viewpoints: scope clarity, source trust boundary, generated files versus inputs,
negative cases, compatibility, diagnostics and publication/independent authority.
Tests use real staging on synthetic locked archives and a separately fetched
fixed upstream cache. No unexecuted custom WASM/object/browser run is claimed.
Rollback: human-reviewed revert; no deploy or data migration.
