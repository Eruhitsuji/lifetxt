#!/usr/bin/env python
"""Confirm a release tag's version matches pyproject.toml's declared version.

Used by the release workflow before any package or image is published, so a
tag that does not match the source tree's own declared version fails loudly
instead of silently publishing a mismatched artifact.
"""

from __future__ import print_function

import argparse
import re
import sys
from pathlib import Path

try:
    import tomllib
except ImportError:  # Python 3.10 compatibility
    import tomli as tomllib

_TAG_PATTERN = re.compile(r"^v(?P<version>\d+\.\d+\.\d+(?:[A-Za-z0-9.]+)?)$")


def project_version(root):
    with open(Path(root) / "pyproject.toml", "rb") as handle:
        return tomllib.load(handle)["project"]["version"]


def version_from_tag(tag):
    match = _TAG_PATTERN.match(tag)
    if not match:
        raise ValueError(
            "Tag %r does not match the vX.Y.Z[suffix] release pattern." % tag
        )
    return match.group("version")


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tag", help="Git tag, e.g. v1.0.0 or v1.0.0rc1")
    parser.add_argument("--root", default=".", help="Repository root")
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    declared = project_version(args.root)
    try:
        from_tag = version_from_tag(args.tag)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    if declared != from_tag:
        print(
            "Tag %r (version %r) does not match pyproject.toml version %r"
            % (args.tag, from_tag, declared),
            file=sys.stderr,
        )
        return 1
    print("OK: tag %s matches pyproject.toml version %s" % (args.tag, declared))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
