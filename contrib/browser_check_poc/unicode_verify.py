"""Verify the exact isolated profile3 candidate; never grants distribution approval."""

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tarfile
import tempfile
import zipfile

from contrib.browser_check_poc import unicode_minimal, unicode_runtime

HERE = Path(__file__).resolve().parent
EVIDENCE = HERE / "profiles/unicode-minimal-3/build-evidence.json"
BLOCKED = (
    "_multibytecodec",
    "_codecs_cn",
    "_codecs_jp",
    "_codecs_kr",
    "_codecs_tw",
    "_codecs_hk",
    "_codecs_iso2022",
)


def _regular(path):
    if not path.is_file() or any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError("missing/nonregular/symlink input: " + str(path))
    return path


def runtime_identity(candidate, expected):
    if {p.name for p in candidate.iterdir()} != set(expected):
        raise ValueError("missing/extra candidate files")
    for name, receipt in expected.items():
        path = _regular(candidate / name)
        if (
            path.stat().st_size != receipt["bytes"]
            or unicode_runtime.sha256(path) != receipt["sha256"]
        ):
            raise ValueError("candidate differs from pin: " + name)
    return expected


def config_and_objects(config, listing, object_names):
    if "_PyImport_Inittab" not in config or "PyInit__codecs" not in config:
        raise ValueError("missing builtin registration evidence")
    if any("PyInit_" + name in config for name in BLOCKED):
        raise ValueError("CJK builtin registration remains")

    def forbidden(name):
        return any(module.lstrip("_") in name.lower() for module in BLOCKED)

    if (
        not listing
        or not object_names
        or not any("codecsmodule" in name for name in listing)
    ):
        raise ValueError("missing static archive evidence")
    if any(forbidden(name) for name in [*listing, *object_names]):
        raise ValueError("CJK static/stale object remains")
    return {
        "archive_members": len(listing),
        "object_files": len(object_names),
        "config_sha256": hashlib.sha256(config.encode("utf-8")).hexdigest(),
    }


def stdlib_identity(path, cp437_sha):
    expected = {
        "encodings/" + name + ".py" for name in unicode_minimal.KEEP_ENCODINGS
    } | {"encodings/cp437.py"}
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)) or archive.testzip() is not None:
            raise ValueError("duplicate/corrupt stdlib archive")
        if {name for name in names if name.startswith("encodings/")} != expected:
            raise ValueError("unexpected stdlib encodings")
        if any(
            "__pycache__" in name or name.endswith((".pyc", ".pyo")) for name in names
        ):
            raise ValueError("unexpected stdlib bytecode")
        if hashlib.sha256(archive.read("encodings/cp437.py")).hexdigest() != cp437_sha:
            raise ValueError("cp437 overlay differs")
    return {"encoding_files": len(expected), "cp437_sha256": cp437_sha}


def checkpoint_build_identity(build, manifest):
    retention = json.loads(
        (HERE / "profiles/unicode-minimal-3/retention.json").read_bytes()
    )
    if unicode_runtime.sha256(_regular(manifest)) != retention["manifest_sha256"]:
        raise ValueError("checkpoint manifest differs from retained pin")
    files = json.loads(manifest.read_bytes())["files"]
    count = 0
    for name, pin in files.items():
        if not name.startswith("build/"):
            continue
        relative = name.removeprefix("build/")
        parts = Path(relative).parts
        if (
            not parts
            or Path(relative).is_absolute()
            or ".." in parts
            or "\\" in relative
        ):
            raise ValueError("unsafe checkpoint path")
        path = _regular(build / relative)
        if (
            path.stat().st_size != pin["bytes"]
            or unicode_runtime.sha256(path) != pin["sha256"]
        ):
            raise ValueError("retained build payload differs: " + relative)
        count += 1
    if not count:
        raise ValueError("no retained build payload evidence")
    return count


def removed_source_directories(source):
    for name in ("Modules/cjkcodecs", "Tools/unicode/python-mappings"):
        directory = source / name
        if (
            directory.is_symlink()
            or (directory.exists() and not directory.is_dir())
            or any(not p.is_dir() or p.is_symlink() for p in directory.rglob("*"))
        ):
            raise ValueError("removed CJK/mapping source payload remains")


