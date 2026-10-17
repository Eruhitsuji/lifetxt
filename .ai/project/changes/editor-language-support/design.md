# Design

The existing Core remains the semantic authority. `lsp_document.py` owns memory
snapshots and code-point/UTF-16 mapping; `lsp_features.py` recognizes conservative
editing positions and delegates metadata/candidates; `lsp.py` owns bounded stdio
JSON-RPC and lifecycle. No mandatory Python dependency. Minimum Python 3.10.

The alternative optional pygls stack was not adopted: this intentionally small,
full-sync subset has no async background jobs or dynamic registration, and the
stdlib transport avoids adding a Python runtime/packaging dependency. Expanding
protocol capabilities should revisit this choice rather than grow an unrestricted
LSP implementation. Maintainer cost is offset by actual-client contract probes.
The VS Code consumer uses Microsoft's pinned optional languageclient, rather than
reimplementing the client protocol. Static mode lazily avoids importing it.

Plaintext Hover reuses `interactive.py`; completion pools derive from `model.py`
and `completion.py`, including additional reference/custom keys. No formatter,
auto-fix, command execution, network, telemetry, source write or automatic install.
Unknown spans remain zero-width. Joined logical-line columns map to physical text
before converting code points to UTF-16. BOM is removed only at the Core input
boundary and retained in the position map. Unsupported version uses Core F110.

Per-server open buffers are the entire workspace; root URIs are never interpreted
as paths. No disk paths/globs, symlink traversal, implicit Core config or unbounded
search. Custom ID settings require explicit `--id-key`, not config discovery.
Bounds: 32 documents, 256 KiB UTF-8 each, 200 results, 2 MiB frame, 8 KiB headers.
Parsing is synchronous O(input plus Core validation cost); stale versions are
ignored, in-flight synchronous work is not preempted. Clients debounce changes.
Core graph algorithms are unchanged. Physical OS/client gaps remain recorded.

Source origin/main; static branch #1369, LSP branch #1370 based on static, workspace
branch #1372 based on LSP. Each has a draft review PR; the final integration PR
into main preserves their ancestry without independently merging sub-PRs.
Shared registries are edited serially by Codex; Owner is integration authority.
Rollback is reverting the final PR and disabling LSP (static fallback available).
