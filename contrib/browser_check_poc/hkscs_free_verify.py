"""Verify source/build inputs alongside the separate WASM execution probe."""

import argparse
import io
import json
from pathlib import Path
import subprocess
import tarfile
import tempfile
import zipfile

from contrib.browser_check_poc.hkscs_free import (
    HERE,
    REMOVED,
    ROOT,
    digest,
    prepare_build,
)


STAGED_INPUTS = (
    "cpython/Setup.local",
    "cpython/Makefile",
    "Makefile",
    "tools/hkscs_free_build.py",
)


def verify_staging(build, curated, source_cache):
    """Reconstruct trusted inputs; workspace receipts cannot vouch for themselves."""
    with tempfile.TemporaryDirectory() as temporary:
        stage = Path(temporary) / "stage"
        expected_build = prepare_build(source_cache, stage)
        for actual, expected in (
            (curated.parent / "build-profile.json", stage / "build-profile.json"),
            (curated / "source-removal.json", stage / "curated/source-removal.json"),
        ):
            if json.loads(actual.read_text("utf-8")) != json.loads(
                expected.read_text("utf-8")
            ):
                raise ValueError(
                    "staging receipt differs from locked source reconstruction"
                )
        if digest((curated / "cpython-hkscs-free.tar.gz").read_bytes()) != digest(
            (stage / "curated/cpython-hkscs-free.tar.gz").read_bytes()
        ):
            raise ValueError(
                "curated archive differs from locked source reconstruction"
            )
        for relative in STAGED_INPUTS:
            if (build / relative).read_bytes() != (
                expected_build / relative
            ).read_bytes():
                raise ValueError(
                    f"staged compiler input differs from locked source: {relative}"
                )


