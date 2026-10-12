# Design

Only release metadata and notes change. Core/runtime/PyPI use 1.0.4.1; Mini Cargo and lock use 1.0.4+1, following merged #1303. Desktop metadata is generated at tagged build time by the existing workflow. One version fixture is updated without weakening the core-only import test.

Existing v1.0.4 artifacts are retained. A new immutable tag is created only after this PR merges, the merge commit passes release checks and the Release Authority approves. Per-channel publication, checksums, native downloads and downstream package processing are retained in #1298/#911.

No credentials, permissions, dependencies, public data formats or new features change. Rollback before publication is a PR revert; an already-public tag is not moved.
