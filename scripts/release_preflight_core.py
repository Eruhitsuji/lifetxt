"""Build and verify a non-public Core payload using the preflight proof contract."""

import argparse
import email.parser
import importlib.metadata
import json
import os
import platform
import shutil
import subprocess
import sys
import tarfile
import tempfile
import zipfile
from pathlib import Path

try:
    import tomllib
except ImportError:
    import tomli as tomllib

import release_evidence
import release_preflight_proof as proof


def run(command, cwd, env=None):
    result = subprocess.run(
        command, cwd=cwd, env=env, capture_output=True, text=True, timeout=600
    )
    # Stream command output into the job log, including on failure.
    sys.stdout.write(result.stdout)
    sys.stderr.write(result.stderr)
    result.check_returncode()
    return result.stdout.strip()


def git(root, *args):
    return run(["git", *args], root)


def validate_context(candidate, controller, context):
    proof.validate_candidate(candidate)
    for key, field in (
        ("GITHUB_REPOSITORY", "repository"),
        ("GITHUB_RUN_ID", "run_id"),
        ("GITHUB_RUN_ATTEMPT", "run_attempt"),
    ):
        proof.require(
            context.get(key) == str(candidate[field]),
            "execution context mismatch: " + key,
        )
    proof.require(
        git(controller, "rev-parse", "HEAD") == candidate["controller_sha"],
        "controller checkout mismatch",
    )
    proof.require(
        not git(controller, "status", "--porcelain", "--untracked-files=no"),
        "controller tracked files are dirty",
    )


def validate_source(candidate, source):
    proof.require(
        git(source, "rev-parse", "HEAD") == candidate["source_sha"],
        "source checkout mismatch",
    )
    proof.require(
        not git(source, "status", "--porcelain", "--untracked-files=no"),
        "source tracked files are dirty",
    )
    with (source / "pyproject.toml").open("rb") as stream:
        project = tomllib.load(stream)["project"]
    proof.require(
        project["name"] == "lifetxt" and project["version"] == candidate["version"],
        "source package/version mismatch",
    )


def package_metadata(path):
    if path.suffix == ".whl":
        with zipfile.ZipFile(path) as archive:
            names = [
                name
                for name in archive.namelist()
                if name.endswith(".dist-info/METADATA")
            ]
            proof.require(len(names) == 1, "wheel must contain one METADATA")
            raw = archive.read(names[0])
    else:
        with tarfile.open(path, "r:gz") as archive:
            members = [
                item
                for item in archive.getmembers()
                if item.name.count("/") == 1
                and item.name.endswith("/PKG-INFO")
                and item.isfile()
            ]
            proof.require(
                len(members) == 1, "sdist must contain one top-level PKG-INFO"
            )
            with archive.extractfile(members[0]) as stream:
                raw = stream.read()
    return email.parser.BytesParser().parsebytes(raw)


def validate_evidence(candidate, payload):
    """Validate actual archives, source provenance, SBOM and per-file digests."""
    paths = sorted(payload.iterdir())
    wheels = [path for path in paths if path.suffix == ".whl"]
    sdists = [path for path in paths if path.name.endswith(".tar.gz")]
    proof.require(len(wheels) == len(sdists) == 1, "expected one wheel and one sdist")
    packages = wheels + sdists
    expected = {path.name for path in packages} | {"sbom.cdx.json", "provenance.json"}
    proof.require(
        {path.name for path in paths} == expected
        and all(path.is_file() and not path.is_symlink() for path in paths),
        "unexpected Core payload inventory",
    )
    for path in packages:
        metadata = package_metadata(path)
        proof.require(
            metadata.get_all("Name") == ["lifetxt"]
            and metadata.get_all("Version") == [candidate["version"]],
            "archive package/version mismatch",
        )
    sbom = proof.load(payload / "sbom.cdx.json")
    component = sbom["metadata"]["component"]
    proof.require(
        component["name"] == "lifetxt" and component["version"] == candidate["version"],
        "SBOM identity mismatch",
    )
    provenance = proof.load(payload / "provenance.json")
    proof.require(
        provenance["schema"] == "lifetxt-release-provenance-v1",
        "unsupported provenance",
    )
    proof.require(
        provenance["package"] == {"name": "lifetxt", "version": candidate["version"]},
        "provenance package mismatch",
    )
    proof.require(
        provenance["source"]["commit"] == candidate["source_sha"],
        "provenance source mismatch",
    )
    proof.require(
        provenance["workflow_run"] == str(candidate["run_id"]),
        "provenance run mismatch",
    )
    expected_rows = sorted(
        [
            {
                "file": path.name,
                "sha256": proof.file_digest(path),
                "bytes": path.stat().st_size,
            }
            for path in packages
        ],
        key=lambda row: row["file"],
    )
    proof.require(
        provenance["artifacts"] == expected_rows, "provenance artifact hashes mismatch"
    )
    return wheels[0], sdists[0]


