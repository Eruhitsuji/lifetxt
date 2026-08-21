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
| install | fresh venv created by `scripts/run_ci_like.py --profile release`, removed after the run |
| result | pass |

Evidence gathered for this run:

- `python -m build --wheel --sdist` produced both artifacts from a clean
  checkout; `twine check` reported `PASSED` for both.
- The wheel's file listing contains only `lifetxt/*.py`, `lifetxt/web_assets.html`,
  and `lifetxt-0.1.0.dist-info/*`; no `__pycache__`, `.git`, `.venv`, `.cache`,
  `.env`, or other development-cache/local-state entries are present. The
  sdist's 294-entry listing was scanned for the same categories plus
  secret/credential-shaped names; none were found.
- A fresh virtual environment installed the built wheel (plus the `dev` and
  `web` extras used by the release profile) without relying on any
  undeclared local dependency.
- `python -m lifetxt --help` and the installed `lifetxt --help` console
  script both ran successfully from the installed package, outside the
  source checkout.
- `python -m lifetxt check examples/minimal_life.txt` (representative
  parse/read smoke) reported `OK: 10 item(s)` against the installed package.
- The full test suite ran inside the same fresh environment:
  `python -m unittest discover` reported `Ran 2513 tests in 454.538s ...
  OK (skipped=5)`, and the release-policy/release-gate smoke reported
  `OK: 10 item(s)`, `OK: 5 item(s)`, `OK: 6 item(s)` with no failures.

This satisfies the #454 minimal clean-artifact verification for one
supported Python version on one supported OS. Additional Python/OS rows
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
