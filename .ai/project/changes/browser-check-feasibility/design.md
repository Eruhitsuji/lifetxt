# Design

#1362 adds source-based candidates and actual-runtime version observations in
notices/components.json. The builder validates all shipped runtime hashes and
notice hashes/references before creating output; it does not infer legal
completeness. Inventory probing is Node-only, separate from browser acceptance.

#1360 adds a Python Playwright probe with ephemeral real Chromium contexts and
a loopback HTTP server. Actual rendering/Worker/CSP tests remain separate from
Node/fake-DOM evidence. Notice snapshots are copied and manifest-hashed; their
inventory is explicitly incomplete. See BROWSER_ACCEPTANCE.md for current
coverage, mobile-emulation limits and outstanding product gates. The original
design below describes the #1356 baseline.

Reuse cap-official-website and the #1055 Core boundary. An isolated contrib
builder packages an explicit corpus-observed closure of unmodified Python
modules, not the CLI bootstrap. The adapter calls parse_text and the existing
diagnostic serializer. A pinned, self-hosted Pyodide module Worker owns the
in-memory Python runtime. Input is an FFI argument, never executable code;
results are textContent. Load only after Check; cancel/timeout terminates and
clears the runtime and input. No public site or workflow is changed.

Native/Node WASM, browser-worker code under a Node shim, CLI subprocess and
fake DOM lifecycle are separate probes. They do not stand in for actual browser
rendering, network/storage, accessibility or mobile measurements. The recommendation
is conditional GO for further validation, not production acceptance. #1358 tracks
adoption gates and scoping; #1356 retains the unmet browser experiment criterion.
