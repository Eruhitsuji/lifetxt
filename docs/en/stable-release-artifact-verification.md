# Stable Release Artifact Verification

This document defines the mechanical artifact check for #326. It proves that
the source tree can produce a wheel and sdist, that a fresh virtual environment
can install the wheel, and that both public entry points run outside the source
checkout. It does not replace real-host evidence for Windows, WSL, Linux, or
macOS.

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

The command output is mechanical evidence only. The supported-environment
matrix is complete only after the real-environment procedure records the same
fields for each required OS row.
