#!/usr/bin/env python
"""Set desktop/src-tauri/tauri.conf.json's version to match a release tag.

Ties the lifetxt Desktop installer's own version to the same immutable
release tag as the bundled lifetxt runtime it packages (#570), so the two
are traceable to one source revision (#574's own requirement) rather than
drifting independently -- this project deliberately keeps them at 1:1 for
this first slice rather than versioning the desktop shell separately.

Usage:
    python scripts/set_tauri_desktop_version.py --version 1.0.0
"""

from __future__ import print_function

import argparse
import json
import re
import sys
from pathlib import Path

DEFAULT_CONFIG_PATH = "desktop/src-tauri/tauri.conf.json"
_VERSION_RE = re.compile(r"^\d+\.\d+\.\d+(?:[A-Za-z0-9.]+)?$")


def set_version(config_path, version):
    if not _VERSION_RE.match(version):
        raise ValueError("--version must look like 1.0.0 or 1.0.0rc1, got %r" % version)
    path = Path(config_path)
    data = json.loads(path.read_text(encoding="utf-8"))
    data["version"] = version
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8", newline="\n")


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--version", required=True, help="Version to set, e.g. 1.0.0 (no leading v)"
    )
    parser.add_argument(
        "--config",
        default=DEFAULT_CONFIG_PATH,
        help="Path to tauri.conf.json",
    )
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        set_version(args.config, args.version)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print("Set %s version to %s" % (args.config, args.version))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
