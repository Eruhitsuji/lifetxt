#!/usr/bin/env python
"""Build the #570 standalone lifetxt binary and stage it for Tauri bundling.

lifetxt Desktop (#574) bundles a real, self-contained lifetxt runtime so a
fresh install needs no separate Python/lifetxt setup. This script builds
that same PyInstaller artifact (packaging/pyinstaller/lifetxt.spec -- no
second, independent build) and copies it to
desktop/src-tauri/resources/bin/, the location tauri.conf.json's
`bundle.resources` config packages into every installer.

Must run natively per target platform (matching #570's own build model),
immediately before `cargo tauri build` in the same CI job/local shell.

Usage:
    python packaging/tauri-desktop/prepare_bundled_runtime.py
"""

from __future__ import print_function

import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_FILE = REPO_ROOT / "packaging" / "pyinstaller" / "lifetxt.spec"
RESOURCE_BIN_DIR = REPO_ROOT / "desktop" / "src-tauri" / "resources" / "bin"


def main(argv=None):
    del argv  # no arguments today; kept for a consistent script signature
    build_dist = REPO_ROOT / "dist" / "standalone"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "PyInstaller",
            str(SPEC_FILE),
            "--distpath",
            str(build_dist),
            "--workpath",
            str(REPO_ROOT / "build" / "pyinstaller"),
            "--clean",
            "--noconfirm",
        ],
        cwd=str(REPO_ROOT),
    )
    if result.returncode != 0:
        print("PyInstaller build failed", file=sys.stderr)
        return 1

    binary_name = "lifetxt.exe" if sys.platform == "win32" else "lifetxt"
    built_binary = build_dist / binary_name
    if not built_binary.exists():
        print("Expected built binary not found: %s" % built_binary, file=sys.stderr)
        return 1

    RESOURCE_BIN_DIR.mkdir(parents=True, exist_ok=True)
    # Clear any stale binary from a previous run/platform before copying,
    # since Tauri's resources glob would otherwise also package it.
    for existing in RESOURCE_BIN_DIR.glob("lifetxt*"):
        if existing.name != ".gitkeep":
            existing.unlink()

    destination = RESOURCE_BIN_DIR / binary_name
    shutil.copy2(built_binary, destination)
    print(str(destination))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