def smoke_archive(archive, sample, expected_version):
    """Both module and console must resolve from the installed archive, not source."""
    with tempfile.TemporaryDirectory(prefix="lifetxt-core-install-") as temp:
        base = Path(temp)
        venv = base / "venv"
        scratch = base / "scratch"
        scratch.mkdir()
        run([sys.executable, "-m", "venv", str(venv)], scratch)
        bindir = venv / ("Scripts" if os.name == "nt" else "bin")
        python = bindir / ("python.exe" if os.name == "nt" else "python")
        console = bindir / ("lifetxt.exe" if os.name == "nt" else "lifetxt")
        env = {
            key: value
            for key, value in os.environ.items()
            if key not in ("PYTHONPATH", "PYTHONHOME")
        }
        env.setdefault("PIP_DEFAULT_TIMEOUT", "30")
        env.setdefault("PIP_RETRIES", "2")
        run(
            [
                str(python),
                "-I",
                "-m",
                "pip",
                "--disable-pip-version-check",
                "install",
                "--no-deps",
                str(archive),
            ],
            scratch,
            env,
        )
        installed = run(
            [str(python), "-I", "-c", "import lifetxt; print(lifetxt.__file__)"],
            scratch,
            env,
        )
        proof.require(
            Path(installed).resolve().is_relative_to(venv.resolve()),
            "smoke imported source instead of installed package",
        )
        for command in ([str(python), "-I", "-m", "lifetxt"], [str(console)]):
            actual = run([*command, "--version"], scratch, env)
            proof.require(
                actual == "lifetxt " + expected_version,
                "installed CLI version mismatch",
            )
            run([*command, "--help"], scratch, env)
            run([*command, "check", str(sample)], scratch, env)


def build(candidate, controller, source, payload, report, context):
    controller, source, payload, report = map(
        lambda path: Path(path).resolve(), (controller, source, payload, report)
    )
    validate_context(candidate, controller, context)
    validate_source(candidate, source)
    proof.require(
        not payload.exists() and not report.exists(), "build outputs must be fresh"
    )
    # Keep incidental checksums/logs separate from the four-role Core payload.
    samples = [
        "examples/minimal_life.txt",
        "examples/status_presence.txt",
        "examples/messages_life.txt",
    ]
    run(
        [
            sys.executable,
            str(source / "scripts/check_release_policy.py"),
            "--root",
            str(source),
            *samples,
        ],
        source,
    )
    run(
        [
            sys.executable,
            "-m",
            "lifetxt",
            "safety",
            "release-gate",
            "--root",
            str(source),
            *samples,
        ],
        source,
    )
    with tempfile.TemporaryDirectory(prefix="lifetxt-core-evidence-") as temp:
        evidence = Path(temp) / "evidence"
        release_evidence.generate(source, evidence)
        # Select the exact proof-contract payload; SHA256SUMS is a build-local
        # intermediate, never a competing public canonical manifest.
        payload.mkdir(parents=True)
        for path in evidence.iterdir():
            if path.name != "SHA256SUMS":
                shutil.copyfile(path, payload / path.name)
    wheel, sdist = validate_evidence(candidate, payload)
    run([sys.executable, "-m", "twine", "check", str(wheel), str(sdist)], source)
    for archive in (wheel, sdist):
        smoke_archive(
            archive, source / "examples/minimal_life.txt", candidate["version"]
        )
    validate_source(candidate, source)
    validate_context(candidate, controller, context)
    files = [
        {
            "path": path.name,
            "role": "wheel"
            if path == wheel
            else "sdist"
            if path == sdist
            else "sbom"
            if path.name == "sbom.cdx.json"
            else "provenance",
        }
        for path in sorted(payload.iterdir())
    ]
    report_data = proof.sealed(
        {
            "schema_version": 1,
            "candidate_digest": candidate["digest"],
            "source_sha": candidate["source_sha"],
            "controller_sha": candidate["controller_sha"],
            "run_id": candidate["run_id"],
            "run_attempt": candidate["run_attempt"],
            "observed_version": candidate["version"],
            "toolchain": {
                "python": platform.python_version(),
                "runner": platform.platform(),
                **{
                    name: importlib.metadata.version(name)
                    for name in ("build", "setuptools", "twine")
                },
            },
            "checks": {
                "metadata": "passed",
                "clean-install": "passed",
                "cli": "passed",
            },
            "files": [
                {
                    **item,
                    "sha256": proof.file_digest(payload / item["path"]),
                    "bytes": (payload / item["path"]).stat().st_size,
                }
                for item in files
            ],
        }
    )
    proof.write_new(report, report_data)
    return report_data


