#!/usr/bin/env python
"""Generate the three winget manifest files for one lifetxt release.

winget-pkgs requires a version manifest, an installer manifest, and a
default-locale manifest per submission (manifest schema 1.6.0). This script
fills the templates in packaging/winget/ with one release's concrete
version/URL/checksum so the maintainer can review and submit them by hand --
see docs/en/distribution.md#4-winget-and-scoop-windows-package-managers for
the manual submission steps this script does not perform.

Usage:
    python scripts/generate_winget_manifest.py \\
        --version 1.0.0 \\
        --installer-url https://github.com/Eruhitsuji/lifetxt/releases/download/v1.0.0/lifetxt-windows-x86_64.exe \\
        --sha256 <sha256 from the release's SHA256SUMS file> \\
        --output-dir packaging/winget/generated
"""

from __future__ import print_function

import argparse
import re
import sys
from pathlib import Path

PACKAGE_IDENTIFIER = "Eruhitsuji.lifetxt"
PUBLISHER = "Eruhitsuji"
PACKAGE_NAME = "lifetxt"
MANIFEST_SCHEMA_VERSION = "1.6.0"

_SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")


def build_version_manifest(version):
    return """# yaml-language-server: $schema=https://aka.ms/winget-manifest.version.1.6.0.schema.json
PackageIdentifier: {identifier}
PackageVersion: {version}
DefaultLocale: en-US
ManifestType: version
ManifestVersion: {schema_version}
""".format(
        identifier=PACKAGE_IDENTIFIER,
        version=version,
        schema_version=MANIFEST_SCHEMA_VERSION,
    )


def build_installer_manifest(version, installer_url, sha256):
    # InstallerType: portable -- the artifact is a single, standalone
    # executable (see #570), not a setup.exe with silent-install switches.
    # winget's portable-installer support symlinks the downloaded binary
    # onto PATH under each name listed in Commands.
    return """# yaml-language-server: $schema=https://aka.ms/winget-manifest.installer.1.6.0.schema.json
PackageIdentifier: {identifier}
PackageVersion: {version}
InstallerType: portable
UpgradeBehavior: install
Commands:
  - lifetxt
Installers:
  - Architecture: x64
    InstallerUrl: {installer_url}
    InstallerSha256: {sha256}
ManifestType: installer
ManifestVersion: {schema_version}
""".format(
        identifier=PACKAGE_IDENTIFIER,
        version=version,
        installer_url=installer_url,
        sha256=sha256.upper(),
        schema_version=MANIFEST_SCHEMA_VERSION,
    )


def build_locale_manifest(version):
    return """# yaml-language-server: $schema=https://aka.ms/winget-manifest.defaultLocale.1.6.0.schema.json
PackageIdentifier: {identifier}
PackageVersion: {version}
PackageLocale: en-US
Publisher: {publisher}
PublisherUrl: https://github.com/Eruhitsuji
PublisherSupportUrl: https://github.com/Eruhitsuji/lifetxt/issues
PackageName: {package_name}
PackageUrl: https://github.com/Eruhitsuji/lifetxt
License: MIT
LicenseUrl: https://github.com/Eruhitsuji/lifetxt/blob/main/LICENSE
ShortDescription: Parser, validator, converter, CLI, and optional web UI for life.txt.
Moniker: lifetxt
Tags:
  - cli
  - task-manager
  - todo
  - productivity
  - plain-text
ManifestType: defaultLocale
ManifestVersion: {schema_version}
""".format(
        identifier=PACKAGE_IDENTIFIER,
        version=version,
        publisher=PUBLISHER,
        package_name=PACKAGE_NAME,
        schema_version=MANIFEST_SCHEMA_VERSION,
    )


def generate(version, installer_url, sha256, output_dir):
    if not _SHA256_RE.match(sha256):
        raise ValueError("--sha256 must be a 64-character hex SHA-256 digest")
    output_dir = (
        Path(output_dir) / PACKAGE_IDENTIFIER.split(".")[0] / PACKAGE_NAME / version
    )
    output_dir.mkdir(parents=True, exist_ok=True)

    files = {
        "%s.yaml" % PACKAGE_IDENTIFIER: build_version_manifest(version),
        "%s.installer.yaml" % PACKAGE_IDENTIFIER: build_installer_manifest(
            version, installer_url, sha256
        ),
        "%s.locale.en-US.yaml" % PACKAGE_IDENTIFIER: build_locale_manifest(version),
    }
    for name, content in files.items():
        (output_dir / name).write_text(content, encoding="utf-8", newline="\n")
    return sorted(str(output_dir / name) for name in files)


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
        "--output-dir",
        default="packaging/winget/generated",
        help="Directory to write manifests/<Publisher>/<Package>/<version>/ under",
    )
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        written = generate(
            args.version, args.installer_url, args.sha256, args.output_dir
        )
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    for path in written:
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
