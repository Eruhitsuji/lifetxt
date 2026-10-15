"""Offline preflight evidence contract. Never grants publication authority."""

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path, PurePosixPath

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lifetxt.versioning import canonical_release, release_parts, semver_metadata

SCHEMA_VERSION = 1
TARGETS = (
    "core-any",
    "standalone-windows-x86_64",
    "standalone-linux-x86_64",
    "standalone-linux-arm64",
    "standalone-macos-arm64",
    "standalone-macos-x86_64",
    "desktop-windows-x86_64",
    "desktop-macos-arm64",
    "desktop-linux-x86_64",
    "mini-linux-x86_64",
    "mini-linux-aarch64",
    "oci-linux-amd64",
    "oci-linux-arm64",
)
CONTRACTS = {
    "core": (
        {"wheel", "sdist", "sbom", "provenance"},
        {"metadata", "clean-install", "cli"},
    ),
    "standalone": (
        {"binary", "checksum"},
        {"version", "check", "init-doctor", "unicode-path", "timezone"},
    ),
    "desktop": ({"installer", "bundled-core"}, {"version", "bundle", "bundled-core"}),
    "mini": (
        {"binary", "checksum", "build-info", "notes"},
        {"version", "native", "static", "conformance", "cli"},
    ),
    "oci": ({"oci-layout"}, {"version", "native", "cli", "web", "non-root"}),
}
HEX = re.compile(r"[0-9a-f]{64}")
SHA = re.compile(r"[0-9a-f]{40}")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def text(value, label):
    require(isinstance(value, str) and bool(value.strip()), label + " is required")
    return value


def positive(value, label):
    require(type(value) is int and value > 0, label + " must be a positive integer")
    return value


def fields(value, expected, label):
    require(
        type(value) is dict and set(value) == set(expected),
        label + " has invalid fields",
    )


def digest(value):
    """Hash deterministic UTF-8 JSON, excluding no fields implicitly."""
    return hashlib.sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


def sealed(value):
    return {**value, "digest": digest(value)}


def unseal(value, expected, label):
    fields(value, {*expected, "digest"}, label)
    payload = {key: item for key, item in value.items() if key != "digest"}
    require(value["digest"] == digest(payload), label + " digest mismatch")
    return payload


def candidate(repository, version, source_sha, controller_sha, run_id, run_attempt):
    """Canonical version equivalence also applies to manually specified N=0."""
    result = sealed(
        {
            "schema_version": SCHEMA_VERSION,
            "repository": repository,
            "version": canonical_release(version),
            "tag": "v" + canonical_release(version),
            "version_parts": list(release_parts(version)),
            "metadata_version": semver_metadata(version),
            "source_sha": source_sha,
            "controller_sha": controller_sha,
            "run_id": run_id,
            "run_attempt": run_attempt,
            "targets": list(TARGETS),
        }
    )
    validate_candidate(result)
    return result


CANDIDATE_FIELDS = {
    "schema_version",
    "repository",
    "version",
    "tag",
    "version_parts",
    "metadata_version",
    "source_sha",
    "controller_sha",
    "run_id",
    "run_attempt",
    "targets",
}


def validate_candidate(value):
    row = unseal(value, CANDIDATE_FIELDS, "candidate")
    require(
        type(row["schema_version"]) is int and row["schema_version"] == SCHEMA_VERSION,
        "unsupported schema",
    )
    require(
        isinstance(row["repository"], str)
        and re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", row["repository"]),
        "invalid repository",
    )
    for key in ("source_sha", "controller_sha"):
        require(isinstance(row[key], str) and SHA.fullmatch(row[key]), "invalid " + key)
    for key in ("run_id", "run_attempt"):
        positive(row[key], key)
    version = canonical_release(row["version"])
    require(
        row["version"] == version and row["tag"] == "v" + version,
        "noncanonical version/tag",
    )
    require(
        row["version_parts"] == list(release_parts(version))
        and all(type(n) is int for n in row["version_parts"]),
        "version parts mismatch",
    )
    require(
        row["metadata_version"] == semver_metadata(version), "metadata version mismatch"
    )
    require(row["targets"] == list(TARGETS), "required target set mismatch")


