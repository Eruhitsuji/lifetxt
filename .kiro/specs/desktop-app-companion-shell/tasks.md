# Implementation Plan

- [x] 1. Verify local prerequisites (Rust toolchain, WebView2 runtime) and record what was needed
  - _Requirements: (environment, no direct requirement mapping)_
- [x] 2. Scaffold desktop/src-tauri (Cargo.toml, build.rs, tauri.conf.json, placeholder icons, static loading/error page)
  - _Requirements: 3.1_
- [x] 3. Implement the backend locator (lifetxt / python -m lifetxt / python3 -m lifetxt / py -m lifetxt fallback chain)
  - _Requirements: 1.1, 1.2_
- [x] 4. Implement port reservation and spawn `lifetxt serve --host 127.0.0.1 --port <port>` with no path argument
  - _Requirements: 2.1, 2.2, 2.3_
- [x] 5. Implement the health-poll loop and window navigation on success / error state on timeout
  - _Requirements: 3.2, 3.3, 3.4_
- [x] 6. Implement process lifecycle: kill the spawned child on app exit / window close
  - _Requirements: 4.1, 4.2_
- [x] 7. Build and live-verify: normal launch, lifetxt-not-found error state, clean process teardown on close
  - _Requirements: 1.2, 3.4, 4.1, 4.2_
- [x] 8. Write desktop/README.md documenting prerequisites and build/run steps
  - _Requirements: (documentation, no direct requirement mapping)_
