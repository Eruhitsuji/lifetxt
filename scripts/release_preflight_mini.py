"""Non-public Mini native/static/conformance producer and payload evidence."""

import argparse
import os
import shutil
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

import release_preflight_core as core
import release_preflight_proof as proof
import release_preflight_standalone as standalone

TARGETS = {
    "mini-linux-x86_64": ("x86_64-unknown-linux-musl", "x86_64", 62),
    "mini-linux-aarch64": ("aarch64-unknown-linux-musl", "arm64", 183),
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
    "static_elf",
    "files",
}


def validate_target(target):
    proof.require(target in TARGETS, "unsupported Mini target")
    standalone.validate_host("standalone-linux-" + TARGETS[target][1])


def static_elf(binary, target):
    """Validate ELF64/arch and reject load-time dynamic linking, without ldd.

    ELF gABI constants: PT_LOAD=1, PT_DYNAMIC=2, PT_INTERP=3,
    DT_NULL=0 and DT_NEEDED=1. This is not a code/sandbox safety claim.
    """
    proof.require(target in TARGETS, "unsupported Mini target")
    size = binary.stat().st_size
    with binary.open("rb") as stream:
        header = stream.read(64)
        proof.require(
            len(header) == 64 and header[:7] == b"\x7fELF\x02\x01\x01",
            "expected little-endian ELF64",
        )
        values = struct.unpack("<HHIQQQIHHHHHH", header[16:])
        kind, machine, version = values[:3]
        phoff, ehsize, phsize, count = values[4], values[7], values[8], values[9]
        proof.require(
            kind in (2, 3) and machine == TARGETS[target][2] and version == 1,
            "ELF executable/architecture mismatch",
        )
        proof.require(
            ehsize == 64
            and phsize == 56
            and 0 < count < 65535
            and phoff >= 64
            and phoff + count * phsize <= size,
            "invalid ELF program-header bounds",
        )
        load = False
        for index in range(count):
            stream.seek(phoff + index * phsize)
            segment = struct.unpack("<IIQQQQQQ", stream.read(phsize))
            segment_type, offset, length = segment[0], segment[2], segment[5]
            proof.require(offset + length <= size, "ELF segment outside file")
            proof.require(segment_type != 3, "dynamic ELF interpreter is forbidden")
            load |= segment_type == 1
            if segment_type == 2:
                proof.require(
                    length > 0 and length % 16 == 0, "invalid ELF dynamic table"
                )
                stream.seek(offset)
                terminated = False
                for _ in range(length // 16):
                    tag, _ = struct.unpack("<qQ", stream.read(16))
                    proof.require(
                        tag not in (1, 0x7FFFFFFD, 0x7FFFFFFF),
                        "dynamic ELF library dependency is forbidden",
                    )
                    if tag == 0:
                        terminated = True
                        break
                proof.require(terminated, "unterminated ELF dynamic table")
        proof.require(load, "ELF has no load segment")
    return {
        "format": "ELF64-LE",
        "machine": machine,
        "interpreter": False,
        "needed_libraries": [],
    }


def notes(candidate):
    # Byte-identical on both arches: a single existing public RELEASE-NOTES.md.
    return "\n".join(
        [
            "lifetxt-mini " + candidate["tag"],
            "Python-free strict-subset Mini Runtime Profile",
            "Official targets: Linux x86_64 and AArch64",
            "Verify: sha256sum -c SHA256SUMS",
            "",
        ]
    )


def names(candidate, target):
    arch = TARGETS[target][0].split("-", 1)[0]
    binary = "lifetxt-mini-%s-linux-%s" % (candidate["tag"], arch)
    return {
        binary: "binary",
        binary + ".sha256": "checksum",
        binary + ".build-info": "build-info",
        "RELEASE-NOTES.md": "notes",
    }


def validate_payload(candidate, payload, target):
    proof.validate_candidate(candidate)
    proof.require(target in TARGETS, "unsupported Mini target")
    expected = names(candidate, target)
    proof.require(
        {path.name for path in payload.iterdir()} == set(expected),
        "Mini payload inventory mismatch",
    )
    for name in expected:
        path = proof.payload_path(payload, name)
        proof.require(path.stat().st_size > 0, "empty Mini payload")
    binary = payload / next(name for name, role in expected.items() if role == "binary")
    proof.require(
        (payload / (binary.name + ".sha256")).read_bytes()
        == standalone.checksum(binary).encode("ascii"),
        "Mini checksum mismatch (expected LF)",
    )
    proof.require(
        (payload / "RELEASE-NOTES.md").read_bytes() == notes(candidate).encode("utf-8"),
        "Mini notes identity mismatch",
    )
    return static_elf(binary, target)


def smoke(binary, source, candidate):
    env = {
        key: value
        for key, value in os.environ.items()
        if key not in ("PYTHONHOME", "PYTHONPATH")
    }
    # The existing conformance script invokes `python`; bind that to this
    # supported interpreter rather than another Python found later on PATH.
    env["PATH"] = str(Path(sys.executable).parent) + os.pathsep + env.get("PATH", "")
    python_alias = shutil.which("python", path=env["PATH"])
    proof.require(
        python_alias is not None
        and Path(python_alias).resolve() == Path(sys.executable).resolve(),
        "conformance python alias does not match supported interpreter",
    )
    with tempfile.TemporaryDirectory(prefix="lifetxt-mini-smoke-") as temp:
        cwd = Path(temp)
        actual = core.run([str(binary), "--version"], cwd, env)
        proof.require(
            actual == "lifetxt-mini " + candidate["version"],
            "Mini runtime version mismatch",
        )
        core.run(
            [
                sys.executable,
                str(source / "scripts/check_lifetxt_mini_version.py"),
                "--root",
                str(source),
                "--binary",
                str(binary),
                "--tag",
                candidate["tag"],
            ],
            cwd,
            env,
        )
        help_text = core.run([str(binary), "--help"], cwd, env)
        proof.require(
            "Mini Runtime Profile" in help_text,
            "Mini help lost runtime profile identity",
        )
        fixture = source / "lifetxt-mini/fixtures/mixed-life.txt"
        core.run([str(binary), "check", str(fixture)], cwd, env)
        core.run([str(binary), "today", "--date", "2026-09-24", str(fixture)], cwd, env)
        core.run(
            [
                sys.executable,
                str(source / "scripts/check_mini_core_conformance.py"),
                "--binary",
                str(binary),
            ],
            source,
            env,
        )


def build(candidate, controller, source, payload, output, target, context):
    controller, source, payload, output = [
        Path(path).resolve() for path in (controller, source, payload, output)
    ]
    core.validate_context(candidate, controller, context)
    core.validate_source(candidate, source)
    validate_target(target)
    proof.require(
        not payload.exists() and not output.exists(), "Mini outputs must be fresh"
    )
    crate = source / "lifetxt-mini"
    triple = TARGETS[target][0]
    core.run(
        [
            sys.executable,
            str(source / "scripts/check_lifetxt_mini_version.py"),
            "--root",
            str(source),
            "--tag",
            candidate["tag"],
        ],
        source,
    )
    with tempfile.TemporaryDirectory(prefix="lifetxt-mini-build-") as temp:
        build_root = Path(temp)
        core.run(
            ["cargo", "test", "--locked", "--target-dir", str(build_root / "tests")],
            crate,
        )
        core.run(
            [
                "cargo",
                "zigbuild",
                "--locked",
                "--release",
                "--target",
                triple,
                "--target-dir",
                str(build_root / "release"),
            ],
            crate,
        )
        built = build_root / "release" / triple / "release/lifetxt-mini"
        proof.payload_path(built.parent, built.name)
        static_elf(built, target)
        payload.mkdir(parents=True)
        binary = payload / next(
            name for name, role in names(candidate, target).items() if role == "binary"
        )
        shutil.copy2(built, binary)
    smoke(binary, source, candidate)
    rustc = core.run(["rustc", "-Vv"], source)
    (payload / (binary.name + ".sha256")).write_text(
        standalone.checksum(binary), encoding="ascii", newline="\n"
    )
    (payload / (binary.name + ".build-info")).write_text(
        rustc + "\n", encoding="utf-8", newline="\n"
    )
    (payload / "RELEASE-NOTES.md").write_text(
        notes(candidate), encoding="utf-8", newline="\n"
    )
    elf = validate_payload(candidate, payload, target)
    core.validate_source(candidate, source)
    core.validate_context(candidate, controller, context)
    toolchain = {
        "python": sys.version.split()[0],
        "rustc": rustc,
        "cargo": core.run(["cargo", "--version"], source),
        "cargo-zigbuild": core.run(["cargo", "zigbuild", "--version"], source),
        "zig": core.run(["zig", "version"], source),
    }
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
            "toolchain": toolchain,
            "checks": dict.fromkeys(proof.CONTRACTS["mini"][1], "passed"),
            "static_elf": elf,
            "files": [
                {
                    "path": path.name,
                    "role": names(candidate, target)[path.name],
                    "sha256": proof.file_digest(path),
                    "bytes": path.stat().st_size,
                }
                for path in sorted(payload.iterdir())
            ],
        }
    )
    proof.write_new(output, result)
    return result


