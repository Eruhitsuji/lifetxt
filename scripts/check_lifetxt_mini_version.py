"""Verify Core, Cargo metadata, tag and the Mini runtime release identity."""

import argparse
import re
import subprocess
import sys
from pathlib import Path

try:
    import tomllib
except ImportError:
    import tomli as tomllib

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lifetxt.versioning import canonical_release, semver_metadata


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--binary", type=Path)
    parser.add_argument("--tag")
    parser.add_argument(
        "--root", type=Path, default=Path(__file__).resolve().parents[1]
    )
    args = parser.parse_args()
    root = args.root
    with (root / "pyproject.toml").open("rb") as handle:
        core = tomllib.load(handle)["project"]["version"]
    with (root / "lifetxt-mini" / "Cargo.toml").open("rb") as handle:
        cargo = tomllib.load(handle)["package"]["version"]
    with (root / "lifetxt-mini" / "Cargo.lock").open("rb") as handle:
        packages = tomllib.load(handle)["package"]
    locked = [p["version"] for p in packages if p["name"] == "lifetxt-mini"]
    expected = semver_metadata(core)
    if cargo != expected or locked != [expected]:
        raise SystemExit(
            "version mismatch: Core=%s, expected Cargo=%s, Cargo=%s, lock=%s"
            % (core, expected, cargo, locked)
        )
    if args.binary:
        output = subprocess.check_output(
            [str(args.binary), "--version"], text=True
        ).strip()
        match = re.fullmatch(r"lifetxt-mini ([0-9]+(?:\.[0-9]+){2,3})", output)
        if not match:
            raise SystemExit("cannot parse Mini version from: " + output)
        if canonical_release(match.group(1)) != canonical_release(core):
            raise SystemExit("Mini version does not match Core: " + output)
    if args.tag and (
        not args.tag.startswith("v")
        or canonical_release(args.tag[1:]) != canonical_release(core)
    ):
        raise SystemExit("tag %s does not match Core version %s" % (args.tag, core))
    print("lifetxt-mini version consistent: " + core)
    return 0


if __name__ == "__main__":
    sys.exit(main())
