"""Produce a *source-only* Unicode-minimal CPython experiment, not a runtime.

The output is deliberately unbuildable without a separate Pyodide Setup.local
review: static/builtin CJK modules must be explicitly disabled before compiling.
It provides no evidence that a compiled WASM is free of mapping tables.
"""

import argparse
import ast
import gzip
import hashlib
import io
import json
import os
import tempfile
from pathlib import Path, PurePosixPath
import tarfile

ROOT = "Python-3.14.2"
EXPECTED_SOURCE_SHA256 = (
    "f862710e3d61091aae013d486d8bedbf1074188fd98086572d6340ec60b5392c"
)
KEEP_ENCODINGS = frozenset(
    {
        "__init__",
        "aliases",
        "ascii",
        "latin_1",
        "utf_8",
        "utf_8_sig",
        "utf_16",
        "utf_16_be",
        "utf_16_le",
        "utf_32",
        "utf_32_be",
        "utf_32_le",
        "unicode_escape",
        "raw_unicode_escape",
        "idna",
        "punycode",
        "charmap",
        "undefined",
    }
)
REQUIRED_INPUTS = frozenset(
    {
        "Lib/encodings/aliases.py",
        "Lib/encodings/utf_8.py",
        "Lib/encodings/latin_1.py",
        "Lib/encodings/ascii.py",
        "Modules/cjkcodecs/_codecs_cn.c",
        "Modules/cjkcodecs/mappings_cn.h",
        "Lib/encodings/gb18030.py",
        "Tools/unicode/python-mappings/gb-18030-2000.xml",
    }
)
REMOVED_DIRS = (
    "Modules/cjkcodecs/",
    "Tools/unicode/python-mappings/",
)

# Conservative safety budgets, not measurements or runtime support guarantees.
MAX_ARCHIVE_BYTES = 128 * 1024 * 1024
MAX_MEMBER_BYTES = 32 * 1024 * 1024
MAX_EXPANDED_BYTES = 512 * 1024 * 1024
MAX_MEMBERS = 16384
EXPECTED_RESULT = {
    "removed_files": 130,
    "retained_files": 4927,
    "removed_sha256": "2d992f949d6af6350deb923e9a97a95687f6af902da6e3326796ff91b2ea97f8",
    "output_sha256": "eb80e7df3c4a4190ec5b83c72e231fbba33dc299a442ce6743ea03a54dea5619",
}


class _BoundedReader:
    """Bound decompressed tar bytes, including headers, padding and extensions."""

    def __init__(self, stream):
        self.stream = stream
        self.remaining = MAX_EXPANDED_BYTES

    def read(self, size=-1):
        size = min(size if size >= 0 else self.remaining + 1, self.remaining + 1)
        data = self.stream.read(size)
        self.remaining -= len(data)
        if self.remaining < 0:
            raise ValueError("expanded archive limit exceeded")
        return data


def _publish(payload, target):
    """Publish complete bytes without replacing a concurrently created target."""
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=target.parent, delete=False) as stream:
        temporary = Path(stream.name)
        try:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        except BaseException:
            temporary.unlink()
            raise
    try:
        # Same-filesystem link is atomic and refuses existing files/symlinks.
        os.link(temporary, target)
    finally:
        temporary.unlink()


def _aliases(source):
    """Filter the original literal aliases dict; reject unexpected syntax."""
    body = ast.parse(source.decode("utf-8"))
    mappings = [
        node.value
        for node in body.body
        if isinstance(node, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == "aliases" for t in node.targets)
    ]
    if len(mappings) != 1:
        raise ValueError("missing or ambiguous encodings.aliases assignment")
    mapping = ast.literal_eval(mappings[0])
    if not isinstance(mapping, dict) or not all(
        isinstance(k, str) and isinstance(v, str) for k, v in mapping.items()
    ):
        raise ValueError("unexpected aliases format")
    kept = {
        name: target for name, target in mapping.items() if target in KEEP_ENCODINGS
    }
    return (
        "# Generated for isolated lifetxt Unicode-minimal source PoC.\n"
        + "aliases = "
        + repr(dict(sorted(kept.items())))
        + "\n"
    ).encode("utf-8")


def curate(source: Path, target: Path):
    """Production entry point: fixed input AND fixed historical output receipt."""
    return _curate(source, target, EXPECTED_SOURCE_SHA256, EXPECTED_RESULT)


