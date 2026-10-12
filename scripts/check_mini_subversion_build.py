"""Build Mini against a disposable four-part Core release (no publication)."""

import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lifetxt.versioning import semver_metadata


def main():
    root = Path(__file__).resolve().parents[1]
    version = "1.0.4.1"
    with tempfile.TemporaryDirectory() as tmp:
        scratch = Path(tmp)
        shutil.copytree(
            root / "lifetxt-mini",
            scratch / "lifetxt-mini",
            ignore=shutil.ignore_patterns("target"),
        )
        (scratch / "pyproject.toml").write_text('[project]\nversion = "%s"\n' % version)
        for name in ("Cargo.toml", "Cargo.lock"):
            path = scratch / "lifetxt-mini" / name
            text = path.read_text()
            text = re.sub(
                r'^version = "[^"\n]+"',
                'version = "%s"' % semver_metadata(version),
                text,
                flags=re.MULTILINE,
            )
            path.write_text(text)
        subprocess.run(
            ["cargo", "build", "--locked"], cwd=scratch / "lifetxt-mini", check=True
        )
        binary = scratch / "lifetxt-mini/target/debug/lifetxt-mini"
        if sys.platform == "win32":
            binary = binary.with_suffix(".exe")
        subprocess.run(
            [
                sys.executable,
                str(root / "scripts/check_lifetxt_mini_version.py"),
                "--root",
                str(scratch),
                "--tag",
                "v" + version,
                "--binary",
                str(binary),
            ],
            check=True,
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
