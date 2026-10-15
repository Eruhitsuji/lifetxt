"""Non-public native Standalone build, frozen smoke, and component evidence."""

import argparse
import importlib.metadata
import os
import platform
import shutil
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

import release_preflight_core as core
import release_preflight_proof as proof

# Preserve the existing supported matrix and binary names. Never cross-build.
TARGETS = {
    "standalone-windows-x86_64": (
        "Windows",
        "x86_64",
        "lifetxt.exe",
        "lifetxt-windows-x86_64.exe",
    ),
    "standalone-linux-x86_64": ("Linux", "x86_64", "lifetxt", "lifetxt-linux-x86_64"),
    "standalone-linux-arm64": ("Linux", "arm64", "lifetxt", "lifetxt-linux-arm64"),
    "standalone-macos-arm64": ("Darwin", "arm64", "lifetxt", "lifetxt-macos-arm64"),
    "standalone-macos-x86_64": ("Darwin", "x86_64", "lifetxt", "lifetxt-macos-x86_64"),
}
REPORT_FIELDS = {
    "schema_version",
    "candidate_digest",
    "source_sha",
    "controller_sha",
    "run_id",
    "run_attempt",
    "target",
    "observed_version",
    "toolchain",
    "checks",
    "files",
}


def validate_host(target):
    proof.require(target in TARGETS, "unsupported Standalone target")
    system, arch, _, _ = TARGETS[target]
    machine = platform.machine().lower()
    machine = {"amd64": "x86_64", "aarch64": "arm64"}.get(machine, machine)
    proof.require(
        platform.system() == system and machine == arch and struct.calcsize("P") == 8,
        "native host/architecture mismatch",
    )


def checksum(binary):
    return proof.file_digest(binary) + "  " + binary.name + "\n"


def validate_payload(target, payload):
    proof.require(target in TARGETS, "unsupported Standalone target")
    name = TARGETS[target][3]
    binary, sums = Path(payload) / name, Path(payload) / (name + ".sha256")
    proof.require(
        {path.name for path in Path(payload).iterdir()} == {name, sums.name},
        "Standalone payload inventory mismatch",
    )
    for path in (binary, sums):
        proof.payload_path(payload, path.name)
        proof.require(path.stat().st_size > 0, "empty Standalone payload")
    proof.require(
        sums.read_bytes() == checksum(binary).encode("ascii"),
        "Standalone checksum mismatch (expected LF)",
    )
    return binary, sums


def smoke(binary, sample, version):
    """Execute only the frozen artifact, outside source, with isolated homes."""
    with tempfile.TemporaryDirectory(prefix="lifetxt-frozen-smoke-") as temp:
        root = Path(temp)
        home = root / "home"
        home.mkdir()
        env = {
            key: value
            for key, value in os.environ.items()
            if key not in ("PYTHONHOME", "PYTHONPATH")
        }
        env.update(
            HOME=str(home),
            USERPROFILE=str(home),
            APPDATA=str(home / "appdata"),
            LOCALAPPDATA=str(home / "localappdata"),
            XDG_CONFIG_HOME=str(home / "config"),
            XDG_DATA_HOME=str(home / "data"),
            XDG_CACHE_HOME=str(home / "cache"),
        )

        def execute(args, cwd):
            return core.run([str(binary), *args], cwd, env)

        actual = execute(["--version"], root)
        proof.require(actual == "lifetxt " + version, "frozen binary version mismatch")
        execute(["check", str(sample)], root)
        scratch = root / "workspace"
        scratch.mkdir()
        execute(["init", "--yes"], scratch)
        execute(["doctor"], scratch)
        execute(["check", "life.txt"], scratch)
        unicode_dir = root / "space dir 日本語"
        unicode_dir.mkdir()
        execute(["init", "--yes"], unicode_dir)
        execute(["check", "life.txt"], unicode_dir)
        timezone = root / "timezone"
        timezone.mkdir()
        (timezone / "life.txt").write_text(
            "#!timezone: Asia/Tokyo\n[ ] T Sample_Task due:2026-09-01\n",
            encoding="utf-8",
            newline="\n",
        )
        execute(["check", "life.txt"], timezone)
        execute(["today", "life.txt"], timezone)
    return dict.fromkeys(proof.CONTRACTS["standalone"][1], "passed")


