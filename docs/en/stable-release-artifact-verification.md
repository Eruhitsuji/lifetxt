# Stable Release Artifact Verification

This document defines the mechanical artifact check for #326. It proves that
the source tree can produce a wheel and sdist, that a fresh virtual environment
can install the wheel, and that both public entry points run outside the source
checkout.

Per [#454](https://github.com/Eruhitsuji/lifetxt/issues/454), this check is the
release-critical minimum for the first Stable 1.0 release; a full real-host
OS/Python matrix is no longer a prerequisite. Real-host evidence for
Windows, WSL, Linux, and macOS beyond what is recorded below remains useful,
tracked post-Stable-1.0 quality work
([External Environment Verification](external-environment-verification.md)),
not a release blocker by itself.

## Reproducible command

From a clean checkout with a supported Python interpreter:

```text
python scripts/run_ci_like.py --profile release
```

On Windows PowerShell, the equivalent is:

```text
python scripts/run_ci_like.py --profile release --python py -3.12
```

The profile builds both artifacts, creates a temporary virtual environment,
installs the wheel, runs `python -m lifetxt --help`, runs the installed
`lifetxt --help` entry point, and executes the installed-package smoke test.
Temporary build and environment directories are removed unless
`--keep-venv` is supplied.

## Evidence record

Record the following for each interpreter and host:

| Field | Required value |
| --- | --- |
| commit | exact source commit SHA |
| artifact | wheel and sdist filenames plus SHA-256 |
| Python | interpreter version and implementation |
| host | OS/build, architecture, and filesystem |
| install | fresh environment path, sanitized |
| result | pass, fail, or skipped with reason |

The command output is mechanical evidence only. Additional real-environment
rows remain useful but, per #454, are not required before Stable 1.0.

## #454 minimal clean-artifact verification (recorded run)

| Field | Value |
| --- | --- |
| commit | `9a7c4cf8cb1b8c96abac4111ad0bb4f9b56548c9` |
| artifact | `lifetxt-0.1.0-py3-none-any.whl` sha256 `e400eaff47f3440910e7934d8c579b22c77eaeb30d2e20b02115b2be51427ad9`; `lifetxt-0.1.0.tar.gz` sha256 `79089c7d6654ceaa6bb0a833b41332f6cec910ab12bf70c391b3c715ce568799` |
| Python | CPython 3.12.3 |
| host | Microsoft Windows 10 Pro, NT 10.0.19045.0, x86_64, NTFS |
| install | two disposable venvs created by `scripts/run_ci_like.py --profile release`, both removed after the run (see below) |
| result | pass |

`scripts/run_ci_like.py --profile release` uses two separate venvs, and this
record keeps their evidence separate rather than conflating what each one
proved:

**Primary venv** (`dev`+`web` extras installed editable via `pip install -e
.[dev]`, used for the test suite and release-policy checks, not the built
wheel):

- The full test suite ran in this venv: `python -m unittest discover`
  reported `Ran 2513 tests in 454.538s ... OK (skipped=5)`.
- `scripts/check_release_policy.py` and `lifetxt safety release-gate`
  reported `OK: 10 item(s)`, `OK: 5 item(s)`, `OK: 6 item(s)` with no
  failures.
- `python -m build --wheel --sdist` produced both artifacts from a clean
  checkout; `python -m twine check` reported `PASSED` for both.

**Separate wheel-install venv** (created after the build, only the built
wheel installed into it — no `dev`/`web` extras, no editable source):

- The wheel's file listing contains only `lifetxt/*.py`,
  `lifetxt/web_assets.html`, and `lifetxt-0.1.0.dist-info/*`; no
  `__pycache__`, `.git`, `.venv`, `.cache`, `.env`, or other
  development-cache/local-state entries are present. The sdist's 294-entry
  listing was scanned for the same categories plus secret/credential-shaped
  names; none were found.
- The venv installed the built wheel without relying on any undeclared
  local dependency.
- `python -m lifetxt --help` and the installed `lifetxt --help` console
  script both ran successfully from the installed wheel, outside the
  source checkout.
- `python -m lifetxt check examples/minimal_life.txt` (parse/read smoke)
  reported `OK: 10 item(s)` against the installed wheel.

The representative core smoke run directly against the installed wheel
itself currently covers parse/read and both entry points, not an explicit
create/mutate/serialize-write/re-read/recovery-safe-path cycle; that
behavior is covered by the primary venv's full test suite instead, against
the same source, but not against the wheel-installed copy specifically.
This gap is recorded rather than silently claimed closed.

This satisfies the build, install, entry-point, artifact-content, and
core-regression items of the #454 minimal clean-artifact verification for
one supported Python version on one supported OS. The recovery-safe-path
part of the representative-smoke item remains open against the literal
installed wheel specifically, tracked as a small follow-up rather than
claimed complete. Additional Python/OS rows remain useful, non-blocking
evidence; normal CI already covers the Linux Python 3.10/3.11/3.12 matrix
and the no-Web job on every push, and the native Windows/macOS core-smoke
CI jobs cover those platforms without a manual real-host run for every
release.

A separate core-only install (no `web`/`tui`/`dev` extras) was also checked
in its own fresh virtual environment on the same commit and host: `pip list
--format=freeze` reported exactly `lifetxt`, `pip`, and the declared
Windows-only `tzdata` dependency, with no Web or TUI packages present. Both
`python -m lifetxt check examples/minimal_life.txt` and the installed
`lifetxt --help` entry point ran successfully from that environment.
