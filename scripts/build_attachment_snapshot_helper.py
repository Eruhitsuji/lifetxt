"""Explicit operator/build-time installation; never imported by request handlers."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import tempfile


SOURCE = Path(__file__).resolve().parents[1] / "native/resource_snapshot.c"
NAME = "_attachment_snapshot_helper"
MANIFEST = ".attachment-snapshot-helper.json"


def build_helper(output):
    if (
        platform.system() != "Linux"
        or platform.machine() != "x86_64"
        or platform.libc_ver()[0] != "glibc"
    ):
        raise RuntimeError("Helper builds currently require Linux x86_64 glibc.")
    compiler = shutil.which("cc")
    if not compiler:
        raise RuntimeError("A build-time C compiler is required.")
    output = Path(output).absolute()
    if output.name != NAME or not output.parent.is_dir():
        raise ValueError("Use an existing package directory and the fixed helper name.")
    with tempfile.TemporaryDirectory(dir=output.parent) as temporary:
        executable = Path(temporary) / NAME
        subprocess.run(
            [
                compiler,
                "-O2",
                "-Wall",
                "-Wextra",
                "-Werror",
                "-o",
                str(executable),
                str(SOURCE),
            ],
            check=True,
            capture_output=True,
            timeout=60,
        )
        executable.chmod(0o755)
        binary = executable.read_bytes()
        if not binary.startswith(b"\x7fELF"):
            raise RuntimeError("Build did not produce an ELF helper.")
        manifest = {
            "protocol": "LTXS1",
            "architecture": platform.machine(),
            "libc": platform.libc_ver()[0],
            "source_sha256": hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
            "helper_sha256": hashlib.sha256(binary).hexdigest(),
        }
        manifest_path = Path(temporary) / MANIFEST
        manifest_path.write_text(json.dumps(manifest, sort_keys=True) + "\n")
        manifest_path.chmod(0o644)
        # Mismatched/partly installed pairs fail closed in the runtime verifier.
        os.replace(executable, output)
        os.replace(manifest_path, output.parent / MANIFEST)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output", type=Path, default=SOURCE.parent.parent / "lifetxt" / NAME
    )
    args = parser.parse_args()
    build_helper(args.output)
    print("Installed optional Linux snapshot helper and integrity manifest.")


if __name__ == "__main__":
    main()