def build(candidate, controller, source, payload, report, target, context):
    controller, source, payload, report = [
        Path(path).resolve() for path in (controller, source, payload, report)
    ]
    core.validate_context(candidate, controller, context)
    core.validate_source(candidate, source)
    validate_host(target)
    proof.require(
        not payload.exists() and not report.exists(), "build outputs must be fresh"
    )
    with tempfile.TemporaryDirectory(prefix="lifetxt-frozen-build-") as temp:
        build_root = Path(temp)
        core.run(
            [
                sys.executable,
                "-m",
                "PyInstaller",
                str(source / "packaging/pyinstaller/lifetxt.spec"),
                "--distpath",
                str(build_root / "dist"),
                "--workpath",
                str(build_root / "work"),
                "--clean",
                "--noconfirm",
            ],
            source,
        )
        built = build_root / "dist" / TARGETS[target][2]
        proof.require(
            built.is_file() and not built.is_symlink(),
            "missing native frozen executable",
        )
        payload.mkdir(parents=True)
        binary = payload / TARGETS[target][3]
        shutil.copy2(built, binary)
    checks = smoke(binary, source / "examples/minimal_life.txt", candidate["version"])
    (payload / (binary.name + ".sha256")).write_text(
        checksum(binary), encoding="ascii", newline="\n"
    )
    binary, sums = validate_payload(target, payload)
    core.validate_source(candidate, source)
    core.validate_context(candidate, controller, context)
    result = proof.sealed(
        {
            "schema_version": 1,
            "candidate_digest": candidate["digest"],
            **{
                key: candidate[key]
                for key in ("source_sha", "controller_sha", "run_id", "run_attempt")
            },
            "target": target,
            "observed_version": candidate["version"],
            "toolchain": {
                "python": platform.python_version(),
                "runner": platform.platform(),
                "machine": platform.machine(),
                **{
                    name: importlib.metadata.version(name)
                    for name in (
                        "pyinstaller",
                        "fastapi",
                        "uvicorn",
                        "textual",
                        "watchdog",
                    )
                },
            },
            "checks": checks,
            "files": [
                {
                    "path": path.name,
                    "role": role,
                    "sha256": proof.file_digest(path),
                    "bytes": path.stat().st_size,
                }
                for path, role in ((binary, "binary"), (sums, "checksum"))
            ],
        }
    )
    proof.write_new(report, result)
    return result


def finish(candidate, report, payload, artifact, target):
    proof.validate_candidate(candidate)
    row = proof.unseal(report, REPORT_FIELDS, "Standalone build report")
    proof.require(
        type(row["schema_version"]) is int and row["schema_version"] == 1,
        "unsupported Standalone report schema",
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
            "Standalone report identity mismatch",
        )
    proof.require(row["target"] == target, "Standalone report target mismatch")
    binary, sums = validate_payload(target, payload)
    expected_roles = {binary.name: "binary", sums.name: "checksum"}
    proof.require(
        all(item["role"] == expected_roles.get(item["path"]) for item in row["files"]),
        "Standalone report role mismatch",
    )
    spec = {
        "target": target,
        "artifact": artifact,
        "observed_version": row["observed_version"],
        "toolchain": row["toolchain"],
        "checks": row["checks"],
        "oci_digest": None,
        "files": [
            {key: item[key] for key in ("path", "role")} for item in row["files"]
        ],
    }
    component = proof.component(candidate, spec, payload)
    proof.require(
        component["files"] == row["files"], "Standalone payload changed since smoke"
    )
    return component


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("build", "component"):
        cmd = sub.add_parser(name)
        for option in ("candidate", "controller", "source", "payload", "report"):
            cmd.add_argument("--" + option, required=True, type=Path)
        cmd.add_argument("--target", required=True, choices=TARGETS)
        if name == "component":
            cmd.add_argument("--output", required=True, type=Path)
            cmd.add_argument("--artifact-id", required=True, type=int)
            cmd.add_argument("--artifact-name", required=True)
            cmd.add_argument("--artifact-digest", required=True)
    args = parser.parse_args(argv)
    try:
        candidate = proof.load(args.candidate)
        if args.command == "build":
            build(
                candidate,
                args.controller,
                args.source,
                args.payload,
                args.report,
                args.target,
                os.environ,
            )
        else:
            core.validate_context(candidate, args.controller, os.environ)
            core.validate_source(candidate, args.source)
            validate_host(args.target)
            component = finish(
                candidate,
                proof.load(args.report),
                args.payload,
                {
                    "id": args.artifact_id,
                    "name": args.artifact_name,
                    "sha256": args.artifact_digest,
                },
                args.target,
            )
            proof.write_new(args.output, component)
    except (
        ValueError,
        OSError,
        TypeError,
        KeyError,
        subprocess.SubprocessError,
    ) as exc:
        parser.exit(1, "Standalone preflight rejected: %s\n" % exc)
    return 0


if __name__ == "__main__":
    sys.exit(main())
