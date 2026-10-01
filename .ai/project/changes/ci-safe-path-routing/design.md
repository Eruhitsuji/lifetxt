# Design

One deterministic Python helper classifies the complete diff. Only `docs/**`
is trusted for lightweight routing. Python core, Web, and TUI are reported
separately for visibility but currently retain the full applicable checks.
Mixed surfaces, control files, workflow self-changes, packaging metadata,
unknown paths, empty comparisons, and manual dispatch all select `full`.

Both aggregate gates compare dependency results with the category. A docs-only
route requires heavy jobs to be `skipped`; all other routes require `success`.
Documentation and PR traceability remain mandatory. The optional-dependency
job uses a static name so a pre-matrix skip never exposes an unevaluated
`${{ matrix.* }}` expression.
