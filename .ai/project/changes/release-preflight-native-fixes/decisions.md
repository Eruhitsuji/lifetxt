# Decisions

- Parent #1321 integration defect; user approved both corrections, tests and PR.
- Bug/High/S, complexity 6, cap-distribution-channels reuse, dedicated branch.
- Direct executable root version invocation follows actual cargo-zigbuild0.23.4 CLI.
- Allow only semantically identical generated tauri-build dependency representation;
  never blanket-whitelist Cargo.toml, ignore changes or restore them after build.
- Compare complete TOML to immutable source SHA blob; index/worktree is not baseline.
- Preserve source files, workflows, permissions, toolchain versions and proof schema.
- Real-git fixtures exercise the changed-file gate. Native Rust/Tauri toolchains are
  unavailable locally; new full Actions run remains required after merge (#1321).
- Do not automatically close parent #1321/#1310 from this correction PR.
- Independent implementation/integration reviews and human merge approval pending.