def verify(build, curated, runtime, llvm_ar, source_cache):
    verify_staging(build, curated, source_cache)
    profile = json.loads((curated.parent / "build-profile.json").read_text())
    for relative, field in (
        ("cpython/Setup.local", "setup_local_sha256"),
        ("cpython/Makefile", "cpython_makefile_sha256"),
        ("Makefile", "root_makefile_sha256"),
        ("tools/hkscs_free_build.py", "build_helper_sha256"),
    ):
        if digest((build / relative).read_bytes()) != profile[field]:
            raise ValueError(f"build profile differs: {relative}")
    if digest((build / "tools/hkscs_free_build.py").read_bytes()) != digest(
        (HERE / "hkscs_free_build.py").read_bytes()
    ):
        raise ValueError("build helper differs from reviewed source")
    runtime_files = {}
    for name in (
        "pyodide.mjs",
        "pyodide.asm.mjs",
        "pyodide.asm.wasm",
        "python_stdlib.zip",
        "pyodide-lock.json",
    ):
        data = (runtime / name).read_bytes()
        if digest(data) != digest((build / "dist" / name).read_bytes()):
            raise ValueError(f"candidate differs from build output: {name}")
        runtime_files[name] = {"bytes": len(data), "sha256": digest(data)}
    source = build / "cpython/build" / ROOT
    receipt = json.loads((curated / "source-removal.json").read_text())
    archive = curated / "cpython-hkscs-free.tar.gz"
    if digest(archive.read_bytes()) != receipt["curated_sha256"]:
        raise ValueError("curated archive changed")
    with tarfile.open(archive) as tar:
        names = {m.name.removeprefix(ROOT + "/") for m in tar}
    if REMOVED.intersection(names):
        raise ValueError("HKSCS payload remains in curated source")
    if any((source / name).exists() for name in REMOVED):
        raise ValueError("HKSCS payload remains in compiler source")
    aliases = source / "Lib/encodings/aliases.py"
    if digest(aliases.read_bytes()) != receipt["aliases_sha256"]:
        raise ValueError("compiler aliases do not match curated source")
    setup = source / "Modules/Setup.local"
    if "_codecs_hk" not in setup.read_text().split("*disabled*", 1)[1].split():
        raise ValueError("HKSCS is not disabled at compilation")
    config = source / "Modules/config.c"
    if "PyInit__codecs_hk" in config.read_text():
        raise ValueError("HKSCS remains registered in built-in module table")
    library = source / "libpython3.14.a"
    installed = build / "cpython/installs/python-3.14.2/lib/libpython3.14.a"
    if digest(library.read_bytes()) != digest(installed.read_bytes()):
        raise ValueError(
            "linked installed CPython library differs from checked library"
        )
    listing = subprocess.run(
        [str(llvm_ar), "t", str(library)], check=True, capture_output=True, text=True
    ).stdout.splitlines()
    if any(
        "codecs_hk" in name.lower() or "mappings_hk" in name.lower() for name in listing
    ):
        raise ValueError("HKSCS object in linked library")
    if not any("_codecs_jp" in name for name in listing):
        raise ValueError("Japanese codec object missing from evidence")
    if list(source.rglob("*codecs_hk*.o")):
        raise ValueError("stale HKSCS build object")
    with zipfile.ZipFile(runtime / "python_stdlib.zip") as stdlib:
        if stdlib.testzip() is not None:
            raise ValueError("corrupt runtime stdlib ZIP")
        names = stdlib.namelist()
        if any("__pycache__" in name or name.endswith(".pyc") for name in names):
            raise ValueError("unexpected bytecode cache in source stdlib")
        if any("big5hkscs" in name.lower() for name in names):
            raise ValueError("HKSCS wrapper in runtime stdlib")
        aliases_name = next(
            name for name in names if name.endswith("encodings/aliases.py")
        )
        if digest(stdlib.read(aliases_name)) != receipt["aliases_sha256"]:
            raise ValueError("runtime aliases differ from curated source")
    inputs = {
        "Setup.local": setup,
        "config.c": config,
        "libpython3.14.a": library,
        "installed/libpython3.14.a": installed,
        "cpython/Makefile": build / "cpython/Makefile",
        "Pyodide.Setup.local": build / "cpython/Setup.local",
        "Pyodide.Makefile": build / "Makefile",
        "build_helper": build / "tools/hkscs_free_build.py",
    }
    lock = json.loads((HERE / "source-lock.json").read_text())
    pyodide = next(x for x in lock["archives"] if x["id"] == "pyodide")
    pyodide_data = (source_cache / pyodide["file"]).read_bytes()
    if digest(pyodide_data) != pyodide["sha256"]:
        raise ValueError("Pyodide source archive changed")
    checked_pyodide = {}
    with tarfile.open(fileobj=io.BytesIO(pyodide_data)) as archive:
        for member in archive:
            name = member.name.removeprefix(pyodide["root"] + "/")
            if not member.isfile() or not name.startswith("src/"):
                continue
            expected = digest(archive.extractfile(member).read())
            actual = build / name
            if not actual.is_file() or digest(actual.read_bytes()) != expected:
                raise ValueError(f"Pyodide runtime source differs: {name}")
            checked_pyodide[name] = expected
    checked_cpython = {}
    with tempfile.TemporaryDirectory() as temporary:
        expected_root = Path(temporary)
        with tarfile.open(curated / "cpython-hkscs-free.tar.gz") as tar:
            tar.extractall(expected_root, filter="data")
        for patch in sorted((build / "cpython/patches").glob("*.patch")):
            key = "cpython/patches/" + patch.name
            if digest(patch.read_bytes()) != pyodide["required_members"].get(key):
                raise ValueError("unlocked CPython patch")
            subprocess.run(
                ["patch", "--batch", "--forward", "-p1", "-i", str(patch.resolve())],
                cwd=expected_root / ROOT,
                check=True,
                capture_output=True,
            )
        if len(list((build / "cpython/patches").glob("*.patch"))) != 9:
            raise ValueError("unexpected CPython patch set")
        for expected_file in sorted((expected_root / ROOT).rglob("*")):
            if not expected_file.is_file() or expected_file.suffix not in (
                ".c",
                ".h",
                ".py",
            ):
                continue
            name = expected_file.relative_to(expected_root / ROOT).as_posix()
            expected = digest(expected_file.read_bytes())
            actual = source / name
            if not actual.is_file() or digest(actual.read_bytes()) != expected:
                raise ValueError(f"CPython compiler input differs: {name}")
            checked_cpython[name] = expected
    dependencies = {}
    for component, directory in (
        ("xz", "lzma"),
        ("zstd", "zstd"),
        ("sqlite", "sqlite3"),
        ("libffi", "libffi"),
        ("hiwire", "hiwire"),
    ):
        entry = next(x for x in lock["archives"] if x["id"] == component)
        data = (source_cache / entry["file"]).read_bytes()
        if digest(data) != entry["sha256"]:
            raise ValueError(f"{component} source archive changed")
        checked = {}
        with tarfile.open(fileobj=io.BytesIO(data)) as archive:
            for member in archive:
                if not member.isfile() or not member.name.endswith((".c", ".h")):
                    continue
                name = member.name.removeprefix(entry["root"] + "/")
                expected = digest(archive.extractfile(member).read())
                actual = build / "cpython/build" / directory / name
                if not actual.is_file() or digest(actual.read_bytes()) != expected:
                    raise ValueError(f"{component} compiler input differs: {name}")
                checked[name] = expected
        if not checked:
            raise ValueError(f"no compiler source evidence for {component}")
        dependencies[component] = {
            "archive_sha256": entry["sha256"],
            "c_and_h_files": len(checked),
            "manifest_sha256": digest(json.dumps(checked, sort_keys=True).encode()),
        }
    return {
        "schema_version": 1,
        "profile": receipt["profile"],
        "runtime_files": runtime_files,
        "curated_sha256": receipt["curated_sha256"],
        "removed_source_files": sorted(REMOVED),
        "archive_object_count": len(listing),
        "inputs_sha256": {
            name: digest(path.read_bytes()) for name, path in inputs.items()
        },
        "dependency_source_checks": dependencies,
        "cpython_source_check": {
            "c_h_and_py_files": len(checked_cpython),
            "patches": 9,
            "manifest_sha256": digest(
                json.dumps(checked_cpython, sort_keys=True).encode()
            ),
        },
        "pyodide_source_check": {
            "src_files": len(checked_pyodide),
            "manifest_sha256": digest(
                json.dumps(checked_pyodide, sort_keys=True).encode()
            ),
        },
        "complete_distribution_audit": False,
        "public_distribution_approved": False,
        "limits": "Source and object inclusion checks; pair with actual WASM probe. "
        "Not independent review, compiler attestation or publication approval.",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("build", "curated", "runtime", "llvm_ar", "output"):
        parser.add_argument(name, type=Path)
    parser.add_argument("--source-cache", type=Path, required=True)
    args = parser.parse_args()
    report = verify(
        args.build, args.curated, args.runtime, args.llvm_ar, args.source_cache
    )
    args.output.write_bytes(
        (json.dumps(report, indent=2, sort_keys=True) + "\n").encode()
    )
