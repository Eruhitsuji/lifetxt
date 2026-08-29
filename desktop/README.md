# lifetxt Desktop (Tauri companion shell)

A native desktop window wrapping lifetxt's existing Web UI. It is a
**companion-process** shell: it spawns `lifetxt serve` as a child process
on a freshly reserved local port and points a native window at it. It adds
no life.txt logic of its own -- see `.kiro/specs/desktop-app-companion-shell/`
for the original (#233) requirements and design.

**Standalone installers bundle a real lifetxt runtime** (#574): the same
PyInstaller artifact `standalone-binaries.yml` builds for #570 is packaged
directly into the installer under `resources/bin/`, so an installed lifetxt
Desktop needs no separate Python/lifetxt install. A source build via
`cargo build`/`cargo run` (below) still needs an existing `lifetxt` on
PATH, since it has nothing bundled -- see
[Build and run (source, no bundling)](#build-and-run-source-no-bundling)
vs. [Build a real installer](#build-a-real-installer-bundled-runtime).

Backend resolution order: a bundled runtime under this app's own resource
directory first, falling back to `lifetxt`, `python -m lifetxt`,
`python3 -m lifetxt`, `py -m lifetxt` on PATH -- so a source build behaves
exactly as it did before #574.

## Why Tauri, not Electron

Tauri uses the OS's native webview instead of bundling a full Chromium +
Node runtime, producing much smaller binaries -- a better fit for this
project's dependency-light design principle (see `.ai/project/RULES.md`).

## Prerequisites

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
  older systems).
- No `npm install` is required. The only bundled frontend asset is one
  static loading/error page (`src-tauri/dist/index.html`); there is no
  JS build step.
- For a real installer build only: `lifetxt[web,tui]` and `pyinstaller`
  installed (to build the bundled runtime) and `tauri-cli`
  (`cargo install tauri-cli --version "^2" --locked`).

## Build and run (source, no bundling)

```sh
cd desktop/src-tauri
cargo build            # or `cargo build --release`
cargo run               # or run the built target/debug/lifetxt_desktop(.exe) directly
```

With nothing in `resources/bin/`, this falls straight through to
PATH-based discovery, matching this crate's original (#233) behavior --
an existing `lifetxt` install reachable from a terminal
(`lifetxt --version`) is required.

## Build a real installer (bundled runtime)

```sh
# From the repository root:
python -m pip install ".[web,tui]" pyinstaller
python packaging/tauri-desktop/prepare_bundled_runtime.py
python scripts/set_tauri_desktop_version.py --version 1.0.0   # ties the installer's own version to a release

cargo install tauri-cli --version "^2" --locked
cd desktop/src-tauri
cargo tauri build
```

Installers land under `desktop/src-tauri/target/release/bundle/` (MSI/NSIS
on Windows, dmg/app on macOS, deb/AppImage on Linux, per Tauri's own
per-platform bundle target selection). `.github/workflows/desktop-installers.yml`
runs this same sequence natively per platform on every tagged release.

## Runtime behavior (both build modes)

The window shows a "Starting lifetxt…" placeholder, then navigates to the
real served Web UI once `GET /api/health` on the spawned server responds.
If no usable runtime is found (bundled or on PATH), or the server does not
become healthy within 15 seconds, the window shows a plain-language error
explaining what was tried instead of staying blank or frozen indefinitely.

Closing the window (or exiting the app) terminates the spawned server;
no orphaned process or bound port is left behind. This uses Tauri's
graceful-exit event, so a hard kill (Task Manager "End task", or `taskkill
/F`) bypasses it, same as it would for any other application -- Windows
does not tie a forcibly-killed process's children to its own lifetime by
default.

## Verification performed for the bundled-runtime path (#574)

On this project's own Windows sandbox: built the #570 standalone binary,
staged it at `resources/bin/lifetxt.exe`, confirmed (via the debug build's
resolved resource directory) that a source `cargo run` correctly finds
*nothing* there and falls through to PATH -- the pre-#574 behavior is
unchanged -- then copied the binary to that same resolved directory to
simulate what Tauri's bundler places in a real installed app, launched the
app, and confirmed via the real process tree that
`lifetxt_desktop.exe` spawned exactly
`...\resources\bin\lifetxt.exe serve --host 127.0.0.1 --port <port>` as its
child, not any PATH-based interpreter.

A real `cargo tauri build` producing an actual installer was **not**
completed in this sandbox: installing `tauri-cli` failed here on a
pre-existing, environment-specific toolchain conflict (this sandbox has
multiple competing `gcc`/`dlltool` installs -- FPC, MSYS2, Anaconda -- and
`ring`/`parking_lot_core`'s build scripts picked up the wrong one; the
existing `cargo build`/`cargo run` path is unaffected since it does not
pull in those crates). This is recorded as an explicit, unverified gap
rather than claimed complete -- the GitHub Actions workflow runs on clean,
single-toolchain runners and is expected to be unaffected, but that has not
been confirmed by an actual CI run yet.

## What's out of scope here

Recorded as explicit follow-up candidates rather than gaps:

- Code signing / notarization (unsigned installers trigger Windows
  SmartScreen and macOS Gatekeeper warnings, matching #570's own recorded
  limitation for the underlying binaries).
- Auto-update.
- System tray icon, native menu bar, auto-launch-on-login.
- A first-run file picker / "create or open life.txt" UI in the Tauri
  shell itself -- the served Web UI already owns that flow; this shell
  does not duplicate it.
- Reducing the desktop installer's own version away from a 1:1 tie to the
  bundled lifetxt version (see `scripts/set_tauri_desktop_version.py`).
