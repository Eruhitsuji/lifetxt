"""Prepare a separately identified HKSCS-free CPython source candidate.

This does not approve or replace the currently locked Pyodide runtime. Run on
the verified upstream archive before compiling, never on installed WASM alone.
"""

import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import shutil
import tarfile
import zipfile

HERE = Path(__file__).resolve().parent
ROOT = "Python-3.14.2"
REMOVED = frozenset(
    {
        "Modules/cjkcodecs/_codecs_hk.c",
        "Modules/cjkcodecs/mappings_hk.h",
        "Lib/encodings/big5hkscs.py",
        "Lib/test/cjkencodings/big5hkscs.txt",
        "Lib/test/cjkencodings/big5hkscs-utf8.txt",
        "Lib/test/test_codecencodings_hk.py",
        "Lib/test/test_codecmaps_hk.py",
    }
)
ALIASES = (
    b"    # big5hkscs codec\n"
    b"    'big5_hkscs'         : 'big5hkscs',\n"
    b"    'hkscs'              : 'big5hkscs',\n\n"
)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def prepare(archive, output):
    """Verify the upstream input and emit a deterministic curated archive.

    Keep upstream licensing and documentation, including historical references.
    A generator reference is not itself HKSCS table data. The generated mapping,
    codec implementation, wrapper and samples are excluded. Setup.local must
    additionally disable the built-in module at compilation time.
    """
    entry = next(
        x
        for x in json.loads((HERE / "source-lock.json").read_text())["archives"]
        if x["id"] == "cpython"
    )
    data = Path(archive).read_bytes()
    if digest(data) != entry["sha256"] or len(data) != entry["bytes"]:
        raise ValueError("CPython upstream archive does not match source-lock")
    if output.exists():
        raise ValueError("output already exists")
    members = {}
    removed = {}
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as source:
        for member in source:
            parts = PurePosixPath(member.name).parts
            if not parts or parts[0] != ROOT or ".." in parts:
                raise ValueError("unexpected upstream path")
            if member.isdir():
                continue
            if not member.isfile():
                raise ValueError("unexpected upstream non-regular member")
            name = "/".join(parts[1:])
            if name in members or name in removed:
                raise ValueError("duplicate member")
            body = source.extractfile(member).read()
            if name in REMOVED:
                removed[name] = digest(body)
                continue
            if name == "Lib/encodings/aliases.py":
                if body.count(ALIASES) != 1:
                    raise ValueError("unexpected alias definitions")
                body = body.replace(ALIASES, b"")
            members[name] = (body, member.mode & 0o777)
    if set(removed) != REMOVED:
        raise ValueError("missing HKSCS removal input")
    output.mkdir(parents=True)
    target = output / "cpython-hkscs-free.tar.gz"
    with (
        target.open("wb") as raw,
        gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as compressed,
        tarfile.open(fileobj=compressed, mode="w") as tar,
    ):
        for name, (body, mode) in sorted(members.items()):
            info = tarfile.TarInfo(f"{ROOT}/{name}")
            info.size, info.mode = len(body), mode
            tar.addfile(info, io.BytesIO(body))
    report = {
        "schema_version": 1,
        "profile": "lifetxt-hkscs-free-1",
        "upstream_sha256": entry["sha256"],
        "curated_sha256": digest(target.read_bytes()),
        "removed_sha256": removed,
        "aliases_sha256": digest(members["Lib/encodings/aliases.py"][0]),
        "required_disabled_builtin": "_codecs_hk",
        "runtime_verified": False,
        "complete_distribution_audit": False,
        "public_distribution_approved": False,
    }
    (output / "source-removal.json").write_bytes(
        (json.dumps(report, indent=2, sort_keys=True) + "\n").encode()
    )
    return report


