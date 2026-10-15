# Design

The first actual integration run 38814960857 used source/controller
dacfd3c322884df37789c1942e24db765ed5381c and version 1.0.4.1. Core, five
Standalone and two OCI targets succeeded. Both Mini jobs finished native static
build, tests, runtime smoke and Core conformance, then failed toolchain collection.
All Desktop jobs built native installers, then rejected a generated Cargo.toml
change. Collector correctly refused partial success; 16 component artifacts and
no final verified artifact existed. This does not satisfy full integration.

Mini calls cargo-zigbuild --version directly. Its clap root owns the version flag;
Cargo forwards zigbuild as a subcommand, where that flag is not accepted. Preserve
nonzero failure propagation and required toolchain evidence. Regression fixture
explicitly rejects the old invocation and accepts the upstream root command;
another fixture fails root version collection after smoke and asserts no report.

Desktop permits generated Cargo.toml in the changed-path set only with complete
semantic verification against git show <source_sha>:desktop/src-tauri/Cargo.toml.
Parse both TOMLs, normalize ONLY build-dependencies.tauri-build string/table and
absent/empty features, then compare type-sensitive deterministic JSON digests of
the whole parsed documents. String/table, comments/format/CRLF may differ without
changing meaning. Dependency versions, source/path, nonempty features and any
other semantic field must remain exact. Other paths including Cargo.lock are still
rejected. No restore/revert hides changes, and original source remains immutable.
Existing version, resource, plist, runtime and installer checks remain intact.

Upstream references verified against the versions installed by that run:
- https://github.com/rust-cross/cargo-zigbuild/blob/v0.23.4/src/bin/cargo-zigbuild.rs
- https://github.com/tauri-apps/tauri/blob/tauri-cli-v2.12.3/crates/tauri-cli/src/interface/rust/manifest.rs
- https://github.com/tauri-apps/tauri/blob/tauri-cli-v2.12.3/crates/tauri-utils/src/config.rs
Tauri rewrite normalizes tauri-build into a version/features table. No config
feature is enabled by this correction. Source dependency versions are unchanged.

Review: exact permitted semantic boundary, fail closed on malformed TOML or
unexpected dependency/feature changes, real git baseline vs mutable index,
unchanged native checks/least privilege, source/controller separation and retry.
Shared docs/traceability integrator Eruhitsuji; sequential after #1328. Revert
helpers to remove correction, with no public bytes/tag effects.

A controller fix requires NEW main dispatch after merge, not rerun of old run's
controller. Can reuse old immutable distribution source/version/main CI while
pinning new controller/run and rebuilding all 13 targets. No publication approval.
