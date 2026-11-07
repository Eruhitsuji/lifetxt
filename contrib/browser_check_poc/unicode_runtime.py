"""Stage a separate, unapproved Unicode-minimal Pyodide build (#1530).

No downloads or compilation are implicit. The caller supplies fixed source
archives and installs the pinned SDK/host before running the documented make.
"""

import argparse
import hashlib
import gzip
import json
from pathlib import Path, PurePosixPath
import shutil
import tarfile

from contrib.browser_check_poc import unicode_minimal

HERE = Path(__file__).resolve().parent
INPUTS = HERE / "profiles/unicode-minimal-3/inputs.json"
DISABLED = (
    "_multibytecodec",
    "_codecs_cn",
    "_codecs_jp",
    "_codecs_kr",
    "_codecs_tw",
    "_codecs_iso2022",
)  # _codecs_hk is already disabled.


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _members(path, root):
    """Validate pinned source archives before extracting, never follow links."""
    seen = set()
    total = 0
    with path.open("rb") as raw, gzip.GzipFile(fileobj=raw) as expanded:
        with tarfile.open(
            fileobj=unicode_minimal._BoundedReader(expanded), mode="r|"
        ) as archive:
            members = []
            for member in archive:
                members.append(member)
                parts = PurePosixPath(member.name).parts
                if (
                    not parts
                    or parts[0] != root
                    or ".." in parts
                    or member.name.startswith("/")
                    or "\\" in member.name
                ):
                    raise ValueError("unsafe source member path")
                normalized = "/".join(parts)
                if normalized in seen:
                    raise ValueError("duplicate source member")
                seen.add(normalized)
                safe_test_link = (
                    root == "cpython-source-deps-zstd-1.5.7"
                    and member.issym()
                    and member.linkname == "zstd"
                    and "/".join(parts[1:])
                    in ("tests/cli-tests/bin/unzstd", "tests/cli-tests/bin/zstdcat")
                )
                if not (member.isfile() or member.isdir() or safe_test_link) or (
                    member.isfile() and len(parts) < 2
                ):
                    raise ValueError("non-regular source member")
                total += member.size
                if (
                    member.size < 0
                    or member.size > 32 * 1024 * 1024
                    or total > 512 * 1024 * 1024
                    or len(seen) > 16384
                ):
                    raise ValueError("source archive resource budget exceeded")
    return members


def _once(body, before, after):
    if body.count(before) != 1:
        raise ValueError("unexpected build recipe anchor: " + before)
    return body.replace(before, after)


def _disable_builtins(body):
    """Append only to a single, terminal disabled section; ignore comments."""
    lines = [line.split("#", 1)[0].strip() for line in body.splitlines()]
    sections = [
        (index, line) for index, line in enumerate(lines) if line.startswith("*")
    ]
    disabled = [index for index, line in sections if line == "*disabled*"]
    if len(disabled) != 1 or sections[-1] != (disabled[0], "*disabled*"):
        raise ValueError("expected one terminal builtin disable section")
    tail = [line for line in lines[disabled[0] + 1 :] if line]
    if tail.count("_codecs_hk") != 1 or any(
        line.split()[0] in DISABLED for line in tail
    ):
        raise ValueError("unexpected disabled builtin entries")
    return (
        body
        + "\n# Isolated Unicode-minimal candidate (#1530)\n"
        + "\n".join(DISABLED)
        + "\n"
    )


