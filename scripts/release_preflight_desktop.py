"""Stage Desktop Core, build native bundles, and bind non-public evidence."""

import argparse
import importlib.metadata
import os
import platform
import plistlib
import shutil
import subprocess
import sys
from pathlib import Path

import release_preflight_core as core
import release_preflight_proof as proof
import release_preflight_standalone as standalone

TARGETS = {
    "desktop-windows-x86_64": ("standalone-windows-x86_64", (".msi", ".exe")),
    "desktop-macos-arm64": ("standalone-macos-arm64", (".dmg", ".app.tar.gz")),
    "desktop-linux-x86_64": ("standalone-linux-x86_64", (".deb", ".AppImage", ".rpm")),
}
STAGE_FIELDS = {
    "schema_version",
    "candidate_digest",
    "source_sha",
    "controller_sha",
    "run_id",
    "run_attempt",
    "target",
    "metadata",
    "runtime_sha256",
    "runtime_checks",
    "toolchain",
}
REPORT_FIELDS = STAGE_FIELDS | {"checks", "files", "installers", "not_verified"}
CONFIG = "desktop/src-tauri/tauri.conf.json"
NOT_VERIFIED = [
    "GUI install/upgrade/uninstall",
    "embedded runtime extraction from every installer format",
]


def validate_target(target):
    proof.require(target in TARGETS, "unsupported Desktop target")
    standalone.validate_host(TARGETS[target][0])


def identity(candidate, row, target):
    proof.validate_candidate(candidate)
    proof.require(
        type(row["schema_version"]) is int and row["schema_version"] == 1,
        "unsupported Desktop schema",
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
            "Desktop evidence identity mismatch",
        )
    proof.require(
        row["target"] == target and target in TARGETS, "Desktop target mismatch"
    )
    proof.fields(
        row["runtime_checks"], proof.CONTRACTS["standalone"][1], "runtime checks"
    )
    proof.require(
        all(value == "passed" for value in row["runtime_checks"].values()),
        "bundled Core smoke incomplete",
    )


def runtime_path(work, target):
    name = standalone.TARGETS[TARGETS[target][0]][2]
    return work / "desktop/src-tauri/resources/bin" / name


def validate_work(candidate, work, target):
    proof.require(
        core.git(work, "rev-parse", "HEAD") == candidate["source_sha"],
        "generated checkout SHA mismatch",
    )
    changed = set(core.git(work, "diff", "HEAD", "--name-only").splitlines())
    proof.require(
        changed <= {CONFIG}, "unexpected tracked changes in generated checkout"
    )
    config = proof.load(work / CONFIG)
    proof.require(
        config["version"] == candidate["metadata_version"],
        "Desktop mapped version mismatch",
    )
    proof.require(
        config["bundle"]["resources"] == {"resources/bin/*": "bin/"},
        "Desktop resource mapping mismatch",
    )
    mac = config["bundle"]["macOS"]
    base = ".".join(map(str, candidate["version_parts"][:3]))
    proof.require(
        mac["bundleVersion"] == base and mac["infoPlist"] == ".release-version.plist",
        "Desktop Apple metadata mismatch",
    )
    with (work / "desktop/src-tauri/.release-version.plist").open("rb") as stream:
        metadata = plistlib.load(stream)
    proof.require(
        metadata.get("LifetxtReleaseVersion") == candidate["version"]
        and metadata.get("CFBundleVersion") == base
        and metadata.get("CFBundleShortVersionString") == base,
        "Desktop precise release identity mismatch",
    )
    runtime = runtime_path(work, target)
    proof.payload_path(runtime.parent, runtime.name)
    proof.require(
        {path.name for path in runtime.parent.iterdir()} <= {runtime.name, ".gitkeep"},
        "unexpected bundled runtime resources",
    )
    return {
        "release_version": candidate["version"],
        "mapped_version": config["version"],
        "resource_mapping": config["bundle"]["resources"],
        "apple_version": base,
    }


def stage(candidate, controller, source, work, output, target, context):
    controller, source, work, output = [
        Path(path).resolve() for path in (controller, source, work, output)
    ]
    core.validate_context(candidate, controller, context)
    core.validate_source(candidate, source)
    validate_target(target)
    proof.require(
        not work.exists() and not output.exists(), "Desktop stage outputs must be fresh"
    )
    core.run(
        ["git", "clone", "--shared", "--no-checkout", str(source), str(work)], source
    )
    core.run(["git", "checkout", "--detach", candidate["source_sha"]], work)
    core.validate_source(candidate, work)
    core.run(
        [
            sys.executable,
            str(work / "packaging/tauri-desktop/prepare_bundled_runtime.py"),
        ],
        work,
    )
    runtime_checks = standalone.smoke(
        runtime_path(work, target),
        work / "examples/minimal_life.txt",
        candidate["version"],
    )
    core.validate_source(candidate, work)
    core.run(
        [
            sys.executable,
            str(work / "scripts/set_tauri_desktop_version.py"),
            "--version",
            candidate["version"],
        ],
        work,
    )
    metadata = validate_work(candidate, work, target)
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
            "metadata": metadata,
            "runtime_sha256": proof.file_digest(runtime_path(work, target)),
            "runtime_checks": runtime_checks,
            "toolchain": {
                "python": platform.python_version(),
                "runner": platform.platform(),
                "pyinstaller": importlib.metadata.version("pyinstaller"),
            },
        }
    )
    proof.write_new(output, result)
    return result