def finish(candidate, report, payload, artifact, target):
    row = proof.unseal(report, REPORT_FIELDS, "Mini build report")
    proof.require(
        type(row["schema_version"]) is int and row["schema_version"] == 1,
        "unsupported Mini schema",
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
            "Mini report identity mismatch",
        )
    proof.require(row["target"] == target, "Mini report target mismatch")
    elf = validate_payload(candidate, Path(payload), target)
    proof.require(elf == row["static_elf"], "Mini ELF evidence mismatch")
    roles = names(candidate, target)
    proof.require(
        all(item["role"] == roles.get(item["path"]) for item in row["files"]),
        "Mini report role mismatch",
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
    result = proof.component(candidate, spec, payload)
    proof.require(result["files"] == row["files"], "Mini payload changed since smoke")
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("build", "component"):
        cmd = sub.add_parser(name)
        for key in ("candidate", "controller", "source", "payload", "output"):
            cmd.add_argument("--" + key, required=True, type=Path)
        cmd.add_argument("--target", choices=TARGETS, required=True)
        if name == "component":
            cmd.add_argument("--report", required=True, type=Path)
            for key in ("artifact-id", "artifact-name", "artifact-digest"):
                cmd.add_argument(
                    "--" + key, required=True, type=int if key == "artifact-id" else str
                )
    args = parser.parse_args(argv)
    try:
        candidate = proof.load(args.candidate)
        if args.command == "build":
            build(
                candidate,
                args.controller,
                args.source,
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
        struct.error,
        subprocess.SubprocessError,
    ) as exc:
        parser.exit(1, "Mini preflight rejected: %s\n" % exc)
    return 0


if __name__ == "__main__":
    sys.exit(main())
