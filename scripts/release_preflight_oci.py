"""Native OCI preflight: build once, import exact digest, smoke, retain layout."""

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

import release_preflight_core as core
import release_preflight_oci_layout as layout
import release_preflight_proof as proof
import release_preflight_standalone as standalone

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
    "oci",
    "files",
}


def validate_target(target):
    proof.require(target in layout.TARGETS, "unsupported OCI target")
    standalone.validate_host(
        "standalone-linux-"
        + {"amd64": "x86_64", "arm64": "arm64"}[layout.TARGETS[target]]
    )


def archive_name(candidate, target):
    return "lifetxt-%s-linux-%s.oci.tar" % (candidate["tag"], layout.TARGETS[target])


def validate_payload(payload, candidate, target):
    proof.require(target in layout.TARGETS, "unsupported OCI target")
    name = archive_name(candidate, target)
    proof.require(
        {p.name for p in payload.iterdir()} == {name}, "OCI payload inventory mismatch"
    )
    archive = proof.payload_path(payload, name)
    with tempfile.TemporaryDirectory(prefix="lifetxt-oci-validate-") as temporary:
        root = Path(temporary) / "image"
        layout.extract(archive, root)
        return layout.validate(root, candidate, target)


def files(payload):
    return [
        {
            "path": relative,
            "role": "oci-layout",
            "sha256": proof.file_digest(payload / relative),
            "bytes": (payload / relative).stat().st_size,
        }
        for relative in sorted(path.name for path in payload.iterdir())
    ]


def smoke(payload, graph, source, candidate):
    """Rootful local storage only; neither transport addresses a registry."""
    run = lambda command: core.run(command, source)  # noqa: E731
    tag = "localhost/lifetxt-preflight:%s-%s" % (
        candidate["run_id"],
        candidate["run_attempt"],
    )
    run(
        [
            "sudo",
            "skopeo",
            "copy",
            "--preserve-digests",
            "oci:" + str(payload),
            "containers-storage:" + tag,
        ]
    )
    inspected = json.loads(run(["sudo", "podman", "image", "inspect", tag]))
    proof.require(len(inspected) == 1, "OCI import inventory mismatch")
    image = inspected[0]
    image_id = image["Id"]
    if not image_id.startswith("sha256:"):
        image_id = "sha256:" + image_id
    proof.require(
        image.get("Digest") == graph["manifest_digest"]
        and image_id == graph["config_digest"],
        "OCI import changed manifest/config digest",
    )
    proof.require(
        image.get("Os") == "linux"
        and image.get("Architecture") == graph["platform"]["architecture"],
        "imported OCI platform mismatch",
    )
    base = ["sudo", "podman", "run", "--pull=never", "--rm", "--network=none"]
    actual = run([*base, image_id, "--version"])
    proof.require(
        actual == "lifetxt " + candidate["version"], "OCI runtime version mismatch"
    )
    help_text = run([*base, image_id, "--help"])
    proof.require(
        "check" in help_text and "serve" in help_text, "OCI CLI help mismatch"
    )
    uid = run([*base, "--entrypoint", "id", image_id, "-u"])
    proof.require(uid == "1000", "OCI runtime must use uid 1000")
    # No source mount: exercise the installed package with a tiny fresh fixture.
    with tempfile.TemporaryDirectory(prefix="lifetxt-oci-smoke-") as temporary:
        fixture = Path(temporary) / "life.txt"
        fixture.write_text("# Life\n", encoding="utf-8")
        fixture.chmod(0o644)
        Path(temporary).chmod(0o755)
        mount = str(fixture) + ":/data/life.txt:ro"
        run([*base, "-v", mount, image_id, "check", "/data/life.txt"])
        name = "lifetxt-preflight-%s-%s" % (
            candidate["run_id"],
            candidate["run_attempt"],
        )
        started = False
        try:
            run(
                [
                    "sudo",
                    "podman",
                    "run",
                    "--pull=never",
                    "-d",
                    "--name",
                    name,
                    "-p",
                    "127.0.0.1:18321:8000",
                    "-v",
                    mount,
                    image_id,
                    "serve",
                    "/data/life.txt",
                    "--host",
                    "0.0.0.0",
                    "--port",
                    "8000",
                    "--read-only",
                ]
            )
            started = True
            health()
        finally:
            if started:
                run(["sudo", "podman", "rm", "-f", name])


