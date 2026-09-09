# Design: exact-revision Historical Temporal Thread

The shared historical input seam resolves every current input-manifest path
inside one Git repository, resolves the requested commit-ish, and reads only
the matching tree blobs. Missing paths are limitations; current and untracked
bytes are never substituted. Blob and aggregate sizes, Git execution time, and
ref syntax are bounded.

Parsed historical items are passed to the unchanged temporal-thread engine.
The additive historical object records requested and resolved revisions,
loaded/missing paths, completeness, and limitations. The feature is CLI-only;
current TUI, Web, and MCP behavior is unchanged.

The extension is read-only and additive. Rollback is a PR revert and requires
no data migration.
