"""Strict offline OCI graph validation and no-rebuild multiarch assembly."""

import hashlib
import json
import re
import shutil
import tarfile
from pathlib import Path

import release_preflight_proof as proof

INDEX = "application/vnd.oci.image.index.v1+json"
MANIFEST = "application/vnd.oci.image.manifest.v1+json"
CONFIG = "application/vnd.oci.image.config.v1+json"
LAYERS = {
    "application/vnd.oci.image.layer.v1.tar",
    "application/vnd.oci.image.layer.v1.tar+gzip",
}
BLOB = re.compile(r"blobs/sha256/[0-9a-f]{64}")
DIGEST = re.compile(r"sha256:[0-9a-f]{64}")
TARGETS = {"oci-linux-amd64": "amd64", "oci-linux-arm64": "arm64"}


def encode(value):
    return (
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode("utf-8")
        + b"\n"
    )


def inventory(root):
    proof.require(
        root.is_dir() and not root.is_symlink(), "OCI root must be a directory"
    )
    found = set()
    for path in root.rglob("*"):
        relative = path.relative_to(root).as_posix()
        proof.require(not path.is_symlink(), "OCI symlink forbidden")
        if path.is_dir():
            proof.require(
                relative in ("blobs", "blobs/sha256"), "unexpected OCI directory"
            )
        else:
            proof.payload_path(root, relative)
            proof.require(
                relative in ("index.json", "oci-layout") or BLOB.fullmatch(relative),
                "unexpected OCI file",
            )
            found.add(relative)
    return found


def extract(archive, root):
    """Never use extractall: reject links, aliases, traversal and sparse files."""
    proof.require(not root.exists(), "OCI output must be fresh")
    root.mkdir(parents=True)
    with tarfile.open(archive, "r:") as stream:
        seen, total = set(), 0
        for member in stream:
            name = member.name
            proof.require(
                name not in seen and len(seen) < 256, "duplicate/oversized OCI archive"
            )
            seen.add(name)
            if member.isdir():
                proof.require(
                    name.rstrip("/") in ("blobs", "blobs/sha256"),
                    "unexpected archive directory",
                )
                continue
            proof.require(
                member.isfile() and not member.sparse,
                "OCI archive links/sparse entries forbidden",
            )
            proof.require(
                name in ("index.json", "oci-layout") or BLOB.fullmatch(name),
                "unsafe OCI archive path",
            )
            total += member.size
            proof.require(
                0 <= member.size and total <= 8 * 1024**3, "OCI archive size limit"
            )
            destination = root / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            with stream.extractfile(member) as source, destination.open("xb") as output:
                shutil.copyfileobj(source, output)


def read_json(path):
    proof.require(path.stat().st_size <= 4 * 1024**2, "OCI JSON size limit")
    return proof.load(path)


def descriptor(root, row, media, referenced):
    proof.require(
        type(row) is dict and row.get("mediaType") in media, "OCI media type mismatch"
    )
    proof.require(
        not (set(row) - {"mediaType", "digest", "size", "annotations", "platform"}),
        "unsupported OCI descriptor fields",
    )
    digest = row.get("digest")
    proof.require(
        isinstance(digest, str) and DIGEST.fullmatch(digest),
        "OCI sha256 descriptor required",
    )
    proof.positive(row.get("size"), "OCI descriptor size")
    path = proof.payload_path(root, "blobs/sha256/" + digest[7:])
    proof.require(
        path.stat().st_size == row["size"] and proof.file_digest(path) == digest[7:],
        "OCI blob size/digest mismatch",
    )
    referenced.add(path.relative_to(root).as_posix())
    return path


