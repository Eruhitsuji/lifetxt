#!/usr/bin/env bash
# One-command entry point for real-host stable-release verification (#435)
# on WSL, native Linux, and macOS.
#
# This script's only job is finding *any* Python 3 already on the host --
# even an unsupported version -- to hand off to
# scripts/run_external_verification.py, which bootstraps a supported
# interpreter (3.10-3.12) internally: an already-installed one if present,
# otherwise a pinned, checksum-verified python-build-standalone build under
# .cache/ (see scripts/verification_python_bootstrap.py). This wrapper never
# touches the system Python and does not require root privileges.
#
# See docs/en/external-environment-verification.md for details, evidence
# format, and what remains manual/blocked.

set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
target="$repo_root/scripts/run_external_verification.py"

python_bin=""
for candidate in python3 python; do
    if command -v "$candidate" >/dev/null 2>&1; then
        python_bin="$candidate"
        break
    fi
done

if [ -z "$python_bin" ]; then
    echo "No Python interpreter (python3 or python) found on PATH. Install any Python 3 -- even an unsupported version is enough to bootstrap -- then re-run this script. See docs/en/external-environment-verification.md." >&2
    exit 1
fi

exec "$python_bin" "$target" "$@"