def finish(candidate, report, payload, artifact):
    """Only emit a component after upload and revalidation of the same bytes."""
    row = proof.unseal(
        report,
        {
            "schema_version",
            "candidate_digest",
            "source_sha",
            "controller_sha",
            "run_id",
            "run_attempt",
            "observed_version",
            "toolchain",
            "checks",
            "files",
        },
        "Core build report",
    )
    proof.require(
        type(row["schema_version"]) is int and row["schema_version"] == 1,
        "unsupported Core report schema",
    )
    for key in (
        "candidate_digest",
        "source_sha",
        "controller_sha",
        "run_id",
        "run_attempt",
    ):
        expected = candidate["digest"] if key == "candidate_digest" else candidate[key]
        proof.require(
            type(row[key]) is type(expected) and row[key] == expected,
            "Core build report identity mismatch",
        )
    wheel, sdist = validate_evidence(candidate, Path(payload))
    roles = {
        wheel.name: "wheel",
        sdist.name: "sdist",
        "sbom.cdx.json": "sbom",
        "provenance.json": "provenance",
    }
    proof.require(
        all(item["role"] == roles.get(item["path"]) for item in row["files"]),
        "Core report role mismatch",
    )
    spec = {
        "target": "core-any",
        "artifact": artifact,
        "observed_version": row["observed_version"],
        "toolchain": row["toolchain"],
        "checks": row["checks"],
        "oci_digest": None,
        "files": [
            {key: item[key] for key in ("path", "role")} for item in row["files"]
        ],
    }
    result = proof.component(candidate, spec, payload)
    proof.require(result["files"] == row["files"], "payload changed since build/smoke")
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    prepare = sub.add_parser("prepare")
    compile_cmd = sub.add_parser("build")
    finalize = sub.add_parser("component")
    for cmd in (prepare, compile_cmd, finalize):
        cmd.add_argument("--candidate", required=True, type=Path)
        cmd.add_argument("--controller", required=True, type=Path)
    for cmd in (compile_cmd, finalize):
        cmd.add_argument("--source", required=True, type=Path)
        cmd.add_argument("--payload", required=True, type=Path)
        cmd.add_argument("--report", required=True, type=Path)
    for cmd in (prepare, finalize):
        cmd.add_argument("--output", required=True, type=Path)
    for key in ("artifact-id", "artifact-name", "artifact-digest"):
        finalize.add_argument(
            "--" + key, required=True, type=int if key == "artifact-id" else str
        )
    args = parser.parse_args(argv)
    try:
        candidate = proof.load(args.candidate)
        validate_context(candidate, args.controller, os.environ)
        if args.command == "prepare":
            # Safe checkout output is fixed-format hex, never arbitrary input.
            with args.output.open("x", encoding="utf-8") as stream:
                stream.write("source_sha=" + candidate["source_sha"] + "\n")
        elif args.command == "build":
            build(
                candidate,
                args.controller,
                args.source,
                args.payload,
                args.report,
                os.environ,
            )
        else:
            validate_source(candidate, args.source)
            result = finish(
                candidate,
                proof.load(args.report),
                args.payload,
                {
                    "id": args.artifact_id,
                    "name": args.artifact_name,
                    "sha256": args.artifact_digest,
                },
            )
            proof.write_new(args.output, result)
    except (
        ValueError,
        OSError,
        TypeError,
        KeyError,
        subprocess.SubprocessError,
        zipfile.BadZipFile,
        tarfile.TarError,
    ) as exc:
        parser.exit(1, "Core preflight rejected: %s\n" % exc)
    return 0


if __name__ == "__main__":
    sys.exit(main())
