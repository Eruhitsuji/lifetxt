# Decisions

- Keep one `release` profile entry point for local, CI, and release workflows.
- Skip only the common source-tree phase when `profile == "release"`.
- Leave `_run_release_profile()` intact so artifact assurance cannot drift in this slice.
- Remove Web/dev extras from the release profile's primary environment; install only core plus explicit release tooling.
- Defer workflow event routing and gate aggregation to #1010.
