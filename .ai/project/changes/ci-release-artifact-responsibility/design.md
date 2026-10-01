# Design

Lifecycle phase: implementation and developer verification of the first #1008
decomposition slice. Review viewpoints are release safety, regression coverage,
compatibility, and operability; test viewpoints are command selection, retained
artifact gates, and unchanged non-release profiles.

`run_for_interpreter()` keeps one disposable environment and installation
boundary. For the `release` profile it now proceeds directly from installing
the core package and release tooling to `_run_release_profile()`. Every other
profile retains compile/tests/examples/smoke behavior. The release profile no
longer requests Web dependencies because none of its artifact-specific steps
need them.

`_run_release_profile()` is unchanged: it still executes the release policy,
safety gate, sdist and wheel build, Twine validation, a second wheel-only
environment, both installed entry points, and an installed-wheel example check.
This preserves publication assurance while removing only checks already owned
by source-tree CI.
