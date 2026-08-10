# Design Document

## Overview
A Rust/Tauri v2 binary crate at `desktop/src-tauri/`. On startup it
locates an installed `lifetxt`, reserves a free TCP port, spawns
`lifetxt serve --host 127.0.0.1 --port <port>` as a child process,
shows a static loading page while polling `/api/health`, then
navigates the main window to the server's root URL. The child process
is killed on app exit. No JS frontend framework or `npm install` step
is required -- the only bundled asset is one static HTML loading/error
page, declared as Tauri's `frontendDist`.

## Boundary Commitments
### This Spec Owns
- `desktop/src-tauri/` (new): `Cargo.toml`, `build.rs`,
  `tauri.conf.json`, `src/main.rs`, `dist/index.html`.
- `desktop/README.md` (new): build/run instructions and the
  prerequisites this session discovered (Rust toolchain, WebView2).

### Out of Boundary
- Every existing Python file (`lifetxt/`, `tests/`) -- unchanged.
  `lifetxt serve` is spawned exactly as an end user would run it from
  a terminal.
- Installer bundling, icons beyond a minimal placeholder, code
  signing, auto-update, CI.

### Allowed Dependencies
- `tauri` (v2, default features) and `tauri-build` from crates.io.
- Rust standard library (`std::process`, `std::net::TcpListener`) for
  process spawning and port reservation.
- An HTTP client for the health poll: `ureq` (small, blocking,
  dependency-light -- avoids pulling in `tokio` purely for a handful
  of polling requests when Tauri's own async runtime is not otherwise
  needed by this slice's logic).

## Backend Locator
Try, in order: `lifetxt --version`, `python -m lifetxt --version`,
`python3 -m lifetxt --version`, `py -m lifetxt --version`. The first
whose child process exits successfully sets the command prefix used
for the actual `serve` invocation. This mirrors the fallback order
already established for the CLI update-check tooling's own
interpreter-invocation patterns in this project, applied here to
locating the package itself rather than an interpreter.

Each candidate's program name is resolved to an absolute path via
`resolve_on_path()`, which searches only the directories listed in the
`PATH` environment variable, before that candidate is ever invoked
(including the `--version` probe). This is deliberately narrower than
`Command::new`'s own unqualified-name lookup, which on Windows also
searches the directory the app was loaded from and the current working
directory *before* PATH -- trusting either of those for the actual
`lifetxt serve` launch would let a planted `python.exe`/`lifetxt.exe`
sitting next to a portable build (for example in a Downloads folder)
execute silently in place of the real interpreter (CWE-426/427,
found during this task's own `/security-review` pass). The resolved
absolute path, not the bare candidate name, is what `spawn_server()`
reuses for the real invocation.

## Port Reservation
Bind a `TcpListener` to `127.0.0.1:0`, read back the OS-assigned port
from `local_addr()`, then drop the listener before spawning the
server with that exact port via `--port`. This is the standard
reserve-then-release pattern; the small race window between drop and
the child binding it is accepted for this first slice (matches how
ephemeral-port reservation is conventionally done -- there is no
portable way to hand a pre-bound listening socket to an arbitrary
child process across platforms without additional OS-specific
plumbing, which is out of scope here).

## Health Poll and Navigation
Poll `GET http://127.0.0.1:<port>/api/health` every 200ms for up to 15
seconds total. On the first successful (2xx) response, call the
window's navigate/eval to redirect to `http://127.0.0.1:<port>/`. On
timeout, or if the backend locator step failed, replace the loading
page's content with a plain-language error message (which candidates
were tried, and to install lifetxt or check `lifetxt serve` runs
correctly from a terminal).

## Process Lifecycle
The spawned `std::process::Child` handle is stored in Tauri's managed
state. A `RunEvent::ExitRequested` (and window-close) handler kills it
before allowing the app to exit, so no orphaned server process or
bound port survives the app.

## File Structure Plan
### New Files
- `desktop/src-tauri/Cargo.toml`
- `desktop/src-tauri/build.rs`
- `desktop/src-tauri/tauri.conf.json`
- `desktop/src-tauri/src/main.rs`
- `desktop/src-tauri/dist/index.html` -- static loading/error page
- `desktop/src-tauri/icons/icon.ico`, `icon.png` -- minimal placeholder
  icon set (Tauri requires at least one icon reference to build)
- `desktop/README.md`

## Requirements Traceability
| Requirement | Design Element |
| --- | --- |
| 1.1-1.2 | backend locator function tried in `main.rs` setup, error state on total failure |
| 2.1-2.3 | port reservation + `Command::new(...).args(["serve", "--host", "127.0.0.1", "--port", &port.to_string()])`, no path argument, no modification to any Python file |
| 3.1-3.4 | static loading page as initial window content; polling loop; navigate-on-success; error-state-on-timeout |
| 4.1-4.2 | managed `Child` handle; kill on `ExitRequested`/window-close |

## Testing Strategy
- `cargo build` in `desktop/src-tauri/` on this session's Windows
  environment (GNU toolchain, since MSVC Build Tools are not
  installed here) -- confirms the crate compiles.
- Live run (`cargo run` or the built `.exe`) against this session's
  own installed lifetxt: confirms the window opens, shows the real
  served Web UI, and that closing the window terminates the spawned
  `lifetxt serve` process (no orphaned process/port left behind,
  checked via a process/port listing after close).
- Live run with `lifetxt` deliberately hidden from PATH/candidates
  (or an invalid override) to confirm the error state renders instead
  of hanging.
- No Python-side tests are needed or added -- this slice adds no
  Python code and does not modify any existing Python behavior.