def verify(build, sources, curated, candidate, llvm_ar, checkpoint_manifest):
    locked = json.loads(EVIDENCE.read_text(encoding="utf-8"))
    runtime_identity(candidate, locked["files"])
    checkpoint_files = checkpoint_build_identity(build, checkpoint_manifest)
    ar_pin = locked["sdk_provenance_recheck"]["binary_files"]["llvm-ar"]
    if unicode_runtime.sha256(_regular(llvm_ar)) != ar_pin["sha256"]:
        raise ValueError("llvm-ar differs from pin")
    if (
        unicode_runtime.sha256(_regular(curated))
        != unicode_minimal.EXPECTED_RESULT["output_sha256"]
    ):
        raise ValueError("curated source differs from pin")
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        staged = unicode_runtime.stage(sources, root / "stage")
        receipt = json.loads((root / "stage/stage-receipt.json").read_bytes())
        for name, expected in receipt["staged_files_sha256"].items():
            if unicode_runtime.sha256(_regular(build / name)) != expected:
                raise ValueError("staged compiler input differs: " + name)
        unicode_runtime._members(curated, unicode_minimal.ROOT)
        with tarfile.open(curated) as archive:
            archive.extractall(root / "source", filter="data")
        expected_source = root / "source" / unicode_minimal.ROOT
        source = build / "cpython/build" / unicode_minimal.ROOT
        removed_source_directories(source)
        for patch in sorted((staged / "cpython/patches").glob("*.patch")):
            subprocess.run(
                ["patch", "--batch", "--forward", "-p1", "-i", str(patch)],
                cwd=expected_source,
                check=True,
                capture_output=True,
            )
        checked = {}
        for path in sorted(expected_source.rglob("*")):
            if path.is_file() and path.suffix in (".c", ".h", ".py"):
                name = path.relative_to(expected_source).as_posix()
                digest = unicode_runtime.sha256(path)
                if unicode_runtime.sha256(_regular(source / name)) != digest:
                    raise ValueError("CPython compiler source differs: " + name)
                checked[name] = digest
        if (source / "Modules/Setup.local").read_bytes() != (
            staged / "cpython/Setup.local"
        ).read_bytes():
            raise ValueError("compiled Setup.local differs from staged declaration")
        library = source / "libpython3.14.a"
        installed = build / "cpython/installs/python-3.14.2/lib/libpython3.14.a"
        if unicode_runtime.sha256(_regular(library)) != unicode_runtime.sha256(
            _regular(installed)
        ):
            raise ValueError("linked installed archive differs from build archive")
        listing = subprocess.run(
            [str(llvm_ar), "t", str(library)],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.splitlines()
        objects = [p.relative_to(source).as_posix() for p in source.rglob("*.o")]
        config_path = _regular(source / "Modules/config.c")
        config = config_and_objects(
            config_path.read_text(encoding="utf-8"), listing, objects
        )
        # References/samples are deliberately inventoried, NOT asserted absent.
        residuals = []
        pattern = re.compile(rb"gb18030|hkscs|jisx?0213|gb2312|big5|cp437", re.I)
        for path in sorted(expected_source.rglob("*")):
            if path.is_file() and not path.is_symlink():
                if pattern.search(path.read_bytes()):
                    residuals.append(path.relative_to(expected_source).as_posix())
        samples = [
            p.relative_to(source).as_posix()
            for p in sorted((source / "Lib/test/cjkencodings").glob("*"))
            if p.is_file()
        ]
        return {
            "schema_version": 1,
            "scope": "exact source/config/static objects/stdlib technical checks; WASM executed separately",
            "runtime_files": locked["files"],
            "checkpoint_build_payloads": checkpoint_files,
            "staged_files": len(receipt["staged_files_sha256"]),
            "cpython_source_files": len(checked),
            "cpython_manifest_sha256": hashlib.sha256(
                json.dumps(checked, sort_keys=True).encode()
            ).hexdigest(),
            "static": config,
            "libpython_sha256": unicode_runtime.sha256(library),
            "stdlib": stdlib_identity(
                candidate / "python_stdlib.zip", locked["internal_cp437_sha256"]
            ),
            "residual_source_references": residuals,
            "retained_cjk_sample_files": samples,
            "source_residual_review_required": True,
            "runtime_verified": False,
            "complete_distribution_audit": False,
            "public_distribution_approved": False,
        }


def prepare_probe(output):
    """Native expected results from all public examples and bounded diagnostics."""
    from contrib.browser_check_poc import adapter
    from contrib.browser_check_poc.build import core_archive_bytes

    output.mkdir(parents=True, exist_ok=False)
    (output / "core.zip").write_bytes(core_archive_bytes())
    (output / "adapter.py").write_bytes((HERE / "adapter.py").read_bytes())
    previous_limit = adapter.MAX_BYTES
    adapter.MAX_BYTES = 16384
    try:
        cases = []
        examples = HERE.parent.parent / "examples"
        texts = [
            (p.relative_to(examples.parent).as_posix(), p.read_text(encoding="utf-8"))
            for p in sorted(examples.rglob("*.txt"))
        ]
        texts += [
            ("ja-emoji", '[ ] T "日本語😀"\n'),
            ("diagnostic-cap", "bad\n" * 120),
            ("boundary", "#" + "a" * 16383),
            ("oversized", "#" + "a" * 16384),
            ("oversized-utf8", "あ" * 5462),
        ]
        for name, text in texts:
            case = {"name": name, "text": text}
            try:
                case["expected"] = adapter.check_text(text)
            except ValueError:
                if len(text.encode("utf-8")) <= adapter.MAX_BYTES:
                    raise
                case["expected_error"] = "ValueError"
            cases.append(case)
        (output / "cases.json").write_bytes(
            json.dumps(cases, ensure_ascii=False).encode("utf-8")
        )
        return len(cases)
    finally:
        adapter.MAX_BYTES = previous_limit


def main():
    import sys

    if len(sys.argv) == 3 and sys.argv[1] == "prepare-probe":
        print(prepare_probe(Path(sys.argv[2])))
        return
    parser = argparse.ArgumentParser(description=__doc__)
    for name in (
        "build",
        "sources",
        "curated",
        "candidate",
        "llvm_ar",
        "checkpoint_manifest",
        "output",
    ):
        parser.add_argument(name, type=Path)
    args = parser.parse_args()
    result = verify(
        args.build,
        args.sources,
        args.curated,
        args.candidate,
        args.llvm_ar,
        args.checkpoint_manifest,
    )
    with args.output.open("x", encoding="utf-8", newline="\n") as output:
        output.write(json.dumps(result, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
