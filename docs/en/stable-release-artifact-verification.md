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
part of the representative-smoke item was open against the literal
installed wheel specifically at this point in the record; it is closed by
the `v1.0.0rc1` evidence recorded further below. Additional Python/OS rows
remain useful, non-blocking evidence; normal CI already covers the Linux
Python 3.10/3.11/3.12 matrix and the no-Web job on every push, and the
native Windows/macOS core-smoke CI jobs cover those platforms without a
manual real-host run for every release.

A separate core-only install (no `web`/`tui`/`dev` extras) was also checked
in its own fresh virtual environment on the same commit and host: `pip list
--format=freeze` reported exactly `lifetxt`, `pip`, and the declared
Windows-only `tzdata` dependency, with no Web or TUI packages present. Both
`python -m lifetxt check examples/minimal_life.txt` and the installed
`lifetxt --help` entry point ran successfully from that environment.

## `v1.0.0rc1` recovery-safe-path smoke (closes the gap above)

Recorded when cutting the `v1.0.0rc1` release candidate.

| Field | Value |
| --- | --- |
| commit | `ca1894b6f5571b3862138d84bfe9dc542ebc2551` |
| artifact | `lifetxt-1.0.0rc1-py3-none-any.whl` sha256 `fba241ab14bea43eb74281ec106a76f7a9c89aab5318e5dc7f837e1955b12c88`; `lifetxt-1.0.0rc1.tar.gz` sha256 `73ffca299840d4268578d782a3caa2dac416b8e9b115fe03901d694e6eba3cf0` |
| Python | CPython 3.12.3 |
| host | Microsoft Windows 10 Pro, NT 10.0.19045.0, x86_64, NTFS |
| install | disposable venv, only the built wheel installed (no `dev`/`web` extras), removed after the run |
| result | pass |

A fresh, disposable venv installed only the built wheel (no source
checkout, no editable install). Both `python -m lifetxt --version` and the
installed `lifetxt --version` entry point reported `lifetxt 1.0.0rc1`. In a
scratch working directory, using only the installed `lifetxt` console
script:

- `lifetxt init --yes` (create) wrote a starter `life.txt`; `lifetxt check`
  reported `OK: 1 item(s)`.
- `echo "Buy milk" | lifetxt quick - --append life.txt` (create) appended a
  second item; re-reading the file and `lifetxt check` confirmed
  `OK: 2 item(s)`.
- `lifetxt complete life.txt --text "Buy milk"` (mutate) marked that item
  done; re-reading the file showed `[x] T "Buy milk" done:2026-08-21`.
- `lifetxt format canon life.txt --write` (serialize/write through the
  revision-checked atomic-write contract) reported `"changed":false,
  "written":false` -- the file was already canonical, confirming the
  round-trip stayed stable.
- `lifetxt format migrate life.txt --write` (a second, distinct
  revision-checked write: the recovery-safe path) reported
  `"changed":true,"written":true` and added the `#! format_version: 1`
  directive; re-reading the file and `lifetxt check` confirmed the write
  took effect and the file remained valid (`OK: 2 item(s)`).

This closes the gap the earlier evidence run above explicitly recorded:
parse/read, create, mutate, serialize/write, re-read, and a recovery-safe
write path are now all confirmed directly against an installed release
artifact, not only against the source tree in a separate venv.