def payload_path(root, relative):
    """Reject portable path aliases, traversal, and every symlink component."""
    text(relative, "payload path")
    path = PurePosixPath(relative)
    require(
        not path.is_absolute() and relative == path.as_posix(),
        "noncanonical payload path",
    )
    require(
        not any(
            part in ("", ".", "..")
            or not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.+-]*", part)
            or part.endswith(".")
            or re.fullmatch(
                r"(?:CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])",
                part.split(".")[0],
                re.IGNORECASE,
            )
            for part in relative.split("/")
        ),
        "unsafe payload path",
    )
    root = Path(root)
    require(root.is_dir() and not root.is_symlink(), "invalid payload root")
    current = root
    for part in path.parts:
        current = current / part
        require(not current.is_symlink(), "symlink payload is forbidden")
    require(current.is_file(), "missing or non-file payload: " + relative)
    return current


def file_digest(path):
    hasher = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def artifact_reference(value):
    fields(value, {"id", "name", "sha256"}, "artifact")
    positive(value["id"], "artifact id")
    text(value["name"], "artifact name")
    require(
        isinstance(value["sha256"], str) and HEX.fullmatch(value["sha256"]),
        "invalid artifact digest",
    )


def contract(target):
    require(isinstance(target, str) and target in TARGETS, "unexpected target")
    return CONTRACTS[target.split("-", 1)[0]]


def component(value, spec, root):
    """Bind an uploaded artifact reference and producer reports to actual files.

    Producer test/toolchain reports are assertions, not independently executed
    by this helper. A trusted controller must supply/verify the job receipts.
    """
    validate_candidate(value)
    fields(
        spec,
        {
            "target",
            "artifact",
            "observed_version",
            "toolchain",
            "checks",
            "files",
            "oci_digest",
        },
        "component spec",
    )
    rows = []
    require(type(spec["files"]) is list, "files must be a list")
    for item in spec["files"]:
        fields(item, {"path", "role"}, "file spec")
        path = payload_path(root, item["path"])
        rows.append({**item, "sha256": file_digest(path), "bytes": path.stat().st_size})
    result = sealed(
        {
            "schema_version": SCHEMA_VERSION,
            "candidate_digest": value["digest"],
            "source_sha": value["source_sha"],
            "controller_sha": value["controller_sha"],
            "run_id": value["run_id"],
            "run_attempt": value["run_attempt"],
            **{key: item for key, item in spec.items() if key != "files"},
            "files": sorted(rows, key=lambda row: row["path"]),
        }
    )
    validate_component(value, result, root)
    return result


COMPONENT_FIELDS = {
    "schema_version",
    "candidate_digest",
    "source_sha",
    "controller_sha",
    "run_id",
    "run_attempt",
    "target",
    "artifact",
    "observed_version",
    "toolchain",
    "checks",
    "files",
    "oci_digest",
}


