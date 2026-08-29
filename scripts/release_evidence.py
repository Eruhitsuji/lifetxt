#!/usr/bin/env python
"""Build release artifacts and emit checksum, SBOM, and provenance evidence."""

from __future__ import print_function

import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
import tempfile
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

try:
    import tomllib
except ImportError:  # Python 3.10 compatibility
    import tomli as tomllib


def _run(command, cwd):
    result = subprocess.run(
        command,
        cwd=str(cwd),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if result.returncode != 0:
        # Captured output must be surfaced before raising: check=True alone
        # discards it, leaving a bare CalledProcessError with no indication
        # of what the subprocess actually reported -- reproduced live when
        # a fresh CI runner's build failed with no diagnostic beyond "exit
        # status 1" until this output was printed by hand from a local
        # reproduction.
        sys.stderr.write(result.stdout)
        sys.stderr.write(result.stderr)
        result.check_returncode()
    return result


def _tool_version(name):
    try:
        return version(name)
    except PackageNotFoundError:
        return None


def _git(root, *args):
    try:
        return _run(["git"] + list(args), root).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def _sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_output_path(path):
    return path.name


def generate(root, output):
    root = Path(root).resolve()
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    if any(output.iterdir()):
        raise RuntimeError("Evidence output directory must be empty.")
    with tempfile.TemporaryDirectory(prefix="lifetxt-release-build-") as temp:
        build_dir = Path(temp)
        _run(
            [
                sys.executable,
                "-m",
                "build",
                "--no-isolation",
                "--sdist",
                "--wheel",
                "--outdir",
                str(build_dir),
            ],
            root,
        )
        artifacts = sorted(
            path for path in build_dir.iterdir() if path.suffix in (".whl", ".gz")
        )
        if len(artifacts) != 2:
            raise RuntimeError("Expected exactly one wheel and one sdist.")
        for artifact in artifacts:
            target = output / _safe_output_path(artifact)
            target.write_bytes(artifact.read_bytes())

    artifact_rows = [
        {"file": path.name, "sha256": _sha256(path), "bytes": path.stat().st_size}
        for path in sorted(output.iterdir())
        if path.suffix in (".whl", ".gz")
    ]
    if len(artifact_rows) != 2:
        raise RuntimeError("Evidence output must contain one wheel and one sdist.")
    (output / "SHA256SUMS").write_text(
        "".join("%s  %s\n" % (row["sha256"], row["file"]) for row in artifact_rows),
        encoding="utf-8",
    )

    with open(root / "pyproject.toml", "rb") as handle:
        project = tomllib.load(handle)["project"]
    dependencies = list(project.get("dependencies", []))
    extras = {
        name: list(values)
        for name, values in project.get("optional-dependencies", {}).items()
    }
    sbom = {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "version": 1,
        "metadata": {
            "component": {
                "type": "application",
                "name": project["name"],
                "version": project["version"],
            }
        },
        "components": [
            {
                "type": "library",
                "name": dependency.split(";", 1)[0].strip(),
                "scope": "required",
            }
            for dependency in dependencies
        ],
        "properties": [
            {"name": "lifetxt:extra:%s" % name, "value": json.dumps(values)}
            for name, values in extras.items()
        ],
    }
    (output / "sbom.cdx.json").write_text(
        json.dumps(sbom, indent=2) + "\n", encoding="utf-8"
    )

    provenance = {
        "schema": "lifetxt-release-provenance-v1",
        "package": {"name": project["name"], "version": project["version"]},
        "source": {
            "commit": _git(root, "rev-parse", "HEAD"),
            "tag": _git(root, "describe", "--tags", "--exact-match"),
        },
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
        },
        "tools": {
            "build": _tool_version("build"),
            "setuptools": _tool_version("setuptools"),
        },
        "workflow_run": os.environ.get("GITHUB_RUN_ID") or "local",
        "artifacts": artifact_rows,
    }
    (output / "provenance.json").write_text(
        json.dumps(provenance, indent=2) + "\n", encoding="utf-8"
    )
    return {
        "ok": True,
        "output_files": sorted(path.name for path in output.iterdir()),
        "artifacts": artifact_rows,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--root", default=Path(__file__).resolve().parents[1], type=Path
    )
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(generate(args.root, args.output), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
