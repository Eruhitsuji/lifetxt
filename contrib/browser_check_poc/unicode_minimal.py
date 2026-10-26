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
from pathlib import Path, PurePosixPath
import tarfile

ROOT = "Python-3.14.2"
EXPECTED_SOURCE_SHA256 = "f862710e3d61091aae013d486d8bedbf1074188fd98086572d6340ec60b5392c"
KEEP_ENCODINGS = frozenset({
    "__init__", "aliases", "ascii", "latin_1", "utf_8", "utf_8_sig",
    "utf_16", "utf_16_be", "utf_16_le", "utf_32", "utf_32_be", "utf_32_le",
    "unicode_escape", "raw_unicode_escape", "idna", "punycode", "charmap",
    "undefined",
})
REQUIRED_INPUTS = frozenset({
    "Lib/encodings/aliases.py", "Lib/encodings/utf_8.py",
    "Lib/encodings/latin_1.py", "Lib/encodings/ascii.py",
    "Modules/cjkcodecs/_codecs_cn.c", "Modules/cjkcodecs/mappings_cn.h",
    "Lib/encodings/gb18030.py",
    "Tools/unicode/python-mappings/gb-18030-2000.xml",
})
REMOVED_DIRS = (
    "Modules/cjkcodecs/", "Tools/unicode/python-mappings/",
)


def _aliases(source):
    """Filter the original literal aliases dict; reject unexpected syntax."""
    body = ast.parse(source.decode("utf-8"))
    mappings = [node.value for node in body.body if isinstance(node, ast.Assign)
                and any(isinstance(t, ast.Name) and t.id == "aliases" for t in node.targets)]
    if len(mappings) != 1:
        raise ValueError("missing or ambiguous encodings.aliases assignment")
    mapping = ast.literal_eval(mappings[0])
    if not isinstance(mapping, dict) or not all(
        isinstance(k, str) and isinstance(v, str) for k, v in mapping.items()
    ):
        raise ValueError("unexpected aliases format")
    kept = {name: target for name, target in mapping.items() if target in KEEP_ENCODINGS}
    return ("# Generated for isolated lifetxt Unicode-minimal source PoC.\n"
            + "aliases = " + repr(dict(sorted(kept.items()))) + "\n").encode("utf-8")


def curate(source: Path, target: Path, *, expected_source_sha256=EXPECTED_SOURCE_SHA256):
    """Curate an HKSCS-free CPython source tar without modifying the input.

    The fixed profile2 source SHA-256 is required; changed source is rejected.
    This function refuses an existing output; never call it on a build tree.
    """
    if target.exists():
        raise FileExistsError(target)
    source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    if source_hash != expected_source_sha256:
        raise ValueError("CPython source SHA-256 differs from pinned input")
    files = {}
    removed = []
    seen = set()
    with tarfile.open(source, "r:gz") as archive:
        for member in archive:
            parts = PurePosixPath(member.name).parts
            if not parts or parts[0] != ROOT or ".." in parts or member.name.startswith("/"):
                raise ValueError("unsafe archive path")
            if member.isdir():
                continue
            if not member.isfile() or len(parts) < 2:
                raise ValueError("non-regular or root member")
            relative = "/".join(parts[1:])
            if relative in seen:
                raise ValueError("duplicate archive member")
            seen.add(relative)
            blob = archive.extractfile(member).read()
            remove = relative.startswith(REMOVED_DIRS)
            if relative.startswith("Lib/encodings/") and relative.endswith(".py"):
                remove = relative.rsplit("/", 1)[-1][:-3] not in KEEP_ENCODINGS
            if remove:
                removed.append(relative)
                continue
            if relative == "Lib/encodings/aliases.py":
                blob = _aliases(blob)
            files[relative] = (blob, member.mode & 0o777)
    if not REQUIRED_INPUTS.issubset(seen):
        raise ValueError("source archive missing expected codec/ICU inputs")
    if any(name.startswith(REMOVED_DIRS) for name in files):
        raise AssertionError("CJK mapping source retained")
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
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(payload)
    return {
        "kind": "source-only-utf8-minimal-candidate",
        "runtime_verified": False,
        "licence_resolved": False,
        "source_sha256": source_hash,
        "output_sha256": hashlib.sha256(payload).hexdigest(),
        "retained_files": len(files),
        "removed_files": len(removed),
        "removed_sha256": hashlib.sha256("\n".join(sorted(removed)).encode()).hexdigest(),
        "remaining_codecs": sorted(KEEP_ENCODINGS),
        "required_build_action": "disable all CJK builtin modules and _multibytecodec in Pyodide Setup.local; rebuild and independently audit object/WASM/stdlib",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="verified HKSCS-free CPython source .tar.gz")
    parser.add_argument("output", type=Path, help="new candidate .tar.gz (must not exist)")
    args = parser.parse_args()
    print(json.dumps(curate(args.source, args.output), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