def stage(sources, output):
    """Prepare only new files under a fresh trusted-parent output directory."""
    if output.exists() or output.is_symlink():
        raise FileExistsError(output)
    lock = json.loads(INPUTS.read_text(encoding="utf-8"))
    entries = {entry["id"]: entry for entry in lock["archives"]}
    # Snapshot the archives so validation and extraction consume the same bytes.
    # All failures before mkdir are read-only; later failures leave an explicitly
    # incomplete directory which must not be compiled or overwritten on retry.
    for entry in entries.values():
        path = sources / entry["file"]
        if path.stat().st_size != entry["bytes"] or sha256(path) != entry["sha256"]:
            raise ValueError("source input differs from pin: " + entry["id"])
        _members(path, entry["root"])
    output.mkdir(parents=True)
    (output / "INCOMPLETE").write_text(
        "Do not compile until stage completes.\n", encoding="utf-8", newline="\n"
    )
    snapshot = output / "inputs"
    snapshot.mkdir()
    for entry in entries.values():
        dest = snapshot / entry["file"]
        shutil.copyfile(sources / entry["file"], dest)
        if sha256(dest) != entry["sha256"]:
            raise ValueError("source input changed during snapshot")
    source_receipt = unicode_minimal.curate(
        snapshot / entries["cpython"]["file"], output / "cpython-unicode-minimal.tar.gz"
    )
    pyodide = entries["pyodide"]
    with tarfile.open(snapshot / pyodide["file"], "r:gz") as archive:
        archive.extractall(output, filter="data")
    root = output / pyodide["root"]
    setup = root / "cpython/Setup.local"
    body = setup.read_text(encoding="utf-8")
    setup.write_text(_disable_builtins(body), encoding="utf-8", newline="\n")
    downloads = root / "cpython/downloads"
    downloads.mkdir()
    shutil.copyfile(
        output / "cpython-unicode-minimal.tar.gz", downloads / "Python-3.14.2.tgz"
    )
    makefile = root / "cpython/Makefile"
    body = makefile.read_text(encoding="utf-8")
    for component, variable, repository, commit in [
        ("libffi", "FFIBUILD", "LIBFFIREPO", "LIBFFI_COMMIT"),
        ("hiwire", "HIWIREBUILD", "HIWIREREPO", "HIWIRE_COMMIT"),
    ]:
        before = f"&& git init \\\n\t\t&& git fetch --depth 1 $({repository}) $({commit}) \\\n\t\t&& git checkout FETCH_HEAD"
        body = _once(
            body,
            before,
            f"&& tar -xzf $(ROOT)/downloads/{entries[component]['file']} --strip-components=1",
        )
    for component in ("libffi", "hiwire", "xz", "zstd", "sqlite"):
        shutil.copyfile(
            snapshot / entries[component]["file"],
            downloads / entries[component]["file"],
        )
    makefile.write_text(body, encoding="utf-8", newline="\n")
    envs = root / "Makefile.envs"
    envs.write_text(
        _once(
            envs.read_text(encoding="utf-8"),
            "export PYTHON_ARCHIVE_SHA256=c609e078adab90e2c6bacb6afafacd5eaf60cd94cf670f1e159565725fcd448d",
            "export PYTHON_ARCHIVE_SHA256=" + source_receipt["output_sha256"],
        ),
        encoding="utf-8",
        newline="\n",
    )
    build_env = root / "pyodide_env.sh"
    build_env.write_text(
        _once(
            build_env.read_text(encoding="utf-8"),
            "export _EMCC_CCACHE=1",
            "export _EMCC_CCACHE=",
        ),
        encoding="utf-8",
        newline="\n",
    )
    # Actual builder smoke found that zipfile requires cp437 for legacy ZIP
    # filenames, including plain ASCII names without the UTF-8 flag. Preserve
    # the reviewed 18-codec CPython archive; add this one verified file via the
    # stdlib packaging overlay, with its original CPython licence retained.
    with tarfile.open(snapshot / entries["cpython"]["file"], "r:gz") as archive:
        cp437 = archive.extractfile(
            entries["cpython"]["root"] + "/Lib/encodings/cp437.py"
        ).read()
        licence = archive.extractfile(entries["cpython"]["root"] + "/LICENSE").read()
    if hashlib.sha256(cp437).hexdigest() != lock["internal_cp437_sha256"]:
        raise ValueError("internal cp437 source differs from pin")
    overlay = root / "tools/unicode_stdlib_overlay/encodings"
    overlay.mkdir(parents=True)
    (overlay / "cp437.py").write_bytes(cp437)
    (root / "tools/unicode_cp437.LICENSE").write_bytes(licence)
    root_make = root / "Makefile"
    body = root_make.read_text(encoding="utf-8")
    body = _once(
        body,
        "dist/python_stdlib.zip: tools/hkscs_free_build.py ",
        "dist/python_stdlib.zip: tools/unicode_stdlib_overlay/encodings/cp437.py tools/hkscs_free_build.py ",
    )
    body = _once(
        body,
        "tools/hkscs_free_build.py stdlib $(CPYTHONLIB) src/py ",
        "tools/hkscs_free_build.py stdlib $(CPYTHONLIB) src/py tools/unicode_stdlib_overlay ",
    )
    root_make.write_text(body, encoding="utf-8", newline="\n")
    (root / "LIFETXT_UNICODE_MODIFICATIONS.md").write_text(
        "# Isolated lifetxt Unicode-minimal candidate (2026-11-07)\n\n"
        "This modifies the delivered HKSCS-free Pyodide source. Original MPL-2.0\n"
        "and vendored notices remain. Disable all CJK builtins/_multibytecodec;\n"
        "consume the fixed source-only Unicode CPython archive; use supplied\n"
        "libffi/hiwire archives and no compiler cache. Add one cp437 stdlib\n"
        "overlay from the fixed CPython source for zipfile internal filenames,\n"
        "retaining its original bytes and tools/unicode_cp437.LICENSE.\n"
        "cp437 file SHA-256: " + lock["internal_cp437_sha256"] + "\n\n"
        "Not an approved distribution. Independent source/object/WASM and\n"
        "licence review, complete corresponding source and Owner approval remain.\n",
        encoding="utf-8",
        newline="\n",
    )
    staged_files = {
        p.relative_to(root).as_posix(): sha256(p)
        for p in sorted(root.rglob("*"))
        if p.is_file()
    }
    staged_digest = hashlib.sha256(
        json.dumps(staged_files, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    if staged_digest != lock["expected_staged_files_sha256"]:
        raise ValueError("staged source receipt differs from pinned baseline")
    receipt = {
        "schema_version": 1,
        "profile": lock["profile"],
        "source_receipt": source_receipt,
        "staged_files_sha256": staged_files,
        "staged_files_digest": staged_digest,
        "inputs_lock_sha256": sha256(INPUTS),
        "disabled_builtins": ["_codecs_hk", *DISABLED],
        "internal_cp437_sha256": lock["internal_cp437_sha256"],
        "runtime_verified": False,
        "complete_distribution_audit": False,
        "public_distribution_approved": False,
    }
    (output / "stage-receipt.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    (output / "INCOMPLETE").unlink()
    return root


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("sources", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    print(stage(args.sources, args.output))


if __name__ == "__main__":
    main()
