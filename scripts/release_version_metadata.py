"""Emit Docker aliases for a stable three/four-part release tag."""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lifetxt.versioning import canonical_release, release_parts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tag")
    args = parser.parse_args()
    if not args.tag.startswith("v"):
        parser.error("release tag must start with v")
    try:
        parts = release_parts(args.tag[1:])
        version = canonical_release(args.tag[1:])
    except ValueError as exc:
        parser.error(str(exc))
    print("version=" + version)
    print("minor=%d.%d" % parts[:2])
    print("major=%d" % parts[0])
    return 0


if __name__ == "__main__":
    sys.exit(main())
