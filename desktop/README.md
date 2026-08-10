# lifetxt Desktop (Tauri companion shell)

A native desktop window wrapping lifetxt's existing Web UI. This is a
**companion-process** shell, not a standalone app: it assumes lifetxt is
already installed on the machine, spawns `lifetxt serve` as a child
process on a freshly reserved local port, and points a native window at
it. It adds no life.txt logic of its own -- see
`.kiro/specs/desktop-app-companion-shell/` for the full requirements and
design.

A fully standalone bundle (embedding a Python runtime so end users need
nothing pre-installed) is an explicit follow-up candidate, not built here.

## Why Tauri, not Electron

Tauri uses the OS's native webview instead of bundling a full Chromium +
Node runtime, producing much smaller binaries -- a better fit for this
project's dependency-light design principle (see `.ai/project/RULES.md`).

## Prerequisites

- An existing `lifetxt` install reachable as `lifetxt`, `python -m lifetxt`,
  `python3 -m lifetxt`, or `py -m lifetxt` from a terminal (confirm with
  `lifetxt --version`).
- Rust (`rustc`/`cargo`). On Windows without Microsoft's MSVC Build Tools
  installed, use the GNU toolchain instead, since it can link with an
  existing MinGW-w64 `gcc` (for example from MSYS2) rather than requiring a
  multi-gigabyte Visual Studio install:

  ```sh
  rustup toolchain install stable-x86_64-pc-windows-gnu
  rustup default stable-x86_64-pc-windows-gnu
  ```

- On Windows, the Microsoft Edge WebView2 Runtime (pre-installed on
  Windows 10 22H2+ and Windows 11; Tauri's own installer bundles it for
  older systems, out of scope for this slice).
- No `npm install` is required. The only bundled frontend asset is one
  static loading/error page (`src-tauri/dist/index.html`); there is no
  JS build step.

## Build and run

```sh
cd desktop/src-tauri
cargo build            # or `cargo build --release`
cargo run               # or run the built target/debug/lifetxt_desktop(.exe) directly
```

The window shows a "Starting lifetxt…" placeholder, then navigates to the
real served Web UI once `GET /api/health` on the spawned server responds.
If lifetxt cannot be found, or the server does not become healthy within
15 seconds, the window shows a plain-language error explaining what was
tried instead of staying blank or frozen indefinitely.

Closing the window (or exiting the app) terminates the spawned server;
no orphaned process or bound port is left behind. This uses Tauri's
graceful-exit event, so a hard kill (Task Manager "End task", or `taskkill
/F`) bypasses it, same as it would for any other application -- Windows
does not tie a forcibly-killed process's children to its own lifetime by
default.

## What's out of scope here

Recorded as explicit follow-up candidates rather than gaps:

- A standalone, Python-bundled distributable
- macOS/Linux packaging verification (this project's own verification
  environment is Windows-only; the Tauri config is written to be
  portable but unverified elsewhere)
- System tray icon, native menu bar, auto-launch-on-login
- Auto-update, code signing, installer/bundling polish, a CI job that
  builds this app