def _curate(source, target, expected_source_sha256, expected_result):
    """Internal synthetic-test seam; callers must not use it for build inputs."""
    if target.exists() or target.is_symlink():
        raise FileExistsError(target)
    with source.open("rb") as stream, tempfile.TemporaryFile() as snapshot:
        digest = hashlib.sha256()
        compressed_bytes = 0
        while chunk := stream.read(1024 * 1024):
            compressed_bytes += len(chunk)
            if compressed_bytes > MAX_ARCHIVE_BYTES:
                raise ValueError("compressed archive limit exceeded")
            digest.update(chunk)
            snapshot.write(chunk)
        source_hash = digest.hexdigest()
        if source_hash != expected_source_sha256:
            raise ValueError("CPython source SHA-256 differs from pinned input")
        snapshot.seek(0)
        return _curate_verified(snapshot, target, source_hash, expected_result)


def _curate_verified(raw, target, source_hash, expected_result):
    files = {}
    removed = []
    seen = set()
    expanded_bytes = 0
    with gzip.GzipFile(fileobj=raw) as expanded:
        with tarfile.open(fileobj=_BoundedReader(expanded), mode="r|") as archive:
            for member_number, member in enumerate(archive, 1):
                if member_number > MAX_MEMBERS:
                    raise ValueError("archive member count limit exceeded")
                if member.size < 0 or member.size > MAX_MEMBER_BYTES:
                    raise ValueError("archive member size limit exceeded")
                expanded_bytes += member.size
                if expanded_bytes > MAX_EXPANDED_BYTES:
                    raise ValueError("expanded member limit exceeded")
                parts = PurePosixPath(member.name).parts
                if (
                    not parts
                    or parts[0] != ROOT
                    or ".." in parts
                    or member.name.startswith("/")
                    or "\\" in member.name
                ):
                    raise ValueError("unsafe archive path")
                normalized = "/".join(parts)
                if normalized in seen:
                    raise ValueError("duplicate archive member")
                seen.add(normalized)
                if member.isdir():
                    continue
                if not member.isfile() or len(parts) < 2:
                    raise ValueError("non-regular or root member")
                relative = "/".join(parts[1:])
                blob = archive.extractfile(member).read()
                remove = relative.startswith(REMOVED_DIRS)
                if relative.startswith("Lib/encodings/"):
                    filename = relative.removeprefix("Lib/encodings/")
                    if "/" in filename or not filename.endswith(".py"):
                        raise ValueError("unexpected encoding subtree member")
                    remove = filename[:-3] not in KEEP_ENCODINGS
                if remove:
                    removed.append(relative)
                    continue
                if relative == "Lib/encodings/aliases.py":
                    blob = _aliases(blob)
                files[relative] = (blob, member.mode & 0o777)
    if not {ROOT + "/" + name for name in REQUIRED_INPUTS}.issubset(seen):
        raise ValueError("source archive missing expected codec/ICU inputs")
    if not all("Lib/encodings/" + key + ".py" in files for key in KEEP_ENCODINGS):
        raise ValueError("missing required Unicode/internal codec")

    buf = io.BytesIO()
    with gzip.GzipFile(fileobj=buf, mode="wb", mtime=0, filename="") as z:
        with tarfile.open(fileobj=z, mode="w") as archive:
            for name, (content, mode) in sorted(files.items()):
                info = tarfile.TarInfo(ROOT + "/" + name)
                info.size, info.mode, info.mtime = len(content), mode, 0
                info.uid = info.gid = 0
                info.uname = info.gname = ""
                archive.addfile(info, io.BytesIO(content))
    payload = buf.getvalue()
    report = {
        "kind": "source-only-utf8-minimal-candidate",
        "runtime_verified": False,
        "licence_resolved": False,
        "source_sha256": source_hash,
        "output_sha256": hashlib.sha256(payload).hexdigest(),
        "retained_files": len(files),
        "removed_files": len(removed),
        "removed_sha256": hashlib.sha256(
            "\n".join(sorted(removed)).encode()
        ).hexdigest(),
        "remaining_codecs": sorted(KEEP_ENCODINGS),
        "required_build_action": "disable all CJK builtin modules and _multibytecodec in Pyodide Setup.local; rebuild and independently audit object/WASM/stdlib",
    }
    report["retained_sha256"] = {
        name: hashlib.sha256(content).hexdigest()
        for name, (content, _) in sorted(files.items())
    }
    for key, expected in expected_result.items():
        if report[key] != expected:
            raise ValueError("curation receipt mismatch: " + key)
    _publish(payload, target)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "source", type=Path, help="verified HKSCS-free CPython source .tar.gz"
    )
    parser.add_argument(
        "output", type=Path, help="new candidate .tar.gz (must not exist)"
    )
    args = parser.parse_args()
    print(json.dumps(curate(args.source, args.output), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