def public_name(name):
    proof.require(
        isinstance(name, str)
        and name not in ("", ".", "..")
        and name[-1:] not in (" ", ".")
        and not any(
            char in "/\\" or ord(char) < 32 or ord(char) == 127 for char in name
        ),
        "unsafe public installer name",
    )


def installer_format(path, target):
    suffix = next(
        (suffix for suffix in TARGETS[target][1] if path.name.endswith(suffix)), None
    )
    proof.require(
        suffix is not None
        and path.is_file()
        and not path.is_symlink()
        and path.stat().st_size > 0,
        "invalid native installer",
    )
    with path.open("rb") as stream:
        head = stream.read(8)
        if suffix == ".dmg":
            proof.require(path.stat().st_size >= 512, "truncated DMG")
            stream.seek(-512, 2)
            valid = stream.read(4) == b"koly"
        else:
            magic = {
                ".msi": b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1",
                ".exe": b"MZ",
                ".deb": b"!<arch>\n",
                ".AppImage": b"\x7fELF",
                ".rpm": b"\xed\xab\xee\xdb",
                ".app.tar.gz": b"\x1f\x8b",
            }[suffix]
            valid = head.startswith(magic)
    proof.require(valid, "installer format signature mismatch")
    return suffix


def collect(work, payload, target):
    proof.require(not payload.exists(), "Desktop payload must be fresh")
    bundle = work / "desktop/src-tauri/target/release/bundle"
    found = sorted(
        path
        for path in bundle.rglob("*")
        if path.is_file() and any(path.name.endswith(ext) for ext in TARGETS[target][1])
    )
    proof.require(bool(found), "no Desktop installer artifacts")
    seen, rows = set(), []
    payload.mkdir(parents=True)
    for index, path in enumerate(found, start=1):
        public_name(path.name)
        proof.require(
            path.name.casefold() not in seen, "duplicate public installer name"
        )
        seen.add(path.name.casefold())
        suffix = installer_format(path, target)
        alias = "installer-%03d%s" % (index, suffix)
        shutil.copyfile(path, payload / alias)
        rows.append({"path": alias, "public_name": path.name, "format": suffix})
    alias = (
        "bundled-core.exe" if target.startswith("desktop-windows-") else "bundled-core"
    )
    shutil.copy2(runtime_path(work, target), payload / alias)
    return rows


def validate_payload(candidate, row, payload, target):
    identity(candidate, row, target)
    proof.require(
        row["not_verified"] == NOT_VERIFIED,
        "Desktop manual verification state mismatch",
    )
    proof.require(
        row["metadata"]
        == {
            "release_version": candidate["version"],
            "mapped_version": candidate["metadata_version"],
            "resource_mapping": {"resources/bin/*": "bin/"},
            "apple_version": ".".join(map(str, candidate["version_parts"][:3])),
        },
        "Desktop bundle metadata mismatch",
    )
    installers, names, paths = row["installers"], set(), set()
    proof.require(
        type(installers) is list and bool(installers), "missing installer inventory"
    )
    for item in installers:
        proof.fields(item, {"path", "public_name", "format"}, "installer mapping")
        public_name(item["public_name"])
        proof.require(
            item["public_name"].casefold() not in names and item["path"] not in paths,
            "duplicate installer mapping",
        )
        names.add(item["public_name"].casefold())
        paths.add(item["path"])
        path = proof.payload_path(payload, item["path"])
        proof.require(
            installer_format(path, target) == item["format"]
            and item["public_name"].endswith(item["format"]),
            "installer mapping format mismatch",
        )
    runtime = (
        "bundled-core.exe" if target.startswith("desktop-windows-") else "bundled-core"
    )
    proof.require(
        runtime not in paths
        and {path.name for path in payload.iterdir()} == paths | {runtime},
        "Desktop payload inventory mismatch",
    )
    proof.payload_path(payload, runtime)
    proof.require(
        proof.file_digest(payload / runtime) == row["runtime_sha256"],
        "bundled Core changed since smoke",
    )
    return runtime, paths


