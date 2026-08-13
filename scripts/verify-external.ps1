# One-command entry point for real-host stable-release verification (#435)
# on Windows PowerShell.
#
# This script's only job is finding *any* Python 3 already on the host --
# even an unsupported version -- to hand off to
# scripts/run_external_verification.py, which bootstraps a supported
# interpreter (3.10-3.12) internally: an already-installed one if present,
# otherwise a pinned, checksum-verified python-build-standalone build under
# .cache/ (see scripts/verification_python_bootstrap.py). This wrapper never
# touches the system Python and does not require administrator privileges.
#
# See docs/en/external-environment-verification.md for details, evidence
# format, and what remains manual/blocked.

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$target = Join-Path $repoRoot "scripts\run_external_verification.py"

$py = Get-Command py -ErrorAction SilentlyContinue
if ($py) {
    & py -3 $target @args
    exit $LASTEXITCODE
}

$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) {
    $python = Get-Command python3 -ErrorAction SilentlyContinue
}
if (-not $python) {
    Write-Error "No Python interpreter (py launcher, python, or python3) found on PATH. Install any Python 3 -- even an unsupported version is enough to bootstrap -- then re-run this script. See docs/en/external-environment-verification.md."
    exit 1
}

& $python.Path $target @args
exit $LASTEXITCODE