def validate(root, candidate, target):
    proof.validate_candidate(candidate)
    proof.require(target in TARGETS, "unsupported OCI target")
    root = Path(root)
    files = inventory(root)
    proof.require(
        read_json(proof.payload_path(root, "oci-layout"))
        == {"imageLayoutVersion": "1.0.0"},
        "unsupported OCI layout",
    )
    index = read_json(proof.payload_path(root, "index.json"))
    proof.require(
        not (set(index) - {"schemaVersion", "mediaType", "manifests", "annotations"}),
        "unsupported OCI index fields",
    )
    proof.require(
        index.get("schemaVersion") == 2
        and index.get("mediaType") == INDEX
        and len(index.get("manifests", [])) == 1,
        "one OCI image required",
    )
    referenced = {"index.json", "oci-layout"}
    image = index["manifests"][0]
    manifest = read_json(descriptor(root, image, {MANIFEST}, referenced))
    proof.require(
        manifest.get("schemaVersion") == 2
        and manifest.get("mediaType") == MANIFEST
        and not (
            set(manifest)
            - {"schemaVersion", "mediaType", "config", "layers", "annotations"}
        ),
        "unsupported OCI manifest",
    )
    config = read_json(descriptor(root, manifest["config"], {CONFIG}, referenced))
    arch = TARGETS[target]
    platform = {"os": "linux", "architecture": arch}
    proof.require(
        config.get("os") == "linux" and config.get("architecture") == arch,
        "OCI architecture mismatch",
    )
    if "platform" in image:
        proof.require(
            image["platform"]
            in (
                platform,
                {**platform, "variant": "v8"} if arch == "arm64" else platform,
            ),
            "OCI descriptor platform mismatch",
        )
    settings = config["config"]
    proof.require(
        settings.get("User") in ("lifetxt", "1000", "1000:1000"),
        "OCI non-root user required",
    )
    proof.require(settings.get("Entrypoint") == ["lifetxt"], "OCI entrypoint mismatch")
    labels = settings["Labels"]
    proof.require(
        labels.get("org.opencontainers.image.version") == candidate["version"]
        and labels.get("org.opencontainers.image.revision") == candidate["source_sha"],
        "OCI version/revision mismatch",
    )
    layers = manifest["layers"]
    proof.require(
        isinstance(layers, list) and 0 < len(layers) <= 128, "OCI layers required"
    )
    for layer in layers:
        descriptor(root, layer, LAYERS, referenced)
    rootfs = config["rootfs"]
    proof.require(
        rootfs.get("type") == "layers"
        and len(rootfs.get("diff_ids", [])) == len(layers)
        and all(
            isinstance(item, str) and DIGEST.fullmatch(item)
            for item in rootfs["diff_ids"]
        ),
        "OCI rootfs mismatch",
    )
    proof.require(files == referenced, "OCI missing or unreferenced files")
    return {
        "manifest_digest": image["digest"],
        "config_digest": manifest["config"]["digest"],
        "index_digest": "sha256:" + proof.file_digest(root / "index.json"),
        "platform": platform,
        "descriptor": {
            "mediaType": MANIFEST,
            "digest": image["digest"],
            "size": image["size"],
            "platform": platform,
        },
    }


def assemble(candidate, layouts, output):
    """Caller must authenticate BOTH component proofs/API references first.

    Not publication authority. Input order cannot change the final index digest.
    Keep index.json bytes: publishing must preserve this digest with --all.
    """
    proof.require(set(layouts) == set(TARGETS), "both OCI targets required")
    graphs = {
        target: validate(Path(root), candidate, target)
        for target, root in layouts.items()
    }
    output = Path(output)
    proof.require(not output.exists(), "assembled OCI output must be fresh")
    output.mkdir(parents=True)
    for target in sorted(TARGETS):
        root = Path(layouts[target])
        for relative in sorted(inventory(root) - {"index.json", "oci-layout"}):
            destination = output / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            if not destination.exists():
                shutil.copyfile(root / relative, destination)
            proof.require(
                proof.file_digest(destination) == relative.split("/")[-1],
                "assembled blob mismatch",
            )
    data = encode(
        {
            "schemaVersion": 2,
            "mediaType": INDEX,
            "manifests": [graphs[target]["descriptor"] for target in sorted(TARGETS)],
        }
    )
    (output / "index.json").write_bytes(data)
    (output / "oci-layout").write_bytes(encode({"imageLayoutVersion": "1.0.0"}))
    return "sha256:" + hashlib.sha256(data).hexdigest()