def validate_component(value, proof, root):
    validate_candidate(value)
    row = unseal(proof, COMPONENT_FIELDS, "component")
    for key in (
        "schema_version",
        "source_sha",
        "controller_sha",
        "run_id",
        "run_attempt",
    ):
        require(
            type(row[key]) is type(value[key]) and row[key] == value[key],
            "component " + key + " mismatch",
        )
    require(row["candidate_digest"] == value["digest"], "component candidate mismatch")
    roles, checks = contract(row["target"])
    artifact_reference(row["artifact"])
    require(row["observed_version"] == value["version"], "observed version mismatch")
    require(
        type(row["toolchain"]) is dict and bool(row["toolchain"]), "missing toolchain"
    )
    for key, item in row["toolchain"].items():
        text(key, "toolchain key")
        text(item, "toolchain version")
    fields(row["checks"], checks, "checks")
    require(
        all(result == "passed" for result in row["checks"].values()),
        "required smoke did not pass",
    )
    if row["target"].startswith("oci-"):
        require(
            isinstance(row["oci_digest"], str)
            and re.fullmatch(r"sha256:[0-9a-f]{64}", row["oci_digest"]),
            "missing OCI digest",
        )
    else:
        require(row["oci_digest"] is None, "unexpected OCI digest")
    require(type(row["files"]) is list and bool(row["files"]), "missing payload files")
    seen, observed_roles = set(), []
    for item in row["files"]:
        fields(item, {"path", "role", "sha256", "bytes"}, "payload")
        path = payload_path(root, item["path"])
        name = item["path"].casefold()
        require(name not in seen, "duplicate payload path")
        seen.add(name)
        require(
            isinstance(item["role"], str) and item["role"] in roles,
            "unexpected payload role",
        )
        observed_roles.append(item["role"])
        positive(item["bytes"], "payload bytes")
        require(
            isinstance(item["sha256"], str) and HEX.fullmatch(item["sha256"]),
            "invalid payload digest",
        )
        require(
            path.stat().st_size == item["bytes"]
            and file_digest(path) == item["sha256"],
            "payload bytes/digest mismatch",
        )
    require(set(observed_roles) == roles, "missing required payload role")
    # Desktop can produce several installer formats; all other roles are unique.
    require(
        all(observed_roles.count(role) == 1 for role in roles if role != "installer"),
        "duplicate payload role",
    )
    actual = set()
    for path in Path(root).rglob("*"):
        require(not path.is_symlink(), "symlink payload is forbidden")
        if path.is_dir():
            continue
        require(path.is_file(), "non-file payload")
        name = path.relative_to(root).as_posix().casefold()
        require(name not in actual, "case alias in payload directory")
        actual.add(name)
    require(actual == seen, "unexpected or unlisted payload files")


def aggregate(value, proofs, root):
    """Each component's files live under root/<target>/, never merged by name."""
    validate_candidate(value)
    targets, artifacts, artifact_names = set(), set(), set()
    for proof in proofs:
        target = proof.get("target") if type(proof) is dict else None
        contract(target)
        require(target not in targets, "duplicate target")
        validate_component(value, proof, Path(root) / target)
        artifact = proof["artifact"]
        require(artifact["id"] not in artifacts, "duplicate artifact id")
        require(artifact["name"] not in artifact_names, "duplicate artifact name")
        artifacts.add(artifact["id"])
        artifact_names.add(artifact["name"])
        targets.add(target)
    require(targets == set(TARGETS), "missing required targets")
    return sealed(
        {
            "schema_version": SCHEMA_VERSION,
            "candidate": value,
            "components": sorted(proofs, key=lambda proof: proof["target"]),
            "status": "preflight_verified",
            "publication_authorized": False,
        }
    )


def no_duplicate_keys(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "duplicate JSON key: " + key)
        result[key] = value
    return result


def load(path):
    with Path(path).open(encoding="utf-8") as stream:
        return json.load(stream, object_pairs_hook=no_duplicate_keys)


def write_new(path, value):
    # A failed command must not silently reuse a stale success file.
    with Path(path).open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(
            value, stream, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False
        )
        stream.write("\n")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    create = sub.add_parser("candidate")
    for option in ("repository", "version", "source-sha", "controller-sha"):
        create.add_argument("--" + option, required=True)
    for option in ("run-id", "run-attempt"):
        create.add_argument("--" + option, required=True, type=int)
    build = sub.add_parser("component")
    combine = sub.add_parser("aggregate")
    for command in (build, combine):
        command.add_argument("--candidate", required=True)
        command.add_argument("--root", required=True)
    build.add_argument("--spec", required=True)
    combine.add_argument("--component", action="append", required=True)
    for command in (create, build, combine):
        command.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    try:
        require(
            not Path(args.output).exists() and not Path(args.output).is_symlink(),
            "output already exists; choose a fresh output path",
        )
        if args.command == "candidate":
            result = candidate(
                args.repository,
                args.version,
                args.source_sha,
                args.controller_sha,
                args.run_id,
                args.run_attempt,
            )
        elif args.command == "component":
            result = component(load(args.candidate), load(args.spec), args.root)
        else:
            result = aggregate(
                load(args.candidate), [load(path) for path in args.component], args.root
            )
        write_new(args.output, result)
    except (ValueError, OSError, TypeError, KeyError) as exc:
        parser.exit(1, "preflight proof rejected: %s\n" % exc)
    return 0


if __name__ == "__main__":
    sys.exit(main())
