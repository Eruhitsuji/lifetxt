#!/usr/bin/env python
"""Generate the Scoop manifest (lifetxt.json) for one lifetxt release.

Scoop manifests are a single JSON file per package, normally kept in a
"bucket" repository (see docs/en/distribution.md#4-winget-and-scoop-windows-package-managers
for why this project does not maintain its own bucket in this first slice).
This script fills the manifest with one release's concrete version/URL/
checksum so the maintainer can review and publish it by hand.

Usage:
    python scripts/generate_scoop_manifest.py \\
        --version 1.0.0 \\
        --installer-url https://github.com/Eruhitsuji/lifetxt/releases/download/v1.0.0/lifetxt-windows-x86_64.exe \\
        --sha256 <sha256 from the release's SHA256SUMS file> \\
        --output packaging/scoop/generated/lifetxt.json
"""

from __future__ import print_function

import argparse
import json
import re
import sys
from pathlib import Path

DOWNLOADED_ARTIFACT_NAME = "lifetxt-windows-x86_64.exe"
LINKED_COMMAND_NAME = "lifetxt.exe"

_SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")


def build_manifest(version, installer_url, sha256):
    if not _SHA256_RE.match(sha256):
        raise ValueError("--sha256 must be a 64-character hex SHA-256 digest")
    return {
        "version": version,
        "description": (
            "Parser, validator, converter, CLI, and optional web UI for life.txt."
        ),
        "homepage": "https://github.com/Eruhitsuji/lifetxt",
        "license": "MIT",
        "url": installer_url,
        "hash": "sha256:%s" % sha256.lower(),
        # Scoop links the downloaded artifact's own filename onto PATH by
        # default; renaming it here keeps the shim name `lifetxt` regardless
        # of the platform-qualified artifact filename #570 publishes.
        "bin": [[DOWNLOADED_ARTIFACT_NAME, LINKED_COMMAND_NAME]],
        "checkver": {"github": "https://github.com/Eruhitsuji/lifetxt"},
        "autoupdate": {
            "url": (
                "https://github.com/Eruhitsuji/lifetxt/releases/download/"
                "v$version/%s" % DOWNLOADED_ARTIFACT_NAME
            )
        },
    }


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", required=True, help="Release version, e.g. 1.0.0")
    parser.add_argument(
        "--installer-url",
        required=True,
        help="Direct download URL for the Windows standalone executable",
    )
    parser.add_argument(
        "--sha256", required=True, help="SHA-256 checksum of the installer, hex"
    )
    parser.add_argument(
        "--output",
        default="packaging/scoop/generated/lifetxt.json",
        help="Path to write the manifest to",
    )
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        manifest = build_manifest(args.version, args.installer_url, args.sha256)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(manifest, indent=4) + "\n", encoding="utf-8", newline="\n"
    )
    print(str(output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
