# CI responsibilities

lifetxt separates continuous integration into three explicit responsibilities.
The split changes when checks run, not which supported environments or quality
boundaries exist.

## Pull requests: fast merge decision

Every pull request runs the full source-tree suite on Python 3.12, compilation,
the three example checks, basic smoke, the approved mypy boundary, release
documentation validation, and the traceability gate. `PR gate` aggregates those
results and fails unless every responsibility succeeds.

Pull-request runs share `pr-ci-<number>` concurrency with
`cancel-in-progress: true`. A newer push cancels obsolete work for the same PR.
Pushes to `main`, manual CI runs, and release runs use non-colliding groups and
are not cancelled by later runs.

CI classifies the complete changed-path set as `docs-only`, `python-core`,
`web`, `tui`, or fail-safe `full`. Only changes entirely below `docs/` use the
lightweight route: documentation validation and PR traceability still run,
while the Python suite and mypy are intentionally skipped. Mixed Web/TUI
changes, workflow and project-control files, packaging metadata, unknown
paths, empty comparisons, and manual dispatch all select `full`.

## Main: compatibility and regression detection

After merge, `main` runs Python 3.10, 3.11, and 3.12; no-Web tests;
ResourceWarning checks; Windows and macOS core smoke; coverage regression;
minimum and upper Web/TUI dependency compatibility; mypy; and release
documentation validation. `Main compatibility gate` fails closed over all of
these results.

For a docs-only merge, main skips compatibility runners and requires their
results to be `skipped`; documentation validation must still succeed. Every
other category continues requiring all compatibility results to be `success`,
so an accidental skip cannot make the aggregate gate green.

The automatic `CI failure on main` Issue observes only that stable aggregate
gate. A failing aggregate opens or updates the Issue; the next successful main
aggregate closes it. Internal job names can therefore evolve without changing
the monitoring contract.

## Releases: distribution artifacts

The tag/manual Release workflow owns publication evidence. It runs the
artifact-specific release profile, builds the release evidence artifacts,
validates metadata, installs the built wheel into a clean environment, and
smoke-tests the installed command. Source-tree full tests are not repeated in
the release profile; see [release-policy-gates.md](release-policy-gates.md).

The standalone binary, package-manifest, Docker, Homebrew, Conda, desktop
installer, and lifetxt-mini workflows remain independent. In particular,
lifetxt-mini keeps its existing path filters.