def bundle(
    candidate, stage_report, controller, source, work, payload, output, target, context
):
    controller, source, work, payload, output = [
        Path(path).resolve() for path in (controller, source, work, payload, output)
    ]
    row = proof.unseal(stage_report, STAGE_FIELDS, "Desktop stage")
    identity(candidate, row, target)
    core.validate_context(candidate, controller, context)
    core.validate_source(candidate, source)
    validate_target(target)
    proof.require(
        not payload.exists() and not output.exists(),
        "Desktop bundle outputs must be fresh",
    )
    proof.require(
        validate_work(candidate, work, target) == row["metadata"]
        and proof.file_digest(runtime_path(work, target)) == row["runtime_sha256"],
        "Desktop stage changed before bundle",
    )
    # A cold native Rust/Tauri build can exceed the shared 10-minute CLI bound.
    subprocess.run(
        ["cargo", "tauri", "build"],
        cwd=work / "desktop/src-tauri",
        check=True,
        timeout=1800,
    )
    proof.require(
        validate_work(candidate, work, target) == row["metadata"]
        and proof.file_digest(runtime_path(work, target)) == row["runtime_sha256"],
        "Desktop stage changed during bundle",
    )
    installers = collect(work, payload, target)
    runtime = (
        "bundled-core.exe" if target.startswith("desktop-windows-") else "bundled-core"
    )
    result = {
        **row,
        "checks": {"version": "passed", "bundle": "passed", "bundled-core": "passed"},
        "installers": installers,
        "files": [
            {
                "path": path.name,
                "role": "bundled-core" if path.name == runtime else "installer",
                "sha256": proof.file_digest(path),
                "bytes": path.stat().st_size,
            }
            for path in sorted(payload.iterdir())
        ],
        "not_verified": list(NOT_VERIFIED),
    }
    result["toolchain"] = {
        **row["toolchain"],
        **{
            tool: core.run([*tool.split(), "--version"], work)
            for tool in ("cargo", "rustc", "cargo tauri")
        },
    }
    validate_payload(candidate, result, payload, target)
    core.validate_source(candidate, source)
    core.validate_context(candidate, controller, context)
    result = proof.sealed(result)
    proof.write_new(output, result)
    return result


def finish(candidate, report, payload, artifact, target):
    row = proof.unseal(report, REPORT_FIELDS, "Desktop bundle report")
    runtime, installers = validate_payload(candidate, row, Path(payload), target)
    roles = {runtime: "bundled-core", **dict.fromkeys(installers, "installer")}
    proof.require(
        all(item["role"] == roles.get(item["path"]) for item in row["files"]),
        "Desktop report role mismatch",
    )
    spec = {
        "target": target,
        "artifact": artifact,
        "observed_version": candidate["version"],
        "toolchain": row["toolchain"],
        "checks": row["checks"],
        "oci_digest": None,
        "files": [
            {key: item[key] for key in ("path", "role")} for item in row["files"]
        ],
    }
    result = proof.component(candidate, spec, payload)
    proof.require(
        result["files"] == row["files"], "Desktop payload changed since bundle"
    )
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("stage", "bundle", "component"):
        cmd = sub.add_parser(name)
        for key in ("candidate", "controller", "source", "output"):
            cmd.add_argument("--" + key, required=True, type=Path)
        cmd.add_argument("--target", required=True, choices=TARGETS)
        if name != "component":
            cmd.add_argument("--work", required=True, type=Path)
        if name != "stage":
            cmd.add_argument("--report", required=True, type=Path)
            cmd.add_argument("--payload", required=True, type=Path)
        if name == "component":
            for key in ("artifact-id", "artifact-name", "artifact-digest"):
                cmd.add_argument(
                    "--" + key, required=True, type=int if key == "artifact-id" else str
                )
    args = parser.parse_args(argv)
    try:
        candidate = proof.load(args.candidate)
        if args.command == "stage":
            stage(
                candidate,
                args.controller,
                args.source,
                args.work,
                args.output,
                args.target,
                os.environ,
            )
        elif args.command == "bundle":
            bundle(
                candidate,
                proof.load(args.report),
                args.controller,
                args.source,
                args.work,
                args.payload,
                args.output,
                args.target,
                os.environ,
            )
        else:
            core.validate_context(candidate, args.controller, os.environ)
            core.validate_source(candidate, args.source)
            validate_target(args.target)
            result = finish(
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
            proof.write_new(args.output, result)
    except (
        ValueError,
        OSError,
        TypeError,
        KeyError,
        subprocess.SubprocessError,
        plistlib.InvalidFileException,
    ) as exc:
        parser.exit(1, "Desktop preflight rejected: %s\n" % exc)
    return 0


if __name__ == "__main__":
    sys.exit(main())