def prepare_build(cache, output):
    """Stage fixed Pyodide and curated CPython; SDK remains an explicit prerequisite."""
    lock = json.loads((HERE / "source-lock.json").read_text())
    entry = next(x for x in lock["archives"] if x["id"] == "pyodide")
    data = (cache / entry["file"]).read_bytes()
    if digest(data) != entry["sha256"] or len(data) != entry["bytes"]:
        raise ValueError("Pyodide archive does not match source-lock")
    if output.exists():
        raise ValueError("build output already exists")
    local_dependencies = {}
    for component in ("xz", "zstd", "sqlite"):
        dependency = next(x for x in lock["archives"] if x["id"] == component)
        body = (cache / dependency["file"]).read_bytes()
        if digest(body) != dependency["sha256"] or len(body) != dependency["bytes"]:
            raise ValueError(f"{component} archive does not match source-lock")
        local_dependencies[component] = (dependency, body)
    # Validate paths and types before touching the output directory.
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as source:
        for member in source:
            parts = PurePosixPath(member.name).parts
            if not parts or parts[0] != entry["root"] or ".." in parts:
                raise ValueError("unexpected Pyodide path")
            if not (
                member.isdir()
                or member.isfile()
                or (
                    member.issym()
                    and parts[1:] == (".cursorrules",)
                    and member.linkname == "AGENTS.md"
                )
            ):
                raise ValueError("unexpected Pyodide member type")
        output.mkdir(parents=True)
        source.extractall(output, filter="data")
    root = output / entry["root"]
    report = prepare(cache / "cpython-source.tar.gz", output / "curated")
    setup = root / "cpython/Setup.local"
    if digest(setup.read_bytes()) != entry["required_members"]["cpython/Setup.local"]:
        raise ValueError("unexpected Pyodide Setup.local")
    setup.write_bytes(
        setup.read_bytes() + b"\n# lifetxt HKSCS-free profile (#1415)\n_codecs_hk\n"
    )
    downloads = root / "cpython/downloads"
    downloads.mkdir(exist_ok=True)
    # Upstream's existing-file target will consume this verified curated archive.
    # Missing cache must not fetch an uncurated replacement under this filename.
    shutil.copyfile(
        output / "curated/cpython-hkscs-free.tar.gz", downloads / "Python-3.14.2.tgz"
    )
    makefile = root / "cpython/Makefile"
    body = makefile.read_bytes()
    before = b"\twget -q -O $@ $(PYTHON_ARCHIVE_URL)"
    if body.count(before) != 1:
        raise ValueError("unexpected CPython download recipe")
    makefile.write_bytes(
        body.replace(
            before,
            b'\t@echo "HKSCS-free curated input missing; rerun hkscs_free.py --build" >&2; exit 1',
        )
    )
    body = makefile.read_bytes()
    for component, variable in (
        ("xz", "LZMATARBALL"),
        ("zstd", "ZSTDTARBALL"),
        ("sqlite", "SQLITE3TARBALL"),
    ):
        dependency, raw = local_dependencies[component]
        (downloads / dependency["file"]).write_bytes(raw)
        before = f"wget -q -O - $({variable})".encode()
        if body.count(before) != 1:
            raise ValueError(f"unexpected {component} download recipe")
        body = body.replace(
            before, f"cat $(ROOT)/downloads/{dependency['file']}".encode()
        )
    makefile.write_bytes(body)
    root_makefile = root / "Makefile"
    body = root_makefile.read_text()
    start = body.index("\trm -f $@\n")
    end = body.index("\n# Don't use ccache here", start)
    body = body[:start] + "\tpython3 tools/hkscs_free_build.py embed\n\n" + body[end:]
    body = body.replace(
        "\t./tools/create_zipfile.py ", "\tpython3 tools/hkscs_free_build.py stdlib "
    )
    for target in ("src/core/pyodide_pre.gen.dat", "dist/python_stdlib.zip"):
        body = body.replace(target + ": ", target + ": tools/hkscs_free_build.py ")
    root_makefile.write_bytes(body.encode())
    shutil.copyfile(HERE / "hkscs_free_build.py", root / "tools/hkscs_free_build.py")
    report["setup_local_sha256"] = digest(setup.read_bytes())
    report["cpython_makefile_sha256"] = digest(makefile.read_bytes())
    report["root_makefile_sha256"] = digest(root_makefile.read_bytes())
    report["build_helper_sha256"] = digest(
        (root / "tools/hkscs_free_build.py").read_bytes()
    )
    (output / "build-profile.json").write_bytes(
        (json.dumps(report, indent=2, sort_keys=True) + "\n").encode()
    )
    return root


def stage_probe(runtime, output):
    """Create an isolated local test layout, without altering the public builder."""
    from contrib.browser_check_poc.adapter import check_text
    from contrib.browser_check_poc.build import RUNTIME_FILES, core_archive_bytes

    if output.exists():
        raise ValueError("probe output already exists")
    files = {name: (runtime / name).read_bytes() for name in RUNTIME_FILES}
    with zipfile.ZipFile(io.BytesIO(files["python_stdlib.zip"])) as archive:
        if archive.testzip() is not None:
            raise ValueError("corrupt candidate stdlib")
    output.mkdir(parents=True)
    (output / "runtime").mkdir()
    for name, data in files.items():
        (output / "runtime" / name).write_bytes(data)
    for name in (
        "index.html",
        "ui.mjs",
        "worker.mjs",
        "engine.mjs",
        "adapter.py",
        "style.css",
    ):
        (output / name).write_bytes((HERE / name).read_bytes())
    (output / "core.zip").write_bytes(core_archive_bytes())
    fixtures = json.loads((HERE / "fixtures.json").read_text(encoding="utf-8"))
    fixtures.append(
        {
            "name": "hkscs-free-japanese-unicode",
            "text": '[ ] T "日本語と𠮷と香港文字をUTF-8で読む"\n',
        }
    )
    (output / "fixtures.json").write_bytes(
        (
            json.dumps(
                [
                    {**fixture, "expected": check_text(fixture["text"])}
                    for fixture in fixtures
                ],
                ensure_ascii=False,
                indent=2,
            )
            + "\n"
        ).encode()
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("output", type=Path)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument(
        "--build",
        action="store_true",
        help="archive argument is a verified source cache directory",
    )
    modes.add_argument(
        "--probe",
        action="store_true",
        help="stage a candidate runtime directory for local Core/browser probes",
    )
    args = parser.parse_args()
    if args.probe:
        stage_probe(args.archive, args.output)
    elif args.build:
        print(prepare_build(args.archive, args.output))
    else:
        prepare(args.archive, args.output)