def health():
    # Explicitly bypass proxy variables for the loopback-only smoke endpoint.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    for attempt in range(30):
        try:
            with opener.open(
                "http://127.0.0.1:18321/api/health", timeout=2
            ) as response:
                result = json.load(response)
                proof.require(
                    response.status == 200
                    and result.get("ok") is True
                    and result.get("read_only") is True,
                    "OCI Web health mismatch",
                )
                return
        except (urllib.error.URLError, TimeoutError):
            if attempt == 29:
                raise
            time.sleep(1)


def build(candidate, controller, source, payload, output, target, context):
    controller, source, payload, output = [
        Path(path).resolve() for path in (controller, source, payload, output)
    ]
    core.validate_context(candidate, controller, context)
    core.validate_source(candidate, source)
    validate_target(target)
    proof.require(
        not payload.exists() and not output.exists(), "OCI outputs must be fresh"
    )
    with tempfile.TemporaryDirectory(prefix="lifetxt-oci-build-") as temporary:
        archive = Path(temporary) / "image.tar"
        core.run(
            [
                "docker",
                "buildx",
                "build",
                "--platform",
                "linux/" + layout.TARGETS[target],
                "--provenance=false",
                "--sbom=false",
                "--label",
                "org.opencontainers.image.version=" + candidate["version"],
                "--label",
                "org.opencontainers.image.revision=" + candidate["source_sha"],
                "--output",
                "type=oci,tar=true,oci-mediatypes=true,dest=" + str(archive),
                ".",
            ],
            source,
        )
        image = Path(temporary) / "image"
        layout.extract(archive, image)
        graph = layout.validate(image, candidate, target)
        archive_hash = proof.file_digest(archive)
        smoke(image, graph, source, candidate)
        proof.require(
            layout.validate(image, candidate, target) == graph
            and proof.file_digest(archive) == archive_hash,
            "OCI bytes changed during smoke",
        )
        payload.mkdir(parents=True)
        shutil.copyfile(archive, payload / archive_name(candidate, target))
    proof.require(
        validate_payload(payload, candidate, target) == graph,
        "OCI retained graph mismatch",
    )
    before = files(payload)
    core.validate_source(candidate, source)
    core.validate_context(candidate, controller, context)
    toolchain = {
        "python": sys.version.split()[0],
        "docker": core.run(["docker", "--version"], source),
        "buildx": core.run(["docker", "buildx", "version"], source),
        "skopeo": core.run(["skopeo", "--version"], source),
        "podman": core.run(["podman", "--version"], source),
    }
    report = proof.sealed(
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
            "checks": dict.fromkeys(proof.CONTRACTS["oci"][1], "passed"),
            "oci": graph,
            "files": before,
        }
    )
    proof.write_new(output, report)
    return report


def finish(candidate, report, payload, artifact, target):
    row = proof.unseal(report, REPORT_FIELDS, "OCI build report")
    proof.require(
        type(row["schema_version"]) is int and row["schema_version"] == 1,
        "unsupported OCI report schema",
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
            "OCI report identity mismatch",
        )
    proof.require(row["target"] == target, "OCI report target mismatch")
    graph = validate_payload(Path(payload), candidate, target)
    proof.require(
        row["oci"] == graph and row["files"] == files(Path(payload)),
        "OCI payload changed since smoke",
    )
    spec = {
        "target": target,
        "artifact": artifact,
        "observed_version": row["observed_version"],
        "toolchain": row["toolchain"],
        "checks": row["checks"],
        "oci_digest": graph["manifest_digest"],
        "files": [
            {key: item[key] for key in ("path", "role")} for item in row["files"]
        ],
    }
    return proof.component(candidate, spec, payload)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("build", "component"):
        cmd = sub.add_parser(name)
        for key in ("candidate", "controller", "source", "payload", "output"):
            cmd.add_argument("--" + key, required=True, type=Path)
        cmd.add_argument("--target", required=True, choices=layout.TARGETS)
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
            proof.write_new(
                args.output,
                finish(
                    candidate,
                    proof.load(args.report),
                    args.payload,
                    {
                        "id": args.artifact_id,
                        "name": args.artifact_name,
                        "sha256": args.artifact_digest,
                    },
                    args.target,
                ),
            )
    except (
        ValueError,
        OSError,
        TypeError,
        KeyError,
        AttributeError,
        subprocess.SubprocessError,
    ) as exc:
        parser.exit(1, "OCI preflight rejected: %s\n" % exc)
    return 0


if __name__ == "__main__":
    sys.exit(main())
