# Stable MCP Read Artifact Smoke Evidence

This record closes the `mcp-client-read` evidence requirement in the stable
support matrix. It verifies the installed wheel's stdio read surface without an
editable checkout and without promoting MCP writes.

## Run

From the repository root, with the build dependency installed:

```console
python scripts/mcp_artifact_smoke.py
```

The script builds one wheel and one sdist, creates a disposable virtual
environment, installs the wheel with `--no-deps`, and invokes the installed
entry point as `python -m lifetxt mcp --read-only PATH`. Build/install
directories are removed on completion. Output contains only the artifact name,
SHA-256, interpreter/platform, and check names; no source paths, credentials, or
life.txt contents are emitted.

The build uses the already-installed project build backend (`--no-isolation`) so
the evidence run does not silently download arbitrary build dependencies.

## Contract checks

- `initialize` returns the documented `lifetxt-mcp` identity, version, and capabilities.
- `resources/list` and `resources/read` expose the installed source resource contract.
- The stable `list_items` read tool returns a result.
- An unsupported JSON-RPC method returns `-32601` without terminating stdio.
- A write tool called in `--read-only` mode returns a bounded read-only error.
- A subsequent `ping` succeeds, proving the server remains alive after errors.

## Evidence record

- Issue: #360
- Support-matrix surface: `mcp-client-read`
- Artifact identity: SHA-256 emitted by the script
- Environment: disposable virtual environment created by the script
- Write surface: not promoted; the smoke explicitly checks write rejection
- Redaction: no credentials, tokens, source paths, or user data are retained
