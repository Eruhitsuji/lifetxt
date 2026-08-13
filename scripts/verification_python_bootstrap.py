#!/usr/bin/env python
"""Bootstrap a supported Python interpreter for real-host release
verification (#435).

`scripts/run_external_verification.py` needs a Python from the stable
support matrix (3.10/3.11/3.12; see ``pyproject.toml``'s ``requires-python``
and ``.ai/project/STABLE_RELEASE.yml``) to drive
``scripts/run_ci_like.py --profile release``. This module finds one if it's
already installed, and otherwise provisions a verification-only interpreter
from a pinned, checksum-verified `python-build-standalone
<https://github.com/astral-sh/python-build-standalone>`_ release -- the same
project ``uv``/``rye``/``pdm`` use -- without touching the host's system
Python and without requiring administrator/root privileges.

This module is pure standard library so it can itself be run by *any*
Python 3 already on the host, even an unsupported one; its whole job is to
find or fetch a supported one for the caller.
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import shutil
import subprocess
import tarfile
import tempfile
import urllib.request
from pathlib import Path

#: Search order: prefer the newest supported version.
SUPPORTED_VERSIONS = ("3.12", "3.11", "3.10")

#: Pinned python-build-standalone release. Confirmed live against the real
#: release before recording: `gh api
#: repos/astral-sh/python-build-standalone/releases/tags/20260807` and its
#: published SHA256SUMS file. Bumping this requires updating every hash
#: below together, from that same release's SHA256SUMS.
MANIFEST_RELEASE_TAG = "20260807"

#: (version, os_name, machine) -> {"filename": ..., "sha256": ...}
#: os_name in {"windows", "linux", "macos"}; machine in {"x86_64", "aarch64"}.
MANIFEST = {
    ("3.12", "windows", "x86_64"): {
        "filename": "cpython-3.12.13+20260807-x86_64-pc-windows-msvc-install_only.tar.gz",
        "sha256": "6cf2be701aa7e9470454c9c86285c1bcc1832518d63e39c3e34e9d8ea1cbb99f",
    },
    ("3.12", "linux", "x86_64"): {
        "filename": "cpython-3.12.13+20260807-x86_64-unknown-linux-gnu-install_only.tar.gz",
        "sha256": "5bd6f36fd7ef02b909234c94dca9994ef0da06ace3bc3cece4fe27870e9cdbbe",
    },
    ("3.12", "macos", "x86_64"): {
        "filename": "cpython-3.12.13+20260807-x86_64-apple-darwin-install_only.tar.gz",
        "sha256": "ce9dc826a3215d5deadf6d7ba409a882b8d431192c4c06deb34ff00f93ceb4f5",
    },
    ("3.12", "macos", "aarch64"): {
        "filename": "cpython-3.12.13+20260807-aarch64-apple-darwin-install_only.tar.gz",
        "sha256": "4201588fc5051c2ba988abbe1f033d318965ee378fadf7fb7ef79882ba7be84b",
    },
    ("3.11", "windows", "x86_64"): {
        "filename": "cpython-3.11.15+20260807-x86_64-pc-windows-msvc-install_only.tar.gz",
        "sha256": "7e61d3d8fa394c063e586db9cc36dc91eb77211f426e2dcc3379412b227d41a6",
    },
    ("3.11", "linux", "x86_64"): {
        "filename": "cpython-3.11.15+20260807-x86_64-unknown-linux-gnu-install_only.tar.gz",
        "sha256": "b9fff092374acebc451bb881156afe6a58991213d25386358742fee296128909",
    },
    ("3.11", "macos", "x86_64"): {
        "filename": "cpython-3.11.15+20260807-x86_64-apple-darwin-install_only.tar.gz",
        "sha256": "d1842391797a9478fc1de67c8575f275c1cdf2e93a8d1deb991939dec3ec9bbf",
    },
    ("3.11", "macos", "aarch64"): {
        "filename": "cpython-3.11.15+20260807-aarch64-apple-darwin-install_only.tar.gz",
        "sha256": "f7783d9a56a75d91554c08409a674e8678d56d42555fdbb365d8190d5cc93659",
    },
    ("3.10", "windows", "x86_64"): {
        "filename": "cpython-3.10.20+20260807-x86_64-pc-windows-msvc-install_only.tar.gz",
        "sha256": "c4bb4b1a09dc09361bb766faff306bc186d1755dd4c8936f6549a5a79ef79633",
    },
    ("3.10", "linux", "x86_64"): {
        "filename": "cpython-3.10.20+20260807-x86_64-unknown-linux-gnu-install_only.tar.gz",
        "sha256": "36d480cf1f8ca45308c6cfedaad54a127e973e0525a97ca19a0229dbd5ce5f13",
    },
    ("3.10", "macos", "x86_64"): {
        "filename": "cpython-3.10.20+20260807-x86_64-apple-darwin-install_only.tar.gz",
        "sha256": "a60e165588e3163ba91a7ce71b1cadb4595148dab09a56fd66e662bd2610ed1c",
    },
    ("3.10", "macos", "aarch64"): {
        "filename": "cpython-3.10.20+20260807-aarch64-apple-darwin-install_only.tar.gz",
        "sha256": "a24ddc5cddd33ec3b73e41926c9fcf32cb65334779bdeb47d3bc3719603e9237",
    },
}


def _download_url(entry):
    return (
        "https://github.com/astral-sh/python-build-standalone/releases/download/"
        + MANIFEST_RELEASE_TAG
        + "/"
        + entry["filename"]
    )


def host_key(system=None, machine=None):
    """Normalize the current host to a MANIFEST (os_name, machine) key."""
    system = (system or platform.system()).strip().lower()
    machine = (machine or platform.machine()).strip().lower()
    if system == "windows":
        os_name = "windows"
    elif system == "darwin":
        os_name = "macos"
    elif system == "linux":
        os_name = "linux"
    else:
        os_name = None
    if machine in ("amd64", "x86_64", "x64"):
        arch = "x86_64"
    elif machine in ("arm64", "aarch64"):
        arch = "aarch64"
    else:
        arch = None
    return (os_name, arch)


def _probe_version(executable, run=subprocess.run):
    """Return "X.Y" for a candidate Python executable, or None if it isn't one."""
    try:
        completed = run(
            [executable, "-c", "import sys; print('%d.%d' % sys.version_info[:2])"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if completed.returncode != 0:
        return None
    version = completed.stdout.strip()
    return version or None


def find_existing_interpreter(env=None, which=shutil.which, probe=_probe_version):
    """Search PATH (and the Windows py launcher) for an already-installed
    supported CPython, preferring 3.12, then 3.11, then 3.10.

    A candidate is only accepted after its *reported* version is checked --
    a bare ``python3`` that resolves to an unsupported version (3.9, 3.13,
    ...) must never be silently accepted.
    """
    env = os.environ if env is None else env
    is_windows = (env.get("OS") or "").lower().startswith("windows") or os.name == "nt"

    if is_windows and which("py"):
        for version in SUPPORTED_VERSIONS:
            # The py launcher needs the -X.Y flag as its own argv entry, so
            # this probes directly rather than reusing probe(executable).
            try:
                completed = subprocess.run(
                    [
                        "py",
                        "-%s" % version,
                        "-c",
                        "import sys; print('%d.%d' % sys.version_info[:2])",
                    ],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
            except (OSError, subprocess.SubprocessError):
                continue
            if completed.returncode == 0 and completed.stdout.strip() == version:
                return {
                    "executable": "py -%s" % version,
                    "launcher": "py",
                    "version": version,
                    "category": "existing",
                }

    candidate_names = []
    for version in SUPPORTED_VERSIONS:
        candidate_names.append("python%s" % version)
    candidate_names.extend(("python3", "python"))

    for name in candidate_names:
        executable = which(name)
        if not executable:
            continue
        version = probe(executable)
        if version in SUPPORTED_VERSIONS:
            return {
                "executable": executable,
                "launcher": None,
                "version": version,
                "category": "existing",
            }
    return None


def _verify_sha256(path, expected_sha256):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest() == expected_sha256


def _default_downloader(url):
    with urllib.request.urlopen(url, timeout=120) as response:  # noqa: S310
        return response.read()


def _managed_python_executable(install_dir, os_name):
    # Every python-build-standalone "install_only" archive extracts under
    # one top-level "python/" directory regardless of platform -- confirmed
    # by extracting the real Windows 3.12.13 asset before writing this
    # module (tar -xzf produced ./python/python.exe, not a flat layout).
    if os_name == "windows":
        return install_dir / "python" / "python.exe"
    return install_dir / "python" / "bin" / "python3"


def provision_managed_python(cache_dir, host=None, downloader=None):
    """Download, checksum-verify, and extract a pinned CPython build.

    Verification happens strictly before extraction: a checksum mismatch
    deletes the downloaded bytes and returns a blocked result without ever
    unpacking unverified content. A prior successful extraction (marked by
    a ``.sha256`` sidecar recording the verified hash) is reused without a
    second download.
    """
    downloader = downloader or _default_downloader
    os_name, arch = host if host is not None else host_key()
    if os_name is None or arch is None:
        return {
            "status": "blocked",
            "category": "managed",
            "reason": "Unsupported host platform/architecture for managed Python provisioning.",
        }

    cache_dir = Path(cache_dir)
    for version in SUPPORTED_VERSIONS:
        entry = MANIFEST.get((version, os_name, arch))
        if entry is None:
            continue

        install_dir = cache_dir / "python" / version
        marker = install_dir / ".sha256"
        executable = _managed_python_executable(install_dir, os_name)
        if (
            marker.exists()
            and marker.read_text(encoding="utf-8").strip() == entry["sha256"]
            and executable.exists()
        ):
            return {
                "status": "passed",
                "category": "managed",
                "version": version,
                "executable": str(executable),
                "source": "python-build-standalone",
                "release_tag": MANIFEST_RELEASE_TAG,
                "reused": True,
            }

        url = _download_url(entry)
        try:
            payload = downloader(url)
        except Exception as exc:  # noqa: BLE001 - any network failure is "blocked", not a crash
            return {
                "status": "blocked",
                "category": "managed",
                "version": version,
                "reason": "Download failed for the managed Python runtime: %s: %s"
                % (type(exc).__name__, exc),
            }

        with tempfile.NamedTemporaryFile(delete=False, suffix=".tar.gz") as handle:
            handle.write(payload)
            temp_path = Path(handle.name)
        try:
            if not _verify_sha256(temp_path, entry["sha256"]):
                return {
                    "status": "blocked",
                    "category": "managed",
                    "version": version,
                    "reason": "Checksum verification failed for the downloaded managed Python "
                    "runtime; refusing to extract unverified content.",
                }

            if install_dir.exists():
                shutil.rmtree(install_dir)
            install_dir.mkdir(parents=True, exist_ok=True)
            with tarfile.open(temp_path, "r:gz") as archive:
                # Prefer the safe extraction filter (PEP 706) when the host
                # Python has it; older interpreters -- this module must run
                # under whatever Python is already on the host, supported
                # or not -- fall back to plain extraction. Checksum
                # verification above already confirms the archive matches
                # the pinned release; the filter is defense in depth against
                # path traversal/symlink members, not the primary guard.
                if hasattr(tarfile, "data_filter"):
                    archive.extractall(install_dir, filter="data")
                else:
                    archive.extractall(install_dir)  # noqa: S202
        finally:
            if temp_path.exists():
                temp_path.unlink()

        resolved_executable = _managed_python_executable(install_dir, os_name)
        if not resolved_executable.exists():
            # The archive layout differs from the expected install_only
            # convention (flat on Windows, python/bin/python3 on POSIX).
            candidates = list(
                install_dir.rglob("python3" if os_name != "windows" else "python.exe")
            )
            if candidates:
                resolved_executable = candidates[0]
        if not resolved_executable.exists():
            return {
                "status": "blocked",
                "category": "managed",
                "version": version,
                "reason": "Extracted managed Python runtime did not contain the expected executable.",
            }

        marker.write_text(entry["sha256"], encoding="utf-8")
        return {
            "status": "passed",
            "category": "managed",
            "version": version,
            "executable": str(resolved_executable),
            "source": "python-build-standalone",
            "release_tag": MANIFEST_RELEASE_TAG,
            "reused": False,
        }

    return {
        "status": "blocked",
        "category": "managed",
        "reason": "No python-build-standalone release is pinned for this host platform/architecture (%s/%s)."
        % (os_name, arch),
    }


def ensure_verification_python(cache_dir, env=None, downloader=None, host=None):
    """Find an existing supported interpreter, or provision a managed one."""
    existing = find_existing_interpreter(env=env)
    if existing is not None:
        return {"status": "passed", **existing}
    return provision_managed_python(cache_dir, host=host, downloader=downloader)


def create_verification_venv(python_executable, cache_dir, reuse=True):
    """Create (or reuse) an isolated venv under ``cache_dir`` for the
    release-profile run, independent of the caller's own active
    venv/Conda environment.
    """
    cache_dir = Path(cache_dir)
    venv_dir = cache_dir / "venv"
    marker = cache_dir / "venv.source"
    venv_python = _venv_python_path(venv_dir)

    if (
        reuse
        and marker.exists()
        and marker.read_text(encoding="utf-8").strip() == str(python_executable)
        and venv_python.exists()
    ):
        return str(venv_python)

    if venv_dir.exists():
        shutil.rmtree(venv_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)

    command = (
        python_executable.split()
        if " " in str(python_executable) and python_executable.startswith("py ")
        else [python_executable]
    )
    subprocess.check_call(command + ["-m", "venv", str(venv_dir)])
    marker.write_text(str(python_executable), encoding="utf-8")
    return str(_venv_python_path(venv_dir))


def _venv_python_path(venv_dir):
    if os.name == "nt":
        return venv_dir / "Scripts" / "python.exe"
    return venv_dir / "bin" / "python"
