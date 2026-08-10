# Requirements Document

## Project Description (Input)
Issue #233: package lifetxt's existing Web UI as a native desktop
application using Tauri (chosen over Electron for its much smaller
binary size, given the project's dependency-light design principle).
Scoped with the repository owner via AskUserQuestion before
implementation as a companion-process first slice: the desktop shell
assumes lifetxt is already installed on the user's machine and spawns
`lifetxt serve` as a subprocess rather than embedding a Python
runtime. Lives in the same repository under a new `desktop/`
directory.

## Requirements

### Requirement 1: Locate an installed lifetxt
**Objective:** As a user launching the desktop app, I want it to find
my existing lifetxt install automatically, so I don't have to
configure anything.

#### Acceptance Criteria
1. WHEN the app starts, THE SYSTEM SHALL try, in order, the `lifetxt`
   console script on PATH, then `python -m lifetxt`, then
   `python3 -m lifetxt`, then `py -m lifetxt`, accepting the first
   candidate whose `--version` invocation succeeds.
2. IF no candidate succeeds, THE SYSTEM SHALL show an error state in
   the window naming the candidates it tried, rather than exiting
   silently or hanging.

### Requirement 2: Start the existing server unmodified
**Objective:** As a user, I want the desktop app to show the same
Web UI I already get from `lifetxt serve`, so behavior stays
consistent across every surface.

#### Acceptance Criteria
1. THE SYSTEM SHALL reserve a free local TCP port before spawning the
   server, and pass it via `--host 127.0.0.1 --port <port>`.
2. THE SYSTEM SHALL NOT pass a life.txt path argument, so the spawned
   server uses lifetxt's own existing config-driven default path
   resolution unchanged.
3. THE SYSTEM SHALL NOT modify, wrap, or reimplement any part of
   `lifetxt serve`, `webapp.py`, or the Web UI itself.

### Requirement 3: Show the UI once ready, fail visibly otherwise
**Objective:** As a user, I want a working window as soon as the
server is ready, and a clear message if something goes wrong, rather
than a blank or frozen window.

#### Acceptance Criteria
1. WHILE the server is starting, THE SYSTEM SHALL display a loading
   state in the window.
2. THE SYSTEM SHALL poll `GET /api/health` on the reserved port with a
   bounded total timeout.
3. WHEN `/api/health` responds successfully, THE SYSTEM SHALL navigate
   the window to the server's root URL.
4. IF the server does not become healthy within the timeout, THE
   SYSTEM SHALL show an error state instead of an indefinite loading
   state.

### Requirement 4: Clean process lifecycle
**Objective:** As a user, I want closing the app to fully stop the
background server, so no orphaned process or bound port survives the
app.

#### Acceptance Criteria
1. WHEN the app's window is closed or the app exits, THE SYSTEM SHALL
   terminate the spawned server child process.
2. THE SYSTEM SHALL NOT leave the reserved port bound after the app
   exits.

## Out of Scope (this slice)
- A standalone bundle embedding a Python runtime (no pre-existing
  lifetxt install required) -- recorded as a follow-up candidate.
- macOS/Linux packaging verification -- this session's environment is
  Windows-only; the Tauri config is written to be portable but is not
  verified on other platforms.
- System tray icon, native menu bar, auto-launch-on-login.
- Auto-update, code signing, installer/bundling polish, a CI job
  building the desktop app.
- Any change to lifetxt's own Python package, CLI, or Web UI.
