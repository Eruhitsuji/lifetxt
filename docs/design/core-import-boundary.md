# Platform-neutral Core import boundary

`import lifetxt` is the backward-compatible package surface for CLI, Web, and
Remote integrations. It now imports only model, parser, and serializer basics.
Embedding consumers should use `lifetxt.core` for authoritative parser,
conversion, quick-input, and priority-matrix operations.

The CLI entrypoint calls `lifetxt.bootstrap_legacy_surfaces()` before dispatch.
This preserves the existing integration compatibility behavior without putting
those side effects on the embedding import path. The refactor is
platform-neutral and contains no Cloudflare-specific conditionals.

`tests.test_core_import_boundary` records comparable cold import/module-graph
evidence for package-root and Core imports. These measurements are evidence
for the boundary decision, not a public performance guarantee.
